#!/usr/bin/env python3
"""Tests for the hud mod's table, config/hud.toml (openspec change
hud-anchors, task 3.6).

The row test, read here with tomllib against the analysis
(analysis/disasm/: xrefs.json, functions.json and the listing):
- every site's ret_va follows a direct call to a function in game.toml's
  [mods] hook_functions or to a listed wrapper;
- no ret_va lies inside a wrapper's body: that names the wrapper's own call,
  which every caller shares (Time's font calls at 0x48691..0x48743 are
  inside sub_00048600), and a case feeds such a row and expects the failure;
- no duplicate sites, wrappers or groups; known kinds and groups; every
  group used (these structural checks need no analysis, so they run in the
  public checks too);
- a site of a moving kind (left, right, proportional, stretch) whose
  function is called from more than one function names every caller's
  sprite, so its row needs a note saying the callers were checked (the
  digit helper's add 0x18216 was such a row; the tracker item review S1);
- the spec's anchors (design and tasks 3.3) hold after a re-emit;
- the canvas and layout are what the 0.3 check found (the immediates
  0x43A00000 / 0x43700000 stored to the half sizes, and the .rdata 320.0 and
  240.0 the sprite helpers subtract).
Then `blinx2 hud-map emit --check`, the CLI's own check, when the CLI in use
has hud-map.

  python3 scripts/test_hud_table.py
  uv run pytest scripts/test_hud_table.py

The analysis is not in the repository: the tests that read it skip without
it (run `blinx2 analyze`).
"""

import bisect
import json
import os
import re
import struct
import subprocess
import sys

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
TABLE = os.path.join(ROOT, "config", "hud.toml")
GAME_TOML = os.path.join(ROOT, "game.toml")
DISASM = os.path.join(ROOT, "analysis", "disasm")
XBE = os.path.join(ROOT, "game_files", "default.xbe")

ADD = 0x00042190
KINDS = {"centre", "center", "left", "right", "proportional", "world", "stretch"}

_LINE_RE = re.compile(r"^  0x([0-9A-Fa-f]{8})  ([0-9a-fA-F]+)\s")


def load(path=TABLE):
    with open(path, "rb") as f:
        return tomllib.load(f)


def hooked():
    with open(GAME_TOML, "rb") as f:
        g = tomllib.load(f)
    return {int(v, 16) for v in g["mods"]["hook_functions"]}


