#!/usr/bin/env python3
"""Tests for the crystals mod (mods."crystals.enable", openspec change
crystal-sets).

Compiles a driver against src/crystals_logic.c with a model of the game's
pickup (tc_crystal_collect's count, its third-crystal grant into the
control's words and its gold payout when the control is full) and checks
the row's rules through the mod's pre and post steps: three of a colour
give the control and four give it twice, a mixed row empties at four with
nothing, a full control pays gold, the set's own words reach the control,
a pickup the game did not count leaves the row alone, the span is restored
around the pickup, and clear empties the row. Then checks the keys: the
env rows, the docs/env.md rows, the descriptor, the golden check's stock
value and the hook slot.

  python3 scripts/test_crystals.py
  uv run pytest scripts/test_crystals.py

The C tests skip when no C compiler is on PATH.
"""

import json
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

# One team's span, a model of the game's pickup over it, and the mod's pre
# (snapshot, cry_prepare) and post (cry_counted, restore, cry_push) around
# it. Commands, one per line on stdin:
#   pick C CAP K... : character C picks crystals of colours K (word 0x100+i
#                     for the ith), every control capped at CAP and empty;
#                     prints one token per pickup: G (granted), $ (gold) or
#                     . (counted only), then the row's length, then for a G
#                     the control's three words; then the final row.
#   skip C K        : a pickup the game counts for another character: the
#                     row and span stay as they were (prints same|changed).
#   clear C         : a row of three, cleared; prints the row and words.
DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "crystals_logic.h"

static uint8_t span[CRY_SPAN];
static int held[CRY_COLOURS], cap;
static uint16_t ctl[CRY_COLOURS][3];

static uint16_t rd16(const uint8_t *s, unsigned off)
{
    return (uint16_t)(s[off] | s[off + 1] << 8);
}

static void wr16(uint8_t *s, unsigned off, uint16_t v)
{
    s[off] = (uint8_t)v;
    s[off + 1] = (uint8_t)(v >> 8);
}

/* tc_crystal_collect's count for character c: the word into slot count[k],
 * the count up; at three the control when it has room (the words copied,
 * count 0), else gold (count 2). Returns 1 grant, 2 gold, 0 counted. */
static int game_collect(int c, int k, uint16_t w)
{
    uint8_t *n = &span[c * CRY_COLOURS + k];

    wr16(span, CRY_WORD(c, k, *n), w);
    if (++*n < 3)
        return 0;
    if (held[k] < cap) {
        int i;

        held[k]++;
        for (i = 0; i < 3; i++)
            ctl[k][i] = rd16(span, CRY_WORD(c, k, i));
        *n = 0;
        return 1;
    }
    *n = 2;
    return 2;
}

/* The mod around one pickup the game counts for character g. */
static int pickup(int c, int g, int k, uint16_t w)
{
    uint8_t snap[CRY_SPAN];
    int slot, r, before = held[k];

    memcpy(snap, span, sizeof span);
    slot = cry_prepare(snap, span, c, k, w);
    r = game_collect(g, k, w);
    if (cry_counted(span, c, k, slot, w)) {
        memcpy(span, snap, sizeof span);
        cry_push(span, c, k, w);
    } else {
        memcpy(span, snap, sizeof span);
    }
    (void)before;
    return r;
}

static void row(int c)
{
    int i, len = cry_row_len(span, c);

    printf(" [");
    for (i = 0; i < len; i++)
        printf("%s%d", i ? "," : "", cry_row_at(span, c, i));
    printf("]");
}

int main(void)
{
    char cmd[16];

    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "pick")) {
            int c, k, i = 0;

            memset(span, 0, sizeof span);
            memset(held, 0, sizeof held);
            memset(ctl, 0, sizeof ctl);
            if (scanf("%d %d", &c, &cap) != 2)
                return 1;
            while (scanf("%d", &k) == 1 && k >= 0) {
                int r = pickup(c, c, k, (uint16_t)(0x100 + i++));

                printf("%s%c%d", i > 1 ? " " : "", r == 1 ? 'G' : r == 2 ? '$' : '.',
                       cry_row_len(span, c));
                if (r == 1)
                    printf("=%x/%x/%x", ctl[k][0], ctl[k][1], ctl[k][2]);
            }
            row(c);
            printf("\n");
        } else if (!strcmp(cmd, "skip")) {
            uint8_t before[CRY_SPAN];
            int c, k;

            if (scanf("%d %d", &c, &k) != 2)
                return 1;
            memset(span, 0, sizeof span);
            cap = 2;
            cry_push(span, c, k, 0x200);
            cry_push(span, c, k, 0x201);
            memcpy(before, span, sizeof span);
            /* The game counts it for character c + 1 (another one's
             * count byte), never into c's poisoned slot. */
            pickup(c, (c + 1) % CRY_CHARS, k, 0x300);
            printf("%s\n", memcmp(before, span, sizeof span) ? "changed" : "same");
        } else if (!strcmp(cmd, "half")) {
            /* The mod toggles between pre and post: settle restores the
             * prepared span (was on) or only rebalances (was off). */
            uint8_t before[CRY_SPAN], snap[CRY_SPAN];
            int depth, active, was_on, r;

            if (scanf("%d", &was_on) != 1)
                return 1;
            memset(span, 0, sizeof span);
            cry_push(span, 0, 0, 0x200);
            cry_push(span, 0, 0, 0x201);
            memcpy(before, span, sizeof span);
            if (was_on) {
                memcpy(snap, span, sizeof span);
                cry_prepare(snap, span, 0, 0, 0x300);
                depth = 1;
                active = 1;
            } else {
                depth = -1;
                active = 0;
            }
            r = cry_settle(&depth, &active);
            if (r)
                memcpy(span, snap, sizeof span);
            printf("%d %d %d %s\n", r, depth, active,
                   memcmp(before, span, sizeof span) ? "changed" : "same");
        } else if (!strcmp(cmd, "clear")) {
            int c, i, words = 0;

            if (scanf("%d", &c) != 1)
                return 1;
            memset(span, 0, sizeof span);
            for (i = 0; i < 3; i++)
                cry_push(span, c, i, (uint16_t)(0x400 + i));
            cry_clear(span, c);
            for (i = 0; i < CRY_ROW; i++)
                words |= rd16(span, CRY_WORD(c, 0, i));
            row(c);
            printf(" %d\n", words);
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
            os.path.join(SRC, "crystals_logic.c"),
            "-o",
            exe,
        ],
        check=True,
    )

    def run(cmd):
        out = subprocess.run([exe], input=cmd + "\n", capture_output=True, text=True, check=True)
        return out.stdout.strip()

    yield run
    shutil.rmtree(d)


