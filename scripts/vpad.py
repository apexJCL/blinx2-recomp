#!/usr/bin/env python3
"""A virtual Xbox 360 pad on /dev/uinput, for testing host-pad input.

Runs on the Linux host. The device is the one scripts/xemu_ref.py
uses ("Microsoft X-Box 360 pad", 045e:028e), which Wine's winebus (SDL or
hidraw) turns into an XInput pad the same way as a real one plugged in
without Steam Input. It exists only while this script runs.

    vpad.py [--count N] [--destroy-after S] COMMAND [ARGS]

    tap BTN [--hold S]      press BTN, release it S seconds later (0.1)
    hold BTN                press BTN and keep it held
    release BTN             release BTN
    axis AX V               LX LY RX RY: -32768..32767 (up and right
                            positive, as on XInput); LT RT: 0..255
    idle                    do nothing (the device just exists)
    seq FILE                one command per line from FILE ('-' = stdin),
                            '#' comments, plus:
                              sleep S
                              waitfile TEXT [TIMEOUT]  until some process of
                                this user has a file open whose path contains
                                TEXT (any case); for a game run with no script
                                this is how a movie opening is seen
                              repeat N EVERY CMD...    CMD N times, EVERY s apart

    BTN  A B X Y LB RB START BACK GUIDE LTHUMB RTHUMB UP DOWN LEFT RIGHT
         (LB = WHITE, RB = BLACK on the Xbox side)

    --count N           create N devices (Wine numbers them as XInput user
                        indices 0..N-1); commands go to device 0, or to
                        device K with a "K:" prefix on the command (1:tap A)
    --destroy-after S   destroy the devices S seconds after they were
                        created, whatever the command is doing; after the
                        command ends they are kept until then (without it,
                        they are destroyed when the command ends)
    --lock-owner TEXT   run-ownership guard: create the devices only while the
                        host's run lock text (~/.recomp-run.lock or $RECOMP_RUN_LOCK, the line
                        blinx2 bench writes when a run takes the lock) contains
                        TEXT, e.g. a stamp or "recomp-inspike/cat/bench-logs/";
                        exit 3 if it names another run. Once matched, that
                        exact line is pinned: when the lock text changes (the
                        next run, whoever's, took the lock) the devices are
                        destroyed at once and the exit status is 3, so a pad
                        never reaches someone else's game
    --lock-wait S       with --lock-owner: wait up to S seconds for a run
                        matching TEXT to take the lock (a line written after
                        vpad started), so the pads exist before the game
                        launches; exit 3 on timeout

Under Proton with a Steam client running, Steam adds an inert virtual pad
(28de:11ff) per uinput device on the low XInput indices; runs that use this
pad set PROTON_NO_STEAMINPUT=1 in the game's environment (bench only;
players keep Steam Input). See input-real-devices design.md, Spike result.

Every action is printed with CLOCK_REALTIME ("wall=<s>"), the clock the
game's [INPUT] host lines carry, so press-to-poll latency is a subtraction.
Refuses (exit 2) when /dev/uinput is not writable; it never escalates.
Exit 1 when a device cannot be created or a command fails.
Never touches xemu: it only creates its own devices and reads /proc.
"""

import argparse
import os
import shlex
import signal
import sys
import threading
import time
import traceback

PAD_NAME = "Microsoft X-Box 360 pad"
PAD_BUS, PAD_VID, PAD_PID, PAD_VER = 0x03, 0x045E, 0x028E, 0x0110

STICKS = {"LX": "ABS_X", "LY": "ABS_Y", "RX": "ABS_RX", "RY": "ABS_RY"}
TRIGGERS = {"LT": "ABS_Z", "RT": "ABS_RZ"}
KEYS = {
    "A": "BTN_A",
    "B": "BTN_B",
    "X": "BTN_X",
    "Y": "BTN_Y",
    "LB": "BTN_TL",
    "RB": "BTN_TR",
    "START": "BTN_START",
    "BACK": "BTN_SELECT",
    "GUIDE": "BTN_MODE",
    "LTHUMB": "BTN_THUMBL",
    "RTHUMB": "BTN_THUMBR",
}
HAT = {
    "UP": ("ABS_HAT0Y", -1),
    "DOWN": ("ABS_HAT0Y", 1),
    "LEFT": ("ABS_HAT0X", -1),
    "RIGHT": ("ABS_HAT0X", 1),
}

