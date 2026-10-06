#!/usr/bin/env python3
"""Tests for progress.py with synthetic tool output and fake children (no
game data, no build). Plain asserts; runs alone or under pytest.

  python3 scripts/test_progress.py
  python3 -m pytest scripts/test_progress.py
"""

import io
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import progress as pg  # noqa: E402

try:
    import pytest
except ImportError:
    pytest = None
if pytest is not None:
    @pytest.fixture
    def d(tmp_path):
        return str(tmp_path)


class Out(io.StringIO):
    def __init__(self, tty=False, encoding="utf-8"):
        super().__init__()
        self._tty, self._enc = tty, encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._enc


def test_parsers():
    n = pg.NinjaParser()
    assert n.feed("[612/1480] Building C object x.o") == (612, 1480)
    assert n.feed("[613/1502] Linking") == (613, 1502)       # Ninja re-counted
    assert n.feed("ninja: no work to do.") is None
    r = pg.RecompParser()
    assert r.feed("Translating 41234 functions...") == (0, 41234)
    assert r.feed("  [500/41234] Translating sub_00012345...") == (500, 41234)
    assert r.feed("  wrote gen/recomp_0001.c") is None
    p = pg.PercentParser()
    assert p.feed("  .text: 0x00123456 (1234 functions) 42%") == (42, 100)
    assert p.feed("found 9000 functions") is None
    m = pg.MakensisParser(3)
    assert [m.feed(x) for x in ('File: "a.exe" [compress] 1/2 bytes', "Output: x",
                                 'File: "b" 1', 'File: "c"', 'File: "d"')] == \
        [(1, 3), None, (2, 3), (3, 3), (3, 3)]
    h = pg.HdiutilParser()
    assert h.feed("PERCENT:12.500000") == (12, 100)
    assert h.feed("PERCENT:-1.000000") == (100, 100)
    assert h.feed("created: x.dmg") is None
    assert isinstance(pg.parser_for(["cmake", "--build", "b"]), pg.NinjaParser)
    assert isinstance(pg.parser_for(["py", "-m", "tools.recomp", "x"]), pg.RecompParser)
    assert isinstance(pg.parser_for(["py", "-m", "tools.disasm", "x"]), pg.PercentParser)
    assert isinstance(pg.parser_for(["py", "-m", "tools.recomp.icall_feedback"]), pg.Parser)
    assert type(pg.parser_for(["codesign", "-s", "-"])) is pg.Parser


def test_mode_selection():
    yes = lambda: True     # noqa: E731
    no = lambda: False     # noqa: E731
    assert pg.choose_mode(False, Out(tty=True), {}, yes) == "tty"
    assert pg.choose_mode(False, Out(tty=True), {}, no) == "line"
    assert pg.choose_mode(True, Out(tty=True), {}, yes) == "plain"
    assert pg.choose_mode(False, Out(tty=False), {}, yes) == "plain"
    assert pg.choose_mode(False, Out(tty=True), {"CI": "1"}, yes) == "plain"
    assert pg.choose_mode(False, Out(tty=True), {"TERM": "dumb"}, yes) == "plain"


def test_ascii_glyphs():
    v = pg.View("tty", Out(tty=True, encoding="cp1252"))
    assert v.g_full == "#" and v.g_ok == "ok"
    v.set_stage("[1/1] build")
    v.begin("build")
    v.progress(5, 10)
    v.end(True)
    v.out.getvalue().encode("cp1252")    # nothing a cp1252 console cannot print
    assert pg.View("tty", Out(encoding="UTF-8")).g_full == "█"


def fake_child(d, body):
    p = os.path.join(d, "child.py")
    with open(p, "w") as f:
        f.write(body)
    return [sys.executable, p]


def test_plain_never_rewrites(d):
    out = Out()
    v = pg.View("plain", out, logs=os.path.join(d, "logs"))
    v.set_stage("[3/4] build")
    v.begin("build windows")
    argv = fake_child(d, "import sys\n"
                         "for i in range(1, 21):\n"
                         "    sys.stdout.write('[%d/20] Building C object o%d\\n' % (i, i))\n"
                         "sys.stdout.write('  .text: 0x1 50%\\r  .text: 0x2 60%\\r')\n")
    assert pg.run_step(v, argv + ["--build"], parser=pg.NinjaParser()) == 0
    v.end(True)
    text = out.getvalue()
    assert "\r" not in text and "\x1b" not in text, repr(text)
    pct = [l for l in text.splitlines() if l.strip().startswith("build windows:")]
    assert 2 <= len(pct) <= 11, pct           # every 10% at most
    assert "100% (20/20)" in pct[-1]
    # The full output, \r fragments included, is in the step's log.
    logs = [n for n in os.listdir(v.logs) if n.endswith(".log")]
    assert len(logs) == 1 and "build-windows" in logs[0]
    with open(os.path.join(v.logs, logs[0]), "rb") as f:
        raw = f.read()
    assert b"[20/20]" in raw and b"60%\r" in raw
    with open(os.path.join(v.logs, "timings.json")) as f:
        assert "build windows" in json.load(f)


