#!/usr/bin/env python3
"""Tests for scripts/occ_flips.py, the occ-reports harness check: the idle
pattern passes, the injected-delay pattern (1509 then 157s) fails naming
the count, a log without flip lines exits 2, and the floor is honoured.

  python3 scripts/test_occ_flips.py
  uv run pytest scripts/test_occ_flips.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import occ_flips  # noqa: E402


def metal(n, batches, reports=2, settled=None):
    s = (
        ""
        if settled is None
        else f" settled {settled[0]} (stale {settled[1]}, first {settled[2]}),"
    )
    return (
        f"[METAL] flip {n} batches {batches} prog 0 skipped 0 culled 0 clears 3 tex 0"
        f" uploads 0 changed 0 rehash 0 flushes 2 occ {reports} (visible 2, pending 0,"
        f" late 0, superseded 0,{s} sync 0 us, slot overflow 0) present 0x0 walker 0x0\n"
    )


def d3d11(n, batches, reports=2, settled=(0, 0, 0)):
    return (
        f"[D3D11] flip {n} batches {batches} prog 0 tex 0 rtt 0 (self 0) skipped 0 culled 0"
        f" clears 3 uploads 0 (mip 0) changed 0 rehash 0 vb 0/0 bytes occ {reports}"
        f" (visible 2, pending 0, late 0, superseded 0, settled {settled[0]}"
        f" (stale {settled[1]}, first {settled[2]}), sync 0 us) present 0x0 walker 0x0\n"
    )


def run(lines, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.writelines(lines)
    try:
        return occ_flips.main([f.name, *args])
    finally:
        os.unlink(f.name)


def test_idle_passes():
    log = ["boot\n"] + [metal(i, 40) for i in range(1, 50)]
    log += [metal(i, 1509, settled=(0, 0, 0)) for i in range(50, 400)]
    assert run(log) == 0
    code, lines = occ_flips.check(occ_flips.parse(log), 1400)
    assert code == 0 and "below 1400: 0" in lines
    assert any("settled 0 (stale 0, first 0)" in s for s in lines)


def test_delay_fails_naming_the_count():
    log = [metal(i, 40) for i in range(1, 50)] + [metal(50, 1509)]
    log += [metal(i, 157) for i in range(51, 200)]
    code, lines = occ_flips.check(occ_flips.parse(log), 1400)
    assert code == 1
    assert any(s.startswith("FAIL: 149 flips below 1400") for s in lines)
    assert any("157 x149" in s for s in lines)
    assert any("no settled field" in s for s in lines)


def test_settled_totals_d3d11():
    log = [d3d11(1, 1509, settled=(2, 0, 2))]
    log += [d3d11(i, 1509, settled=(2, 2, 0)) for i in range(2, 11)]
    code, lines = occ_flips.check(occ_flips.parse(log), 1400)
    assert code == 0
    assert any("20 reports, settled 20 (stale 18, first 2)" in s for s in lines)


def test_no_flip_lines_exits_2():
    assert run(["[GPU] flip 1\n", "nothing here\n"]) == 2


def test_floor_is_honoured():
    log = [metal(1, 1509)] + [metal(i, 1450) for i in range(2, 20)]
    assert run(log) == 0
    assert run(log, "--min-batches", "1500") == 1


def test_screen_never_up_fails():
    log = [metal(i, 157) for i in range(1, 20)]
    code, lines = occ_flips.check(occ_flips.parse(log), 1400)
    assert code == 1 and lines[0].startswith("screen never up")


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
