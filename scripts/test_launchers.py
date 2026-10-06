#!/usr/bin/env python3
"""Tests for the packaged launchers' defaults and the macOS launcher script,
on a fake app with a fake cat_recomp (no game data, no build). Every run
points HOME and BLINX2_DATA_DIR at a scratch folder: a test must never touch
the player's real saves or launch.env. Plain asserts; runs alone or under
pytest.

  python3 scripts/test_launchers.py
  python3 -m pytest scripts/test_launchers.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "packaging")
sys.path.insert(0, HERE)
import package_lib as pl  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


def env_keys(path):
    keys = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                k, _, v = line.partition("=")
                keys[k] = v
    return keys


def test_launch_env_defaults():
    mac = env_keys(os.path.join(PKG, "launch.env.default.macos"))
    win = env_keys(os.path.join(PKG, "launch.env.default.windows"))
    # macOS: the runtime keeps host pads off off-Windows, the app turns them on.
    assert mac.get("RECOMP_HOST_PAD") == "1"
    # The keyboard backend is Windows-only (Proton too); on macOS it does nothing.
    assert "RECOMP_KEYBOARD" not in mac
    assert win.get("RECOMP_KEYBOARD") == "1"
    # Windows and steamos get the pad from the runtime's _WIN32 default.
    assert "RECOMP_HOST_PAD" not in win
    for t in ("windows", "steamos"):
        with open(os.path.join(PKG, t, "README.part")) as f:
            text = f.read()
        assert "Enter       START" in text and "RECOMP_KEYBOARD=0" in text, t


def fake_app(d):
    """BLiNX2.app/Contents with the real launcher script and a cat_recomp that
    prints the environment it was given."""
    c = os.path.join(d, "BLiNX2.app", "Contents")
    macos, res = os.path.join(c, "MacOS"), os.path.join(c, "Resources")
    os.makedirs(macos)
    os.makedirs(os.path.join(res, "game_files"))
    open(os.path.join(res, "game_files", "default.xbe"), "w").close()
    with open(os.path.join(PKG, "macos", "BLiNX2.in")) as f:
        script = f.read().replace("@NAME@", pl.PRODUCT_NAME)
    with open(os.path.join(macos, "BLiNX2"), "w") as f:
        f.write(script)
    shutil.copy(os.path.join(PKG, "launch.env.default.macos"),
                os.path.join(res, "launch.env.default"))
    shutil.copy(os.path.join(PKG, "enhance.toml.default"),
                os.path.join(res, "enhance.toml.default"))
    fake = os.path.join(macos, "cat_recomp")
    with open(fake, "w") as f:
        f.write("#!/bin/sh\nenv | grep -E '^(RECOMP_|SDL_)' | sort\necho \"cwd=$PWD\"\n")
    os.chmod(fake, 0o755)
    os.chmod(os.path.join(macos, "BLiNX2"), 0o755)
    return os.path.join(macos, "BLiNX2"), res


def snapshot(top):
    out = {}
    for dp, _, fs in os.walk(top):
        for f in fs:
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, top)] = fh.read()
    return out


def run(argv, env):
    return subprocess.run(argv, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)


def test_macos_data_dir_override(d):
    launcher, _ = fake_app(d)
    home = os.path.join(d, "home")
    real = os.path.join(home, "Library", "Application Support", "BLiNX2")
    os.makedirs(os.path.join(real, "config"))
    with open(os.path.join(real, "config", "launch.env"), "w") as f:
        f.write("RECOMP_PB_BACKEND=cpu\n")
    before = snapshot(real)
    data = os.path.join(d, "scratch-data")
    os.makedirs(os.path.join(data, "config"))
    with open(os.path.join(data, "config", "launch.env"), "w") as f:
        f.write("SDL_AUDIODRIVER=dummy\n")
    env = {"PATH": "/usr/bin:/bin", "HOME": home, "BLINX2_DATA_DIR": data}
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 0, r.stderr
    got = dict(l.split("=", 1) for l in r.stdout.splitlines())
    for k in ("RECOMP_HDD_DIR", "RECOMP_ENHANCE_CONFIG", "RECOMP_STDIO_LOG"):
        assert got[k].startswith(data + "/"), (k, got[k])
    assert os.path.realpath(got["cwd"]) == os.path.realpath(os.path.join(data, "logs"))
    assert got["SDL_AUDIODRIVER"] == "dummy"
    assert got["RECOMP_HOST_PAD"] == "1"
    # The scratch launch.env won; the "real" one was never read or touched.
    assert got["RECOMP_PB_BACKEND"] == "metal"
    assert snapshot(real) == before
    assert os.path.isfile(os.path.join(data, "config", "enhance.toml"))


def test_macos_default_data_dir(d):
    launcher, _ = fake_app(d)
    home = os.path.join(d, "home")
    r = run(["/bin/bash", launcher], {"PATH": "/usr/bin:/bin", "HOME": home})
    assert r.returncode == 0, r.stderr
    got = dict(l.split("=", 1) for l in r.stdout.splitlines())
    want = os.path.join(home, "Library", "Application Support", "BLiNX2")
    assert got["RECOMP_HDD_DIR"] == os.path.join(want, "hdd")


def test_macos_alert_message_is_data(d):
    launcher, _ = fake_app(d)
    stub_dir = os.path.join(d, "stub")
    os.makedirs(stub_dir)
    argv_out = os.path.join(d, "osascript.argv")
    with open(os.path.join(stub_dir, "osascript"), "w") as f:
        f.write('#!/bin/sh\nfor a in "$@"; do printf "%%s\\n" "$a"; done > "%s"\n' % argv_out)
    os.chmod(os.path.join(stub_dir, "osascript"), 0o755)
    # A data dir with a quote and a backslash in its path, and a launch.env
    # line the launcher rejects: the alert names that path.
    data = os.path.join(d, 'a "quoted" \\ path')
    os.makedirs(os.path.join(data, "config"))
    with open(os.path.join(data, "config", "launch.env"), "w") as f:
        f.write("not a setting\n")
    env = {"PATH": stub_dir + ":/usr/bin:/bin", "HOME": os.path.join(d, "home"),
           "BLINX2_DATA_DIR": data}
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 1
    with open(argv_out) as f:
        args = f.read().splitlines()
    # The script text is fixed; the message is the one argument after "--".
    assert args[:6] == ["-e", "on run argv",
                        "-e", 'display alert "%s cannot start" message (item 1 of argv)'
                        % pl.PRODUCT_NAME,
                        "-e", "end run"], args
    assert args[6] == "--" and len(args) == 8
    assert args[7] == "%s/config/launch.env:1: not a KEY=value line" % data



def test_product_name_single_source():
    """The shown name lives in package_lib.PRODUCT_NAME; templates carry
    @NAME@, and no template spells it out or keeps "(recomp)"."""
    assert pl.PRODUCT_NAME == "BLiNX 2"
    for rel in ("windows/installer.nsi.in", "macos/Info.plist.in", "macos/BLiNX2.in",
                "steamos/launch.sh", "README.txt.in"):
        with open(os.path.join(PKG, rel)) as f:
            text = f.read()
        assert "@NAME@" in text, rel
        assert "(recomp)" not in text, rel


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        if t.__code__.co_argcount:
            with tempfile.TemporaryDirectory() as d:
                t(d)
        else:
            t()
        print("ok %s" % t.__name__)
    print("%d tests passed" % len(tests))


if __name__ == "__main__":
    main()
