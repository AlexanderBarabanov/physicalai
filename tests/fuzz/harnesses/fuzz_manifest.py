"""Fuzz harness: Manifest JSON parsing (FT-1).

Covers two code paths:

  Path A — raw JSON bytes → json.loads → Manifest.model_validate
           (exercises the JSON decoder and all Pydantic field validators)

  Path B — structured dict with fuzz-derived values
           (reaches validators directly: negative shape dims, huge n_obs_steps,
            missing/extra keys, empty strings, surrogate-free unicode)

Invariants asserted by this harness
------------------------------------
- No Python crash (segfault, stack overflow, infinite loop).
- Only ValidationError, ValueError, or json.JSONDecodeError may be raised.
- Extreme integers in shape / n_obs_steps do not escape the parser.
"""
from __future__ import annotations

import json
import sys

import atheris

with atheris.instrument_imports():
    from pydantic import ValidationError
    from physicalai.inference.manifest import Manifest


@atheris.instrument_func
def _path_raw_json(fdp: atheris.FuzzedDataProvider) -> None:
    text = fdp.ConsumeUnicodeNoSurrogates(fdp.remaining_bytes())
    try:
        Manifest.model_validate(json.loads(text))
    except (ValidationError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        pass


@atheris.instrument_func
def _path_structured(fdp: atheris.FuzzedDataProvider) -> None:
    def _s(n: int = 16) -> str:
        return fdp.ConsumeUnicodeNoSurrogates(n)

    def _component() -> dict:
        if fdp.ConsumeBool():
            return {
                "class_path": _s(64),
                "init_args": {_s(8): _s(16) for _ in range(fdp.ConsumeIntInRange(0, 4))},
            }
        return {
            "type": _s(32),
            **{_s(8): _s(16) for _ in range(fdp.ConsumeIntInRange(0, 4))},
        }

    manifest_dict: dict = {
        "format": _s(16),
        "version": _s(8),
        "policy": {
            "name": _s(48),
            "source": {"repo_id": _s(64), "class_path": _s(64)},
        },
        "model": {
            # Intentionally unclamped: tests that negative / huge values are caught.
            # ConsumeInt(64) gives a full 64-bit signed range; (8) was too narrow.
            "n_obs_steps": fdp.ConsumeInt(64),
            "runner": _component() if fdp.ConsumeBool() else None,
            "artifacts": {_s(8): _s(32) for _ in range(fdp.ConsumeIntInRange(0, 4))},
            "preprocessors": [_component() for _ in range(fdp.ConsumeIntInRange(0, 4))],
            "postprocessors": [_component() for _ in range(fdp.ConsumeIntInRange(0, 4))],
        },
        "hardware": {
            "robots": [
                {
                    "name": _s(8),
                    "state": {
                        # Negative dims should be caught by _shape_must_be_positive
                        "shape": [fdp.ConsumeInt(4) for _ in range(fdp.ConsumeIntInRange(0, 6))],
                        "dtype": _s(8),
                        "order": [_s(8) for _ in range(fdp.ConsumeIntInRange(0, 6))],
                    },
                    "action": {
                        "shape": [fdp.ConsumeInt(4) for _ in range(fdp.ConsumeIntInRange(0, 6))],
                        "dtype": _s(8),
                    },
                }
                for _ in range(fdp.ConsumeIntInRange(0, 3))
            ],
            "cameras": [
                {
                    "name": _s(8),
                    # CameraSpec requires exactly 3 elements when non-empty
                    "shape": [fdp.ConsumeInt(4) for _ in range(fdp.ConsumeIntInRange(0, 6))],
                    "dtype": _s(8),
                }
                for _ in range(fdp.ConsumeIntInRange(0, 3))
            ],
        },
        "metadata": {"created_at": _s(32), "created_by": _s(32)},
    }
    try:
        Manifest.model_validate(manifest_dict)
    except (ValidationError, ValueError):
        pass


def test_one_input(data: bytes) -> None:
    if len(data) < 2:
        return
    fdp = atheris.FuzzedDataProvider(data)
    if fdp.ConsumeBool():
        _path_raw_json(fdp)
    else:
        _path_structured(fdp)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
