#!/usr/bin/env python3
"""List (and optionally end) running BLiNX 2 game processes.

  running_game.py            print "pid<TAB>command line" per match; exit 0
  running_game.py --kill     SIGTERM the matches, wait 5 s, SIGKILL survivors,
                             print what was ended

--kill ends every match, and the match rule also catches the umu-run and
pressure-vessel wrappers whose arguments name cat_recomp.exe, so the whole
Proton launch of a foreign game goes, not only the game process.

A match is a process whose command line names cat_recomp.exe (any path, any
case: a Wine process hosting the Windows build, or the installed game under
Proton) or whose program is a cat_recomp executable (the macOS build or the
app's copy). The caller's own process tree (itself, its ancestors and its
descendants) is never listed.

bench.sh calls this after taking the run lock and before starting a game:
every bench game run holds that lock, so any match then is a foreign game
(the installed copy, or one started by hand) that would make the run's
timings noisy. Linux reads /proc; macOS uses ps; on Windows nothing calls
it (the bench is Linux, golden.py runs on the Mac) and it lists nothing.
Standard library only.
"""

import os
import re
import signal
import subprocess
import sys
import time

EXE_RE = re.compile(r"(^|[\\/])cat_recomp\.exe$", re.I)
BIN_RE = re.compile(r"(^|/)cat_recomp$")


def is_game(argv):
    """argv: the process's arguments. True for the game itself."""
    if not argv:
        return False
    if BIN_RE.search(argv[0]) or EXE_RE.search(argv[0]):
        return True
    # Wine and umu-run host the exe as an argument (wine64 Z:\...\cat_recomp.exe).
    return any(EXE_RE.search(a) for a in argv[1:])


def processes_linux(proc="/proc"):
    """[(pid, ppid, argv)] from /proc."""
    out = []
    for name in os.listdir(proc):
        if not name.isdigit():
            continue
        try:
            with open(os.path.join(proc, name, "cmdline"), "rb") as f:
                raw = f.read()
            with open(os.path.join(proc, name, "stat")) as f:
                stat = f.read()
        except OSError:
            continue
        argv = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
        # stat: "pid (comm) state ppid ..."; comm may hold spaces.
        ppid = int(stat.rsplit(")", 1)[1].split()[1])
        out.append((int(name), ppid, argv))
    return out


def parse_ps(text):
    """`ps -axo pid=,ppid=,command=` -> [(pid, ppid, argv)]. ps joins the
    arguments with spaces, so a path with spaces stays in argv[0] as far as
    the next argument; the match rule only looks at path endings."""
    out = []
    for line in text.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        cmd = parts[2]
        # The program: the longest prefix of the line that ends in cat_recomp,
        # so "/Applications/My Games/BLiNX2.app/Contents/MacOS/cat_recomp" counts.
        m = re.match(r"^(.*?/cat_recomp)(\s|$)", cmd)
        argv = [m.group(1)] + cmd[m.end():].split() if m else cmd.split()
        out.append((int(parts[0]), int(parts[1]), argv))
    return out


def processes_macos():
    r = subprocess.run(["ps", "-axo", "pid=,ppid=,command="], stdout=subprocess.PIPE)
    return parse_ps(r.stdout.decode("utf-8", "replace"))


def own_tree(procs, me):
    """me, its ancestors and its descendants (not its ancestors' other
    children: a game started from the same shell is still foreign)."""
    parent = {p: pp for p, pp, _ in procs}
    tree = {me}
    p = me
    while p in parent and parent[p] > 0 and parent[p] not in tree:
        p = parent[p]
        tree.add(p)
    kids = {}
    for pid, pp, _ in procs:
        kids.setdefault(pp, []).append(pid)
    todo = [me]
    while todo:
        for c in kids.get(todo.pop(), []):
            if c not in tree:
                tree.add(c)
                todo.append(c)
    return tree


def find_games(procs, me):
    skip = own_tree(procs, me)
    return [(pid, " ".join(argv)) for pid, _, argv in procs if pid not in skip and is_game(argv)]


def list_processes():
    if sys.platform.startswith("linux"):
        return processes_linux()
    if sys.platform == "darwin":
        return processes_macos()
    return []


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def kill(pids, grace=5.0):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    end = time.time() + grace
    while time.time() < end and any(alive(p) for p in pids):
        time.sleep(0.2)
    for pid in pids:
        if alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.name == "nt":
        print("running_game: not supported on Windows; nothing listed", file=sys.stderr)
        return 0
    games = find_games(list_processes(), os.getpid())
    if "--kill" in argv and games:
        kill([p for p, _ in games])
        time.sleep(0.5)
        left = {p for p, _ in find_games(list_processes(), os.getpid())}
        for pid, cmd in games:
            print("%s\t%s\t%s" % (pid, "survived" if pid in left else "ended", cmd))
        return 1 if left else 0
    for pid, cmd in games:
        print("%d\t%s" % (pid, cmd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
