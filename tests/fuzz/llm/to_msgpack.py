# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Convert untrusted JSON (for example LLM output) into MessagePack seed bytes.

A JSON object of the form ``{"$bytes": "<base64>"}`` becomes a MessagePack ``bin`` value; every other
JSON value maps to its MessagePack equivalent. The converter enforces its own caps and never trusts
sizes stated in the input. Byte-level corruption is left to the fuzzer.

Usage: ``python to_msgpack.py <in_dir> <out_dir>`` converts every ``*.json`` file to ``<stem>.bin``.
"""

from __future__ import annotations

import base64
import binascii
import json
import sys
from pathlib import Path

import msgpack

from physicalai.transport._codec import DEFAULT_MAX_PAYLOAD_DEPTH

# A few levels above the codec's gate so the depth check stays reachable by seeds and mutation.
MAX_DEPTH = DEFAULT_MAX_PAYLOAD_DEPTH + 4
MAX_DECODED_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 64 * 1024
# Base64 of MAX_DECODED_BYTES plus slack for container syntax and whitespace.
MAX_INPUT_BYTES = 256 * 1024

_BYTES_KEY = "$bytes"
_MAX_BASE64_CHARS = (MAX_DECODED_BYTES + 2) // 3 * 4


class ConversionError(ValueError):
    """The JSON input is malformed or exceeds a converter cap."""


def _convert_value(value: object, depth: int, budget: list[int]) -> object:
    """Return ``value`` with ``$bytes`` objects replaced by ``bytes``.

    Raises:
        ConversionError: If nesting, decoded size, or a ``$bytes`` object is invalid.
    """
    if isinstance(value, dict):
        if _BYTES_KEY in value:
            return _decode_bytes(value, budget)
        if depth > MAX_DEPTH:
            msg = f"nesting exceeds {MAX_DEPTH} levels"
            raise ConversionError(msg)
        return {key: _convert_value(item, depth + 1, budget) for key, item in value.items()}
    if isinstance(value, list):
        if depth > MAX_DEPTH:
            msg = f"nesting exceeds {MAX_DEPTH} levels"
            raise ConversionError(msg)
        return [_convert_value(item, depth + 1, budget) for item in value]
    return value


def _decode_bytes(value: dict[str, object], budget: list[int]) -> bytes:
    encoded = value[_BYTES_KEY]
    if len(value) != 1 or not isinstance(encoded, str):
        msg = f"{_BYTES_KEY!r} must be the only key and hold a base64 string"
        raise ConversionError(msg)
    if len(encoded) > _MAX_BASE64_CHARS:
        msg = f"{_BYTES_KEY!r} value exceeds the {MAX_DECODED_BYTES}-byte decoded cap"
        raise ConversionError(msg)
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        msg = f"{_BYTES_KEY!r} value is not valid base64"
        raise ConversionError(msg) from error
    budget[0] += len(decoded)
    if budget[0] > MAX_DECODED_BYTES:
        msg = f"decoded bytes exceed the {MAX_DECODED_BYTES}-byte cap"
        raise ConversionError(msg)
    return decoded


def convert(value: object) -> bytes:
    """Pack a parsed JSON value as MessagePack, applying all caps.

    Returns:
        MessagePack bytes no longer than ``MAX_OUTPUT_BYTES``.

    Raises:
        ConversionError: If the value exceeds a cap or cannot be packed.
    """
    converted = _convert_value(value, 0, [0])
    try:
        packed = msgpack.packb(converted, use_bin_type=True)
    except (TypeError, ValueError, OverflowError) as error:
        msg = f"cannot pack as MessagePack: {error}"
        raise ConversionError(msg) from error
    if not isinstance(packed, bytes) or len(packed) > MAX_OUTPUT_BYTES:
        msg = f"output exceeds the {MAX_OUTPUT_BYTES}-byte cap"
        raise ConversionError(msg)
    return packed


def convert_json(data: bytes) -> bytes:
    """Parse untrusted JSON bytes and convert them with :func:`convert`.

    Returns:
        MessagePack bytes.

    Raises:
        ConversionError: If the input is not valid JSON or exceeds a cap.
    """
    if len(data) > MAX_INPUT_BYTES:
        msg = f"input exceeds the {MAX_INPUT_BYTES}-byte cap"
        raise ConversionError(msg)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError) as error:
        msg = f"invalid JSON: {error}"
        raise ConversionError(msg) from error
    return convert(parsed)


def _read_capped(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read(MAX_INPUT_BYTES + 1)


def convert_dir(in_dir: Path, out_dir: Path) -> int:
    """Convert every regular ``*.json`` file in ``in_dir`` to ``<stem>.bin`` in ``out_dir``.

    Returns:
        The number of rejected files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rejected = 0
    for path in sorted(in_dir.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            print(f"skipped {path}: not a regular file", file=sys.stderr)
            rejected += 1
            continue
        try:
            packed = convert_json(_read_capped(path))
        except ConversionError as error:
            print(f"rejected {path.name}: {error}", file=sys.stderr)
            rejected += 1
            continue
        (out_dir / f"{path.stem}.bin").write_bytes(packed)
    return rejected


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Returns:
        ``0`` if every file converted, ``1`` if any was rejected, ``2`` on a usage error.
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:  # noqa: PLR2004
        print("usage: to_msgpack.py <in_dir> <out_dir>", file=sys.stderr)
        return 2
    in_dir = Path(args[0])
    if not in_dir.is_dir():
        print(f"not a directory: {in_dir}", file=sys.stderr)
        return 2
    return 1 if convert_dir(in_dir, Path(args[1])) else 0


if __name__ == "__main__":
    sys.exit(main())
