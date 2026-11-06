# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the pinned model and binary fetcher (no network access)."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from tests.fuzz.llm import fetch_pinned
from tests.fuzz.llm.fetch_pinned import LockError, VerifyError, download_verified, load_lock, sha256_file


def _write_lock(path: Path, **overrides: str) -> Path:
    values = {
        "repo": "owner/name",
        "revision": "a" * 40,
        "file": "model.gguf",
        "model_sha": "b" * 64,
        "tag": "b1",
        "asset": "llama.tar.gz",
        "llama_sha": "c" * 64,
    } | overrides
    path.write_text(
        f"""
[model]
repo = "{values['repo']}"
revision = "{values['revision']}"
file = "{values['file']}"
sha256 = "{values['model_sha']}"
size_bytes = 10

[llama_cpp]
tag = "{values['tag']}"
asset = "{values['asset']}"
sha256 = "{values['llama_sha']}"
""",
        encoding="utf-8",
    )
    return path


def _tar(path: Path, *names: str) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))


def _patch_download(monkeypatch: pytest.MonkeyPatch, archive: Path) -> None:
    lock = load_lock(_write_lock(archive.with_suffix(".toml")))
    monkeypatch.setattr(fetch_pinned, "load_lock", lambda: lock)
    monkeypatch.setattr(fetch_pinned, "download_verified", lambda _url, dest, *_args: dest.write_bytes(archive.read_bytes()))


def test_checked_in_lock_is_valid() -> None:
    lock = load_lock()

    assert lock["model"]["file"].endswith(".gguf")
    assert lock["llama_cpp"]["asset"].endswith(".tar.gz")


@pytest.mark.parametrize(
    "override",
    [
        {"model_sha": "REPLACE_ME"},
        {"llama_sha": "C" * 64},
        {"revision": "main"},
        {"file": "../evil.gguf"},
        {"repo": "owner/name/extra"},
        {"tag": "b1/../x"},
        {"asset": "a b"},
    ],
)
def test_malformed_lock_fields_are_rejected(tmp_path: Path, override: dict[str, str]) -> None:
    with pytest.raises(LockError):
        load_lock(_write_lock(tmp_path / "lock.toml", **override))


def test_existing_file_with_matching_hash_is_reused(tmp_path: Path) -> None:
    path = tmp_path / "model.gguf"
    path.write_bytes(b"model")

    download_verified("https://example.invalid/model", path, sha256_file(path), 100)

    assert path.read_bytes() == b"model"


def test_non_https_download_is_refused(tmp_path: Path) -> None:
    with pytest.raises(VerifyError, match="https"):
        download_verified("http://example.invalid/model", tmp_path / "model.gguf", "0" * 64, 100)


def test_extraction_finds_llama_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source" / "release.tar.gz"
    source.parent.mkdir()
    _tar(source, "llama-b1/llama-server")
    _patch_download(monkeypatch, source)

    server = fetch_pinned.fetch_llama_cpp(tmp_path / "dest")

    assert server.name == "llama-server"
    assert server.is_relative_to(tmp_path / "dest")


def test_extraction_rejects_path_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source" / "release.tar.gz"
    source.parent.mkdir()
    _tar(source, "../escaped")
    _patch_download(monkeypatch, source)

    with pytest.raises(tarfile.TarError):
        fetch_pinned.fetch_llama_cpp(tmp_path / "dest")

    assert not (tmp_path / "escaped").exists()
