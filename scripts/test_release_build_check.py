#!/usr/bin/env python3
"""release_build_check.py's checks on a fake tree (no clone, no build):
the bundle line it reads and the pins it holds the tree to. Plain asserts;
runs alone or under pytest.

  uv run pytest scripts/test_release_build_check.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import release_build_check as rbc  # noqa: E402

GIT_ENV = dict(
    os.environ,
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_NOSYSTEM="1",
    GIT_AUTHOR_NAME="t",
    GIT_AUTHOR_EMAIL="t@example.invalid",
    GIT_COMMITTER_NAME="t",
    GIT_COMMITTER_EMAIL="t@example.invalid",
)


def git(*args):
    r = subprocess.run(
        ["git"] + list(args), env=GIT_ENV, capture_output=True, text=True, check=True
    )
    return r.stdout.strip()


def repo(d):
    os.makedirs(d)
    git("init", "-q", d)
    git("-C", d, "commit", "-q", "--allow-empty", "-m", "c")
    return git("-C", d, "rev-parse", "HEAD")


def fake_tree(d, tk_pin=None, cli_pin=None):
    tree = os.path.join(d, "src")
    tk = repo(os.path.join(tree, "external", "xboxrecomp"))
    cli = repo(os.path.join(tree, "external", "xboxrecomp-cli"))
    with open(os.path.join(tree, "game.toml"), "w") as f:
        f.write(
            '[cli]\ntag = "v0.1.0"\ncommit = "%s"\n[toolkit]\ntag = "t-v0.1.0"\ncommit = "%s"\n'
            % (cli_pin or cli, tk_pin or tk)
        )
    return tree, tk


def test_bundle_from_log():
    text = "bundle: full (--full)\nbundle: /d/G-1-ca-t1234567-g8-windows\nnote: x\n"
    assert rbc.bundle_from_log(text) == "/d/G-1-ca-t1234567-g8-windows"
    assert rbc.bundle_from_log("no bundle here\n") == ""


def test_pin_problems_at_the_pins():
    with tempfile.TemporaryDirectory() as d:
        tree, tk = fake_tree(d)
        assert rbc.pin_problems(tree, "/d/G-1-ca-t%s-g8-windows" % tk[:7]) == []


def test_pin_problems_off_the_pins():
    # The update path's failure: the toolkit checkout left at the old pin,
    # and a bundle that names another toolkit.
    with tempfile.TemporaryDirectory() as d:
        tree, tk = fake_tree(d, tk_pin="ab" * 20)
        got = rbc.pin_problems(tree, "/d/G-1-ca-t%s-g8-dirtyc7-windows" % tk[:7])
        assert any(p.startswith("toolkit: external/xboxrecomp is at") for p in got), got
        assert any("not built on the pinned toolkit tababab" in p for p in got), got
        assert any("dirty" in p for p in got), got
        assert not any(p.startswith("cli:") for p in got), got
        assert rbc.pin_problems(tree, "")[-1] == "package named no bundle"


def test_run_failures_are_the_scripts_own_message():
    # Without a log (the clone, the checkouts) as with one: a one-line
    # "release check:" exit, never a traceback.
    false = [sys.executable, "-c", "raise SystemExit(3)"]
    for log in (None, "log"):
        with tempfile.TemporaryDirectory() as d:
            try:
                rbc.run(false, cwd=d, log=log and os.path.join(d, log))
            except SystemExit as e:
                msg = str(e.code)
            else:
                msg = ""
        assert msg.startswith("release check: ") and "(exit 3)" in msg, msg


if __name__ == "__main__":
    test_bundle_from_log()
    test_pin_problems_at_the_pins()
    test_pin_problems_off_the_pins()
    test_run_failures_are_the_scripts_own_message()
    print("ok")
