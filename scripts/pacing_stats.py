#!/usr/bin/env python3
"""Frame-pacing statistics from run logs (RECOMP_TRACE=flip,pacing=all).
Standard library only.

  pacing_stats.py [--scen SCEN] [--anchor EVENT | --after-flip N] LOG...
  pacing_stats.py [...] --arm NAME LOG... --arm NAME LOG... [--gate clock|sleep]

For each run, over the 3D flips after the checkpoint (golden.json's anchor
EVENT for SCEN, found from the batch counts as golden.py finds it; default
stage1's first-3d):
  - the flip interval p5/p50/p95/max, from the "[PACING] flip N t_us T" lines
    (microseconds; "[GPU] flip N T ms" when they are missing);
  - flips/s over the 3D flips;
  - CPU raster ms p50, from "[GPU] flip ... raster X ms" (the CPU path; the
    GPU backends print 0);
  - process CPU, and per spin-wait site the in-wait and thread CPU and how
    the waits ended, from the "[PACING]" summaries;
  - every 600-vblank window ("[NV2A] vblank N: ... gap a-b ms"): its spread
    b - a, the median spread, and the share within 16.67 +- 1.5 ms. A window
    that ends before the checkpoint, or that spans a flip with 2 or fewer
    batches (a load or a black frame), is listed and left out.

A 3D flip has more than 2 batches (the bench-methodology rule; movie windows
are not tagged yet, so batches alone). Its interval is from the flip before.

With arms, each statistic of an arm is the median of its runs; the arm's
spread is the range of its runs, widened by 2% for flips/s and 0.5 ms for an
interval percentile. The second arm is compared with the first:
  flags (recorded, not fails): flips/s 25% or more below; CPU raster p50 at
  1.5x or more.
  --gate clock (first arm vblank_clock=ms, second the ns clock): p95 - p5 at
  most half the first arm's; p50 within 33.3 +- 0.5 ms on both; median
  window spread at most 3 ms and at least 80% of windows within 16.67 +- 1.5
  ms, on the second arm.
  --gate sleep (first arm spin, second sleep): in-wait CPU at most 10% at
  every site; process CPU at least 25 points lower; at every site, loops
  that left on the 1 ms timeout at most 5% of loop exits in every summary
  (mid-loop timeouts are normal and only reported); flips/s and each
  interval percentile inside the first arm's spread; no flag.
Exit 0, or 1 when a gate fails, 2 on unusable input.
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import golden  # noqa: E402  (flip_batches, find_anchor, load_golden)

PACING_FLIP_RE = re.compile(r"^\[PACING\] flip (\d+) t_us (\d+) batches (\d+)")
GPU_FLIP_RE = re.compile(r"^\[GPU\] flip (\d+) (\d+) ms\b.*?\bbatches (\d+)(?:.*?\braster ([\d.]+) ms)?")
SUMMARY_RE = re.compile(r"^\[PACING\] flips \d+: .*?cpu process ([\d.]+)%; mode (\w+)")
SITE_RE = re.compile(r"^\[PACING\]\s+site (0x[0-9A-Fa-f]+|other): waits (\d+) immediate (\d+)"
                     r" wakes (\d+) timeouts (\d+) dispatch (\d+);"
                     r"(?: exits wake (\d+) timeout (\d+);)? cpu in-wait ([\d.]+)%"
                     r" thread ([\d.]+)%")
EXIT_TIMEOUT_MAX = 0.05   # loops that left on the timeout, of all loop exits
VBLANK_RE = re.compile(r"^\s*\[NV2A\] vblank (\d+): last 600 in (\d+) ms, gap ([\d.]+)-([\d.]+) ms")
FLIP_ANY_RE = re.compile(r"^\[(?:PACING|GPU|D3D11|METAL)\] flip (\d+)\b")

VBLANK_MS = 1000.0 / 60.0
WINDOW_TOL = 1.5
THREE_D = 2          # batches above this: a 3D flip


def pct(vals, p):
    """Nearest rank on the sorted list, as the runtime's summary does."""
    s = sorted(vals)
    return s[int(p * (len(s) - 1) + 0.5)]


