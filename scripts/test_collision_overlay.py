#!/usr/bin/env python3
"""Tests for the collision overlay mod (mods."collision.enable", openspec
change collision-overlay).

Compiles a driver against src/collision_logic.c and checks what the overlay
computes from the game's bake: the normal, the flatness bands, the sliver
rule, the shade and the colour scale; the crease and open edges of a small
mesh, per class; the stage key; and the octree walk on a synthetic guest
image, whose every pointer is checked so a bake in progress yields fewer
triangles, never a bad read. Then the
env rows, the docs/env.md rows, the descriptor, the golden check's stock
value, the hook slots and the glue in main.c and recomp_manual.c.

  python3 scripts/test_collision_overlay.py
  uv run pytest scripts/test_collision_overlay.py

The C tests skip when no C compiler is on PATH. The bands, colours, light
and constants are the Godot collision view's, read from the CLI's
extract/collision.py; those tests skip when no CLI checkout is found.
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

# Commands, one per line on stdin:
#   normal V0 V1 V2   : col_normal; prints ok and n.
#   flat NX NY NZ     : col_flatness_deg and its band.
#   band DEG          : col_band.
#   sliver V0 V1 V2   : col_sliver.
#   shade NX NY NZ    : col_shade.
#   scale RGB S       : col_scale_rgb (RGB in hex).
#   tri V0 V1 V2 CLS  : appends a baked record (class in hex) to the guest
#                       image and bumps the triangle count.
#   count N           : sets the triangle count.
#   load              : col_stage_load; prints n, creases, opens, then each
#                       triangle's ok, band and edge bits.
#   key               : col_stage_key.
#   node I C H        : node I with centre C and half-size H; the node
#                       count becomes at least I + 1.
#   kid I K J         : node I's child K points at node J.
#   rawkid I K HEX    : node I's child K is the raw pointer HEX.
#   ref I T           : prepends a reference cell for triangle T to node I.
#   rawref I HEX NEXT : prepends a cell whose triangle pointer is HEX.
#   refs N            : sets the reference count.
#   nodes N           : sets the node count.
#   query C R STAMP   : col_query; prints the sorted indices.
DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "collision_logic.h"

#ifdef DIRTY_HEAP
/* Built with -Dmalloc=dirty_malloc: every malloc in collision_logic.c
 * returns a block filled with 0xAA, as a reused heap block can be. */
#undef malloc
void *malloc(size_t n);         /* stdlib.h declared dirty_malloc */

void *dirty_malloc(size_t n)
{
    void *p = malloc(n);

    if (p)
        memset(p, 0xAA, n);
    return p;
}
#endif

static uint8_t *mem;
static struct col_stage st;
static uint32_t mark[COL_TRI_MAX];
static uint32_t ntri, nnode, nref;

static void rd3(float v[3])
{
    if (scanf("%f %f %f", &v[0], &v[1], &v[2]) != 3)
        exit(1);
}

static void w32(uint32_t va, uint32_t v) { memcpy(mem + va, &v, 4); }
static uint32_t r32(uint32_t va) { uint32_t v; memcpy(&v, mem + va, 4); return v; }
static void wf(uint32_t va, float v) { memcpy(mem + va, &v, 4); }

static int cmp(const void *a, const void *b) { return *(const int *)a - *(const int *)b; }

static void push_ref(uint32_t node, uint32_t tri_ptr)
{
    uint32_t cell = COL_REF_BUF + nref++ * COL_REF_SIZE;
    uint32_t na = COL_NODE_BUF + node * COL_NODE_SIZE;

    w32(cell, tri_ptr);
    w32(cell + 4, r32(na + COL_NODE_HEAD));
    w32(na + COL_NODE_HEAD, cell);
    w32(na + COL_NODE_NREF, r32(na + COL_NODE_NREF) + 1);
    w32(COL_REF_COUNT, nref);
}

int main(void)
{
    char cmd[32];

    mem = calloc(1, COL_MEM_END);
    if (!mem)
        return 1;
    while (scanf("%31s", cmd) == 1) {
        if (!strcmp(cmd, "normal")) {
            float v[3][3], n[3];
            int ok;
            rd3(v[0]); rd3(v[1]); rd3(v[2]);
            ok = col_normal(v, n);
            printf("%d %.4f %.4f %.4f\n", ok, n[0], n[1], n[2]);
        } else if (!strcmp(cmd, "flat")) {
            float n[3], d;
            rd3(n);
            d = col_flatness_deg(n);
            printf("%.4f %d\n", d, col_band(d));
        } else if (!strcmp(cmd, "band")) {
            float d;
            if (scanf("%f", &d) != 1) return 1;
            printf("%d\n", col_band(d));
        } else if (!strcmp(cmd, "sliver")) {
            float v[3][3];
            rd3(v[0]); rd3(v[1]); rd3(v[2]);
            printf("%d\n", col_sliver(v));
        } else if (!strcmp(cmd, "shade")) {
            float n[3];
            rd3(n);
            printf("%.4f\n", col_shade(n));
        } else if (!strcmp(cmd, "scale")) {
            unsigned rgb; float s;
            if (scanf("%x %f", &rgb, &s) != 2) return 1;
            printf("%06X\n", col_scale_rgb(rgb, s));
        } else if (!strcmp(cmd, "tri")) {
            float v[3][3];
            unsigned cls;
            uint32_t rec = COL_TRI_BUF + ntri * COL_TRI_SIZE;
            int j, k;
            rd3(v[0]); rd3(v[1]); rd3(v[2]);
            if (scanf("%x", &cls) != 1) return 1;
            for (j = 0; j < 3; j++)
                for (k = 0; k < 3; k++)
                    wf(rec + 0x0C * (uint32_t)j + 4 * (uint32_t)k, v[j][k]);
            w32(rec + 0x24, 0xFF000000u | cls);
            w32(COL_TRI_COUNT, ++ntri);
            printf("%u\n", ntri - 1);
        } else if (!strcmp(cmd, "count")) {
            unsigned n;
            if (scanf("%u", &n) != 1) return 1;
            w32(COL_TRI_COUNT, n);
        } else if (!strcmp(cmd, "load")) {
            int i;
            col_stage_load(&st, mem);
            printf("%d %d %d", st.n, st.creases, st.opens);
            for (i = 0; i < st.n; i++)
                printf(" %d:%d:%d", st.t[i].ok, st.t[i].band, st.t[i].edges);
            printf("\n");
        } else if (!strcmp(cmd, "key")) {
            printf("%08X\n", col_stage_key(mem));
        } else if (!strcmp(cmd, "node")) {
            unsigned i; float c[3], h;
            uint32_t na;
            if (scanf("%u", &i) != 1) return 1;
            rd3(c);
            if (scanf("%f", &h) != 1) return 1;
            na = COL_NODE_BUF + i * COL_NODE_SIZE;
            wf(na + COL_NODE_CENTRE, c[0]);
            wf(na + COL_NODE_CENTRE + 4, c[1]);
            wf(na + COL_NODE_CENTRE + 8, c[2]);
            wf(na + COL_NODE_HALF, h);
            if (i + 1 > nnode)
                nnode = i + 1;
            w32(COL_NODE_COUNT, nnode);
        } else if (!strcmp(cmd, "kid") || !strcmp(cmd, "rawkid")) {
            unsigned i, k, j;
            int raw = cmd[0] == 'r';
            if (scanf(raw ? "%u %u %x" : "%u %u %u", &i, &k, &j) != 3) return 1;
            w32(COL_NODE_BUF + i * COL_NODE_SIZE + COL_NODE_KIDS + 4 * k,
                raw ? j : COL_NODE_BUF + j * COL_NODE_SIZE);
        } else if (!strcmp(cmd, "ref")) {
            unsigned i, t;
            if (scanf("%u %u", &i, &t) != 2) return 1;
            push_ref(i, COL_TRI_BUF + t * COL_TRI_SIZE);
        } else if (!strcmp(cmd, "rawref")) {
            unsigned i, p, next;
            if (scanf("%u %x %x", &i, &p, &next) != 3) return 1;
            push_ref(i, p);
            if (next != 0xFFFFFFFFu)
                w32(COL_REF_BUF + (nref - 1) * COL_REF_SIZE + 4, next);
        } else if (!strcmp(cmd, "refs")) {
            unsigned n;
            if (scanf("%u", &n) != 1) return 1;
            w32(COL_REF_COUNT, n);
        } else if (!strcmp(cmd, "nodes")) {
            unsigned n;
            if (scanf("%u", &n) != 1) return 1;
            w32(COL_NODE_COUNT, n);
        } else if (!strcmp(cmd, "query")) {
            float c[3], r;
            unsigned stamp;
            static int out[COL_TRI_MAX];
            int n, i;
            rd3(c);
            if (scanf("%f %u", &r, &stamp) != 2) return 1;
            n = col_query(&st, mem, c, r, mark, stamp, out, COL_TRI_MAX);
            qsort(out, (size_t)n, sizeof out[0], cmp);
            printf("%d:", n);
            for (i = 0; i < n; i++)
                printf(" %d", out[i]);
            printf("\n");
        } else {
            return 2;
        }
        fflush(stdout);
    }
    return 0;
}
"""


