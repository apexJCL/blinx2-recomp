#!/usr/bin/env python3
"""Tests for the fdm mod, Full Diagonal Movement (mods."fdm.enable", openspec
change b2-full-diagonal-movement).

Compiles a driver against src/fdm_logic.h and checks the speed factor: 1 on
a straight line and inside the unit circle, BLiNX 1's 1.690 at a square
stick's corner with the walk's 0.4 deadzone, 1 in the 0.6 mode (y forced to
0), stock for a NaN stick or a deadzone of 1 or more, and a small gain just
past the circle. Then the walk constants against the design, the env rows,
the docs/env.md rows, the descriptor (off by default), the golden check's
stock value and the hook slots.

  python3 scripts/test_fdm.py
  uv run pytest scripts/test_fdm.py

The C tests skip when no C compiler is on PATH.
"""

import json
import math
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

# One "x y dz" per line on stdin; prints the factor. "p pad base" lines
# print fdm_live_pad instead.
DRIVER = r"""
#include <stdio.h>
#include "fdm_logic.h"

int main(void)
{
    float x, y, dz;
    unsigned pad, base;
    char k[32];

    while (scanf("%31s", k) == 1) {
        if (k[0] == 'p') {
            if (scanf("%x %x", &pad, &base) != 2)
                return 1;
            printf("%d\n", fdm_live_pad(pad, base));
            continue;
        }
        if (sscanf(k, "%f", &x) != 1 || scanf("%f %f", &y, &dz) != 2)
            return 1;
        printf("%.6f\n", (double)fdm_factor(x, y, dz));
    }
    return 0;
}
"""


@pytest.fixture(scope="module")
def drv():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("no C compiler")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "drv.c")
    exe = os.path.join(d, "drv")
    with open(c, "w") as f:
        f.write(DRIVER)
    subprocess.run([cc, "-std=c11", "-Wall", "-Werror", "-I", SRC, c, "-lm", "-o", exe], check=True)

    def run(x, y, dz=0.4):
        out = subprocess.run(
            [exe], input=f"{x} {y} {dz}\n", capture_output=True, text=True, check=True
        )
        return float(out.stdout.split()[0])

    def live(pad, base=PAD_BASE):
        out = subprocess.run(
            [exe], input=f"p {pad:x} {base:x}\n", capture_output=True, text=True, check=True
        )
        return out.stdout.split()[0] == "1"

    run.live = live
    yield run
    shutil.rmtree(d)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


PAD_BASE = 0xEBD278  # [0xADC794] as one Mac run saw it; any base will do
PAD_SIZE = 0x1E4


def test_live_pads_are_the_four_slots(drv):
    for i in range(4):
        assert drv.live(PAD_BASE + i * PAD_SIZE)
    assert not drv.live(PAD_BASE + 4 * PAD_SIZE)
    assert not drv.live(PAD_BASE - PAD_SIZE)
    # Inside a pad but not at its start.
    assert not drv.live(PAD_BASE + 4)
    assert not drv.live(PAD_BASE + PAD_SIZE + 0x14)
    # No pads yet.
    assert not drv.live(0, 0)


def test_other_pad_sources_keep_the_stock_walk(drv):
    # REC playback, the CPU input array and the [0xEC4B6C] array (0x176FB0).
    for pad in (0xDD5B28, 0x5F0760, 0x5F0760 + PAD_SIZE, 0xCCCE00, 0xCCCE00 + 3 * PAD_SIZE):
        assert not drv.live(pad)


def test_straight_line_is_stock(drv):
    assert drv(1.0, 0.0) == 1.0
    assert drv(0.0, -1.0) == 1.0


def test_inside_the_circle_is_stock(drv):
    # A round pad's diagonal: L = 1 at most.
    assert drv(0.7071, 0.7071) == 1.0
    assert drv(0.3, 0.2) == 1.0
    assert drv(0.0, 0.0) == 1.0