class Analysis:
    """The calls' return addresses and the functions' ranges."""

    def __init__(self, disasm=DISASM):
        with open(os.path.join(disasm, "functions.json"), encoding="utf-8") as f:
            self.funcs = sorted((int(x["start"], 16), int(x["end"], 16)) for x in json.load(f))
        self.starts = [s for s, _ in self.funcs]
        with open(os.path.join(disasm, "xrefs.json"), encoding="utf-8") as f:
            self.calls = [
                (int(x["from"], 16), int(x["to"], 16)) for x in json.load(f) if x["type"] == "call"
            ]
        self.disasm = disasm
        self._len = None

    def lengths(self, froms):
        """Instruction length of each address in froms, from the listing."""
        want, out = set(froms), {}
        asm = os.path.join(self.disasm, "asm")
        for name in sorted(os.listdir(asm)):
            with open(os.path.join(asm, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = _LINE_RE.match(line)
                    if m and int(m.group(1), 16) in want:
                        out[int(m.group(1), 16)] = len(m.group(2)) // 2
            if len(out) == len(want):
                break
        return out

    def listing(self, vas):
        """The disassembly text of each address in vas, from the listing."""
        want, out = set(vas), {}
        asm = os.path.join(self.disasm, "asm")
        for name in sorted(os.listdir(asm)):
            with open(os.path.join(asm, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    m = _LINE_RE.match(line)
                    if m and int(m.group(1), 16) in want:
                        out[int(m.group(1), 16)] = " ".join(line[m.end() :].split())
            if len(out) == len(want):
                break
        return out

    def returns_to(self, targets):
        froms = [a for a, t in self.calls if t in targets]
        ln = self.lengths(froms)
        return {a + ln[a] for a in froms if a in ln}

    def containing(self, va):
        """The (start, end) of the function va lies in, or None."""
        i = bisect.bisect_right(self.starts, va) - 1
        if i >= 0 and self.funcs[i][0] <= va < self.funcs[i][1]:
            return self.funcs[i]
        return None

    def caller_functions(self, start):
        """The starts of the functions that call start directly."""
        out = set()
        for a, t in self.calls:
            if t == start:
                f = self.containing(a)
                out.add(f[0] if f else a)
        return out

    def body(self, va):
        i = bisect.bisect_left(self.starts, va)
        if i < len(self.funcs) and self.funcs[i][0] == va:
            return self.funcs[i]
        return None


MOVING = {"left", "right", "proportional", "stretch"}

# Functions with moving sites and more than one caller function, whose
# callers were checked (review S1). A new one needs a line here,
# or a note on its row naming the callers checked.
CHECKED_SHARED = {
    # cutscene dim, 5 callers: always the full canvas (-320,-240)..(320,240)
    # in 161 captured calls, so stretch is right for each one seen.
    0x000550C0: "dim",
    # loading bands: only the two loading paths (sub_0005E410, sub_00062FB0).
    0x0005EB30: "loading",
    # radar: only the two radar functions (sub_001A6640, sub_001A6910).
    0x001A63B0: "radar",
}


def kind_of(doc, site):
    if "kind" in site:
        return site["kind"]
    for g in doc.get("group", []):
        if g["name"] == site.get("group"):
            return g.get("kind")
    return None


def struct_errors(doc, hooked_vas):
    """The checks that need no analysis: one line per bad row."""
    errs = []
    wrappers = [w["va"] for w in doc.get("wrapper", [])]
    groups = {}
    for g in doc.get("group", []):
        if g["name"] in groups:
            errs.append("group %s: duplicate" % g["name"])
        if g.get("kind") not in KINDS:
            errs.append("group %s: unknown kind %r" % (g["name"], g.get("kind")))
        groups[g["name"]] = g
    if len(set(wrappers)) != len(wrappers):
        errs.append("wrapper: duplicate")
    for va in wrappers:
        if va not in hooked_vas:
            errs.append("wrapper 0x%08X: not in [mods] hook_functions" % va)
    seen, used = set(), set()
    for s in doc.get("site", []):
        ret = s["ret_va"]
        if ret in seen:
            errs.append("site 0x%08X: duplicate" % ret)
        seen.add(ret)
        if ("group" in s) == ("kind" in s):
            errs.append("site 0x%08X: needs a group or a kind, not both" % ret)
        if "group" in s:
            used.add(s["group"])
            if s["group"] not in groups:
                errs.append("site 0x%08X: unknown group %s" % (ret, s["group"]))
        if "kind" in s and s["kind"] not in KINDS:
            errs.append("site 0x%08X: unknown kind %r" % (ret, s["kind"]))
    for name in groups:
        if name not in used:
            errs.append("group %s: no site uses it" % name)
    return errs


def row_errors(doc, hooked_vas, an):
    """The row test: the structural checks, then the analysis ones."""
    errs = struct_errors(doc, hooked_vas)
    wrappers = [w["va"] for w in doc.get("wrapper", [])]
    rets = an.returns_to(hooked_vas | set(wrappers))
    bodies = [(va, an.body(va)) for va in wrappers]
    for s in doc.get("site", []):
        ret = s["ret_va"]
        if ret not in rets:
            errs.append("site 0x%08X: does not follow a call to a hooked function" % ret)
        for va, body in bodies:
            if body and body[0] <= ret < body[1]:
                errs.append("site 0x%08X: inside wrapper 0x%08X's body" % (ret, va))
        if kind_of(doc, s) in MOVING and "caller" not in s.get("note", ""):
            f = an.containing(ret)
            callers = an.caller_functions(f[0]) if f else set()
            if len(callers) > 1 and f[0] not in CHECKED_SHARED:
                errs.append(
                    "site 0x%08X: moves, and its function 0x%08X has %d caller functions"
                    " (a note naming the callers checked, or a wrapper)" % (ret, f[0], len(callers))
                )
    return errs


def test_canvas_and_layout():
    doc = load()
    assert doc["version"] == 1
    assert doc["canvas"] == {
        "w": 640,
        "h": 480,
        "origin": "centre",
        "y": "down",
        "view": [0, 0, 640, 480],
        "target": "frame",
        "source": "fixed",
    }
    assert doc["layout"] == {"stride": 16, "x_off": 0, "u_off": 8, "prim": 4}
    assert [w["va"] for w in doc["wrapper"]] == [
        0x177F0,
        0x178C0,
        0x18030,
        0x18250,
        0x17330,
        0x47A00,
        0x48600,
    ]


def test_hook_functions_cover_the_add_and_wrappers():
    vas = hooked()
    assert ADD in vas
    for w in load()["wrapper"]:
        assert w["va"] in vas


def test_rows_are_well_formed():
    assert struct_errors(load(), hooked()) == []


def test_bad_structure_fails():
    doc = load()
    first = doc["site"][0]["ret_va"]
    doc = dict(
        doc,
        group=list(doc["group"]) + [{"name": "unused", "kind": "left"}],
        site=list(doc["site"])
        + [
            {"ret_va": first, "kind": "left"},
            {"ret_va": 0x00012346, "kind": "sideways"},
            {"ret_va": 0x00012347, "group": "nosuch"},
            {"ret_va": 0x00012348, "group": "panel", "kind": "left"},
        ],
    )
    errs = "\n".join(struct_errors(doc, hooked()))
    assert "0x%08X: duplicate" % first in errs
    assert "unknown kind 'sideways'" in errs
    assert "unknown group nosuch" in errs
    assert "0x00012348: needs a group or a kind" in errs
    assert "group unused: no site uses it" in errs


# The anchors the spec fixes (design, tasks 3.3, the tracker item's element table),
# so a re-emit cannot drift them.
ANCHORS = {
    "panel": "left",
    "radar": "left",
    "counter": "right",
    "gold": "left",
    "goal": "right",
    "tc_legend": "right",
    "markers": "world",
    "loading": "stretch",
    "dialogue": "centre",
    "objectives": "centre",
    "time_control": "centre",
    "pause": "centre",
    "menu": "centre",
}


def test_spec_anchors():
    kinds = {g["name"]: g["kind"] for g in load()["group"]}
    for name, kind in ANCHORS.items():
        got = kinds.get(name)
        assert got == kind, "group %s is %r, the spec says %s" % (name, got, kind)


def test_gold_tally_keyed_at_its_callers():
    # S1: not the digit helper's own add, which its uncaptured callers share.
    # the tracker item: sub_00092370 draws the gold tally at the left above the
    # radar (cap-gold), not the item counter, so its digits, its text and
    # sub_00017410's icon all move left together.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    kinds = {g["name"]: g["kind"] for g in doc["group"]}
    assert 0x00018216 not in sites
    assert kinds["gold"] == "left"
    for ret in (
        0x000926C3,
        0x00092715,
        0x00092754,
        0x000174FB,
        0x000927FD,
        0x00092840,
        0x000928D3,
        0x00092942,
    ):
        assert sites[ret]["group"] == "gold"


def test_goal_message_and_counter_pieces():
    # the tracker item: the tutorial goal message (sub_000EB550, upper right) moves
    # right as one box with its slide-in; the gun icon and the
    # vacuumed-trash stack sit with the item counter in sub_0006B1F0.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    kinds = {g["name"]: g["kind"] for g in doc["group"]}
    assert kinds["goal"] == "right"
    for ret in (0x000EB65F, 0x000EB69D, 0x000EB6D3, 0x000EB80A):
        assert sites[ret]["group"] == "goal"
    for ret in (0x0006EE42, 0x0006ED21):
        assert sites[ret]["group"] == "counter"


def test_boss_bar_moves_right_as_one():
    # the tracker item: the boss health bar ("Scissor Demon", debug stage 0x1c) is
    # sub_00070A20's three adds and its one text call, upper right. Its
    # frame and fill are wider than the fallback's size cap and no listed
    # right group is drawn near it, so it needs rows. The rows also move
    # the bar of the uncaptured panel sub_0016F660 (caller 0x1706C6); see
    # the group's comment in hud.toml.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    kinds = {g["name"]: g["kind"] for g in doc["group"]}
    assert kinds["boss_bar"] == "right"
    for ret in (0x00070B75, 0x00070C9B, 0x00070D61, 0x00070E1A):
        assert sites[ret]["group"] == "boss_bar"


def test_team_block_moves_with_the_panel():
    # the tracker item: in team stages the "Team:" label and the teammate bars sit
    # under the stick panel. The fallback's join reached only the top bar
    # and tore the column, so every call of the block is a panel row.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    for ret in (0x0006DECC, 0x0006FC10, 0x0006FD35, 0x0006FDDD, 0x0006FE2A):
        assert sites[ret]["group"] == "panel"


def test_item_counter_big_digit_moves():
    # the tracker item: the big count digit's five outline passes reach the digits
    # helper through sub_00018250's tail jump, from sub_0006B1F0 at stage
    # play; both helpers are wrappers, so the rows sit at those calls and
    # move with the counter. sub_0006AB30's widget stays unlisted until a
    # capture places all its pieces.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    wrappers = {w["va"] for w in doc["wrapper"]}
    assert {0x00018030, 0x00018250} <= wrappers
    for ret in (
        0x0006E7D0,
        0x0006E7F3,
        0x0006E816,
        0x0006E839,
        0x0006E85C,
    ):
        assert sites[ret]["group"] == "counter"
    for ret in (0x0006ACE4, 0x0006AD03, 0x0006AD22, 0x0006AD45, 0x0006AD64, 0x000EC785):
        assert ret not in sites


# sub_00017330's callers: the time-control legend's two calls in
# sub_00072010 are keyed; the other 14 (one in SRCADV), the restart dialog
# among them, stay unlisted so they draw as they did before the helper
# became a wrapper.
LEGEND_CALLS = (0x0007235F, 0x0007258A)
# The "+" (0x3D95D0) that sub_00072010 draws through the text wrapper next
# to the second legend (four shadow copies, then the main one); unkeyed, it
# would stay put while the legend moves (review S1).
LEGEND_PLUS_CALLS = (0x00072730, 0x00072760, 0x0007278A, 0x000727B4, 0x000727DE)
SPRITE_2_OTHER_CALLS = (
    0x0001702E,
    0x00017078,
    0x000170AF,
    0x00017665,
    0x00062F14,
    0x00074888,
    0x00074AC8,
    0x001D148A,
    0x001D14C5,
    0x00201A7C,
    0x00201AC0,
    0x00201AF3,
    0x00201B30,
    0x0035E42C,
)


def test_time_control_legend_keyed_at_its_callers():
    # the tracker item: the legend (REW, PAUSE, ... at the upper right while a
    # control runs) is one quad from sub_00017330's add, which its other
    # callers share, so the helper is a wrapper and the rows sit at
    # sub_00072010's two calls, in a right group of their own.
    doc = load()
    sites = {s["ret_va"]: s for s in doc["site"]}
    kinds = {g["name"]: g["kind"] for g in doc["group"]}
    assert 0x00017330 in {w["va"] for w in doc["wrapper"]}
    assert 0x0001740A not in sites
    assert kinds["tc_legend"] == "right"
    for ret in LEGEND_CALLS + LEGEND_PLUS_CALLS:
        assert sites[ret]["group"] == "tc_legend"
    for ret in SPRITE_2_OTHER_CALLS:
        assert ret not in sites, "0x%08X: sub_00017330's caller is keyed" % ret


# sub_0006B1F0's lit heart crystals: a glow quad and the heart,
# one pair per crystal. Their x comes from the lives balls' base [esp+0x18]
# (stored at 0x6D666, added at 0x6D6BE for the lives and 0x6D92F for the
# hearts; test_hearts_are_every_add_of_the_heart_loop checks those three).
# Unkeyed, they stayed at 4:3 while their slots moved with the panel.
HEART_CALLS = (0x0006DA50, 0x0006DB1C)
LIVES_CALLS = (0x0006D7E1, 0x0006D8C9)


def test_heart_crystals_move_with_the_lives():
    sites = {s["ret_va"]: s for s in load()["site"]}
    for ret in HEART_CALLS + LIVES_CALLS:
        assert sites[ret]["group"] == "panel"


# sub_0006FF10's long-bar draws (GitHub #6). Past the default max
# hp the panel grows: 0x70347 stretches a strip of the frame over the extra
# length (drawn only when that length is above 0), and the pieces after it
# move right by it. 0x70A0E is the bar's hit flash, a red quad at the
# bar's end, drawn while the record's +0xAA timer runs. Unkeyed, both stayed
# at 4:3 while the rest of the panel moved at 16:9: the strip as a dark block
# past the end cap, and its gap under the bar's translucent green segments
# as a faded copy of the bar.
BAR_CALLS = (0x00070347, 0x00070A0E)
PANEL_FN = 0x0006FF10
PANEL_FN_END = 0x00070A16


def test_long_bar_pieces_move_with_the_panel():
    sites = {s["ret_va"]: s for s in load()["site"]}
    for ret in BAR_CALLS:
        assert sites[ret]["group"] == "panel"


needs_analysis = pytest.mark.skipif(
    not os.path.isfile(os.path.join(DISASM, "xrefs.json")), reason="no analysis: run analyze"
)


@needs_analysis
def test_rows_follow_hooked_calls():
    assert row_errors(load(), hooked(), Analysis()) == []


@needs_analysis
def test_counter_holds_no_gold_tally_site():
    # Review N3: sub_00092370 is the gold tally, so none of its
    # rows may stay behind in counter, which moves the other way.
    an = Analysis()
    stray = [
        "0x%08X" % s["ret_va"]
        for s in load()["site"]
        if s.get("group") == "counter" and (an.containing(s["ret_va"]) or (None,))[0] == 0x00092370
    ]
    assert not stray, "counter holds sub_00092370 sites: %s" % stray


@needs_analysis
def test_sprite_2_callers_are_the_ones_pinned():
    # The pinned lists cover every call of sub_00017330 the analysis knows,
    # so a caller found later fails here until someone decides its row.
    an = Analysis()
    assert an.returns_to({0x00017330}) == set(LEGEND_CALLS) | set(SPRITE_2_OTHER_CALLS)
    for ret in LEGEND_CALLS:
        assert an.containing(ret)[0] == 0x00072010


@needs_analysis
def test_legend_plus_is_every_text_call_of_the_legend():
    # Every text-wrapper call in the legend's gated block (0x72362, the
    # [0xAEB814] test, to its exit 0x72811) is the "+", so none of its draws
    # stays behind when the legend moves. The analysis runs sub_00072010 on
    # past 0x72811 into code that is not the legend, hence the bounds.
    an = Analysis()
    text = {r for r in an.returns_to({0x00047A00}) if 0x00072362 <= r < 0x00072811}
    assert text == set(LEGEND_PLUS_CALLS)


@needs_analysis
def test_hearts_are_every_add_of_the_heart_loop():
    # The heart loop (0x6D920, one pass per crystal, to its exit 0x6DB3C)
    # draws through the add only at these two calls, so no quad of a lit
    # heart stays behind at 16:9.
    an = Analysis()
    loop = range(0x0006D920, 0x0006DB3C)
    adds = {r for r in an.returns_to({ADD}) if r in loop}
    assert adds == set(HEART_CALLS)
    # A draw through a wrapper would have its own site, unkeyed here.
    wrappers = {w["va"] for w in load()["wrapper"]}
    assert not {r for r in an.returns_to(wrappers) if r in loop}
    for ret in HEART_CALLS + LIVES_CALLS:
        assert an.containing(ret)[0] == 0x0006B1F0
    # The hearts and the lives share one x base, so panel's dx fits both.
    base = an.listing({0x0006D666, 0x0006D6BE, 0x0006D92F})
    assert base[0x0006D666].endswith("fstp dword ptr [esp + 0x18]")
    assert base[0x0006D6BE].endswith("fadd dword ptr [esp + 0x18]")
    assert base[0x0006D92F].endswith("fadd dword ptr [esp + 0x18]")


@needs_analysis
def test_panel_function_draws_only_in_panel():
    # Every add in sub_0006FF10 (the name, the frame, the bar) is keyed in
    # panel, so no piece that only a long bar or a hit draws stays behind.
    # Its text goes through a wrapper, at the name rows. The analysis also
    # lists tail-jump aliases that start inside it (0x6FF1D, ..., 0x7011D)
    # and end with it, so the span is its bytes, not its innermost entry.
    an = Analysis()
    span = range(PANEL_FN, PANEL_FN_END)
    sites = {s["ret_va"]: s for s in load()["site"]}
    wrappers = {w["va"] for w in load()["wrapper"]}
    calls = {r for r in an.returns_to({ADD} | wrappers) if r in span}
    assert set(BAR_CALLS) <= calls
    assert an.containing(PANEL_FN)[0] == PANEL_FN
    for ret in calls:
        assert ret in sites, "0x%08X: draw of the panel function unkeyed" % ret
        assert sites[ret]["group"] == "panel", "0x%08X" % ret


@needs_analysis
def test_row_inside_a_wrapper_fails():
    # Time's font call: inside sub_00048600, so every outlined string shares it.
    doc = load()
    doc = dict(doc, site=list(doc.get("site", [])) + [{"ret_va": 0x00048691, "kind": "left"}])
    errs = row_errors(doc, hooked(), Analysis())
    assert any("0x00048691: inside wrapper 0x00048600" in e for e in errs), errs


@needs_analysis
def test_bad_rows_fail():
    doc = load()
    first = doc["site"][0]["ret_va"] if doc.get("site") else 0x000178AE
    doc = dict(
        doc,
        site=list(doc.get("site", []))
        + [
            {"ret_va": first, "kind": "left"},  # duplicate (or the helper's own add)
            {"ret_va": 0x00012345, "kind": "left"},  # follows no call
            {"ret_va": 0x00012346, "kind": "sideways"},
            {"ret_va": 0x00012347, "group": "nosuch"},
        ],
    )
    errs = "\n".join(row_errors(doc, hooked(), Analysis()))
    assert "0x%08X: duplicate" % first in errs
    assert "0x00012345: does not follow" in errs
    assert "unknown kind 'sideways'" in errs
    assert "unknown group nosuch" in errs


@needs_analysis
def test_shared_moving_site_fails():
    # The digit helper's own add, as the table had it before the review:
    # sub_00018030 is called from sub_00092370 and two functions under
    # sub_000EA270, so a right row there moves all of their digits.
    doc = load()
    doc = dict(
        doc,
        wrapper=[w for w in doc["wrapper"] if w["va"] != 0x00018030],
        site=list(doc["site"]) + [{"ret_va": 0x00018216, "group": "counter"}],
    )
    errs = row_errors(doc, hooked(), Analysis())
    assert any("0x00018216: moves" in e for e in errs), errs


@needs_analysis
def test_canvas_immediates_in_the_listing():
    # The half sizes behind the 2D shader's offset are written only these
    # constants (320.0, 240.0), so a fixed canvas is right (notes 0.3).
    with open(os.path.join(DISASM, "asm", "text.asm"), encoding="utf-8", errors="replace") as f:
        text = f.read()
    for va, want in (
        (0x63022, "43a00000"),
        (0x6302C, "43700000"),
        (0x746F0, "43a00000"),
        (0x746FA, "43700000"),
    ):
        m = re.search(r"^  0x%08X  ([0-9a-f]+)\s" % va, text, re.M | re.I)
        assert m, "no instruction at 0x%08X" % va
        imm = bytes.fromhex(m.group(1))[-4:][::-1].hex()
        assert imm == want, "0x%08X stores %s" % (va, imm)


@pytest.mark.skipif(not os.path.isfile(XBE), reason="no game_files/default.xbe")
def test_rdata_half_sizes():
    with open(XBE, "rb") as f:
        xbe = f.read()
    (base,) = struct.unpack_from("<I", xbe, 0x104)
    nsec, secs = struct.unpack_from("<II", xbe, 0x11C)

    def f32(va):
        for i in range(nsec):
            vaddr, vsize, raddr, rsize = struct.unpack_from("<IIII", xbe, secs - base + i * 56 + 4)
            if vaddr <= va < vaddr + rsize:
                return struct.unpack_from("<f", xbe, raddr + va - vaddr)[0]
        raise AssertionError("0x%08X in no section" % va)

    assert f32(0x3DEDDC) == 320.0
    assert f32(0x3DEDD8) == 240.0


def _cli_has_hud_map():
    try:
        r = subprocess.run(
            [os.path.join(ROOT, "blinx2"), "hud-map", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "emit" in r.stdout


@needs_analysis
def test_cli_emit_check():
    if not _cli_has_hud_map():
        pytest.skip("the CLI in use has no hud-map")
    r = subprocess.run(
        [os.path.join(ROOT, "blinx2"), "hud-map", "emit", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stdout + r.stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
