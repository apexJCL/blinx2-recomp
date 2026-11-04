#!/usr/bin/env python3
"""Tests for the crystals mod, "BLiNX 1 crystals" (mods."crystals.enable",
openspec changes crystal-sets and crystals-rewrite).

Compiles a driver against src/crystals_logic.c with a model of the game's
pickup (tc_crystal_collect's count, its third-crystal grant into the
control's words and its gold payout when the control is full) and checks
the row's rules through cry_pickup_begin and cry_pickup_end: three of a
colour give the control and four give it twice, a mixed row empties at four
with nothing, a full control pays gold, the set's own words reach the
control, a pickup the game did not count leaves every span alone, a pickup
the game counts for another character (another team's included) goes to
that character's row, an undone pickup puts every span back, a toggle in
the middle of a pickup settles, the row's hearts light the stock hearts,
and clear empties the row. Then the slot icon choice (with the empty
fallback), the HUD quad (cry_quad) for slot icons and for the
heart, and the keys: the env rows, the docs/env.md rows, the descriptor,
the golden check's stock value and the hook slot.

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

# Every team's span, a model of the game's pickup over one of them, and the
# mod's begin and end around it. Commands, one per line on stdin:
#   pick T C CAP K... -1 : character C of team T picks crystals of colours K
#                     (word 0x100+i for the ith), every control capped at
#                     CAP and empty; prints one token per pickup: G
#                     (granted), $ (gold) or . (counted only), then the
#                     row's length, then for a G the control's three words;
#                     then the final row. A ! means end's verdict and the
#                     game's disagree, or end named someone else.
#   bounce          : the game counts nobody; prints end's result and
#                     same|changed for every span.
#   redirect T C    : character 0 of team 0 has two PAUSE crystals and the
#                     game counts a third for character C of team T instead;
#                     prints end's result, team, character, then both rows.
#   undo            : begin, a pickup, then undo; prints same|changed.
#   clear C         : a row of three, cleared; prints the row and words.
#   quad OWN X Y S  : the slot-icon template quad moved to (X, Y) and scaled
#                     by S, own_uv OWN; prints x y u v per corner.
#   hearts K... -1  : character 1 of team 0 picks crystals of colours K
#                     (cap 2); prints its RETRY count byte after each.
#   icon K L        : cry_icon for colour K (-1 empty), heart texture
#                     loaded L; prints empty|colour|heart.
#   settle A D      : a row of two, then a pickup begun (A 1, its end never
#                     run) or not (A 0) and the depth D; then the toggle's
#                     settle; prints its result, the depth, active and
#                     same|changed against the row before.
DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "crystals_logic.h"

static uint8_t spans[CRY_TEAMS][CRY_SPAN];
static uint8_t *const span[CRY_TEAMS] = { spans[0], spans[1], spans[2], spans[3] };
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

/* tc_crystal_collect's count for character c of team t: the word into slot
 * count[k], the count up; at three the control when it has room (the words
 * copied, count 0), else gold (count 2). Returns 1 grant, 2 gold, 0
 * counted. */
static int game_collect(int t, int c, int k, uint16_t w)
{
    uint8_t *s = span[t], *n = &s[c * CRY_COLOURS + k];

    wr16(s, CRY_WORD(c, k, *n), w);
    if (++*n < 3)
        return 0;
    if (held[k] < cap) {
        int i;

        held[k]++;
        for (i = 0; i < 3; i++)
            ctl[k][i] = rd16(s, CRY_WORD(c, k, i));
        *n = 0;
        return 1;
    }
    *n = 2;
    return 2;
}

static void row(int t, int c)
{
    int i, len = cry_row_len(span[t], c);

    printf(" [");
    for (i = 0; i < len; i++)
        printf("%s%d", i ? "," : "", cry_row_at(span[t], c, i));
    printf("]");
}

static void reset(void)
{
    memset(spans, 0, sizeof spans);
    memset(held, 0, sizeof held);
    memset(ctl, 0, sizeof ctl);
}

int main(void)
{
    static struct cry_pickup p;
    char cmd[16];

    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "pick")) {
            int t, c, k, i = 0;

            reset();
            if (scanf("%d %d %d", &t, &c, &cap) != 3)
                return 1;
            while (scanf("%d", &k) == 1 && k >= 0) {
                uint16_t w = (uint16_t)(0x100 + i++);
                int r, e, et, ec;

                cry_pickup_begin(&p, span, k, w);
                r = game_collect(t, c, k, w);
                e = cry_pickup_end(&p, span, &et, &ec);
                printf("%s%c%d", i > 1 ? " " : "", r == 1 ? 'G' : r == 2 ? '$' : '.',
                       cry_row_len(span[t], c));
                if (e != (r ? 2 : 1) || et != t || ec != c)
                    printf("!");
                if (r == 1)
                    printf("=%x/%x/%x", ctl[k][0], ctl[k][1], ctl[k][2]);
            }
            row(t, c);
            printf("\n");
        } else if (!strcmp(cmd, "bounce")) {
            uint8_t before[CRY_TEAMS][CRY_SPAN];
            int t, e, et, ec;

            reset();
            for (t = 0; t < CRY_TEAMS; t++) {
                cry_push(span[t], t % CRY_CHARS, 2, (uint16_t)(0x200 + t));
                cry_push(span[t], t % CRY_CHARS, 2, (uint16_t)(0x210 + t));
            }
            memcpy(before, spans, sizeof spans);
            cry_pickup_begin(&p, span, 2, 0x300);
            e = cry_pickup_end(&p, span, &et, &ec);
            printf("%d %d %d %s\n", e, et, ec, memcmp(before, spans, sizeof spans) ? "changed" : "same");
        } else if (!strcmp(cmd, "redirect")) {
            int t, c, r, e, et, ec;

            if (scanf("%d %d", &t, &c) != 2)
                return 1;
            reset();
            cap = 2;
            cry_push(span[0], 0, 0, 0x200);
            cry_push(span[0], 0, 0, 0x201);
            cry_pickup_begin(&p, span, 0, 0x300);
            r = game_collect(t, c, 0, 0x300);
            e = cry_pickup_end(&p, span, &et, &ec);
            printf("%d %d %d %d", r, e, et, ec);
            row(0, 0);
            row(t, c);
            printf("\n");
        } else if (!strcmp(cmd, "undo")) {
            uint8_t before[CRY_TEAMS][CRY_SPAN];

            reset();
            cap = 2;
            cry_push(span[1], 2, 4, 0x200);
            cry_push(span[1], 2, 4, 0x201);
            memcpy(before, spans, sizeof spans);
            cry_pickup_begin(&p, span, 4, 0x300);
            game_collect(1, 2, 4, 0x300);
            cry_pickup_undo(&p, span);
            printf("%s\n", memcmp(before, spans, sizeof spans) ? "changed" : "same");
        } else if (!strcmp(cmd, "clear")) {
            int c, i, words = 0;

            if (scanf("%d", &c) != 1)
                return 1;
            reset();
            for (i = 0; i < 3; i++)
                cry_push(span[0], c, i, (uint16_t)(0x400 + i));
            cry_clear(span[0], c);
            for (i = 0; i < CRY_ROW; i++)
                words |= rd16(span[0], CRY_WORD(c, 0, i));
            row(0, c);
            printf(" %d\n", words);
        } else if (!strcmp(cmd, "hearts")) {
            int k, i = 0;

            reset();
            cap = 2;
            while (scanf("%d", &k) == 1 && k >= 0) {
                int et, ec;

                cry_pickup_begin(&p, span, k, (uint16_t)(0x100 + i));
                game_collect(0, 1, k, (uint16_t)(0x100 + i));
                cry_pickup_end(&p, span, &et, &ec);
                printf("%s%d", i++ ? " " : "", span[0][1 * CRY_COLOURS + CRY_RETRY]);
            }
            printf("\n");
        } else if (!strcmp(cmd, "icon")) {
            static const char *const names[] = { "empty", "colour", "heart" };
            int k, l;

            if (scanf("%d %d", &k, &l) != 2)
                return 1;
            printf("%s\n", names[cry_icon(k, l)]);
        } else if (!strcmp(cmd, "settle")) {
            uint8_t before[CRY_TEAMS][CRY_SPAN];
            int a, depth, active, r;

            if (scanf("%d %d", &a, &depth) != 2)
                return 1;
            reset();
            cap = 2;
            cry_push(span[0], 0, 4, 0x200);
            cry_push(span[0], 0, 4, 0x201);
            memcpy(before, spans, sizeof spans);
            active = a;
            if (a) {
                cry_pickup_begin(&p, span, 4, 0x300);
                game_collect(0, 0, 4, 0x300);
            }
            r = cry_settle(&p, span, &depth, &active);
            printf("%d %d %d %s\n", r, depth, active, memcmp(before, spans, sizeof spans) ? "changed" : "same");
        } else if (!strcmp(cmd, "quad")) {
            /* A slot icon as the panel draws it: corners in the sprite
             * add's order (left top, left bottom, right top, right bottom)
             * over a 16x12 box at (100, 50), UVs a sub-rectangle of the
             * panel's texture. */
            static const float tpl[16] = {
                100, 50, 0.25f, 0.5f,  100, 62, 0.25f, 0.75f,
                116, 50, 0.5f, 0.5f,   116, 62, 0.5f, 0.75f,
            };
            float out[16], x, y, sc;
            int own, i;

            if (scanf("%d %f %f %f", &own, &x, &y, &sc) != 4)
                return 1;
            cry_quad(tpl, out, x, y, sc, own);
            for (i = 0; i < 4; i++)
                printf("%s%g %g %g %g", i ? " | " : "", out[i * 4], out[i * 4 + 1], out[i * 4 + 2],
                       out[i * 4 + 3]);
            printf("\n");
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
    assert drv("pick 0 0 2 0 0 0 -1") == ".1 .2 G3=100/101/102 [0,0,0]"


def test_four_give_it_twice_then_the_row_empties(drv):
    assert drv("pick 0 0 2 0 0 0 0 -1") == ".1 .2 G3=100/101/102 G0=101/102/103 []"


def test_three_among_four(drv):
    assert drv("pick 0 1 2 5 4 5 5 -1") == ".1 .2 .3 G0=100/102/103 []"
    assert drv("pick 0 2 2 4 3 3 3 -1") == ".1 .2 .3 G0=101/102/103 []"


def test_any_team_and_character(drv):
    # VS keeps one record per team; begin prepares every team's characters.
    for t in range(4):
        for c in range(3):
            assert drv(f"pick {t} {c} 2 1 1 1 -1") == ".1 .2 G3=100/101/102 [1,1,1]"


def test_mixed_row_empties_at_four_with_nothing(drv):
    assert drv("pick 0 0 2 0 4 5 0 -1") == ".1 .2 .3 .0 []"
    assert drv("pick 0 0 2 0 4 0 5 -1") == ".1 .2 .3 .0 []"


def test_rows_go_on_after_emptying(drv):
    assert drv("pick 0 0 2 1 2 3 4 1 1 1 -1") == ".1 .2 .3 .0 .1 .2 G3=104/105/106 [1,1,1]"


def test_heart_crystals_are_a_colour_like_the_rest(drv):
    # k3 is RETRY, the heart crystal: three in a row give a retry.
    assert drv("pick 0 0 2 3 3 3 -1") == ".1 .2 G3=100/101/102 [3,3,3]"


def test_row_hearts_light_the_stock_hearts(drv):
    # The stock lit hearts read the RETRY count byte (0x6DB27): the row's
    # hearts, at most two, go there; other colours leave it, and the row
    # emptying at four clears it.
    assert drv("hearts 3 0 3 3 3 -1") == "1 1 2 0 1"
    assert drv("hearts 3 3 3 3 -1") == "1 2 2 0"
    assert drv("hearts 0 4 5 -1") == "0 0 0"


def test_full_control_pays_gold(drv):
    # Cap 1: the first set grants, the second (the fourth crystal) pays.
    assert drv("pick 0 0 1 0 0 0 0 -1") == ".1 .2 G3=100/101/102 $0 []"
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


def test_uncounted_pickup_leaves_every_span(drv):
    assert drv("bounce") == "0 -1 -1 same"


def test_redirected_pickup_goes_to_the_counted_row(drv):
    # Character 0's two PAUSE crystals stay; the counted one starts a row.
    assert drv("redirect 0 1") == "0 1 0 1 [0,0] [0]"
    assert drv("redirect 3 2") == "0 1 3 2 [0,0] [0]"


def test_undo_puts_every_span_back(drv):
    # The mod switched off between pre and post.
    assert drv("undo") == "same"


def test_clear(drv):
    assert drv("clear 1") == "[] 0"


def test_toggle_mid_pickup_settles(drv):
    # Off between pre and post: the prepared spans go back, balanced.
    assert drv("settle 1 1") == "1 0 0 same"
    # On between pre and post: post ran alone (depth -1); only rebalance.
    assert drv("settle 0 -1") == "0 0 0 same"
    # Off and on in one frame: the second call repeats the state, and still
    # leaves the depth balanced.
    assert drv("settle 0 1") == "0 0 0 same"


def test_toggle_settles_before_the_repeat_check():
    # on_enable settles before it returns for a repeated state, so an off
    # and on in one frame cannot leave the depth at 1.
    text = _read("src", "crystals_mod.c")
    body = text[text.index("static void on_enable(") :]
    assert body.index("cry_settle(") < body.index("if (on == s_on)")


def test_slot_icon_choice(drv):
    assert drv("icon 0 1") == "colour"
    assert drv("icon 5 0") == "colour"
    assert drv("icon 3 1") == "heart"
    # The heart's texture not loaded yet: the empty slot, never a wrong
    # frame of the panel's texture (it has no RETRY icon).
    assert drv("icon 3 0") == "empty"
    assert drv("icon -1 1") == "empty"


def test_slot_icon_quad_keeps_its_uvs(drv):
    # Centre (108, 56) moves to (40, 20); scale 1 keeps the 16x12 box.
    assert drv("quad 0 40 20 1") == (
        "32 14 0.25 0.5 | 32 26 0.25 0.75 | 48 14 0.5 0.5 | 48 26 0.5 0.75"
    )


def test_quad_scales_about_its_centre(drv):
    assert drv("quad 0 40 20 0.5") == (
        "36 17 0.25 0.5 | 36 23 0.25 0.75 | 44 17 0.5 0.5 | 44 23 0.5 0.75"
    )


def test_heart_quad_takes_the_whole_texture(drv):
    # The gauge heart's own texture, as sub_0006B1F0 draws it at 0x6DB17:
    # u 0 left, v 0 top, whatever the slot icon's UVs were.
    assert drv("quad 1 40 20 1") == "32 14 0 0 | 32 26 0 1 | 48 14 1 0 | 48 26 1 1"


def test_heart_icon_is_the_gauge_heart():
    # The heart crystal has no icon in the panel's texture (no RETRY slot),
    # so the row borrows the heart drawn above the heart gauge: texture
    # pointer 0x418848, frame 3 (sub_0006B1F0, 0x6DB17).
    text = _read("src", "crystals_mod.c")
    assert re.search(r"#define\s+HEART_TEX\s+0x00418848u", text)
    assert re.search(r"#define\s+HEART_FRAME\s+3u?\b", text)
    # Loaded means frame 3's handle is set (sub_00037090 writes it at
    # frames + i*0x24 + 0x20), not only the static descriptor's pointer.
    assert re.search(r"#define\s+TEX_FRAME_SIZE\s+0x24u", text)
    assert re.search(r"#define\s+TEX_FRAME_HANDLE\s+0x20u", text)
    assert "HEART_FRAME * TEX_FRAME_SIZE + TEX_FRAME_HANDLE" in text


def test_player_facing_name():
    text = _read("src", "crystals_mod.c")
    assert '"BLiNX 1 crystals"' in text


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