def build_driver(extra):
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
            *extra,
            "-I",
            SRC,
            c,
            os.path.join(SRC, "collision_logic.c"),
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

    return d, run


@pytest.fixture(scope="module")
def drv():
    d, run = build_driver([])
    yield run
    shutil.rmtree(d)


@pytest.fixture(scope="module")
def dirty_drv():
    d, run = build_driver(["-DDIRTY_HEAP", "-Dmalloc=dirty_malloc"])
    yield run
    shutil.rmtree(d)


def nums(s):
    return [float(x) for x in s.split()]


def test_normal(drv):
    ok, *n = nums(drv("normal 0 0 0  1 0 0  0 1 0"))
    assert ok == 1 and n == pytest.approx([0, 0, 1])
    ok, *n = nums(drv("normal 0 0 0  0 0 2  2 0 0"))
    assert ok == 1 and n == pytest.approx([0, 1, 0])


def test_degenerate_normal(drv):
    assert nums(drv("normal 0 0 0  1 1 1  2 2 2")) == [0, 0, 0, 0]
    assert nums(drv("normal 1 1 1  1 1 1  1 1 1")) == [0, 0, 0, 0]


def test_flatness_floor_wall_and_tilt(drv):
    assert nums(drv("flat 0 -1 0")) == [0, 0]
    assert nums(drv("flat 1 0 0")) == [0, 0]
    # 45 degrees: as far from flat as from vertical.
    deg, band = nums(drv("flat 0.70710678 0.70710678 0"))
    assert deg == pytest.approx(45, abs=1e-3) and band == 3


