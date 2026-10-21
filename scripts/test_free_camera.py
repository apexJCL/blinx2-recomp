#!/usr/bin/env python3
"""Tests for the free camera (camera.free, openspec change free-camera).

Compiles a driver against src/free_cam_fly.c and checks the fly maths
(dead zone, basis, speed and look multipliers, the pitch clamp, the dt cap)
and the freeze bookkeeping on 0xAF0EF4 (the entry guards, game writes kept
as the restore value, the drop paths giving the flag back). Then checks the
keys: every camera.* key has an env row, a docs/env.md row and a stock line
in packaging/config.default.toml, and the golden check knows camera.free's
stock value.

  python3 scripts/test_free_camera.py
  uv run pytest scripts/test_free_camera.py

The C tests skip when no C compiler is on PATH.
"""

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SRC = os.path.join(ROOT, "src")

KEYS = {
    "camera.free": ("RECOMP_CAMERA_FREE", "off"),
    "camera.free_speed": ("RECOMP_CAMERA_FREE_SPEED", 1.0),
    "camera.free_look_sens": ("RECOMP_CAMERA_FREE_LOOK_SENS", 1.0),
    "camera.free_hud": ("RECOMP_CAMERA_FREE_HUD", "keep"),
    "camera.free_toggle": ("RECOMP_CAMERA_FREE_TOGGLE", "F6"),
    "camera.free_hud_key": ("RECOMP_CAMERA_FREE_HUD_KEY", "F7"),
    "camera.free_freeze_key": ("RECOMP_CAMERA_FREE_FREEZE_KEY", "F8"),
    "camera.free_reset_key": ("RECOMP_CAMERA_FREE_RESET_KEY", "F5"),
}

# Each line: a command and its numbers; the driver prints one result line.
DRIVER = r"""
#include <stdio.h>
#include <string.h>
#include "free_cam_fly.h"

static struct fc_cam c;
static struct fc_input in;
static struct fc_params pr = { 1.0f, 1.0f };
static struct fc_freeze fz;

int main(void)
{
    char cmd[32];
    while (scanf("%31s", cmd) == 1) {
        if (!strcmp(cmd, "axis")) {
            int v, d;
            scanf("%d %d", &v, &d);
            printf("%.6f\n", fc_axis(v, d));
        } else if (!strcmp(cmd, "basis")) {
            float p, y, f[3], r[3];
            scanf("%f %f", &p, &y);
            fc_basis(p, y, f, r);
            printf("%.6f %.6f %.6f %.6f %.6f %.6f\n", f[0], f[1], f[2], r[0], r[1], r[2]);
        } else if (!strcmp(cmd, "cam")) {
            scanf("%f %f %f %f %f", &c.p[0], &c.p[1], &c.p[2], &c.pitch, &c.yaw);
            printf("ok\n");
        } else if (!strcmp(cmd, "par")) {
            scanf("%f %f", &pr.speed, &pr.look_sens);
            printf("ok\n");
        } else if (!strcmp(cmd, "in")) {
            memset(&in, 0, sizeof in);
            scanf("%f %f %f %f %f %f %d %d %f %f", &in.lx, &in.ly, &in.rx, &in.ry,
                  &in.up, &in.down, &in.fast, &in.slow, &in.mouse_dx, &in.mouse_dy);
            printf("ok\n");
        } else if (!strcmp(cmd, "step")) {
            float dt;
            scanf("%f", &dt);
            fc_fly_step(&c, &in, &pr, dt);
            printf("%.6f %.6f %.6f %.6f %.6f\n", c.p[0], c.p[1], c.p[2], c.pitch, c.yaw);
        } else if (!strcmp(cmd, "fzstart")) {
            unsigned run, menu, flag;
            scanf("%u %u %u", &run, &menu, &flag);
            printf("%d %d\n", fc_freeze_start(&fz, run, menu, flag), fz.on);
        } else if (!strcmp(cmd, "fztick")) {
            unsigned flag, run, menu;
            int wrote, r;
            scanf("%u %u %u", &flag, &run, &menu);
            r = fc_freeze_tick(&fz, flag, run, menu, &wrote);
            printf("%s %d %u %u %d\n", r == FC_FZ_KEEP ? "keep" : "drop", wrote,
                   (unsigned)fz.restore, fz.game_writes, fz.on);
        } else if (!strcmp(cmd, "fzstop")) {
            printf("%u %d\n", (unsigned)fc_freeze_stop(&fz), fz.on);
        } else if (!strcmp(cmd, "fzev")) {
            unsigned flag;
            int r;
            scanf("%u", &flag);
            r = fc_freeze_events(&fz, flag);
            printf("%d %u %u %d\n", r, (unsigned)fz.restore, fz.game_writes, fz.on);
        } else if (!strcmp(cmd, "fzpre")) {
            unsigned flag, v;
            int wrote;
            scanf("%u", &flag);
            v = fc_freeze_pre(&fz, flag, &wrote);
            printf("%u %d %u %d\n", v, wrote, fz.game_writes, fz.on);
        } else if (!strcmp(cmd, "fzdrop")) {
            printf("%u %d\n", (unsigned)fc_freeze_drop(&fz), fz.on);
        }
        fflush(stdout);
    }
    return 0;
}
"""