def parse(log):
    run = {"flip_us": {}, "batches": {}, "raster": {}, "summaries": [], "sites": [],
           "windows": []}
    last_flip = 0
    with open(log, errors="replace") as f:
        for line in f:
            m = PACING_FLIP_RE.match(line)
            if m:
                fl = int(m.group(1))
                run["flip_us"][fl] = int(m.group(2))
                run["batches"].setdefault(fl, int(m.group(3)))
                last_flip = max(last_flip, fl)
                continue
            m = GPU_FLIP_RE.match(line)
            if m:
                fl = int(m.group(1))
                run.setdefault("gpu_ms", {})[fl] = int(m.group(2))
                if m.group(4) is not None:
                    run["raster"][fl] = float(m.group(4))
                last_flip = max(last_flip, fl)
                continue
            m = SUMMARY_RE.match(line)
            if m:
                run["summaries"].append({"cpu": float(m.group(1)), "mode": m.group(2),
                                         "flip": last_flip, "sites": {}})
                continue
            m = SITE_RE.match(line)
            if m and run["summaries"]:
                run["summaries"][-1]["sites"][m.group(1)] = {
                    "waits": int(m.group(2)), "immediate": int(m.group(3)),
                    "wakes": int(m.group(4)), "timeouts": int(m.group(5)),
                    "dispatch": int(m.group(6)),
                    "exit_wake": int(m.group(7)) if m.group(7) else None,
                    "exit_timeout": int(m.group(8)) if m.group(8) else None,
                    "inwait": float(m.group(9)), "thread": float(m.group(10))}
                continue
            m = VBLANK_RE.match(line)
            if m:
                run["windows"].append({"vblank": int(m.group(1)), "ms": int(m.group(2)),
                                       "lo": float(m.group(3)), "hi": float(m.group(4)),
                                       "flip": last_flip})
                continue
            m = FLIP_ANY_RE.match(line)
            if m:
                last_flip = max(last_flip, int(m.group(1)))
    # The backend's batch count wins, as in golden.py; the pacing line's
    # stands in for flips that have none.
    gb = golden.flip_batches(log) or {}
    for fl, b in gb.items():
        if b or fl not in run["batches"]:
            run["batches"][fl] = b
    if not run["flip_us"] and run.get("gpu_ms"):
        run["flip_us"] = {fl: ms * 1000 for fl, ms in run["gpu_ms"].items()}
        run["coarse"] = True
    return run


def checkpoint(run, scen, event, after_flip):
    if after_flip is not None:
        return after_flip
    g = golden.load_golden()
    ev = g["scenarios"][scen]["anchors"][event]
    return golden.find_anchor(run["batches"], ev)


def stats(log, scen="stage1", event="first-3d", after_flip=None):
    run = parse(log)
    out = {"log": log, "coarse": run.get("coarse", False)}
    start = checkpoint(run, scen, event, after_flip)
    if start is None:
        out["error"] = f"no {event} checkpoint in the log"
        return out
    out["checkpoint"] = start
    t, b = run["flip_us"], run["batches"]
    iv, flips3d = [], []
    for fl in sorted(t):
        if fl <= start or b.get(fl, 0) <= THREE_D:
            continue
        flips3d.append(fl)
        if fl - 1 in t:
            iv.append((t[fl] - t[fl - 1]) / 1000.0)
    out["flips3d"] = len(flips3d)
    if len(iv) < 2:
        out["error"] = "fewer than two 3D flip intervals after the checkpoint"
        return out
    out.update(p5=pct(iv, .05), p50=pct(iv, .50), p95=pct(iv, .95), max=max(iv))
    span = (t[flips3d[-1]] - t[flips3d[0]]) / 1e6
    out["flips_s"] = (len(flips3d) - 1) / span if span > 0 else 0.0
    r = [run["raster"][fl] for fl in flips3d if fl in run["raster"]]
    out["raster_p50"] = statistics.median(r) if r else None

    summ = [s for s in run["summaries"] if s["flip"] > start]
    out["cpu_process"] = statistics.median([s["cpu"] for s in summ]) if summ else None
    out["modes"] = sorted({s["mode"] for s in summ})
    sites = {}
    for s in summ:
        for va, st in s["sites"].items():
            sites.setdefault(va, []).append(st)
    out["sites"] = {va: {"inwait": statistics.median([x["inwait"] for x in v]),
                         "thread": statistics.median([x["thread"] for x in v]),
                         "waits": sum(x["waits"] for x in v),
                         "wakes": sum(x["wakes"] for x in v),
                         "timeouts": sum(x["timeouts"] for x in v),
                         "immediate": sum(x["immediate"] for x in v),
                         "dispatch": sum(x["dispatch"] for x in v),
                         "exit_wake": sum(x["exit_wake"] or 0 for x in v),
                         "exit_timeout": sum(x["exit_timeout"] or 0 for x in v),
                         "exit_share_max": exit_share_max(v)}
                    for va, v in sites.items()}

    windows, excluded, prev_flip = [], [], 0
    for w in run["windows"]:
        lo_flip, hi_flip = prev_flip, w["flip"]
        prev_flip = w["flip"]
        if hi_flip <= start:
            excluded.append(dict(w, why="before the checkpoint"))
            continue
        low = [fl for fl in range(max(lo_flip, start) + 1, hi_flip + 1)
               if fl in b and b[fl] <= THREE_D]
        if low:
            excluded.append(dict(w, why=f"flips {low[0]}-{low[-1]} with <= {THREE_D} batches"
                                        " (a load or black frame)"))
            continue
        windows.append(w)
    out["windows"] = len(windows)
    out["windows_excluded"] = excluded
    if windows:
        spreads = [w["hi"] - w["lo"] for w in windows]
        out["window_spread_p50"] = statistics.median(spreads)
        ok = [w for w in windows if w["lo"] >= VBLANK_MS - WINDOW_TOL
              and w["hi"] <= VBLANK_MS + WINDOW_TOL]
        out["windows_in_tol"] = len(ok) / len(windows)
    return out


