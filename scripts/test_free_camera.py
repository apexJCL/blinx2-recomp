#!/usr/bin/env python3
"""Tests for the free camera (camera.free, openspec change free-camera).

Compiles a driver against src/free_cam_fly.c and checks the fly maths
(dead zone, basis, speed, look, mouse, fast and slow multipliers, the
inverts, the pitch clamp, the dt cap)
and the freeze bookkeeping on 0xAF0EF4 (the entry guards, game writes kept
as the restore value, the drop paths giving the flag back), and the fly
input read through the captured controls (mod-settings D.4: the old pad
read with the default bindings, each stick's dead zone with Move and Look
swapped), and the indicator card (overlay-revamp D12a: the reminder lines
for 10 s under Brief, always or never, the card off, cleared when flight
ends and on a toolkit before API version 7). Then checks the
keys: every camera.* setting has an env row, a docs/env.md row, a stock line
in packaging/config.default.toml and a row in the mod's descriptor
(mod-settings C), every action keeps its old key as an alias, and the golden
check knows camera.free's stock value.

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

# The settings: [camera] key, env row, stock value.
SETTINGS = {
    "camera.free": ("RECOMP_CAMERA_FREE", "off"),
    "camera.free_speed": ("RECOMP_CAMERA_FREE_SPEED", 1.0),
    "camera.free_look_sens": ("RECOMP_CAMERA_FREE_LOOK_SENS", 1.0),
    "camera.free_mouse_sens": ("RECOMP_CAMERA_FREE_MOUSE_SENS", 1.0),
    "camera.free_invert_x": ("RECOMP_CAMERA_FREE_INVERT_X", False),
    "camera.free_invert_y": ("RECOMP_CAMERA_FREE_INVERT_Y", False),
    "camera.free_fast": ("RECOMP_CAMERA_FREE_FAST", 4.0),
    "camera.free_slow": ("RECOMP_CAMERA_FREE_SLOW", 0.25),
    "camera.free_hud": ("RECOMP_CAMERA_FREE_HUD", "keep"),
    "camera.free_indicator": ("RECOMP_CAMERA_FREE_INDICATOR", True),
    "camera.free_reminder": ("RECOMP_CAMERA_FREE_REMINDER", "brief"),
}
# The host actions camera.free.<id>: old [camera] key (now an alias), env
# row, stock bindings under [input.actions].
ACTIONS = {
    "toggle": (
        "camera.free_toggle",
        "RECOMP_CAMERA_FREE_TOGGLE",
        ["F6", "guide+y", "back+right_thumb@400"],
    ),
    "hud": ("camera.free_hud_key", "RECOMP_CAMERA_FREE_HUD_KEY", "F7"),
    "freeze": ("camera.free_freeze_key", "RECOMP_CAMERA_FREE_FREEZE_KEY", "End"),
    "reset": ("camera.free_reset_key", "RECOMP_CAMERA_FREE_RESET_KEY", "Home"),
}
KEYS = {k: env for k, (env, _) in SETTINGS.items()} | {
    alias: env for alias, env, _ in ACTIONS.values()
}

# Each line: a command and its numbers; the driver prints one result line.
DRIVER = r"""
#include <stdio.h>
#include <string.h>
#include "free_cam_fly.h"

