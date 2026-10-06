#!/usr/bin/env python3
"""Golden-frame compare for RECOMP_DEBUG=d3d11_dump frames. Standard library only.

  golden.py plan                  scenario<TAB>seconds<TAB>min_flips<TAB>env lines, for bench.sh
  golden.py frames SCEN           the dump indexes (NNNN) SCEN checks
  golden.py diff A B [TOL]                     per-channel stats for two images (BMP or PNG)
  golden.py check [--window K] [--log SCEN=LOG]... [--allow-enhance KEY=VALUE]...
                SCEN=DIR...
                                  compare each scenario's dumped frames with
                                  analysis/golden/golden.json; exit 1 on a
                                  regression, 2 on a missing frame or reference.
                                  A run whose [ENHANCE] lines show a non-stock
                                  render.scale, display.aspect, present.pacing
                                  or fps.mode FAILs unless that KEY=VALUE is
                                  allowed (an evaluation run, noted; record
                                  refuses the flag)
  golden.py dumpat SCEN [--slack W] [--window K]
                                  the RECOMP_DEBUG=fb_dump_at= flip list that makes a
                                  run (Metal, CPU) dump SCEN's frames by flip
  golden.py anchors LOG           each anchor event's flip in a run's log
  golden.py pulls SCEN LOG [--window K]
                                  the flip_NNNNN.bmp files a check of SCEN
                                  reads, given the run's flip log
  golden.py refs                  name each frame whose reference PNG is
                                  missing, and a worktree that has it
                                  (exit 2 if any)
  golden.py record [--only NAME[,NAME]] SCEN=DIR...
                                  copy the chosen frames (or only the named
                                  ones, leaving the others' references) to
                                  analysis/golden/frames/<name>.png and write
                                  their hashes into golden.json; a frame
                                  with references (below) is left alone. An
                                  anchored frame also takes the run's anchor
                                  flip as its ref_flip (from the run's log)
  golden.py reference SCEN NAME LABEL DIR
                                  record DIR's dump of frame NAME as its
                                  reference LABEL (added, or replaced if
                                  LABEL exists), e.g. one camera view

DIR is a run's frame directory, holding the dumper's frame_NNNN.bmp files
(d3d11_dump: dump k is present 60k+1) or flip_NNNNN.bmp files
(fb_dump_at, named by flip; flip N is present N). Dump k is looked up
as frame_000k.bmp, else as flip 60k+1.

Skips. A scenario's (or frame's) "skip_backends" list, e.g. ["cpu"], with
"skip_why", leaves its frames unchecked on a run whose flip log shows that
backend (D3D11 or METAL flip lines, else cpu): SKIP, which neither passes
nor fails. For a scenario whose timeline a slow backend cannot follow.

Masks. A frame's "masks" list ({"rect": [x, y, w, h], "why": ...}) takes
those pixels out of the compare: the run's pixels there are replaced by
the reference's, and a split frame leaves them out of its panel, overlay
and background. For a part of the screen that animates on a clock the
anchor does not follow (a pulsing button, a blinking prompt); keep each
rect to the pixels that differ. A mask may carry "presence": {"pixel_tol",
"max_bad_fraction", "max_channel_mae"}: its pixels may animate but must
stay that close to the reference (the thing is still there).

Event anchors. A frame may name an anchor, "anchor": {"event": E,
"ref_flip": R}, where the scenario's "anchors" define E as the first flip at
or after `after_flip` where the run's flip log (RECOMP_TRACE=flip lines
"[D3D11] flip N batches B" or "[METAL] flip N batches B") crosses into at
least `min_batches` (or at most `max_batches`) batches: this flip and the
next qualify, the one before does not. R is that flip in the reference run (a reference in
`references` may carry its own "anchor_flip"). With the run's log (--log, or
DIR/../game-stdio.log, or DIR.log) giving the run's anchor A, the frame is
checked at flip A + (60*dump + 1 - R): the same distance from the event as
the reference, so a run whose timeline starts a few presents early or late
is compared with the frame it means. That needs flip_NNNNN.bmp dumps; a run
with no flip dumps, no anchor in its log, or not the target flip is
INCOMPLETE (exit 2) for that frame, never compared at the plain dump. --window K (default 2) also
compares the flips within K of the target and prints the best one: a
diagnostic, the verdict is the target's.

Pace. Some content follows wall time, not flips (the title's cloud movie),
so a run flipping at another rate lands elsewhere in it. The run's pace
(flips per wall second from its anchor to the target, from the "[GPU] flip
N T ms" lines) is compared with the reference run's over the same span (the
anchor's "ref_pace", or a reference's "pace"; written by record/reference).
Off by more than max_pace_diff (frame, scenario or compare; default 0.10),
an EXACT or in-limits frame still passes (CLOSE notes the mismatch); one
outside its limits is INCOMPLETE "pace mismatch (run X fps vs ref Y fps)",
not FAIL, unless every reference is off by pace_fail_bad (default 0.5) of
its pixels or more: a wrong screen at any pace, FAIL. No recorded pace, a
target not after the anchor, or max_pace_diff null is no check. The limit
is a ratio, but the harm is drift (span x ratio): a long span drifts
further at the same ratio, so set a frame's max_pace_diff to its span.

The verdict: exit 1 on any FAIL, else 2 on any INCOMPLETE (counts printed).
golden.json names, per scenario, the frames to check (by dump index) and the
thresholds; it holds hashes and metrics only. The reference PNGs live in
analysis/golden/frames/, which is gitignored: they are game frames.

The hash is SHA-256 of the RGB pixels (rows top-down, 3 bytes a pixel, alpha
dropped), so it does not depend on the file format. A frame passes when its
hash equals the reference's, or else when every channel's mean absolute
difference from the reference PNG is at most `max_channel_mae` (0..255) and
the share of pixels differing by more than `pixel_tol` in any channel is at
most `max_bad_fraction`, and in no 64x64 tile is that share above
`max_tile_bad_fraction`; each frame may override any of the limits, and
its `regions` may set their own tile limit (see tile_violation()). A frame with a reference hash and no reference PNG
can only pass by hash.

A frame whose content legitimately comes in a few fixed forms (the hub's
camera opens on one of several views at random) lists them as
`references`: [{"label", "sha256", "size"}, ...], with the PNGs at
frames/<name>.<label>.png, instead of one sha256. It passes when it matches
any one of them by hash or within the frame's limits, the same limits for
each, so every reference is checked as strictly as a single one.

A frame with `split` (the hub: a fixed 2D panel over a random 3D view) is
judged in parts instead: the panel's opaque overlay strictly in any view,
the panel rects strictly and the background loosely against the view the
background matches. A view not seen before is NEWVIEW, which is
INCOMPLETE: someone looks at it and records it. See "split frames" below.

`dumpat` and `check` print a WARNING (stderr; never a failure) when a game
process is running (scripts/running_game.py): an installed copy left open
beside a Metal or CPU golden run makes its timings noisy.
"""

import contextlib
import hashlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GOLDEN_DIR = os.path.normpath(os.path.join(HERE, "..", "analysis", "golden"))
GOLDEN_JSON = os.path.join(GOLDEN_DIR, "golden.json")
FRAMES_DIR = os.path.join(GOLDEN_DIR, "frames")


# ---- images: (width, height, rgb bytes top-down) ----------------------------

