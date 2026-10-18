#!/usr/bin/env python3
"""Tests for src/pad_slots.c, which host pad slot drives which guest port.

Compiles a small driver against pad_slots.c and feeds it a sequence of
host slot masks (what xbox_InputIsConnected reports each frame) and, as
aMASK, activity masks (the slots whose pad was pressed), checking the
slot:port map, the port mask and the reverse lookup after each one. The
title reads player 1 from port 0, so a pad alone on a slot above 0, or
behind Steam's inert virtual pad, must still reach it.

  python3 scripts/test_pad_slots.py
  uv run pytest scripts/test_pad_slots.py

Skips (exit 0) when no C compiler is on PATH.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")

DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include "pad_slots.h"
int main(int argc, char **argv)
{
    PadSlots ps;
    char map[64];
    pad_slots_init(&ps);
    for (int i = 1; i < argc; i++) {
        int changed = argv[i][0] == 'a'
            ? pad_slots_activity(&ps, (uint32_t)strtoul(argv[i] + 1, NULL, 0))
            : pad_slots_update(&ps, (uint32_t)strtoul(argv[i], NULL, 0));
        pad_slots_format(&ps, map, sizeof map);
        printf("%s %X %d", map, pad_slots_ports(&ps), changed);
        for (uint32_t p = 0; p < PAD_SLOTS; p++)
            printf(" %d", pad_slots_slot_of(&ps, p));
        printf(" %X %X\n", pad_slots_mapped(&ps), pad_slots_idle(&ps));
    }
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _run(*masks):
    """One (map, port mask, changed, [slot of port 0..3], mapped, idle) per mask."""
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "t.c"), os.path.join(d, "t")
        with open(c, "w") as f:
            f.write(DRIVER)
        subprocess.run(
            [
                _cc(),
                "-std=c11",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-I",
                SRC,
                "-o",
                exe,
                c,
                os.path.join(SRC, "pad_slots.c"),
            ],
            check=True,
        )
        out = subprocess.run(
            [exe, *(m if isinstance(m, str) else hex(m) for m in masks)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    rows = []
    for line in out.splitlines():
        f = line.split()
        rows.append(
            (
                f[0],
                int(f[1], 16),
                int(f[2]),
                [int(x) for x in f[3:7]],
                int(f[7], 16),
                int(f[8], 16),
            )
        )
    return rows


def _need_cc():
    if not _cc():
        pytest.skip("no C compiler")


def _maps(*masks):
    return [r[0] for r in _run(*masks)]


def test_stock_slot_zero():
    """A pad on slot 0 drives port 0, as before the change."""
    _need_cc()
    assert _run(0x0, 0x1, 0x1) == [
        ("none", 0x0, 0, [-1, -1, -1, -1], 0x0, 0x0),
        ("0:0", 0x1, 1, [0, -1, -1, -1], 0x1, 0x1),
        ("0:0", 0x1, 0, [0, -1, -1, -1], 0x1, 0x1),
    ]


def test_slots_from_zero_are_identity():
    """Slots filled from 0 in order, as XInput assigns them, keep slot N on port N."""
    _need_cc()
    assert _maps(0x3) == ["0:0,1:1"]
    assert _maps(0x1, 0x3, 0x7, 0xF) == ["0:0", "0:0,1:1", "0:0,1:1,2:2", "0:0,1:1,2:2,3:3"]
    assert _run(0xF)[0][3] == [0, 1, 2, 3]


def test_lone_pad_on_higher_slot():
    """A pad alone on slot 1 (or 3) drives port 0."""
    _need_cc()
    assert _run(0x2) == [("1:0", 0x1, 1, [1, -1, -1, -1], 0x2, 0x2)]
    assert _maps(0x8) == ["3:0"]


def test_later_pads_fill_next_ports():
    """Pads that come up later take the next free port, whatever their slot."""
    _need_cc()
    # Slot 1 first, then slot 0 (a pad plugged in on the empty lower index).
    assert _maps(0x2, 0x3) == ["1:0", "0:1,1:0"]
    # Two pads coming up together go in slot order.
    assert _maps(0x0, 0xA) == ["none", "1:0,3:1"]


def test_unplug_keeps_other_players():
    """A pad going away frees its port and moves nobody else."""
    _need_cc()
    rows = _run(0x3, 0x2, 0x3)
    assert [r[0] for r in rows] == ["0:0,1:1", "1:1", "0:0,1:1"]
    assert rows[1][1] == 0x2 and rows[1][3] == [-1, 1, -1, -1]
    # The freed port is the lowest, so the next pad (any slot) takes it.
    assert _maps(0x3, 0x2, 0x6) == ["0:0,1:1", "1:1", "1:1,2:0"]
    # Everything gone, then back: as at start.
    assert _maps(0x6, 0x0, 0x4) == ["1:0,2:1", "none", "2:0"]


def test_swap_in_one_interval():
    """A pad swapped for another between two updates hands its port on."""
    _need_cc()
    assert _maps(0x1, 0x2) == ["0:0", "1:0"]
    assert [r[2] for r in _run(0x1, 0x2, 0x2)] == [1, 1, 0]


def test_high_bits_ignored():
    _need_cc()
    assert _maps(0x12) == ["1:0"]


def test_four_pads_middle_replugged():
    """Two freed ports are refilled lowest first, whatever the new slots."""
    _need_cc()
    assert _maps(0xF, 0x9, 0xB, 0xF) == [
        "0:0,1:1,2:2,3:3",
        "0:0,3:3",
        "0:0,1:1,3:3",
        "0:0,1:1,2:2,3:3",
    ]
    # Back in the other order: each slot takes its own port again.
    assert _maps(0xF, 0x9, 0xD, 0xF) == [
        "0:0,1:1,2:2,3:3",
        "0:0,3:3",
        "0:0,2:2,3:3",
        "0:0,1:1,2:2,3:3",
    ]


def test_slot_zero_back_on_port_zero():
    _need_cc()
    assert _maps(0xF, 0xE, 0xF) == ["0:0,1:1,2:2,3:3", "1:1,2:2,3:3", "0:0,1:1,2:2,3:3"]


def test_first_press_takes_inert_port():
    """Steam's inert pad on slot 0, the real one on slot 1: pressing it swaps."""
    _need_cc()
    rows = _run(0x3, "a0x2", "a0x1", "a0x3")
    assert [r[0] for r in rows] == ["0:0,1:1", "0:1,1:0", "0:1,1:0", "0:1,1:0"]
    assert [r[2] for r in rows] == [1, 1, 0, 0]
    assert rows[1][1] == 0x3  # ports stay present: no remove or insert
    assert rows[1][3] == [1, 0, -1, -1]