static struct fc_cam c;
static struct fc_input in;
#ifdef FC_PARAMS_DEFAULT
static struct fc_params pr = FC_PARAMS_DEFAULT;
#else /* free_cam_fly.h before the mod-settings C fields */
static struct fc_params pr = { 1.0f, 1.0f };
#endif
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
#ifdef FC_PARAMS_DEFAULT
        } else if (!strcmp(cmd, "parx")) {
            scanf("%f %f %d %d", &pr.mouse_sens, &pr.fast, &pr.invert_x, &pr.invert_y);
            scanf("%f", &pr.slow);
            printf("ok\n");
#endif
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
        } else if (!strcmp(cmd, "stepx")) {
            float dt;
            scanf("%f", &dt);
            fc_fly_step(&c, &in, &pr, dt);
            printf("%a %a %a %a %a\n", c.p[0], c.p[1], c.p[2], c.pitch, c.yaw);
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


def _run(lines, src=SRC):
    """Run the driver over the command lines; one output line each. src is
    the directory holding free_cam_fly.{c,h}."""
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
                src,
                "-o",
                exe,
                c,
                os.path.join(src, "free_cam_fly.c"),
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


# Flight inputs that touch every term: sticks, mouse, rise and sink, fast,
# slow, and a pitch past the clamp.
DEFAULT_FLIGHT = [
    "cam 1 2 3 0.1 0.2",
    "in 0.3 0.7 -0.4 0.6 1 0 0 0 7 -3",
    "stepx 0.033",
    "in 0.2 1 0 0 0 1 1 0 -2 4",
    "stepx 0.05",
    "in 1 0 0 0 0 0 0 1 0 0",
    "stepx 0.04",
    "in 0 0 0 1 0 0 0 0 0 -400",
    "stepx 0.1",
]
# The commit before the settings (mod-settings C): its free_cam_fly.c is the
# reference for the defaults.
OLD_FLY = "7954399"


def test_defaults_fly_as_the_old_formula():
    # The old fc_fly_step: yaw -= (rx*1.8*dt + mdx*0.0025)*look, pitch +=
    # (ry*1.8*dt - mdy*0.0025)*look, v = 80*speed*dt, x4 fast, x0.25 slow.
    def old(cam, inp, dt, speed=1.0, look=1.0):
        p, (pitch, yaw) = list(cam[:3]), cam[3:]
        lx, ly, rx, ry, up, down, fast, slow, mdx, mdy = inp
        yaw -= (rx * 1.8 * dt + mdx * 0.0025) * look
        pitch = max(-1.5, min(1.5, pitch + (ry * 1.8 * dt - mdy * 0.0025) * look))
        v = 80 * speed * dt * (4 if fast else 1) * (0.25 if slow else 1)
        fwd = (-math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch))
        right = (math.cos(yaw), 0.0, math.sin(yaw))
        p = [p[i] + (fwd[i] * ly + right[i] * lx) * v for i in range(3)]
        p[1] += (down - up) * v
        return p + [pitch, yaw]

    cam = [1.0, 2.0, 3.0, 0.1, 0.2]
    out = _run(DEFAULT_FLIGHT)
    for k, (inp, step) in enumerate(zip(DEFAULT_FLIGHT[1::2], DEFAULT_FLIGHT[2::2], strict=True)):
        cam = old(cam, [float(x) for x in inp.split()[1:]], float(step.split()[1]))
        got = [float.fromhex(x) for x in out[2 + 2 * k].split()]
        assert _close(got, cam), (k, got, cam)


def test_defaults_fly_bit_for_bit_as_before():
    # The same flight through the old free_cam_fly.c: identical bits.
    with tempfile.TemporaryDirectory() as d:
        for f in ("free_cam_fly.c", "free_cam_fly.h"):
            r = subprocess.run(
                ["git", "-C", ROOT, "show", f"{OLD_FLY}:src/{f}"], capture_output=True, text=True
            )
            if r.returncode:
                pytest.skip(f"no {OLD_FLY} in this checkout")
            with open(os.path.join(d, f), "w") as fh:
                fh.write(r.stdout)
        old = _run(DEFAULT_FLIGHT, src=d)
    assert _run(DEFAULT_FLIGHT) == old


def test_inverts_flip_the_look_signs():
    look = ["cam 0 0 0 0 0", "in 0 0 0.5 -0.5 0 0 0 0 6 4", "step 0.05"]
    p, y = _floats(_run(look)[2])[3:]
    assert p != 0 and y != 0
    p2, y2 = _floats(_run(look[:1] + ["parx 1 4 1 0 0.25"] + look[1:])[3])[3:]
    assert abs(p2 - p) < 1e-6 and abs(y2 + y) < 1e-6
    p3, y3 = _floats(_run(look[:1] + ["parx 1 4 0 1 0.25"] + look[1:])[3])[3:]
    assert abs(p3 + p) < 1e-6 and abs(y3 - y) < 1e-6
    # Moving is not inverted.
    mv = ["cam 0 0 0 0 0", "parx 1 4 1 1 0.25", "in 0.5 1 0 0 0 0 0 0 0 0", "step 0.05"]
    assert _close(_floats(_run(mv)[3]), _floats(_run(mv[:1] + mv[2:])[2]))


def test_mouse_sens_scales_only_the_mouse():
    # The stick look ignores it; the mouse look takes it on top of look_sens.
    stick = ["cam 0 0 0 0 0", "parx 3 4 0 0 0.25", "in 0 0 1 1 0 0 0 0 0 0", "step 0.1"]
    p, y = _floats(_run(stick)[3])[3:]
    assert abs(p - 0.18) < 1e-5 and abs(y + 0.18) < 1e-5
    mouse = ["cam 0 0 0 0 0", "par 1 2", "parx 3 4 0 0 0.25", "in 0 0 0 0 0 0 0 0 10 -10"]
    p, y = _floats(_run(mouse + ["step 0.01"])[4])[3:]
    assert abs(p - 3 * 2 * 10 * 0.0025) < 1e-5 and abs(y + 3 * 2 * 10 * 0.0025) < 1e-5


