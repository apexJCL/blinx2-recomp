#!/usr/bin/env python3
"""Tests for scripts/soak.py: the script generator, and run_one against fake games.

uv run pytest scripts/test_soak.py
"""

import os
import re
import signal
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import soak  # noqa: E402

ST5 = os.path.join(HERE, "shots", "pad", "st5.txt")
_BUTTONS = {
    "UP",
    "DOWN",
    "LEFT",
    "RIGHT",
    "START",
    "BACK",
    "LTHUMB",
    "RTHUMB",
    "A",
    "B",
    "X",
    "Y",
    "BLACK",
    "WHITE",
    "L",
    "R",
    "LX",
    "LY",
    "RX",
    "RY",
}


def test_prefix_stops_at_the_first_gameplay_line(tmp_path):
    p = tmp_path / "pre.txt"
    p.write_text(
        "# nav\nwait open a.sfd\n\ntap A until mem 0x10 == 1\nwait 2\nLX=1;A/0.3\nwait 9\n"
    )
    assert soak.load_prefix(str(p)) == ["wait open a.sfd", "tap A until mem 0x10 == 1", "wait 2"]


def test_st5_prefix_is_the_stage_select_jump():
    pre = soak.load_prefix(ST5)
    assert "poke 0x5eb638 0x14" in pre
    assert pre[-1] == "wait 2"
    assert not any("LX=" in s for s in pre)


def test_gen_is_seeded_and_long_enough():
    pre = soak.load_prefix(ST5)
    a, b, c = (soak.gen(pre, s, 2) for s in (7, 7, 8))
    assert a == b and a != c
    play = a.splitlines()[1 + len(pre) :]
    assert sum(soak._block_secs(line) for line in play) >= 120


def test_gen_emits_only_known_actions():
    pre = soak.load_prefix(ST5)
    for seed in range(20):
        for line in soak.gen(pre, seed, 3).splitlines()[1 + len(pre) :]:
            for part in line.split(";"):
                if part.startswith("wait "):
                    float(part[5:])
                    continue
                for act in part.split(","):
                    m = re.fullmatch(r"-?([A-Z]+)(=-?\d+|/[0-9.]+)?", act)
                    assert m and m.group(1) in _BUTTONS, act


def test_trace_and_debug_lists_join():
    base = {"RECOMP_TRACE": "flip", "RECOMP_DEBUG": "fb_dump=x/", "RECOMP_PB_BACKEND": "metal"}
    extra = {"RECOMP_DEBUG": "dpc_on_raise=0", "RECOMP_PB_BACKEND": "cpu"}
    out = soak.merge_env(base, extra)
    assert out == {"RECOMP_DEBUG": "fb_dump=x/,dpc_on_raise=0", "RECOMP_PB_BACKEND": "cpu"}


# run_one against fake games: small Python scripts that print the log lines
# soak.py reads (`[GPU] flip N`, `[INPUT] ... script done`, `[CRASH]`).
_FAKE = """\
import os, sys, time
mode = os.environ["FAKE_MODE"]
open(os.environ["FAKE_PID"], "w").write(str(os.getpid()))
n = 0
def flip():
    global n
    n += 1
    print(f"[METAL] flip {n} 0 ms", flush=True)
    print(f"[GPU] flip {n} 0 ms fence 0x0", flush=True)
while True:
    if mode == "noflip":
        time.sleep(0.05)
        continue
    if mode == "stall" and n >= 3:
        time.sleep(0.05)
        continue
    flip()
    if mode == "exit3":
        sys.exit(3)
    if mode == "crash" and n == 3:
        print("[CRASH] Access violation at 0xFE0001D8", flush=True)
        sys.exit(1)
    if mode == "done" and n == 5:
        print("[INPUT] t=0.250 script done", flush=True)
    time.sleep(0.05)
"""


def _fake(tmp_path, monkeypatch):
    exe = tmp_path / "fake_game"
    exe.write_text(f"#!{sys.executable}\n" + _FAKE)
    exe.chmod(0o755)
    monkeypatch.setattr(soak, "POLL", 0.1)
    monkeypatch.setattr(soak, "DUMP_SECS", 0.2)
    monkeypatch.setattr(soak, "REPORTS_DIR", str(tmp_path / "reports"))
    return str(exe)


