#!/usr/bin/env python3
"""Tests for src/glow.c, the weight maths behind fx.glow_intensity.

Compiles a small driver against glow.c and checks the scaled weights: the
cube root (design D3 of openspec change glow-toggle), the 0xFF clamp, alpha
kept, and that nothing is active until glow_configure says so.

  python3 scripts/test_glow.py
  uv run pytest scripts/test_glow.py

Skips (exit 0) when no C compiler is on PATH.
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")

DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include "glow.h"
int main(int argc, char **argv)
{
    int i;
    printf("active %d\n", glow_active());
    for (i = 1; i + 1 < argc; i += 2) {
        if (argv[i][0] == 'c') {          /* c<off> k: configure */
            glow_configure(argv[i][1] == '1', atof(argv[i + 1]));
            printf("active %d %g\n", glow_active(), glow_factor());
        } else {
            printf("%08X\n", glow_weight((uint32_t)strtoul(argv[i], NULL, 16),
                                         atof(argv[i + 1])));
        }
    }
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _run(*args):
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
                "-I",
                SRC,
                "-o",
                exe,
                c,
                os.path.join(SRC, "glow.c"),
                "-lm",
            ],
            check=True,
        )
        out = subprocess.run(
            [exe, *map(str, args)], check=True, capture_output=True, text=True
        ).stdout
    return out.splitlines()


def _weights(pairs):
    flat = [x for w, k in pairs for x in (f"{w:08X}", k)]
    return [int(x, 16) for x in _run(*flat)[1:]]


def test_identity_and_zero():
    if not _cc():
        print("skip: no C compiler")
        return
    got = _weights(
        [(0x404040, 1.0), (0x383838, 1.0), (0x404040, 0.0), (0x80404040, 0.0), (0x404040, -1)]
    )
    assert got == [0x404040, 0x383838, 0, 0x80000000, 0]


def test_design_table():
    """The bytes design D3 lists for the game's four weights."""
    if not _cc():
        print("skip: no C compiler")
        return
    ws = [0x383838, 0x404040, 0x484848, 0x505050]
    half = _weights([(w, 0.5) for w in ws])
    double = _weights([(w, 2.0) for w in ws])
    assert [g & 0xFF for g in half] == [0x2C, 0x33, 0x39, 0x3F]
    assert [g & 0xFF for g in double] == [0x47, 0x51, 0x5B, 0x65]
    # R = G = B in, R = G = B out.
    assert all(g == (g & 0xFF) * 0x010101 for g in half + double)


def test_clamp_and_alpha():
    if not _cc():
        print("skip: no C compiler")
        return
    assert _weights([(0xF0F0F0, 2.0), (0x80404040, 2.0), (0x102030, 2.0)]) == [
        0xFFFFFF,
        0x80515151,
        0x14283C,
    ]


def test_configure():
    if not _cc():
        print("skip: no C compiler")
        return
    out = _run("c0", 1, "c0", 0.5, "c1", 1, "c0", 1)
    assert out == ["active 0", "active 0 1", "active 1 0.5", "active 1 0", "active 0 1"]


if __name__ == "__main__":
    for t in (test_identity_and_zero, test_design_table, test_clamp_and_alpha, test_configure):
        t()
    print("ok")
    sys.exit(0)
