#!/usr/bin/env python3
"""Tests for the debug_menu mod (mods."debug_menu.*", openspec change
debug-menu-mod).

Compiles a driver against src/debug_menu_logic.c and checks the rules: the
menu opens only from PRESS START, the open writes (players, pad,
both cursors, then the state last), and the cursor skip past unsafe rows in the
direction the cursor moved, wrapping. Then checks the keys: each setting
and the control have a CONFIG env row and a docs/env.md row, the
descriptor names them, and the golden check knows the switch's stock value.

  python3 scripts/test_debug_menu.py
  uv run pytest scripts/test_debug_menu.py

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
N = 15

# setting name -> (env row, kind in the descriptor)
SETTINGS = {
    "enable": ("RECOMP_DEBUG_MENU", "XBOX_SET_ENUM"),
}
CONTROL_ENV = "RECOMP_DEBUG_MENU_KEY"

# "p <scene> <ptr> <state>" prints at_press_start and in_menu; "f <prev>
# <now> <mask>" prints the fixed cursor; "s <cur> <step> <mask>" the cursor
# written before the handler's step; "g <prev> <now> <step> <mask>" the
# cursor the fallback writes; "d <up> <down>" the pad step; "o"
# prints the open writes;
# "u" prints the build's unsafe mask.
DRIVER = r"""
#include <stdio.h>
#include <string.h>
#include "debug_menu_logic.h"