def godot_view():
    """The Godot collision view's constants, read from the CLI's
    extract/collision.py: the overlay must agree with it. None when no CLI
    checkout is found (XBOXRECOMP_CLI_DIR, or xboxrecomp-cli beside an
    ancestor of this repo)."""
    import ast

    dirs = [os.environ.get("XBOXRECOMP_CLI_DIR", "")]
    d = os.path.abspath(ROOT)
    while os.path.dirname(d) != d:
        d = os.path.dirname(d)
        dirs.append(os.path.join(d, "xboxrecomp-cli"))
    for cli in dirs:
        path = os.path.join(cli, "src", "xboxrecomp_cli", "extract", "collision.py")
        if cli and os.path.isfile(path):
            break
    else:
        return None
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name):
                try:
                    out[t.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return out


GODOT = godot_view()
needs_godot = pytest.mark.skipif(GODOT is None, reason="no xboxrecomp-cli checkout")


def band_cases():
    """Each band edge from the Godot view, just below and at it."""
    if GODOT is None:
        return []
    cases = [(0, 0)]
    for i, edge in enumerate(GODOT["FLAT_BANDS"]):
        cases += [(round(edge * 0.99, 4), i), (edge, i + 1)]
    return cases + [(45, len(GODOT["FLAT_BANDS"]))]


@needs_godot
@pytest.mark.parametrize("deg,band", band_cases())
def test_bands(drv, deg, band):
    assert drv(f"band {deg}") == str(band)


def c_source(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return f.read()


@needs_godot
def test_bands_names_and_colours_match_the_godot_view():
    src = c_source("collision_logic.c")
    deg = re.search(r"col_band_deg\[[^]]*\] = \{([^}]*)\}", src).group(1)
    names = re.search(r"col_band_name\[[^]]*\] = \{([^}]*)\}", src).group(1)
    rgb = re.search(r"col_band_rgb\[[^]]*\] = \{([^}]*)\}", src).group(1)
    assert tuple(float(x.rstrip("f")) for x in re.findall(r"[\d.]+f?", deg)) == tuple(
        GODOT["FLAT_BANDS"]
    )
    assert tuple(re.findall(r'"(\w+)"', names)) == tuple(GODOT["FLAT_NAMES"])
    assert tuple(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]+)u", rgb)) == tuple(
        GODOT["FLAT_COLOURS"]
    )


