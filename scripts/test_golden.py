#!/usr/bin/env python3
"""Tests for golden.py: anchor transitions, INCOMPLETE on a missing anchored
flip, masks and their presence check, CPU skip. Synthetic images and logs in
a temp dir; plain asserts. Runs alone or under pytest.

  python3 scripts/test_golden.py
  python3 -m pytest scripts/test_golden.py

Exit 0 when every test passes.
"""

import contextlib
import io
import json
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import golden as G  # noqa: E402

W, H = 64, 64


def write_bmp(path, rgb):
    """24-bit top-down BMP of a W x H image (rgb bytes, row-major)."""
    stride = (W * 3 + 3) & ~3
    body = bytearray()
    for y in range(H):
        row = bytearray()
        for x in range(W):
            r, g, b = rgb[3 * (y * W + x): 3 * (y * W + x) + 3]
            row += bytes((b, g, r))
        body += row + b"\0" * (stride - W * 3)
    hdr = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, W, -H, 1, 24, 0, len(body), 0, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(hdr + info + body)


def flat(v):
    return bytes([v]) * (W * H * 3)


def with_rect(base, rect, v):
    p = bytearray(base)
    x0, y0, w, h = rect
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            p[3 * (y * W + x): 3 * (y * W + x) + 3] = bytes((v, v, v))
    return bytes(p)


# ---- anchors ------------------------------------------------------------------

def test_anchor_needs_a_transition_and_two_hits():
    ev = {"after_flip": 10, "max_batches": 100}
    b = {f: 500 for f in range(1, 60)}
    b[20] = 0            # one stray low flip (missing backend line, black frame)
    for f in range(40, 60):
        b[f] = 80
    assert G.find_anchor(b, ev) == 40


def test_anchor_not_at_after_flip_without_a_crossing():
    ev = {"after_flip": 10, "max_batches": 100}
    b = {f: 50 for f in range(1, 60)}   # already low before after_flip
    assert G.find_anchor(b, ev) is None


def test_anchor_min_batches():
    ev = {"after_flip": 5, "min_batches": 5}
    b = {f: 3 for f in range(1, 40)}
    b[12] = 6            # single spike
    for f in range(30, 40):
        b[f] = 5
    assert G.find_anchor(b, ev) == 30


def test_anchor_gap_breaks_a_run():
    ev = {"after_flip": 1, "min_batches": 5}
    b = {f: 3 for f in range(1, 40)}
    b[20] = 5
    del b[21]            # the next flip is missing from the log
    for f in range(30, 40):
        b[f] = 5
    assert G.find_anchor(b, ev) == 30


# ---- check: INCOMPLETE, masks, skip -----------------------------------------------

def make_golden(tmp, frame, anchors=None, extra=None):
    g = {"compare": {"pixel_tol": 8, "max_channel_mae": 1.0, "max_bad_fraction": 0.01,
                     "max_tile_bad_fraction": 0.5},
         "scenarios": {"s": dict({"seconds": 1, "frames": [frame],
                                  "anchors": anchors or {}}, **(extra or {}))}}
    path = os.path.join(tmp, "golden.json")
    with open(path, "w") as f:
        json.dump(g, f)
    return path


def run_check(tmp, golden_json, run_dir):
    G.GOLDEN_JSON = golden_json
    G.FRAMES_DIR = os.path.join(tmp, "frames")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = G.cmd_check(["s=" + run_dir])
    return rc, out.getvalue()


def setup_run(tmp, log_lines, flips):
    run = os.path.join(tmp, "run")
    os.makedirs(os.path.join(run, "frames"), exist_ok=True)
    with open(os.path.join(run, "game-stdio.log"), "w") as f:
        f.write("\n".join(log_lines) + "\n")
    for n, img in flips.items():
        write_bmp(os.path.join(run, "frames", "flip_%05d.bmp" % n), img)
    return os.path.join(run, "frames")


def ref_png(tmp, name, img):
    os.makedirs(os.path.join(tmp, "frames"), exist_ok=True)
    G.write_png(os.path.join(tmp, "frames", name + ".png"), W, H, img)
    return G.pixel_sha((W, H, img))


def metal_log(batches):
    return ["[METAL] flip %d batches %d" % (f, b) for f, b in sorted(batches.items())]


