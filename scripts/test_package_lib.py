#!/usr/bin/env python3
"""Tests for package_lib.py on synthetic inputs (no game data, no build).
Plain asserts; runs alone or under pytest.

  python3 scripts/test_package_lib.py
  python3 -m pytest scripts/test_package_lib.py

Exit 0 when every test passes.
"""

import datetime
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
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


def state(commit, dirt=""):
    return {"commit": commit, "branch": "main", "dirty": bool(dirt),
            "dirty_paths": 1 if dirt else 0, "_dirt": dirt}


T1 = datetime.datetime(2026, 10, 1, 21, 43, tzinfo=datetime.timezone.utc)
T2 = datetime.datetime(2026, 10, 2, 9, 5, tzinfo=datetime.timezone.utc)


def test_version_format():
    v = pl.format_version(T1, state("874f29d" + "0" * 33), state("fbfc46f" + "1" * 33), "4e521f24" + "f" * 56)
    assert v == "20261001.2143-c874f29d-tfbfc46f-g4e521f24", v
    later = pl.format_version(T2, state("874f29d" + "0" * 33), state("fbfc46f" + "1" * 33), "4e521f24" + "f" * 56)
    assert sorted([later, v]) == [v, later]


def test_dirty_suffix():
    c, t, g = "a" * 40, "b" * 40, "c" * 64
    a1 = pl.format_version(T1, state(c, "d1"), state(t), g)
    a2 = pl.format_version(T1, state(c, "d1"), state(t), g)
    b = pl.format_version(T1, state(c, "d2"), state(t), g)
    assert a1 == a2 and a1 != b and "-dirty" in a1 and len(a1.split("-dirty")[1]) == 8


def test_tree_state_dirt(d):
    def g(*a):
        subprocess.run(["git", "-C", d] + list(a), check=True, stdout=subprocess.DEVNULL)
    g("init", "-q")
    with open(os.path.join(d, "f"), "w") as f:
        f.write("1")
    g("add", "f")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x")
    assert not pl.tree_state(d)["dirty"]
    with open(os.path.join(d, "new"), "w") as f:
        f.write("a")
    s1 = pl.tree_state(d)
    with open(os.path.join(d, "new"), "w") as f:
        f.write("b")
    s2 = pl.tree_state(d)
    assert s1["dirty"] and s1["_dirt"] != s2["_dirt"]


def test_gen_digest_matches_bench(d):
    gen = os.path.join(d, "gen")
    os.makedirs(gen)
    for n, data in (("b.c", b"2"), ("a.c", b"1"), ("recomp_funcs.h", b"3"), (".hidden", b"x")):
        with open(os.path.join(gen, n), "wb") as f:
            f.write(data)
    sha, n = pl.gen_digest(gen)
    # bench.sh: (cd gen && shasum -a 256 -- *) | shasum -a 256
    listing = "".join("%s  %s\n" % (hashlib.sha256(v).hexdigest(), k)
                      for k, v in sorted({"a.c": b"1", "b.c": b"2", "recomp_funcs.h": b"3"}.items()))
    assert n == 3 and sha == hashlib.sha256(listing.encode()).hexdigest()
    try:
        out = subprocess.run("shasum -a 256 -- * | shasum -a 256", shell=True, cwd=gen,
                             stdout=subprocess.PIPE, check=True).stdout.decode().split()[0]
        assert out == sha
    except (OSError, subprocess.CalledProcessError):
        pass   # no shasum on this host


def test_xbe_title():
    hdr = bytearray(0x200)
    hdr[:4] = b"XBEH"
    struct.pack_into("<I", hdr, 0x104, 0x10000)
    struct.pack_into("<I", hdr, 0x118, 0x10000 + 0x180)
    struct.pack_into("<I", hdr, 0x180 + 8, pl.TITLE_ID)
    assert pl.xbe_title_id(bytes(hdr)) == pl.TITLE_ID
    for bad in (b"MZ" + bytes(0x200), bytes(hdr[:0x100])):
        try:
            pl.xbe_title_id(bad)
            assert False, "accepted a bad header"
        except ValueError:
            pass