def test_fast_and_slow_settings():
    out = _run(["cam 0 0 0 0 0", "parx 1 10 0 0 0.5", "in 0 1 0 0 0 0 1 0 0 0", "step 0.05"])
    assert _close(_floats(out[3])[:3], [0, 0, 80 * 10 * 0.05])
    out = _run(["cam 0 0 0 0 0", "parx 1 10 0 0 0.5", "in 0 1 0 0 0 0 0 1 0 0", "step 0.05"])
    assert _close(_floats(out[3])[:3], [0, 0, 80 * 0.5 * 0.05])


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


# ---- the off path (mod-settings C.2) ---------------------------------------------

# Builds src/free_camera.c against the toolkit's headers with a fake
# xbox_mod_api: in flight, frozen, HUD hidden, then off from the Mods page.
OFF_HARNESS = r"""
/* The mod itself, statics and all, against a fake API. */
#include "free_camera.c"

#define MEM_SIZE 0xB00000u
static unsigned char *g_mem;
static int g_capture = -1, g_capture_calls, g_active = -1;
static double g_set[SET_N];
static void (*g_on_enable)(int, void *);

static void f_log(const struct xbox_mod *m, const char *fmt, ...)
{
    va_list ap;
    (void)m;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
}
static int f_on_frame(xbox_mod_frame_fn fn, void *u) { (void)fn; (void)u; return 0; }
static int f_batch(xbox_mod_batch_fn fn, void *u) { (void)fn; (void)u; return 0; }
static void f_capture(int on) { g_capture = on; g_capture_calls++; }
static int f_on_enable(void (*fn)(int, void *), void *u) { (void)u; g_on_enable = fn; return 0; }
static int f_arm(const char *k) { (void)k; return 0; }
static double f_setting(const struct xbox_mod_desc *d, uint32_t i) { (void)d; return g_set[i]; }
static int f_ctl_action(const struct xbox_mod_desc *d, uint32_t i) { (void)d; return (int)i + 1; }
static void f_active(const struct xbox_mod *m, int on) { (void)m; g_active = on; }
static int f_status(const struct xbox_mod *m, const char *t) { (void)m; (void)t; return 0; }

uint64_t xbox_HostNowNs(void) { return 0; }
void xbox_mod_frame(void) {}

static struct xbox_mod_api g_api;

#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); return 1; } } while (0)

int main(void)
{
    g_mem = calloc(1, MEM_SIZE);
    g_api.version = XBOX_MOD_API_VERSION;
    g_api.size = sizeof g_api;
    g_api.mem = (uintptr_t)g_mem;
    g_api.log = f_log;
    g_api.on_frame = f_on_frame;
    g_api.batch_filter = f_batch;
    g_api.input_capture = f_capture;
    g_api.on_enable = f_on_enable;
    g_api.actions_arm = f_arm;
    g_api.setting = f_setting;
    g_api.control_action = f_ctl_action;
    g_api.active = f_active;
    g_api.status = f_status;
    for (int i = 0; i < SET_N; i++)
        g_set[i] = k_set[i].def;
    g_set[SET_ENABLE] = 1;
    g_set[SET_HUD] = 1;                       /* hide while flying */
    /* A running stage with a game camera. */
    XBOX_MOD_MEM32(&g_api, CAM_PTR) = 0x100000u;
    XBOX_MOD_MEM32(&g_api, RUN_FLAG) = 1;

    CHECK(s_mod.init(&g_api) == 0 && g_on_enable && g_active == 1);
    free_cam_action_toggle();
    CHECK(s_flying && g_capture == 1 && __atomic_load_n(&s_hud_hide_now, __ATOMIC_ACQUIRE));
    free_cam_action_freeze();
    CHECK(s_fz.on && XBOX_MOD_MEM32(&g_api, STOP_FLAG) == 1);

    /* Off from the Mods page mid-flight. */
    g_on_enable(0, NULL);
    CHECK(!s_flying && !s_fz.on && XBOX_MOD_MEM32(&g_api, STOP_FLAG) == 0);
    CHECK(g_capture == 0 && !__atomic_load_n(&s_hud_hide_now, __ATOMIC_ACQUIRE));
    CHECK(!on_now() && g_active == 0);
    /* Told again: nothing changes, the pad is not released twice. */
    int calls = g_capture_calls;
    XBOX_MOD_MEM32(&g_api, STOP_FLAG) = 7;    /* the game's own value now */
    g_on_enable(0, NULL);
    CHECK(g_capture_calls == calls && XBOX_MOD_MEM32(&g_api, STOP_FLAG) == 7 && g_active == 0);
    /* Off: the toggle does nothing. */
    free_cam_action_toggle();
    CHECK(!s_flying && g_capture_calls == calls);
    /* On again: the toggle flies. */
    g_on_enable(1, NULL);
    CHECK(on_now() && g_active == 1);
    free_cam_action_toggle();
    CHECK(s_flying && g_capture == 1);
    printf("ok\n");
    return 0;
}
"""


