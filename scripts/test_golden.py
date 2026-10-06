#!/usr/bin/env python3
"""Tests for golden.py: anchor transitions, INCOMPLETE on a missing anchored
flip, masks and their presence check, CPU skip. Synthetic images and logs in
a temp dir; plain asserts. Runs alone or under pytest.

  python3 scripts/test_golden.py
  python3 -m pytest scripts/test_golden.py

Exit 0 when every test passes. Also covers the pace check (CLOSE in limits,
INCOMPLETE outside, FAIL on a wrong screen) and FAIL-over-INCOMPLETE.
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


# ---- stock guarantee: a run with enhancements on is never a golden ---------------

STOCK = "[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 (display.aspect=4:3)"


def enhance_case(tmp, enhance_lines):
    sha = ref_png(tmp, "f", flat(100))
    frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H]}
    gj = make_golden(tmp, frame)
    d = setup_run(tmp, enhance_lines + metal_log({61: 3}), {61: flat(100)})
    return run_check(tmp, gj, d)


def test_enhance_scale_2_fails():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [STOCK.replace("render.scale=1", "render.scale=2")])
        assert rc == 1 and "not a stock run" in out and "render.scale=2" in out, out


def test_enhance_aspect_fails():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [
            "[ENHANCE] display.aspect=16:9 not implemented yet (hor+ is a later slice); using 4:3",
            STOCK])
        assert rc == 1 and "display.aspect=16:9" in out, out


def test_enhance_stock_passes():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [STOCK])
        assert rc == 0 and "EXACT" in out, out


def test_enhance_no_line_passes():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [])
        assert rc == 0 and "EXACT" in out, out


PACED = ("[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0"
         " present.pacing={} (display.aspect=4:3)")


def test_enhance_pacing_spin_and_lock30_pass():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [PACED.format("spin"), "[ENHANCE] fps.mode=lock30"])
        assert rc == 0 and "EXACT" in out, out


def test_enhance_pacing_sleep_fails():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [PACED.format("sleep")])
        assert rc == 1 and "present.pacing=sleep" in out, out


def test_enhance_fps_mode_fails_even_when_unavailable():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = enhance_case(tmp, [
            PACED.format("spin"),
            "[ENHANCE] fps.mode=lock60 not available for this title (stage logic"
            " advances a fixed 1/30 s per frame; see docs/env.md); using lock30"])
        assert rc == 1 and "fps.mode=lock60" in out, out


def check_allowing(tmp, lines, *allow):
    sha = ref_png(tmp, "f", flat(100))
    frame = {"name": "f", "dump": 1, "sha256": sha, "size": [W, H]}
    gj = make_golden(tmp, frame)
    d = setup_run(tmp, lines + metal_log({61: 3}), {61: flat(100)})
    G.GOLDEN_JSON = gj
    G.FRAMES_DIR = os.path.join(tmp, "frames")
    args = []
    for a in allow:
        args += ["--allow-enhance", a]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = G.cmd_check(args + ["s=" + d])
    return rc, out.getvalue()


def test_allow_enhance_evaluates_with_a_note():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = check_allowing(tmp, [PACED.format("sleep")], "present.pacing=sleep")
        assert rc == 0 and "EXACT" in out and "NOTE" in out and "present.pacing=sleep" in out, out


def test_allow_enhance_is_only_that_value():
    with tempfile.TemporaryDirectory() as tmp:
        rc, out = check_allowing(tmp, [PACED.format("sleep").replace(
            "render.scale=1", "render.scale=2")], "present.pacing=sleep")
        assert rc == 1 and "render.scale=2" in out and "present.pacing=sleep" not in out.split(
            "not a stock run")[1].split(")")[0], out


def test_allow_enhance_bad_key_and_record_refuse():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            check_allowing(tmp, [], "present.vsync=1")
            assert False, "bad key accepted"
        except SystemExit as e:
            assert "KEY=VALUE" in str(e)
        try:
            G.cmd_record(["--allow-enhance", "present.pacing=sleep", "s=" + tmp])
            assert False, "record accepted --allow-enhance"
        except SystemExit as e:
            assert "stock runs only" in str(e)


# ---- pace: flips per wall second from the anchor to the frame ------------------

def paced_run(tmp, fps, timed=True, img=None, flip=81):
    """Anchor e at flip 30 (ref_flip 10, dump 1: target 81); flips at fps.
    The default image is close to the reference, not equal (no EXACT)."""
    b = {f: (5 if f >= 30 else 1) for f in range(1, 120)}
    lines = metal_log(b)
    if timed:
        lines += ["[GPU] flip %d %d ms fence 0x0 batches 0" % (f, round(f * 1000 / fps))
                  for f in sorted(b)]
    return setup_run(tmp, lines, {flip: flat(101) if img is None else img})


ANCHORS = {"e": {"after_flip": 1, "min_batches": 5}}


def paced_frame(tmp, ref_pace=None, name="f", ref_flip=10, **extra):
    sha = ref_png(tmp, name, flat(100))
    anchor = {"event": "e", "ref_flip": ref_flip}
    if ref_pace is not None:
        anchor["ref_pace"] = ref_pace
    return dict({"name": name, "dump": 1, "sha256": sha, "size": [W, H], "anchor": anchor},
                **extra)


def paced_golden(tmp, ref_pace=None, scen_extra=None, **frame_extra):
    return make_golden(tmp, paced_frame(tmp, ref_pace, **frame_extra), ANCHORS, scen_extra)


OFF = with_rect(flat(100), [0, 0, 16, 16], 200)   # 6.25% bad: outside limits, not gross


def test_pace_ok():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=57.0)        # run 60: 5% off
        rc, out = run_check(tmp, gj, paced_run(tmp, 60))
        assert rc == 0 and "CLOSE" in out and "run 60.0 fps vs ref 57.0 fps" in out, out
        assert "pace mismatch" not in out, out


def test_pace_mismatch_within_limits_is_close():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41))
        assert rc == 0 and out.startswith("CLOSE"), out
        assert "pace mismatch (run 41.0 fps vs ref 60.0 fps), but within limits" in out, out


def test_pace_mismatch_outside_limits_is_incomplete():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 2 and out.startswith("INCOMPLETE s/f") and "pace mismatch (run 41.0 fps vs ref 60.0 fps); outside limits" in out, out
        assert "golden: INCOMPLETE (1 INCOMPLETE)" in out, out


def test_pace_mismatch_wrong_screen_fails():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=flat(200)))
        assert rc == 1 and "wrong screen at any pace" in out, out
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0, pace_fail_bad=0.05)   # per-frame floor
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 1 and "wrong screen at any pace" in out, out


def test_pace_mismatch_exact_stays_exact():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=flat(100)))
        assert rc == 0 and out.startswith("EXACT"), out


def test_pace_threshold_from_golden_json():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0, max_pace_diff=0.5)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 1 and out.startswith("FAIL") and "pace mismatch" not in out, out
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0, max_pace_diff=None)   # opted out
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 1 and out.startswith("FAIL") and "pace" not in out, out


def test_pace_threshold_scenario_level():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0, scen_extra={"max_pace_diff": 0.5})
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 1 and "limit +-50%" in out and "pace mismatch" not in out, out
    with tempfile.TemporaryDirectory() as tmp:   # the frame's own limit wins
        gj = paced_golden(tmp, ref_pace=60.0, scen_extra={"max_pace_diff": 0.5},
                          max_pace_diff=0.1)
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 2 and "pace mismatch" in out, out


def test_pace_unknown_is_not_checked():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp)                        # no ref_pace recorded
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=OFF))
        assert rc == 1 and "reference unknown" in out, out
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0)         # run log has no flip times
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, timed=False, img=OFF))
        assert rc == 1 and "not timed" in out, out


def test_pace_target_not_after_anchor():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp, ref_pace=60.0, ref_flip=70)    # target 30+61-70 = 21
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, flip=21))
        assert rc == 0 and "target flip 21 not after anchor 30" in out, out


def test_fail_dominates_incomplete():
    with tempfile.TemporaryDirectory() as tmp:
        sha = ref_png(tmp, "g", flat(100))
        plain = {"name": "g", "dump": 1, "sha256": sha, "size": [W, H]}   # plain dump 61
        paced = paced_frame(tmp, 60.0)
        gj = make_golden(tmp, paced, ANCHORS, {"frames": [paced, plain]})
        d = paced_run(tmp, 41, img=OFF)
        write_bmp(os.path.join(d, "flip_00061.bmp"), flat(200))
        rc, out = run_check(tmp, gj, d)
        assert rc == 1 and "golden: REGRESSION (1 FAIL, 1 INCOMPLETE)" in out, out


def split_golden(tmp, ref_pace):
    ref = with_rect(flat(50), [0, 0, 32, 16], 255)          # white panel text
    os.makedirs(os.path.join(tmp, "frames"), exist_ok=True)
    G.write_png(os.path.join(tmp, "frames", "f.a.png"), W, H, ref)
    frame = {"name": "f", "dump": 1, "anchor": {"event": "e", "ref_flip": 10},
             "references": [{"label": "a", "sha256": G.pixel_sha((W, H, ref)), "size": [W, H],
                             "anchor_flip": 10, "pace": ref_pace}],
             "split": {"panel": {"rects": [[0, 0, 32, 16]], "max_channel_mae": 1.5,
                                 "max_bad_fraction": 0.03, "max_tile_bad_fraction": 0.25},
                       "overlay": {"max_spread": 8, "min_luma": 200, "min_pixels": 100,
                                   "max_bad_fraction": 0.005},
                       "background": {"max_channel_mae": 3.0, "max_bad_fraction": 0.1,
                                      "max_tile_bad_fraction": 0.9, "min_luma_std": 10,
                                      "new_view_min_mae": 16}}}
    return make_golden(tmp, frame, ANCHORS), ref


def test_split_frame_pace_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        gj, ref = split_golden(tmp, 60.0)
        # Background off (panel fine): the split check FAILs; at a mismatched
        # pace that is INCOMPLETE, with the split and whole-frame compares shown.
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=with_rect(ref, [16, 32, 16, 16], 150)))
        assert rc == 2 and out.startswith("INCOMPLETE") and "pace mismatch" in out, out
        assert "for information: FAIL" in out and "whole frame vs a" in out, out
    with tempfile.TemporaryDirectory() as tmp:
        gj, ref = split_golden(tmp, 60.0)
        # Another screen behind the same panel: wrong at any pace.
        rc, out = run_check(tmp, gj, paced_run(tmp, 41, img=with_rect(flat(200), [0, 0, 32, 16], 255)))
        assert rc == 1 and "wrong screen at any pace" in out, out
    with tempfile.TemporaryDirectory() as tmp:
        gj, ref = split_golden(tmp, 60.0)
        rc, out = run_check(tmp, gj, paced_run(tmp, 60, img=with_rect(ref, [16, 32, 16, 16], 150)))
        assert rc == 1 and out.startswith("FAIL"), out   # pace matches: a plain FAIL


def test_record_stores_pace():
    with tempfile.TemporaryDirectory() as tmp:
        gj = paced_golden(tmp)
        d = paced_run(tmp, 50)
        write_bmp(os.path.join(d, "flip_00061.bmp"), flat(100))   # dump 1
        G.GOLDEN_JSON, G.FRAMES_DIR = gj, os.path.join(tmp, "frames")
        with contextlib.redirect_stdout(io.StringIO()):
            assert G.cmd_record(["s=" + d]) == 0
        with open(gj) as f:
            a = json.load(f)["scenarios"]["s"]["frames"][0]["anchor"]
        assert a["ref_flip"] == 30 and a["ref_pace"] == 50.0, a


def test_reference_stores_pace():
    with tempfile.TemporaryDirectory() as tmp:
        frame = {"name": "f", "dump": 1, "anchor": {"event": "e", "ref_flip": 10}}
        gj = make_golden(tmp, frame, ANCHORS)
        d = paced_run(tmp, 50)
        write_bmp(os.path.join(d, "flip_00061.bmp"), flat(100))
        G.GOLDEN_JSON, G.FRAMES_DIR = gj, os.path.join(tmp, "frames")
        with contextlib.redirect_stdout(io.StringIO()):
            assert G.cmd_reference(["s", "f", "a", d]) == 0
        with open(gj) as f:
            r = json.load(f)["scenarios"]["s"]["frames"][0]["references"][0]
        assert r["anchor_flip"] == 30 and r["pace"] == 50.0, r


def test_pace_of_a_log():
    t = {10: 1000, 70: 2000}
    assert G.pace(t, 10, 70) == 60.0
    assert G.pace(t, 10, 71) is None and G.pace(None, 10, 70) is None


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
