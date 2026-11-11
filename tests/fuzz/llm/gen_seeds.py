# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Generate fuzz seeds with a small local LLM (llama.cpp).

Best-effort: every failure path exits 0 so the fuzzer still runs with its static seeds.
Run in an isolated env (``uv run --no-project --with llama-cpp-python``); it must not import project code.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_THEMES_MARKER = "\n### THEMES\n"
_MAX_SEED_BYTES = 65536  # keep in sync with -max_len in fuzz.yml
_SYSTEM = "You generate test inputs for a fuzzer. Reply with exactly one JSON object and nothing else."


def _encode_manifest(obj: Any) -> bytes:  # noqa: ANN401
    # fuzz_manifest.test_one_input: byte 0 bit 0 picks the raw-JSON path; byte 1 bit 0 makes
    # ConsumeUnicodeNoSurrogates read the rest as ASCII (atheris src/native/fuzzed_data_provider.cc).
    return b"\x01\x01" + json.dumps(obj, ensure_ascii=True).encode("ascii")


_ENCODERS = {"manifest": _encode_manifest}


def _read(path: Path | None) -> str:
    return path.read_text(encoding="utf-8").strip() if path else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", required=True, choices=sorted(_ENCODERS))
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--schema", type=Path, help="JSON schema text injected into the prompt")
    parser.add_argument("--example", type=Path, help="One valid input shown to the model")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, help="Write attempts.jsonl and a copy of the seeds here (debugging)")
    parser.add_argument("--n", type=int, default=40, help="Target number of seeds")
    parser.add_argument("--budget-s", type=float, default=180.0, help="Wall-clock cap for generation")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    prompt_file = Path(__file__).parent / "prompts" / f"{args.harness}.txt"
    template, _, themes_text = prompt_file.read_text(encoding="utf-8").partition(_THEMES_MARKER)
    themes = [line.strip() for line in themes_text.splitlines() if line.strip()]
    template = template.replace("{schema}", _read(args.schema)).replace("{example}", _read(args.example))
    encode = _ENCODERS[args.harness]

    try:
        from llama_cpp import Llama  # noqa: PLC0415

        llm = Llama(model_path=str(args.model), n_ctx=4096, n_threads=args.threads, seed=args.seed, verbose=False)
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::LLM seed generation unavailable: {exc!r}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    report = None
    if args.report_dir:
        (args.report_dir / "seeds").mkdir(parents=True, exist_ok=True)
        report = (args.report_dir / "attempts.jsonl").open("w", encoding="utf-8")

    start = time.monotonic()
    written = 0
    statuses: Counter[str] = Counter()
    tokens = 0
    # Allow 2x attempts: small models occasionally emit truncated or oversized JSON.
    for i, theme in zip(range(args.n * 2), itertools.cycle(themes), strict=False):
        if written >= args.n or time.monotonic() - start > args.budget_s:
            break
        began = time.monotonic()
        entry: dict[str, Any] = {"attempt": i, "theme": theme}
        raw = ""
        try:
            reply = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    # Theme goes last so the shared prompt prefix stays in the KV cache.
                    {"role": "user", "content": template.replace("{theme}", theme)},
                ],
                response_format={"type": "json_object"},
                temperature=0.9,
                top_p=0.95,
                max_tokens=1024,
                seed=args.seed + i,
            )
            raw = reply["choices"][0]["message"]["content"]
            entry["completion_tokens"] = reply.get("usage", {}).get("completion_tokens", 0)
            tokens += entry["completion_tokens"]
            obj = json.loads(raw)
            data = encode(obj)
        except (ValueError, KeyError, IndexError, RuntimeError) as exc:
            entry.update(status="error", error=repr(exc), raw=raw[:2000])
        else:
            if len(data) > _MAX_SEED_BYTES:
                entry.update(status="too_large", bytes=len(data))
            else:
                name = f"llm-{written:03d}.bin"
                (args.out / name).write_bytes(data)
                if args.report_dir:
                    (args.report_dir / "seeds" / name).write_bytes(data)
                written += 1
                entry.update(status="ok", seed=name, bytes=len(data), json=obj)
        entry["seconds"] = round(time.monotonic() - began, 1)
        statuses[entry["status"]] += 1
        print(f"[{i:02d}] {entry['status']:<9} {entry['seconds']:>5.1f}s theme={theme[:60]!r}", flush=True)
        if report:
            report.write(json.dumps(entry) + "\n")
            report.flush()

    elapsed = time.monotonic() - start
    print(
        f"Generated {written} LLM seeds in {elapsed:.0f}s -> {args.out} "
        f"(attempts: {dict(statuses)}, {tokens / max(elapsed, 1e-9):.1f} tok/s)",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
