"""Fuzz StatsDenormalizer — passthrough-key preservation, NaN propagation,
and normalize(denormalize(x)) ≈ x round-trip for well-conditioned stats.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atheris
import numpy as np

with atheris.instrument_imports():
    from physicalai.inference.postprocessors.stats_denormalizer import StatsDenormalizer
    from physicalai.inference.preprocessors.stats_normalizer import StatsNormalizer

from _helpers import make_float_array, make_stats_dict

_MODES = ["mean_std", "min_max", "quantiles", "identity"]

# Minimum range magnitude below which eps-stabilisation in StatsNormalizer
# dominates and the round-trip invariant no longer holds numerically.
_MIN_RANGE = 1e-3

# Upper bound on derived ranges / std: if the float64 value exceeds float32 max,
# the float32 arithmetic (tensor * range) will overflow even though the individual
# stat values are both finite.  Check in float64 to avoid float32 overflow here.
_FLOAT32_MAX = np.float64(np.finfo(np.float32).max)

# float32 subnormal threshold: values below np.finfo(np.float32).tiny are flushed
# to the same result as 0 when added to 1.0, so denorm(subnormal) == denorm(0) and
# the round-trip norm(denorm(x)) cannot reproduce the original value.
_FLOAT32_TINY = np.float64(np.finfo(np.float32).tiny)


def _is_roundtrip_conditioned(mode: str, stats: dict, feature_name: str) -> bool:
    """Return True only when the round-trip normalize(denormalize(x)) ≈ x is
    numerically expected to hold.

    Two failure modes are excluded beyond simple non-finiteness of individual
    stat arrays:

    1. Float32 overflow in *derived* ranges (e.g. ``max - min`` overflows to
       ``inf`` even when both ``max`` and ``min`` are individually finite).
       Detection is done in float64.
    2. Eps-stabilisation dominates when the denominator is too small.
       ``StatsNormalizer`` adds ``_EPS`` to prevent division-by-zero; when
       ``|range| < _MIN_RANGE`` the ``_EPS`` term is no longer negligible and
       ``normalize(denormalize(x)) ≠ x``.
    """
    s = stats.get(feature_name, {})

    # All individual stat arrays must be finite first.
    for v in s.values():
        if isinstance(v, np.ndarray) and not np.all(np.isfinite(v)):
            return False

    if mode == "mean_std":
        std = s.get("std")
        if std is None:
            return False
        abs_std = np.abs(std.astype(np.float64))
        # std must be large enough that _EPS doesn't dominate, and small enough
        # that tensor * std doesn't overflow in float32.
        return bool(np.all(abs_std >= _MIN_RANGE) and np.all(abs_std <= _FLOAT32_MAX))

    if mode == "min_max":
        mn, mx = s.get("min"), s.get("max")
        if mn is None or mx is None:
            return False
        rng = mx.astype(np.float64) - mn.astype(np.float64)
        # rng must be finite in float64 AND fit in float32, otherwise
        # (tensor + 1) * rng overflows in the actual float32 computation.
        return bool(
            np.all(np.isfinite(rng))
            and np.all(np.abs(rng) >= _MIN_RANGE)
            and np.all(np.abs(rng) <= _FLOAT32_MAX)
        )

    if mode == "quantiles":
        q01, q99 = s.get("q01"), s.get("q99")
        if q01 is None or q99 is None:
            return False
        rng = q99.astype(np.float64) - q01.astype(np.float64)
        return bool(
            np.all(np.isfinite(rng))
            and np.all(np.abs(rng) >= _MIN_RANGE)
            and np.all(np.abs(rng) <= _FLOAT32_MAX)
        )

    return True  # identity mode — always a no-op, trivially round-trips


def test_one_input(data: bytes) -> None:
    if len(data) < 8:
        return

    fdp = atheris.FuzzedDataProvider(data)
    mode = fdp.PickValueInList(_MODES)
    feature_name = "action"

    stat_dim = fdp.ConsumeIntInRange(1, 16)
    stats = make_stats_dict(fdp, feature_name, stat_dim=stat_dim, mode=mode)

    arr = make_float_array(fdp, max_ndim=3, max_dim=32)
    other_key = "extra_output"
    other_arr = make_float_array(fdp, max_ndim=2, max_dim=16)

    outputs = {feature_name: arr, other_key: other_arr}

    # Check whether stats contain NaN (used by the propagation check below)
    stat_has_nan = any(
        not np.all(np.isfinite(v))
        for v in stats.get(feature_name, {}).values()
        if isinstance(v, np.ndarray)
    )

    try:
        denorm = StatsDenormalizer(mode=mode, features=[feature_name], stats=stats)
        result = denorm(outputs)
    except (ValueError, TypeError, FloatingPointError):
        return

    # NaN/Inf stats on a finite input must propagate downstream
    if (
        mode != "identity"
        and stat_has_nan
        and arr.size > 0
        and np.all(np.isfinite(arr))
        and feature_name in result
        and result[feature_name].size > 0
    ):
        assert not np.all(np.isfinite(result[feature_name])), (
            f"StatsDenormalizer silently produced finite output despite NaN/Inf stats "
            f"(mode={mode!r}).  NaN/Inf must propagate to be detectable downstream."
        )

    assert other_key in result, (
        f"StatsDenormalizer dropped passthrough key {other_key!r}"
    )
    np.testing.assert_array_equal(
        result[other_key],
        other_arr,
        err_msg=f"StatsDenormalizer modified non-listed key {other_key!r}",
    )

    # Round-trip check: normalize(denormalize(x)) ≈ x for well-conditioned stats.
    # Skip when stats are ill-conditioned: non-finite individual values, float32
    # overflow in derived ranges (max-min, q99-q01), or eps-dominated denominators.
    # Also skip when the original array contains subnormal float32 values: those
    # are destroyed by float32 arithmetic (subnormal + 1.0 == 1.0) so the
    # round-trip can never reproduce them regardless of how good the stats are.
    if feature_name in result and np.all(np.isfinite(result[feature_name])):
        if not _is_roundtrip_conditioned(mode, stats, feature_name):
            return
        arr_f64 = arr.astype(np.float64)
        if arr.size > 0 and np.any((arr != 0.0) & (np.abs(arr_f64) < _FLOAT32_TINY)):
            return  # subnormal inputs cannot survive float32 round-trip arithmetic

        try:
            norm = StatsNormalizer(mode=mode, features=[feature_name], stats=stats)
            round_tripped = norm({feature_name: result[feature_name]})[feature_name]
            if np.all(np.isfinite(round_tripped)) and arr.shape == round_tripped.shape:
                np.testing.assert_allclose(
                    round_tripped,
                    arr,
                    rtol=1e-4,
                    atol=1e-5,
                    err_msg=(
                        "normalize(denormalize(x)) should ≈ x for well-conditioned stats"
                    ),
                )
        except (ValueError, FloatingPointError):
            pass


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
