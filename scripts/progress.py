"""The progress view for `blinx2 package` (and plain `blinx2`): which step of
the plan is running, how far along it is, and the child's latest line, with
every child's full output in build-logs/. Standard library only, Python 3.9
or newer.

Three modes:
  tty    two lines repainted in place (ANSI cursor-up and erase-line);
  line   one line rewritten with \\r, for a console without ANSI;
  plain  one line per step start and end, and every 10% at most: nothing
         is rewritten (--plain, not a TTY, CI set, TERM=dumb, --verbose).

The bar moves only on real progress parsed from what the tools print today:
Ninja's [n/m] (through NINJA_STATUS), recomp's "Translating N functions..."
and "[i/n]", disasm's NN%, makensis's File: lines, hdiutil's PERCENT:, and
download bytes. Recomp reports every 500 functions, so between ticks the
view shows an ETA from the step's last duration on this machine
(build-logs/timings.json), as text, never as bar.
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

KEEP_RUNS = 20
TAIL_LINES = 40
REPAINT_S = 0.1


# ── parsers: fragment -> (done, total) or None ───────────────────────────

class Parser:
    """Base: no progress, only lines."""
    def feed(self, text):
        return None


class NinjaParser(Parser):
    """'[612/1480] Building C object ...' (NINJA_STATUS="[%f/%t] "). The
    total can change while Ninja re-counts edges; the latest wins."""
    RE = re.compile(r"^\[(\d+)/(\d+)\] ")

    def feed(self, text):
        m = self.RE.match(text)
        return (int(m.group(1)), int(m.group(2))) if m else None


class RecompParser(Parser):
    """'Translating 41234 functions...' sets the total; '  [500/41234]
    Translating name...' advances it."""
    TOTAL = re.compile(r"^\s*Translating (\d+) functions")
    TICK = re.compile(r"^\s*\[(\d+)/(\d+)\] Translating ")

    def __init__(self):
        self.total = None

    def feed(self, text):
        m = self.TICK.match(text)
        if m:
            self.total = int(m.group(2))
            return int(m.group(1)), self.total
        m = self.TOTAL.match(text)
        if m:
            self.total = int(m.group(1))
            return 0, self.total
        return None


class PercentParser(Parser):
    """disasm's '  .text: 0x00012345 ... 42%' lines, which arrive through \\r."""
    RE = re.compile(r"^\s*\S+:.*?(\d{1,3})%\s*$")

    def feed(self, text):
        m = self.RE.match(text)
        return (min(100, int(m.group(1))), 100) if m else None


class MakensisParser(Parser):
    """makensis -V3: one 'File: "name" ...' line per file it adds."""
    RE = re.compile(r'^\s*File: "')

    def __init__(self, total):
        self.total, self.done = max(1, total), 0

    def feed(self, text):
        if self.RE.match(text):
            self.done += 1
            return min(self.done, self.total), self.total
        return None


class HdiutilParser(Parser):
    """hdiutil -puppetstrings: 'PERCENT:42.5'; -1 means 'no estimate' and
    comes at the end, so it is not an error."""
    RE = re.compile(r"^PERCENT:(-?[\d.]+)")

    def feed(self, text):
        m = self.RE.match(text)
        if not m:
            return None
        p = float(m.group(1))
        return (100, 100) if p < 0 else (int(min(100.0, p)), 100)


def parser_for(argv):
    """The parser for a child, from its command line."""
    words = [os.path.basename(str(a)) for a in argv]
    joined = " ".join(str(a) for a in argv)
    if "--build" in words:
        return NinjaParser()
    if "tools.recomp" in joined.split():
        return RecompParser()
    if "tools.disasm" in joined.split():
        return PercentParser()
    if words and words[0].startswith("hdiutil"):
        return HdiutilParser()
    return Parser()


# ── the view ─────────────────────────────────────────────────────────────

