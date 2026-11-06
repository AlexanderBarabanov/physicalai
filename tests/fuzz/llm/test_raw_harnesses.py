# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Smoke tests for the raw-input fuzz harnesses (Atheris is Linux-only)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("atheris")
pytest.importorskip("msgpack")
pytest.importorskip("zenoh")  # imported by physicalai.inference.remote
import fuzz_manifest_json
import fuzz_remote_raw

from tests.fuzz.llm.to_msgpack import convert_json

_FUZZ_DIR = Path(__file__).parents[1]
_CONTROL_DIR = Path(__file__).parent / "control" / "remote_raw"


@pytest.mark.parametrize("harness", [fuzz_manifest_json, fuzz_remote_raw])
def test_harness_accepts_empty_input(harness: object) -> None:
    harness.test_one_input(b"")


@pytest.mark.parametrize("path", sorted((_FUZZ_DIR / "seeds" / "fuzz_manifest").glob("*.json")), ids=lambda p: p.name)
def test_manifest_json_accepts_control_seeds(path: Path) -> None:
    fuzz_manifest_json.test_one_input(path.read_bytes())


@pytest.mark.parametrize("path", sorted(_CONTROL_DIR.glob("*.json")), ids=lambda p: p.name)
def test_remote_raw_accepts_control_seeds(path: Path) -> None:
    fuzz_remote_raw.test_one_input(convert_json(path.read_bytes()))
