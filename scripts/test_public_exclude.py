#!/usr/bin/env python3
"""Tests for game.toml's [public] exclude against .gitignore: every tracked
file on an ignored path is named by an exclude glob or deliberately
un-ignored. The old export script rebuilt the tree with `git add`, so it
never published such a file; `blinx2 public export` reads the tracked tree
and would, so a file tracked by accident under analysis/* (a shader list,
a replay) has to fail here first.

  python3 scripts/test_public_exclude.py
  python3 -m pytest scripts/test_public_exclude.py

Exit 0 when every test passes.
"""

import fnmatch
import os
import subprocess
import sys

import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def excludes():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        return tomllib.load(f).get("public", {}).get("exclude", [])


def tracked_but_ignored():
    r = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z", "-ci", "--exclude-standard"],
        capture_output=True,
        check=True,
    )
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def test_tracked_ignored_files_are_excluded():
    globs = excludes()
    left = [
        p
        for p in tracked_but_ignored()
        if not any(
            fnmatch.fnmatchcase(p, g.rstrip("/")) or p.startswith(g.rstrip("/") + "/")
            for g in globs
        )
    ]
    assert not left, "tracked on an ignored path, published by `public export`: %s" % ", ".join(
        left
    )


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
