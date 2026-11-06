# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Generate fuzz seeds with a local LLM served by ``llama-server`` (OpenAI-compatible API).

The model returns JSON only. Deterministic code turns each JSON seed into bytes, enforces the caps from
``to_msgpack`` and drops anything it rejects. Model output is untrusted data: it is never executed, imported,
or used as configuration. The endpoint must be a loopback address and no credential is ever sent.

Usage: ``python generate_seeds.py --harness {manifest_json,remote_raw} --count N [--endpoint URL] [--seed S]``
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.fuzz.llm import to_msgpack  # noqa: E402
from tests.fuzz.llm.to_msgpack import ConversionError  # noqa: E402

HARNESSES = ("manifest_json", "remote_raw")
DEFAULT_ENDPOINT = "http://127.0.0.1:8080"

_LLM_DIR = Path(__file__).resolve().parent
_FUZZ_DIR = _LLM_DIR.parent
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_MAX_COUNT = 10_000
_MERGE_TIMEOUT_S = 1800
# Same limits as fuzz.yml so merged inputs are not truncated.
_MERGE_FLAGS = ("-merge=1", "-max_len=65536", "-timeout=30", "-rss_limit_mb=2048")


class EndpointError(ValueError):
    """The endpoint is not a loopback URL without credentials."""


class GenerationError(RuntimeError):
    """The LLM endpoint failed or returned an unusable HTTP response."""


class MergeError(RuntimeError):
    """The libFuzzer merge step failed."""


@dataclass
class Stats:
    """Counters behind the Y metrics."""

    calls: int = 0
    valid_calls: int = 0
    received: int = 0
    accepted: int = 0
    duplicates: int = 0
    completion_tokens: int = 0
    request_seconds: float = 0.0

    def rates(self) -> dict[str, float]:
        """Return the JSON-valid, converter-accepted, and duplicate rates (0.0 when undefined)."""
        return {
            "json_valid_rate": self.valid_calls / self.calls if self.calls else 0.0,
            "converter_accepted_rate": self.accepted / self.received if self.received else 0.0,
            "duplicate_rate": self.duplicates / self.accepted if self.accepted else 0.0,
        }


def validate_endpoint(endpoint: str) -> str:
    """Return a normalized base URL for a loopback endpoint.

    Raises:
        EndpointError: If the scheme, host, or shape of the URL is not allowed.
    """
    parts = urllib.parse.urlsplit(endpoint)
    if parts.scheme not in {"http", "https"}:
        msg = "endpoint scheme must be http or https"
        raise EndpointError(msg)
    if parts.username or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}:
        msg = "endpoint must be scheme://host[:port] without credentials, path, or query"
        raise EndpointError(msg)
    host = parts.hostname
    if not host:
        msg = "endpoint has no host"
        raise EndpointError(msg)
    if host.lower() == "localhost":
        host = "127.0.0.1"  # avoid a name lookup that could resolve elsewhere
    else:
        try:
            address = ipaddress.ip_address(host)
        except ValueError as error:
            msg = "endpoint host must be localhost or a loopback IP address"
            raise EndpointError(msg) from error
        if not address.is_loopback:
            msg = f"endpoint host {host} is not a loopback address"
            raise EndpointError(msg)
        host = str(address)
    try:
        port = parts.port
    except ValueError as error:
        msg = "endpoint port is invalid"
        raise EndpointError(msg) from error
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return f"{parts.scheme}://{netloc}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so a loopback server cannot send the request elsewhere."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def _build_opener() -> urllib.request.OpenerDirector:
    # An empty ProxyHandler ignores proxy environment variables.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)


def _chat(
    opener: urllib.request.OpenerDirector,
    base_url: str,
    payload: dict[str, object],
    timeout: float,
) -> tuple[str, int, float]:
    """POST one chat completion; return the message content, completion tokens, and request seconds.

    Raises:
        GenerationError: On a transport error, an oversized response, or an unexpected response shape.
    """
    request = urllib.request.Request(  # noqa: S310 - base_url is validated loopback http(s)
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(_MAX_RESPONSE_BYTES + 1)
    except (OSError, http.client.HTTPException) as error:
        msg = f"LLM request failed: {error}"
        raise GenerationError(msg) from error
    elapsed = time.monotonic() - start
    if len(body) > _MAX_RESPONSE_BYTES:
        msg = f"LLM response exceeds {_MAX_RESPONSE_BYTES} bytes"
        raise GenerationError(msg)
    try:
        data = json.loads(body)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError) as error:
        msg = "LLM response has an unexpected shape"
        raise GenerationError(msg) from error
    if not isinstance(content, str):
        msg = "LLM message content is not a string"
        raise GenerationError(msg)
    tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    return content, tokens if isinstance(tokens, int) and tokens > 0 else 0, elapsed


def parse_seeds(content: str) -> list[object] | None:
    """Return the ``seeds`` list from the model's JSON reply, or ``None`` if the reply is unusable."""
    try:
        parsed = json.loads(content)
    except (ValueError, RecursionError):
        return None
    seeds = parsed.get("seeds") if isinstance(parsed, dict) else None
    return seeds if isinstance(seeds, list) else None


