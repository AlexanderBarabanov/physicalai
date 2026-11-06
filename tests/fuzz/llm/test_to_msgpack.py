# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Tests for the JSON-to-MessagePack seed converter and the ``remote_raw`` control seeds."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

msgpack = pytest.importorskip("msgpack")
pytest.importorskip("zenoh")  # imported by physicalai.inference.remote
from physicalai.inference.remote._protocol import decode_message, decode_predict_reply, decode_predict_request
from physicalai.transport._codec import DEFAULT_MAX_PAYLOAD_DEPTH, unpack_msgpack
from tests.fuzz.llm import to_msgpack
from tests.fuzz.llm.to_msgpack import ConversionError, convert, convert_dir, convert_json, main

_CONTROL_DIR = Path(__file__).parent / "control" / "remote_raw"
_REQUEST_SEEDS = ("request_minimal", "request_np_input", "request_jpeg_image")


def _b64(size: int) -> str:
    return base64.b64encode(bytes(size)).decode("ascii")


def _nested_lists(levels: int) -> object:
    value: object = []
    for _ in range(levels - 1):
        value = [value]
    return value


def test_converts_small_example() -> None:
    packed = convert_json(b'{"a": [1, {"$bytes": "AAEC"}], "b": null, "c": 1.5}')

    assert msgpack.unpackb(packed, raw=False) == {"a": [1, b"\x00\x01\x02"], "b": None, "c": 1.5}


def test_bytes_becomes_msgpack_bin() -> None:
    packed = convert({"$bytes": "AAEC"})

    assert packed == b"\xc4\x03\x00\x01\x02"


@pytest.mark.parametrize(
    "document",
    [
        b"",
        b"{",
        b"\xff\xfe",
        b'{"$bytes": 1}',
        b'{"$bytes": "AAEC", "extra": 1}',
        b'{"$bytes": "not base64!"}',
        b'{"x": 99999999999999999999999999}',
        b'{"x": "\\ud800"}',
        b"[" * 100_000,
    ],
)
def test_rejects_malformed_input(document: bytes) -> None:
    with pytest.raises(ConversionError):
        convert_json(document)


def test_rejects_input_over_input_cap() -> None:
    document = b"[" + b" " * to_msgpack.MAX_INPUT_BYTES + b"]"

    with pytest.raises(ConversionError, match="input exceeds"):
        convert_json(document)


def test_rejects_decoded_bytes_over_cap() -> None:
    half = to_msgpack.MAX_DECODED_BYTES // 2 + 1
    value = [{"$bytes": _b64(half)}, {"$bytes": _b64(half)}]

    with pytest.raises(ConversionError, match="decoded bytes exceed"):
        convert(value)


def test_rejects_single_bytes_value_over_cap_before_decoding() -> None:
    value = {"$bytes": "A" * (to_msgpack._MAX_BASE64_CHARS + 4)}  # noqa: SLF001

    with pytest.raises(ConversionError, match="decoded cap"):
        convert(value)


def test_rejects_output_over_cap() -> None:
    with pytest.raises(ConversionError, match="output exceeds"):
        convert({"text": "x" * to_msgpack.MAX_OUTPUT_BYTES})


def test_accepts_nesting_at_cap_and_rejects_beyond() -> None:
    at_cap = convert(_nested_lists(to_msgpack.MAX_DEPTH + 1))

    with pytest.raises(ConversionError, match="nesting exceeds"):
        convert(_nested_lists(to_msgpack.MAX_DEPTH + 2))
    # The depth gate in the codec stays reachable from converter output.
    assert to_msgpack.MAX_DEPTH > DEFAULT_MAX_PAYLOAD_DEPTH
    with pytest.raises(ValueError, match="nesting exceeds"):
        unpack_msgpack(at_cap)


@pytest.mark.parametrize("name", _REQUEST_SEEDS)
def test_request_control_seeds_decode(name: str) -> None:
    packed = convert_json((_CONTROL_DIR / f"{name}.json").read_bytes())

    decode_message(packed)
    decode_predict_request(packed)


def test_reply_control_seed_decodes() -> None:
    packed = convert_json((_CONTROL_DIR / "reply_valid.json").read_bytes())

    reply = decode_predict_reply(packed)

    assert reply["outputs"]["action"].shape == (1, 2)


def test_jpeg_control_seed_decodes_to_declared_shape() -> None:
    packed = convert_json((_CONTROL_DIR / "request_jpeg_image.json").read_bytes())

    _, inputs = decode_predict_request(packed)

    assert inputs["images.front"].shape == (8, 8, 3)


def test_cli_converts_control_seeds(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"

    assert main([str(_CONTROL_DIR), str(out_dir)]) == 0

    expected = {f"{path.stem}.bin" for path in _CONTROL_DIR.glob("*.json")}
    assert {path.name for path in out_dir.iterdir()} == expected


def test_cli_reports_rejected_files(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "good.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    (in_dir / "bad.json").write_text("{", encoding="utf-8")
    out_dir = tmp_path / "out"

    assert convert_dir(in_dir, out_dir) == 1

    assert [path.name for path in out_dir.iterdir()] == ["good.bin"]


def test_cli_requires_two_arguments() -> None:
    assert main(["only-one"]) == 2