def _toolkit():
    """The toolkit checkout, as CMakeLists.txt finds it: XBOXRECOMP_DIR, else
    ../xboxrecomp; None without its mod.h."""
    d = os.environ.get("XBOXRECOMP_DIR") or os.path.join(ROOT, "..", "xboxrecomp")
    h = os.path.join(d, "src", "enhance", "mod.h")
    if not os.path.isfile(h):
        return None
    # The camera builds only on a toolkit with the port-0 record.
    with open(h, encoding="utf-8") as f:
        return d if "XBOX_MOD_PAD_SEEN" in f.read() else None


def _run_mod(harness):
    """Build harness (which includes src/free_camera.c) against the toolkit's
    headers and run it; its output lines."""
    tk = _toolkit()
    if not _cc() or not tk:
        pytest.skip("no C compiler or no toolkit with the pad record (XBOXRECOMP_DIR)")
    incs = []
    for top in ("src", "include"):
        for dirpath, _, _ in os.walk(os.path.join(tk, top)):
            incs += ["-I", dirpath]
    with tempfile.TemporaryDirectory() as d:
        c, exe = os.path.join(d, "mod.c"), os.path.join(d, "mod")
        with open(c, "w") as f:
            f.write(harness)
        subprocess.run(
            [_cc(), "-std=c11", "-Wall", "-Werror", "-Wno-unused-function"]
            + ["-DRECOMP_ENV_HAVE_ENHANCE_KEYS", "-DXBOXRECOMP_ENHANCE"]
            + ["-I", SRC, "-I", os.path.join(SRC, "env")]
            + incs
            + ["-o", exe, c, os.path.join(SRC, "free_cam_fly.c"), "-lm"],
            check=True,
        )
        out = subprocess.run([exe], capture_output=True, text=True).stdout
    return out.splitlines()


def test_off_drops_freeze_hud_and_capture_once():
    out = _run_mod(OFF_HARNESS)
    assert out[-1] == "ok", out


# ---- the captured controls (mod-settings D.4) ------------------------------------