def _cc():
    return shutil.which("clang") or shutil.which("gcc") or shutil.which("cc")


def _run(lines):
    """Run the driver over the command lines; one output line each."""
    if not _cc():
        pytest.skip("no C compiler")
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "t.c"), os.path.join(d, "t")
        with open(c, "w") as f:
            f.write(DRIVER)
        subprocess.run(
            [
                _cc(),
                "-std=c11",
                "-Wall",
                "-Werror",
                "-Wno-unused-result",
                "-I",
                SRC,
                "-o",
                exe,
                c,
                os.path.join(SRC, "free_cam_fly.c"),
                "-lm",
            ],
            check=True,
        )
        out = subprocess.run(
            [exe], input="\n".join(lines) + "\n", check=True, capture_output=True, text=True
        ).stdout
    return out.splitlines()


def _floats(line):
    return [float(x) for x in line.split()]


def _close(a, b, tol=1e-4):
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


# ---- fly maths ---------------------------------------------------------------


def test_axis_dead_zone_and_range():
    out = _run(
        ["axis 0 7849", "axis 7849 7849", "axis -7849 7849", "axis 32767 7849"]
        + ["axis -32768 7849", "axis 20308 7849"]
    )
    v = [float(x) for x in out]
    assert v[0] == 0.0 and v[1] == 0.0 and v[2] == 0.0
    assert v[3] == 1.0 and v[4] == -1.0
    assert abs(v[5] - (20308 - 7849) / (32767 - 7849)) < 1e-5


def test_basis_matches_the_view_rows():
    # sub_0021B1F0's rows (free_cam_fly.c): forward (-sin y cos p, -sin p,
    # cos y cos p), right (cos y, 0, sin y); unit length and orthogonal.
    for p, y in ((0.0, 0.0), (-0.263, 0.0), (0.4, 1.2), (-1.4, -2.9)):
        f = _floats(_run([f"basis {p} {y}"])[0])
        want = [
            -math.sin(y) * math.cos(p),
            -math.sin(p),
            math.cos(y) * math.cos(p),
            math.cos(y),
            0.0,
            math.sin(y),
        ]
        assert _close(f, want)
        fwd, right = f[:3], f[3:]
        assert abs(sum(a * b for a, b in zip(fwd, right, strict=True))) < 1e-5


def test_forward_speed_and_multipliers():
    base = "cam 0 0 0 0 0"
    full_fwd = "in 0 1 0 0 0 0 0 0 0 0"
    out = _run([base, full_fwd, "step 0.05"])
    assert _close(_floats(out[2]), [0, 0, 80 * 0.05, 0, 0])
    out = _run([base, "par 2 1", "in 0 1 0 0 0 0 1 0 0 0", "step 0.05"])
    assert _close(_floats(out[3])[:3], [0, 0, 80 * 2 * 4 * 0.05])
    out = _run([base, "in 0 1 0 0 0 0 0 1 0 0", "step 0.05"])
    assert _close(_floats(out[2])[:3], [0, 0, 80 * 0.25 * 0.05])


def test_rise_is_minus_y():
    # The world is Y-down: rising (RT, X) lowers y.
    out = _run(["cam 0 0 0 0 0", "in 0 0 0 0 1 0 0 0 0 0", "step 0.1"])
    assert _close(_floats(out[2])[:3], [0, -8.0, 0])
    out = _run(["cam 0 0 0 0 0", "in 0 0 0 0 0 1 0 0 0 0", "step 0.1"])
    assert _close(_floats(out[2])[:3], [0, 8.0, 0])


def test_look_rates_and_sensitivity():
    out = _run(["cam 0 0 0 0 0", "in 0 0 1 1 0 0 0 0 0 0", "step 0.1"])
    p, y = _floats(out[2])[3:]
    assert abs(p - 0.18) < 1e-5 and abs(y + 0.18) < 1e-5
    out = _run(["cam 0 0 0 0 0", "par 1 2", "in 0 0 0 0 0 0 0 0 10 -10", "step 0.01"])
    p, y = _floats(out[3])[3:]
    assert abs(p - 2 * 10 * 0.0025) < 1e-5 and abs(y + 2 * 10 * 0.0025) < 1e-5


def test_pitch_clamped_and_dt_capped():
    out = _run(["cam 0 0 0 0 0", "in 0 0 0 1 0 0 0 0 0 0"] + ["step 0.1"] * 20)
    assert abs(_floats(out[-1])[3] - 1.5) < 1e-6
    # A two-second hitch moves no farther than FC_DT_MAX (0.1 s).
    out = _run(["cam 0 0 0 0 0", "in 0 1 0 0 0 0 0 0 0 0", "step 2.0"])
    assert _close(_floats(out[2])[:3], [0, 0, 8.0])
    # dt 0 or negative: nothing moves.
    out = _run(["cam 1 2 3 0.1 0.2", "in 1 1 1 1 1 0 0 0 5 5", "step 0", "step -1"])
    assert _close(_floats(out[2]), [1, 2, 3, 0.1, 0.2])
    assert _close(_floats(out[3]), [1, 2, 3, 0.1, 0.2])


