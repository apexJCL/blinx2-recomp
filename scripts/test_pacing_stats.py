"""pacing_stats.py on synthetic logs: percentiles, the 3D filter, the
checkpoint, vblank windows, both flags and both gates."""
import contextlib
import io
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pacing_stats as P  # noqa: E402

ANCHOR = 100          # the checkpoint: flips 100 and on have 3D batches

import pytest  # noqa: E402

REAL_GOLDEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "analysis", "golden", "golden.json")


@pytest.fixture(autouse=True)
def real_golden(monkeypatch):
    """The checkpoint comes from the project's golden.json; other test files
    point golden.py at temporary ones."""
    monkeypatch.setattr(P.golden, "GOLDEN_JSON", REAL_GOLDEN)


def make_log(path, intervals_ms, mode="spin", cpu=60.0, raster=0.0, site=None,
             windows=(), load_at=None, menu_batches=10):
    """Flips 1..ANCHOR-1 are menus (menu_batches), then 3D (6000 batches);
    flip n+1 comes intervals_ms[n % len] after flip n. A summary every 600
    flips, a vblank window line after flips in `windows` ({flip: (lo, hi)})."""
    lines, t, n = [], 0.0, len(intervals_ms)
    total = ANCHOR + 1200
    for fl in range(1, total + 1):
        t += intervals_ms[fl % n] * 1000
        b = menu_batches if fl < ANCHOR else 6000
        if load_at and load_at[0] <= fl <= load_at[1]:
            b = 1
        lines.append(f"[PACING] flip {fl} t_us {int(t)} batches {b}")
        lines.append(f"[GPU] flip {fl} {int(t / 1000)} ms fence 0x0 batches {b} tex 0"
                     f" presents 0x0 640x480 raster {raster:.3f} ms (xf 0)")
        if fl in dict(windows):
            lo, hi = dict(windows)[fl]
            lines.append(f"  [NV2A] vblank {fl * 2}: last 600 in 10000 ms, gap {lo}-{hi} ms,"
                         " ack give-ups 0, late acks 0 (max 0 ms), declined 0")
        if fl % 600 == 0:
            lines.append(f"[PACING] flips 600: interval p5 1 p50 1 p95 1 max 1 ms;"
                         f" vblank gap -; cpu process {cpu:.0f}%; mode {mode}")
            if site:
                w, wk, to, iw = site[:4]
                exits = (f" exits wake {site[4]} timeout {site[5]};"
                         if len(site) > 4 else "")
                lines.append(f"[PACING]   site 0x00060475: waits {w} immediate 0 wakes {wk}"
                             f" timeouts {to} dispatch 0;{exits} cpu in-wait {iw}% thread 40%")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return path


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = P.main(argv)
    return rc, out.getvalue()


def test_percentiles_and_rate():
    with tempfile.TemporaryDirectory() as d:
        log = make_log(os.path.join(d, "a.log"), [30.0, 33.0, 33.0, 33.0, 40.0])
        s = P.stats(log, after_flip=ANCHOR)
        assert s["checkpoint"] == ANCHOR and s["flips3d"] == 1200
        assert s["p5"] == 30.0 and s["p50"] == 33.0 and s["p95"] == 40.0 and s["max"] == 40.0
        assert abs(s["flips_s"] - 1000 / 33.8) < 0.05


def test_3d_filter_and_checkpoint_from_batches():
    """Menu flips are not counted, and the checkpoint is golden.json's
    stage1 first-3d anchor (min 1000 batches)."""
    with tempfile.TemporaryDirectory() as d:
        iv = [16.7] * 7 + [33.3] * 3
        log = make_log(os.path.join(d, "a.log"), iv, menu_batches=10)
        s = P.stats(log)
        assert s["checkpoint"] == ANCHOR, s
        log2 = make_log(os.path.join(d, "b.log"), iv, menu_batches=1,
                        load_at=(500, 520))
        s2 = P.stats(log2, after_flip=ANCHOR)
        assert s2["flips3d"] == 1200 - 21     # the load's flips are not 3D


def test_vblank_windows_and_exclusions():
    with tempfile.TemporaryDirectory() as d:
        windows = [(50, (10.0, 30.0)),          # before the checkpoint
                   (300, (16.4, 16.9)), (600, (16.2, 17.4)), (900, (15.0, 19.0)),
                   (1200, (16.5, 16.8))]
        log = make_log(os.path.join(d, "a.log"), [33.3], windows=windows,
                       load_at=(850, 860))
        s = P.stats(log, after_flip=ANCHOR)
        # 900's window spans the load: listed, not counted.
        assert s["windows"] == 3, s
        whys = [w["why"] for w in s["windows_excluded"]]
        assert whys[0] == "before the checkpoint" and "load" in whys[1]
        assert abs(s["window_spread_p50"] - 0.5) < 1e-9
        assert s["windows_in_tol"] == 1.0


