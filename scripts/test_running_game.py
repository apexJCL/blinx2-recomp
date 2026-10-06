#!/usr/bin/env python3
"""Tests for running_game.py on synthetic process listings. Plain asserts;
runs alone or under pytest.

  python3 scripts/test_running_game.py
  python3 -m pytest scripts/test_running_game.py

Exit 0 when every test passes.
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import running_game as rg  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


def test_match_rule():
    yes = [["/home/u/Games/BLiNX2/versions/v1/cat_recomp.exe"],
           ["wine64", "Z:\\home\\u\\Games\\BLiNX2\\versions\\v1\\cat_recomp.exe"],
           ["C:\\Program Files\\x\\CAT_RECOMP.EXE"],
           ["/Applications/BLiNX2.app/Contents/MacOS/cat_recomp"],
           ["./build/cat_recomp", "--flag"],
           ["cat_recomp.exe"]]
    no = [[], ["cat_recomp.exe.log"], ["/usr/bin/tail", "-f", "logs/cat_recomp.log"],
          ["/x/cat_recomp_test"], ["vim", "src/cat_recomp.c"], ["/x/not_cat_recomp"],
          ["grep", "cat_recomp"]]
    for a in yes:
        assert rg.is_game(a), a
    for a in no:
        assert not rg.is_game(a), a


def test_proc_reader(d):
    proc = os.path.join(d, "proc")

    def mk(pid, ppid, argv, comm="x y"):
        p = os.path.join(proc, str(pid))
        os.makedirs(p)
        with open(os.path.join(p, "cmdline"), "wb") as f:
            f.write(b"\0".join(a.encode() for a in argv) + b"\0")
        with open(os.path.join(p, "stat"), "w") as f:
            f.write("%d (%s) S %d 1 1 0" % (pid, comm, ppid))

    mk(10, 1, ["wine64", "Z:\\g\\cat_recomp.exe"], comm="a) b")
    mk(11, 10, [])
    os.makedirs(os.path.join(proc, "self"))
    got = sorted(rg.processes_linux(proc))
    assert got == [(10, 1, ["wine64", "Z:\\g\\cat_recomp.exe"]), (11, 10, [])], got


def test_parse_ps():
    text = ("    1     0 /sbin/launchd\n"
            "  500     1 /Applications/My Games/BLiNX2.app/Contents/MacOS/cat_recomp -x\n"
            "  501   500 /bin/zsh -l\n"
            "garbage line\n")
    got = rg.parse_ps(text)
    assert got[1] == (500, 1, ["/Applications/My Games/BLiNX2.app/Contents/MacOS/cat_recomp", "-x"]), got
    assert len(got) == 3
    assert rg.is_game(got[1][2]) and not rg.is_game(got[2][2])


def test_own_tree_excluded():
    # 1 init; 100 shell; 200 bench (me) -> 201 umu -> 202 game (ours);
    # 100 -> 300 foreign game started from the same shell.
    procs = [(1, 0, ["init"]), (100, 1, ["bash"]), (200, 100, ["bench.sh"]),
             (201, 200, ["umu-run", "/r/cat_recomp.exe"]), (202, 201, ["wine", "Z:\\r\\cat_recomp.exe"]),
             (300, 100, ["/i/versions/v/cat_recomp.exe"])]
    assert rg.own_tree(procs, 200) == {1, 100, 200, 201, 202}
    assert [p for p, _ in rg.find_games(procs, 200)] == [300]


def test_cycle_safe():
    procs = [(5, 6, ["a"]), (6, 5, ["b"]), (7, 5, ["cat_recomp.exe"])]
    assert rg.own_tree(procs, 5) == {5, 6, 7}


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
