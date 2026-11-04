#!/usr/bin/env python3
"""Tests for src/glow.c, the weight maths behind fx.glow_intensity, and the
glow mod's keys (src/glow_mod.c, openspec change glow-mod).

Compiles a small driver against glow.c and checks the scaled weights: the
cube root (design D3 of openspec change glow-toggle), the 0xFF clamp, alpha
kept, and that nothing is active until glow_configure says so. Then checks
that the mod's settings keep the old keys and env rows, that docs/env.md and
config.default.toml name them, and that the golden check knows the stock
values.

  python3 scripts/test_glow.py
  uv run pytest scripts/test_glow.py

Skips (exit 0) when no C compiler is on PATH.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

# setting name -> (config key, env row or None, kind in the descriptor)
SETTINGS = {
    "enable": ('mods."glow.enable"', None, "XBOX_SET_ENUM"),
    "glow": ("fx.glow", "RECOMP_GLOW", "XBOX_SET_ENUM"),
    "intensity": ("fx.glow_intensity", "RECOMP_GLOW_INTENSITY", "XBOX_SET_FLOAT"),
}

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
            int off;
            double k;
            glow_configure(argv[i][1] == '1', atof(argv[i + 1]));
            glow_settings(&off, &k);
            printf("active %d %g (%d %g)\n", glow_active(), glow_factor(), off, k);
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
    out = _run("c0", 1, "c0", 0.5, "c1", 1, "c0", 0, "c1", 0.5, "c0", 1)
    assert out == [
        "active 0",
        "active 0 1 (0 1)",
        "active 1 0.5 (0 0.5)",
        "active 1 0 (1 1)",
        "active 1 0 (0 0)",
        "active 1 0 (1 0.5)",
        "active 0 1 (0 1)",
    ]


# ---- the mod's keys -------------------------------------------------------------


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_descriptor_keeps_the_old_keys():
    text = _read("src", "glow_mod.c")
    for name, (key, env, kind) in SETTINGS.items():
        keyed = "NULL" if key.startswith("mods.") else f'"{key}"'
        envd = "NULL" if env is None else f'"{env}"'
        pat = r'\{ "' + name + r'", ' + re.escape(keyed) + ", " + re.escape(envd) + ","
        m = re.search(pat + r"(.*?)\},", text, re.S)
        assert m, f"{name}: not declared with key {keyed} and env {envd}"
        assert kind in m.group(1), f"{name}: not {kind}"
        assert "ENHANCE_LIVE" in m.group(1), f"{name}: not live"
    assert re.search(r'"glow", init, NULL, &k_desc', text)


def test_env_rows_are_config_tier():
    text = _read("src", "env", "recomp_env_game.h")
    for key, env, _ in SETTINGS.values():
        if env is None:
            continue
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert key in m.group(1), f"{env}: its row does not name {key}"


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for key, env, _ in SETTINGS.values():
        assert f"| `{key}` |" in doc, f"{key}: no settings row in docs/env.md"
        if env:
            assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"


def test_defaults_file_is_stock():
    with open(os.path.join(ROOT, "packaging", "config.default.toml"), "rb") as f:
        d = tomllib.load(f)
    assert d["fx"] == {"glow": "on", "glow_intensity": 1.0}
    assert d["mods"].get("glow.enable", "on") == "on"


def test_golden_knows_the_stock_values():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock["fx.glow"] == "on"
    assert float(stock["fx.glow_intensity"]) == 1.0
    assert stock["mods.glow.enable"] == "on"


if __name__ == "__main__":
    for t in (
        test_identity_and_zero,
        test_design_table,
        test_clamp_and_alpha,
        test_configure,
        test_descriptor_keeps_the_old_keys,
        test_env_rows_are_config_tier,
        test_env_doc_has_every_key,
        test_defaults_file_is_stock,
        test_golden_knows_the_stock_values,
    ):
        t()
    print("ok")
    sys.exit(0)