def test_square_corner_is_blinx1(drv):
    want = (math.sqrt(2) - 0.4) / 0.6
    assert abs(drv(1.0, 1.0) - want) < 1e-4
    assert abs(drv(-1.0, 1.0) - 1.690) < 1e-3


def test_part_way_past_the_circle(drv):
    length = math.hypot(1.0, 0.5)
    assert abs(drv(1.0, 0.5) - (length - 0.4) / 0.6) < 1e-4


def test_never_past_the_corner(drv):
    assert abs(drv(2.0, 2.0) - drv(1.0, 1.0)) < 1e-6


def test_mode_with_y_forced_to_zero(drv):
    # The 0.6 deadzone mode zeroes y before the clamp: L = |x| <= 1.
    assert drv(1.0, 0.0, 0.6) == 1.0


def test_nan_is_stock(drv):
    assert drv("nan", 1.0) == 1.0
    assert drv(1.0, 1.0, "nan") == 1.0


def test_no_deadzone(drv):
    # dz = 0: s is L itself, so the corner gives sqrt(2).
    assert abs(drv(1.0, 1.0, 0.0) - math.sqrt(2)) < 1e-5
    assert drv(1.0, 0.0, 0.0) == 1.0


def test_deadzone_of_one_or_more_is_stock(drv):
    # (L - dz) / (1 - dz) has no meaning there; the walk's own s is 0 or
    # negative, so the mod leaves it alone.
    assert drv(1.0, 1.0, 1.0) == 1.0
    assert drv(1.0, 1.0, 1.5) == 1.0


def test_just_past_the_circle(drv):
    # An SDL pad can report a little outside the circle: a small gain only.
    length = math.hypot(1.0, 0.01)
    got = drv(1.0, 0.01)
    assert got > 1.0
    assert abs(got - (length - 0.4) / 0.6) < 1e-5


def test_walk_constants_match_the_design():
    text = _read("src", "fdm_mod.c")
    design = _read("openspec", "changes", "b2-full-diagonal-movement", "design.md")
    for name, val in (
        ("RET_WALK", "0x0017C8FCu"),
        ("VA_CALL_POW", "0x0017C8F7u"),
        ("VA_MAX_READ", "0x0017D301u"),
        ("VA_PADS", "0x00ADC794u"),
        ("W_X", "0x18u"),
        ("W_Y", "0x38u"),
        ("W_DZ", "0x28u"),
        ("W_PAD", "0x20u"),
    ):
        assert re.search(rf"#define {name}\s+{val}\b", text), name
    logic = _read("src", "fdm_logic.h")
    assert re.search(r"#define FDM_PAD_SIZE\s+0x1E4u\b", logic)
    assert re.search(r"#define FDM_N_PADS\s+4u\b", logic)
    assert "return address is 0x17C8FC" in design
    assert "`+0x18`, `+0x38`, `+0x28`" in design
    assert "`[f+0x20]`" in design and "`[0xADC794]` + slot × 0x1E4" in design
    # The XBE guard's bytes: the call of pow and the table's one read.
    assert "0xE8, 0x60, 0x9E, 0x15, 0x00" in text
    assert "0xD8, 0x8B, 0x84, 0x0A, 0x45, 0x00" in text
    assert "`E8 60 9E 15 00`" in design and "`D8 8B 84 0A 45 00`" in design


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    m = re.search(r'X\(FDM,\s*CONFIG,\s*"RECOMP_FDM",\s*NULL,\s*"([^"]*)"', text)
    assert m and "mods.fdm.enable" in m.group(1)


def test_env_doc_rows():
    doc = _read("docs", "env.md")
    assert "| `RECOMP_FDM` | `RECOMP_FDM`" in doc
    assert '| `mods."fdm.enable"` |' in doc