def read_bmp(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:2] != b"BM":
        raise ValueError(f"{path}: not a BMP")
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    bpp = struct.unpack_from("<H", d, 28)[0]
    if bpp not in (24, 32):
        raise ValueError(f"{path}: {bpp} bpp BMP not supported")
    bypp = bpp // 8
    stride = (w * bypp + 3) & ~3
    rows = range(abs(h)) if h < 0 else range(h - 1, -1, -1)
    out = bytearray()
    for y in rows:
        row = d[off + y * stride: off + y * stride + w * bypp]
        px = bytearray(w * 3)
        px[0::3] = row[2::bypp]
        px[1::3] = row[1::bypp]
        px[2::3] = row[0::bypp]
        out += px
    return w, abs(h), bytes(out)


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not a PNG")
    pos, idat, w = 8, b"", None
    while pos < len(d):
        n, typ = struct.unpack_from(">I4s", d, pos)
        body = d[pos + 8: pos + 8 + n]
        pos += 12 + n
        if typ == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if depth != 8 or ctype not in (2, 6) or inter:
                raise ValueError(f"{path}: only 8-bit RGB/RGBA non-interlaced PNG")
            bypp = 3 if ctype == 2 else 4
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
    raw = zlib.decompress(idat)
    stride = w * bypp
    prev = bytearray(stride)
    out = bytearray()
    i = 0
    for _ in range(h):
        ft = raw[i]
        cur = bytearray(raw[i + 1: i + 1 + stride])
        i += 1 + stride
        if ft == 1:
            for x in range(bypp, stride):
                cur[x] = (cur[x] + cur[x - bypp]) & 255
        elif ft == 2:
            for x in range(stride):
                cur[x] = (cur[x] + prev[x]) & 255
        elif ft == 3:
            for x in range(stride):
                left = cur[x - bypp] if x >= bypp else 0
                cur[x] = (cur[x] + ((left + prev[x]) >> 1)) & 255
        elif ft == 4:
            for x in range(stride):
                left = cur[x - bypp] if x >= bypp else 0
                ul = prev[x - bypp] if x >= bypp else 0
                cur[x] = (cur[x] + _paeth(left, prev[x], ul)) & 255
        elif ft != 0:
            raise ValueError(f"{path}: bad PNG filter {ft}")
        if bypp == 4:
            rgb = bytearray(w * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = cur[0::4], cur[1::4], cur[2::4]
            out += rgb
        else:
            out += cur
        prev = cur
    return w, h, bytes(out)


def write_png(path, w, h, rgb):
    stride = w * 3
    raw = b"".join(b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(h))

    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))


def read_image(path):
    with open(path, "rb") as f:
        magic = f.read(2)
    return read_bmp(path) if magic == b"BM" else read_png(path)


def pixel_sha(img):
    w, h, rgb = img
    return hashlib.sha256(struct.pack("<II", w, h) + rgb).hexdigest()


TILE = 64


