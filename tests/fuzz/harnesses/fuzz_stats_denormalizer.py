"""Fuzz harness: StatsDenormalizer (FT-6).

Invariants asserted
-------------------
- No Python crash for arbitrary array shapes and stat values.
- Keys NOT listed in ``features`` pass through unchanged.
- Differential oracle: normalize(denormalize(x)) ≈ x for well-conditioned
  stats (skipped when stats contain inf/nan or zero-width denominators).
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

    # Snapshot whether stats contain NaN for the propagation oracle.
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

    # Oracle 0 (physical AI safety): NaN/Inf stats on finite input must propagate.
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

    # Oracle 1: passthrough key must still be present and unmodified
    assert other_key in result, (
        f"StatsDenormalizer dropped passthrough key {other_key!r}"
    )
    np.testing.assert_array_equal(
        result[other_key],
        other_arr,
        err_msg=f"StatsDenormalizer modified non-listed key {other_key!r}",
    )

    # Oracle 2 (differential): norm(denorm(x)) ≈ x for well-conditioned stats
    # Only run when the stats are finite and results are finite
    if feature_name in result and np.all(np.isfinite(result[feature_name])):
        for stat_vals in stats.get(feature_name, {}).values():
            if not np.all(np.isfinite(stat_vals)):
                return  # ill-conditioned stats; skip round-trip check

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
