#!/usr/bin/env python3
"""Tests for src/unimpl_budget.h, the per-address [UNIMPL] log budget.

Compiles a small driver against the header and checks which hits print. The
case that matters: a site hit thousands of times must not keep a site hit
once from printing, which is what the old global 50-line cap did.

  python3 scripts/test_unimpl_budget.py
  xboxrecomp/.venv/bin/python3 -m pytest scripts/test_unimpl_budget.py

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
#include "unimpl_budget.h"
static struct unimpl_budget b;
#define HIT(va, per) printf("%08X %u\n", (unsigned)(va), unimpl_budget_hit(&b, (va), (per)))
int main(void)
{
    uint32_t i;
    for (i = 0; i < 2000; i++)                  /* the chatty site */
        unimpl_budget_hit(&b, 0x00355000u, 3);
    HIT(0x00301AB7u, 3);                        /* new: prints */
    HIT(0x00301AB7u, 3);
    HIT(0x00301AB7u, 3);
    HIT(0x00301AB7u, 3);                        /* 4th: quiet */
    for (i = 5; i < 10; i++)
        unimpl_budget_hit(&b, 0x00301AB7u, 3);
    HIT(0x00301AB7u, 3);                        /* 10th: prints */
    HIT(0x00000000u, 0);                        /* va 0, budget 0: still once */
    HIT(0x00000000u, 0);
    HIT(0xFFFFFFFFu, 3);                        /* no key: overflow path */
    /* Fill the table, then an untracked site still prints. */
    for (i = 0; i < UNIMPL_SLOTS; i++)
        unimpl_budget_hit(&b, 0x01000000u + i * 4u, 3);
    HIT(0x02000000u, 3);
    HIT(0x00301AB7u, 3);                        /* tracked: 11th, quiet */
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _run(driver=DRIVER):
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "t.c"), os.path.join(d, "t")
        with open(c, "w") as f:
            f.write(driver)
        subprocess.run([_cc(), "-std=c11", "-Wall", "-Werror", "-I", SRC, "-o", exe, c], check=True)
        out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout
    return [line.split() for line in out.splitlines()]


def test_budget():
    if not _cc():
        print("skip: no C compiler")
        return
    lines = _run()
    assert lines == [
        ["00301AB7", "1"],
        ["00301AB7", "2"],
        ["00301AB7", "3"],
        ["00301AB7", "0"],
        ["00301AB7", "10"],
        ["00000000", "1"],
        ["00000000", "0"],
        ["FFFFFFFF", str(0xFFFFFFFF)],
        ["02000000", str(0xFFFFFFFF)],
        ["00301AB7", "0"],
    ], lines


def test_chatty_site_reports_powers_of_ten():
    if not _cc():
        return
    driver = DRIVER.replace(
        "HIT(0x00301AB7u, 3);                        /* new: prints */",
        "for (i = 2000; i < 9999; i++) unimpl_budget_hit(&b, 0x00355000u, 3);"
        " HIT(0x00355000u, 3); HIT(0x00355000u, 3);"
        " HIT(0x00301AB7u, 3);",
    )
    lines = _run(driver)
    assert lines[:2] == [["00355000", "10000"], ["00355000", "0"]], lines


if __name__ == "__main__":
    test_budget()
    test_chatty_site_reports_powers_of_ten()
    print("ok")
    sys.exit(0)
