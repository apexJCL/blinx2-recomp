#!/usr/bin/env python3
"""Release gate: build the public tree as a player's machine does, before
the release tag is pushed (docs/packaging.md, Releasing).

A player either clones the release fresh or updates the clone an earlier
release left behind, keeping its toolkit checkout and build folders. The
second path once shipped broken: the clone moved to the new commit, the
toolkit stayed at the old pin, and the new game code failed to compile
against it. So this gate takes the update path when given --from (a
fresh clone at the previous release, set up, then moved in place to the
new commit) and the fresh path without it, runs `package` with your dump,
and checks that the bundle was built on the toolkit and CLI that
game.toml pins.

  python3 scripts/release_build_check.py --dump PATH --work DIR \\
      [--ref main] [--from vYEAR.MONTH.N] [--target windows]

DIR must not exist yet. It ends up holding the clone, its build and the
bundle, all private (they hold your dump's code): delete it afterwards.
The pinned CLI and toolkit tags must already be public (their push
rounds go first). Takes the better part of an hour on a cold DIR.
"""

import argparse
import os
import re
import subprocess
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11: tomli from the dev group
    import tomli as tomllib

REPO = "https://github.com/apexJCL/blinx2-recomp.git"


def run(argv, cwd=None, log=None, check=True):
    print("$ " + " ".join(argv), flush=True)
    if log is None:
        r = subprocess.run(argv, cwd=cwd)
        if r.returncode:
            sys.exit("release check: %s failed (exit %d)" % (" ".join(argv[:2]), r.returncode))
        return r
    with open(log, "ab") as f:
        r = subprocess.run(argv, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode and check:
        sys.exit("release check: %s failed (exit %d); see %s" % (argv[0], r.returncode, log))
    return r


def head(d):
    r = subprocess.run(["git", "-C", d, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def bundle_from_log(text):
    """The last 'bundle: <path>' line of a package run, or ''."""
    found = re.findall(r"^bundle: (\S.*)$", text, re.M)
    return found[-1].strip() if found else ""


def pin_problems(tree, bundle):
    """What in tree and its bundle is not at game.toml's pins: [] when all is."""
    with open(os.path.join(tree, "game.toml"), "rb") as f:
        m = tomllib.load(f)
    out = []
    for what, sub in (("toolkit", "xboxrecomp"), ("cli", "xboxrecomp-cli")):
        want = m[what].get("commit", "")
        got = head(os.path.join(tree, "external", sub))
        if want and got != want:
            out.append(
                "%s: external/%s is at %s, the pin %s is %s"
                % (what, sub, got[:12] or "nothing", m[what].get("tag", ""), want[:12])
            )
    tk = m["toolkit"].get("commit", "")[:7]
    name = os.path.basename(bundle)
    if not name:
        out.append("package named no bundle")
    elif tk and "-t%s" % tk not in name:
        out.append("bundle %s was not built on the pinned toolkit t%s" % (name, tk))
    if "-dirty" in name:
        out.append("bundle %s was built from a dirty tree" % name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dump", required=True, help="your disc image or dump folder")
    ap.add_argument("--work", required=True, help="a new directory for the clone and its build")
    ap.add_argument("--repo", default=REPO, help="the public repository (default %(default)s)")
    ap.add_argument("--ref", default="main", help="the commit to release (default %(default)s)")
    ap.add_argument("--from", dest="prev", help="the previous release tag: update in place from it")
    ap.add_argument("--target", default="windows", choices=("windows", "steamos", "macos"))
    a = ap.parse_args(argv)
    if os.path.exists(a.work):
        sys.exit("release check: %s exists; give a new directory" % a.work)
    work = os.path.abspath(a.work)
    tree = os.path.join(work, "src")
    log = os.path.join(work, "release-check.log")
    os.makedirs(work)
    run(["git", "clone", "--quiet", a.repo, tree])
    boot = [sys.executable, "blinx2.py"]
    if a.prev:
        # The earlier release's state: its CLI and toolkit at their pins.
        run(["git", "checkout", "--quiet", "--detach", a.prev], cwd=tree)
        # setup ends with doctor, which fails while game_files/ is empty:
        # judge it by the toolkit checkout it leaves instead.
        run(boot + ["setup"], cwd=tree, log=log, check=False)
        with open(os.path.join(tree, "game.toml"), "rb") as f:
            old = tomllib.load(f)["toolkit"].get("commit", "")
        got = head(os.path.join(tree, "external", "xboxrecomp"))
        if not got or (old and got != old):
            sys.exit(
                "release check: setup at %s left no toolkit at its pin; see %s" % (a.prev, log)
            )
    run(["git", "checkout", "--quiet", "--detach", a.ref], cwd=tree)
    dist = os.path.join(work, "dist")
    before = os.path.getsize(log) if os.path.exists(log) else 0
    run(
        boot + ["package", a.target, "--dump", os.path.abspath(a.dump), "--plain", "--out", dist],
        cwd=tree,
        log=log,
    )
    with open(log, "rb") as f:
        f.seek(before)
        bundle = bundle_from_log(f.read().decode("utf-8", errors="replace"))
    problems = pin_problems(tree, bundle)
    for p in problems:
        print("release check: " + p)
    if problems:
        return 1
    how = "updated from %s" % a.prev if a.prev else "fresh clone"
    print("release check: %s at %s (%s) built %s" % (a.target, a.ref, how, bundle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
