#!/usr/bin/env python3
"""Tests for the walls mod (mods."walls.enable", openspec change
collision-spike, task 1.7).

Compiles a driver against src/wall_logic.c with a model of the game's face
choice (sub_00165630 under one best value for the walk: the smallest signed
distance wins) and checks the thin-wall rule: a centre that came into a
thin wall through its near face is pushed back by that face where the game
takes the far one, a centre past half-way stays the game's, and a one-sided
platform jumped into from below, a floor stood on, a centre already inside
the wall a frame earlier, a skipped class and a projection outside the
entry face all keep the game's contact. Then the record layout, the pair
search the probe uses, the env rows, the docs/env.md rows, the descriptor,
the golden check's stock value and the hook slots.

  python3 scripts/test_walls.py
  uv run pytest scripts/test_walls.py

The C tests skip when no C compiler is on PATH.
"""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

# Commands, one per line on stdin:
#   tri V0 V1 V2 N CLS : a triangle (9 vertex floats, 3 normal floats, the
#                        class in hex); prints its index.
#   game C R          : the face the game takes for centre C (3 floats) and
#                       radius R: the smallest signed distance among the
#                       faces within R that hold the projection; -1 for none.
#   entry X C P R     : wall_entry_face for the game's face X, centre C and
#                       previous centre P (switches all off).
#   sw A B C D X C P R: the same with the four class switches.
#   pair F WMAX       : wall_pair for face F; prints b and w.
#   decide X C D R FL B0 B: wall_decide for the test that took X with centre
#                       C, the player's step D, radius R, flags FL (hex),
#                       the best before (B0) and after (B), push factor 1.1;
#                       prints K or R and y, or W, y, the written triangle,
#                       its best and push.
#   load HEX          : wall_tri_load on a 0x48-byte record; prints v0, n,
#                       centroid, radius and class.
DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wall_logic.h"

static struct wall_tri tris[64];
static int n;
static const uint32_t off[4];

static void rd3(float v[3])
{
    if (scanf("%f %f %f", &v[0], &v[1], &v[2]) != 3)
        exit(1);
}

static int game(const float c[3], float r, const uint32_t sw[4])
{
    int i, best = -1;
    float bs = 99999.0f;

    for (i = 0; i < n; i++) {
        float s = wall_s(&tris[i], c);

        if (wall_skipped(tris[i].cls, sw) || s > r || s < -r || s > bs ||
            !wall_inside(&tris[i], c, s))
            continue;
        best = i;
        bs = s;
    }
    return best;
}