def test_python_child_unbuffered(d):
    """A Python child's stdout reaches the parser while it runs."""
    out = Out()
    v = pg.View("plain", out, logs=os.path.join(d, "logs"))
    v.begin("recomp")
    seen = []
    real = v.progress
    v.progress = lambda a, b: (seen.append((a, time.monotonic())), real(a, b))
    argv = fake_child(d, "import time\n"
                         "print('Translating 2 functions...')\n"
                         "print('  [1/2] Translating f...')\n"
                         "time.sleep(0.6)\n"
                         "print('  [2/2] Translating g...')\n")
    assert pg.run_step(v, argv, parser=pg.RecompParser()) == 0
    assert [a for a, _ in seen] == [0, 1, 2]
    assert seen[2][1] - seen[1][1] > 0.4, seen     # the first tick came before the sleep


def test_failure_tail(d):
    out = Out()
    v = pg.View("plain", out, logs=os.path.join(d, "logs"))
    v.begin("recomp")
    argv = fake_child(d, "import sys\n"
                         "for i in range(100): print('line %d' % i)\n"
                         "sys.exit(3)\n")
    assert pg.run_step(v, argv) == 3
    text = out.getvalue()
    assert "failed (exit 3)" in text and "full log: " in text
    assert "line 99" in text and "line 60" in text and "line 59" not in text
    assert "FAILED recomp" in text


def test_silent_child_still_repaints(d):
    out = Out(tty=True)
    v = pg.View("tty", out, logs=os.path.join(d, "logs"))
    v.begin("recomp")
    paints = []
    real = v.paint
    v.paint = lambda force=False: (paints.append(1), real(force))
    argv = fake_child(d, "import time\ntime.sleep(1.0)\n")
    assert pg.run_step(v, argv) == 0
    assert len(paints) >= 5, len(paints)     # elapsed time ticks while it is silent
    assert "\x1b[2K" in out.getvalue()


def test_interrupt_reaps_child(d):
    """Ctrl-C while a child runs: the child is killed and reaped, the reader
    has stopped before the log closes, and no failure tail is shown."""
    out = Out()
    v = pg.View("plain", out, logs=os.path.join(d, "logs"))
    v.begin("recomp")
    pidf = os.path.join(d, "pid")
    argv = fake_child(d, "import os, time\n"
                         "open(%r, 'w').write(str(os.getpid()))\n"
                         "print('started', flush=True)\n"
                         "time.sleep(30)\n" % pidf)

    def interrupt(force=False):
        if os.path.exists(pidf):
            raise KeyboardInterrupt
    v.paint = interrupt
    threads = threading.active_count()
    t0 = time.monotonic()
    try:
        pg.run_step(v, argv)
        raise AssertionError("the interrupt was swallowed")
    except KeyboardInterrupt:
        pass
    assert time.monotonic() - t0 < 10
    with open(pidf) as f:
        pid = int(f.read())
    if os.name != "nt":      # signal 0 is a probe only on POSIX
        try:
            os.kill(pid, 0)
            raise AssertionError("child %d still exists" % pid)
        except ProcessLookupError:
            pass
    assert threading.active_count() == threads
    assert "failed" not in out.getvalue() and "FAILED" not in out.getvalue()


def test_no_match_stays_spinner(d):
    out = Out(tty=True)
    v = pg.View("tty", out, logs=os.path.join(d, "logs"))
    v.begin("codesign")
    argv = fake_child(d, "print('signed')\nprint('done 42% maybe')\n")
    assert pg.run_step(v, argv, parser=pg.NinjaParser()) == 0
    assert v.total is None
    assert v.last == "done 42% maybe"


def test_eta_text():
    t = [100.0]
    v = pg.View("tty", Out(tty=True), clock=lambda: t[0])
    v.timings = {"recomp": 600.0}
    v.begin("recomp")
    assert v.eta() == "~10 min left"
    t[0] += 300
    v.progress(1, 2)
    assert v.eta() == "~5 min left"
    t[0] += 290
    assert v.eta() == "under a minute left"
    v.begin("build")                 # no history: no ETA
    assert v.eta() == ""


def test_prune_logs(d):
    logs = os.path.join(d, "build-logs")
    os.makedirs(logs)
    stamps = ["20261005-%06d" % i for i in range(25)]
    for s in stamps:
        for step in ("build", "recomp"):
            open(os.path.join(logs, "%s-%s.log" % (s, step)), "w").close()
    for keep in ("timings.json", "notes.txt", "x-build.log"):
        open(os.path.join(logs, keep), "w").close()
    outside = os.path.join(d, "20200101-000000-build.log")
    open(outside, "w").close()
    gone = pg.prune_logs(logs, keep=20)
    assert len(gone) == 10
    left = sorted(os.listdir(logs))
    assert "timings.json" in left and "notes.txt" in left and "x-build.log" in left
    assert not any(n.startswith(tuple(stamps[:5])) for n in left)
    assert os.path.exists(outside)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        if t.__code__.co_argcount:
            with tempfile.TemporaryDirectory() as d:
                t(d)
        else:
            t()
        print("ok %s" % t.__name__)
    print("%d tests passed" % len(tests))


if __name__ == "__main__":
    main()
