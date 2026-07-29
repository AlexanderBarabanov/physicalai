"""Fuzz harness: ResizePreprocessor (FT-7).

Exercises _resize_with_ar_pad with:
- Zero spatial dimensions  (triggers division by zero in scale ratio)
- Batch dimension = 0
- Channels-first and channels-last layouts
- uint8 and float32 dtypes
- Three image key presentations: flat ndarray, nested dict, dotted key
- Extreme target resolutions (1×1, large)

Invariants asserted
-------------------
- No unhandled Python crash.
- When a non-empty output is produced, dtype is float32.
- When a 4-D output is produced, it is channels-first (B, C, H, W).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import atheris
import numpy as np

with atheris.instrument_imports():
    from physicalai.inference.preprocessors.resize import ResizePreprocessor
    from physicalai.inference.constants import IMAGES

from _helpers import make_image_array


def test_one_input(data: bytes) -> None:
    if len(data) < 10:
        return

    fdp = atheris.FuzzedDataProvider(data)

    # Target resolution — clamped to [1, 512] to avoid OOM but allows extremes
    target_h = fdp.ConsumeIntInRange(1, 512)
    target_w = fdp.ConsumeIntInRange(1, 512)
    mode = fdp.PickValueInList(["stretch", "letterbox"])
    pad_value = float(fdp.ConsumeFloat())

    try:
        preprocessor = ResizePreprocessor(
            image_resolution=(target_h, target_w),
            mode=mode,
            pad_value=pad_value,
        )
    except (ValueError, OverflowError):
        return

    img = make_image_array(fdp, max_spatial=64)

    # Three different ways to present image data to the preprocessor
    presentation = fdp.ConsumeIntInRange(0, 2)
    if presentation == 0:
        inputs: dict = {IMAGES: img}
    elif presentation == 1:
        inputs = {IMAGES: {"cam0": img}}
    else:
        inputs = {f"{IMAGES}.cam0": img}

    try:
        outputs = preprocessor(inputs)
    except (ValueError, MemoryError):
        return
    except Exception as exc:
        # cv2 raises its own error type; suppress those, propagate the rest
        if "cv2" in type(exc).__module__ or "cv2" in type(exc).__qualname__:
            return
        raise

    # Oracle: non-empty ndarray outputs must be float32 channels-first
    img_out = outputs.get(IMAGES)
    if isinstance(img_out, np.ndarray) and img_out.size > 0:
        assert img_out.dtype == np.float32, (
            f"Expected float32 output, got {img_out.dtype}"
        )
        if img_out.ndim == 4:  # noqa: PLR2004
            # (B, C, H, W) — C should be small (≤4 for RGB/RGBA)
            assert img_out.shape[1] <= 4, (  # noqa: PLR2004
                f"Unexpected channel count {img_out.shape[1]} in channels-first output"
            )


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
