#!/usr/bin/env python3
"""Tests for .gitignore: the dump stays out of git, and so do the two
folders `blinx2 import` keeps beside it while it runs (game_files.partial/
holds the new tree, game_files.old/ the one it replaces). Each holds a
whole disc, so a missing line would put game data one `git add` away.

  python3 scripts/test_gitignore.py
  python3 -m pytest scripts/test_gitignore.py

Exit 0 when every test passes.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ignored(path):
    # --no-index: the answer comes from the rules alone, so a file that
    # is tracked or absent is judged the same.
    r = subprocess.run(
        ["git", "-C", ROOT, "check-ignore", "-q", "--no-index", path],
        capture_output=True,
    )
    assert r.returncode in (0, 1), r.stderr
    return r.returncode == 0


def test_the_dump_and_its_siblings_are_ignored():
    for p in ("game_files/default.xbe", "game_files.partial/x", "game_files.old/x"):
        assert ignored(p), p


def test_neighbours_are_not():
    for p in ("game.toml", "scripts/test_gitignore.py", "game_files.txt"):
        assert not ignored(p), p


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
