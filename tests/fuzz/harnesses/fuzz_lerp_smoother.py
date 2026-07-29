"""Fuzz harness: LerpSmoother.merge() (FT-11).

Sub-targets
-----------
  A — Matching action_dim: asserts output is 2-D float32 with correct dims.
  B — Mismatching action_dim: asserts ValueError is raised.
  C — Non-2D inputs: asserts ValueError is raised.
  D — Empty remaining: asserts output equals incoming (cast to float32).

Invariants asserted
-------------------
- Output is always 2-D float32.
- Output action_dim == incoming.shape[1].
- ValueError raised for shape violations (different cols, non-2D).
- LerpSmoother(empty_remaining, x) == ReplaceSmoother(empty_remaining, x).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atheris
import numpy as np

with atheris.instrument_imports():
    from physicalai.runtime.smoothers import LerpSmoother, ReplaceSmoother

from _helpers import make_2d_float_array, make_2d_same_cols


def test_one_input(data: bytes) -> None:
    if len(data) < 8:
        return

    fdp = atheris.FuzzedDataProvider(data)
    duration_frames = fdp.ConsumeIntInRange(0, 32)
    lerp = LerpSmoother(duration_frames=duration_frames)
    replace = ReplaceSmoother()

    sub = fdp.ConsumeIntInRange(0, 3)

    if sub == 0:
        # A: matching dims
        remaining = make_2d_float_array(fdp, max_rows=32, max_cols=16)
        incoming = make_2d_same_cols(fdp, remaining.shape[1], max_rows=32)

        try:
            result = lerp.merge(remaining, incoming)
        except ValueError:
            return

        assert result.ndim == 2, f"Expected 2D, got {result.ndim}D"  # noqa: PLR2004
        assert result.dtype == np.float32, f"Expected float32, got {result.dtype}"
        if incoming.shape[1] > 0:
            assert result.shape[1] == incoming.shape[1], (
                f"action_dim changed: expected {incoming.shape[1]}, got {result.shape[1]}"
            )

    elif sub == 1:
        # B: mismatching dims → ValueError expected
        remaining = make_2d_float_array(fdp, max_rows=16, max_cols=16)
        # Force different cols
        mismatch_cols = remaining.shape[1] + fdp.ConsumeIntInRange(1, 8)
        incoming = make_2d_same_cols(fdp, mismatch_cols, max_rows=16)
        try:
            lerp.merge(remaining, incoming)
        except ValueError:
            return  # Expected
        # If both action_dims are 0, no mismatch; that's fine
        if remaining.shape[1] != incoming.shape[1]:
            raise AssertionError(
                f"Expected ValueError for mismatched cols "
                f"({remaining.shape[1]} vs {incoming.shape[1]})"
            )

    elif sub == 2:
        # C: non-2D inputs → ValueError expected
        ndim = fdp.ConsumeIntInRange(1, 4)
        shape = tuple(fdp.ConsumeIntInRange(1, 8) for _ in range(ndim))
        if ndim == 2:  # noqa: PLR2004
            return  # skip — would be valid
        arr = np.zeros(shape, dtype=np.float32)
        try:
            lerp.merge(arr, arr)
        except ValueError:
            return
        raise AssertionError(f"Expected ValueError for {ndim}D input, got none")

    else:
        # D: empty remaining → output == incoming (differential with Replace)
        cols = fdp.ConsumeIntInRange(0, 16)
        incoming = make_2d_same_cols(fdp, cols, max_rows=32)
        empty = np.zeros((0, cols), dtype=np.float32)

        try:
            lerp_result = lerp.merge(empty, incoming)
            replace_result = replace.merge(empty, incoming)
        except ValueError:
            return

        np.testing.assert_array_almost_equal(
            lerp_result,
            replace_result,
            decimal=5,
            err_msg="LerpSmoother(empty_remaining, x) should equal ReplaceSmoother(empty_remaining, x)",
        )


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
