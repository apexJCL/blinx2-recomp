#!/usr/bin/env python3
"""bench.sh hold_run_lock: the script it sends to the host, run here with
stub systemctl and systemd-run on PATH and a scratch HOME. Plain asserts;
runs alone or under pytest.

  python3 scripts/test_bench_hold.py
  python3 -m pytest scripts/test_bench_hold.py
"""

import os
import re
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "bench.sh")


def host_script():
    """The heredoc hold_run_lock pipes to the host."""
    text = open(BENCH).read()
    fn = text[text.index("hold_run_lock() {"):]
    m = re.search(r"cat <<'EOF'\n(.*?)\nEOF\n", fn, re.S)
    assert m, "hold_run_lock heredoc not found"
    return m.group(1)


def stub(bindir, name, body):
    p = os.path.join(bindir, name)
    with open(p, "w") as f:
        f.write("#!/bin/sh\n" + body + "\n")
    os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR)


def run(home, systemd_run_body):
    bindir = os.path.join(home, "bin")
    os.makedirs(bindir, exist_ok=True)
    log = os.path.join(home, "calls.log")
    stub(bindir, "systemctl", f'echo "systemctl $*" >> "{log}"')
    stub(bindir, "systemd-run", f'echo "systemd-run" >> "{log}"\n' + systemd_run_body)
    env = dict(os.environ, HOME=home, PATH=bindir + os.pathsep + os.environ["PATH"],
               XDG_RUNTIME_DIR=home)
    t0 = time.time()
    p = subprocess.run(["bash", "-s"], input="MAX=5\n" + host_script(), env=env,
                       capture_output=True, text=True, timeout=60)
    calls = open(log).read().splitlines() if os.path.exists(log) else []
    return p.returncode, time.time() - t0, calls


def test_leftover_holder_is_stopped_first():
    with tempfile.TemporaryDirectory() as home:
        rc, _, calls = run(home, 'touch "$HOME/.recomp-run.held"')
        assert rc == 0, calls
        assert calls[0] == "systemctl --user stop recomp-pacing-hold", calls
        assert calls[1] == "systemctl --user reset-failed recomp-pacing-hold", calls
        assert calls[2] == "systemd-run", calls
        assert os.path.exists(os.path.join(home, ".recomp-run.hold"))


def test_failed_launch_gives_up_at_once():
    with tempfile.TemporaryDirectory() as home:
        rc, dt, calls = run(home, "exit 1")
        assert rc == 75, (rc, calls)
        assert dt < 10, dt
        assert not os.path.exists(os.path.join(home, ".recomp-run.hold"))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    sys.exit(0)