def test_cache_problems():
    assert pl.cache_problems({"CMAKE_BUILD_TYPE": "Release"}) == ([], [])
    dbg, ns = pl.cache_problems({"CMAKE_BUILD_TYPE": "Debug", "CAT_GEN_OPT": "-O1",
                                 "XBOXRECOMP_ENHANCE": "OFF"})
    assert len(dbg) == 1 and len(ns) == 2


def test_manifest_and_sums(d):
    root = os.path.join(d, "payload")
    os.makedirs(os.path.join(root, "game_files", "media"))
    for rel, data in (("cat_recomp.exe", b"MZ"), ("game_files/default.xbe", b"XBEH"),
                      ("game_files/media/a.xpr", b"x")):
        with open(os.path.join(root, rel), "wb") as f:
            f.write(data)
    m = pl.build_manifest(root, "steamos-x86_64-proton", "v", state("a" * 40), state("b" * 40),
                          "c" * 64, 109, {"CMAKE_BUILD_TYPE": "Release"}, "clang 21",
                          extra={"host": {"os": "macos", "arch": "aarch64"}, "ghidra_names": False})
    for k in ("schema", "product", "version", "target", "built", "sources", "gen", "build",
              "data_layout", "files", "notice", "host", "ghidra_names"):
        assert k in m, k
    text = json.dumps(m, indent=2)
    assert pl.private_leaks(text, home="/Users/someone", host="somehost") == []
    assert root not in text
    sums = pl.sums_text(m)
    assert [l.split("  ", 1)[1] for l in sums.splitlines()] == [f["path"] for f in m["files"]]
    for line in sums.splitlines():
        h, rel = line.split("  ", 1)
        assert h == pl.sha256_file(os.path.join(root, rel))


def test_private_leaks():
    assert pl.private_leaks('{"a": "/Users/x/y"}', home="/nope", host="zz") == ["absolute path"]
    assert "home directory" in pl.private_leaks("/opt/me/x", home="/opt/me", host="zz")
    assert pl.private_leaks("built on Gamebox", home="/nope", host="gamebox") == ["host name"]
    assert pl.private_leaks('{"p": "C:\\\\Users\\\\x"}', home="/nope", host="zz") == ["absolute path"]


def fake_otool(table):
    def run(path):
        lines = [path + ":"] + ["\t%s (compatibility version 1.0.0, current version 1.0.0)" % x
                                for x in table[path]]
        return "\n".join(lines) + "\n"
    return run


def test_dylib_plan():
    table = {
        "/b/cat_recomp": ["/opt/homebrew/opt/sdl2/lib/libSDL2-2.0.0.dylib", "/usr/lib/libSystem.B.dylib",
                          "/opt/homebrew/opt/openssl/lib/libcrypto.3.dylib"],
        "/opt/homebrew/opt/sdl2/lib/libSDL2-2.0.0.dylib": ["/opt/homebrew/opt/sdl2/lib/libSDL2-2.0.0.dylib",
                                                           "/usr/lib/libSystem.B.dylib"],
        "/opt/homebrew/opt/openssl/lib/libcrypto.3.dylib": ["/opt/homebrew/opt/openssl/lib/libcrypto.3.dylib",
                                                            "/opt/homebrew/opt/zz/lib/libz.1.dylib"],
        "/opt/homebrew/opt/zz/lib/libz.1.dylib": ["/opt/homebrew/opt/zz/lib/libz.1.dylib"],
        "/opt/homebrew/lib/libSDL3.dylib": ["@rpath/libSDL3.0.dylib", "/System/Library/Frameworks/X"],
    }
    plan = pl.dylib_plan("/b/cat_recomp", ["libSDL3.dylib=/opt/homebrew/lib/libSDL3.dylib"],
                         run=fake_otool(table), realpath=lambda p: p)
    names = [l["name"] for l in plan["libs"]]
    assert names == ["libSDL2-2.0.0.dylib", "libSDL3.dylib", "libcrypto.3.dylib", "libz.1.dylib"], names
    assert {"file": "libcrypto.3.dylib", "old": "/opt/homebrew/opt/zz/lib/libz.1.dylib",
            "new": "@rpath/libz.1.dylib"} in plan["changes"]
    assert all(not c["old"].startswith("/usr/lib") for c in plan["changes"])