# The player-facing texts, plain and ASCII only (the user, 2026-11-05).
HELP = (
    "Diagonals run up to 1.69x as fast as straight, as in BLiNX 1. Needs"
    " Square left stick (pads and keyboard)."
)
ABOUT = (
    "Stock BLiNX 2 caps diagonal speed at straight speed. This mod lifts"
    " the cap: diagonals run up to 1.69x as fast, as in BLiNX 1. Pads and"
    " the keyboard need Square left stick, below."
)
SQUARE_HELP = (
    "Pads and the keyboard need it for full diagonals. The same switch as Controls > Sticks."
)


def _square_macros(text):
    """The FDM_SQUARE_* texts for a toolkit with link settings (the first
    branch of the descriptor-version check)."""
    block = re.search(r"#if XBOX_MOD_DESC_VERSION >= 2\n(.*?)#else", text, re.S)
    assert block
    return dict(re.findall(r'#  define (FDM_SQUARE_\w+) "([^"]*)"', block.group(1)))


def test_descriptor():
    text = _read("src", "fdm_mod.c")
    m = re.search(r'\{ "enable", NULL, "RECOMP_FDM".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_ENUM" in m.group(0) and "XBOX_SET_ENABLE" in m.group(0)
    # Off by default: the setting's def field is 0.
    assert "XBOX_SET_ENABLE, 0," in m.group(0)
    assert '"Full Diagonal Movement"' in m.group(0)
    assert "Square left" in m.group(0)
    # The menu's tooltip holds 159 bytes; the full text is the About.
    help_text = "".join(re.findall(r'"([^"]*)"', m.group(0))[3:5])
    assert help_text == HELP
    assert len(help_text.encode()) <= 159 and help_text.isascii()
    macros = _square_macros(text)
    about = re.search(r'sizeof k_desc, "Full Diagonal Movement",(.*?)NULL, "1"', text, re.S)
    about = re.sub(r"\b(FDM_SQUARE_\w+)", lambda w: '"%s"' % macros[w.group(1)], about.group(1))
    about = "".join(re.findall(r'"([^"]*)"', about))
    assert about == ABOUT and about.isascii()
    row = re.search(r'"mods\.fdm\.status".*?\};', text, re.S)
    row_help = "".join(re.findall(r'"([^"]*)"', row.group(0))[2:])
    assert len(row_help.encode()) <= 159
    assert '{ "fdm", init, NULL, &k_desc' in text


def test_square_left_row():
    """The toolkit's Square left stick as a link row after Enabled: the
    same value as Controls > Sticks, with the item's own label."""
    text = _read("src", "fdm_mod.c")
    m = re.search(r'\[SET_SQUARE\] = \{ "square_left", "input\.pad_square_left".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_LINK" in m.group(0)
    # No env, aliases or label of its own: the item's.
    assert '"input.pad_square_left", NULL, NULL, NULL,' in m.group(0)
    help_text = "".join(re.findall(r'"([^"]*)"', m.group(0))[2:])
    assert help_text == SQUARE_HELP
    assert len(help_text.encode()) <= 159 and help_text.isascii()
    # Listed after Enabled, and only with a toolkit that has links.
    assert text.index("[SET_ENABLE] =") < m.start()
    guard = text.rfind("#ifdef FDM_SQUARE_ROW", 0, m.start())
    assert guard > text.index("[SET_ENABLE] =")
    macros = _square_macros(text)
    assert macros["FDM_SQUARE_HINT"] == "Turn on Square left stick above"
    assert '"%s", FDM_SQUARE_HINT' in text
    # The Status row's value column holds about 46 characters.
    assert len(macros["FDM_SQUARE_HINT"]) <= 46


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.fdm.enable") == "off"


def test_hook_slots():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        cfg = json.load(f)["mods"]
    for va in ("0x00176150", "0x002D675C"):
        assert va in mods["hook_functions"]
        assert va in cfg["hook_functions"]
    # pow returns its float in st0; ent_player_update returns none.
    assert "0x002D675C" in mods["st0"] and "0x002D675C" in cfg["st0"]
    assert "0x00176150" in mods["no_st0"] and "0x00176150" in cfg["no_st0"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