# fly_input against a fake control_value that resolves each control's
# bindings over one pad state as the toolkit does (a stick: its axes and
# source; a button: the largest of its bindings). With the descriptor's
# defaults the input must be what the camera read from the merged pad
# before the controls were rebindable; with Move and Look swapped, each
# stick keeps its own dead zone.
FLY_HARNESS = r"""
#include "free_camera.c"

uint64_t xbox_HostNowNs(void) { return 0; }
void xbox_mod_frame(void) {}

static XBOX_GAMEPAD g_pad;
static int g_conn;
static const char *const *g_bind[CTL_N];

static int f_ctl_value(const struct xbox_mod_desc *d, uint32_t k, struct xbox_ctl_value *out)
{
    static const char *const names[] = { "a", "b", "x", "y", "black", "white", "lt", "rt" };
    const char *const *b = g_bind[k];

    (void)d;
    memset(out, 0, sizeof *out);
    out->connected = (uint8_t)g_conn;
    for (; b && *b; b++) {
        if (!strcmp(*b, "left_stick") || !strcmp(*b, "right_stick")) {
            int r = (*b)[0] == 'r';
            out->src = r ? XBOX_CTL_SRC_RIGHT : XBOX_CTL_SRC_LEFT;
            out->raw[0] = g_conn ? (r ? g_pad.sThumbRX : g_pad.sThumbLX) : 0;
            out->raw[1] = g_conn ? (r ? g_pad.sThumbRY : g_pad.sThumbLY) : 0;
            return g_conn;
        }
        for (int i = 0; i < 8; i++)
            if (!strcmp(*b, names[i]) && g_conn && g_pad.bAnalogButtons[i] > out->raw[0])
                out->raw[0] = g_pad.bAnalogButtons[i];
    }
    return g_conn;
}

/* fly() as it read the merged pad before mod-settings D. */
static float old_analog(BYTE v)
{
    return v > XBOX_ANALOG_BUTTON_THRESHOLD ? (float)v / 255.0f : 0.0f;
}
static void old_input(const XBOX_GAMEPAD *gp, int conn, struct fc_input *in)
{
    XBOX_GAMEPAD g = *gp;
    memset(in, 0, sizeof *in);
    if (conn) {
        float lt = old_analog(g.bAnalogButtons[6]), rt = old_analog(g.bAnalogButtons[7]);
        float x = old_analog(g.bAnalogButtons[2]), y = old_analog(g.bAnalogButtons[3]);

        in->lx = fc_axis(g.sThumbLX, 7849);
        in->ly = fc_axis(g.sThumbLY, 7849);
        in->rx = fc_axis(g.sThumbRX, 8689);
        in->ry = fc_axis(g.sThumbRY, 8689);
        in->up = rt > x ? rt : x;
        in->down = lt > y ? lt : y;
        in->fast = g.bAnalogButtons[5] > XBOX_ANALOG_BUTTON_THRESHOLD;
        in->slow = g.bAnalogButtons[4] > XBOX_ANALOG_BUTTON_THRESHOLD;
    }
}

static struct xbox_mod_api g_api;
static unsigned g_rng = 12345u;
static unsigned rnd(void) { g_rng = g_rng * 1103515245u + 12345u; return g_rng >> 8; }
static int16_t rnd_axis(void)
{
    /* Around both dead zones as often as across the whole range. */
    static const int16_t edge[] = { 0, 7849, 7850, 8000, 8689, 8690, -7850, -8690,
                                    32767, -32768 };
    if (rnd() & 1)
        return edge[rnd() % (sizeof edge / sizeof edge[0])];
    return (int16_t)(rnd() & 0xFFFF);
}

#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); return 1; } } while (0)

int main(void)
{
    static const char *const swap_move[] = { "right_stick", NULL };
    static const char *const swap_look[] = { "left_stick", NULL };
    struct fc_input a, b;

    g_api.version = XBOX_MOD_API_VERSION;
    g_api.size = sizeof g_api;
    g_api.control_value = f_ctl_value;
    s_api = &g_api;
    for (int k = 0; k < CTL_N; k++)
        g_bind[k] = k_ctl[k].defaults;

    for (int n = 0; n < 4000; n++) {
        memset(&g_pad, 0, sizeof g_pad);
        g_pad.sThumbLX = rnd_axis();
        g_pad.sThumbLY = rnd_axis();
        g_pad.sThumbRX = rnd_axis();
        g_pad.sThumbRY = rnd_axis();
        for (int i = 0; i < 8; i++)
            g_pad.bAnalogButtons[i] = (BYTE)(rnd() & 1 ? rnd() & 0xFF
                                                       : XBOX_ANALOG_BUTTON_THRESHOLD + (int)(rnd() % 3) - 1);
        g_conn = n % 17 != 0;
        g_bind[CTL_MOVE] = k_ctl[CTL_MOVE].defaults;
        g_bind[CTL_LOOK] = k_ctl[CTL_LOOK].defaults;
        fly_input(&a);
        old_input(&g_pad, g_conn, &b);
        CHECK(!memcmp(&a, &b, sizeof a));

        /* Move on the right stick, Look on the left: each keeps its dead zone. */
        g_bind[CTL_MOVE] = swap_move;
        g_bind[CTL_LOOK] = swap_look;
        fly_input(&a);
        CHECK(a.lx == (g_conn ? fc_axis(g_pad.sThumbRX, 8689) : 0.0f));
        CHECK(a.ly == (g_conn ? fc_axis(g_pad.sThumbRY, 8689) : 0.0f));
        CHECK(a.rx == (g_conn ? fc_axis(g_pad.sThumbLX, 7849) : 0.0f));
        CHECK(a.ry == (g_conn ? fc_axis(g_pad.sThumbLY, 7849) : 0.0f));
        CHECK(a.up == b.up && a.down == b.down && a.fast == b.fast && a.slow == b.slow);
    }
    /* 8000 is past the left stick's dead zone, inside the right one's:
     * swapped, Move (the right stick) stays still and Look (the left)
     * turns; with the defaults, the other way round. */
    memset(&g_pad, 0, sizeof g_pad);
    g_pad.sThumbLX = g_pad.sThumbRX = 8000;
    g_conn = 1;
    fly_input(&a);
    CHECK(a.lx == 0.0f && a.rx > 0.0f);
    g_bind[CTL_MOVE] = k_ctl[CTL_MOVE].defaults;
    g_bind[CTL_LOOK] = k_ctl[CTL_LOOK].defaults;
    fly_input(&a);
    CHECK(a.lx > 0.0f && a.rx == 0.0f);
    printf("ok\n");
    return 0;
}
"""


