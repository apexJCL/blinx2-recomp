#!/usr/bin/env python3
"""Tests for docs/env.md: the tier counts in the intro bullets
("- **Debug** (76): ...") match the rows in that tier's table. The counts
went stale by hand once (Debug said 72 with 76 rows).

  python3 scripts/test_env_doc.py
  python3 -m pytest scripts/test_env_doc.py

Exit 0 when every test passes.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "..", "docs", "env.md")
TIERS = ("Config", "Trace", "Debug")


def parse(text):
    """Return ({tier: stated count}, {tier: table rows})."""
    stated = {
        m.group(1): int(m.group(2)) for m in re.finditer(r"^- \*\*(\w+)\*\* \((\d+)\):", text, re.M)
    }
    rows, section = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].split()[0]
            continue
        # Skip the header row and the |---| separator; every other row is a key.
        if section in TIERS and line.startswith("| ") and not line.startswith("| Old name"):
            rows[section] = rows.get(section, 0) + 1
    return stated, rows


def test_tier_counts_match_rows():
    with open(DOC, encoding="utf-8") as f:
        stated, rows = parse(f.read())
    for tier in TIERS:
        assert tier in stated, f"no '- **{tier}** (N):' bullet in env.md"
        assert stated[tier] == rows.get(tier, 0), (
            f"{tier}: heading says {stated[tier]}, table has {rows.get(tier, 0)} rows"
        )


def test_parse_counts_rows_not_headers():
    text = (
        "- **Config** (1): x\n- **Trace** (0): x\n- **Debug** (2): x\n"
        "## Config\n\n| Old name | New name |\n|---|---|\n| `A` | `A` |\n"
        "## Debug (`RECOMP_DEBUG=`)\n\n| Old name | New name |\n|---|---|\n| a | `a` |\n| b | `b` |\n"
        "## Deleted\n\n| Name | What |\n|---|---|\n| `X` | gone |\n"
    )
    stated, rows = parse(text)
    assert stated == {"Config": 1, "Trace": 0, "Debug": 2}
    assert rows == {"Config": 1, "Debug": 2}


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
