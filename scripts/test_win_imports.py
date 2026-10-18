#!/usr/bin/env python3
"""Tests for the Windows exe's import table: the XInput DLL it names must
ship with Windows. mingw-w64's plain libxinput.a imports XINPUT1_3.dll, the
DirectX June 2010 redistributable; a stock Windows 10/11 lacks it and the
exe dies with 0xC0000135 before it opens a window or a log. Proton ships the
DLL, so the Proton bench never shows it. Reads every built
build-win/ and build-pkg-win/ game exe with llvm-objdump -p; skips when
there is no Windows build or no llvm-objdump.

  python3 scripts/test_win_imports.py
  python3 -m pytest scripts/test_win_imports.py

Exit 0 when every test passes or skips.
"""

import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIRS = ("build-win", "build-pkg-win")


class Skip(Exception):
    pass


def skip(msg):
    # Under pytest a skip is a skip; run alone, the __main__ loop reports it.
    if "pytest" not in sys.modules:
        raise Skip(msg)
    import pytest

    pytest.skip(msg)


def objdump():
    # The toolchain blinx2 builds with first, then PATH. GNU objdump on a
    # Linux host has no PE support, so only llvm-objdump counts.
    found = sorted(
        glob.glob(os.path.join(ROOT, "third_party", "llvm-mingw-*", "bin", "llvm-objdump"))
    )
    return found[-1] if found else shutil.which("llvm-objdump")


def built_exes():
    exes = []
    for d in BUILD_DIRS:
        exes += sorted(glob.glob(os.path.join(ROOT, d, "*_recomp.exe")))
    return exes


def dll_imports(tool, exe):
    out = subprocess.run([tool, "-p", exe], capture_output=True, text=True, check=True).stdout
    return [
        line.split(":", 1)[1].strip().upper()
        for line in out.splitlines()
        if line.strip().startswith("DLL Name:")
    ]


def test_xinput_import_ships_with_windows():
    exes = built_exes()
    if not exes:
        skip("no Windows build in " + " or ".join(BUILD_DIRS))
    tool = objdump()
    if not tool:
        skip("no llvm-objdump")
    for exe in exes:
        xinput = [n for n in dll_imports(tool, exe) if n.startswith("XINPUT")]
        rel = os.path.relpath(exe, ROOT)
        assert xinput == ["XINPUT1_4.DLL"], (
            f"{rel} imports {xinput}; rebuild after linking xinput1_4"
        )


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Skip as e:
                print("skip", name, e)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
