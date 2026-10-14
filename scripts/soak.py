#!/usr/bin/env python3
"""Soak runs: play a stage over and over with a varied scripted pad and catch
crashes and hangs.

  scripts/soak.py gen PREFIX [--seed N] [--minutes M]   print a script
  scripts/soak.py run PREFIX --out DIR [--runs N] [--minutes M] [--seed N]
                  [--grace S] [--margin S] [--stall S] [--backend metal]
                  [--exe build/cat_recomp] [-- ENV=V ...]

PREFIX is a pad script that gets the game to the stage and hands over, e.g.
scripts/shots/pad/st5.txt (the debug stage select to 5-1). Its lines up to and
including the last "wait" step before the first gameplay line are kept; any
gameplay lines after it (a line with "LX=" etc.) are dropped. `gen` appends
M minutes of play: runs and jumps in all stick directions, attacks, held
triggers and every face/shoulder button (so the time powers and the menus get
pressed too), camera turns, and A/START taps that get past a death, the
continue screen or a dialogue. The seed picks the mix, so each run of `run`
plays differently (seed, seed+1, ...) and any run can be replayed exactly.

`run` is macOS only. It launches the game headless with no sound
(SDL_AUDIODRIVER=dummy; an SDL_AUDIODRIVER=... in the extra env overrides
that, so never pass one on the Mac without asking), RECOMP_THREAD_DUMP on and
a frame dump every 600 flips, one run at a time. A run ends --grace seconds
after the input script logs `script done`; --minutes*60 + --margin is only a
hang cap, and the prefix's navigation runs inside it. Each run gets
OUT/run-NN/{script.txt,log.txt,fb/,save/} and one summary line: the verdict,
the exit status, the [GPU] flip count, when the script ended, the idle
seconds after it, and the first [CRASH] line. Verdicts:
  ok          the script finished and the game ran to the grace stop
  STALL       no flip for --stall seconds, also before the first one (a
              SIGUSR1 thread dump goes into the log before the stop)
  CRASH       a [CRASH] line, or killed by a signal soak.py didn't send
  EXIT        the game exited on its own
  INCOMPLETE  the hang cap came before `script done` (e.g. a prefix
              `wait mem` that never came true)
New macOS crash reports for the exe (~/Library/Logs/DiagnosticReports) are
copied into the run. OUT/summary.txt collects the lines; an existing run-NN is
refused. Exits 1 if any run was not ok, 2 off macOS. Proton soaks would go
through blinx2 bench (a follow-up: Wine has no SIGUSR1 thread dump).

Macs: wrap it in notes' mac-run-lock (one game run at a time on the host).
Release playthrough soak (BLX-101): run it per stage prefix, 10 runs or more
each, with OUT under the workspace runs/, never inside a worktree.
"""

import argparse
import glob
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# A gameplay line in a pad script: actions only, no step keyword.
_STEP_WORDS = ("wait", "tap", "poke", "memdump")
_STICK = 20000


def load_prefix(path):
    """The steps of PREFIX up to the end of its navigation part."""
    keep = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.split()[0] not in _STEP_WORDS:
                break  # the first gameplay line: the hand-over point
            keep.append(line)
    if not keep:
        raise ValueError(f"{path}: no navigation steps")
    return keep


def _dir(rng):
    """A stick direction, sometimes neutral."""
    if rng.random() < 0.15:
        return 0, 0
    return rng.choice((-_STICK, 0, _STICK)), rng.choice((-_STICK, 0, _STICK))


def play_block(rng):
    """About 4 to 8 seconds of play, as one line of actions."""
    lx, ly = _dir(rng)
    parts = [f"LX={lx},LY={ly}"]
    kind = rng.random()
    if kind < 0.35:  # run and jump, attack on landing
        parts += ["A/0.3", "wait 0.6", "A/0.2", "wait 0.4", "X/0.3", "wait 1"]
    elif kind < 0.55:  # attack chain
        parts += ["X/0.2", "wait 0.4", "X/0.2", "wait 0.4", "B/0.3", "wait 1"]
    elif kind < 0.75:  # a power: hold a trigger, press a face/shoulder button
        trig = rng.choice(("L", "R"))
        btn = rng.choice(("Y", "B", "X", "BLACK", "WHITE"))
        parts += [trig, "wait 0.3", f"{btn}/0.3", "wait 0.8", f"-{trig}", "wait 1"]
    elif kind < 0.85:  # camera turn while moving
        parts += [f"RX={rng.choice((-_STICK, _STICK))}", "wait 1", "RX=0", "Y/0.3", "wait 1"]
    elif kind < 0.93:  # get past a death, a continue screen or a dialogue
        parts += ["LX=0,LY=0", "A/0.2", "wait 0.6", "A/0.2", "wait 0.6", "A/0.2", "wait 1"]
    else:  # pause and resume: the menu path (no cursor moves, so never "quit")
        parts += ["START/0.2", "wait 1.5", "START/0.2", "wait 1.5"]
    parts.append(f"wait {rng.choice((1, 2, 3))}")
    return ";".join(parts)


