#!/usr/bin/env python3
"""Tests for packaging/steamos/install_lib.py on fake bundles in a temp dir
(no game data, no Proton). Plain asserts; runs alone or under pytest.

  python3 scripts/test_steamos_install.py
  python3 -m pytest scripts/test_steamos_install.py

Every command runs between two snapshots of hdd/, config/ and logs/ (paths,
sizes, mtimes, contents): the installer must never write the user's data.
Exit 0 when every test passes.
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "packaging", "steamos"))
import install_lib as il  # noqa: E402
import package_lib as pl  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


def make_bundle(base, version, exe=b"MZ program", game=None):
    """A payload like `blinx2 package steamos` stages, with a real manifest."""
    b = os.path.join(base, "BLiNX2-%s-steamos" % version)
    os.makedirs(os.path.join(b, "game_files", "media"))
    files = {"cat_recomp.exe": exe, "launch.sh": b"#!/bin/sh\nexit 0\n",
             "install.sh": b"#!/bin/sh\n", "install_lib.py": b"# lib\n",
             "launch.env.default": b"RECOMP_PB_BACKEND=d3d11\n", "README.txt": b"readme\n"}
    game = game or {"default.xbe": b"XBEH game", "media/a.xpr": b"asset a"}
    for n, data in files.items():
        with open(os.path.join(b, n), "wb") as f:
            f.write(data)
    for n, data in game.items():
        with open(os.path.join(b, "game_files", n), "wb") as f:
            f.write(data)
    st = {"commit": "a" * 40, "branch": "main", "dirty": False, "dirty_paths": 0, "_dirt": ""}
    m = pl.build_manifest(b, "steamos-x86_64-proton", version, st, st, "c" * 64, 1,
                          {"CMAKE_BUILD_TYPE": "Release"}, "clang")
    with open(os.path.join(b, "manifest.json"), "w") as f:
        json.dump(m, f)
    with open(os.path.join(b, "SHA256SUMS"), "w") as f:
        f.write(pl.sums_text(m))
    return b


def snapshot(root):
    out = {}
    for d in il.USER_DIRS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(root, d)):
            for n in dirnames + filenames:
                p = os.path.join(dirpath, n)
                st = os.lstat(p)
                data = b""
                if os.path.isfile(p):
                    with open(p, "rb") as f:
                        data = f.read()
                out[os.path.relpath(p, root)] = (st.st_mode, st.st_size, st.st_mtime_ns,
                                                 hashlib.sha256(data).hexdigest())
    return out


def plant_user_data(root):
    for rel, data in (("hdd/UDATA/4d530065/save.xsv", b"save"), ("config/enhance.toml", b"[render]\n"),
                      ("config/launch.env", b"LOG_KEEP=3\n"), ("logs/game-1.log", b"log")):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)


def cli(bundle, root, *args, bench="/nonexistent-bench"):
    """install_lib.main with the host check off; returns (exit, output) and
    asserts the user data is untouched."""
    before = snapshot(root)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = il.main(list(args) + ["--root", root, "--bundle", bundle], host_check=False, bench=bench)
    if "--import-saves" not in args:
        assert snapshot(root) == before, "user data changed by %s" % (args,)
    return rc, buf.getvalue()


def test_first_install_layout(d):
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    root = os.path.join(d, "Games", "BLiNX2")
    rc, out = cli(b, root, "install")
    assert rc == 0, out
    assert os.readlink(os.path.join(root, "current")) == os.path.join("versions", "20261001.0000-ca-tb-g1")
    for rel in ("versions/20261001.0000-ca-tb-g1/cat_recomp.exe", "game_files/default.xbe",
                "game_files/media/a.xpr", "state/history", "state/layout"):
        assert os.path.isfile(os.path.join(root, rel)), rel
    launcher = os.path.join(root, "BLiNX2")
    assert os.path.isfile(launcher) and not os.path.islink(launcher) and os.access(launcher, os.X_OK)
    assert os.access(os.path.join(root, "current", "launch.sh"), os.X_OK)
    assert not os.path.exists(os.path.join(root, "hdd")), "install must not create hdd/"


def test_same_version_noop(d):
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    root = os.path.join(d, "r")
    cli(b, root, "install")
    plant_user_data(root)
    hist = open(os.path.join(root, "state", "history")).read()
    rc, out = cli(b, root, "install")
    assert rc == 0 and "already installed" in out and "unchanged" in out, out
    assert open(os.path.join(root, "state", "history")).read() == hist


def test_corrupt_bundle_keeps_current(d):
    root = os.path.join(d, "r")
    v1 = make_bundle(os.path.join(d, "1"), "20261001.0000-ca-tb-g1")
    cli(v1, root, "install")
    v2 = make_bundle(os.path.join(d, "2"), "20261002.0000-ca-tb-g2", exe=b"MZ v2")
    with open(os.path.join(v2, "cat_recomp.exe"), "ab") as f:
        f.write(b"damage")
    rc, out = cli(v2, root, "install")
    assert rc == 1 and "checksum mismatch" in out, out
    assert il.Root(root).current() == "20261001.0000-ca-tb-g1"
    assert not [n for n in os.listdir(os.path.join(root, "versions")) if n.endswith(".partial")]


def test_failed_copy_removes_partial(d):
    root = os.path.join(d, "r")
    v1 = make_bundle(os.path.join(d, "1"), "20261001.0000-ca-tb-g1")
    cli(v1, root, "install")
    v2 = make_bundle(os.path.join(d, "2"), "20261002.0000-ca-tb-g2", exe=b"MZ v2")
    real = il.sha256_file
    calls = {"n": 0}

    def flaky(p, *a):
        # Damage the check of the copy in versions/<v>.partial only.
        if ".partial" in p:
            calls["n"] += 1
            return "0" * 64
        return real(p, *a)
    il.sha256_file = flaky
    try:
        rc, out = cli(v2, root, "install")
    finally:
        il.sha256_file = real
    assert rc == 1 and calls["n"] and "copy damaged" in out, out
    assert il.Root(root).current() == "20261001.0000-ca-tb-g1"
    assert not os.path.exists(os.path.join(root, "versions", "20261002.0000-ca-tb-g2.partial"))


def test_switch_is_one_rename(d):
    root = os.path.join(d, "r")
    v1 = make_bundle(os.path.join(d, "1"), "20261001.0000-ca-tb-g1")
    v2 = make_bundle(os.path.join(d, "2"), "20261002.0000-ca-tb-g2", exe=b"MZ v2")
    cli(v1, root, "install")
    renames = []
    real = il.os.replace

    def spy(a, b):
        renames.append((os.path.basename(a), os.path.basename(b)))
        return real(a, b)
    il.os.replace = spy
    try:
        cli(v2, root, "install")
    finally:
        il.os.replace = real
    assert [r for r in renames if r[1] == "current"] == [("current.new", "current")], renames
    # The unchanged files were hard-linked against v1.
    a = os.stat(os.path.join(root, "versions", "20261001.0000-ca-tb-g1", "launch.sh"))
    b = os.stat(os.path.join(root, "versions", "20261002.0000-ca-tb-g2", "launch.sh"))
    assert a.st_ino == b.st_ino


def test_prune_and_foreign(d):
    root = os.path.join(d, "r")
    vs = ["2026100%d.0000-ca-tb-g%d" % (i, i) for i in range(1, 6)]
    for i, v in enumerate(vs):
        b = make_bundle(os.path.join(d, str(i)), v, exe=("MZ %d" % i).encode())
        rc, out = cli(b, root, "install", "--keep", "2")
        assert rc == 0, out
        if i == 0:   # a user's own dir beside the versions
            os.makedirs(os.path.join(root, "versions", "my-notes"))
    left = sorted(n for n in os.listdir(os.path.join(root, "versions")))
    # keep 2 newest (v4, v5) + current (v5) + previous (v4); v1-v3 removed.
    assert left == sorted(vs[3:] + ["my-notes"]), left
    assert "left alone: versions/my-notes" in out


def test_rollback(d):
    root = os.path.join(d, "r")
    v1 = make_bundle(os.path.join(d, "1"), "20261001.0000-ca-tb-g1")
    v2 = make_bundle(os.path.join(d, "2"), "20261002.0000-ca-tb-g2", exe=b"MZ v2")
    cli(v1, root, "install")
    cli(v2, root, "install")
    plant_user_data(root)
    rc, out = cli(v2, root, "rollback")
    assert rc == 0 and il.Root(root).current() == "20261001.0000-ca-tb-g1", out
    rc, out = cli(v2, root, "rollback", "20261002.0000-ca-tb-g2")
    assert rc == 0 and il.Root(root).current() == "20261002.0000-ca-tb-g2", out
    rc, out = cli(v2, root, "rollback", "nope")
    assert rc == 1 and "not installed" in out
    rc, out = cli(v2, root, "list")
    assert rc == 0 and "* 20261002" in out


def test_dev_tree_refused(d):
    bench = os.path.join(d, "xbox-recomp")
    os.makedirs(os.path.join(bench, "cat"))
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    rc, out = cli(b, os.path.join(bench, "Games"), "install", bench=bench)
    assert rc == 1 and "dev/bench tree" in out, out
    repo = os.path.join(d, "repo")
    os.makedirs(os.path.join(repo, ".git"))
    rc, out = cli(b, os.path.join(repo, "inst"), "install")
    assert rc == 1 and "git checkout" in out, out


def test_desktop_entry_and_steam(d):
    root = os.path.join(d, 'my "Games" $x', "BLiNX2")
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    rc, out = cli(b, root, "install")
    assert rc == 0, out
    with open(os.path.join(root, "BLiNX2.desktop")) as f:
        entry = f.read().splitlines()
    assert entry[0] == "[Desktop Entry]"
    kv = dict(l.split("=", 1) for l in entry[1:])
    assert kv["Name"] == pl.PRODUCT_NAME and kv["Type"] == "Application"
    assert kv["Terminal"] == "false"
    assert kv["Icon"] == os.path.join(root, "current", "icon.png")
    # Exec: one quoted argument; ", ` and $ escaped, then backslashes doubled.
    want = '"%s"' % os.path.join(root, "BLiNX2").replace('"', '\\"').replace("$", "\\$")
    assert kv["Exec"] == want.replace("\\", "\\\\"), kv["Exec"]
    # --steam hands the desktop entry (not the script) to the helper.
    bindir = os.path.join(d, "bin")
    os.makedirs(bindir)
    argv_log = os.path.join(d, "helper.argv")
    for name, body in (("steamos-add-to-steam", 'printf "%%s\\n" "$@" > "%s"\n' % argv_log),
                       ("pgrep", "exit 0\n")):
        with open(os.path.join(bindir, name), "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(os.path.join(bindir, name), 0o755)
    saved = {k: os.environ.get(k) for k in ("PATH", "DISPLAY")}
    os.environ["PATH"] = bindir + os.pathsep + "/usr/bin:/bin"
    os.environ["DISPLAY"] = ":0"
    try:
        rc, out = cli(b, root, "install", "--steam")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    assert rc == 0, out
    with open(argv_log) as f:
        assert f.read().splitlines() == [os.path.join(root, "BLiNX2.desktop")]
    rc, out = cli(b, root, "uninstall")
    assert not os.path.exists(os.path.join(root, "BLiNX2.desktop"))


def test_uninstall_keeps_user_data(d):
    root = os.path.join(d, "r")
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    cli(b, root, "install")
    plant_user_data(root)
    os.makedirs(os.path.join(root, "prefix", "drive_c"))
    rc, out = cli(b, root, "uninstall")
    assert rc == 0, out
    assert sorted(os.listdir(root)) == ["config", "hdd", "logs"], os.listdir(root)
    assert "Remove the %s shortcut" % pl.PRODUCT_NAME in out, out
    # Installing again into what uninstall left works; cli() checks the
    # saves are untouched.
    rc, out = cli(b, root, "install")
    assert rc == 0, out
    assert os.path.isfile(os.path.join(root, "game_files", "default.xbe"))


def test_foreign_root_refused(d):
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    root = os.path.join(d, "Games")
    os.makedirs(os.path.join(root, "game_files"))
    with open(os.path.join(root, "game_files", "mine.txt"), "w") as f:
        f.write("not yours")
    os.makedirs(os.path.join(root, "versions", "x"))
    for args in (("install",), ("uninstall",), ("rollback",)):
        rc, out = cli(b, root, *args)
        assert rc == 1 and "not a BLiNX2 install root" in out, (args, out)
    assert os.path.isfile(os.path.join(root, "game_files", "mine.txt"))
    assert os.path.isdir(os.path.join(root, "versions", "x"))
    # An empty or absent root is fine for install.
    empty = os.path.join(d, "empty")
    os.makedirs(empty)
    assert cli(b, empty, "install")[0] == 0


def test_import_saves(d):
    root = os.path.join(d, "r")
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    old = os.path.join(d, "old")
    os.makedirs(os.path.join(old, "UDATA", "4d530065"))
    with open(os.path.join(old, "UDATA", "4d530065", "s"), "w") as f:
        f.write("s")
    rc, out = cli(b, root, "install", "--import-saves", old)
    assert rc == 0 and os.path.isfile(os.path.join(root, "hdd", "UDATA", "4d530065", "s")), out
    before = snapshot(root)
    rc, out = cli(b, root, "install", "--import-saves", old)
    assert rc == 1 and "not empty" in out, out
    assert snapshot(root) == before


def test_tar_modes(d):
    import blinx2
    b = make_bundle(d, "20261001.0000-ca-tb-g1")
    os.chmod(os.path.join(b, "launch.sh"), 0o644)   # as a Windows checkout would leave it
    out = os.path.join(d, "dist")
    os.makedirs(out)
    tar = blinx2.wrap_steamos(b, "20261001.0000-ca-tb-g1", os.path.join(b, "cat_recomp.exe"), out)
    with tarfile.open(tar) as t:
        ms = {m.name: m for m in t.getmembers()}
        top = os.path.basename(b)
        assert all(n == top or n.startswith(top + "/") for n in ms)
        assert ms[top + "/launch.sh"].mode == 0o755 and ms[top + "/install.sh"].mode == 0o755
        assert ms[top + "/cat_recomp.exe"].mode == 0o644
        assert all(m.uid == 0 and m.gid == 0 and m.uname == "" and not m.issym() for m in ms.values())
        assert len({m.mtime for m in ms.values()}) == 1
        t.extractall(os.path.join(d, "x"))
    x = os.path.join(d, "x", top)
    assert os.access(os.path.join(x, "launch.sh"), os.X_OK)
    rc, o = cli(x, os.path.join(d, "r"), "install")
    assert rc == 0, o


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        with tempfile.TemporaryDirectory() as d:
            t(os.path.realpath(d))
        print("ok %s" % t.__name__)
    print("%d tests passed" % len(tests))


if __name__ == "__main__":
    main()
