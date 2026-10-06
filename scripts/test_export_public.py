#!/usr/bin/env python3
"""Tests for scripts/export-public.sh on a throwaway repository: the curated
README screenshots in docs/images/*.png reach the public tree, while other
images, bundles and the private notes do not slip through.

  python3 scripts/test_export_public.py
  python3 -m pytest scripts/test_export_public.py

Exit 0 when every test passes.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "export-public.sh")
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89")


def git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           *args], check=True, capture_output=True, text=True, env=env)


def make_repo(root, files):
    repo = os.path.join(root, "repo")
    os.makedirs(os.path.join(repo, "scripts"))
    shutil.copy(SCRIPT, os.path.join(repo, "scripts", "export-public.sh"))
    # The repository's own .gitignore decides which images may be tracked.
    shutil.copy(os.path.join(HERE, "..", ".gitignore"), os.path.join(repo, ".gitignore"))
    git(repo, "init", "-q", "-b", "main")
    for rel, data in files.items():
        p = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "x")
    return repo


def export(repo, out):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid")
    return subprocess.run(["bash", os.path.join(repo, "scripts", "export-public.sh"), "HEAD", out],
                          capture_output=True, text=True, env=env)


def test_docs_images_png_are_exported():
    with tempfile.TemporaryDirectory() as d:
        repo = make_repo(d, {"README.md": b"hi\n", "docs/images/hero.png": PNG,
                             "docs/images/title.png": PNG, "TASKS.md": b"private\n"})
        out = os.path.join(d, "out")
        r = export(repo, out)
        assert r.returncode == 0, r.stderr
        assert os.path.isfile(os.path.join(out, "docs/images/hero.png"))
        assert os.path.isfile(os.path.join(out, "docs/images/title.png"))
        assert not os.path.exists(os.path.join(out, "TASKS.md"))


def test_png_outside_docs_images_is_not_trackable():
    # A frame dump anywhere else is ignored by .gitignore, so `git add -A` leaves it out
    # and the export cannot carry it.
    with tempfile.TemporaryDirectory() as d:
        repo = make_repo(d, {"README.md": b"hi\n", "docs/images/hero.png": PNG,
                             "analysis/frame.png": PNG, "docs/other/shot.png": PNG})
        out = os.path.join(d, "out")
        assert export(repo, out).returncode == 0
        assert os.path.isfile(os.path.join(out, "docs/images/hero.png"))
        assert not os.path.exists(os.path.join(out, "analysis/frame.png"))
        assert not os.path.exists(os.path.join(out, "docs/other/shot.png"))


def test_bundles_still_block_the_export():
    with tempfile.TemporaryDirectory() as d:
        repo = make_repo(d, {"README.md": b"hi\n", "docs/images/hero.png": PNG})
        os.makedirs(os.path.join(repo, "dist"))
        with open(os.path.join(repo, "dist", "x.dmg"), "wb") as f:
            f.write(b"x")
        git(repo, "add", "-f", "dist/x.dmg")
        git(repo, "commit", "-q", "-m", "bundle")
        r = export(repo, os.path.join(d, "out"))
        assert r.returncode != 0 and "bundle" in r.stderr


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
