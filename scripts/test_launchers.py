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
import xbr_cli  # noqa: E402

NAME = xbr_cli.game_name()

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
    # The keyboard and the mouse are switched in config.default.toml
    # (input.keyboard, input.mouse), not by the launchers.
    assert "RECOMP_KEYBOARD" not in mac
    assert "RECOMP_KEYBOARD" not in win
    # Windows and steamos get the pad from the runtime's _WIN32 default.
    assert "RECOMP_HOST_PAD" not in win
    # One Controls section, the same in both of this repo's README parts. The
    # steamos part is xboxrecomp-cli's and still has the old keyboard block
    # until its follow-up (kbm-input 7.1), so it is not compared here.
    blocks = []
    for t in ("windows", "macos"):
        with open(os.path.join(PKG, t, "README.part")) as f:
            text = f.read()
        start = text.index("Controls\n--------\n")
        end = text.find("\n\n\n", start)
        block = text[start : end if end >= 0 else None].rstrip("\n")
        assert "config/config.toml" in block and "[input.bindings]" in block, t
        assert "mouse" in block and "F9" in block, t
        assert "Escape" in block and "START (pause)" in block, t
        assert "RECOMP_KEYBOARD" not in block, t
        blocks.append(block)
    assert blocks[0] == blocks[1], blocks


def fake_app(d):
    """BLiNX2.app/Contents with the real launcher script and a cat_recomp that
    prints the environment it was given."""
    c = os.path.join(d, "BLiNX2.app", "Contents")
    macos, res = os.path.join(c, "MacOS"), os.path.join(c, "Resources")
    os.makedirs(macos)
    os.makedirs(os.path.join(res, "game_files"))
    open(os.path.join(res, "game_files", "default.xbe"), "w").close()
    with open(os.path.join(PKG, "macos", "BLiNX2.in")) as f:
        script = f.read().replace("@NAME@", NAME)
    with open(os.path.join(macos, "BLiNX2"), "w") as f:
        f.write(script)
    shutil.copy(
        os.path.join(PKG, "launch.env.default.macos"), os.path.join(res, "launch.env.default")
    )
    shutil.copy(os.path.join(PKG, "config.default.toml"), os.path.join(res, "config.default.toml"))
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
    return subprocess.run(argv, env=env, capture_output=True, text=True)


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
    # An earlier version's reference copy of the defaults.
    with open(os.path.join(data, "config", "enhance.toml.default"), "w") as f:
        f.write("[render]\nscale = 1\n")
    env_before = snapshot(os.path.join(data, "config"))["launch.env"]
    env = {"PATH": "/usr/bin:/bin", "HOME": home, "BLINX2_DATA_DIR": data}
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 0, r.stderr
    got = dict(line.split("=", 1) for line in r.stdout.splitlines())
    for k in ("RECOMP_HDD_DIR", "RECOMP_CONFIG", "RECOMP_STDIO_LOG"):
        assert got[k].startswith(data + "/"), (k, got[k])
    assert got["RECOMP_CONFIG"] == os.path.join(data, "config", "config.toml")
    assert "RECOMP_ENHANCE_CONFIG" not in got
    assert os.path.realpath(got["cwd"]) == os.path.realpath(os.path.join(data, "logs"))
    assert got["SDL_AUDIODRIVER"] == "dummy"
    assert got["RECOMP_HOST_PAD"] == "1"
    # The scratch launch.env won; the "real" one was never read or touched.
    assert got["RECOMP_PB_BACKEND"] == "metal"
    assert snapshot(real) == before
    # The launcher copies nothing: the game reads Resources/config.default.toml
    # and writes config/config.toml's header itself. The old reference copy is
    # gone, launch.env is byte-identical.
    cfg = snapshot(os.path.join(data, "config"))
    assert sorted(cfg) == ["launch.env"], sorted(cfg)
    assert cfg["launch.env"] == env_before


def test_macos_default_data_dir(d):
    launcher, _ = fake_app(d)
    home = os.path.join(d, "home")
    r = run(["/bin/bash", launcher], {"PATH": "/usr/bin:/bin", "HOME": home})
    assert r.returncode == 0, r.stderr
    got = dict(line.split("=", 1) for line in r.stdout.splitlines())
    want = os.path.join(home, "Library", "Application Support", "BLiNX2")
    assert got["RECOMP_HDD_DIR"] == os.path.join(want, "hdd")


def test_macos_seed_config_once(d):
    """A bundle the build wizard made carries config.seed.toml: the first
    launch copies it to config/config.toml, a later one never replaces the
    player's file."""
    launcher, res = fake_app(d)
    with open(os.path.join(res, "config.seed.toml"), "w") as f:
        f.write("[render]\nscale = 2\n")
    data = os.path.join(d, "data")
    env = {"PATH": "/usr/bin:/bin", "HOME": os.path.join(d, "home"), "BLINX2_DATA_DIR": data}
    cfg = os.path.join(data, "config", "config.toml")
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 0, r.stderr
    with open(cfg) as f:
        assert f.read() == "[render]\nscale = 2\n"
    with open(cfg, "w") as f:
        f.write("[render]\nscale = 3\n")
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 0, r.stderr
    with open(cfg) as f:
        assert f.read() == "[render]\nscale = 3\n"
    # An earlier version's enhance.toml is the player's file too: a seeded
    # config.toml would stop the runtime's one-time rename of it.
    data2 = os.path.join(d, "data2")
    os.makedirs(os.path.join(data2, "config"))
    with open(os.path.join(data2, "config", "enhance.toml"), "w") as f:
        f.write("[render]\nscale = 3\n")
    r = run(["/bin/bash", launcher], dict(env, BLINX2_DATA_DIR=data2))
    assert r.returncode == 0, r.stderr
    assert "kept your existing settings" in r.stderr
    assert not os.path.exists(os.path.join(data2, "config", "config.toml"))


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
    env = {
        "PATH": stub_dir + ":/usr/bin:/bin",
        "HOME": os.path.join(d, "home"),
        "BLINX2_DATA_DIR": data,
    }
    r = run(["/bin/bash", launcher], env)
    assert r.returncode == 1
    with open(argv_out) as f:
        args = f.read().splitlines()
    # The script text is fixed; the message is the one argument after "--".
    assert args[:6] == [
        "-e",
        "on run argv",
        "-e",
        'display alert "%s cannot start" message (item 1 of argv)' % NAME,
        "-e",
        "end run",
    ], args
    assert args[6] == "--" and len(args) == 8
    assert args[7] == "%s/config/launch.env:1: not a KEY=value line" % data


def test_product_name_single_source():
    """The shown name lives in game.toml ([game] name); templates carry
    @NAME@, and no template spells it out or keeps "(recomp)". The windows
    installer and the README are xboxrecomp-cli's (its own tests)."""
    assert NAME == "BLiNX 2"
    for rel in (
        "macos/Info.plist.in",
        "macos/BLiNX2.in",
    ):
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
