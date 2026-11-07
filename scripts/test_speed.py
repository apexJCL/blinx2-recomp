#!/usr/bin/env python3
"""Tests for the speed mod, Speed readout (mods."speed.enable", openspec
change b2-full-diagonal-movement, D4).

Compiles a driver against src/speed_logic.h and checks the ratio: no
reading before a straight push has settled, 1.00 on it, 1.69 on a corner
at 1.69 times the speed with the reference kept, the peak of the last
second and its expiry, nothing learned below running speed or from a
corner, and a NaN read as stopped. Then the texts, the env rows, the
golden check's stock value, the registration, and that the mod only
reads the guest.

  python3 scripts/test_speed.py
  uv run pytest scripts/test_speed.py

The C tests skip when no C compiler is on PATH.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

# One "speed l" per line on stdin, one frame each; prints "ratio peak".
# "p id base i0 i1 i2 i3" lines print speed_live_pad instead.
DRIVER = r"""
#include <stdio.h>
#include "speed_logic.h"

int main(void)
{
    struct speed_state st = { 0 };
    float v, l, peak, r;
    unsigned base, ix[4];
    int id;
    char k[32];

    while (scanf("%31s", k) == 1) {
        if (k[0] == 'p') {
            if (scanf("%d %x %x %x %x %x", &id, &base, &ix[0], &ix[1], &ix[2], &ix[3]) != 6)
                return 1;
            printf("%x\n", (unsigned)speed_live_pad(id, base, (const uint32_t *)ix));
            continue;
        }
        if (sscanf(k, "%f", &v) != 1 || scanf("%f", &l) != 1)
            return 1;
        r = speed_step(&st, v, l, &peak);
        printf("%.4f %.4f\n", (double)r, (double)peak);
    }
    return 0;
}
"""

STRAIGHT = 2.1942  # stage 1-1's settled straight push (design section 6)
CORNER = 3.7106  # the same with Full Diagonal Movement on a corner

# The player-facing texts, plain and ASCII only (the user, 2026-11-05).
HELP = (
    "Shows Blinx's run speed on screen: 1.00 straight, up to 1.69 on"
    " diagonals with Full Diagonal Movement."
)
ABOUT = (
    "Debug readout of Blinx's run speed. Push straight on the stick or a"
    " key to set 1.00; diagonals reach 1.69 only with Full Diagonal Movement and Square left"
    " stick. Peak is the top of about the last second."
)


@pytest.fixture(scope="module")
def run():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("no C compiler")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "drv.c")
    exe = os.path.join(d, "drv")
    with open(c, "w") as f:
        f.write(DRIVER)
    subprocess.run([cc, "-std=c11", "-Wall", "-Werror", "-I", SRC, c, "-lm", "-o", exe], check=True)

    def go(frames):
        text = "".join(f"{v} {length}\n" for v, length in frames)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True)
        return [tuple(float(t) for t in line.split()) for line in out.stdout.splitlines()]

    def pad(pid, base, index):
        line = f"p {pid} {base:x} " + " ".join(f"{i & 0xFFFFFFFF:x}" for i in index) + "\n"
        out = subprocess.run([exe], input=line, capture_output=True, text=True, check=True)
        return int(out.stdout.split()[0], 16)

    go.pad = pad
    yield go
    shutil.rmtree(d)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_nothing_before_a_straight_push(run):
    out = run([(STRAIGHT, 1.414)] * 20)
    assert all(r < 0 and p < 0 for r, p in out)


def test_straight_reads_one(run):
    out = run([(STRAIGHT, 1.0)] * 12)
    assert out[-1][0] == pytest.approx(1.0, abs=1e-3)
    # Not before the speed has settled for eight frames.
    assert out[3][0] < 0


def test_corner_reads_1_69_and_keeps_the_reference(run):
    out = run([(STRAIGHT, 1.0)] * 12 + [(CORNER, 1.414)] * 40)
    assert out[-1][0] == pytest.approx(1.691, abs=1e-3)
    assert out[-1][1] == pytest.approx(1.691, abs=1e-3)


def test_corner_with_the_mod_off_reads_one(run):
    out = run([(STRAIGHT, 1.0)] * 12 + [(STRAIGHT, 1.414)] * 40)
    assert out[-1][0] == pytest.approx(1.0, abs=1e-3)


def test_peak_holds_one_second(run):
    frames = [(STRAIGHT, 1.0)] * 12 + [(CORNER, 1.414)] * 5 + [(STRAIGHT, 1.0)] * 29
    out = run(frames)
    assert out[-1][0] == pytest.approx(1.0, abs=1e-3)
    assert out[-1][1] == pytest.approx(1.691, abs=1e-3)
    out = run(frames + [(STRAIGHT, 1.0)])
    assert out[-1][1] == pytest.approx(1.0, abs=1e-3)


def test_slow_or_moving_speeds_teach_nothing(run):
    # A walk below running speed, and a speed still easing up.
    out = run([(0.3, 1.0)] * 20)
    assert out[-1][0] < 0
    out = run([(0.5 + 0.1 * i, 1.0) for i in range(20)])
    assert out[-1][0] < 0


def test_window_edges(run):
    # Inside 0.995..1.005 teaches; just outside does not.
    for length in (0.995, 1.005):
        assert run([(STRAIGHT, length)] * 12)[-1][0] == pytest.approx(1.0, abs=1e-3)
    for length in (0.99, 1.01, 0.97, 1.03):
        assert run([(STRAIGHT, length)] * 20)[-1][0] < 0


def test_a_stale_settle_count_teaches_nothing(run):
    # A settled corner, then one frame on the circle: the corner's speed is
    # not the reference.
    out = run([(CORNER, 1.414)] * 20 + [(CORNER, 1.0)])
    assert out[-1][0] < 0
    # Seven straight frames, one off the circle, seven more: still none.
    out = run([(STRAIGHT, 1.0)] * 7 + [(STRAIGHT, 1.2)] + [(STRAIGHT, 1.0)] * 7)
    assert out[-1][0] < 0
    # And with a reference, a corner then one straight frame keeps it.
    out = run([(STRAIGHT, 1.0)] * 12 + [(CORNER, 1.414)] * 20 + [(CORNER, 1.0)])
    assert out[-1][0] == pytest.approx(1.691, abs=1e-3)


PAD_BASE = 0xEBD278  # [0xADC794] as one Mac run saw it; any base will do
PAD_SIZE = 0x1E4


def test_live_pad_slot_is_id_over_four(run):
    # The walk's index is (id / 4) % 4, not id % 4: ids 0..3 share entry 0.
    index = [2, 0, 3, 1]
    for pid in range(16):
        want = PAD_BASE + index[(pid // 4) % 4] * PAD_SIZE
        assert run.pad(pid, PAD_BASE, index) == want, pid


def test_live_pad_negative_id(run):
    # Truncating: -1..-3 and -128 (a quotient of -32) give entry 0; -4..-15
    # give a negative index, which is no pad.
    index = [1, 2, 3, 0]
    for pid in (-1, -3, -128):
        assert run.pad(pid, PAD_BASE, index) == PAD_BASE + PAD_SIZE
    for pid in (-4, -5, -15):
        assert run.pad(pid, PAD_BASE, index) == 0


def test_live_pad_needs_a_base_and_a_slot(run):
    assert run.pad(0, 0, [0, 0, 0, 0]) == 0
    for slot in range(4):
        assert run.pad(0, PAD_BASE, [slot, 0, 0, 0]) == PAD_BASE + slot * PAD_SIZE
    for slot in (4, 0xFFFFFFFF, -1):
        assert run.pad(0, PAD_BASE, [slot, 0, 0, 0]) == 0


def test_nan_reads_stopped(run):
    out = run([(STRAIGHT, 1.0)] * 12 + [("nan", 1.0)])
    assert out[-1][0] == 0.0


def test_texts():
    text = _read("src", "speed_mod.c")
    m = re.search(r'\{ "enable", NULL, "RECOMP_SPEED_READOUT".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_ENABLE, 0," in m.group(0)
    help_text = "".join(re.findall(r'"([^"]*)"', m.group(0))[3:5])
    assert help_text == HELP
    assert len(help_text.encode()) <= 159 and help_text.isascii()
    about = re.search(r'sizeof k_desc, "Speed readout",(.*?)NULL, "1"', text, re.S)
    about = "".join(re.findall(r'"([^"]*)"', about.group(1)))
    assert about == ABOUT and about.isascii()
    # The card's line, as BLiNX 1's readout writes it.
    assert '"Speed\\nnow %.2f  peak %.2f"' in text


def test_reads_only():
    text = _read("src", "speed_mod.c")
    assert "->hook(" not in text and "poke" not in text
    assert not re.search(r"XBOX_MOD_MEM(32|F)\([^)]*\)\s*=[^=]", text)
    assert '{ "speed", init, NULL, &k_desc, 0 }' in text


def test_env_and_registration():
    env = _read("src", "env", "recomp_env_game.h")
    m = re.search(r'X\(SPEED_READOUT,\s*CONFIG,\s*"RECOMP_SPEED_READOUT",\s*NULL,\s*"([^"]*)"', env)
    assert m and "mods.speed.enable" in m.group(1)
    doc = _read("docs", "env.md")
    assert "| `RECOMP_SPEED_READOUT` | `RECOMP_SPEED_READOUT`" in doc
    assert '| `mods."speed.enable"` |' in doc
    main = _read("src", "main.c")
    assert "mods[nm++] = speed_mod();" in main
    assert "src/speed_mod.c" in _read("CMakeLists.txt")


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.speed.enable") == "off"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
