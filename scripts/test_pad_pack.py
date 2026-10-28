#!/usr/bin/env python3
"""Tests for src/pad_pack.h, the title's 18-byte pad from an XBOX_GAMEPAD.

cat_pad_get_state merges the script, the host pad and the keyboard into
an XBOX_GAMEPAD, runs the host actions' pad filter on it as an
XBOX_INPUT_STATE (a consumed chord leaves it there) and packs the result
for the title. A driver packs given states and prints the 18 bytes, which
are checked against the XINPUT_GAMEPAD layout the title reads.

  uv run pytest scripts/test_pad_pack.py

Skips when no C compiler is on PATH or the toolkit is not beside the
project (external/xboxrecomp or ../xboxrecomp, as CMakeLists.txt finds it).
"""

import os
import shutil
import struct
import subprocess
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include "pad_pack.h"
int main(int argc, char **argv)
{
    for (int i = 1; i + 12 < argc; i += 13) {
        XBOX_INPUT_STATE st;
        uint8_t out[18];
        memset(&st, 0, sizeof st);
        st.Gamepad.wButtons = (WORD)strtol(argv[i], NULL, 0);
        for (int k = 0; k < 8; k++)
            st.Gamepad.bAnalogButtons[k] = (BYTE)strtol(argv[i + 1 + k], NULL, 0);
        st.Gamepad.sThumbLX = (SHORT)strtol(argv[i + 9], NULL, 0);
        st.Gamepad.sThumbLY = (SHORT)strtol(argv[i + 10], NULL, 0);
        st.Gamepad.sThumbRX = (SHORT)strtol(argv[i + 11], NULL, 0);
        st.Gamepad.sThumbRY = (SHORT)strtol(argv[i + 12], NULL, 0);
        cat_pad_pack(&st.Gamepad, out);
        for (int k = 0; k < 18; k++)
            printf("%02x", out[k]);
        printf("\n");
    }
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _toolkit():
    for d in (os.path.join(ROOT, "external", "xboxrecomp"), os.path.join(ROOT, "..", "xboxrecomp")):
        if os.path.exists(os.path.join(d, "src", "input", "xinput_xbox.h")):
            return os.path.join(d, "src")
    return None


def _pack(*states):
    """The 18 bytes of each (buttons, [8 analog], lx, ly, rx, ry)."""
    tk = _toolkit()
    if not _cc() or not tk:
        pytest.skip("no C compiler or no toolkit beside the project")
    args = []
    for buttons, analog, lx, ly, rx, ry in states:
        args += [str(buttons), *map(str, analog), str(lx), str(ly), str(rx), str(ry)]
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "t.c"), os.path.join(d, "t")
        with open(c, "w") as f:
            f.write(DRIVER)
        subprocess.run(
            [_cc(), "-std=c11", "-Wall", "-Wextra", "-Werror"]
            + ["-I", SRC, "-I", tk, "-I", os.path.join(tk, "input"), "-o", exe, c],
            check=True,
        )
        out = subprocess.run([exe, *args], check=True, capture_output=True, text=True).stdout
    return [bytes.fromhex(line) for line in out.split()]


def test_layout_little_endian():
    """wButtons, the 8 analog buttons, then the four sticks, little-endian."""
    analog = [255, 0, 30, 31, 1, 2, 128, 254]
    (got,) = _pack((0x00F5, analog, 1, -1, 32767, -32768))
    assert len(got) == 18
    assert got == struct.pack("<H8B4h", 0x00F5, *analog, 1, -1, 32767, -32768)


def test_released_is_zero():
    """A pad the filter emptied (a consumed chord, no source) packs as zeros."""
    (got,) = _pack((0, [0] * 8, 0, 0, 0, 0))
    assert got == bytes(18)


def test_consumed_buttons_leave_the_rest():
    """Clearing A and BACK (guide+a, back+left_thumb) keeps the other fields."""
    full, cleared = _pack(
        (0x0060, [255, 255, 0, 0, 0, 0, 0, 0], 100, -100, 0, 0),
        (0x0040, [0, 255, 0, 0, 0, 0, 0, 0], 100, -100, 0, 0),
    )
    assert full[0] == 0x60 and cleared[0] == 0x40
    assert full[2] == 255 and cleared[2] == 0
    assert full[3:] == cleared[3:]