_out_lock = threading.Lock()


def say(*a):
    with _out_lock:
        print("[VPAD] wall=%.6f" % time.clock_gettime(time.CLOCK_REALTIME), *a, flush=True)


class Pad:
    def __init__(self, idx):
        from evdev import AbsInfo, UInput
        from evdev import ecodes as e

        self.e, self.idx = e, idx
        stick = AbsInfo(0, -32768, 32767, 16, 128, 0)
        trig = AbsInfo(0, 0, 255, 0, 0, 0)
        hat = AbsInfo(0, -1, 1, 0, 0, 0)
        caps = {
            e.EV_KEY: [getattr(e, k) for k in KEYS.values()],
            e.EV_ABS: [
                (e.ABS_X, stick),
                (e.ABS_Y, stick),
                (e.ABS_RX, stick),
                (e.ABS_RY, stick),
                (e.ABS_Z, trig),
                (e.ABS_RZ, trig),
                (e.ABS_HAT0X, hat),
                (e.ABS_HAT0Y, hat),
            ],
        }
        self.ui = UInput(
            caps, name=PAD_NAME, vendor=PAD_VID, product=PAD_PID, version=PAD_VER, bustype=PAD_BUS
        )
        self.lock = threading.Lock()
        say("pad %d created %s" % (idx, self.ui.device.path if self.ui.device else "?"))

    def _write(self, typ, code, val):
        with self.lock:
            self.ui.write(typ, code, val)
            self.ui.syn()

    def button(self, name, down):
        e = self.e
        if name in KEYS:
            self._write(e.EV_KEY, getattr(e, KEYS[name]), 1 if down else 0)
        elif name in HAT:
            code, v = HAT[name]
            self._write(e.EV_ABS, getattr(e, code), v if down else 0)
        else:
            raise ValueError("unknown button %r" % name)
        say("pad %d %s %s" % (self.idx, "press" if down else "release", name))

    def axis(self, name, v):
        e = self.e
        if name in STICKS:
            v = max(-32768, min(32767, v))
            # evdev Y axes point down; XInput's (and the Duke's) point up.
            if name in ("LY", "RY"):
                v = max(-32768, min(32767, -v - 1 if v else 0))
            code = STICKS[name]
        elif name in TRIGGERS:
            v = max(0, min(255, v))
            code = TRIGGERS[name]
        else:
            raise ValueError("unknown axis %r" % name)
        self._write(e.EV_ABS, getattr(e, code), v)
        say("pad %d axis %s %d" % (self.idx, name, v))

    def close(self):
        with self.lock:
            self.ui.close()
        say("pad %d destroyed" % self.idx)


def open_files_matching(text):
    """Paths containing text (any case) that this user's processes hold open."""
    text = text.lower()
    me = os.getuid()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            if os.stat("/proc/" + pid).st_uid != me:
                continue
            fds = os.listdir("/proc/%s/fd" % pid)
        except OSError:
            continue
        for fd in fds:
            try:
                path = os.readlink("/proc/%s/fd/%s" % (pid, fd))
            except OSError:
                continue
            if text in path.lower():
                return pid, path
    return None