@needs_godot
@pytest.mark.parametrize(
    "macro,name",
    [
        ("COL_WELD", "WELD"),
        ("COL_CREASE_DEG", "CREASE_DEG"),
        ("COL_AMBIENT", "AMBIENT"),
        ("COL_ALPHA", "DEBUG_ALPHA"),
        ("COL_EDGE_DARKEN", "EDGE_DARKEN"),
    ],
)
def test_constants_match_the_godot_view(macro, name):
    m = re.search(rf"#define {macro}\s+([\d.e+-]+)f", c_source("collision_logic.h"))
    assert m and float(m.group(1)) == pytest.approx(GODOT[name])


def test_band_from_a_small_tilt(drv):
    import math

    a = math.radians(5)
    deg, band = nums(drv(f"flat {math.sin(a)} {math.cos(a)} 0"))
    assert deg == pytest.approx(5, abs=1e-3) and band == 2


def test_sliver(drv):
    assert drv("sliver 0 0 0  0.0005 0 0  5 5 5") == "1"
    assert drv("sliver 0 0 0  5 5 5  0 0.0009 0") == "1"
    assert drv("sliver 0 0 0  0.01 0 0  5 5 5") == "0"


@needs_godot
def test_shade(drv):
    # The Godot view's LIGHT normalised, y and z negated (its frame is the
    # bake's turned half a turn about X); AMBIENT + (1 - AMBIENT) |n.L|.
    import math

    lx, ly, lz = GODOT["LIGHT"]
    amb = GODOT["AMBIENT"]
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    up = amb + (1 - amb) * (ly / ln)
    assert float(drv("shade 0 1 0")) == pytest.approx(up, abs=1e-4)
    assert float(drv("shade 0 -1 0")) == pytest.approx(up, abs=1e-4)
    # A face edge-on to the light gets the ambient alone: n.L = 0.
    n = [ly, lx, 0]
    m = math.hypot(n[0], n[1])
    assert float(drv(f"shade {n[0] / m} {n[1] / m} 0")) == pytest.approx(amb, abs=1e-4)


def test_scale_rgb(drv):
    assert drv("scale BFBFBF 0.3") == "393939"
    assert drv("scale 00FFFF 1") == "00FFFF"
    assert drv("scale 808080 3") == "FFFFFF"
    assert drv("scale 102030 0") == "000000"


# Two triangles sharing the edge (0,0,0)-(10,0,0): a flat quad.
QUAD = [
    "tri 0 0 0  10 0 0  0 0 10  BFBFBF",
    "tri 10 0 0  0 0 0  10 0 -10  BFBFBF",
]


def test_flat_quad_has_only_open_edges(drv):
    out = drv(*QUAD, "load").split()
    n, creases, opens = map(int, out[:3])
    assert (n, creases, opens) == (2, 0, 4)
    # The shared edge is v0->v1 on both: bit 0 clear, the other two set.
    assert out[3:] == ["1:0:6", "1:0:6"]


def test_fold_is_a_crease(drv):
    # The second face folded to vertical along the shared edge.
    out = drv(
        "tri 0 0 0  10 0 0  0 0 10  BFBFBF",
        "tri 10 0 0  0 0 0  10 -10 0  BFBFBF",
        "load",
    ).split()
    assert list(map(int, out[:3])) == [2, 1, 4]
    # One of the two faces draws the crease (bit 0).
    assert sorted(int(x.split(":")[2]) & 1 for x in out[3:]) == [0, 1]


def test_shallow_fold_is_not_a_crease(drv):
    # 10 degrees off the plane: under CREASE_DEG.
    out = drv(
        "tri 0 0 0  10 0 0  0 0 10  BFBFBF",
        "tri 10 0 0  0 0 0  10 -1.7633 -10  BFBFBF",
        "load",
    ).split()
    assert list(map(int, out[:3])) == [2, 0, 4]


def test_edges_are_per_class(drv):
    # The same quad, the halves in two classes: the seam is open in each.
    out = drv(
        "tri 0 0 0  10 0 0  0 0 10  BFBFBF",
        "tri 10 0 0  0 0 0  10 0 -10  00FFFF",
        "load",
    ).split()
    assert list(map(int, out[:3])) == [2, 0, 6]
    assert out[3:] == ["1:0:7", "1:0:7"]