def test_active_pad_is_never_moved():
    """Player 1 pressed first: player 2's first press moves nobody."""
    _need_cc()
    assert _maps(0x3, "a0x1", "a0x2") == ["0:0,1:1", "0:0,1:1", "0:0,1:1"]


def test_three_pads_two_inert():
    """The one pad in use lands on port 0, wherever it was."""
    _need_cc()
    assert _maps(0x7, "a0x4") == ["0:0,1:1,2:2", "0:2,1:1,2:0"]
    # Then the second pad pressed takes the lowest inert port left (1).
    assert _maps(0x7, "a0x4", "a0x1") == ["0:0,1:1,2:2", "0:2,1:1,2:0", "0:1,1:2,2:0"]


def test_activity_forgotten_when_unplugged():
    """A pad that goes away and comes back is inert again."""
    _need_cc()
    assert _maps(0x3, "a0x1", 0x2, 0x3, "a0x2") == [
        "0:0,1:1",
        "0:0,1:1",
        "1:1",
        "0:0,1:1",
        "0:1,1:0",
    ]


def test_activity_ignores_slots_without_port():
    _need_cc()
    assert _run(0x1, "a0x6")[1][0] == "0:0"
    assert _maps(0x1, "a0x6", 0x3) == ["0:0", "0:0", "0:0,1:1"]