def _run(tmp_path, monkeypatch, mode, cap=3.0):
    exe = _fake(tmp_path, monkeypatch)
    rundir = tmp_path / "run"
    env = {"FAKE_MODE": mode, "FAKE_PID": str(tmp_path / "pid")}
    return soak.run_one(exe, "s.txt", str(rundir), cap, "metal", 1.0, env, grace=0.5, ips_wait=0)


def test_run_ends_a_grace_after_script_done(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, "done", cap=20)
    assert res["verdict"] == "ok"
    assert res["done"] == 0.25 and res["secs"] < 5
    # [METAL] and [GPU] lines for the same flip count once
    log = (tmp_path / "run" / "log.txt").read_text()
    assert res["flips"] == log.count("[GPU] flip ") >= 5


def test_cap_without_script_done_is_incomplete(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, "flip")["verdict"] == "INCOMPLETE"


def test_flips_that_stop_are_a_stall(tmp_path, monkeypatch):
    # the fake dies of our SIGUSR1 (rc -30): still STALL, not CRASH
    res = _run(tmp_path, monkeypatch, "stall")
    assert res["verdict"] == "STALL" and res["flips"] == 3


def test_no_flip_at_all_is_a_stall(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, "noflip")["verdict"] == "STALL"


def test_an_exit_of_its_own_is_exit(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, "exit3")
    assert res["verdict"] == "EXIT" and res["rc"] == 3


def test_crash_line_is_crash(tmp_path, monkeypatch):
    res = _run(tmp_path, monkeypatch, "crash")
    assert res["verdict"] == "CRASH" and "0xFE0001D8" in res["crash"]


def test_crash_report_is_copied(tmp_path, monkeypatch):
    exe = _fake(tmp_path, monkeypatch)
    reports = tmp_path / "reports"
    reports.mkdir()
    real = soak._reports
    calls = []

    def late_report(e):
        # the .ips shows up only after a few polls, as ReportCrash does
        calls.append(1)
        if len(calls) == 3:
            (reports / "fake_game-2026-10-11.ips").write_text("{}")
        return real(e)

    monkeypatch.setattr(soak, "_reports", late_report)
    env = {"FAKE_MODE": "exit3", "FAKE_PID": str(tmp_path / "pid")}
    res = soak.run_one(exe, "s.txt", str(tmp_path / "run"), 3, "metal", 1, env, ips_wait=5)
    assert res["reports"] == ["fake_game-2026-10-11.ips"]
    assert (tmp_path / "run" / "fake_game-2026-10-11.ips").exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="soak.py run is macOS only")
def test_sigterm_to_soak_stops_the_game(tmp_path, monkeypatch):
    exe = _fake(tmp_path, monkeypatch)
    pidf = tmp_path / "pid"
    out = tmp_path / "out"
    p = subprocess.Popen(
        [
            sys.executable,
            os.path.join(HERE, "soak.py"),
            "run",
            ST5,
            "--runs",
            "1",
            "--minutes",
            "0.05",
            "--out",
            str(out),
            "--exe",
            exe,
            "FAKE_MODE=flip",
            f"FAKE_PID={pidf}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(100):
        if pidf.exists() and pidf.read_text():
            break
        time.sleep(0.05)
    game = int(pidf.read_text())
    p.send_signal(signal.SIGTERM)
    p.wait(20)
    for _ in range(100):
        try:
            os.kill(game, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        os.kill(game, signal.SIGKILL)
        raise AssertionError("the game outlived soak.py")
    assert "interrupted" in (out / "summary.txt").read_text()


def test_existing_run_dir_and_bad_env_are_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")
    (tmp_path / "run-01").mkdir()
    with pytest.raises(SystemExit) as e:
        soak.main(["run", ST5, "--runs", "1", "--out", str(tmp_path)])
    assert e.value.code == 2 and "exists" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        soak.main(["run", ST5, "--out", str(tmp_path / "x"), "NOEQUALS"])
    assert e.value.code == 2 and "ENV=VALUE" in capsys.readouterr().err


def test_run_is_refused_off_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert soak.main(["run", ST5, "--out", str(tmp_path)]) == 2
    assert not (tmp_path / "run-01").exists()