# ---- freeze -------------------------------------------------------------------


def test_freeze_guards():
    # Only in a running stage (0x449F40 == 1), no menu (0xAE73B4 == 0),
    # no event stop (0xAF0EF4 == 0).
    assert _run(["fzstart 0 0 0"]) == ["0 0"]
    assert _run(["fzstart 1 1 0"]) == ["0 0"]
    assert _run(["fzstart 1 0 1"]) == ["0 0"]
    assert _run(["fzstart 1 0 0", "fzstart 1 0 0"]) == ["1 1", "0 1"]


def test_freeze_keeps_and_restores_game_writes():
    out = _run(["fzstart 1 0 0", "fztick 1 1 0", "fztick 0 1 0", "fztick 1 1 0", "fzstop"])
    assert out[1] == "keep 0 0 0 1"
    # The game cleared it, but the restore value is already 0: re-asserted,
    # not counted (pre and the events count only changes too).
    assert out[2] == "keep 0 0 0 1"
    assert out[3] == "keep 0 0 0 1"
    assert out[4] == "0 0"
    out = _run(["fzstart 1 0 0", "fztick 2 1 0", "fzstop"])
    assert out[1] == "keep 1 2 1 1" and out[2] == "2 0"


def test_freeze_sees_event_writes():
    # The event system runs on the game's own value while frozen; what it
    # leaves becomes the value unfreeze puts back. An event that stops the
    # world itself (writes 1) still holds after unfreeze.
    out = _run(["fzstart 1 0 0", "fzev 0", "fzev 1", "fztick 1 1 0", "fzstop"])
    assert out[1] == "0 0 0 1"  # no change, no write
    assert out[2] == "1 1 1 1"  # the event stopped the world
    assert out[3] == "keep 0 1 1 1"  # the re-assert sees 1, not a write
    assert out[4] == "1 0"
    out = _run(["fzstart 1 0 0", "fzev 1", "fzev 0", "fzstop"])
    assert out[2] == "1 0 2 1" and out[3] == "0 0"  # stopped then restarted
    # Not frozen: nothing is tracked.
    assert _run(["fzev 1"]) == ["0 0 0 0"]


def test_freeze_sees_writes_outside_the_event_window():
    # Before the event system the flag holds the re-assert's 1 unless the
    # game wrote it since (sub_00076030's snapshot restore): that value is
    # put in instead of the stale restore and kept for unfreeze.
    out = _run(["fzstart 1 0 0", "fzev 1", "fzpre 0", "fzev 0", "fzpre 1", "fzstop"])
    assert out[1] == "1 1 1 1"  # an event stopped the world
    assert out[2] == "0 1 2 1"  # the game's 0 goes in, not the stale 1
    assert out[3] == "0 0 2 1"  # the events left it: no new write
    assert out[4] == "0 0 2 1"  # 1 is the freeze's own, not a write
    assert out[5] == "0 0"
    out = _run(["fzstart 1 0 0", "fzpre 1", "fzpre 2", "fzstop"])
    assert out[1] == "0 0 0 1" and out[2] == "2 1 1 1" and out[3] == "2 0"
    # The game's 0 equals the restore value: it goes in, but is no write.
    assert _run(["fzstart 1 0 0", "fzpre 0"])[1] == "0 0 0 1"
    # Not frozen: nothing is tracked.
    assert _run(["fzpre 0"]) == ["0 0 0 0"]


def test_freeze_drop_gives_the_flag_back():
    # The pause menu or a stage change ends the freeze; the caller writes
    # the restore value so the world does not stay stopped after it.
    out = _run(["fzstart 1 0 0", "fztick 1 1 1"])
    assert out[1] == "drop 0 0 0 0"
    out = _run(["fzstart 1 0 0", "fztick 1 0 0"])
    assert out[1] == "drop 0 0 0 0"
    out = _run(["fzstart 1 0 0", "fzdrop", "fztick 1 1 0"])
    assert out[1] == "0 0" and out[2].startswith("drop")


# ---- keys and stock default ----------------------------------------------------


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows_are_config_tier():
    text = _read("src", "env", "recomp_env_game.h")
    for key, (env, _) in KEYS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert key in m.group(1), f"{env}: its row does not name {key}"


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for key, (env, _) in KEYS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f"`{key}`" in doc, f"{key}: not in docs/env.md"


def test_config_default_is_stock():
    with open(os.path.join(ROOT, "packaging", "config.default.toml"), "rb") as f:
        cfg = tomllib.load(f)
    cam = cfg["camera"]
    for key, (_, stock) in KEYS.items():
        assert cam[key.split(".", 1)[1]] == stock, key
    assert set(cam) == {k.split(".", 1)[1] for k in KEYS}


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("camera.free") == "off"
    # free_camera.c logs the line the golden check reads.
    assert '"[ENHANCE] camera.free=%s\\n"' in _read("src", "free_camera.c")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