def _check_depth(value: object, depth: int = 0) -> None:
    if isinstance(value, (dict, list)):
        if depth > to_msgpack.MAX_DEPTH:
            msg = f"nesting exceeds {to_msgpack.MAX_DEPTH} levels"
            raise ConversionError(msg)
        for item in value.values() if isinstance(value, dict) else value:
            _check_depth(item, depth + 1)


def seed_to_bytes(harness: str, seed: object) -> bytes:
    """Convert one JSON seed to harness input bytes, applying the converter caps.

    Raises:
        ConversionError: If the seed is not a JSON object or exceeds a cap.
    """
    if not isinstance(seed, dict):
        msg = "seed must be a JSON object"
        raise ConversionError(msg)
    if harness == "remote_raw":
        return to_msgpack.convert(seed)
    _check_depth(seed)
    try:
        encoded = json.dumps(seed, separators=(",", ":")).encode("ascii")
    except (TypeError, ValueError, RecursionError) as error:
        msg = f"cannot serialize seed: {error}"
        raise ConversionError(msg) from error
    if len(encoded) > to_msgpack.MAX_OUTPUT_BYTES:
        msg = f"output exceeds the {to_msgpack.MAX_OUTPUT_BYTES}-byte cap"
        raise ConversionError(msg)
    return encoded


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _control_seed_bytes(harness: str) -> list[bytes]:
    if harness == "manifest_json":
        return [path.read_bytes() for path in sorted((_FUZZ_DIR / "seeds" / "fuzz_manifest").glob("*.json"))]
    return [
        to_msgpack.convert_json(path.read_bytes())
        for path in sorted((_LLM_DIR / "control" / "remote_raw").glob("*.json"))
    ]