def _block_secs(line):
    secs = 0.0
    for part in line.split(";"):
        m = re.fullmatch(r"wait ([0-9.]+)", part.strip())
        if m:
            secs += float(m.group(1))
    return secs


def gen(prefix_lines, seed, minutes):
    rng = random.Random(seed)
    out = [f"# soak.py gen seed={seed} minutes={minutes}"] + list(prefix_lines)
    total = 0.0
    while total < minutes * 60:
        line = play_block(rng)
        total += _block_secs(line)
        out.append(line)
    return "\n".join(out) + "\n"


_FLIP = re.compile(rb"\[GPU\] flip (\d+) ")
_DONE = re.compile(rb"\[INPUT\] t=([0-9.]+) script done")


class LogTail:
    """Reads a growing game log from where it left off: the last `[GPU] flip N`
    (the other backends' flip lines repeat the same flip), whether the input
    script finished, and the first [CRASH] line."""

    def __init__(self, path):
        self.path, self.offset, self.rest = path, 0, b""
        self.flips, self.done, self.crash = 0, None, ""

    def update(self):
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return
        self.offset += len(data)
        lines = (self.rest + data).split(b"\n")
        self.rest = lines.pop()
        for line in lines:
            m = _FLIP.match(line)
            if m:
                self.flips = int(m.group(1))
                continue
            m = _DONE.match(line)
            if m:
                self.done = float(m.group(1))
            elif not self.crash and b"[CRASH]" in line:
                self.crash = line.decode("utf-8", "replace").strip()


REPORTS_DIR = os.path.expanduser("~/Library/Logs/DiagnosticReports")


def _reports(exe):
    return set(glob.glob(os.path.join(REPORTS_DIR, os.path.basename(exe) + "*")))


def merge_env(base, extra):
    """extra over base, but RECOMP_TRACE / RECOMP_DEBUG are comma lists that
    join (a later entry wins in the runtime), as blinx2 bench merges them."""
    out = dict(extra)
    for key in ("RECOMP_TRACE", "RECOMP_DEBUG"):
        if base.get(key) and extra.get(key):
            out[key] = base[key] + "," + extra[key]
    return out


# Seconds between log polls, and for the SIGUSR1 thread dump to be written.
POLL = 2.0
DUMP_SECS = 3.0


