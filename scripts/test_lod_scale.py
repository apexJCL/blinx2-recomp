#!/usr/bin/env python3
"""Tests for the lod mod (mods."lod.*", openspec change lod-scale).

Compiles a driver against src/lod_table.c and checks the threshold maths
(stock at 1x, the spike's 2x and 3x tables, the distance factor, follow_scale
off, the floor of 1, non-decreasing output), the stock-table check and the
table guard over a simulated table (the first write, a foreign change, the
restore, no write when nothing changed). Then checks the keys: each setting has a CONFIG env row and a docs/env.md row, the
descriptor names them, and the golden check knows the switch's stock value.

  python3 scripts/test_lod_scale.py
  uv run pytest scripts/test_lod_scale.py

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

STOCK = [(8, 0), (24, 1), (48, 2), (80, 3), (160, 4)]

# setting name -> (env row, kind in the descriptor)
SETTINGS = {
    "enable": ("RECOMP_LOD", "XBOX_SET_ENUM"),
    "follow_scale": ("RECOMP_LOD_FOLLOW_SCALE", "XBOX_SET_BOOL"),
    "distance": ("RECOMP_LOD_DISTANCE", "XBOX_SET_FLOAT"),
}

# "t <scale> <distance>" prints thresholds 1..4; "s <ten ints>" prints the
# stock check. The state machine runs over a simulated table: "i" resets the
# state and the table to stock, "W <scale> <distance>" steps to that scale
# (the mod on), "o" steps to stock (the mod off), "p <word> <value>" pokes a
# table word as another writer would; each step prints its result and the
# ten table words.
DRIVER = r"""
#include <stdio.h>
#include <string.h>
#include "lod_table.h"

static volatile uint32_t table[2 * LOD_TABLE_N];
static struct lod_state st;

static void step(const int32_t want[LOD_SCALED_N])
{
    int i, r = (int)lod_step(&st, table, want);

    printf("%d", r);
    for (i = 0; i < 2 * LOD_TABLE_N; i++)
        printf(" %d", (int32_t)table[i]);
    printf("\n");
}

int main(void)
{
    char cmd[8];
    while (scanf("%7s", cmd) == 1) {
        if (!strcmp(cmd, "i")) {
            int i;
            for (i = 0; i < LOD_TABLE_N; i++) {
                table[2 * i] = (uint32_t)lod_stock[i][0];
                table[2 * i + 1] = (uint32_t)lod_stock[i][1];
            }
            lod_state_init(&st);
            printf("ok\n");
        } else if (!strcmp(cmd, "W")) {
            unsigned s;
            double d;
            int32_t t[LOD_SCALED_N];
            scanf("%u %lf", &s, &d);
            lod_thresholds(s, d, t);
            step(t);
        } else if (!strcmp(cmd, "o")) {
            int32_t t[LOD_SCALED_N];
            lod_stock_thresholds(t);
            step(t);
        } else if (!strcmp(cmd, "p")) {
            int i, v;
            scanf("%d %d", &i, &v);
            table[i] = (uint32_t)v;
            printf("ok\n");
        } else if (!strcmp(cmd, "t")) {
            unsigned s;
            double d;
            int32_t t[LOD_SCALED_N];
            scanf("%u %lf", &s, &d);
            lod_thresholds(s, d, t);
            printf("%d %d %d %d\n", t[0], t[1], t[2], t[3]);
        } else if (!strcmp(cmd, "s")) {
            int32_t w[LOD_TABLE_N][2];
            int i;
            for (i = 0; i < LOD_TABLE_N; i++)
                scanf("%d %d", &w[i][0], &w[i][1]);
            printf("%d\n", lod_table_is_stock(w));
        }
        fflush(stdout);
    }
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _run(lines):
    """Run the driver over the command lines; one output line each."""
    if not _cc():
        pytest.skip("no C compiler")
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "t.c"), os.path.join(d, "t")
        with open(c, "w") as f:
            f.write(DRIVER)
        subprocess.run(
            [
                _cc(),
                "-std=c11",
                "-Wall",
                "-Werror",
                "-Wno-unused-result",
                "-I",
                SRC,
                "-o",
                exe,
                c,
                os.path.join(SRC, "lod_table.c"),
                "-lm",
            ],
            check=True,
        )
        out = subprocess.run(
            [exe], input="\n".join(lines) + "\n", check=True, capture_output=True, text=True
        ).stdout
    return out.splitlines()


def _t(scale, dist):
    return [int(x) for x in _run([f"t {scale} {dist}"])[0].split()]


# ---- thresholds ----------------------------------------------------------------


def test_one_x_is_stock():
    assert _t(1, 1.0) == [24, 48, 80, 160]


def test_spike_tables():
    # The values the tracker item poked and measured (+27% at 2x, +35% at 3x).
    assert _t(2, 1.0) == [12, 24, 40, 80]
    assert _t(3, 1.0) == [8, 16, 27, 53]
    assert _t(4, 1.0) == [6, 12, 20, 40]


def test_distance_multiplies_the_scale():
    assert _t(1, 2.0) == _t(2, 1.0)
    assert _t(2, 0.5) == [24, 48, 80, 160]
    assert _t(1, 0.5) == [48, 96, 160, 320]
    assert _t(2, 1.5) == _t(3, 1.0)


def test_bad_inputs_are_stock():
    # scale 0 and a non-positive or NaN distance count as 1.
    assert _t(0, 1.0) == [24, 48, 80, 160]
    assert _t(1, 0.0) == [24, 48, 80, 160]
    assert _t(1, -2.0) == [24, 48, 80, 160]
    assert _t(1, "nan") == [24, 48, 80, 160]


