#!/usr/bin/env python3
"""Checks config/symbols.toml, the game's symbol map (openspec change
entity-system-spike, Part A).

Every entry has an address (or, for a field of a heap struct, a struct and an
offset), a unique name with a known subsystem prefix, a valid kind and a
source. Entries stay sorted by address so branches that add symbols merge
without conflicts. The file also stays in the TOML subset the Ghidra import
script (scripts/ghidra/ImportSymbolMap.java) parses by hand.

  uv run pytest scripts/test_symbols.py
  SYMBOLS_TOML=other.toml uv run pytest scripts/test_symbols.py
"""

import os
import re

import pytest

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("SYMBOLS_TOML") or os.path.join(HERE, "..", "config", "symbols.toml")

KINDS = {"function", "global", "field", "label"}
PREFIXES = {
    "nj",  # Ninja library
    "lib",  # other XDK and C runtime library code
    "d3d",  # Direct3D and XGRAPHICS
    "pb",  # pushbuffer
    "snd",  # sound
    "sys",  # boot, main loop, threads, memory, files, saves
    "pad",  # input
    "fmv",  # movies
    "gfx",  # game-side rendering
    "cam",  # camera
    "stage",  # stage, area and frame loop
    "ent",  # entities
    "hud",  # HUD and 2D
    "menu",  # menus and shop
    "evt",  # events and cutscenes
    "tc",  # time control
}
KEYS = {
    "addr",
    "name",
    "kind",
    "struct",
    "offset",
    "note",
    "source",
    "conflict",
    "in_gen",
    "ghidra_only",
}
NAME = re.compile(r"^[a-z][a-z0-9]*_[a-z0-9_]+$")
# The lines the hand-written parser in ImportSymbolMap.java accepts.
LINE = re.compile(r'^(\[\[symbol\]\]|[a-z_]+ = (0x[0-9A-F]+|[0-9]+|true|false|"([^"\\]|\\.)*"))$')
# The XBE's mapped range (.text to the last section).
VA_LO, VA_HI = 0x00010000, 0x03040000


@pytest.fixture(scope="module")
def entries():
    with open(PATH, "rb") as f:
        data = tomllib.load(f)
    assert set(data) == {"symbol"}, "only [[symbol]] tables"
    return data["symbol"]


def test_parser_subset():
    with open(PATH, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            assert LINE.match(line), "line %d outside the import script's subset: %s" % (n, line)


def test_fields(entries):
    for e in entries:
        assert set(e) <= KEYS, "%s: unknown keys %s" % (e.get("name"), set(e) - KEYS)
        assert e.get("kind") in KINDS, "%s: kind %r" % (e.get("name"), e.get("kind"))
        assert e.get("source", "").strip(), "%s: no source" % e.get("name")
        if e["kind"] == "field":
            assert "struct" in e and "offset" in e, (
                "%s: a field needs struct and offset" % e["name"]
            )
        else:
            assert "addr" in e, "%s: no addr" % e["name"]
            assert "struct" not in e and "offset" not in e, e["name"]
        if "addr" in e:
            assert VA_LO <= e["addr"] < VA_HI, "%s: 0x%X outside the XBE" % (e["name"], e["addr"])
        if "in_gen" in e or "ghidra_only" in e:
            assert e["kind"] == "function", "%s: gen status on a non-function" % e["name"]


def test_names(entries):
    seen = set()
    for e in entries:
        name = e["name"]
        assert NAME.match(name), "bad name %r" % name
        assert name.split("_", 1)[0] in PREFIXES, "unknown prefix in %r" % name
        assert name not in seen, "duplicate name %r" % name
        seen.add(name)


def test_unique_addresses(entries):
    seen = {}
    for e in entries:
        key = e["addr"] if "addr" in e else (e["struct"], e["offset"])
        assert key not in seen, "%s and %s share %r" % (seen.get(key), e["name"], key)
        seen[key] = e["name"]


def test_sorted(entries):
    # Fixed addresses first, ascending; heap-struct fields after, by struct and offset.
    keys = [(0, e["addr"], "") if "addr" in e else (1, e["offset"], e["struct"]) for e in entries]
    fixed = [k for k in keys if k[0] == 0]
    heap = [(k[2], k[1]) for k in keys if k[0] == 1]
    assert keys == fixed + [(1, o, s) for s, o in heap], "fixed addresses before heap fields"
    assert fixed == sorted(fixed), "entries not sorted by address"
    assert heap == sorted(heap), "heap fields not sorted by struct and offset"


def test_field_addresses(entries):
    # A field of a struct that has a global entry of the same name sits at
    # that global's address plus its offset.
    bases = {e["name"]: e["addr"] for e in entries if e["kind"] == "global"}
    for e in entries:
        if e["kind"] == "field" and e["struct"] in bases:
            assert "addr" in e, "%s: %s is a global, so the field has an addr" % (
                e["name"],
                e["struct"],
            )
            assert e["addr"] == bases[e["struct"]] + e["offset"], "%s: 0x%X is not %s + 0x%X" % (
                e["name"],
                e["addr"],
                e["struct"],
                e["offset"],
            )