def test_incomplete_when_anchor_missing_but_flips_dumped():
    with tempfile.TemporaryDirectory() as tmp:
        img = flat(100)
        sha = ref_png(tmp, "f", img)
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H],
                 "anchor": {"event": "e", "ref_flip": 10}}
        gj = make_golden(tmp, frame, {"e": {"after_flip": 1, "min_batches": 5}})
        d = setup_run(tmp, metal_log({f: 1 for f in range(1, 80)}), {61: img})
        rc, out = run_check(tmp, gj, d)
        assert rc == 2 and "INCOMPLETE" in out, out


def test_incomplete_when_target_flip_not_dumped():
    with tempfile.TemporaryDirectory() as tmp:
        img = flat(100)
        sha = ref_png(tmp, "f", img)
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H],
                 "anchor": {"event": "e", "ref_flip": 10}}
        gj = make_golden(tmp, frame, {"e": {"after_flip": 1, "min_batches": 5}})
        b = {f: (5 if f >= 30 else 1) for f in range(1, 120)}
        d = setup_run(tmp, metal_log(b), {61: img})   # target is 30+61-10 = 81
        rc, out = run_check(tmp, gj, d)
        assert rc == 2 and "INCOMPLETE" in out, out


def test_incomplete_when_no_flip_dumps_pulled():
    with tempfile.TemporaryDirectory() as tmp:
        img = flat(100)
        sha = ref_png(tmp, "f", img)
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H],
                 "anchor": {"event": "e", "ref_flip": 10}}
        gj = make_golden(tmp, frame, {"e": {"after_flip": 1, "min_batches": 5}})
        b = {f: (5 if f >= 30 else 1) for f in range(1, 120)}
        d = setup_run(tmp, metal_log(b), {})
        write_bmp(os.path.join(d, "frame_0001.bmp"), img)   # plain dump only
        rc, out = run_check(tmp, gj, d)
        assert rc == 2 and "INCOMPLETE" in out, out


def test_anchored_target_is_used():
    with tempfile.TemporaryDirectory() as tmp:
        img = flat(100)
        sha = ref_png(tmp, "f", img)
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H],
                 "anchor": {"event": "e", "ref_flip": 10}}
        gj = make_golden(tmp, frame, {"e": {"after_flip": 1, "min_batches": 5}})
        b = {f: (5 if f >= 30 else 1) for f in range(1, 120)}
        d = setup_run(tmp, metal_log(b), {61: flat(0), 81: img})
        rc, out = run_check(tmp, gj, d)
        assert rc == 0 and "EXACT" in out, out


def test_mask_and_presence():
    with tempfile.TemporaryDirectory() as tmp:
        rect = [8, 8, 16, 16]
        ref = with_rect(flat(100), rect, 200)
        sha = ref_png(tmp, "f", ref)
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H],
                 "masks": [{"rect": rect, "presence": {"pixel_tol": 96,
                                                       "max_bad_fraction": 0.02,
                                                       "max_channel_mae": 60}}]}
        gj = make_golden(tmp, frame)
        # Pulsing inside the mask: passes.
        d = setup_run(tmp, metal_log({61: 1}), {61: with_rect(flat(100), rect, 160)})
        rc, out = run_check(tmp, gj, d)
        assert rc == 0 and "CLOSE" in out, out
    with tempfile.TemporaryDirectory() as tmp:
        sha = ref_png(tmp, "f", ref)
        gj = make_golden(tmp, frame)
        # The masked thing is gone (background there): presence fails.
        d = setup_run(tmp, metal_log({61: 1}), {61: flat(100)})
        rc, out = run_check(tmp, gj, d)
        assert rc == 1 and "presence" in out, out


def test_cpu_skip():
    with tempfile.TemporaryDirectory() as tmp:
        sha = ref_png(tmp, "f", flat(100))
        frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H]}
        gj = make_golden(tmp, frame, extra={"skip_backends": ["cpu"], "skip_why": "slow"})
        d = setup_run(tmp, ["[GPU] flip 61 0 ms fence 0x0 batches 3"], {61: flat(0)})
        rc, out = run_check(tmp, gj, d)
        assert rc == 0 and "SKIP" in out, out


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   " + name)
            except AssertionError as e:
                fails += 1
                print("FAIL " + name + ": " + str(e)[:400])
    sys.exit(1 if fails else 0)