int main(void)
{
    char cmd[16];

    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "tri")) {
            struct wall_tri *t = &tris[n];
            int i, j;

            for (i = 0; i < 3; i++)
                rd3(t->v[i]);
            rd3(t->n);
            if (scanf("%x", &t->cls) != 1)
                return 1;
            for (j = 0; j < 3; j++)
                t->centroid[j] = (t->v[0][j] + t->v[1][j] + t->v[2][j]) / 3.0f;
            t->radius = 1000.0f;
            printf("%d\n", n++);
        } else if (!strcmp(cmd, "game")) {
            float c[3], r;

            rd3(c);
            if (scanf("%f", &r) != 1)
                return 1;
            printf("%d\n", game(c, r, off));
        } else if (!strcmp(cmd, "entry") || !strcmp(cmd, "sw")) {
            uint32_t sw[4] = { 0, 0, 0, 0 };
            float c[3], p[3], r;
            int x;

            if (!strcmp(cmd, "sw") &&
                scanf("%u %u %u %u", &sw[0], &sw[1], &sw[2], &sw[3]) != 4)
                return 1;
            if (scanf("%d", &x) != 1)
                return 1;
            rd3(c);
            rd3(p);
            if (scanf("%f", &r) != 1)
                return 1;
            printf("%d\n", wall_entry_face(tris, n, x, c, p, r, sw));
        } else if (!strcmp(cmd, "pair")) {
            float wmax, w = -1;
            int f, b;

            if (scanf("%d %f", &f, &wmax) != 2)
                return 1;
            b = wall_pair(tris, n, f, wmax, off, &w);
            printf("%d %.3f\n", b, b >= 0 ? w : -1.0f);
        } else if (!strcmp(cmd, "decide")) {
            struct wall_contact o;
            float c[3], d[3], r, b0, b;
            unsigned fl;
            int x, y, k;

            if (scanf("%d", &x) != 1)
                return 1;
            rd3(c);
            rd3(d);
            if (scanf("%f %x %f %f", &r, &fl, &b0, &b) != 4)
                return 1;
            k = wall_decide(tris, n, x, c, d, r, fl, off, b0, b, 1.1f, &o, &y);
            if (k == WALL_WRITE)
                printf("W %d %d %.3f %.3f\n", y, o.tri, o.best, o.pen);
            else
                printf("%c %d\n", k == WALL_RESTORE ? 'R' : 'K', y);
        } else if (!strcmp(cmd, "load")) {
            uint8_t rec[WALL_TRI_SIZE];
            struct wall_tri t;
            unsigned i, b;

            for (i = 0; i < WALL_TRI_SIZE; i++) {
                if (scanf("%2x", &b) != 1)
                    return 1;
                rec[i] = (uint8_t)b;
            }
            wall_tri_load(&t, rec);
            printf("%g %g %g %g %g %g %g %g %g %g %06X\n", t.v[0][0], t.v[0][1], t.v[0][2],
                   t.n[0], t.n[1], t.n[2], t.centroid[0], t.centroid[1], t.centroid[2], t.radius,
                   t.cls);
        }
        fflush(stdout);
    }
    return 0;
}
"""

# A wall w thick in x: its near face F at x = 0 facing -x, its far face B
# at x = w facing +x; both large in y and z.
BIG = "{x} -50 -50  {x} 50 -50  {x} 0 50"


def wall(w, cls="808080"):
    return [
        f"tri {BIG.format(x=0)}  -1 0 0  {cls}",
        f"tri {BIG.format(x=w)}  1 0 0  808080",
    ]


# A floor facing up at y = 0.
FLOOR = "tri -50 0 -50  50 0 -50  0 0 50  0 1 0  808080"


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
            os.path.join(SRC, "wall_logic.c"),
            "-lm",
            "-o",
            exe,
        ],
        check=True,
    )

    def run(*lines):
        out = subprocess.run(
            [exe], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True
        )
        return out.stdout.split("\n")[-2]

    yield run
    shutil.rmtree(d)


def test_thin_wall_tunnels_in_the_game_model(drv):
    # w = 2, r = 2.95, centre 0.6 into F: B is deeper (-1.4 < -0.6).
    assert drv(*wall(2.0), "game 0.6 0 0 2.95") == "1"
    # Past half-way the game takes F, the face it came in by.
    assert drv(*wall(2.0), "game 1.4 0 0 2.95") == "0"


def test_entry_face_replaces_the_far_face(drv):
    # Came from in front of F (x = -0.5), the game took B: F is the contact.
    assert drv(*wall(2.0), "entry 1 0.6 0 0  -0.5 0 0  2.95") == "0"
    # A wall thicker than r but under 2r, centre jumped to w - r.
    assert drv(*wall(4.0), "game 1.5 0 0 2.95") == "1"
    assert drv(*wall(4.0), "entry 1 1.5 0 0  -1.0 0 0  2.95") == "0"


def test_game_contact_stands_or_mirrors(drv):
    # The game took F (came from its front): nothing to change.
    assert drv(*wall(2.0), "entry 0 1.4 0 0  -0.5 0 0  2.95") == "-1"
    # The centre was already inside the wall a frame earlier.
    assert drv(*wall(2.0), "entry 1 0.6 0 0  0.3 0 0  2.95") == "-1"
    # The same wall entered from the other side: the game takes F, and B,
    # the side it came in by, pushes it back.
    assert drv(*wall(2.0), "entry 0 1.4 0 0  2.5 0 0  2.95") == "1"


def test_platform_from_below_stays_stock(drv):
    # A one-sided floor, jumped into from below: no face the sphere entered
    # by, so the game's push up through it stands.
    assert drv(FLOOR, "game 0 -0.3 0 1.5") == "0"
    assert drv(FLOOR, "entry 0 0 -0.3 0  0 -1 0  1.5") == "-1"


def test_floor_stood_on_is_untouched(drv):
    # Centre above the floor: s > 0, the rule never looks.
    assert drv(FLOOR, "entry 0 0 1.0 0  0 1.2 0  1.5") == "-1"


def test_floor_does_not_win_over_a_penetrated_wall(drv):
    # A thin wall standing on a floor: the floor is in reach but faces
    # sideways to both faces (n . n = 0), so it is never the entry face.
    lines = [*wall(2.0), FLOOR]
    assert drv(*lines, "entry 1 0.6 1.0 0  -0.5 1.0 0  2.95") == "0"


def test_skipped_entry_face(drv):
    # F's class always skipped (0xFFFFFF): the game never sees it, nor does
    # the rule.
    assert drv(*wall(2.0, "FFFFFF"), "entry 1 0.6 0 0  -0.5 0 0  2.95") == "-1"
    # A switchable class: skipped only while its switch is set.
    lines = wall(2.0, "00FFFF")
    assert drv(*lines, "sw 0 0 0 0  1 0.6 0 0  -0.5 0 0  2.95") == "0"
    assert drv(*lines, "sw 0 0 0 1  1 0.6 0 0  -0.5 0 0  2.95") == "-1"


def test_projection_outside_the_entry_face(drv):
    # F is a small triangle away from the centre's projection.
    lines = [
        "tri 0 20 20  0 21 20  0 20 21  -1 0 0  808080",
        f"tri {BIG.format(x=2.0)}  1 0 0  808080",
    ]
    assert drv(*lines, "entry 1 0.6 0 0  -0.5 0 0  2.95") == "-1"


def test_beyond_the_radius(drv):
    # F more than r behind the centre is out of reach.
    assert drv(*wall(2.0), "entry 1 0.6 0 0  -0.5 0 0  0.5") == "-1"


# The game took B (s = -1.4) with the centre 0.6 into a 2-thick wall, the
# player having stepped 1.1 in from in front of F.
TOOK_B = "decide 1 0.6 0 0  1.1 0 0  2.95 7"


def test_decide_writes_the_entry_face(drv):
    # Nothing before: F's contact, s = -0.6, push (2.95 + 0.6) * 1.1.
    assert drv(*wall(2.0), f"{TOOK_B} 99999 -1.4") == "W 0 0 -0.600 3.905"


def test_decide_restores_a_better_earlier_contact(drv):
    # The walk held something deeper than F before B's test: it stands.
    assert drv(*wall(2.0), f"{TOOK_B} -1.0 -1.4") == "R 0"


def test_decide_tie_and_f_visited_first(drv):
    # F came first in the walk (best -0.6, F's own value): a tie keeps it,
    # as the game's strict comparison would.
    assert drv(*wall(2.0), f"{TOOK_B} -0.6 -1.4") == "R 0"


def test_decide_second_triangle_of_the_far_face(drv):
    # B is two triangles: after the first wrote F, the second takes again
    # with best -0.6 before it, and F's contact stays.
    lines = [*wall(2.0), f"tri {BIG.format(x=2.0)}  1 0 0  808080"]
    assert drv(*lines, f"{TOOK_B} 99999 -1.4") == "W 0 0 -0.600 3.905"
    assert drv(*lines, "decide 2 0.6 0 0  1.1 0 0  2.95 7 -0.6 -1.4") == "R 0"


def test_decide_keeps_vertex_and_edge_contacts(drv):
    # Not a face contact (best is not x's signed distance): untouched.
    assert drv(*wall(2.0), "decide 1 0.6 0 0  1.1 0 0  2.95 7 99999 0.3") == "K -1"
    # x at x = 1 facing +x, with an edge 0.1 from the centre's projection;
    # the entry face y at x = 2 facing -x, the centre 1.5 in front of it.
    # x's edge (distance 0.51) beats y's 1.5: the edge is the contact, as
    # the game would have had it without x's face.
    lines = [
        "tri 1 -0.1 -10  1 -0.1 10  1 10 0  1 0 0  808080",
        f"tri {BIG.format(x=2.0)}  -1 0 0  808080",
    ]
    took_x = "decide 0 0.5 0 0  0.2 0 0  2.95"
    assert drv(*lines, f"{took_x} 7 99999 -0.5") == "W 1 0 0.510 2.440"
    # Without the edge flag only y is left.
    assert drv(*lines, f"{took_x} 2 99999 -0.5") == "W 1 1 1.500 1.595"


def test_decide_ignores_a_warp(drv):
    # A step longer than 2r is a respawn or warp: no previous centre.
    assert drv(*wall(2.0), "decide 1 0.6 0 0  6.0 0 0  2.95 7 99999 -1.4") == "K -1"


def test_decide_degenerate_normals(drv):
    # A zero or NaN normal on x or on the would-be entry face: nothing.
    zero = [f"tri {BIG.format(x=0)}  0 0 0  808080", f"tri {BIG.format(x=2.0)}  1 0 0  808080"]
    assert drv(*zero, f"{TOOK_B} 99999 -1.4") == "K -1"
    nan = [f"tri {BIG.format(x=0)}  nan nan nan  808080", zero[1]]
    assert drv(*nan, f"{TOOK_B} 99999 -1.4") == "K -1"
    assert (
        drv(
            f"tri {BIG.format(x=0)}  -1 0 0  808080",
            f"tri {BIG.format(x=2.0)}  nan 0 0  808080",
            "entry 1 0.6 0 0  -0.5 0 0  2.95",
        )
        == "-1"
    )


def test_pairs(drv):
    assert drv(*wall(2.0), "pair 0 5.9") == "1 2.000"
    assert drv(*wall(8.0), "pair 0 5.9") == "-1 -1.000"
    # A floor is never a wall face.
    assert drv(FLOOR, "tri -50 -2 -50  50 -2 -50  0 -2 50  0 -1 0  808080", "pair 0 5.9") == (
        "-1 -1.000"
    )


def test_record_layout(drv):
    rec = bytearray(0x48)
    struct.pack_into("<9f", rec, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)
    struct.pack_into("<I", rec, 0x24, 0xAA00FFFF)
    struct.pack_into("<I", rec, 0x28, 77)
    struct.pack_into("<3f", rec, 0x2C, 0, 0, -1)
    struct.pack_into("<3f", rec, 0x38, 4, 5, 6)
    struct.pack_into("<f", rec, 0x44, 2.5)
    assert drv(f"load {rec.hex()}") == "1 2 3 0 0 -1 4 5 6 2.5 AA00FFFF"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    m = re.search(r'X\(WALLS,\s*CONFIG,\s*"RECOMP_WALLS",\s*NULL,\s*"([^"]*)"', text)
    assert m and "mods.walls.enable" in m.group(1)
    assert re.search(r'X\(WALLS_TRACE,\s*DEBUG,\s*"walls_trace"', text)


def test_env_doc_rows():
    doc = _read("docs", "env.md")
    assert "| `RECOMP_WALLS` | `RECOMP_WALLS`" in doc
    assert '| `mods."walls.enable"` |' in doc
    assert "| (none) | `walls_trace` |" in doc


def test_descriptor():
    text = _read("src", "walls_mod.c")
    m = re.search(r'\{ "enable", NULL, "RECOMP_WALLS".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_ENUM" in m.group(0) and "XBOX_SET_ENABLE" in m.group(0)
    # Off by default: the setting's def field is 0.
    assert "XBOX_SET_ENABLE, 0," in m.group(0)
    assert '{ "walls", init, NULL, &k_desc' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.walls.enable") == "off"


def test_hook_slots():
    vas = ("0x00163160", "0x001636C0", "0x00165630")
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        slots = json.load(f)["mods"]["hook_functions"]
    for va in vas:
        assert va in mods["hook_functions"]
        assert va in slots


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
