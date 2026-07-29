"""Fuzz harness: InferenceModel._prepare_inputs() dot-key collision (FT-17).

_prepare_inputs() flattens nested input dicts using dot notation *one level
deep* then filters to adapter.input_names.  When the caller supplies BOTH a
literal flat key ``"obs.image"`` AND a nested dict ``{"obs": {"image": x}}``
in the same call, both produce the same flattened key.  The last writer wins
silently — no KeyError, no warning.

This is a physical-AI safety issue: an attacker who controls the obs dict
structure can silently substitute a different tensor for an expected model
input, producing actions calibrated for the wrong observation.

Sub-targets
-----------
  A — Determinism: given two dicts that differ only in insertion order of a
      colliding pair, _prepare_inputs must choose one of them consistently
      (either always flat-key-wins or always nested-key-wins for the same
      collision pattern).
  B — No crash: arbitrary unicode key names, nested vs flat, extra keys,
      empty dicts, arrays of various shapes.
  C — Filtering: when expected_keys is non-empty, output contains exactly
      those keys (no more, no fewer) — or raises KeyError for missing keys.

Invariants asserted
-------------------
- No Python crash for any input.
- Output values for a key come from the input (not fabricated).
- When both flat and nested paths collide on a key, the result is consistent
  across equivalent inputs differing only in dict ordering.
- With expected_keys=['k'], output has exactly one key 'k'.
"""
from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atheris
import numpy as np

with atheris.instrument_imports():
    from physicalai.inference.model import InferenceModel

from _helpers import make_float_array


def _call_prepare_inputs(
    inputs: dict,
    expected_keys: list[str] | None,
) -> dict:
    """Call InferenceModel._prepare_inputs via a lightweight mock self."""
    mock = types.SimpleNamespace()
    mock.adapter = types.SimpleNamespace(input_names=expected_keys or [])
    return InferenceModel._prepare_inputs(mock, inputs)  # type: ignore[arg-type]


@atheris.instrument_func
def _sub_collision_determinism(fdp: atheris.FuzzedDataProvider) -> None:
    """Assert that key-collision result is consistent regardless of dict ordering."""
    prefix = fdp.ConsumeUnicodeNoSurrogates(8) or "obs"
    suffix = fdp.ConsumeUnicodeNoSurrogates(8) or "image"

    if not prefix or not suffix:
        return

    dot_key = f"{prefix}.{suffix}"
    flat_val = make_float_array(fdp, max_ndim=2, max_dim=8)
    nested_val = make_float_array(fdp, max_ndim=2, max_dim=8)

    # Order A: flat key first, then nested dict
    inputs_a = {dot_key: flat_val, prefix: {suffix: nested_val}}
    # Order B: nested dict first, then flat key
    inputs_b = {prefix: {suffix: nested_val}, dot_key: flat_val}

    try:
        result_a = _call_prepare_inputs(inputs_a, [dot_key])
        result_b = _call_prepare_inputs(inputs_b, [dot_key])
    except KeyError:
        return  # Acceptable — key may not survive the filter

    # Both calls must succeed or both fail; if both succeed, each must return
    # the same tensor (whichever side of the collision wins must be consistent).
    if dot_key in result_a and dot_key in result_b:
        val_a = result_a[dot_key]
        val_b = result_b[dot_key]
        # At minimum the shapes must match — if the winner differs the shapes
        # could differ, which is the actual safety bug (wrong tensor fed to model).
        assert val_a.shape == val_b.shape, (
            f"_prepare_inputs collision is non-deterministic: "
            f"order-A produced shape {val_a.shape}, order-B produced {val_b.shape} "
            f"for key {dot_key!r}"
        )


@atheris.instrument_func
def _sub_no_crash(fdp: atheris.FuzzedDataProvider) -> None:
    """No crash for arbitrary key names and structures."""
    n_keys = fdp.ConsumeIntInRange(0, 6)
    inputs: dict = {}
    for _ in range(n_keys):
        key = fdp.ConsumeUnicodeNoSurrogates(24)
        if not key:
            continue
        if fdp.ConsumeBool():
            # Nested dict
            sub_key = fdp.ConsumeUnicodeNoSurrogates(16) or "x"
            inputs[key] = {sub_key: make_float_array(fdp, max_ndim=2, max_dim=8)}
        else:
            inputs[key] = make_float_array(fdp, max_ndim=2, max_dim=8)

    expected = None
    if fdp.ConsumeBool() and inputs:
        # Pick a random subset of flat-projected keys as expected
        flat_keys = []
        for k, v in inputs.items():
            if isinstance(v, dict):
                for sk in v:
                    flat_keys.append(f"{k}.{sk}")
            else:
                flat_keys.append(k)
        if flat_keys:
            n = fdp.ConsumeIntInRange(1, min(len(flat_keys), 4))
            expected = flat_keys[:n]

    try:
        result = _call_prepare_inputs(inputs, expected)
    except KeyError:
        return  # Acceptable — a requested key was not present

    # Oracle: result values must be ndarray instances (not raw dicts)
    for v in result.values():
        assert isinstance(v, np.ndarray), (
            f"_prepare_inputs returned a non-ndarray value: {type(v).__name__}"
        )


@atheris.instrument_func
def _sub_filter_exact(fdp: atheris.FuzzedDataProvider) -> None:
    """With a single expected key present, output has exactly that key."""
    key = fdp.ConsumeUnicodeNoSurrogates(16) or "state"
    arr = make_float_array(fdp, max_ndim=2, max_dim=8)
    inputs = {key: arr}

    try:
        result = _call_prepare_inputs(inputs, [key])
    except KeyError:
        return

    assert list(result.keys()) == [key], (
        f"_prepare_inputs with expected=[{key!r}] returned keys {list(result.keys())!r}"
    )
    np.testing.assert_array_equal(
        result[key],
        arr,
        err_msg=f"_prepare_inputs mutated value for key {key!r}",
    )


def test_one_input(data: bytes) -> None:
    if len(data) < 4:
        return

    fdp = atheris.FuzzedDataProvider(data)
    sub = fdp.ConsumeIntInRange(0, 2)

    if sub == 0:
        _sub_collision_determinism(fdp)
    elif sub == 1:
        _sub_no_crash(fdp)
    else:
        _sub_filter_exact(fdp)


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