KEYS = ("p5", "p50", "p95", "max", "flips_s", "raster_p50", "cpu_process",
        "window_spread_p50", "windows_in_tol")
WIDEN = {"flips_s": lambda v: 0.02 * v, "p5": lambda v: 0.5, "p50": lambda v: 0.5,
         "p95": lambda v: 0.5, "max": lambda v: 0.5}


def arm(runs):
    a = {"runs": len(runs)}
    for k in KEYS:
        vals = [r[k] for r in runs if r.get(k) is not None]
        if not vals:
            continue
        med = statistics.median(vals)
        w = WIDEN.get(k, lambda v: 0.0)(med)
        a[k] = med
        a[k + "_spread"] = (min(vals) - w, max(vals) + w)
    a["jitter"] = statistics.median([r["p95"] - r["p5"] for r in runs])
    sites = {}
    for r in runs:
        for va, st in r.get("sites", {}).items():
            sites.setdefault(va, []).append(st)
    a["sites"] = {va: {"inwait": statistics.median([x["inwait"] for x in v]),
                       "thread": statistics.median([x["thread"] for x in v]),
                       "exit_share_max": (max(x["exit_share_max"] for x in v)
                                          if all(x["exit_share_max"] is not None for x in v)
                                          else None)}
                  for va, v in sites.items()}
    return a


def exit_share_max(summaries):
    """The largest share of loop exits on the timeout over a site's
    summaries; None when no summary has exit counts (an older trace)."""
    shares = []
    for x in summaries:
        if x["exit_wake"] is None:
            continue
        n = x["exit_wake"] + x["exit_timeout"]
        shares.append(x["exit_timeout"] / n if n else 0.0)
    return max(shares) if shares else None


def flags(base, test):
    out = []
    if base.get("flips_s") and test.get("flips_s") is not None \
            and test["flips_s"] <= 0.75 * base["flips_s"]:
        out.append(f"flips/s {test['flips_s']:.2f} is 25% or more below {base['flips_s']:.2f}")
    if base.get("raster_p50") and test.get("raster_p50") is not None \
            and test["raster_p50"] >= 1.5 * base["raster_p50"]:
        out.append(f"CPU raster p50 {test['raster_p50']:.2f} ms is 1.5x or more of"
                   f" {base['raster_p50']:.2f} ms")
    return out


def gate_clock(base, test):
    res = []
    res.append(("p95-p5 at most half the ms arm's",
                test["jitter"] <= base["jitter"] / 2,
                f"{test['jitter']:.2f} vs {base['jitter']:.2f} ms"))
    for name, a in (("ms", base), ("ns", test)):
        res.append((f"p50 within 33.3 +- 0.5 ms ({name})", abs(a["p50"] - 33.33) <= 0.5,
                    f"{a['p50']:.2f} ms"))
    sp, share = test.get("window_spread_p50"), test.get("windows_in_tol")
    res.append(("median vblank window spread at most 3 ms", sp is not None and sp <= 3.0,
                "-" if sp is None else f"{sp:.2f} ms"))
    res.append(("80% of windows within 16.67 +- 1.5 ms", share is not None and share >= 0.8,
                "-" if share is None else f"{share * 100:.0f}%"))
    return res


def gate_sleep(base, test):
    res = []
    for va, st in sorted(test["sites"].items()):
        res.append((f"in-wait CPU at most 10% at {va}", st["inwait"] <= 10.0,
                    f"{st['inwait']:.1f}%"))
        sh = st["exit_share_max"]
        res.append((f"timeout exits at most {EXIT_TIMEOUT_MAX * 100:.0f}% of loop exits"
                    f" in every summary at {va}",
                    sh is not None and sh <= EXIT_TIMEOUT_MAX,
                    "no exit counts (older trace)" if sh is None
                    else f"worst summary {sh * 100:.1f}%"))
    if not test["sites"]:
        res.append(("a spin-wait site reports at sleep", False, "no site lines"))
    bc, tc = base.get("cpu_process"), test.get("cpu_process")
    res.append(("process CPU down at least 25 points",
                bc is not None and tc is not None and bc - tc >= 25.0,
                "-" if bc is None or tc is None else f"{bc:.0f}% -> {tc:.0f}%"))
    for k in ("flips_s", "p5", "p50", "p95", "max"):
        lo, hi = base[k + "_spread"]
        res.append((f"{k} inside the spin spread", lo <= test[k] <= hi,
                    f"{test[k]:.2f} in [{lo:.2f}, {hi:.2f}]"))
    f = flags(base, test)
    res.append(("no regression flag", not f, "; ".join(f)))
    return res