def enable_vt():
    """Windows: turn on ANSI handling in this console; False if it can't."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not k.GetConsoleMode(h, ctypes.byref(mode)):
            return False
        return bool(k.SetConsoleMode(h, mode.value | 0x0004))
    except (AttributeError, OSError):
        return False


def choose_mode(plain=False, stream=None, env=None, vt=enable_vt):
    stream = stream or sys.stdout
    env = os.environ if env is None else env
    if plain or env.get("CI") or env.get("TERM") == "dumb":
        return "plain"
    try:
        if not stream.isatty():
            return "plain"
    except (AttributeError, ValueError):
        return "plain"
    return "tty" if vt() else "line"


def fmt_time(s):
    s = int(s)
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 \
        else "%d:%02d" % (s // 60, s % 60)


class View:
    def __init__(self, mode="plain", stream=None, logs=None, clock=time.monotonic):
        self.mode = mode
        self.out = stream or sys.stdout
        enc = (getattr(self.out, "encoding", "") or "").lower().replace("-", "")
        self.utf8 = enc == "utf8"
        self.g_full, self.g_empty, self.g_ok, self.g_spin = \
            ("█", "░", "✓", "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏") \
            if self.utf8 else ("#", "-", "ok", "|/-\\")
        self.logs = logs
        self.clock = clock
        self.stamp = time.strftime("%Y%m%d-%H%M%S")
        self.stage = ""            # "[3/4] build"
        self.label = None          # the running step
        self.t0 = 0.0
        self.done = self.total = None
        self.last = ""
        self.drawn = 0             # lines of live area on screen (tty)
        self.last_paint = 0.0
        self.last_pct = -10
        self.spin = 0
        self.timings = self._load_timings()

    # -- output primitives
    def _w(self, s):
        self.out.write(s)
        self.out.flush()

    def _clear(self):
        """Erase the live area; the cursor ends at the start of its first
        line (the area never ends in a newline, so it sits on its last)."""
        if self.mode == "tty" and self.drawn:
            self._w("\r\x1b[2K" + "\x1b[1A\x1b[2K" * (self.drawn - 1))
        elif self.mode == "line" and self.drawn:
            self._w("\r" + " " * (self.width() - 1) + "\r")
        self.drawn = 0

    def width(self):
        return max(40, shutil.get_terminal_size((100, 24)).columns)

    def say(self, msg=""):
        """A permanent line, above the live area."""
        self._clear()
        for line in str(msg).split("\n"):
            self._w(line + "\n")
        self.paint(force=True)

    # -- steps
    def set_stage(self, text):
        self.end(True)          # the last step of the previous stage is done
        self.stage = text
        if self.mode == "plain":
            self.say("== %s ==" % text)
        else:
            self.paint(force=True)

    def begin(self, label):
        if self.label:
            self.end(True)
        self.label, self.t0 = label, self.clock()
        self.done = self.total = None
        self.last, self.last_pct = "", -10
        if self.mode == "plain":
            self.say("  %s ..." % label)
        else:
            self.paint(force=True)

    def end(self, ok=True):
        if not self.label:
            return
        took = self.clock() - self.t0
        if ok:
            self.timings[self.label] = round(took, 1)
            self._save_timings()
        label, self.label = self.label, None
        mark = self.g_ok if ok else "FAILED"
        self.say("  %s %s  %s" % (mark, label, fmt_time(took)))

    def progress(self, done, total):
        self.done, self.total = done, total
        if self.mode == "plain" and total:
            pct = int(100 * done / total)
            if pct >= self.last_pct + 10 or done == total and pct != self.last_pct:
                self.last_pct = pct
                self.say("  %s: %d%% (%d/%d)" % (self.label, pct, done, total))
        else:
            self.paint()

    def line(self, text):
        text = text.strip()
        if text:
            self.last = text
            self.paint()

    def eta(self):
        """'~7 min left' from the last run's duration, or ''."""
        prev = self.timings.get(self.label or "")
        if not prev or not self.label:
            return ""
        el = self.clock() - self.t0
        if self.total and self.done:
            left = prev * (1 - self.done / float(self.total))
            left = min(left, max(0.0, prev - el)) if el < prev else left
        else:
            left = prev - el
        if left <= 60:
            return "under a minute left" if left > 0 else ""
        return "~%d min left" % round(left / 60.0)

    def paint(self, force=False):
        if self.mode == "plain":
            return
        now = self.clock()
        if not force and now - self.last_paint < REPAINT_S:
            return
        self.last_paint = now
        w = self.width()
        el = fmt_time(now - self.t0) if self.label else ""
        head = "%s  %s" % (self.stage, self.label or "")
        if self.total:
            bar_w = max(10, min(30, w // 4))
            fill = int(bar_w * min(1.0, self.done / float(self.total)))
            bar = self.g_full * fill + self.g_empty * (bar_w - fill)
            body = "%s  %d/%d" % (bar, self.done, self.total)
        elif self.label:
            self.spin = (self.spin + 1) % len(self.g_spin)
            body = self.g_spin[self.spin]
        else:
            body = ""
        eta = self.eta()
        status = "  ".join(x for x in (head, body, el, eta) if x)
        if self.mode == "line":
            self._clear()
            self._w(status[:w - 1])
            self.drawn = 1
            return
        self._clear()
        lines = [status[:w - 1], ("      " + self.last)[:w - 1]]
        self._w("\n".join(lines))
        self.drawn = len(lines)

    def close(self):
        self._clear()

    # -- timings
    def _timings_path(self):
        return os.path.join(self.logs, "timings.json") if self.logs else None

    def _load_timings(self):
        p = self._timings_path()
        try:
            with open(p) as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _save_timings(self):
        p = self._timings_path()
        if not p:
            return
        try:
            os.makedirs(self.logs, exist_ok=True)
            with open(p + ".tmp", "w") as f:
                json.dump(self.timings, f, indent=1, sort_keys=True)
            os.replace(p + ".tmp", p)
        except OSError:
            pass

    def log_path(self, label):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "step"
        return os.path.join(self.logs, "%s-%s.log" % (self.stamp, safe))


def split_fragments(buf):
    """Complete fragments of a byte buffer split on \\r and \\n, and the
    incomplete rest."""
    parts = re.split(rb"[\r\n]", buf)
    return parts[:-1], parts[-1]


def run_step(view, argv, cwd=None, env=None, parser=None, verbose=False):
    """Run argv with its output (stdout and stderr in one stream) teed to the
    step's log; feed the parser and the view. Returns the exit code; on
    failure the view shows the log's tail and path."""
    parser = parser or parser_for(argv)
    # A Python tool writes its stdout through a block buffer into a pipe:
    # recomp's [i/n] lines would arrive all at once, at the end.
    env = dict(os.environ if env is None else env)
    env.setdefault("PYTHONUNBUFFERED", "1")
    os.makedirs(view.logs, exist_ok=True)
    log_path = view.log_path(view.label or os.path.basename(str(argv[0])))
    tail = []
    q = queue.Queue()
    with open(log_path, "ab") as log:
        log.write(("$ %s\n" % " ".join(str(a) for a in argv)).encode("utf-8", "replace"))
        log.flush()
        p = subprocess.Popen([str(a) for a in argv], cwd=cwd, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

        def reader():
            buf = b""
            for chunk in iter(lambda: p.stdout.read1(65536) if hasattr(p.stdout, "read1")
                              else p.stdout.read(4096), b""):
                log.write(chunk)
                frags, buf = split_fragments(buf + chunk)
                for f in frags:
                    q.put(f)
            if buf:
                q.put(buf)
            q.put(None)
        t = threading.Thread(target=reader, daemon=True)
        t.start()
        # Ctrl-C (or any error in the view) must not leave the child running
        # or the reader writing into the log after it closes. The caller
        # reports the interrupt; the view's failure tail is for exit codes.
        try:
            while True:
                try:
                    frag = q.get(timeout=REPAINT_S)
                except queue.Empty:
                    view.paint()
                    continue
                if frag is None:
                    break
                text = frag.decode("utf-8", "replace")
                if not text.strip():
                    continue
                tail.append(text)
                del tail[:-TAIL_LINES]
                if verbose:
                    view.say(text)
                got = parser.feed(text)
                if got:
                    view.progress(*got)
                view.line(text)
        except BaseException:
            p.kill()
            p.wait()
            # A grandchild (Ninja's compilers) can hold the pipe open a little
            # longer; it got the same Ctrl-C from the terminal, so wait briefly.
            t.join(timeout=5)
            raise
        t.join()
        rc = p.wait()
    if rc != 0:
        view.end(False)
        view.say("%s failed (exit %d); the last lines:" % (os.path.basename(str(argv[0])), rc))
        view.say("\n".join("  " + l for l in tail))
        view.say("full log: %s" % log_path)
    return rc


def prune_logs(logs, keep=KEEP_RUNS):
    """Keep the newest `keep` run stamps' logs; only <stamp>-*.log files in
    logs/ itself are ever removed."""
    pat = re.compile(r"^(\d{8}-\d{6})-.*\.log$")
    try:
        names = os.listdir(logs)
    except OSError:
        return []
    stamps = sorted({m.group(1) for m in map(pat.match, names) if m}, reverse=True)
    old = set(stamps[keep:])
    gone = []
    for n in names:
        m = pat.match(n)
        p = os.path.join(logs, n)
        if m and m.group(1) in old and os.path.isfile(p) and not os.path.islink(p):
            os.remove(p)
            gone.append(n)
    return gone