def test_sites_and_summaries():
    with tempfile.TemporaryDirectory() as d:
        log = make_log(os.path.join(d, "a.log"), [33.3], mode="sleep", cpu=30,
                       site=(1200, 1190, 10, 1.5, 590, 10))
        s = P.stats(log, after_flip=ANCHOR)
        st = s["sites"]["0x00060475"]
        assert s["cpu_process"] == 30 and s["modes"] == ["sleep"]
        assert st["inwait"] == 1.5 and st["wakes"] == 2 * 1190
        assert st["exit_wake"] == 2 * 590 and st["exit_timeout"] == 2 * 10
        assert abs(st["exit_share_max"] - 10 / 600) < 1e-9
        # A trace from before the exit counts parses, with no share.
        old = make_log(os.path.join(d, "old.log"), [33.3], mode="sleep",
                       site=(1200, 1190, 10, 1.5))
        assert P.stats(old, after_flip=ANCHOR)["sites"]["0x00060475"]["exit_share_max"] is None


def test_flags_both():
    with tempfile.TemporaryDirectory() as d:
        a = [make_log(os.path.join(d, f"a{i}.log"), [33.3], raster=4.0) for i in range(3)]
        b = [make_log(os.path.join(d, f"b{i}.log"), [50.0], raster=6.5) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--arm", "spin"] + a + ["--arm", "sleep"] + b)
        assert rc == 0, out
        assert "FLAG flips/s" in out and "FLAG CPU raster" in out, out
        c = [make_log(os.path.join(d, f"c{i}.log"), [34.0], raster=4.5) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--arm", "spin"] + a + ["--arm", "sleep"] + c)
        assert "no flags" in out, out


def test_clock_gate():
    random.seed(1)
    with tempfile.TemporaryDirectory() as d:
        wide = [33.3 + random.choice([-7, -3, 0, 3, 7]) for _ in range(50)]
        tight = [33.3 + random.choice([-0.5, 0, 0.5]) for _ in range(50)]
        good_w = [(fl, (16.4, 16.9)) for fl in range(200, 1300, 100)]
        ms = [make_log(os.path.join(d, f"ms{i}.log"), wide) for i in range(3)]
        ns = [make_log(os.path.join(d, f"ns{i}.log"), tight, windows=good_w) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--gate", "clock",
                       "--arm", "ms"] + ms + ["--arm", "ns"] + ns)
        assert rc == 0 and "FAIL" not in out, out
        bad_w = [(fl, (12.0, 22.0)) for fl in range(200, 1300, 100)]
        ns2 = [make_log(os.path.join(d, f"nb{i}.log"), tight, windows=bad_w) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--gate", "clock",
                       "--arm", "ms"] + ms + ["--arm", "ns"] + ns2)
        assert rc == 1 and "FAIL  median vblank window spread" in out, out


def test_sleep_gate():
    with tempfile.TemporaryDirectory() as d:
        spin = [make_log(os.path.join(d, f"s{i}.log"), [33.3], cpu=95) for i in range(3)]
        # More timeouts than wakes (a vblank wait spans many 1 ms timeouts),
        # yet the loops leave on a wake: that passes.
        good = [make_log(os.path.join(d, f"g{i}.log"), [33.3], mode="sleep", cpu=55,
                         site=(20000, 4000, 15000, 2.0, 590, 10)) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--gate", "sleep",
                       "--arm", "spin"] + spin + ["--arm", "sleep"] + good)
        assert rc == 0 and "FAIL" not in out, out
        bad = [make_log(os.path.join(d, f"b{i}.log"), [33.3], mode="sleep", cpu=80,
                        site=(1200, 100, 1100, 25.0, 500, 100)) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--gate", "sleep",
                       "--arm", "spin"] + spin + ["--arm", "sleep"] + bad)
        assert rc == 1, out
        for what in ("FAIL  in-wait CPU", "FAIL  timeout exits", "FAIL  process CPU"):
            assert what in out, (what, out)
        old = [make_log(os.path.join(d, f"o{i}.log"), [33.3], mode="sleep", cpu=55,
                        site=(1200, 1150, 50, 2.0)) for i in range(3)]
        rc, out = run(["--after-flip", str(ANCHOR), "--gate", "sleep",
                       "--arm", "spin"] + spin + ["--arm", "sleep"] + old)
        assert rc == 1 and "older trace" in out, out


def test_bad_input():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "empty.log")
        open(p, "w").close()
        rc, out = run([p])
        assert rc == 2 and "checkpoint" in out, out
        rc, out = run(["--gate", "fast", p])
        assert rc == 2