def run_merge(harness: str, harness_dir: Path) -> int:
    """Merge generated seeds into a corpus holding the control seeds; move new files to ``added/``.

    Returns:
        M3, the number of generated seeds that added coverage.

    Raises:
        MergeError: If the fuzzer exits non-zero or times out.
    """
    merged, added = harness_dir / "merged", harness_dir / "added"
    merged.mkdir(exist_ok=True)
    added.mkdir(exist_ok=True)
    for data in _control_seed_bytes(harness):
        (merged / hashlib.sha256(data).hexdigest()).write_bytes(data)
    before = {path.name for path in merged.iterdir()}
    harness_path = (_FUZZ_DIR / "harnesses" / f"fuzz_{harness}.py").resolve()
    log_path = harness_dir / "merge.log"
    # libFuzzer re-executes argv[0] through sh in merge mode, so it must be an executable file.
    launcher = (harness_dir / "run_harness.py").resolve()
    launcher.write_text(
        f"#!{sys.executable}\nimport runpy\nrunpy.run_path({str(harness_path)!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    command = [str(launcher), *_MERGE_FLAGS, str(merged.resolve()), str((harness_dir / "raw").resolve())]
    with log_path.open("wb") as log:
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, no shell
                command,
                cwd=_REPO_ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=_MERGE_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            msg = f"merge timed out after {_MERGE_TIMEOUT_S}s; see {log_path}"
            raise MergeError(msg) from error
    if result.returncode != 0:
        msg = f"merge exited with code {result.returncode}; see {log_path}"
        raise MergeError(msg)
    # libFuzzer exits 0 even when every inner process failed; a retry means the merge did not work.
    if "MERGE-OUTER: attempt 2" in log_path.read_text(encoding="utf-8", errors="replace"):
        msg = f"merge inner process failed and was retried; see {log_path}"
        raise MergeError(msg)
    new_files = sorted(path for path in merged.iterdir() if path.name not in before)
    for path in new_files:
        shutil.move(str(path), added / path.name)
    return len(new_files)


def _generate(args: argparse.Namespace, base_url: str, prompt: str, harness_dir: Path) -> tuple[Stats, int, float]:
    raw_dir, responses_dir = harness_dir / "raw", harness_dir / "responses"
    raw_dir.mkdir(parents=True)
    responses_dir.mkdir()
    opener = _build_opener()
    stats = Stats()
    seen: set[str] = set()
    max_calls = args.max_calls or math.ceil(args.count / args.batch_size) * 3
    user_message = (
        f"Generate {args.batch_size} diverse seeds. "
        'Reply with one JSON object of the form {"seeds": [<seed>, ...]} and nothing else.'
    )
    start = time.monotonic()
    for index in range(max_calls):
        if len(seen) >= args.count:
            break
        payload = {
            "model": args.model,
            "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user_message}],
            "response_format": {"type": "json_object"},
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "seed": args.seed + index,
            "stream": False,
        }
        content, tokens, seconds = _chat(opener, base_url, payload, args.timeout)
        stats.calls += 1
        stats.completion_tokens += tokens
        stats.request_seconds += seconds
        (responses_dir / f"call_{index + 1:04d}.txt").write_bytes(content.encode("utf-8", "backslashreplace"))
        seeds = parse_seeds(content)
        if seeds is None:
            continue
        stats.valid_calls += 1
        for seed in seeds:
            if len(seen) >= args.count:
                break
            stats.received += 1
            try:
                data = seed_to_bytes(args.harness, seed)
            except ConversionError:
                continue
            stats.accepted += 1
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                stats.duplicates += 1
                continue
            seen.add(digest)
            (raw_dir / digest).write_bytes(data)
    return stats, len(seen), time.monotonic() - start


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--harness", choices=HARNESSES, required=True)
    parser.add_argument("--count", type=int, required=True, help="number of unique accepted seeds to produce")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="loopback llama-server base URL")
    parser.add_argument("--seed", type=int, default=0, help="base sampling seed; call i uses seed + i")
    parser.add_argument("--batch-size", type=int, default=5, help="seeds requested per call")
    parser.add_argument("--max-calls", type=int, default=0, help="call limit (default: 3 x calls needed)")
    parser.add_argument("--model", default="local", help="model name sent to the server")
    parser.add_argument("--model-file", type=Path, help="GGUF file; its SHA-256 is recorded in run.json")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=3072)
    parser.add_argument("--timeout", type=float, default=900.0, help="per-call timeout in seconds")
    parser.add_argument("--out-dir", type=Path, default=_LLM_DIR / "out")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing out/<harness> directory")
    parser.add_argument("--merge", action="store_true", help="run the libFuzzer merge step (Linux, needs Atheris)")
    args = parser.parse_args(argv)
    checks = (
        (1 <= args.count <= _MAX_COUNT, f"--count must be in 1..{_MAX_COUNT}"),
        (1 <= args.batch_size <= 50, "--batch-size must be in 1..50"),  # noqa: PLR2004
        (args.max_calls >= 0, "--max-calls must be non-negative"),
        (0 <= args.temperature <= 2, "--temperature must be in 0..2"),  # noqa: PLR2004
        (0 < args.top_p <= 1, "--top-p must be in (0, 1]"),
        (1 <= args.max_tokens <= 8192, "--max-tokens must be in 1..8192"),  # noqa: PLR2004
        (args.timeout > 0, "--timeout must be positive"),
        (0 <= args.seed < 2**31 - _MAX_COUNT * 3, "--seed is out of range"),
    )
    for ok, message in checks:
        if not ok:
            parser.error(message)
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the generator.

    Returns:
        ``0`` on success, ``1`` if generation or merging failed or no seed was produced, ``2`` on a usage error.
    """
    args = _parse_args(argv)
    try:
        base_url = validate_endpoint(args.endpoint)
    except EndpointError as error:
        print(f"refused endpoint: {error}", file=sys.stderr)
        return 2

    harness_dir = args.out_dir / args.harness
    if harness_dir.exists() and any(harness_dir.iterdir()):
        if not args.overwrite:
            print(f"{harness_dir} is not empty; pass --overwrite to replace it", file=sys.stderr)
            return 2
        shutil.rmtree(harness_dir)

    prompt_bytes = (_LLM_DIR / "prompts" / f"{args.harness}.md").read_bytes()
    try:
        stats, unique, seconds = _generate(args, base_url, prompt_bytes.decode("utf-8"), harness_dir)
    except GenerationError as error:
        print(str(error), file=sys.stderr)
        return 1

    minutes = seconds / 60
    run_info: dict[str, object] = {
        "harness": args.harness,
        "endpoint": base_url,
        "model": args.model,
        "model_file_sha256": _sha256_file(args.model_file) if args.model_file else None,
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "sampling": {
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "batch_size": args.batch_size,
        },
        "seed": args.seed,
        "counts": {
            "calls": stats.calls,
            "valid_calls": stats.valid_calls,
            "received": stats.received,
            "accepted": stats.accepted,
            "duplicates": stats.duplicates,
            "unique": unique,
        },
        "yield": stats.rates(),
        "generation_seconds": seconds,
        "seeds_per_minute": unique / minutes if minutes > 0 else None,
        "tokens_per_second": (
            stats.completion_tokens / stats.request_seconds if stats.completion_tokens and stats.request_seconds else None
        ),
        "merge_added": None,
    }

    status = 0 if unique else 1
    if args.merge and unique:
        try:
            run_info["merge_added"] = run_merge(args.harness, harness_dir)
        except MergeError as error:
            print(str(error), file=sys.stderr)
            status = 1
    (harness_dir / "run.json").write_text(json.dumps(run_info, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rates = stats.rates()
    print(
        f"harness={args.harness} calls={stats.calls} valid_calls={stats.valid_calls} received={stats.received} "
        f"accepted={stats.accepted} duplicates={stats.duplicates} unique={unique}",
    )
    print(
        f"Y: json_valid={rates['json_valid_rate']:.0%} converter_accepted={rates['converter_accepted_rate']:.0%} "
        f"duplicate={rates['duplicate_rate']:.0%}",
    )
    if run_info["merge_added"] is not None:
        print(f"M3: {run_info['merge_added']}")
    print(f"tokens_per_second={run_info['tokens_per_second']} seeds_per_minute={run_info['seeds_per_minute']}")
    return status


if __name__ == "__main__":
    sys.exit(main())
