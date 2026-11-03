#!/usr/bin/env python3
"""Tests for scripts/shots (openspec change frame-dumps-png): sheet.sh and
strip.sh take each dump's PNG when there is one, else its BMP; run.sh turns
its dumps into PNG with `blinx2 frames compact` before the sheet, unless
XBR_FRAMES_BMP=1. Each runs in a temp copy of the tree with fake magick,
blinx2 and game binaries on PATH or in place.

  python3 scripts/test_shots.py
  uv run pytest scripts/test_shots.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "shots")


def tree(tmp):
    """A copy of scripts/shots under tmp, a fake magick (its args, one per
    line, to tmp/magick.args), a fake blinx2 (to tmp/blinx2.args) and a
    fake game binary. Returns the env to run them with."""
    dst = os.path.join(tmp, "scripts", "shots")
    os.makedirs(dst)
    for n in ("sheet.sh", "strip.sh", "run.sh"):
        shutil.copy2(os.path.join(SHOTS, n), dst)
    bin_dir = os.path.join(tmp, "bin")
    os.makedirs(bin_dir)
    fakes = {
        os.path.join(bin_dir, "magick"): 'printf "%%s\\n" "$@" > "%s/magick.args"\n' % tmp,
        os.path.join(tmp, "blinx2"): 'printf "%%s\\n" "$@" >> "%s/blinx2.args"\n' % tmp,
        os.path.join(tmp, "build", "cat_recomp"): 'for i in 1 2; do : > "%s/fb/f_$i.bmp"; done\n'
        % os.path.join(tmp, "analysis", "runs", "r"),
    }
    for p, body in fakes.items():
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(p, 0o755)
    env = dict(os.environ, PATH=bin_dir + os.pathsep + os.environ.get("PATH", ""))
    env.pop("XBR_FRAMES_BMP", None)
    return env


def touch(*paths):
    for p in paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()


def magick_args(tmp):
    with open(os.path.join(tmp, "magick.args")) as f:
        return f.read().split("\n")


def test_sheet_prefers_png_else_bmp():
    with tempfile.TemporaryDirectory() as tmp:
        env = tree(tmp)
        d = os.path.join(tmp, "d")
        touch(*(os.path.join(d, n) for n in ("a.bmp", "a.png", "b.bmp", "c.png", "notes.txt")))
        sh = os.path.join(tmp, "scripts", "shots", "sheet.sh")
        r = subprocess.run(["sh", sh, d, os.path.join(tmp, "o.png")], env=env)
        assert r.returncode == 0
        args = magick_args(tmp)
        frames = [a for a in args if a.startswith(d)]
        assert frames == [os.path.join(d, n) for n in ("a.png", "b.bmp", "c.png")], frames
        # An RGBA PNG (a dump whose fourth byte is not 0) draws opaque, as its BMP did.
        assert args[args.index(frames[-1]) + 1 : args.index(frames[-1]) + 3] == ["-alpha", "off"]


def test_sheet_without_frames_fails():
    with tempfile.TemporaryDirectory() as tmp:
        env = tree(tmp)
        os.makedirs(os.path.join(tmp, "d"))
        sh = os.path.join(tmp, "scripts", "shots", "sheet.sh")
        r = subprocess.run(
            ["sh", sh, os.path.join(tmp, "d"), "o.png"], env=env, stderr=subprocess.PIPE
        )
        assert r.returncode == 1 and b"no .png or .bmp" in r.stderr


def test_strip_prefers_png():
    with tempfile.TemporaryDirectory() as tmp:
        env = tree(tmp)
        runs = os.path.join(tmp, "analysis", "runs")
        touch(os.path.join(runs, "x", "fb", "1.png"), os.path.join(runs, "y", "fb", "2.bmp"))
        sh = os.path.join(tmp, "scripts", "shots", "strip.sh")
        r = subprocess.run(["bash", sh, "o.png", "x:1", "y:2"], env=env)
        assert r.returncode == 0
        args = magick_args(tmp)
        assert args[1:3] == ["x/fb/1.png", "y/fb/2.bmp"], args
        assert args[3:5] == ["-alpha", "off"], args


def run_sh(tmp, env):
    sh = os.path.join(tmp, "scripts", "shots", "run.sh")
    r = subprocess.run(["sh", sh, "r", "@attract", "5"], env=env, stdout=subprocess.PIPE)
    assert r.returncode == 0, r


def test_run_compacts_before_sheet():
    with tempfile.TemporaryDirectory() as tmp:
        env = tree(tmp)
        run_sh(tmp, env)
        fb = os.path.join(tmp, "analysis", "runs", "r", "fb")
        with open(os.path.join(tmp, "blinx2.args")) as f:
            assert f.read().split("\n")[:3] == ["frames", "compact", fb]
        assert os.path.exists(os.path.join(tmp, "magick.args"))


def test_run_keeps_bmp_with_opt_out():
    with tempfile.TemporaryDirectory() as tmp:
        env = tree(tmp)
        env["XBR_FRAMES_BMP"] = "1"
        run_sh(tmp, env)
        assert not os.path.exists(os.path.join(tmp, "blinx2.args"))
        assert os.path.exists(os.path.join(tmp, "magick.args"))


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   " + name)
            except AssertionError as e:
                fails += 1
                print("FAIL %s: %s" % (name, e))
    sys.exit(1 if fails else 0)
