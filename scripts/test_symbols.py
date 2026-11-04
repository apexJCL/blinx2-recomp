#!/usr/bin/env python3
"""Checks config/symbols.toml, the game's symbol map (openspec change
entity-system-spike, Part A).

Every entry has an address (or, for a field of a heap struct, a struct and an
offset), a unique name with a known subsystem prefix, a valid kind and a
source. Entries stay sorted by address so branches that add symbols merge
without conflicts. The file also stays in the TOML subset the Ghidra import
script (scripts/ghidra/ImportSymbolMap.java) parses by hand.

The CLI makes each function name gen's identifier ([pipeline] symbols,
openspec change gen-names), so no name may collide in C: not a keyword, not
a libc, POSIX or Windows CRT name, not an identifier in cat's sources or an
extern one in the toolkit's, not another function's name. Code outside
src/recomp_manual.c must not name a mapped function by its sub_ symbol:
only the manual file pins sub_ names (design D2).

  uv run pytest scripts/test_symbols.py
  SYMBOLS_TOML=other.toml uv run pytest scripts/test_symbols.py
"""

import glob
import json
import os
import re
import sys

import pytest

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
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


# ── C collisions (openspec change gen-names, design D6) ──────────────────

C_KEYWORDS = set(
    """
auto break case char const continue default do double else enum extern float
for goto if inline int long register restrict return short signed sizeof static
struct switch typedef union unsigned void volatile while bool true false
nullptr alignas alignof static_assert thread_local typeof class new delete this
namespace template typename operator public private protected virtual friend
using try catch throw
""".split()
)
# Comments, strings and character literals, blanked before looking for
# identifiers.
NOISE = re.compile(r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.S)
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
STATIC = re.compile(r"\bstatic\b[^;{(=]*?\b([A-Za-z_][A-Za-z0-9_]*)\s*[(\[=;]")
SUB = re.compile(r"\bsub_([0-9A-Fa-f]{8})(?:_gen)?\b")
GEN = os.path.join(ROOT, "src", "recomp", "gen")
MANUAL = os.path.join(ROOT, "src", "recomp_manual.c")


def code(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return NOISE.sub(" ", f.read())


def sources(*roots, exts=(".c", ".h", ".cpp", ".m", ".mm", ".inc")):
    for root in roots:
        for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
            if p.endswith(exts) and not p.startswith(GEN + os.sep):
                yield p


def toolkit():
    # The toolkit checkout next to cat (or vendored), not the one game.toml
    # pins, and test_no_reserved_names adds the host libc's exports: a
    # result can differ between hosts and toolkit branches.
    for d in (os.path.join(ROOT, "external", "xboxrecomp"), os.path.join(ROOT, "..", "xboxrecomp")):
        if os.path.isdir(os.path.join(d, "src")):
            return d
    return None


def gen_functions(entries):
    return {e["name"]: e for e in entries if e["kind"] == "function" and e.get("in_gen", True)}


def test_no_reserved_names(entries):
    sys.path.insert(0, HERE)
    import host_reserved_names as hr

    reserved = C_KEYWORDS | hr.POSIX_BASELINE | hr.WINDOWS_BASELINE | hr.host_libc_exports()
    tk = toolkit()
    if tk:
        sys.path.insert(0, os.path.join(tk, "tools", "ghidra_naming"))
        try:
            import merge_names

            reserved |= merge_names.RESERVED
        except ImportError:
            pass
    hits = sorted(e["name"] for e in entries if e["name"] in reserved)
    assert not hits, "names reserved in C or a host C library: %s" % ", ".join(hits)


def test_no_clash_with_cat_sources(entries):
    # A mod's own function or global by the same name would clash at link
    # time, or shadow the gen function in that file.
    funcs = gen_functions(entries)
    hits = {}
    for p in sources(os.path.join(ROOT, "src")):
        for name in funcs.keys() & set(IDENT.findall(code(p))):
            hits.setdefault(name, os.path.relpath(p, ROOT))
    assert not hits, "function names already used in cat's sources: %s" % hits


def test_no_clash_with_toolkit(entries):
    tk = toolkit()
    if not tk:
        pytest.skip("no toolkit checkout (external/xboxrecomp or ../xboxrecomp)")
    funcs = gen_functions(entries)
    hits = {}
    for p in sources(*(os.path.join(tk, d) for d in ("src", "include", "templates"))):
        text = code(p)
        names = set(IDENT.findall(text))
        # A static name in a .c file stays there, and that file never sees
        # gen's. A header's statics (recomp_types.h's static inline helpers)
        # land in every gen file that includes it, so they still clash.
        if p.endswith(".c"):
            names -= set(STATIC.findall(text))
        for name in funcs.keys() & names:
            hits.setdefault(name, os.path.relpath(p, tk))
    assert not hits, "function names the toolkit already uses: %s" % hits


def test_no_clash_with_other_functions(entries):
    path = os.path.join(ROOT, "analysis", "disasm", "functions.json")
    if not os.path.exists(path):
        pytest.skip("no analysis/disasm/functions.json (run analyze)")
    with open(path) as f:
        starts = {e["name"]: int(e["start"], 16) for e in json.load(f)}
    hits = sorted(
        "%s (0x%08X, map 0x%08X)" % (n, starts[n], e["addr"])
        for n, e in gen_functions(entries).items()
        if n in starts and starts[n] != e["addr"]
    )
    assert not hits, "names another function already has: %s" % ", ".join(hits)


def test_sub_references_only_in_manual(entries):
    # recomp pins to sub_ only the names src/recomp_manual.c mentions; a
    # mapped function named sub_ anywhere else would not link once gen calls
    # it by its map name. Move the reference there or call it by address.
    mapped = {e["addr"]: e["name"] for e in gen_functions(entries).values()}
    hits = []
    for p in sources(os.path.join(ROOT, "src")):
        if os.path.samefile(p, MANUAL):
            continue
        for m in SUB.finditer(code(p)):
            va = int(m.group(1), 16)
            if va in mapped:
                hits.append("%s: %s (%s)" % (os.path.relpath(p, ROOT), m.group(0), mapped[va]))
    assert not hits, "sub_ references outside src/recomp_manual.c: %s" % ", ".join(sorted(hits))
