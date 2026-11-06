# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the local LLM seed generator, using a loopback fake endpoint (no external network)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytest.importorskip("msgpack")

from tests.fuzz.llm import generate_seeds
from tests.fuzz.llm.generate_seeds import EndpointError, main, parse_seeds, seed_to_bytes, validate_endpoint
from tests.fuzz.llm.to_msgpack import MAX_OUTPUT_BYTES, ConversionError

_CONTROL_DIR = Path(__file__).parent / "control" / "remote_raw"
_REQUEST = json.loads((_CONTROL_DIR / "request_minimal.json").read_text(encoding="utf-8"))
_REQUEST_NP = json.loads((_CONTROL_DIR / "request_np_input.json").read_text(encoding="utf-8"))
_MANIFEST = {"format": "policy_package", "version": "1.0"}


class _FakeLLM:
    """A loopback HTTP server that replays queued chat-completion contents."""

    def __init__(self, contents: list[str], *, redirect: bool = False) -> None:
        self.contents = contents
        self.requests: list[dict[str, object]] = []
        self.headers: list[dict[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers["Content-Length"])
                outer.requests.append(json.loads(self.rfile.read(length)))
                outer.headers.append({key.lower(): value for key, value in self.headers.items()})
                if redirect:
                    self.send_response(302)
                    self.send_header("Location", "http://example.invalid/")
                    self.end_headers()
                    return
                index = min(len(outer.requests) - 1, len(outer.contents) - 1)
                body = json.dumps({
                    "choices": [{"message": {"content": outer.contents[index]}}],
                    "usage": {"completion_tokens": 10},
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> _FakeLLM:
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()


def _seeds(*seeds: object) -> str:
    return json.dumps({"seeds": list(seeds)})


def _run(tmp_path: Path, url: str, harness: str, *extra: str) -> int:
    return main([
        "--harness", harness, "--count", "3", "--endpoint", url, "--out-dir", str(tmp_path),
        "--batch-size", "4", "--max-calls", "2", "--timeout", "5", *extra,
    ])  # fmt: skip


def _run_info(tmp_path: Path, harness: str) -> dict[str, object]:
    return json.loads((tmp_path / harness / "run.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.com:8080",
        "http://192.168.1.5:8080",
        "http://0.0.0.0:8080",
        "http://user:secret@127.0.0.1:8080",
        "http://127.0.0.1:8080/v1",
        "http://127.0.0.1:8080?x=1",
        "ftp://127.0.0.1:8080",
        "http://localhost.example.com:8080",
        "127.0.0.1:8080",
    ],
)
def test_rejects_non_loopback_or_unsafe_endpoint(endpoint: str) -> None:
    with pytest.raises(EndpointError):
        validate_endpoint(endpoint)


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("http://127.0.0.1:8080/", "http://127.0.0.1:8080"),
        ("http://localhost:9", "http://127.0.0.1:9"),
        ("http://[::1]:9", "http://[::1]:9"),
    ],
)
def test_accepts_loopback_endpoint(endpoint: str, expected: str) -> None:
    assert validate_endpoint(endpoint) == expected


def test_main_refuses_non_loopback_endpoint_without_output(tmp_path: Path) -> None:
    assert _run(tmp_path, "http://example.com:8080", "manifest_json") == 2
    assert not (tmp_path / "manifest_json").exists()


def test_parse_seeds_rejects_unusable_replies() -> None:
    assert parse_seeds("not json") is None
    assert parse_seeds("[1, 2]") is None
    assert parse_seeds('{"seeds": "x"}') is None
    assert parse_seeds('{"seeds": [{}]}') == [{}]


def test_invalid_json_reply_yields_no_seeds(tmp_path: Path) -> None:
    with _FakeLLM(["this is not json"]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json") == 1

    info = _run_info(tmp_path, "manifest_json")
    assert info["counts"]["valid_calls"] == 0
    assert info["yield"]["json_valid_rate"] == 0.0
    assert list((tmp_path / "manifest_json" / "raw").iterdir()) == []


@pytest.mark.parametrize("harness", ["manifest_json", "remote_raw"])
def test_over_cap_and_non_object_seeds_are_rejected(harness: str) -> None:
    with pytest.raises(ConversionError):
        seed_to_bytes(harness, {"text": "x" * MAX_OUTPUT_BYTES})
    with pytest.raises(ConversionError):
        seed_to_bytes(harness, [1, 2, 3])


def test_remote_raw_rejects_bad_bytes_value(tmp_path: Path) -> None:
    bad = {"inputs": {"state": {"$bytes": "not base64!"}}}
    huge = {"text": "x" * MAX_OUTPUT_BYTES}
    with _FakeLLM([_seeds(bad, huge, _REQUEST)]) as llm:
        assert _run(tmp_path, llm.url, "remote_raw", "--count", "1") == 0

    info = _run_info(tmp_path, "remote_raw")
    assert info["counts"]["received"] == 3
    assert info["counts"]["accepted"] == 1


def test_generates_dedups_and_records_run_info(tmp_path: Path) -> None:
    model_file = tmp_path / "model.gguf"
    model_file.write_bytes(b"fake model")
    reply = _seeds(_REQUEST, _REQUEST, _REQUEST_NP, "not an object")
    with _FakeLLM([reply]) as llm:
        assert _run(tmp_path, llm.url, "remote_raw", "--model-file", str(model_file), "--seed", "7", "--max-calls", "1") == 0

    raw_files = sorted((tmp_path / "remote_raw" / "raw").iterdir())
    assert len(raw_files) == 2
    assert all(path.name == hashlib.sha256(path.read_bytes()).hexdigest() for path in raw_files)
    info = _run_info(tmp_path, "remote_raw")
    assert info["counts"] == {
        "calls": 1, "valid_calls": 1, "received": 4, "accepted": 3, "duplicates": 1, "unique": 2,
    }  # fmt: skip
    assert info["yield"]["converter_accepted_rate"] == 0.75
    assert info["model_file_sha256"] == hashlib.sha256(b"fake model").hexdigest()
    prompt = (Path(generate_seeds.__file__).parent / "prompts" / "remote_raw.md").read_bytes()
    assert info["prompt_sha256"] == hashlib.sha256(prompt).hexdigest()
    assert info["seed"] == 7
    assert info["tokens_per_second"] > 0
    assert info["seeds_per_minute"] > 0
    assert info["merge_added"] is None


def test_manifest_json_seeds_are_written_as_json(tmp_path: Path) -> None:
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json") == 0

    (seed_file,) = (tmp_path / "manifest_json" / "raw").iterdir()
    assert json.loads(seed_file.read_bytes()) == _MANIFEST


def test_request_has_no_credentials_and_asks_for_json_object(tmp_path: Path) -> None:
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        _run(tmp_path, llm.url, "manifest_json", "--seed", "5")

    body, headers = llm.requests[0], llm.headers[0]
    assert "authorization" not in headers
    assert body["response_format"] == {"type": "json_object"}
    assert body["seed"] == 5
    assert body["messages"][0]["role"] == "system"
    assert "Manifest.model_validate" in body["messages"][0]["content"]


def test_redirect_is_not_followed(tmp_path: Path) -> None:
    with _FakeLLM([], redirect=True) as llm:
        assert _run(tmp_path, llm.url, "manifest_json") == 1

    assert len(llm.requests) == 1


def test_refuses_existing_output_unless_overwrite(tmp_path: Path) -> None:
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json") == 0
        assert _run(tmp_path, llm.url, "manifest_json") == 2
        assert _run(tmp_path, llm.url, "manifest_json", "--overwrite") == 0


def test_merge_moves_new_files_to_added(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_merge(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        assert "-merge=1" in command
        launcher = Path(command[0])
        assert launcher.read_text(encoding="utf-8").startswith("#!")
        assert "fuzz_manifest_json.py" in launcher.read_text(encoding="utf-8")
        if os.name == "posix":
            assert os.access(launcher, os.X_OK)
        merged_dir = Path(command[-2])
        assert list(merged_dir.iterdir()), "control seeds must be in the merge target first"
        (merged_dir / "new_coverage_seed").write_bytes(b"{}")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(generate_seeds.subprocess, "run", fake_merge)
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json", "--merge") == 0

    harness_dir = tmp_path / "manifest_json"
    assert [path.name for path in (harness_dir / "added").iterdir()] == ["new_coverage_seed"]
    assert not (harness_dir / "merged" / "new_coverage_seed").exists()
    assert _run_info(tmp_path, "manifest_json")["merge_added"] == 1


def test_merge_with_retried_inner_process_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_merge(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        kwargs["stdout"].write(b"MERGE-OUTER: attempt 1\nMERGE-OUTER: attempt 2\n")  # type: ignore[attr-defined]
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(generate_seeds.subprocess, "run", fake_merge)
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json", "--merge") == 1

    assert not list((tmp_path / "manifest_json" / "added").iterdir())


def test_merge_failure_returns_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        generate_seeds.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 77),
    )
    with _FakeLLM([_seeds(_MANIFEST)]) as llm:
        assert _run(tmp_path, llm.url, "manifest_json", "--merge") == 1


@pytest.mark.parametrize("harness", ["manifest_json", "remote_raw"])
def test_prompt_files_exist(harness: str) -> None:
    prompt = Path(generate_seeds.__file__).parent / "prompts" / f"{harness}.md"

    assert prompt.stat().st_size < 12_000  # keep room for output in an 8k context
