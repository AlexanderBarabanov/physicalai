# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz harness for manifest.json parsing.

Threat model targets
--------------------
TM-001  ``class_path`` field is a passthrough — any dotted module path
        accepted without allowlist at parse layer.
TM-009  Deeply nested ``init_args`` dicts may cause RecursionError in
        ``instantiate_component()``.  This harness probes the Pydantic
        parse boundary; ``fuzz_component_instantiate.py`` probes the
        runtime boundary.
TM-010  ``manifest.policy.name`` is used to construct ``model_path``
        without ``is_relative_to(export_dir)`` — path-traversal characters
        (``../``) are not rejected at parse time.

Running
-------
    python tests/fuzz/fuzz_manifest.py tests/fuzz/corpus/manifests \
        -max_total_time=600 -artifact_prefix=crashes/manifest-

Crash interpretation
--------------------
A crash file written to ``crashes/manifest-*`` indicates an unhandled
exception escaped ``Manifest.model_validate_json()`` or
``ComponentSpec.model_validate()`` for the saved input.  RecursionError
is the TM-009 signal; any other unexpected exception is a separate finding.
"""

import json
import sys

import atheris

with atheris.instrument_imports():
    from pydantic import ValidationError

    from physicalai.inference.manifest import ComponentSpec, Manifest


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    """Atheris entry point — called with mutated byte sequences."""
    # ------------------------------------------------------------------ #
    # Path 1: Full manifest JSON round-trip.                              #
    # Covers TM-001 (arbitrary class_path), TM-010 (policy.name with     #
    # path-traversal bytes), and any Pydantic schema edge cases.          #
    # RecursionError is NOT caught — atheris records it as a crash.       #
    # ------------------------------------------------------------------ #
    try:
        Manifest.model_validate_json(data)
    except (ValueError, ValidationError, UnicodeDecodeError):
        pass

    # ------------------------------------------------------------------ #
    # Path 2: ComponentSpec in isolation.                                 #
    # Exercises the extra="allow" / flat_params code path and nested      #
    # init_args parsing at the Pydantic layer (TM-009 parsing boundary).  #
    # ------------------------------------------------------------------ #
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
        if isinstance(obj, dict):
            ComponentSpec.model_validate(obj)
    except (ValueError, ValidationError, json.JSONDecodeError, TypeError):
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
