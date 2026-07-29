"""Shared utilities for Physical AI Atheris fuzz harnesses.

All helpers are pure functions — no atheris import — so they can also be
used in non-fuzz unit tests.
"""
from __future__ import annotations

import numpy as np


def make_float_array(
    fdp,  # atheris.FuzzedDataProvider
    *,
    max_ndim: int = 4,
    max_dim: int = 64,
    dtype: type = np.float32,
) -> np.ndarray:
    """Return an ndarray of fuzz-derived random shape and float values."""
    ndim = fdp.ConsumeIntInRange(1, max_ndim)
    shape = tuple(fdp.ConsumeIntInRange(0, max_dim) for _ in range(ndim))
    total = int(np.prod(shape)) if shape else 0
    if total == 0:
        return np.zeros(shape, dtype=dtype)
    item_size = np.dtype(dtype).itemsize
    n_bytes = total * item_size
    raw = fdp.ConsumeBytes(n_bytes)
    if len(raw) < n_bytes:
        raw = raw + b"\x00" * (n_bytes - len(raw))
    return np.frombuffer(raw[:n_bytes], dtype=dtype).copy().reshape(shape)


def make_2d_float_array(
    fdp,
    *,
    max_rows: int = 64,
    max_cols: int = 32,
) -> np.ndarray:
    """Return a 2-D float32 array (rows, cols) from fuzz bytes."""
    rows = fdp.ConsumeIntInRange(0, max_rows)
    cols = fdp.ConsumeIntInRange(0, max_cols)
    total = rows * cols
    if total == 0:
        return np.zeros((rows, cols), dtype=np.float32)
    n_bytes = total * 4
    raw = fdp.ConsumeBytes(n_bytes)
    if len(raw) < n_bytes:
        raw = raw + b"\x00" * (n_bytes - len(raw))
    return np.frombuffer(raw[:n_bytes], dtype=np.float32).copy().reshape((rows, cols))


def make_2d_same_cols(
    fdp,
    cols: int,
    *,
    max_rows: int = 64,
) -> np.ndarray:
    """Return a 2-D float32 array with exactly *cols* columns."""
    rows = fdp.ConsumeIntInRange(0, max_rows)
    if rows == 0 or cols == 0:
        return np.zeros((rows, cols), dtype=np.float32)
    n_bytes = rows * cols * 4
    raw = fdp.ConsumeBytes(n_bytes)
    if len(raw) < n_bytes:
        raw = raw + b"\x00" * (n_bytes - len(raw))
    return np.frombuffer(raw[:n_bytes], dtype=np.float32).copy().reshape((rows, cols))


def make_image_array(fdp, *, max_spatial: int = 128) -> np.ndarray:
    """Return a plausible image array — channels-first (B,C,H,W) or channels-last (B,H,W,C).

    Dtype is uint8 or float32; chosen randomly from fuzz data.
    """
    channels_first = fdp.ConsumeBool()
    B = fdp.ConsumeIntInRange(0, 4)
    C = fdp.ConsumeIntInRange(1, 4)
    H = fdp.ConsumeIntInRange(0, max_spatial)
    W = fdp.ConsumeIntInRange(0, max_spatial)
    shape = (B, C, H, W) if channels_first else (B, H, W, C)
    total = B * C * H * W
    dtype = np.uint8 if fdp.ConsumeBool() else np.float32
    if total == 0:
        return np.zeros(shape, dtype=dtype)
    item_size = np.dtype(dtype).itemsize
    n_bytes = total * item_size
    raw = fdp.ConsumeBytes(n_bytes)
    if len(raw) < n_bytes:
        raw = raw + b"\x00" * (n_bytes - len(raw))
    return np.frombuffer(raw[:n_bytes], dtype=dtype).copy().reshape(shape)


def make_stats_dict(
    fdp,
    feature_name: str,
    *,
    stat_dim: int | None = None,
) -> dict[str, dict[str, np.ndarray]]:
    """Return a pre-loaded stats dict suitable for StatsNormalizer/StatsDenormalizer.

    Bypasses safetensors file loading by passing stats directly via the ``stats``
    constructor kwarg.  The mode (mean_std / min_max / quantiles) is chosen from
    fuzz data; the stat arrays use fuzz-derived float32 values including edge
    cases (inf, nan, negative std, inverted quantiles).
    """
    dim = stat_dim if stat_dim is not None else fdp.ConsumeIntInRange(1, 16)
    # Include "identity" — previously missing, causing its code path to never be fuzzed.
    mode = fdp.PickValueInList(["mean_std", "min_max", "quantiles", "identity"])

    def _stat() -> np.ndarray:
        n_bytes = dim * 4
        raw = fdp.ConsumeBytes(n_bytes)
        if len(raw) < n_bytes:
            raw = raw + b"\x00" * (n_bytes - len(raw))
        return np.frombuffer(raw[:n_bytes], dtype=np.float32).copy()

    if mode == "mean_std":
        return {feature_name: {"mean": _stat(), "std": _stat()}}
    elif mode == "min_max":
        return {feature_name: {"min": _stat(), "max": _stat()}}
    elif mode == "quantiles":
        return {feature_name: {"q01": _stat(), "q99": _stat()}}
    else:  # identity — no stat arrays needed; return an empty stats dict
        return {feature_name: {}}
