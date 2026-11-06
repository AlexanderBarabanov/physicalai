# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz ``Manifest`` validation on verbatim JSON bytes (no ``FuzzedDataProvider``).

Unlike ``fuzz_manifest``, the input is the JSON document itself, so a seed file is a manifest and
mutation edits it directly. Seeds can therefore be plain JSON.
"""

from __future__ import annotations

import json
import sys

import atheris

with atheris.instrument_imports():
    from pydantic import ValidationError

    from physicalai.inference.manifest import Manifest

# Same tuple as fuzz_manifest's raw-JSON path; do not widen it to `Exception`.
_EXPECTED_EXCEPTIONS = (ValidationError, ValueError, json.JSONDecodeError, UnicodeDecodeError)


def test_one_input(data: bytes) -> None:
    try:
        Manifest.model_validate(json.loads(data))
    except _EXPECTED_EXCEPTIONS:
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
