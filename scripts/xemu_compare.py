#!/usr/bin/env python3
"""Compare a recomp golden frame with xemu reference captures.

  uv run --with pillow --with numpy scripts/xemu_compare.py GOLDEN.png XEMU_DIR_OR_PNG... \
      --out DIR [--shift 8]

For each golden frame: picks the xemu capture with the lowest mean abs diff
(after resizing to the golden size and searching integer shifts up to
--shift px), then writes side-by-side, diff-heat and stats JSON to --out.
Stats: per-channel mae, mean colour of both, the share of pixels off by >8
and >48, and a 8x6 tile grid of mae (worst tiles listed).
Frames stay local: analysis/reference/xemu/ is gitignored.
"""

import argparse
import glob
import json
import os

import numpy as np
from PIL import Image


def load(path, size=None):
    im = Image.open(path).convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.BILINEAR)
    return np.asarray(im).astype(np.int16)


def best_shift(g, x, maxs):
    best = (1e9, 0, 0)
    h, w, _ = g.shape
    m = maxs
    gc = g[m : h - m, m : w - m]
    for dy in range(-maxs, maxs + 1, 2 if maxs > 4 else 1):
        for dx in range(-maxs, maxs + 1, 2 if maxs > 4 else 1):
            xc = x[m + dy : h - m + dy, m + dx : w - m + dx]
            e = np.abs(gc - xc).mean()
            if e < best[0]:
                best = (e, dy, dx)
    # refine
    e0, dy0, dx0 = best
    for dy in range(dy0 - 1, dy0 + 2):
        for dx in range(dx0 - 1, dx0 + 2):
            if abs(dy) > maxs or abs(dx) > maxs:
                continue
            xc = x[m + dy : h - m + dy, m + dx : w - m + dx]
            e = np.abs(gc - xc).mean()
            if e < best[0]:
                best = (e, dy, dx)
    return best


def stats(g, x):
    d = np.abs(g - x)
    h, w, _ = g.shape
    tiles = []
    th, tw = h // 6, w // 8
    for ty in range(6):
        row = []
        for tx in range(8):
            row.append(round(float(d[ty * th : (ty + 1) * th, tx * tw : (tx + 1) * tw].mean()), 1))
        tiles.append(row)
    flat = sorted(
        ((v, ty, tx) for ty, r in enumerate(tiles) for tx, v in enumerate(r)), reverse=True
    )
    return {
        "mae": round(float(d.mean()), 2),
        "mae_rgb": [round(float(d[..., c].mean()), 2) for c in range(3)],
        "mean_golden_rgb": [round(float(g[..., c].mean()), 1) for c in range(3)],
        "mean_xemu_rgb": [round(float(x[..., c].mean()), 1) for c in range(3)],
        "bad8": round(float((d.max(-1) > 8).mean()), 4),
        "bad48": round(float((d.max(-1) > 48).mean()), 4),
        "tiles_mae_8x6": tiles,
        "worst_tiles": [
            {"mae": v, "x": tx * tw, "y": ty * th, "w": tw, "h": th} for v, ty, tx in flat[:6]
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("golden")
    ap.add_argument("xemu", nargs="+")
    ap.add_argument(
        "--out",
        required=True,
        help="output dir; keep it under analysis/reference/xemu/ (gitignored)",
    )
    ap.add_argument("--shift", type=int, default=8)
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    g = load(a.golden)
    size = (g.shape[1], g.shape[0])
    files = []
    for p in a.xemu:
        files += sorted(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else [p]
    # coarse pass: no shift, every file
    scored = []
    for f in files:
        x = load(f, size)
        scored.append((float(np.abs(g - x).mean()), f))
    scored.sort()
    results = []
    for e, f in scored[: a.top]:
        x = load(f, size)
        e2, dy, dx = best_shift(g, x, a.shift)
        xs = np.roll(x, (-dy, -dx), axis=(0, 1))
        st = stats(g, xs)
        st.update(
            {
                "file": f,
                "mae_noshift": round(e, 2),
                "shift_dy_dx": [dy, dx],
                "src_size": list(Image.open(f).size),
            }
        )
        results.append(st)
    best = results[0]
    name = os.path.splitext(os.path.basename(a.golden))[0]
    x = np.roll(load(best["file"], size), tuple(-v for v in best["shift_dy_dx"]), axis=(0, 1))
    d = np.abs(g - x).max(-1)
    heat = np.clip(d * 4, 0, 255).astype(np.uint8)
    side = np.concatenate([g, x], axis=1).astype(np.uint8)
    Image.fromarray(side).save(os.path.join(a.out, f"{name}-side.png"))
    Image.fromarray(heat).save(os.path.join(a.out, f"{name}-diff.png"))
    with open(os.path.join(a.out, f"{name}-stats.json"), "w") as f:
        json.dump(results, f, indent=1)
    print(
        json.dumps(
            {
                k: best[k]
                for k in (
                    "file",
                    "mae",
                    "mae_rgb",
                    "mean_golden_rgb",
                    "mean_xemu_rgb",
                    "bad8",
                    "bad48",
                    "shift_dy_dx",
                    "src_size",
                    "worst_tiles",
                )
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