def fmt_run(r):
    if "error" in r:
        return f"{r['log']}: {r['error']}"
    s = (f"{r['log']}: checkpoint flip {r['checkpoint']}, {r['flips3d']} 3D flips"
         f"{' (ms resolution)' if r['coarse'] else ''}; interval p5 {r['p5']:.2f}"
         f" p50 {r['p50']:.2f} p95 {r['p95']:.2f} max {r['max']:.2f} ms;"
         f" {r['flips_s']:.2f} flips/s")
    if r.get("raster_p50") is not None:
        s += f"; raster p50 {r['raster_p50']:.2f} ms"
    if r.get("cpu_process") is not None:
        s += f"; cpu process {r['cpu_process']:.0f}% (mode {','.join(r['modes'])})"
    if r.get("window_spread_p50") is not None:
        s += (f"; vblank windows {r['windows']}, spread p50 {r['window_spread_p50']:.2f} ms,"
              f" {r['windows_in_tol'] * 100:.0f}% within 16.67 +- 1.5")
    for va, st in sorted(r.get("sites", {}).items()):
        s += (f"\n    site {va}: waits {st['waits']} immediate {st['immediate']} wakes"
              f" {st['wakes']} timeouts {st['timeouts']} dispatch {st['dispatch']};"
              f" exits wake {st['exit_wake']} timeout {st['exit_timeout']};"
              f" in-wait {st['inwait']:.1f}% thread {st['thread']:.0f}%")
    for w in r.get("windows_excluded", []):
        if w["why"] != "before the checkpoint":
            s += (f"\n    excluded vblank window {w['vblank']} (gap {w['lo']}-{w['hi']} ms):"
                  f" {w['why']}")
    return s


def main(argv):
    scen, event, after, gate, arms, logs, as_json = "stage1", "first-3d", None, None, [], [], False
    it = iter(argv)
    for a in it:
        if a == "--scen":
            scen = next(it)
        elif a == "--anchor":
            event = next(it)
        elif a == "--after-flip":
            after = int(next(it))
        elif a == "--gate":
            gate = next(it)
            if gate not in ("clock", "sleep"):
                print("pacing_stats: --gate clock or sleep", file=sys.stderr)
                return 2
        elif a == "--arm":
            arms.append((next(it), []))
        elif a == "--json":
            as_json = True
        elif a.startswith("--"):
            print(__doc__, file=sys.stderr)
            return 2
        elif arms:
            arms[-1][1].append(a)
        else:
            logs.append(a)
    if not arms:
        arms = [("run", logs)]
    if not any(l for _, l in arms):
        print(__doc__, file=sys.stderr)
        return 2
    if gate and len(arms) != 2:
        print("pacing_stats: a gate compares exactly two arms", file=sys.stderr)
        return 2

    report, rc = {"arms": []}, 0
    for name, ls in arms:
        runs = [stats(l, scen, event, after) for l in ls]
        print(f"== {name}")
        for r in runs:
            print("  " + fmt_run(r))
        good = [r for r in runs if "error" not in r]
        if len(good) != len(runs):
            rc = 2
        a = arm(good) if good else None
        if a and len(arms) > 1:
            print(f"  median of {a['runs']}: p5 {a['p5']:.2f} p50 {a['p50']:.2f} p95 {a['p95']:.2f}"
                  f" max {a['max']:.2f} ms, p95-p5 {a['jitter']:.2f} ms,"
                  f" {a['flips_s']:.2f} flips/s"
                  + (f", cpu process {a['cpu_process']:.0f}%" if "cpu_process" in a else ""))
        report["arms"].append({"name": name, "runs": runs, "arm": a})
    if rc == 0 and len(arms) == 2:
        base, test = report["arms"][0]["arm"], report["arms"][1]["arm"]
        f = flags(base, test)
        print(f"== {arms[1][0]} against {arms[0][0]}")
        for x in f:
            print("  FLAG " + x)
        if not f:
            print("  no flags")
        report["flags"] = f
        if gate:
            res = (gate_clock if gate == "clock" else gate_sleep)(base, test)
            report["gate"] = [{"check": c, "pass": ok, "value": v} for c, ok, v in res]
            print(f"== {gate} gate")
            for c, ok, v in res:
                print(f"  {'PASS' if ok else 'FAIL'}  {c}{': ' + v if v else ''}")
            if not all(ok for _, ok, _ in res):
                rc = 1
    if as_json:
        print(json.dumps(report, indent=1, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