def test_weld_joins_close_corners(drv):
    out = drv(
        "tri 0 0 0  10 0 0  0 0 10  BFBFBF",
        "tri 10.0005 0 0  0 0 0.0005  10 0 -10  BFBFBF",
        "load",
    ).split()
    assert list(map(int, out[:3])) == [2, 0, 4]


def test_load_on_a_dirty_heap(dirty_drv):
    # the tracker item: the edge table came from malloc with only .a cleared, so on a
    # reused block (turning the mod on mid-game) an edge's face count was
    # garbage, its triangle never set, and the edge bits were written far
    # outside the stage. Loaded twice, as a stage change reloads it.
    out = dirty_drv(*QUAD, "load", "load").split()
    assert list(map(int, out[:3])) == [2, 0, 4]
    assert out[3:] == ["1:0:6", "1:0:6"]


def test_huge_corners_are_left_out_of_the_edges(drv):
    # Past the weld grid's int32 range the corner has no cell: the face is
    # drawn but gets no edges, and nothing overflows.
    out = drv("tri 0 0 0  3e7 0 0  0 0 3e7  BFBFBF", "load").split()
    assert list(map(int, out[:3])) == [1, 0, 0]
    assert out[3] == "1:0:0"


def test_degenerate_and_sliver_faces(drv):
    out = drv(
        "tri 0 0 0  1 1 1  2 2 2  BFBFBF",
        "tri 0 0 0  0.0005 0 0  0 0 10  BFBFBF",
        "load",
    ).split()
    assert out[3].startswith("0:")  # no normal: not drawn
    ok, band, _ = out[4].split(":")
    assert ok == "1" and band == "4"  # COL_SLIVER


def test_stage_key(drv):
    a = drv(*QUAD, "key")
    b = drv(*QUAD, "key")
    c = drv(QUAD[0], "tri 10 0 0  0 0 0  10 0 -11  BFBFBF", "key")
    d = drv(QUAD[0], QUAD[1].replace("BFBFBF", "00FFFF"), "key")
    assert a == b and a != c and a != d


def test_stage_key_counts_capped(drv):
    # A count past the buffer's capacity reads no further than the buffer.
    assert re.fullmatch(r"[0-9A-F]{8}", drv(*QUAD, "count 4000000000", "key"))


def grid():
    """Four floor triangles 100 apart along x, the root over all of them and
    two children, triangles 0-1 in child 1 and 2-3 in child 2."""
    tris = [f"tri {x} 0 0  {x + 10} 0 0  {x} 0 10  BFBFBF" for x in (0, 100, 200, 300)]
    return tris + [
        "load",
        "node 0  150 0 0  200",
        "node 1  50 0 0  100",
        "node 2  250 0 0  100",
        "kid 0 0 1",
        "kid 0 5 2",
        "ref 1 0",
        "ref 1 1",
        "ref 2 2",
        "ref 2 3",
    ]


def test_query_near(drv):
    assert drv(*grid(), "query 3 0 3  5 1") == "1: 0"
    assert drv(*grid(), "query 103 0 3  20 1") == "1: 1"


def test_query_radius(drv):
    assert drv(*grid(), "query 150 0 3  60 1") == "2: 1 2"
    assert drv(*grid(), "query 150 0 3  1000 1") == "4: 0 1 2 3"
    assert drv(*grid(), "query 150 0 500  20 1") == "0:"


def test_query_lists_once_per_stamp(drv):
    # Triangle 0 referenced by the root and child 1: listed once.
    out = drv(*grid(), "ref 0 0", "query 3 0 3  1000 7")
    assert out == "4: 0 1 2 3"


def test_query_same_stamp_again_lists_nothing(drv):
    out = drv(*grid(), "query 3 0 3  1000 7", "query 3 0 3  1000 7")
    assert out == "0:"


def test_query_bad_child_pointers(drv):
    # A misaligned child, one past the node count and one below the buffer
    # are skipped; the good child still answers.
    out = drv(
        *grid(),
        "rawkid 0 1 CAE8A9",
        f"rawkid 0 2 {0xCAE8A8 + 0x38 * 50:X}",
        "rawkid 0 3 1000",
        "query 150 0 3  1000 1",
    )
    assert out == "4: 0 1 2 3"


def test_query_bad_triangle_pointers(drv):
    out = drv(
        *grid(),
        "rawref 1 C21EA9 FFFFFFFF",  # misaligned
        f"rawref 1 {0xC21EA8 + 0x48 * 50:X} FFFFFFFF",  # past the count
        "rawref 1 0 FFFFFFFF",  # null
        "query 3 0 3  1000 1",
    )
    assert out == "4: 0 1 2 3"


