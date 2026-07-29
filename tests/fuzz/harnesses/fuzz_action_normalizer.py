"""Fuzz harness: ActionNormalizer (FT-9).

Invariants asserted
-------------------
- "action" key is always present in the output (when the call succeeds).
- Keys other than the action key pass through unchanged.
- Works for single-key dicts, multi-key dicts, and dicts with a
  canonical "action" key already present.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atheris
import numpy as np

with atheris.instrument_imports():
    from physicalai.inference.postprocessors.action_normalizer import ActionNormalizer
    from physicalai.inference.constants import ACTION

from _helpers import make_float_array


def test_one_input(data: bytes) -> None:
    if len(data) < 4:
        return

    fdp = atheris.FuzzedDataProvider(data)

    use_explicit_key = fdp.ConsumeBool()
    n_extra_keys = fdp.ConsumeIntInRange(0, 4)

    # Build output dict with fuzz-derived key names and arrays
    keys = [fdp.ConsumeUnicodeNoSurrogates(24) for _ in range(n_extra_keys)]
    keys = [k for k in keys if k]  # drop empty strings

    outputs: dict[str, np.ndarray] = {
        k: make_float_array(fdp, max_ndim=3, max_dim=16) for k in keys
    }

    # Optionally add the canonical "action" key
    if fdp.ConsumeBool():
        outputs[ACTION] = make_float_array(fdp, max_ndim=3, max_dim=16)

    if not outputs:
        return  # Empty dict: next(iter({})) raises StopIteration — known edge case

    explicit_key = keys[0] if (use_explicit_key and keys) else None
    normalizer = ActionNormalizer(action_key=explicit_key)

    # Track non-action keys before the call
    pre_action_key = ACTION if ACTION in outputs else (explicit_key or next(iter(outputs)))
    passthrough_keys = {k: v.copy() for k, v in outputs.items() if k != pre_action_key}

    try:
        result = normalizer(dict(outputs))  # pass a copy
    except (KeyError, StopIteration):
        # KeyError: explicit action_key not in outputs — documented edge case
        # StopIteration: empty dict fallback (already guarded above but race-safe)
        return

    # Oracle 1: "action" must always be in the result
    assert ACTION in result, (
        f"'action' key missing from ActionNormalizer output. keys={list(result.keys())}"
    )

    # Oracle 2: passthrough keys must be present and unmodified
    for k, v in passthrough_keys.items():
        assert k in result, f"ActionNormalizer dropped passthrough key {k!r}"
        np.testing.assert_array_equal(result[k], v, err_msg=f"Key {k!r} was modified")


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