def test_game_files_exclusions(d):
    src = os.path.join(d, "src")
    for rel in ("default.xbe", "default_analysis.json", "UDATA/x", "TDATA/y", ".DS_Store",
                "media/a.xpr", "media/.DS_Store"):
        p = os.path.join(src, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(rel)
    dst = os.path.join(d, "dst")
    pl.stage_game_files(src, dst)
    assert pl.list_files(dst) == ["default.xbe", "media/a.xpr"], pl.list_files(dst)


def test_staged_refusals(d):
    os.makedirs(os.path.join(d, "game_files", "nul"))
    with open(os.path.join(d, "launch.sh"), "wb") as f:
        f.write(b"#!/bin/sh\r\nexit 0\r\n")
    with open(os.path.join(d, "README.txt"), "wb") as f:
        f.write(b"crlf is fine here\r\n")
    with open(os.path.join(d, "trail."), "w") as f:
        f.write("")
    probs = pl.staged_problems(d)
    assert sorted(probs) == ["game_files/nul: reserved name on Windows",
                             "launch.sh: CRLF line endings",
                             "trail.: trailing dot or space"], probs
    for ok in ("con_trol", "LPT10", "aux_data.bin", "media"):
        assert pl.name_problem(ok) is None, ok
    for bad in ("COM1", "lpt3.txt", "Aux.dat", "a<b"):
        assert pl.name_problem(bad), bad


def test_nsis_lists(d):
    root = os.path.join(d, "pay$load")
    os.makedirs(os.path.join(root, "game_files"))
    for n in ("cat_recomp.exe", "BLiNX2.exe", "game_files/default.xbe"):
        with open(os.path.join(root, n), "w") as f:
            f.write("x")
    names, inst, uninst = pl.nsis_lists(root)
    assert names == ["BLiNX2.exe", "cat_recomp.exe"]
    assert "pay$$load" in inst and "game_files" not in inst
    assert uninst == '  Delete "$INSTDIR\\BLiNX2.exe"\n  Delete "$INSTDIR\\cat_recomp.exe"\n'
    os.makedirs(os.path.join(root, "extra"))
    with open(os.path.join(root, "extra", "x"), "w") as f:
        f.write("x")
    try:
        pl.nsis_lists(root)
        assert False, "a payload subdirectory was dropped silently"
    except ValueError as e:
        assert "extra/x" in str(e)


def test_missing_media(d):
    # A synthetic image (made-up names): path templates, names of files the
    # dump has and lacks, and look-alike strings that are not media (wrong
    # family, wrong shape, a family with a single file).
    strings = [b"music\\%s.adx", b"bgm_MAIN", b"bgm_HUBa", b"bgm_START",
               b"bgm_tex_01", b"fanfare_03", b"VC_ab1-0_XYZ", b"VC_cd1-1a_QRST_P",
               b"VC_6-1a_XYZ", b"VM_ab1-1_QQ", b"Bgm_finalboss", b"intro_tex_xx"]
    data = b"XBEH" + b"\0" * 16 + b"\0".join(strings) + b"\0"
    files = {"adx": ["bgm_MAIN.adx", "bgm_HUBa.adx", "bgm_FINALBOSS.adx",
                     "fanfare_01first.adx"],
             "voice": ["VC_ab1-0_XYZ.adx", "VC_6-1a_XYZ.adx", "VC_cd1-1a_QRST.adx",
                       "VC_ef3-2b_UVW_P.adx", "VM_ab2-3b_QQ.adx"],
             "movie": ["intro_movie_1a.sfd", "intro_movie_2a.sfd", "art_vs_img.sfd"]}
    for sub, names in files.items():
        os.makedirs(os.path.join(d, sub))
        for n in names:
            open(os.path.join(d, sub, n), "w").close()
    m = pl.missing_media(data, d)
    # bgm_tex_01: shape a_a_0, no bgm file has it; Bgm_finalboss: present,
    # matched without case; VM_*: one VM file only; intro_tex_xx: the intro
    # files are intro_movie_<n><x>, a different shape.
    assert m == {"adx": ["bgm_START"], "voice": ["VC_cd1-1a_QRST_P"]}, m
    text = pl.missing_media_text(m)
    assert "2 media files" in text and "bgm_START" in text
    assert "Extract the disc again" in text
    assert pl.missing_media_text({}) == ""
    # A dump without the media folders warns about nothing.
    assert pl.missing_media(data, os.path.join(d, "nowhere")) == {}

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