def test_fly_input_defaults_match_the_old_pad_read():
    out = _run_mod(FLY_HARNESS)
    assert out and out[-1] == "ok", out


# ---- the indicator card (overlay-revamp D12a) ----------------------------------

# The mod against a fake API that keeps the card's text and a clock the
# harness moves; each line it prints is one card change.
PANEL_HARNESS = r"""
#include "free_camera.c"

#define MEM_SIZE 0xB00000u
static unsigned char *g_mem;
static double g_set[SET_N];
static void (*g_on_enable)(int, void *);
static uint64_t g_now = 1000000000ull;
static char g_card[1024];
static int g_calls;

static void f_log(const struct xbox_mod *m, const char *fmt, ...) { (void)m; (void)fmt; }
static int f_on_frame(xbox_mod_frame_fn fn, void *u) { (void)fn; (void)u; return 0; }
static int f_batch(xbox_mod_batch_fn fn, void *u) { (void)fn; (void)u; return 0; }
static void f_capture(int on) { (void)on; }
static int f_on_enable(void (*fn)(int, void *), void *u) { (void)u; g_on_enable = fn; return 0; }
static int f_arm(const char *k) { (void)k; return 0; }
static double f_setting(const struct xbox_mod_desc *d, uint32_t i) { (void)d; return g_set[i]; }
static int f_ctl_action(const struct xbox_mod_desc *d, uint32_t i) { (void)d; return (int)i + 1; }
static void f_active(const struct xbox_mod *m, int on) { (void)m; (void)on; }
static int f_pressed(int id) { (void)id; return 0; }
static int f_ctl_value(const struct xbox_mod_desc *d, uint32_t k, struct xbox_ctl_value *v)
{
    (void)d; (void)k;
    memset(v, 0, sizeof *v);
    return 0;
}
static void f_input_state(struct enhance_input_state *st) { memset(st, 0, sizeof *st); }
static int f_status(const struct xbox_mod *m, const char *t)
{
    (void)m;
    g_calls++;
    snprintf(g_card, sizeof g_card, "%s", t ? t : "");
    return 0;
}

uint64_t xbox_HostNowNs(void) { return g_now; }
void xbox_mod_frame(void) {}

static struct xbox_mod_api g_api;

/* The card in one line: its line count, 0 for none. */
static int lines(void)
{
    int n = g_card[0] != 0;
    for (const char *p = g_card; *p; p++)
        n += *p == '\n';
    return n;
}

static void frame(double secs)
{
    g_now += (uint64_t)(secs * 1e9);
    on_frame(NULL);
}

#define CHECK(c) do { if (!(c)) { printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); return 1; } } while (0)

static void setup(size_t size)
{
    g_api.version = XBOX_MOD_API_VERSION;
    g_api.size = (uint32_t)size;
    g_api.mem = (uintptr_t)g_mem;
    g_api.log = f_log;
    g_api.on_frame = f_on_frame;
    g_api.batch_filter = f_batch;
    g_api.input_capture = f_capture;
    g_api.on_enable = f_on_enable;
    g_api.actions_arm = f_arm;
    g_api.setting = f_setting;
    g_api.control_action = f_ctl_action;
    g_api.control_value = f_ctl_value;
    g_api.action_pressed = f_pressed;
    g_api.input_state = f_input_state;
    g_api.active = f_active;
    g_api.status = f_status;
}

static int old_api(void)
{
    setup(offsetof(struct xbox_mod_api, guest_alloc) + sizeof g_api.guest_alloc);
    for (int i = 0; i < SET_N; i++)
        g_set[i] = k_set[i].def;
    g_set[SET_ENABLE] = 1;
    XBOX_MOD_MEM32(&g_api, CAM_PTR) = 0x100000u;
    XBOX_MOD_MEM32(&g_api, RUN_FLAG) = 1;
    CHECK(s_mod.init(&g_api) == 0);
    free_cam_action_toggle();
    CHECK(s_flying);
    frame(1);
    free_cam_action_toggle();
    CHECK(!s_flying && g_calls == 0);
    printf("ok\n");
    return 0;
}

int main(void)
{
    g_mem = calloc(1, MEM_SIZE);
#ifdef OLD_API
    return old_api();
#endif
    setup(sizeof g_api);
    for (int i = 0; i < SET_N; i++)
        g_set[i] = k_set[i].def;
    CHECK(g_set[SET_INDICATOR] == 1 && g_set[SET_REMINDER] == REMIND_BRIEF);
    g_set[SET_ENABLE] = 1;
    XBOX_MOD_MEM32(&g_api, CAM_PTR) = 0x100000u;
    XBOX_MOD_MEM32(&g_api, RUN_FLAG) = 1;
    CHECK(s_mod.init(&g_api) == 0);
    CHECK(g_calls == 0);

    /* Brief: the title and five lines, for 10 s; then the title alone. */
    free_cam_action_toggle();
    CHECK(s_flying && lines() == 6 && !strcmp(g_card, k_panel_full));
    CHECK(strstr(g_card, "{act:camera.free.toggle} Exit") && strstr(g_card, "{ctl:move} Move"));
    frame(9.9);
    CHECK(lines() == 6 && g_calls == 1);
    frame(0.2);
    CHECK(lines() == 1 && !strcmp(g_card, "Free camera") && g_calls == 2);
    frame(5);
    CHECK(g_calls == 2);
    /* Off: cleared. */
    free_cam_action_toggle();
    CHECK(!s_flying && lines() == 0 && g_calls == 3);
    /* A second flight starts its own 10 s. */
    frame(60);
    free_cam_action_toggle();
    CHECK(lines() == 6);
    frame(10.1);
    CHECK(lines() == 1);

    /* Always, set in flight: the lines come back and stay. */
    g_set[SET_REMINDER] = REMIND_ALWAYS;
    frame(0.016);
    CHECK(lines() == 6);
    frame(120);
    CHECK(lines() == 6);
    /* Never: the title alone. */
    g_set[SET_REMINDER] = REMIND_NEVER;
    frame(0.016);
    CHECK(lines() == 1);
    /* Show indicator off: no card; on again: back. */
    g_set[SET_INDICATOR] = 0;
    frame(0.016);
    CHECK(lines() == 0);
    g_set[SET_INDICATOR] = 1;
    frame(0.016);
    CHECK(lines() == 1);
    /* Indicator off from the start: flight never sets a card. */
    free_cam_action_toggle();
    g_set[SET_INDICATOR] = 0;
    g_set[SET_REMINDER] = REMIND_BRIEF;
    int calls = g_calls;
    free_cam_action_toggle();
    CHECK(s_flying && g_calls == calls && lines() == 0);
    frame(1);
    CHECK(g_calls == calls);
    free_cam_action_toggle();
    g_set[SET_INDICATOR] = 1;

    /* Off from the Mods page mid-flight, and the exit: cleared. */
    free_cam_action_toggle();
    CHECK(lines() == 6);
    g_on_enable(0, NULL);
    CHECK(!s_flying && lines() == 0);
    g_on_enable(1, NULL);
    free_cam_action_toggle();
    CHECK(lines() == 6);
    s_mod.shutdown();
    CHECK(lines() == 0);
    printf("ok\n");
    return 0;
}
"""