def test_pad_pressed_alone_keeps_port_zero():
    """Played alone, then a second pad comes up and is pressed: no swap.

    pad_input watches every never-active pad, a lone one included, so the
    first pad is marked active before the second can claim its port.
    """
    _need_cc()
    rows = _run(0x1, "a0x1", 0x3, "a0x2")
    assert [r[0] for r in rows] == ["0:0", "0:0", "0:0,1:1", "0:0,1:1"]
    assert rows[1][2] == 0 and rows[3][2] == 0
    # The lone pad is idle until pressed, so pad_input watches it (idle != 0).
    assert rows[0][5] == 0x1
    # Then only the newcomer is idle: active= would read mapped & ~idle.
    assert (rows[2][4], rows[2][5]) == (0x3, 0x2)
    assert rows[3][5] == 0
    # Unmarked (the bug): the second pad's first press takes port 0.
    assert _maps(0x1, 0x3, "a0x2")[-1] == "0:1,1:0"


def test_replug_keeps_its_port():
    """A pad pulled and replugged takes its old port back, not the lowest free.

    The SDL backend gives a replugged model its old slot, and
    XInput the lowest free index, so the slot stands for the pad.
    """
    _need_cc()
    # Slots 0 and 1 go; slot 1 comes back first, to port 1 and not 0.
    assert _maps(0x7, 0x4, 0x6, 0x7) == [
        "0:0,1:1,2:2",
        "2:2",
        "1:1,2:2",
        "0:0,1:1,2:2",
    ]
    # Its old port taken by a newcomer: the lowest free one instead.
    assert _maps(0x3, 0x1, 0x5, 0x7) == ["0:0,1:1", "0:0", "0:0,2:1", "0:0,1:2,2:1"]


def test_replug_alone_is_player_one():
    """With no other pad up, a returning pad takes port 0, not its old port."""
    _need_cc()
    assert _maps(0x3, 0x0, 0x2) == ["0:0,1:1", "none", "1:0"]
    # And the pad left alone on a higher port stays there (no shift).
    assert _maps(0x3, 0x2) == ["0:0,1:1", "1:1"]


def test_replug_after_promotion():
    """The port remembered is the one held when the pad went, after a swap."""
    _need_cc()
    # Steam's inert pad on slot 0, the real one on slot 1 pressed, a third
    # pad on slot 2; slots 0 and 1 go, then slot 0 comes back alone with
    # slot 2: port 1, where it was, not port 0.
    assert _maps(0x3, "a0x2", 0x7, 0x4, 0x5) == [
        "0:0,1:1",
        "0:1,1:0",
        "0:1,1:0,2:2",
        "2:2",
        "0:1,2:2",
    ]
    # The real pad comes back: port 0 again, and it is idle until pressed.
    rows = _run(0x3, "a0x2", 0x7, 0x4, 0x5, 0x7)
    assert rows[-1][0] == "0:1,1:0,2:2"
    assert rows[-1][5] == 0x7


def test_same_poll_presses_in_slot_order():
    """Two never-pressed pads whose first press falls in one poll."""
    _need_cc()
    assert _maps(0x3, "a0x3") == ["0:0,1:1", "0:0,1:1"]
    assert _maps(0x2, 0x3, "a0x3") == ["1:0", "0:1,1:0", "0:0,1:1"]


if __name__ == "__main__":
    for t in (
        test_stock_slot_zero,
        test_slots_from_zero_are_identity,
        test_lone_pad_on_higher_slot,
        test_later_pads_fill_next_ports,
        test_unplug_keeps_other_players,
        test_swap_in_one_interval,
        test_high_bits_ignored,
        test_four_pads_middle_replugged,
        test_slot_zero_back_on_port_zero,
        test_first_press_takes_inert_port,
        test_active_pad_is_never_moved,
        test_three_pads_two_inert,
        test_activity_forgotten_when_unplugged,
        test_activity_ignores_slots_without_port,
        test_pad_pressed_alone_keeps_port_zero,
        test_replug_keeps_its_port,
        test_replug_alone_is_player_one,
        test_replug_after_promotion,
        test_same_poll_presses_in_slot_order,
    ):
        t()
    print("ok")
    sys.exit(0)
