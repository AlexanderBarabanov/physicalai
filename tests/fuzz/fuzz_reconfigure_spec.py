# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz harness for the IPC reconfigure channel spec parsing (TM-007).

Threat model target
-------------------
TM-007  The iceoryx2 ``{service_name}/control`` service accepts ``RECONFIGURE``
        JSON from any host process.  The ``spec_data`` dict from the request is
        validated only as ``isinstance(spec_data, dict)`` — no schema
        enforcement on field values — before being passed to
        ``CameraSpec.from_json_dict()`` and then ``build_camera()``.

        This harness tests the ``CameraSpec.from_json_dict()`` boundary:
        the first layer of parsing that attacker-controlled ``spec_data``
        passes through in ``_handle_reconfigure()``.  (The downstream
        ``build_camera()`` call is excluded because it requires live camera
        hardware.)

Two fuzzing paths
-----------------
1. **Arbitrary JSON path** — raw bytes decoded as UTF-8 JSON, then passed
   directly to ``CameraSpec.from_json_dict()``.  This mirrors the actual
   attacker-controlled data flow in ``_handle_reconfigure()``.

2. **Structured reconfigure request path** — FDP synthesises a valid-looking
   ``RECONFIGURE`` request dict with arbitrary string/dict field values and
   passes the inner ``spec`` dict to ``CameraSpec.from_json_dict()``.

Running
-------
    python tests/fuzz/fuzz_reconfigure_spec.py tests/fuzz/corpus/reconfigure \
        -max_total_time=600 -artifact_prefix=crashes/reconfigure-

Crash interpretation
--------------------
A crash file written to ``crashes/reconfigure-*`` indicates an unhandled
exception escaped ``CameraSpec.from_json_dict()`` for the saved input.
``KeyError`` (missing ``camera_type``) and ``TypeError`` are expected and
are caught.  Any other exception is a finding.
"""

import json
import sys

import atheris

with atheris.instrument_imports():
    from physicalai.capture.transport._spec import CameraSpec


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    """Atheris entry point — called with mutated byte sequences."""
    # ------------------------------------------------------------------ #
    # Path 1: Arbitrary JSON → CameraSpec.from_json_dict().               #
    # Mirrors what _handle_reconfigure does after the isinstance check.   #
    # ------------------------------------------------------------------ #
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
        if isinstance(obj, dict):
            CameraSpec.from_json_dict(obj)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass

    # ------------------------------------------------------------------ #
    # Path 2: FDP-constructed RECONFIGURE request → spec dict parsing.    #
    # Exercises camera_type / camera_kwargs field extraction.             #
    # ------------------------------------------------------------------ #
    fdp = atheris.FuzzedDataProvider(data)
    if fdp.remaining_bytes() < 2:
        return

    try:
        type_len = fdp.ConsumeIntInRange(0, min(128, fdp.remaining_bytes()))
        camera_type = fdp.ConsumeUnicodeNoSurrogates(type_len)
        spec = {
            "camera_type": camera_type,
            "camera_kwargs": {},
        }
        CameraSpec.from_json_dict(spec)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
