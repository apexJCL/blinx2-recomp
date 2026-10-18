#!/usr/bin/env python3
"""occ_flips.py LOG [--min-batches 1400]: the occ-reports harness check.
Reads the backend flip lines of a RECOMP_TRACE=flip log
("[METAL] flip N batches B ..." or "[D3D11] flip N batches B ..."), takes
the first flip with at least --min-batches batches as the screen being up,
and prints the histogram of batch counts from there, the flips below the
floor, and the visibility totals over them (reports, settled, stale,
first). On the Story Mode screen (@story-idle) a flip below the floor is
one where the title skipped its characters because a visibility test read
incomplete: 157 batches instead of 1509.

Exit 0 when every flip after the first one up reaches the floor, 1 when one
does not (or the screen never comes up), 2 when the log has no flip lines.
The floor is 1400, not 1509, so a cursor blink does not fail the case.
"""

import argparse
import collections
import re
import sys

FLIP = re.compile(r"^\[(?:METAL|D3D11)\] flip (\d+) batches (\d+)\b.*?\bocc (\d+) \(")
SETTLED = re.compile(r"\bsettled (\d+) \(stale (\d+), first (\d+)\)")


def parse(lines):
    """[(flip, batches, reports, settled, stale, first)]; the last three are
    None on a log from before occ-reports (no settled field)."""
    out = []
    for line in lines:
        m = FLIP.match(line)
        if not m:
            continue
        s = SETTLED.search(line)
        n, b, r = (int(v) for v in m.groups())
        out.append((n, b, r) + (tuple(int(v) for v in s.groups()) if s else (None, None, None)))
    return out


def check(flips, floor):
    """(exit code, report lines)."""
    if not flips:
        return 2, ["no flip lines (run with RECOMP_TRACE=flip)"]
    up = next((i for i, f in enumerate(flips) if f[1] >= floor), None)
    if up is None:
        return 1, [
            f"screen never up: no flip with {floor} batches or more in {len(flips)} flips",
            f"batch counts: {format_hist(collections.Counter(f[1] for f in flips))}",
        ]
    after = flips[up:]
    hist = collections.Counter(f[1] for f in after)
    below = [f for f in after[1:] if f[1] < floor]
    reports = sum(f[2] for f in after)
    lines = [
        f"screen up at flip {after[0][0]} ({after[0][1]} batches); {len(after)} flips from there",
        f"batch counts: {format_hist(hist)}",
        f"below {floor}: {len(below)}",
    ]
    if after[0][3] is None:
        lines.append(f"occ: {reports} reports (no settled field: a log from before occ-reports)")
    else:
        settled, stale, first = (sum(f[k] for f in after) for k in (3, 4, 5))
        lines.append(f"occ: {reports} reports, settled {settled} (stale {stale}, first {first})")
    if below:
        lines.append(
            f"FAIL: {len(below)} flips below {floor} batches after the screen was up"
            f" (first at flip {below[0][0]}: {below[0][1]} batches)"
        )
        return 1, lines
    lines.append("PASS")
    return 0, lines


def format_hist(hist):
    return ", ".join(f"{b} x{n}" for b, n in sorted(hist.items(), key=lambda kv: (-kv[1], kv[0])))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("log")
    ap.add_argument("--min-batches", type=int, default=1400)
    a = ap.parse_args(argv)
    with open(a.log, encoding="utf-8", errors="replace") as f:
        code, lines = check(parse(f), a.min_batches)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