# The same mod on a toolkit before version 7 (its size ends at guest_alloc):
# it flies and never calls status.
OLD_API_HARNESS = "#define OLD_API 1\n" + PANEL_HARNESS


def test_indicator_brief_always_never_and_off():
    out = _run_mod(PANEL_HARNESS)
    assert out and out[-1] == "ok", out


def test_indicator_needs_api_version_7():
    out = _run_mod(OLD_API_HARNESS)
    assert out and out[-1] == "ok", out


# ---- keys and stock default ----------------------------------------------------


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows_are_config_tier():
    text = _read("src", "env", "recomp_env_game.h")
    for key, env in KEYS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert key in m.group(1), f"{env}: its row does not name {key}"


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for key, env in KEYS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f"`{key}`" in doc, f"{key}: not in docs/env.md"


def test_config_default_is_stock():
    with open(os.path.join(ROOT, "packaging", "config.default.toml"), "rb") as f:
        cfg = tomllib.load(f)
    cam = cfg["camera"]
    for key, (_, stock) in SETTINGS.items():
        assert cam[key.split(".", 1)[1]] == stock, key
    # The old key lines are gone: the bindings live under [input.actions].
    assert set(cam) == {k.split(".", 1)[1] for k in SETTINGS}
    acts = cfg["input"]["actions"]["camera"]["free"]
    assert acts == {a: stock for a, (_, _, stock) in ACTIONS.items()}