int main(void)
{
    char cmd[8];
    while (scanf("%7s", cmd) == 1) {
        if (!strcmp(cmd, "p")) {
            unsigned c, p, s;
            scanf("%x %x %x", &c, &p, &s);
            printf("%d %d\n", dbgm_at_press_start(c, p, s), dbgm_in_menu(c, p, s));
        } else if (!strcmp(cmd, "s")) {
            int a, b;
            unsigned m;
            scanf("%d %d %x", &a, &b, &m);
            printf("%d\n", dbgm_cursor_pre(a, b, m));
        } else if (!strcmp(cmd, "d")) {
            int u, d;
            scanf("%d %d", &u, &d);
            printf("%d\n", dbgm_pad_step(u, d));
        } else if (!strcmp(cmd, "f")) {
            int a, b;
            unsigned m;
            scanf("%d %d %x", &a, &b, &m);
            printf("%d\n", dbgm_cursor_fix(a, b, m));
        } else if (!strcmp(cmd, "g")) {
            int a, b, st;
            unsigned m;
            scanf("%d %d %d %x", &a, &b, &st, &m);
            printf("%d\n", dbgm_cursor_guard(a, b, st, m));
        } else if (!strcmp(cmd, "o")) {
            struct dbgm_poke w[DBGM_OPEN_POKES];
            int i;
            dbgm_open_pokes(w);
            for (i = 0; i < DBGM_OPEN_POKES; i++)
                printf("%s%X=%X", i ? " " : "", w[i].va, w[i].value);
            printf("\n");
        } else if (!strcmp(cmd, "u")) {
            printf("%X\n", dbgm_unsafe);
        }
        fflush(stdout);
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
    subprocess.run(
        [
            cc,
            "-std=c11",
            "-Wall",
            "-Werror",
            "-I",
            SRC,
            c,
            os.path.join(SRC, "debug_menu_logic.c"),
            "-o",
            exe,
        ],
        check=True,
    )

    def run(cmds):
        out = subprocess.run(
            [exe], input="\n".join(cmds) + "\n", capture_output=True, text=True, check=True
        )
        return out.stdout.split("\n")[:-1]

    yield run
    shutil.rmtree(d)


def test_opens_only_from_press_start(drv):
    # Scene 1 inited (0x81): the title runs.
    assert drv(
        [
            "p 81 5EB620 0",
            "p 81 5EB620 1",
            "p 81 5EB620 B",
            "p 81 0 0",
            "p 81 5EB621 0",
            "p 9C 5EB620 0",
        ]
    ) == ["1 0", "0 1", "0 0", "0 0", "0 0", "1 0"]


def test_boot_and_intro_are_not_press_start(drv):
    # Boot sets the pointer with the state 0 before the title's init has run
    # (scene 1 without 0x80) or while another scene plays the intro movies.
    assert drv(
        ["p 1 5EB620 0", "p 0 5EB620 0", "p 82 5EB620 0", "p 181 5EB620 0", "p 1 5EB620 1"]
    ) == [
        "0 0",
        "0 0",
        "0 0",
        "0 0",
        "0 0",
    ]


def test_open_writes_the_state_last(drv):
    # Players, pad, both cursors, then the state.
    assert drv(["o"]) == ["B22E3C=1 AE7A10=0 5EB630=0 5EB638=0 5EB620=1"]


def test_pad_step(drv):
    assert drv(["d 1 0", "d 0 1", "d 1 1", "d 0 0"]) == ["-1", "1", "0", "0"]


def test_pre_step_lands_past_unsafe_rows(drv):
    mask = (1 << 9) | (1 << 11) | (1 << 13) | (1 << 14)
    # Down from 8 onto MODEL_EDIT: written 9, the handler steps to 10.
    # Down from 10 onto GARAGE: 11, the handler steps to 12.
    # Up from 0 wraps onto THEATER, ENDING: 13, the handler steps to 12.
    # Up from 12 onto GARAGE: 11, the handler steps to 10.
    # Down from 12 onto ENDING, THEATER: 14, the handler wraps to 0.
    assert drv(
        [
            f"s 8 1 {mask:x}",
            f"s 10 1 {mask:x}",
            f"s 0 -1 {mask:x}",
            f"s 12 -1 {mask:x}",
            f"s 12 1 {mask:x}",
        ]
    ) == ["9", "11", "13", "11", "14"]


def test_pre_step_leaves_safe_steps_alone(drv):
    mask = (1 << 9) | (1 << 11) | (1 << 13) | (1 << 14)
    assert drv([f"s 0 1 {mask:x}", f"s 8 0 {mask:x}", f"s 7 1 {mask:x}", f"s 20 1 {mask:x}"]) == [
        "0",
        "8",
        "7",
        "20",
    ]


def test_guard_steps_past_the_fixed_row(drv):
    mask = (1 << 9) | (1 << 11) | (1 << 13) | (1 << 14)
    # Left on 9 by an outside write, Down this poll: the fix is 10, but the
    # handler steps after the mod, so it writes 11 and the step lands on 12.
    # Left on 11, Up: the fix is 10, the step from 10 would land on 9, so it
    # writes 9 and the step lands on 8. No step: just the fix. A safe row
    # with a step onto an unsafe one gets the pre-shift.
    assert drv(
        [
            f"g 8 9 1 {mask:x}",
            f"g 12 11 -1 {mask:x}",
            f"g 8 9 0 {mask:x}",
            f"g 7 8 1 {mask:x}",
        ]
    ) == ["11", "9", "10", "9"]


def test_safe_rows_are_left_alone(drv):
    mask = 1 << 9
    assert drv([f"f 7 8 {mask:x}", f"f 10 10 {mask:x}", "f 3 4 0"]) == ["8", "10", "4"]


def test_skip_follows_the_direction(drv):
    mask = (1 << 9) | (1 << 10)
    assert drv([f"f 8 9 {mask:x}", f"f 11 10 {mask:x}"]) == ["11", "8"]


def test_skip_wraps_at_both_ends(drv):
    first, last = 1 << 0, 1 << (N - 1)
    assert drv([f"f 13 14 {last:x}", f"f 1 0 {first:x}", f"f 0 14 {last:x}"]) == ["0", "14", "13"]


def test_all_unsafe_or_out_of_range_is_left(drv):
    full = (1 << N) - 1
    assert drv([f"f 0 1 {full:x}", "f 0 20 ffff", "f 0 -1 ffff"]) == ["1", "20", "-1"]


def test_row_zero_is_never_unsafe(drv):
    # 1P_MISSION(NORMAL) leads to the stage select: the mod's point.
    assert not int(drv(["u"])[0], 16) & 1


def test_unsafe_rows_are_the_measured_ones(drv):
    # MODEL_EDIT, GARAGE, ENDING, THEATER hang on the loading screen.
    assert int(drv(["u"])[0], 16) == (1 << 9) | (1 << 11) | (1 << 13) | (1 << 14)


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows_are_config_tier():
    text = _read("src", "env", "recomp_env_game.h")
    for name, (env, _) in SETTINGS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert f"mods.debug_menu.{name}" in m.group(1), f"{env}: its row does not name the key"
    m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + CONTROL_ENV + r'",\s*NULL,\s*"([^"]*)"', text)
    assert m and "debug_menu.open" in m.group(1)


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for name, (env, _) in SETTINGS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f'`mods."debug_menu.{name}"`' in doc, f"debug_menu.{name}: not in docs/env.md"
    assert f"| `{CONTROL_ENV}` | `{CONTROL_ENV}`" in doc


def test_descriptor_declares_each_setting():
    text = _read("src", "debug_menu.c")
    for name, (env, kind) in SETTINGS.items():
        m = re.search(r'\{ "' + name + r'", NULL, "' + env + r'".*?\}', text, re.S)
        assert m, f"{name}: no descriptor row with env {env}"
        assert kind in m.group(0), f"{name}: not {kind}"
    assert "XBOX_SET_ENABLE" in re.search(r'\{ "enable".*?\}', text, re.S).group(0)
    assert re.search(r'\{ "open",.*?XBOX_CTL_ACTION, NULL, NULL, "' + CONTROL_ENV + '"', text, re.S)
    assert '{ "debug_menu", init, NULL, &k_desc' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.debug_menu.enable") == "off"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