def _stop(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


def run_one(exe, script, rundir, cap, backend, stall, extra_env, grace=20, ips_wait=10):
    """One run. It ends `grace` s after the input script reports `script done`,
    or at `cap` s as a hang cap. Verdicts: ok; STALL (no flip for `stall` s,
    also before the first one); CRASH (a [CRASH] line, or killed by a signal
    we didn't send); EXIT (exited on its own); INCOMPLETE (hit the cap before
    the script finished, e.g. a prefix `wait mem` that never came true)."""
    os.makedirs(os.path.join(rundir, "fb"), exist_ok=True)
    env = dict(os.environ)
    env.update(
        RECOMP_HEADLESS="1",
        SDL_AUDIODRIVER="dummy",
        RECOMP_PB_BACKEND=backend,
        RECOMP_SAVE_DIR=os.path.join(rundir, "save"),
        RECOMP_HOST_PAD="0",
        RECOMP_KEYBOARD="0",
        RECOMP_INPUT_SCRIPT=script,
        RECOMP_THREAD_DUMP="1",
        RECOMP_TRACE="flip",
        RECOMP_DEBUG=f"fb_dump={rundir}/fb/,fb_dump_flips=600",
    )
    env.update(merge_env(env, extra_env))
    os.makedirs(env["RECOMP_SAVE_DIR"], exist_ok=True)
    log = os.path.join(rundir, "log.txt")
    tail = LogTail(log)
    before = _reports(exe)
    t0 = time.monotonic()
    stalled = we_stopped = False
    done_at = None
    with open(log, "wb") as f:
        p = subprocess.Popen([exe], cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
        try:
            last_flips, last_change = 0, t0
            while p.poll() is None:
                time.sleep(POLL)
                now = time.monotonic()
                tail.update()
                if tail.flips != last_flips:
                    last_flips, last_change = tail.flips, now
                elif now - last_change > stall:
                    stalled = True
                    p.send_signal(signal.SIGUSR1)  # thread dump, then stop
                    time.sleep(DUMP_SECS)
                    break
                if tail.done is not None and done_at is None:
                    done_at = now
                if done_at is not None and now - done_at >= grace:
                    break
                if now - t0 > cap:
                    break
            we_stopped = p.poll() is None
        finally:
            _stop(p)  # also on KeyboardInterrupt / SystemExit: no orphan game
    end = time.monotonic()
    rc = p.returncode
    tail.update()
    if stalled:
        verdict = "STALL"
    elif tail.crash:
        verdict = "CRASH"
    elif not we_stopped:
        verdict = "CRASH" if rc < 0 else "EXIT"
    elif tail.done is None:
        verdict = "INCOMPLETE"
    else:
        verdict = "ok"
    new = sorted(_reports(exe) - before)
    # ReportCrash writes the .ips a few seconds after the process dies.
    deadline = end + (ips_wait if verdict in ("CRASH", "EXIT") else 0)
    while not new and time.monotonic() < deadline:
        time.sleep(1)
        new = sorted(_reports(exe) - before)
    for r in new:
        shutil.copy2(r, rundir)
    return {
        "verdict": verdict,
        "rc": rc,
        "secs": round(end - t0),
        "flips": tail.flips,
        "done": tail.done,
        "idle": round(end - done_at) if done_at is not None else None,
        "crash": tail.crash,
        "reports": [os.path.basename(r) for r in new],
    }


def _raise_exit(signum, frame):
    raise SystemExit(128 + signum)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("prefix")
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--minutes", type=float, default=5)
    r = sub.add_parser("run")
    r.add_argument("prefix")
    r.add_argument("--runs", type=int, default=10)
    r.add_argument("--minutes", type=float, default=5)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out", required=True, help="<workspace>/runs/<topic>, never a worktree")
    r.add_argument("--exe", default=os.path.join(ROOT, "build", "cat_recomp"))
    r.add_argument("--backend", default="metal")
    r.add_argument(
        "--grace", type=float, default=20, help="seconds a run goes on after `script done`"
    )
    r.add_argument(
        "--margin",
        type=float,
        default=300,
        help="hang cap: seconds past the play time (the prefix runs inside it)",
    )
    r.add_argument(
        "--stall", type=float, default=30, help="seconds without a flip that count as a hang"
    )
    r.add_argument("env", nargs="*", help="extra ENV=VALUE for every run")
    a = ap.parse_args(argv)

    prefix = load_prefix(a.prefix)
    if a.cmd == "gen":
        sys.stdout.write(gen(prefix, a.seed, a.minutes))
        return 0

    if sys.platform != "darwin":
        print(
            "soak.py run is macOS only (SIGUSR1 thread dumps, DiagnosticReports); "
            "Proton soaks go through blinx2 bench (follow-up)",
            file=sys.stderr,
        )
        return 2
    extra = {}
    for kv in a.env:
        if "=" not in kv:
            ap.error(f"not ENV=VALUE: {kv}")
        k, v = kv.split("=", 1)
        extra[k] = v
    rundirs = [os.path.join(a.out, f"run-{a.seed + i:02d}") for i in range(a.runs)]
    old = [d for d in rundirs if os.path.exists(d)]
    if old:
        ap.error(f"{old[0]} exists: pick other seeds or another --out")
    # A harness kill or `kill PID` reaches only us, not the game: make it a
    # SystemExit so run_one's finally stops the game instead of orphaning it.
    signal.signal(signal.SIGTERM, _raise_exit)
    signal.signal(signal.SIGHUP, _raise_exit)
    os.makedirs(a.out, exist_ok=True)
    bad = 0
    with open(os.path.join(a.out, "summary.txt"), "a", encoding="utf-8") as summ:
        for i, rundir in enumerate(rundirs):
            seed = a.seed + i
            os.makedirs(rundir)
            script = os.path.join(rundir, "script.txt")
            with open(script, "w", encoding="utf-8") as f:
                f.write(gen(prefix, seed, a.minutes))
            stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            try:
                res = run_one(
                    os.path.abspath(a.exe),
                    script,
                    rundir,
                    a.minutes * 60 + a.margin,
                    a.backend,
                    a.stall,
                    extra,
                    grace=a.grace,
                )
            except (KeyboardInterrupt, SystemExit):
                summ.write(f"{stamp} seed={seed} interrupted\n")
                raise
            bad += res["verdict"] != "ok"
            done = f"{res['done']:.0f}" if res["done"] is not None else "-"
            line = (
                f"{stamp} seed={seed} {res['verdict']} rc={res['rc']} secs={res['secs']} "
                f"flips={res['flips']} script_done={done} idle={res['idle']} "
                f"reports={len(res['reports'])}" + (f" | {res['crash']}" if res["crash"] else "")
            )
            print(line, flush=True)
            summ.write(line + "\n")
            summ.flush()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