def test_floor_and_order():
    lines = [f"t {s} {d}" for s in (1, 2, 3, 4) for d in (0.5, 1, 2.25, 4)]
    lines.append("t 4 1000")
    for line in _run(lines):
        t = [int(x) for x in line.split()]
        assert min(t) >= 1, line
        assert t == sorted(t), line
    assert _t(4, 1000) == [1, 1, 1, 1]


def test_stock_check():
    flat = " ".join(f"{a} {b}" for a, b in STOCK)
    out = _run(
        [
            "s " + flat,
            "s " + flat.replace("24 1", "12 1"),
            "s " + flat.replace("160 4", "160 5"),
            "s " + flat.replace("8 0", "9 0", 1),
        ]
    )
    assert out == ["1", "0", "0", "0"]


# ---- the state machine (design D5) ------------------------------------------------

SAME, WROTE, DEAD, NOT_STOCK, FOREIGN = range(5)
STOCK_WORDS = [w for pair in STOCK for w in pair]


def _steps(cmds):
    """Run "i" then cmds; (result, words) for each step, None for a poke."""
    out = []
    for line in _run(["i"] + cmds)[1:]:
        if line == "ok":
            out.append(None)
            continue
        v = [int(x) for x in line.split()]
        out.append((v[0], v[1:]))
    return out


def _with(t):
    """The stock table words with thresholds 1..4 set to t."""
    w = list(STOCK_WORDS)
    for i, x in enumerate(t):
        w[2 * (i + 1)] = x
    return w


def test_off_never_writes():
    for r, w in _steps(["o", "o"]):
        assert (r, w) == (SAME, STOCK_WORDS)


def test_one_x_writes_nothing():
    assert _steps(["W 1 1"]) == [(SAME, STOCK_WORDS)]


def test_on_writes_once_then_holds():
    s = _steps(["W 2 1", "W 2 1", "W 2 1"])
    assert s[0] == (WROTE, _with([12, 24, 40, 80]))
    assert s[1:] == [(SAME, _with([12, 24, 40, 80]))] * 2


def test_scale_change_writes_once():
    s = _steps(["W 2 1", "W 3 1", "W 3 1"])
    assert [r for r, _ in s] == [WROTE, WROTE, SAME]
    assert s[2][1] == _with([8, 16, 27, 53])


def test_off_restores_stock():
    s = _steps(["W 3 1", "o", "o", "W 2 1"])
    assert [r for r, _ in s] == [WROTE, WROTE, SAME, WROTE]
    assert s[1][1] == STOCK_WORDS
    assert s[3][1] == _with([12, 24, 40, 80])


def test_threshold_0_and_levels_never_written():
    for _, w in _steps(["W 4 4", "W 1 0.5", "o"]):
        assert w[0] == 8
        assert w[1::2] == [0, 1, 2, 3, 4]


def test_not_stock_first_is_dead():
    # Another writer (a patch, a poke) got there first: never written,
    # restore included.
    s = _steps(["p 2 30", "W 2 1", "o", "W 3 1"])
    poked = _with([30, 48, 80, 160])
    assert s[1] == (NOT_STOCK, poked)
    assert s[2:] == [(DEAD, poked)] * 2


def test_not_stock_level_word_is_dead():
    s = _steps(["p 9 5", "W 2 1"])
    assert s[1][0] == NOT_STOCK
    assert s[1][1][2] == 24


def test_foreign_change_stops_without_restore():
    s = _steps(["W 2 1", "p 4 50", "W 3 1", "o"])
    left = _with([12, 50, 40, 80])
    assert s[0][0] == WROTE
    assert s[2] == (FOREIGN, left)
    assert s[3] == (DEAD, left)


def test_foreign_change_to_stock_is_still_foreign():
    # Even stock values put back by someone else end the mod's hold.
    s = _steps(["W 2 1", "p 2 24", "p 4 48", "p 6 80", "p 8 160", "W 3 1"])
    assert s[-1] == (FOREIGN, STOCK_WORDS)


# ---- keys ------------------------------------------------------------------------


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_table_matches_the_c_source():
    text = _read("src", "lod_table.c")
    pairs = [(int(a), int(b)) for a, b in re.findall(r"\{ (\d+), (\d+) \}", text)]
    assert pairs == STOCK
    assert "0x450B08u" in _read("src", "lod_table.h")


def test_env_rows_are_config_tier():
    text = _read("src", "env", "recomp_env_game.h")
    for name, (env, _) in SETTINGS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert f"mods.lod.{name}" in m.group(1), f"{env}: its row does not name the key"


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for name, (env, _) in SETTINGS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f'`mods."lod.{name}"`' in doc, f"lod.{name}: not in docs/env.md"


def test_descriptor_declares_each_setting():
    text = _read("src", "lod_scale.c")
    for name, (env, kind) in SETTINGS.items():
        m = re.search(r'\{ "' + name + r'", NULL, "' + env + r'".*?\}', text, re.S)
        assert m, f"{name}: no descriptor row with env {env}"
        assert kind in m.group(0), f"{name}: not {kind}"
    assert "XBOX_SET_ENABLE" in re.search(r'\{ "enable".*?\}', text, re.S).group(0)
    assert '{ "lod", init, shutdown_mod, &k_desc }' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    # The toolkit prints "[ENHANCE] mods.lod.enable=off" for the enable setting.
    assert stock.get("mods.lod.enable") == "off"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