def stats(a, b, pixel_tol):
    """Per-channel mean abs diff, max diff, and the share of pixels with any
    channel off by more than pixel_tol."""
    (wa, ha, pa), (wb, hb, pb) = a, b
    if (wa, ha) != (wb, hb):
        return None
    n = wa * ha
    sums, maxs = [0, 0, 0], [0, 0, 0]
    if pa == pb:
        return {"mae": [0.0] * 3, "max": [0] * 3, "bad_fraction": 0.0,
                "worst_tile": 0.0, "worst_tile_at": (0, 0), "tiles": []}
    # Histogram of |a-b| per channel via a difference table: fast enough in
    # pure Python for 640x480 (a second or two).
    bad = 0
    for c in range(3):
        ca, cb = pa[c::3], pb[c::3]
        if ca == cb:
            continue
        hist = [0] * 256
        for x, y in zip(ca, cb):
            hist[x - y if x >= y else y - x] += 1
        sums[c] = sum(i * k for i, k in enumerate(hist))
        maxs[c] = max(i for i, k in enumerate(hist) if k)
    # Bad pixels, also counted per TILE x TILE tile: run-to-run noise (timer
    # digits, an idle pose) is scattered or small, a missing HUD element or an
    # inset is a contiguous block, so the worst tile catches what the global
    # share is too coarse for. Two grids, the second shifted by TILE/2 in x
    # and y: a block straddling a corner of one grid lies mostly in one tile
    # of the other, so the max over both does not depend on the grid's phase.
    # The shifted grid keeps only its full tiles; the strips it drops (up to
    # TILE-1 px wide) are covered by the first grid's tiles, partial ones
    # with their true area.
    H = TILE // 2
    tw, th = (wa + TILE - 1) // TILE, (ha + TILE - 1) // TILE
    tbad = [0] * (tw * th)
    sw, sh = (wa + H) // TILE + 1, (ha + H) // TILE + 1
    sbad = [0] * (sw * sh)
    if any(maxs) and max(maxs) > pixel_tol:
        for y in range(ha):
            row = 3 * y * wa
            ty = (y // TILE) * tw
            sy = ((y + H) // TILE) * sw
            for x in range(wa):
                j = row + 3 * x
                if (abs(pa[j] - pb[j]) > pixel_tol or abs(pa[j + 1] - pb[j + 1]) > pixel_tol
                        or abs(pa[j + 2] - pb[j + 2]) > pixel_tol):
                    bad += 1
                    tbad[ty + x // TILE] += 1
                    sbad[sy + (x + H) // TILE] += 1
    worst, wt, tiles = 0.0, (0, 0), []
    for t, k in enumerate(tbad):
        if not k:
            continue
        tx, ty = t % tw, t // tw
        area = (min(TILE, wa - tx * TILE)) * (min(TILE, ha - ty * TILE))
        tiles.append((tx * TILE, ty * TILE, k / area))
    for t, k in enumerate(sbad):
        x0, y0 = (t % sw) * TILE - H, (t // sw) * TILE - H
        if k and x0 >= 0 and y0 >= 0 and x0 + TILE <= wa and y0 + TILE <= ha:
            tiles.append((x0, y0, k / (TILE * TILE)))
    for x0, y0, frac in tiles:
        if frac > worst:
            worst, wt = frac, (x0, y0)
    return {"mae": [s / n for s in sums], "max": maxs, "bad_fraction": bad / n,
            "worst_tile": worst, "worst_tile_at": wt, "tiles": tiles}


def tile_limit(x, y, frame_limit, regions):
    """The limit for the tile at x,y and the region that set it (or None)."""
    for r in regions:
        rx, ry, rw, rh = r["rect"]
        if x < rx + rw and x + TILE > rx and y < ry + rh and y + TILE > ry:
            return r["max_tile_bad_fraction"], r
    return frame_limit, None


def tile_violation(s, frame_limit, regions):
    """The tile furthest over its limit, as (x, y, share, limit), or None. A
    region {"rect": [x, y, w, h], "max_tile_bad_fraction": v} sets the limit
    of every tile that overlaps it (first match wins): a shifted tile that
    straddles the rect's edge holds the region's noise too. Its part outside
    the rect is still judged at the frame's limit by the aligned tiles under
    it when the rect lies on TILE bounds (keep it so)."""
    worst = None
    for x, y, frac in s["tiles"]:
        lim, _ = tile_limit(x, y, frame_limit, regions)
        if frac > lim and (worst is None or frac - lim > worst[2] - worst[3]):
            worst = (x, y, frac, lim)
    return worst


# ---- split frames: a fixed overlay over a 3D view that varies ---------------
#
# A frame with "split" is judged in parts instead of as a whole. Its panel is
# the 2D overlay (text, a counter, a prompt) at fixed rects; the rest is the
# 3D background. golden.json:
#
#   "split": {
#     "panel":      {"rects": [[x, y, w, h], ...], <limits>},
#     "overlay":    {"max_spread": S, "min_luma": L, "min_pixels": N,
#                    "max_bad_fraction": F},
#     "background": {<limits>, "new_view_min_mae": M, "min_luma_std": D}
#   }
#
# <limits> are max_channel_mae, max_bad_fraction and max_tile_bad_fraction,
# over the selected pixels only (a tile's share is of its selected pixels;
# tiles with under TILE*TILE/8 of them are not judged on their own).
#
# 1. Overlay (view-independent, strict). The pixels in the panel rects where
#    every reference agrees within S in each channel and is at least L luma
#    are the opaque overlay: the same in every view. Fewer than N such pixels
#    is a setup error. The frame must match them (within the frame's
#    pixel_tol of the references' range) with at most F bad, whatever the
#    view; otherwise FAIL.
# 2. Known view. A reference whose background matches within the
#    background's (loose) limits names the view; the panel rects must then
#    match that reference within the panel's (strict) limits: CLOSE, else
#    FAIL.
# 3. Unknown view. No background matches. If the panel rects match a view
#    (their translucent parts show the scene, so other views do not), or the
#    closest background is within mae M of it (new_view_min_mae; different
#    views are far apart), it is that view rendered differently: FAIL. A flat
#    background (luma standard deviation under D, min_luma_std): FAIL.
#    Otherwise NEWVIEW, which is INCOMPLETE, not a pass: the overlay holds
#    the opaque text, but the scene is unchecked and a broken render can
#    look like a new view. Look at it; if it is right, record it (golden.py
#    reference) so it is held from then on.

def luma(p, j):
    return (299 * p[j] + 587 * p[j + 1] + 114 * p[j + 2]) // 1000


def rect_mask(w, h, rects):
    m = bytearray(w * h)
    for rx, ry, rw, rh in rects:
        x0, x1 = max(0, rx), min(w, rx + rw)
        for y in range(max(0, ry), min(h, ry + rh)):
            m[y * w + x0: y * w + x1] = b"\x01" * (x1 - x0)
    return m


def masked_stats(a, b, tol, idx):
    """stats() over the pixel indexes idx only. Tiles: the aligned grid, each
    tile's share of bad pixels among its selected ones."""
    (w, h, pa), (wb, hb, pb) = a, b
    if (w, h) != (wb, hb):
        return None
    tw = (w + TILE - 1) // TILE
    tsel, tbad = {}, {}
    sums, maxs, bad = [0, 0, 0], [0, 0, 0], 0
    for i in idx:
        j = 3 * i
        d0, d1, d2 = abs(pa[j] - pb[j]), abs(pa[j + 1] - pb[j + 1]), abs(pa[j + 2] - pb[j + 2])
        sums[0] += d0
        sums[1] += d1
        sums[2] += d2
        if d0 > maxs[0]:
            maxs[0] = d0
        if d1 > maxs[1]:
            maxs[1] = d1
        if d2 > maxs[2]:
            maxs[2] = d2
        t = (i // w // TILE) * tw + (i % w) // TILE
        tsel[t] = tsel.get(t, 0) + 1
        if d0 > tol or d1 > tol or d2 > tol:
            bad += 1
            tbad[t] = tbad.get(t, 0) + 1
    n = max(1, len(idx))
    worst, wt = 0.0, (0, 0)
    for t, k in tbad.items():
        if tsel[t] >= TILE * TILE // 8 and k / tsel[t] > worst:
            worst, wt = k / tsel[t], ((t % tw) * TILE, (t // tw) * TILE)
    return {"mae": [x / n for x in sums], "max": maxs, "bad_fraction": bad / n,
            "worst_tile": worst, "worst_tile_at": wt, "n": len(idx)}


def within(s, lim):
    return (max(s["mae"]) <= lim["max_channel_mae"] and s["bad_fraction"] <= lim["max_bad_fraction"]
            and s["worst_tile"] <= lim["max_tile_bad_fraction"])


def apply_masks(img, ref, fr):
    """img with the pixels under fr's masks taken from ref (see Masks)."""
    rects = [m["rect"] for m in fr.get("masks", [])]
    if not rects or (img[0], img[1]) != (ref[0], ref[1]):
        return img
    w, h, p = img
    out, src = bytearray(p), ref[2]
    for rx, ry, rw, rh in rects:
        x0, x1 = max(0, rx), min(w, rx + rw)
        for y in range(max(0, ry), min(h, ry + rh)):
            a, b = 3 * (y * w + x0), 3 * (y * w + x1)
            out[a:b] = src[a:b]
    return w, h, bytes(out)


def mask_presence(img, ref, fr):
    """None, or why a mask's "presence" check failed: the masked pixels may
    animate, but must still be roughly the reference's (the button is
    there, not some other screen): at most max_bad_fraction off by more
    than pixel_tol, and every channel's mae at most max_channel_mae."""
    w, h, _ = img
    for m in fr.get("masks", []):
        pr = m.get("presence")
        if not pr:
            continue
        mk = rect_mask(w, h, [m["rect"]])
        st = masked_stats(img, ref, pr["pixel_tol"], [i for i in range(w * h) if mk[i]])
        if st is None:
            return "size differs"
        if st["bad_fraction"] > pr["max_bad_fraction"] or max(st["mae"]) > pr["max_channel_mae"]:
            return ("masked rect %s: mae %s, %.1f%% off by more than %d (presence limits mae %s,"
                    " %.1f%%)" % (",".join(map(str, m["rect"])),
                                  "/".join("%.1f" % x for x in st["mae"]),
                                  100 * st["bad_fraction"], pr["pixel_tol"],
                                  pr["max_channel_mae"], 100 * pr["max_bad_fraction"]))
    return None


def split_parts(fr, refs):
    """(panel idx, background idx, overlay [(i, lo, hi)]) for a split frame,
    from its references' images refs (a list). Masked pixels are in none."""
    sp = fr["split"]
    w, h, _ = refs[0]
    pm = rect_mask(w, h, sp["panel"]["rects"])
    mm = rect_mask(w, h, [m["rect"] for m in fr.get("masks", [])])
    panel = [i for i in range(w * h) if pm[i] and not mm[i]]
    back = [i for i in range(w * h) if not pm[i] and not mm[i]]
    ov, S, L = [], sp["overlay"]["max_spread"], sp["overlay"]["min_luma"]
    for i in panel:
        j = 3 * i
        lo = [min(r[2][j + c] for r in refs) for c in range(3)]
        hi = [max(r[2][j + c] for r in refs) for c in range(3)]
        if max(hi[c] - lo[c] for c in range(3)) <= S and min(luma(r[2], j) for r in refs) >= L:
            ov.append((i, lo, hi))
    return panel, back, ov


def overlay_bad(img, ov, tol):
    p, bad = img[2], 0
    for i, lo, hi in ov:
        j = 3 * i
        for c in range(3):
            if p[j + c] < lo[c] - tol or p[j + c] > hi[c] + tol:
                bad += 1
                break
    return bad / max(1, len(ov))


def luma_std(img, idx):
    p = img[2]
    v = [luma(p, 3 * i) for i in idx]
    m = sum(v) / max(1, len(v))
    return (sum((x - m) ** 2 for x in v) / max(1, len(v))) ** 0.5


def split_fmt(s):
    return "mae %s bad %.3f%% tile %.1f%% at %d,%d" % (
        "/".join("%.2f" % m for m in s["mae"]), 100 * s["bad_fraction"],
        100 * s["worst_tile"], *s["worst_tile_at"])


def check_split(tag, fr, th, refs, have, imgs):
    """Judge a split frame (see above); print the verdict, return 0/1/2."""
    sp = fr["split"]
    tol = fr.get("pixel_tol", th["pixel_tol"])
    present = [r for r in refs if os.path.exists(r[2])]
    if len(present) != len(refs):
        for r in refs:
            if r not in present:
                print(f"FAIL     {tag}: no reference PNG at {r[2]}")
                print("         " + missing_ref_hint(fr, r))
        print("         (a split frame's overlay needs every reference)")
        return 1
    ref_imgs = {r[0]: read_image(r[2]) for r in present}
    panel, back, ov = split_parts(fr, list(ref_imgs.values()))
    if len(ov) < sp["overlay"]["min_pixels"]:
        print(f"FAIL     {tag}: overlay has {len(ov)} pixels, under min_pixels "
              f"{sp['overlay']['min_pixels']} (panel rects or references wrong?)")
        return 1
    # The view-independent overlay, on any target (they differ only by anchor).
    img0 = imgs[next(iter(have.values()))]
    ob = overlay_bad(img0, ov, tol)
    ov_ok = ob <= sp["overlay"]["max_bad_fraction"]
    ov_line = "overlay %d px, bad %.3f%% (limit %.2f%%)" % (
        len(ov), 100 * ob, 100 * sp["overlay"]["max_bad_fraction"])
    results = []
    for label, _, _ in refs:
        if label not in have:
            continue
        img = imgs[have[label]]
        ps = masked_stats(img, ref_imgs[label], tol, panel)
        bs = masked_stats(img, ref_imgs[label], tol, back)
        if ps is None or bs is None:
            print(f"FAIL     {tag}: size {img[0]}x{img[1]} differs from {label}")
            return 1
        results.append((within(bs, sp["background"]), within(ps, sp["panel"]), ps, bs, label))
    # The view is the reference whose background matches; then its panel
    # must too. Else the closest background.
    views = [r for r in results if r[0]]
    best = (([r for r in views if r[1]] or views)[0] if views
            else min(results, key=lambda r: max(r[3]["mae"])))
    _, panel_ok, ps, bs, label = best
    detail = "panel %s; background %s" % (split_fmt(ps), split_fmt(bs))
    if not ov_ok:
        print(f"FAIL     {tag}: {ov_line}")
        print(f"         closest view {label}: {detail}")
        return 1
    if views:
        print(f"{'CLOSE   ' if panel_ok else 'FAIL    '} {tag} vs {label}: {ov_line}")
        print(f"         {detail}" + ("" if panel_ok else " (panel outside its limits)"))
        return 0 if panel_ok else 1
    # The panel's translucent text shows the background through it, so a
    # panel that matches a view whose background does not is that view
    # with its scene rendered differently (lighting, fog, missing models).
    twin = [r for r in results if r[1]]
    if twin:
        _, _, tps, tbs, tlabel = twin[0]
        print(f"FAIL     {tag}: panel matches view {tlabel} but its background "
              f"does not: that view, rendered differently")
        print(f"         {ov_line}; panel {split_fmt(tps)}; background {split_fmt(tbs)}")
        return 1
    near = sp["background"]["new_view_min_mae"]
    if max(bs["mae"]) < near:
        print(f"FAIL     {tag}: background is near view {label} (mae {max(bs['mae']):.2f} < "
              f"{near}) but outside its limits: that view, rendered differently")
        print(f"         {ov_line}; {detail}")
        return 1
    std = luma_std(img0, back)
    floor = sp["background"]["min_luma_std"]
    if std < floor:
        print(f"FAIL     {tag}: no known view, and the background is flat "
              f"(luma std {std:.1f} < {floor})")
        print(f"         {ov_line}; closest view {label}: {detail}")
        return 1
    print(f"NEWVIEW  {tag}: matches no known view; {ov_line}; background luma std {std:.1f}")
    print(f"         closest view {label}: {detail}")
    print(f"         if the view is right, record it: golden.py reference "
          f"{tag.split('/')[0]} {fr['name']} LABEL DIR")
    # Not a pass: the text agrees but the scene is unchecked, and a broken
    # render of a known view can look like a new one. Someone looks first.
    return 2


def frame_refs(fr):
    """(label, sha256, PNG path) of each reference of a frame: its
    `references`, or its one sha256 (label None) at frames/<name>.png."""
    if "references" in fr:
        return [(r["label"], r["sha256"],
                 os.path.join(FRAMES_DIR, "%s.%s.png" % (fr["name"], r["label"])))
                for r in fr["references"]]
    return [(None, fr["sha256"], os.path.join(FRAMES_DIR, fr["name"] + ".png"))]


def missing_ref_hint(fr, ref=None):
    """'reference missing: ...' naming a git worktree of this repo whose copy
    of the PNG has the recorded hash. The PNGs are gitignored (game frames),
    so a merge carries the hash but not the picture. ref: one of
    frame_refs(fr), default the first."""
    _, sha, path = ref or frame_refs(fr)[0]
    rel = os.path.relpath(path, REPO)
    found = []
    try:
        out = subprocess.run(["git", "-C", REPO, "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if not line.startswith("worktree "):
                continue
            wt = line[len("worktree "):]
            cand = os.path.join(wt, rel)
            if os.path.realpath(wt) == os.path.realpath(REPO) or not os.path.exists(cand):
                continue
            try:
                ok = pixel_sha(read_image(cand)) == sha
            except Exception:
                ok = False
            found.append((ok, cand))
    except Exception:
        pass
    good = [c for ok, c in found if ok]
    if good:
        return f"reference missing: {rel}; copy from {good[0]}"
    if found:
        return (f"reference missing: {rel}; {found[0][1]} exists but its hash is not the "
                f"recorded {sha[:16]}")
    return f"reference missing: {rel}; no worktree has it (record it, or copy it from the recording checkout)"


def cmd_refs(args):
    """Name every frame whose reference PNG is missing; exit 2 if any."""
    g = load_golden()
    miss = 0
    for scen, sc in g["scenarios"].items():
        for fr in sc["frames"]:
            for ref in frame_refs(fr):
                if not os.path.exists(ref[2]):
                    lab = f" ({ref[0]})" if ref[0] else ""
                    print(f"golden: WARNING {scen}/{fr['name']}{lab}: " + missing_ref_hint(fr, ref))
                    miss += 1
    return 2 if miss else 0


# ---- golden.json ---------------------------------------------------------------

def load_golden():
    with open(GOLDEN_JSON) as f:
        return json.load(f)


def frame_path(d, index):
    return os.path.join(d, "frame_%04d.bmp" % index)


def flip_path(d, flip):
    return os.path.join(d, "flip_%05d.bmp" % flip)


def dump_image_path(d, index):
    """Dump `index` of DIR: frame_NNNN.bmp, else flip 60*index + 1."""
    p = frame_path(d, index)
    if os.path.exists(p):
        return p
    q = flip_path(d, 60 * index + 1)
    return q if os.path.exists(q) else p


FLIP_RE = None


def flip_batches(log):
    """{flip: batches} from a run's RECOMP_TRACE=flip lines (the backend's
    "[D3D11] flip N batches B" / "[METAL] flip N batches B", else the CPU
    path's "[GPU] flip N ... batches B"), or None. Under a backend the walker
    prints a "[GPU]" line too, with batches 0; the backend's line wins."""
    global FLIP_RE
    import re
    if FLIP_RE is None:
        FLIP_RE = re.compile(r"^\[(D3D11|METAL|GPU)\] flip (\d+)\b.*?\bbatches (\d+)")
    out = {}
    try:
        with open(log, errors="replace") as f:
            for line in f:
                m = FLIP_RE.match(line)
                if m:
                    flip, b = int(m.group(2)), int(m.group(3))
                    if m.group(1) == "GPU":
                        out.setdefault(flip, b)
                    else:
                        out[flip] = b
    except OSError:
        return None
    return out or None


TIME_RE = None


def flip_times(log):
    """{flip: wall ms} from the walker's "[GPU] flip N T ms" lines, which
    every backend prints under RECOMP_TRACE=flip, or None."""
    global TIME_RE
    import re
    if TIME_RE is None:
        TIME_RE = re.compile(r"^\[GPU\] flip (\d+) (\d+) ms\b")
    out = {}
    try:
        with open(log, errors="replace") as f:
            for line in f:
                m = TIME_RE.match(line)
                if m:
                    out.setdefault(int(m.group(1)), int(m.group(2)))
    except (OSError, TypeError):
        return None
    return out or None


def pace(times, a, b):
    """Flips per wall second from flip a to flip b, or None if either flip
    has no time in the log or b is not after a."""
    if not times or a not in times or b not in times or b <= a:
        return None
    dt = times[b] - times[a]
    return (b - a) * 1000.0 / dt if dt > 0 else None


DEFAULT_MAX_PACE_DIFF = 0.10


def ref_pace(fr, label):
    """The reference run's pace (flips/s from its anchor to the frame) for
    reference `label` of frame fr, or None when not recorded."""
    for r in fr.get("references", []):
        if r["label"] == label and "anchor_flip" in r:
            return r.get("pace")
    return fr["anchor"].get("ref_pace")


def pace_report(fr, sc, th, batches, times):
    """For an anchored frame: (mismatch, notes). Each reference with a
    recorded pace is compared with the run's pace over the same span (its
    anchor to its target flip); mismatch is the first "pace mismatch (run X
    fps vs ref Y fps)" reason past max_pace_diff, or None. An unknown pace
    on either side is no check."""
    if "anchor" not in fr or not batches:
        return None, []
    ev = sc.get("anchors", {}).get(fr["anchor"]["event"])
    A = find_anchor(batches, ev) if ev else None
    if A is None:
        return None, []
    lim = DEFAULT_MAX_PACE_DIFF
    for src in (fr, sc, th):
        if "max_pace_diff" in src:
            lim = src["max_pace_diff"]
            break
    if lim is None:   # the frame follows flips, not wall time: no pace check
        return None, []
    mismatch, notes = None, []
    for label, _, _ in frame_refs(fr):
        target = A + 60 * fr["dump"] + 1 - ref_anchor_flip(fr, label)
        run = pace(times, A, target)
        ref = ref_pace(fr, label)
        who = "" if label is None else " (%s)" % label
        if target <= A:
            notes.append("pace%s: target flip %d not after anchor %d; not checked" % (
                who, target, A))
        elif run is None:
            notes.append("pace%s: flips %d-%d not timed in the run's log; not checked" % (
                who, A, target))
        elif ref is None:
            notes.append("pace%s: run %.1f fps over flips %d-%d, reference unknown; not checked"
                         % (who, run, A, target))
        else:
            notes.append("pace%s: run %.1f fps vs ref %.1f fps over flips %d-%d (limit +-%.0f%%)"
                         % (who, run, ref, A, target, 100 * lim))
            if mismatch is None and abs(run / ref - 1) > lim:
                mismatch = "pace mismatch (run %.1f fps vs ref %.1f fps)" % (run, ref)
    return mismatch, notes


DEFAULT_PACE_FAIL_BAD = 0.5


def pace_fail_bad(fr, sc, th):
    """The bad-pixel share at which a pace-mismatched frame FAILs anyway."""
    for src in (fr, sc, th):
        if "pace_fail_bad" in src:
            return src["pace_fail_bad"]
    return DEFAULT_PACE_FAIL_BAD


def raw_compares(refs, have, imgs, fr, th):
    """[(label, whole-frame stats)] against each reference with a PNG."""
    out = []
    for lab, _, rp in refs:
        if lab in have and os.path.exists(rp):
            _, st, _ = compare(imgs[have[lab]], rp, fr, th)
            if st is not None:
                out.append((lab, st))
    return out


def run_backend(log):
    """The run's render backend from its flip log: d3d11 or metal when that
    backend printed flip lines, cpu when only the walker did, None without a
    log or flip lines."""
    seen = None
    try:
        with open(log, errors="replace") as f:
            for line in f:
                if line.startswith("[D3D11] flip "):
                    return "d3d11"
                if line.startswith("[METAL] flip "):
                    return "metal"
                if seen is None and line.startswith("[GPU] flip "):
                    seen = "cpu"
    except (OSError, TypeError):
        return None
    return seen


ENHANCE_SCALE_RE = re.compile(r"\[ENHANCE\] render\.scale=(\d+) ")
ENHANCE_ASPECT_RE = re.compile(r"\[ENHANCE\].*display\.aspect=([0-9:]+)")
ENHANCE_PACING_RE = re.compile(r"\[ENHANCE\].* present\.pacing=(\w+)")
ENHANCE_FPS_RE = re.compile(r"\[ENHANCE\] fps\.mode=(\w+)")

# key -> (pattern, stock value)
ENHANCE_STOCK = (("render.scale", ENHANCE_SCALE_RE, "1"),
                 ("display.aspect", ENHANCE_ASPECT_RE, "4:3"),
                 ("present.pacing", ENHANCE_PACING_RE, "spin"),
                 ("fps.mode", ENHANCE_FPS_RE, "lock30"))


def enhance_nonstock(log, allow=()):
    """Why a run is not a stock run, from its enhancements lines, or None.
    Goldens always run at the title's stock resolution, aspect, pacing and
    frame rate: a render.scale other than 1, a display.aspect other than
    4:3, a present.pacing other than spin or an fps.mode other than lock30
    (asked for, even where the game falls back) makes the run unusable as a
    golden, whatever its frames look like. No [ENHANCE] line (a build
    without the layer) is stock.

    allow: "key=value" strings an evaluation run asked for on purpose
    (--allow-enhance); those are left out here and reported by
    enhance_allowed instead."""
    why = []
    try:
        with open(log, errors="replace") as f:
            for line in f:
                if "[ENHANCE]" not in line:
                    continue
                for key, rx, stock in ENHANCE_STOCK:
                    m = rx.search(line)
                    kv = f"{key}={m.group(1)}" if m else None
                    if m and m.group(1) != stock and kv not in why and kv not in allow:
                        why.append(kv)
    except (OSError, TypeError):
        return None
    return ", ".join(why) or None


def enhance_allowed(log, allow):
    """The --allow-enhance settings this run's log does show, for the note."""
    if not allow or not log:
        return []
    seen = []
    try:
        with open(log, errors="replace") as f:
            for line in f:
                if "[ENHANCE]" not in line:
                    continue
                for key, rx, _ in ENHANCE_STOCK:
                    m = rx.search(line)
                    kv = f"{key}={m.group(1)}" if m else None
                    if kv in allow and kv not in seen:
                        seen.append(kv)
    except OSError:
        return []
    return seen


def find_anchor(batches, ev):
    """The first flip at or after ev's after_flip where the batch count
    crosses into the event: at least min_batches (or, with max_batches
    instead, at most that many) on this flip and the next, and not on the
    flip before. One stray flip (a black or loading frame, or a flip whose
    backend line is missing so the walker's "batches 0" stands in) is not an
    event; flips missing from the log break a run of hits."""
    lo = ev.get("after_flip", 0)
    if "min_batches" in ev:
        hit = lambda n: n >= ev["min_batches"]
    else:
        hit = lambda n: n <= ev["max_batches"]
    for fl in sorted(batches):
        if (fl >= lo and hit(batches[fl])
                and fl - 1 in batches and not hit(batches[fl - 1])
                and fl + 1 in batches and hit(batches[fl + 1])):
            return fl
    return None


def run_log(d, logs, scen):
    if scen in logs:
        return logs[scen]
    for cand in (os.path.join(os.path.dirname(os.path.normpath(d)), "game-stdio.log"),
                 os.path.normpath(d) + ".log"):
        if os.path.exists(cand):
            return cand
    return None


def ref_anchor_flip(fr, label):
    """The reference run's anchor flip for reference `label` of frame fr."""
    for r in fr.get("references", []):
        if r["label"] == label and "anchor_flip" in r:
            return r["anchor_flip"]
    return fr["anchor"]["ref_flip"]


def parse_scen_args(args):
    out = {}
    for a in args:
        if "=" not in a:
            sys.exit(f"golden: expected SCENARIO=DIR, got {a}")
        k, v = a.split("=", 1)
        out[k] = v
    return out


def fmt(s):
    return "mae %s max %s bad %.4f%% worst tile %.1f%% at %d,%d" % (
        "/".join("%.3f" % m for m in s["mae"]), "/".join(map(str, s["max"])),
        100 * s["bad_fraction"], 100 * s["worst_tile"], *s["worst_tile_at"])


def compare(img, ref_path, fr, th):
    """(ok, stats, tile violation) of img against one reference PNG."""
    tol = fr.get("pixel_tol", th["pixel_tol"])
    mae_lim = fr.get("max_channel_mae", th["max_channel_mae"])
    bad_lim = fr.get("max_bad_fraction", th["max_bad_fraction"])
    tile_lim = fr.get("max_tile_bad_fraction", th["max_tile_bad_fraction"])
    ref = read_image(ref_path)
    s = stats(apply_masks(img, ref, fr), ref, tol)
    if s is None:
        return False, None, None
    pres = mask_presence(img, ref, fr)
    if pres:
        s["presence"] = pres
        return False, s, tile_violation(s, tile_lim, fr.get("regions", []))
    tv = tile_violation(s, tile_lim, fr.get("regions", []))
    return max(s["mae"]) <= mae_lim and s["bad_fraction"] <= bad_lim and tv is None, s, tv


def frame_targets(d, fr, sc, batches):
    """{reference label: (image path, note)} for frame fr in run dir d. An
    anchored frame maps each reference to the flip at the same distance from
    the run's anchor event as the reference was from its own; without flip
    dumps or a log, the plain dump (and a note why). An anchored frame
    whose run misses the anchor, the target flip, or flip dumps altogether
    (none pulled, say) gets path None: the check cannot be made as
    recorded, so it is INCOMPLETE, not a compare of the plain dump."""
    out = {}
    plain = dump_image_path(d, fr["dump"])
    for label, _, _ in frame_refs(fr):
        if "anchor" not in fr:
            out[label] = (plain, None)
            continue
        ev = sc.get("anchors", {}).get(fr["anchor"]["event"])
        if ev is None:
            sys.exit(f"golden: {fr['name']}: no anchor event {fr['anchor']['event']!r} in its scenario")
        R = ref_anchor_flip(fr, label)
        A = find_anchor(batches, ev) if batches else None
        if A is None:
            why = ("not in the run's flip log" if batches
                   else "no flip log (RECOMP_TRACE=flip; --log)")
            out[label] = (None, "anchor %s: %s" % (fr["anchor"]["event"], why))
            continue
        target = A + 60 * fr["dump"] + 1 - R
        fp = flip_path(d, target)
        if os.path.exists(fp):
            out[label] = (fp, "anchor %s at flip %d (reference %d): flip %d" % (
                fr["anchor"]["event"], A, R, target))
        else:
            out[label] = (None, "anchor %s at flip %d (reference %d): no %s (not dumped or"
                          " not pulled; dump_slack?)" % (
                              fr["anchor"]["event"], A, R, os.path.basename(fp)))
    return out


def window_report(d, img_path, ref, fr, th, k):
    """Compare the flips within k of img_path's flip with ref; the best."""
    import re
    m = re.search(r"flip_(\d+)\.bmp$", img_path)
    if not m or k <= 0 or not os.path.exists(ref[2]):
        return None
    t = int(m.group(1))
    best = None
    for off in range(-k, k + 1):
        p = flip_path(d, t + off)
        if not os.path.exists(p):
            continue
        ok, s, _ = compare(read_image(p), ref[2], fr, th)
        if s is not None and (best is None or s["bad_fraction"] < best[2]["bad_fraction"]):
            best = (off, ok, s)
    return best


def cmd_check(args):
    g = load_golden()
    th = g["compare"]
    window, logs, rest, allow = 2, {}, [], []
    it = iter(args)
    for a in it:
        if a == "--window":
            window = int(next(it))
        elif a == "--log":
            logs.update(parse_scen_args([next(it)]))
        elif a == "--allow-enhance":
            kv = next(it)
            if "=" not in kv or kv.split("=", 1)[0] not in {k for k, _, _ in ENHANCE_STOCK}:
                sys.exit(f"golden: --allow-enhance takes KEY=VALUE with KEY one of "
                         + ", ".join(k for k, _, _ in ENHANCE_STOCK))
            allow.append(kv)
        else:
            rest.append(a)
    dirs = parse_scen_args(rest)
    rcs = []   # per frame: 1 FAIL, 2 INCOMPLETE (MISSING, NEWVIEW too)
    for scen, d in dirs.items():
        sc = g["scenarios"].get(scen)
        if sc is None:
            sys.exit(f"golden: no scenario {scen} in {GOLDEN_JSON}")
        log = run_log(d, logs, scen)
        batches = flip_batches(log) if log else None
        times = flip_times(log) if log else None
        backend = run_backend(log) if log else None
        nonstock = enhance_nonstock(log, allow) if log else None
        if nonstock:
            print(f"FAIL     {scen}: not a stock run ({nonstock} in {log}); goldens run"
                  " at the stock resolution, aspect, pacing and frame rate, frames"
                  " not compared")
            rcs.append(1)
            continue
        for kv in enhance_allowed(log, allow):
            print(f"NOTE     {scen}: evaluation run with {kv} (--allow-enhance);"
                  " not a stock run, never recorded")
        for fr in sc["frames"]:
            tag = f"{scen}/{fr['name']} (dump {fr['dump']}, present {fr['dump'] * 60 + 1})"
            skip = fr.get("skip_backends", sc.get("skip_backends", []))
            if backend in skip:
                print(f"SKIP     {tag}: not checked on the {backend} backend "
                      f"({fr.get('skip_why', sc.get('skip_why', 'see golden.json'))})")
                continue
            targets = frame_targets(d, fr, sc, batches)
            refs = frame_refs(fr)
            multi = len(refs) > 1 or refs[0][0] is not None
            notes = sorted({n for _, n in targets.values() if n})
            if any(p is None for p, _ in targets.values()):
                print(f"INCOMPLETE {tag}: the anchored flip is not checkable in this run")
                for n in notes:
                    print("         " + n)
                rcs.append(2)
                continue
            have = {lab: p for lab, (p, _) in targets.items() if os.path.exists(p)}
            if not have:
                p = targets[refs[0][0]][0]
                print(f"MISSING  {tag}: {p} not dumped (run too short or crashed?)")
                for n in notes:
                    print("         " + n)
                rcs.append(2)
                continue
            imgs = {p: read_image(p) for p in set(have.values())}
            mismatch, pnotes = pace_report(fr, sc, th, batches, times)
            notes += pnotes
            hit = [r for r in refs if r[0] in have and pixel_sha(imgs[have[r[0]]]) == r[1]]
            if hit:
                print(f"EXACT    {tag}" + (f" = {hit[0][0]}" if multi else ""))
                for n in notes:
                    print("         " + n)
                continue
            floor = pace_fail_bad(fr, sc, th)
            if "split" in fr:
                if not mismatch:
                    rcs.append(check_split(tag, fr, th, refs, have, imgs))
                    for n in notes:
                        print("         " + n)
                    continue
                # Pace mismatch: the split verdict stands when it passes
                # (CLOSE) or is already INCOMPLETE (NEWVIEW); a FAIL is
                # INCOMPLETE unless the frame is a wrong screen at any pace.
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = check_split(tag, fr, th, refs, have, imgs)
                raw = raw_compares(refs, have, imgs, fr, th)
                if rc == 1:
                    gross = bool(raw) and min(st["bad_fraction"] for _, st in raw) >= floor
                    rc = 1 if gross else 2
                    print((f"FAIL     {tag}: wrong screen at any pace ({mismatch}): "
                           f"every reference off by {100 * floor:.0f}%+ of pixels") if gross else
                          f"INCOMPLETE {tag}: {mismatch}; the split compare failed, not judged")
                    for line in buf.getvalue().splitlines():
                        print("         for information: " + line.strip())
                else:
                    sys.stdout.write(buf.getvalue())
                    if rc == 0:
                        print(f"         {mismatch}, but within limits")
                for n in notes:
                    print("         " + n)
                for lab, st in raw:
                    print("         for information, whole frame vs %s: %s" % (lab, fmt(st)))
                rcs.append(rc)
                continue
            tol = fr.get("pixel_tol", th["pixel_tol"])
            mae_lim = fr.get("max_channel_mae", th["max_channel_mae"])
            bad_lim = fr.get("max_bad_fraction", th["max_bad_fraction"])
            tile_lim = fr.get("max_tile_bad_fraction", th["max_tile_bad_fraction"])
            lims = f"(limits mae {mae_lim}, bad {100 * bad_lim:.2f}%, tile {100 * tile_lim:.0f}% at tol {tol})"
            # One result per reference with a PNG and an image: (ok, s, tv, label).
            results, absent = [], []
            for ref in refs:
                if not os.path.exists(ref[2]):
                    absent.append(ref)
                    continue
                if ref[0] not in have:
                    continue
                ok, s, tv = compare(imgs[have[ref[0]]], ref[2], fr, th)
                results.append((ok, s, tv, ref[0]))
            for ref in absent:
                sha = pixel_sha(next(iter(imgs.values())))
                print(f"{'WARNING ' if results else 'FAIL    '} {tag}: no reference PNG at {ref[2]} "
                      f"(got {sha[:16]}, want {ref[1][:16]})")
                print("         " + missing_ref_hint(fr, ref))
            if not results:
                rcs.append(1)
                continue
            # Report the passing reference, else the closest one.
            ok, s, tv, label = max(results, key=lambda r: (r[0], r[1] is not None,
                                                          -(r[1]["bad_fraction"] if r[1] else 1)))
            name = f" vs {label}" if multi else ""
            if s is None:
                img = imgs[have[label]]
                print(f"FAIL     {tag}{name}: size {img[0]}x{img[1]} differs from the reference")
                rcs.append(1)
                continue
            rc, why = (0 if ok else 1), ""
            if ok:
                head = "CLOSE   "
                if mismatch:
                    notes.append(f"{mismatch}, but within limits")
            elif not mismatch:
                head = "FAIL    "
            elif min(r[1]["bad_fraction"] for r in results if r[1] is not None) >= floor:
                # Off at every reference by this much: a wrong screen, which
                # no flip rate explains.
                head, why = "FAIL    ", f"wrong screen at any pace ({mismatch}): "
            else:
                # Wall-time content (the title's cloud movie) sits elsewhere
                # at another flip rate: not a verdict on the rendering.
                head, rc = "INCOMPLETE", 2
                why = f"{mismatch}; outside limits, not judged: "
            print(f"{head} {tag}{name}: {why}{fmt(s)} {lims}")
            for n in notes:
                print("         " + n)
            if multi and not ok:
                for o in results:
                    if o[3] != label and o[1] is not None:
                        print(f"         vs {o[3]}: {fmt(o[1])}")
            if s.get("presence"):
                print("         presence: " + s["presence"])
            if tv:
                print("         tile %d,%d: %.1f%% of its pixels off (limit %.0f%%)"
                      % (tv[0], tv[1], 100 * tv[2], 100 * tv[3]))
            else:
                # The printed tile limit is the frame's; say so when a region
                # set the worst tile's limit, or a pass looks like a bug.
                wl, wr = tile_limit(*s["worst_tile_at"], tile_lim, fr.get("regions", []))
                if wr is not None and s["worst_tile"] > tile_lim:
                    print("         worst tile is in region %s: limit %.0f%% there"
                          % (",".join(map(str, wr["rect"])), 100 * wl))
            ref = [r for r in refs if r[0] == label][0]
            best = window_report(d, have[label], ref, fr, th, window)
            if best is not None:
                print("         window +-%d: best flip offset %+d: %s%s" % (
                    window, best[0], fmt(best[2]), "" if best[1] else " (outside limits)"))
            if rc:
                rcs.append(rc)
    return verdict(rcs)


def verdict(rcs):
    """Print the run's verdict; exit 1 on any FAIL, else 2 on any
    INCOMPLETE, else 0. A FAIL is never hidden behind an INCOMPLETE."""
    nf, ni = rcs.count(1), rcs.count(2)
    counts = ", ".join(c for c in ("%d FAIL" % nf if nf else "",
                                   "%d INCOMPLETE" % ni if ni else "") if c)
    if nf:
        print("golden: REGRESSION (%s)" % counts)
        return 1
    if ni:
        print("golden: INCOMPLETE (%s)" % counts)
        return 2
    print("golden: pass")
    return 0


def cmd_dumpat(args):
    """The RECOMP_DEBUG=fb_dump_at= list for SCEN: each frame's flip (60*dump + 1),
    widened by --slack W (default the scenario's dump_slack, else 12; an
    anchored frame's run anchor may sit a few flips from the reference's)
    plus --window K (default 2)."""
    if not args:
        sys.exit("golden: dumpat SCEN [--slack W] [--window K]")
    scen, slack, window = args[0], None, 2
    it = iter(args[1:])
    for a in it:
        if a == "--slack":
            slack = int(next(it))
        elif a == "--window":
            window = int(next(it))
        else:
            sys.exit(f"golden: dumpat: unknown option {a}")
    sc = load_golden()["scenarios"].get(scen)
    if sc is None:
        sys.exit(f"golden: no scenario {scen} in {GOLDEN_JSON}")
    print(dumpat_ranges(sc, slack, window))
    return 0


def dumpat_ranges(sc, slack=None, window=2):
    """dumpat's list for scenario sc, as the string fb_dump_at takes."""
    if slack is None:
        slack = sc.get("dump_slack", 12)
    ranges = []
    for fr in sc["frames"]:
        f = 60 * fr["dump"] + 1
        w = window + (slack if "anchor" in fr else 0)
        ranges.append((max(1, f - w), f + w))
    ranges.sort()
    merged = []
    for a, b in ranges:
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return ",".join("%d-%d" % r if r[0] != r[1] else "%d" % r[0] for r in merged)


def cmd_pulls(args):
    """pulls SCEN LOG [--window K]: the flip_NNNNN.bmp names a check of SCEN
    reads from a run with this flip log: each anchored frame's target flip
    per reference, +-K (default 2, as check's --window), and flip 60*dump+1
    +-K for the others. For pulling only those from the bench host."""
    if len(args) < 2:
        sys.exit("golden: pulls SCEN LOG [--window K]")
    scen, log, window = args[0], args[1], 2
    if args[2:4] and args[2] == "--window":
        window = int(args[3])
    sc = load_golden()["scenarios"].get(scen)
    if sc is None:
        sys.exit(f"golden: no scenario {scen} in {GOLDEN_JSON}")
    batches = flip_batches(log)
    want = set()
    dumped = []
    for part in dumpat_ranges(sc).split(","):
        a, _, b = part.partition("-")
        dumped.append((int(a), int(b or a)))
    for fr in sc["frames"]:
        centres = [60 * fr["dump"] + 1]
        if "anchor" in fr and batches:
            ev = sc.get("anchors", {}).get(fr["anchor"]["event"])
            A = find_anchor(batches, ev) if ev else None
            if A is not None:
                centres += [A + 60 * fr["dump"] + 1 - ref_anchor_flip(fr, lab)
                            for lab, _, _ in frame_refs(fr)]
        for c in centres:
            want.update(range(max(1, c - window), c + window + 1))
    for f in sorted(want):
        if any(a <= f <= b for a, b in dumped):   # only what the run dumped
            print("flip_%05d.bmp" % f)
    return 0


def cmd_anchors(args):
    """Each scenario's anchor events as found in LOG."""
    if len(args) != 1:
        sys.exit("golden: anchors LOG")
    b = flip_batches(args[0])
    if not b:
        sys.exit(f"golden: no flip-log lines in {args[0]} (RECOMP_TRACE=flip)")
    for scen, sc in load_golden()["scenarios"].items():
        for name, ev in sc.get("anchors", {}).items():
            print("%s\t%s\t%s" % (scen, name, find_anchor(b, ev)))
    return 0


def record_anchor(fr, sc, d, scen):
    """For recording an anchored frame from run dir d: the run's anchor flip
    (it becomes the reference's), or exit if the run's log lacks it, since a
    reference with the wrong anchor flip would shift every later check."""
    if "anchor" not in fr:
        return None
    ev = sc.get("anchors", {}).get(fr["anchor"]["event"])
    if ev is None:
        sys.exit(f"golden: {fr['name']}: no anchor event {fr['anchor']['event']!r} in its scenario")
    log = run_log(d, {}, scen)
    batches = flip_batches(log) if log else None
    A = find_anchor(batches, ev) if batches else None
    if A is None:
        sys.exit(f"golden: {scen}/{fr['name']}: anchor {fr['anchor']['event']} not found in "
                 f"{log or 'the run (no game-stdio.log next to ' + d + ')'}; not recording")
    return A


def record_pace(fr, sc, d, scen, A):
    """The recording run's pace from its anchor flip A to the recorded
    flip (60*dump + 1), rounded, or None if its log has no flip times."""
    if A is None:
        return None
    log = run_log(d, {}, scen)
    p = pace(flip_times(log) if log else None, A, 60 * fr["dump"] + 1)
    return None if p is None else round(p, 2)


def cmd_record(args):
    """All or nothing: every frame must exist and decode before any reference
    changes; PNGs and the JSON are written as .tmp files and renamed last, so
    a short run cannot leave new PNGs next to old hashes."""
    g = load_golden()
    only = None
    if "--allow-enhance" in args:
        sys.exit("golden: --allow-enhance is for evaluating runs (check); references"
                 " are recorded from stock runs only")
    if args[:1] == ["--only"] and len(args) > 1:
        only, args = set(args[1].split(",")), args[2:]
    dirs = parse_scen_args(args)
    todo, missing = [], []
    for scen, d in dirs.items():
        if scen not in g["scenarios"]:
            sys.exit(f"golden: no scenario {scen} in {GOLDEN_JSON}")
        for fr in g["scenarios"][scen]["frames"]:
            if only is not None and fr["name"] not in only:
                continue
            if "references" in fr:
                if only is not None:
                    sys.exit(f"golden: {fr['name']} has references; record one with "
                             f"golden.py reference {scen} {fr['name']} LABEL DIR")
                print(f"golden: {scen}/{fr['name']} has references ("
                      + ",".join(r["label"] for r in fr["references"])
                      + "); left as they are (golden.py reference records one)")
                continue
            p = dump_image_path(d, fr["dump"])
            A = record_anchor(fr, g["scenarios"][scen], d, scen)
            (todo if os.path.exists(p) else missing).append((scen, fr, p, A))
    if only is not None:
        unknown = only - {t[1]["name"] for t in todo + missing}
        if unknown:
            sys.exit("golden: --only names no frame in these scenarios: " + ",".join(sorted(unknown)))
    if missing:
        for scen, fr, p, _ in missing:
            print(f"MISSING  {scen}/{fr['name']}: {p}")
        print("golden: not recording: frames missing; references unchanged")
        return 2
    os.makedirs(FRAMES_DIR, exist_ok=True)
    renames = []
    try:
        for scen, fr, p, A in todo:
            img = read_image(p)
            fr["sha256"] = pixel_sha(img)
            fr["size"] = [img[0], img[1]]
            if A is not None:
                fr["anchor"]["ref_flip"] = A
                fr["anchor"]["why"] = "the recording run's anchor (golden.py record, %s)" % (
                    os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(p)))))
                P = record_pace(fr, g["scenarios"][scen], os.path.dirname(p), scen, A)
                if P is None:
                    fr["anchor"].pop("ref_pace", None)
                else:
                    fr["anchor"]["ref_pace"] = P
            dst = os.path.join(FRAMES_DIR, fr["name"] + ".png")
            write_png(dst + ".tmp", *img)
            renames.append((dst + ".tmp", dst))
            print(f"recorded {scen}/{fr['name']} dump {fr['dump']} {fr['sha256'][:16]}"
                  + ("" if A is None else f" (anchor {fr['anchor']['event']} at flip {A})"))
        with open(GOLDEN_JSON + ".tmp", "w") as f:
            json.dump(g, f, indent=2)
            f.write("\n")
        renames.append((GOLDEN_JSON + ".tmp", GOLDEN_JSON))
    except BaseException:
        for tmp, _ in renames:
            if os.path.exists(tmp):
                os.remove(tmp)
        raise
    for tmp, dst in renames:
        os.replace(tmp, dst)
    return 0


def cmd_reference(args):
    """reference SCEN NAME LABEL DIR: DIR's dump of frame NAME becomes its
    reference LABEL. A frame with a single sha256 is turned into a list."""
    if len(args) != 4:
        sys.exit("golden: reference SCEN NAME LABEL DIR")
    scen, name, label, d = args
    if not label or not all(c.isalnum() or c in "-_" for c in label):
        sys.exit(f"golden: bad label {label!r} (letters, digits, - and _)")
    g = load_golden()
    sc = g["scenarios"].get(scen)
    if sc is None:
        sys.exit(f"golden: no scenario {scen} in {GOLDEN_JSON}")
    frs = [f for f in sc["frames"] if f["name"] == name]
    if not frs:
        sys.exit(f"golden: no frame {name} in {scen}")
    fr = frs[0]
    p = dump_image_path(d, fr["dump"])
    if not os.path.exists(p):
        print(f"MISSING  {scen}/{name}: {p}")
        return 2
    if "references" not in fr and "sha256" in fr:
        sys.exit(f"golden: {name} has a single reference; give it a `references` list first")
    A = record_anchor(fr, sc, d, scen)
    img = read_image(p)
    entry = {"label": label, "sha256": pixel_sha(img), "size": [img[0], img[1]]}
    if A is not None:
        entry["anchor_flip"] = A
        P = record_pace(fr, sc, d, scen, A)
        if P is not None:
            entry["pace"] = P
    refs = [r for r in fr.get("references", []) if r["label"] != label]
    refs.append(entry)
    refs.sort(key=lambda r: r["label"])
    fr["references"] = refs
    os.makedirs(FRAMES_DIR, exist_ok=True)
    dst = os.path.join(FRAMES_DIR, f"{name}.{label}.png")
    write_png(dst + ".tmp", *img)
    with open(GOLDEN_JSON + ".tmp", "w") as f:
        json.dump(g, f, indent=2)
        f.write("\n")
    os.replace(dst + ".tmp", dst)
    os.replace(GOLDEN_JSON + ".tmp", GOLDEN_JSON)
    print(f"recorded {scen}/{name} reference {label} dump {fr['dump']} {entry['sha256'][:16]}")
    return 0


def cmd_plan(args):
    g = load_golden()
    for scen, sc in g["scenarios"].items():
        env = dict(g.get("env", {}))
        for k, v in sc.get("env", {}).items():
            # The list variables add up; any other pin is replaced.
            if k in ("RECOMP_TRACE", "RECOMP_DEBUG") and env.get(k):
                v = env[k] + "," + v
            env[k] = v
        print("%s\t%d\t%s\t%s" % (scen, sc["seconds"], sc.get("min_flips", 0),
                                    " ".join(f"{k}={v}" for k, v in env.items())))
    return 0


def cmd_frames(args):
    for fr in load_golden()["scenarios"][args[0]]["frames"]:
        print("%04d" % fr["dump"])
    return 0


def cmd_diff(args):
    a, b = read_image(args[0]), read_image(args[1])
    tol = int(args[2]) if len(args) > 2 else 8
    sa, sb = pixel_sha(a), pixel_sha(b)
    s = stats(a, b, tol)
    print(f"{'same' if sa == sb else 'differ'}  {sa[:16]} {sb[:16]}  "
          + (fmt(s) if s else "size differs"))
    return 0 if sa == sb else 1


def warn_running_game():
    """A game outside the run (the installed copy, or one started by hand)
    makes a Metal or CPU golden run's timing-sensitive frames noisy. Warn
    only: on the Mac nothing holds a run lock that would make the match
    certainly foreign, and the caller may be running the game on purpose."""
    try:
        import running_game
        games = running_game.find_games(running_game.list_processes(), os.getpid())
    except Exception:   # a listing failure must never fail a golden check
        return
    for pid, cmd in games:
        print("golden: WARNING a game process is running (pid %d: %s); a run "
              "overlapping it has noisy timings" % (pid, cmd[:160]), file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd in ("dumpat", "check"):
        warn_running_game()
    return {"check": cmd_check, "record": cmd_record, "diff": cmd_diff,
             "plan": cmd_plan, "frames": cmd_frames, "refs": cmd_refs,
             "reference": cmd_reference,
             "dumpat": cmd_dumpat, "anchors": cmd_anchors, "pulls": cmd_pulls}.get(
        cmd, lambda a: (print(__doc__), 2)[1])(args)


if __name__ == "__main__":
    sys.exit(main())
