# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Fuzz harness for SO-101 calibration parsing.

Threat model target
-------------------
TM-008  ``SO101Calibration.from_dict()`` casts numeric fields with ``int()``
        but applies no bounds checks.  Specifically:

        * ``range_min > range_max`` (inverted range) is silently accepted and
          would reverse computed joint limits.
        * Extreme ``homing_offset``, ``range_min``, or ``range_max`` values
          pass all validation and could drive joints outside safe mechanical
          limits.
        * Only ``drive_mode ∈ {0, 1}`` and positive/unique servo IDs are
          checked.

Two fuzzing paths
-----------------
1. **Structured path** — FDP generates a complete calibration dict with all
   six joints present but with arbitrary integer field values.  This path
   exercises the numeric validation logic directly and is the most likely
   to find the range-inversion gap.

2. **Unstructured path** — raw bytes decoded as UTF-8 JSON.  This path
   explores structural edge cases (missing joints, wrong field types, etc.)
   and may surface unexpected exceptions from ``int()`` coercion.

Running
-------
    python tests/fuzz/fuzz_calibration.py tests/fuzz/corpus/calibration \
        -max_total_time=600 -artifact_prefix=crashes/calibration-

Crash interpretation
--------------------
A crash file written to ``crashes/calibration-*`` indicates an unhandled
exception escaped ``SO101Calibration.from_dict()`` for the saved input.
``TypeError`` and ``ValueError`` from the validation layer are expected and
are caught.  Any other exception (e.g. ``OverflowError``, ``AttributeError``)
is a finding.
"""

import json
import sys
from unittest.mock import MagicMock

import atheris

# physicalai.robot.so101.__init__ imports SO101 which imports scservo_sdk
# (the Feetech servo hardware SDK).  Stub it out exactly as the unit tests do
# so the harness can run without physical hardware or the optional so101 extra.
sys.modules.setdefault("scservo_sdk", MagicMock())

with atheris.instrument_imports():
    from physicalai.robot.so101.calibration import SO101Calibration

# All six joints must be present in the calibration dict.
_JOINT_NAMES = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
)

# Bytes consumed per joint: 5 fields × 4 bytes each.
_BYTES_PER_JOINT = 5 * 4
_MIN_BYTES = len(_JOINT_NAMES) * _BYTES_PER_JOINT


@atheris.instrument_func
def test_one_input(data: bytes) -> None:
    """Atheris entry point — called with mutated byte sequences."""
    # ------------------------------------------------------------------ #
    # Path 1: Structured calibration — all joints present, arbitrary      #
    # numeric field values.  Targets TM-008 numeric bounds gaps.          #
    # ------------------------------------------------------------------ #
    fdp = atheris.FuzzedDataProvider(data)
    if fdp.remaining_bytes() >= _MIN_BYTES:
        cal_dict: dict = {}
        for name in _JOINT_NAMES:
            cal_dict[name] = {
                "id": fdp.ConsumeInt(4),
                "drive_mode": fdp.ConsumeInt(4),
                "homing_offset": fdp.ConsumeInt(4),
                "range_min": fdp.ConsumeInt(4),
                "range_max": fdp.ConsumeInt(4),
            }
        try:
            SO101Calibration.from_dict(cal_dict)
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------ #
    # Path 2: Fully arbitrary JSON → calibration parsing.                 #
    # Exercises structural edge cases (missing keys, wrong types, etc.).  #
    # ------------------------------------------------------------------ #
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
        SO101Calibration.from_dict(obj)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