def _descriptor():
    text = _read("src", "free_camera.c")
    i = text.index("static const struct xbox_mod_setting k_set[")
    j = text.index("static const struct xbox_mod_desc k_desc")
    return text, text[i:j]


# A row's fields up to its closing brace; quoted strings may hold the
# glyph tokens' own braces ({ctl:move}).
_ROW = r'(?:"(?:[^"\\]|\\.)*"|[^}"])*'


def test_descriptor_declares_every_setting():
    _, desc = _descriptor()
    for key, env in KEYS.items():
        assert f'"{key}"' in desc, f"{key}: not in the descriptor"
        assert f'"{env}"' in desc, f"{env}: not in the descriptor"
    assert re.search(r'"camera\.free",\s*"RECOMP_CAMERA_FREE",' + _ROW + "XBOX_SET_ENABLE", desc)
    for aid, (alias, env, stock) in ACTIONS.items():
        m = re.search(
            r'\{\s*"' + aid + r'",' + _ROW + r'XBOX_CTL_ACTION,\s*(\w+),\s*(\w+),\s*"(\w+)"', desc
        )
        assert m, f"camera.free.{aid}: no action row"
        defs, aliases, row_env = m.groups()
        assert row_env == env, f"camera.free.{aid}: env {row_env}"

        def strings(name):
            body = re.search(r"\b" + name + r"\[\]\s*=\s*\{([^}]*)\}", desc).group(1)
            return re.findall(r'"([^"]*)"', body)

        assert alias in strings(aliases), f"camera.free.{aid}: alias {alias} missing"
        assert strings(defs) == (stock if isinstance(stock, list) else [stock]), aid


def test_toolkit_does_the_ranges_and_keys():
    # The toolkit clamps and snaps the values and polls the actions; the mod
    # keeps no range checks or key polling of its own.
    text, _ = _descriptor()
    assert "out of range" not in text
    assert "xbox_FramebufferKeyDown" not in text and "key_code(" not in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("camera.free") == "off"
    # The toolkit logs the line the golden check reads from the descriptor's
    # enable setting (D4), inited or not; the mod prints it no more.
    text, desc = _descriptor()
    assert "XBOX_SET_ENABLE" in desc
    assert "camera.free=%s" not in text


def test_screen_projection_gets_the_swap():
    # the tracker item: the shadows' screen projection reads the camera outside the
    # builds too, so it takes the same swap, but who=NULL keeps it out of
    # the build count that cam_log=n and cam_fix=hold:n use.
    manual = _read("src", "recomp_manual.c")
    body = re.search(r"\nvoid sub_00042E50\(void\)\n\{(.*?)\n\}", manual, re.S)
    assert body, "sub_00042E50 wrapper"
    assert re.search(
        r"cam_build\(0x00042E50u, sub_00042E50_gen, NULL, MEM32\(0x4B271Cu\), 1, 0\);",
        body.group(1),
    )
    assert "extern void sub_00042E50_gen(void);" in manual
    build = re.search(r"\nstatic void cam_build\(.*?\n\}", manual, re.S).group(0)
    assert re.search(r"if \(who\)\s*s_cam_calls\+\+;", build)
    assert "if (who && s_cam_log_every" in build


@pytest.mark.parametrize(
    "va",
    [
        # the tracker item: the stage pass (its eye-relative callees, and the sky
        # dome it centres on the eye at 0xE5A06, which runs only in split
        # screen), the eye-facing quads, the two billboards and the radar
        # draw relative to the camera outside the builds, and the effect
        # draw pass copies the camera for its particles.
        "000E58D0",
        "001F73C0",
        "000DAEC0",
        "0004D740",
        "001A6E00",
        "0015BC40",
    ],
)
def test_render_pass_readers_get_the_swap(va):
    manual = _read("src", "recomp_manual.c")
    body = re.search(rf"\nvoid sub_{va}\(void\)\n\{{(.*?)\n\}}", manual, re.S)
    assert body, f"sub_{va} wrapper"
    assert re.search(
        rf"cam_build\(0x{va}u, sub_{va}_gen, NULL, MEM32\(0x4B271Cu\), 1, 0\);",
        body.group(1),
    )
    assert f"\nextern void sub_{va}_gen(void);" in manual


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