def test_query_bad_cell_stops_the_list(drv):
    # A cell whose next is outside the cell buffer ends the list there: the
    # cells after it (pushed earlier) are not read.
    out = drv(*grid(), "rawref 2 0 1234", "query 250 0 3  1000 1")
    assert out == "2: 0 1"


def test_query_counts_cap_the_walk(drv):
    # A cycle back to the root stops at the node count.
    assert drv(*grid(), "kid 1 0 0", "query 3 0 3  1000 1") == "4: 0 1 2 3"
    # No nodes, or a triangle count that changed since the load: nothing.
    assert drv(*grid(), "nodes 0", "query 3 0 3  1000 1") == "0:"
    assert drv(*grid(), "count 3", "query 3 0 3  1000 1") == "0:"
    # A reference count of 0: no cell is valid.
    assert drv(*grid(), "refs 0", "query 3 0 3  1000 1") == "0:"


def test_query_bad_box(drv):
    # A NaN or zero half-size node is skipped with its subtree.
    assert drv(*grid(), "node 1  50 0 0  nan", "query 3 0 3  1000 1") == "2: 2 3"
    assert drv(*grid(), "node 0  150 0 0  -0.1", "query 3 0 3  1000 1") == "0:"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    m = re.search(r'X\(COLLISION,\s*CONFIG,\s*"RECOMP_COLLISION",\s*NULL,\s*"([^"]*)"', text)
    assert m and "mods.collision.enable" in m.group(1)
    m = re.search(
        r'X\(COLLISION_KEY,\s*CONFIG,\s*"RECOMP_COLLISION_KEY",\s*NULL,\s*"([^"]*)"', text
    )
    assert m and "collision.toggle" in m.group(1)


def test_env_doc_rows():
    doc = _read("docs", "env.md")
    assert "| `RECOMP_COLLISION` | `RECOMP_COLLISION`" in doc
    assert "| `RECOMP_COLLISION_KEY` | `RECOMP_COLLISION_KEY`" in doc
    assert '| `mods."collision.enable"` |' in doc
    assert "`collision.toggle`" in doc
    # The rows cite the descriptor's lines.
    src = _read("src", "collision_mod.c").split("\n")
    first = {"RECOMP_COLLISION": "[SET_ENABLE]", "RECOMP_COLLISION_KEY": "[CTL_TOGGLE]"}
    rows = re.findall(r"\| `(RECOMP_COLLISION\w*)` \|.*?`cat:src/collision_mod\.c:(\d+)`", doc)
    assert sorted(env for env, _ in rows) == sorted(first)
    for env, lnum in rows:
        assert first[env] in src[int(lnum) - 1]


def test_descriptor():
    text = _read("src", "collision_mod.c")
    m = re.search(r'\{ "enable", NULL, "RECOMP_COLLISION".*?\}', text, re.S)
    assert m
    assert "XBOX_SET_ENUM" in m.group(0) and "XBOX_SET_ENABLE" in m.group(0)
    # Off by default: the setting's def field is 0.
    assert "XBOX_SET_ENABLE, 0," in m.group(0)
    assert re.search(r'\{ "toggle",.*?"RECOMP_COLLISION_KEY" \}', text, re.S)
    assert '{ "F4", NULL }' in text
    assert '{ "collision", init, NULL, &k_desc' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.collision.enable") == "off"


def test_hook_slots():
    vas = ("0x001636C0", "0x00165630")
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        slots = json.load(f)["mods"]["hook_functions"]
    for va in vas:
        assert va in mods["hook_functions"]
        assert va in slots


def test_glue():
    main = _read("src", "main.c")
    assert '#include "collision_mod.h"' in main
    assert re.search(r"if \(collision_mod\(\)\)\s*mods\[nm\+\+\] = collision_mod\(\);", main)
    manual = _read("src", "recomp_manual.c")
    for fn in ("sub_000292A0", "sub_0021B1F0"):
        body = re.search(rf"\nvoid {fn}\(void\)\n\{{(.*?)\n\}}", manual, re.S)
        assert body and "collision_mod_view();" in body.group(1), fn
    cmake = _read("CMakeLists.txt")
    assert "src/collision_logic.c" in cmake and "src/collision_mod.c" in cmake


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
