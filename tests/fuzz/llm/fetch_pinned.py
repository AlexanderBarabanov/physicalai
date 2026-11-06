# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Download the pinned llama.cpp build or GGUF model and verify its SHA-256 before use.

Usage: ``python fetch_pinned.py {model,llama_cpp} <dest_dir>``. Prints the model file path or the
``llama-server`` path on stdout; progress goes to stderr. Pins come from ``model.lock.toml``. Fields are
validated before they are put in a URL, only https is used, and no credential is sent.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tarfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parent / "model.lock.toml"

_MAX_LLAMA_ARCHIVE_BYTES = 512 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*")


class LockError(ValueError):
    """The lock file is missing a field or holds a malformed value."""


class VerifyError(RuntimeError):
    """A downloaded file does not match its pinned size or SHA-256."""


class _HttpsOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN201, PLR0913
        if urllib.parse.urlsplit(newurl).scheme != "https":
            reason = f"refusing non-https redirect to {newurl}"
            raise urllib.error.URLError(reason)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _field(table: dict[str, object], key: str, pattern: re.Pattern[str]) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not pattern.fullmatch(value):
        msg = f"lock field {key!r} is missing or malformed"
        raise LockError(msg)
    return value


def load_lock(path: Path = LOCK_PATH) -> dict[str, dict[str, object]]:
    """Load and validate the lock file.

    Raises:
        LockError: If any pinned field is missing or malformed.
    """
    with path.open("rb") as handle:
        lock = tomllib.load(handle)
    model, llama = lock.get("model"), lock.get("llama_cpp")
    if not isinstance(model, dict) or not isinstance(llama, dict):
        msg = "lock file needs [model] and [llama_cpp] tables"
        raise LockError(msg)
    _field(model, "repo", _REPO)
    _field(model, "revision", _COMMIT)
    _field(model, "file", _NAME)
    _field(model, "sha256", _SHA256)
    size = model.get("size_bytes")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        msg = "lock field 'size_bytes' must be a positive integer"
        raise LockError(msg)
    _field(llama, "tag", _NAME)
    _field(llama, "asset", _NAME)
    _field(llama, "sha256", _SHA256)
    return {"model": model, "llama_cpp": llama}


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, dest: Path, sha256: str, max_bytes: int) -> None:
    """Download ``url`` to ``dest`` and check its SHA-256; reuse ``dest`` if it already matches.

    Raises:
        VerifyError: If the download exceeds ``max_bytes`` or its hash differs from ``sha256``.
    """
    if dest.is_file() and sha256_file(dest) == sha256:
        print(f"using verified {dest}", file=sys.stderr)
        return
    if urllib.parse.urlsplit(url).scheme != "https":
        msg = "only https downloads are allowed"
        raise VerifyError(msg)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    size = 0
    print(f"downloading {url}", file=sys.stderr)
    opener = urllib.request.build_opener(_HttpsOnlyRedirect)
    try:
        with opener.open(urllib.request.Request(url), timeout=60) as response, partial.open("wb") as out:  # noqa: S310
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                size += len(chunk)
                if size > max_bytes:
                    msg = f"download exceeds {max_bytes} bytes"
                    raise VerifyError(msg)
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != sha256:
            msg = f"SHA-256 mismatch for {dest.name}: got {digest.hexdigest()}"
            raise VerifyError(msg)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(dest)


def fetch_model(dest_dir: Path) -> Path:
    """Download the pinned GGUF file.

    Returns:
        The verified model path.
    """
    model = load_lock()["model"]
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['file']}"
    path = dest_dir / str(model["file"])
    download_verified(url, path, str(model["sha256"]), int(model["size_bytes"]))  # type: ignore[arg-type]
    return path


def fetch_llama_cpp(dest_dir: Path) -> Path:
    """Download, verify, and extract the pinned llama.cpp build.

    Returns:
        The path to ``llama-server``.

    Raises:
        VerifyError: If the archive holds no ``llama-server`` binary.
    """
    llama = load_lock()["llama_cpp"]
    url = f"https://github.com/ggml-org/llama.cpp/releases/download/{llama['tag']}/{llama['asset']}"
    archive = dest_dir / str(llama["asset"])
    download_verified(url, archive, str(llama["sha256"]), _MAX_LLAMA_ARCHIVE_BYTES)
    target = dest_dir / "llama-cpp"
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(target, filter="data")  # the data filter rejects absolute paths and traversal
    server = next((path for path in sorted(target.rglob("llama-server")) if path.is_file()), None)
    if server is None:
        msg = "archive contains no llama-server binary"
        raise VerifyError(msg)
    return server


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        ``0`` on success, ``1`` on a verification or lock error, ``2`` on a usage error.
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in {"model", "llama_cpp"}:  # noqa: PLR2004
        print("usage: fetch_pinned.py {model,llama_cpp} <dest_dir>", file=sys.stderr)
        return 2
    try:
        fetch = fetch_model if args[0] == "model" else fetch_llama_cpp
        print(fetch(Path(args[1])))
    except (LockError, VerifyError, urllib.error.URLError, OSError, tarfile.TarError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
