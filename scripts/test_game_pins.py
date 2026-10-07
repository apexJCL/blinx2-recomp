#!/usr/bin/env python3
"""This game's own pins and wrappers, which stay here while the CLI's code
and tests moved to xboxrecomp-cli: uv.lock's hashes and the lifter's
versions, setup-pins.json against game.toml, the wrappers' line endings,
and blinx2.py against the CLI's bootstrap template. Plain asserts; runs
alone or under pytest.

  python3 scripts/test_game_pins.py
  uv run pytest scripts/test_game_pins.py
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import xbr_cli  # noqa: E402


def load_toml(path):
    """tomllib (3.11+), else tomli from the dev group; None without either."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def test_lockfile_pins():
    lock = load_toml(os.path.join(ROOT, "uv.lock"))
    if lock is None:
        print("skip test_lockfile_pins: no tomllib or tomli (Python < 3.11 outside uv run)")
        return
    pkgs = {}
    for p in lock["package"]:
        if "registry" not in p["source"]:
            continue  # the project itself (virtual): nothing is downloaded for it
        files = ([p["sdist"]] if "sdist" in p else []) + p.get("wheels", [])
        assert files, p["name"]
        for f in files:
            assert f["hash"].startswith("sha256:") and len(f["hash"]) == 71, (p["name"], f)
        pkgs.setdefault(p["name"], []).append(p["version"])
    # The lifter decodes with capstone: a different version could change gen/.
    assert pkgs["capstone"] == ["5.0.9"], pkgs["capstone"]
    assert pkgs["pefile"] == ["2024.8.26"], pkgs["pefile"]
    for name in ("cmake", "ninja", "pytest", "ruff"):
        assert name in pkgs, name


def test_setup_pins_match_game_toml():
    """setup-pins.json holds the downloads of the releases game.toml names;
    the toolkit and CLI pins are game.toml's alone."""
    with open(os.path.join(ROOT, "config", "setup-pins.json")) as f:
        pins = json.load(f)
    with open(os.path.join(ROOT, "game.toml")) as f:
        text = f.read()
    tag = re.search(r'^llvm_mingw = "([^"]+)"', text, re.M).group(1)
    nsis = re.search(r'^nsis = "([^"]+)"', text, re.M).group(1)
    assert pins["llvm_mingw"]["tag"] == tag
    assert len(pins["llvm_mingw"]["assets"]) == 5, pins["llvm_mingw"]["assets"]
    for name, a in pins["llvm_mingw"]["assets"].items():
        assert tag in name and len(a["sha256"]) == 64 and a["size"] > 0, name
        assert a["url"].startswith("https://github.com/mstorsjo/llvm-mingw/"), a["url"]
    assert pins["nsis"]["version"] == nsis and len(pins["nsis"]["sha256"]) == 64
    assert "toolkit" not in pins


def test_wrapper_line_endings():
    with open(os.path.join(ROOT, "blinx2.cmd"), "rb") as f:
        cmd = f.read()
    with open(os.path.join(ROOT, "blinx2"), "rb") as f:
        sh = f.read()
    assert b"\r\n" in cmd and cmd.count(b"\n") == cmd.count(b"\r\n"), "blinx2.cmd must be CRLF"
    assert b"\r" not in sh and sh.startswith(b"#!/bin/sh\n"), "blinx2 must be LF"
    assert os.access(os.path.join(ROOT, "blinx2"), os.X_OK)


def test_bootstrap_is_the_template():
    """blinx2.py is xboxrecomp-cli's wrapper/game.py, unchanged (the CLI's
    `blinx2 wrapper --check` says the same)."""
    d = xbr_cli.cli_dir()
    if d is None:
        print("skip test_bootstrap_is_the_template: " + xbr_cli.SKIP)
        return
    with open(os.path.join(d, "src", "xboxrecomp_cli", "wrapper", "game.py"), "rb") as f:
        want = f.read()
    with open(os.path.join(ROOT, "blinx2.py"), "rb") as f:
        assert f.read().replace(b"\r\n", b"\n") == want


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok   %s" % name)