def run_cmd(pads, words, stop):
    """One command; returns False when the sequence should end."""
    if not words:
        return True
    target = 0
    if ":" in words[0] and words[0].split(":", 1)[0].isdigit():
        t, words[0] = words[0].split(":", 1)
        target = int(t)
    if target >= len(pads):
        raise ValueError("no pad %d (--count %d)" % (target, len(pads)))
    pad = pads[target]
    cmd, args = words[0].lower(), words[1:]
    if cmd == "tap":
        hold = 0.1
        if "--hold" in args:
            i = args.index("--hold")
            hold = float(args[i + 1])
            del args[i : i + 2]
        pad.button(args[0].upper(), True)
        stop.wait(hold)
        pad.button(args[0].upper(), False)
    elif cmd == "hold":
        pad.button(args[0].upper(), True)
    elif cmd == "release":
        pad.button(args[0].upper(), False)
    elif cmd == "axis":
        pad.axis(args[0].upper(), int(args[1], 0))
    elif cmd == "idle":
        pass
    elif cmd == "sleep":
        stop.wait(float(args[0]))
    elif cmd == "waitfile":
        timeout = float(args[1]) if len(args) > 1 else 1e9
        end = time.monotonic() + timeout
        say("waitfile %s (timeout %gs)" % (args[0], timeout))
        while not stop.is_set():
            hit = open_files_matching(args[0])
            if hit:
                say("waitfile %s: open in pid %s: %s" % (args[0], hit[0], hit[1]))
                return True
            if time.monotonic() >= end:
                say("waitfile %s: TIMEOUT" % args[0])
                return True
            stop.wait(0.05)
    elif cmd == "repeat":
        n, every = int(args[0]), float(args[1])
        for i in range(n):
            if stop.is_set():
                break
            t0 = time.monotonic()
            run_cmd(pads, list(args[2:]), stop)
            if i + 1 < n:
                stop.wait(max(0.0, every - (time.monotonic() - t0)))
    elif cmd == "seq":
        f = sys.stdin if args[0] == "-" else open(args[0])
        for line in f:
            if stop.is_set():
                break
            line = line.split("#", 1)[0].strip()
            if line:
                run_cmd(pads, shlex.split(line), stop)
    else:
        raise ValueError("unknown command %r" % cmd)
    return True


LOCK_PATH = os.environ.get("RECOMP_RUN_LOCK") or os.path.expanduser("~/.recomp-run.lock")


def lock_line():
    try:
        with open(LOCK_PATH) as f:
            return f.read().strip(), os.stat(LOCK_PATH).st_mtime
    except OSError:
        return "", 0.0


def wait_lock_owner(text, wait, stop):
    """The lock line naming a run that matches text, or None (message printed).
    With wait > 0, only a line written after this started counts."""
    t0 = time.time()
    end = time.monotonic() + wait
    while True:
        line, mtime = lock_line()
        if text in line and (wait <= 0 or mtime >= t0 - 1.0):
            say("lock owner: %s" % line)
            return line
        if wait <= 0 or time.monotonic() >= end or stop.is_set():
            print(
                "vpad: the run lock names another run (%r), not %r; "
                "not creating a device" % (line, text),
                file=sys.stderr,
            )
            return None
        stop.wait(0.1)


def guard_lock_owner(owner, stop, lost):
    while not stop.is_set():
        line, _ = lock_line()
        if line != owner:
            say("lock owner changed to: %s; destroying the device(s)" % line)
            lost.set()
            stop.set()
            return
        stop.wait(0.2)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1],
    )
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--destroy-after", type=float)
    ap.add_argument("--lock-owner")
    ap.add_argument("--lock-wait", type=float, default=0.0)
    ap.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    if not a.command:
        ap.error("no command")
    if not os.access("/dev/uinput", os.W_OK):
        print(
            "vpad: /dev/uinput is not writable by this user (%s); not creating "
            "a device. Give the user access (e.g. a uaccess/ACL rule) instead "
            "of running this as root." % os.getuid(),
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        import evdev  # noqa: F401
    except ImportError:
        print("vpad: python-evdev is not installed", file=sys.stderr)
        sys.exit(2)

    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    owner = None
    if a.lock_owner:
        owner = wait_lock_owner(a.lock_owner, a.lock_wait, stop)
        if owner is None:
            sys.exit(3)
    pads = []
    rc = 0
    lost = threading.Event()
    try:
        try:
            for i in range(a.count):
                pads.append(Pad(i))
        except Exception:
            traceback.print_exc()
            print("vpad: could not create pad %d" % len(pads), file=sys.stderr)
            rc = 1
            return
        if owner is not None:
            threading.Thread(target=guard_lock_owner, args=(owner, stop, lost), daemon=True).start()
        t_end = time.monotonic() + a.destroy_after if a.destroy_after else None
        if t_end:
            threading.Timer(a.destroy_after, stop.set).start()
        try:
            run_cmd(pads, list(a.command), stop)
        except (ValueError, IndexError, OSError) as ex:
            print("vpad: %s" % ex, file=sys.stderr)
            rc = 1
        if t_end and not stop.is_set():
            say("command done; keeping the device(s) until destroy-after")
            stop.wait()
    finally:
        for p in pads:
            p.close()
        if lost.is_set():
            rc = 3
        os._exit(rc)  # the destroy-after timer thread may still be pending


if __name__ == "__main__":
    main()