def test_three_give_the_control(drv):
    # The set's own words reach the control, in pickup order.
    assert drv("pick 0 2 0 0 0 -1") == ".1 .2 G3=100/101/102 [0,0,0]"


def test_four_give_it_twice_then_the_row_empties(drv):
    assert drv("pick 0 2 0 0 0 0 -1") == ".1 .2 G3=100/101/102 G0=101/102/103 []"


def test_three_among_four(drv):
    assert drv("pick 1 2 5 4 5 5 -1") == ".1 .2 .3 G0=100/102/103 []"
    assert drv("pick 2 2 4 3 3 3 -1") == ".1 .2 .3 G0=101/102/103 []"


def test_mixed_row_empties_at_four_with_nothing(drv):
    assert drv("pick 0 2 0 4 5 0 -1") == ".1 .2 .3 .0 []"
    assert drv("pick 0 2 0 4 0 5 -1") == ".1 .2 .3 .0 []"


def test_rows_go_on_after_emptying(drv):
    assert drv("pick 0 2 1 2 3 4 1 1 1 -1") == ".1 .2 .3 .0 .1 .2 G3=104/105/106 [1,1,1]"


def test_full_control_pays_gold(drv):
    # Cap 1: the first set grants, the second (the fourth crystal) pays.
    assert drv("pick 0 1 0 0 0 0 -1") == ".1 .2 G3=100/101/102 $0 []"
    # (A cap-0 control is no case: the game refuses that colour's crystal
    # before counting it, as the live proof showed for SLOW in stage 1.)


def test_colour_to_control_map():
    # The pickup's jump table at 0x8C4F8: k0 PAUSE 2, k1 REC 6, k2 FF 4,
    # k3 RETRY 1, k4 REW 5, k5 SLOW 3. The live proof caught an earlier
    # map that sent REW crystals to SLOW.
    text = _read("src", "crystals_logic.c")
    m = re.search(r"cry_k_to_id\[[^]]*\]\s*=\s*\{([^}]*)\}", text)
    assert m
    assert [int(x) for x in m.group(1).split(",")] == [2, 6, 4, 1, 5, 3]


def test_uncounted_pickup_leaves_the_row(drv):
    for c in range(3):
        assert drv(f"skip {c} 0") == "same"


def test_toggle_mid_pickup_settles(drv):
    # Off between pre and post: the prepared span is put back.
    assert drv("half 1") == "1 0 0 same"
    # On between pre and post: post ran alone (depth -1); only rebalance.
    assert drv("half 0") == "0 0 0 same"


def test_clear(drv):
    assert drv("clear 1") == "[] 0"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    m = re.search(r'X\(CRYSTALS,\s*CONFIG,\s*"RECOMP_CRYSTALS",\s*NULL,\s*"([^"]*)"', text)
    assert m and "mods.crystals.enable" in m.group(1)
    assert re.search(r'X\(CRYSTALS_PROOF,\s*DEBUG,\s*"crystals_proof"', text)


def test_env_doc_rows():
    doc = _read("docs", "env.md")
    assert "| `RECOMP_CRYSTALS` | `RECOMP_CRYSTALS`" in doc
    assert '| `mods."crystals.enable"` |' in doc
    assert "| (none) | `crystals_proof` |" in doc


def test_descriptor():
    text = _read("src", "crystals_mod.c")
    m = re.search(r'\{ "enable", NULL, "RECOMP_CRYSTALS".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_ENUM" in m.group(0) and "XBOX_SET_ENABLE" in m.group(0)
    assert '{ "crystals", init, NULL, &k_desc' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.crystals.enable") == "off"


def test_hook_slot():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    assert "0x0008BFD0" in mods["hook_functions"]
    assert "0x0008BFD0" in mods.get("no_st0", [])
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        assert "0x0008BFD0" in json.load(f)["mods"]["hook_functions"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
