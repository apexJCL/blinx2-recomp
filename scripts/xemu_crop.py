#!/usr/bin/env python3
"""Crop xemu window captures (spectacle) to the guest image.

  uv run --with pillow --with numpy scripts/xemu_crop.py IN_DIR OUT_DIR [--w 640 --h 480]

xemu draws the guest image centred in its window (fit = center,
surface_scale 1), so every capture of one session has the image at the same
place. The window chrome (border, title bar) is static and the guest image
is not, so the rectangle is the bounding box of the pixels that change over
the session's frames, snapped to WxH around its centre.
"""

import argparse
import glob
import os

import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--w", type=int, default=640)
    ap.add_argument("--h", type=int, default=480)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.src, "f*.png")))
    sample = files[:: max(1, len(files) // 40)]
    stack = np.stack([np.asarray(Image.open(f).convert("L"), dtype=np.int16) for f in sample])
    moving = (stack.max(0) - stack.min(0)) > 16
    ys, xs = np.nonzero(moving)
    if not len(xs):
        raise SystemExit("no moving pixels")
    cx, cy = (xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2
    x0, y0 = int(round(cx - a.w / 2)), int(round(cy - a.h / 2))
    print("moving bbox", xs.min(), ys.min(), xs.max() + 1, ys.max() + 1, "-> crop at", x0, y0)
    os.makedirs(a.dst, exist_ok=True)
    for f in files:
        Image.open(f).convert("RGB").crop((x0, y0, x0 + a.w, y0 + a.h)).save(
            os.path.join(a.dst, os.path.basename(f))
        )


if __name__ == "__main__":
    main()
