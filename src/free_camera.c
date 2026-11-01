/*
 * free_camera.c - camera.free, the enhancements layer's first mod (see
 * free_camera.h; openspec change free-camera).
 *
 * The camera flies a copy of the game camera's fields; the view builders'
 * wrappers in recomp_manual.c swap the copy in for each build and the game
 * back out after it, so the game's own maths makes the view, the
 * projection, the cull planes and the inverse view, and the game's camera
 * logic never sees the free one (D1). Port 0 is the camera's while it
 * flies: the game reads a released pad (pad_input.c), and the camera reads
 * its captured controls (api->control_value) from the merged pad and
 * keyboard the game would have read, which pad_input.c records before that
 * (xbox_enhance_pad_seen), and from the host keys. The toolkit's
 * api->input_state pad is not used: it is fed by the toolkit's own pad
 * read, which this title replaces.
 *
 * The freeze is the event world-stop flag 0xAF0EF4 (spike.md 9.6),
 * kept in three phases (fc_freeze_*):
 * - around the event system (sub_000EEB40) each frame: the game's own value
 *   is put in and read back, so an event that stops or starts the world
 *   while frozen is seen; a value other than 1 found before it is a game
 *   write made outside the window and is taken as the game's value too;
 * - after sub_00161120, before the gate at 0x652DC: 1 again;
 * - on unfreeze and when the freeze is dropped (the pause menu or retry,
 *   leaving the stage, a stage start): the game's value put back.
 *
 * The mod has a descriptor (mod-settings D6): its settings, its four
 * actions and the fly controls are static data the toolkit reads before
 * any init, resolves (env, the files, aliases, the defaults) and clamps,
 * and the Mods page and RECOMP_MODS_DESCRIBE show. The toolkit prints
 * "[ENHANCE] camera.free=" and inits the mod only when camera.free is on,
 * or dormant when the menu can turn it on (D4's init rule). A stock run
 * (camera.free off, the menu off) never inits it: nothing is registered,
 * so neither a frame callback nor the draw filter exists.
 */
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "free_camera.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
/* control_value reads what pad_input.c records (XBOX_MOD_PAD_SEEN): a
 * toolkit without the record builds without the camera. */
#    if XBOX_MOD_API_VERSION >= 6 && defined(XBOX_MOD_PAD_SEEN)
#      define FREE_CAM_MOD 1
#    endif
#  endif
#endif

#ifdef FREE_CAM_MOD

#include "enhance_menu.h"
#include "host_time.h"
#include "xinput_xbox.h"

#define CAM_PTR    0x4B271Cu    /* the game camera struct */
#define RUN_FLAG   0x449F40u    /* 1 while the stage runs */
#define MENU_FLAG  0xAE73B4u    /* pause menu or retry */
#define STOP_FLAG  0xAF0EF4u    /* the event world stop */

/* The HUD's vertex programs (spike.md, the 2D pass). */
#define HUD_PROG_A 0x5474DB2Au
#define HUD_PROG_B 0xB2913952u

/* ---- the descriptor (mod-settings D6) ------------------------------------- */

enum {
    SET_ENABLE, SET_SPEED, SET_LOOK, SET_MOUSE, SET_INVERT_X, SET_INVERT_Y,
    SET_FAST, SET_SLOW, SET_HUD, SET_N
};
enum {
    CTL_TOGGLE, CTL_HUD, CTL_FREEZE, CTL_RESET,         /* host actions */
    CTL_MOVE, CTL_LOOK, CTL_RISE, CTL_SINK, CTL_FAST, CTL_SLOW, CTL_MOUSE, CTL_N
};

static const char *const k_offon[] = { "off", "on", NULL };
static const char *const k_hud[] = { "keep", "hide", NULL };

/* What the camera holds, and what is a setting (D10; mod-settings D6's
 * audit, from this file and free_cam_fly.{c,h}). Before adding a knob,
 * check it is not one of the "no" rows, and why:
 *
 *   value                          setting       why
 *   FC_MOVE_BASE 80 units/s        speed         speed is its multiplier
 *   FC_LOOK_RATE 1.8 rad/s         look_sens     look_sens is its multiplier
 *   FC_MOUSE_RATE 0.0025 rad/count mouse_sens    on top of look_sens, so an
 *                                                old look_sens means the same
 *   FC_FAST x4, FC_SLOW x0.25      fast, slow    a preference
 *   pitch and yaw signs            invert_x, _y  a preference
 *   HUD hidden while flying        hud           already a key
 *   stick dead zones 7849 / 8689   no            input.pad_deadzone_* apply
 *                                                first; these are the XInput
 *                                                floor fc_axis needs
 *   fast/slow trigger threshold    no            the toolkit's, every button
 *   FC_PITCH_MAX 1.50 rad          no            past +-pi/2 the view flips
 *   FC_DT_MAX 0.1 s                no            a hitch guard
 *   roll, +0x14..+0x1C             no            written 0 (free-camera D2)
 *   field of view                  no            not a field the mod writes;
 *                                                a follow-up feature
 *   the freeze drop rules          no            they keep the game sound (D5)
 *   guest addresses, HUD hashes    no            game facts
 *   cam_log lines                  no            diagnostics
 *
 * The keys are the ones the camera read before the descriptor, so old
 * configs and env rows keep working. */
static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", "camera.free", "RECOMP_CAMERA_FREE", NULL, "Free camera",
      "A free-flying camera, started and stopped with its toggle. Player 1"
      " stands still while it flies.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
    [SET_SPEED] = { "speed", "camera.free_speed", "RECOMP_CAMERA_FREE_SPEED", NULL,
      "Fly speed", "A multiplier of the fly speed (80 units a second at full stick).",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 1.0, 0.05, 20, 0.05, NULL },
    [SET_LOOK] = { "look_sens", "camera.free_look_sens", "RECOMP_CAMERA_FREE_LOOK_SENS", NULL,
      "Look sensitivity", "A multiplier of the turn rate, for the stick and the mouse.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 1.0, 0.05, 10, 0.05, NULL },
    [SET_MOUSE] = { "mouse_sens", "camera.free_mouse_sens", "RECOMP_CAMERA_FREE_MOUSE_SENS",
      NULL, "Mouse sensitivity", "The mouse's turn rate, on top of look sensitivity.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 1.0, 0.05, 10, 0.05, NULL },
    [SET_INVERT_X] = { "invert_x", "camera.free_invert_x", "RECOMP_CAMERA_FREE_INVERT_X", NULL,
      "Invert X", "Turn the other way, with the stick and the mouse.",
      NULL, XBOX_SET_BOOL, ENHANCE_LIVE, 0, 0, 0, 1, 0, NULL },
    [SET_INVERT_Y] = { "invert_y", "camera.free_invert_y", "RECOMP_CAMERA_FREE_INVERT_Y", NULL,
      "Invert Y", "Look up and down the other way, with the stick and the mouse.",
      NULL, XBOX_SET_BOOL, ENHANCE_LIVE, 0, 0, 0, 1, 0, NULL },
    [SET_FAST] = { "fast", "camera.free_fast", "RECOMP_CAMERA_FREE_FAST", NULL,
      "Fast multiplier", "How much faster the camera flies while Fast is held.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 4.0, 1, 20, 0.5, NULL },
    [SET_SLOW] = { "slow", "camera.free_slow", "RECOMP_CAMERA_FREE_SLOW", NULL,
      "Slow multiplier", "How much slower the camera flies while Slow is held.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 0.25, 0.05, 1, 0.05, NULL },
    [SET_HUD] = { "hud", "camera.free_hud", "RECOMP_CAMERA_FREE_HUD", NULL, "HUD while flying",
      "Keep or hide the HUD when the camera starts; Toggle HUD flips it in flight.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE_ACTIVATE, 0, 0, 0, 0, 0, k_hud },
};

static const char *const k_toggle_def[] = { "F6", "guide+y", NULL };
static const char *const k_hud_def[] = { "F7", NULL };
static const char *const k_freeze_def[] = { "End", NULL };
static const char *const k_reset_def[] = { "Home", NULL };
static const char *const k_toggle_alias[] = { "camera.free_toggle", NULL };
static const char *const k_hud_alias[] = { "camera.free_hud_key", NULL };
static const char *const k_freeze_alias[] = { "camera.free_freeze_key", NULL };
static const char *const k_reset_alias[] = { "camera.free_reset_key", NULL };
static const char *const k_move_def[] = { "left_stick", NULL };
static const char *const k_look_def[] = { "right_stick", NULL };
static const char *const k_rise_def[] = { "rt", "x", NULL };
static const char *const k_sink_def[] = { "lt", "y", NULL };
static const char *const k_fast_def[] = { "white", NULL };
static const char *const k_slow_def[] = { "black", NULL };
static const char *const k_mouse_def[] = { "Look", NULL };

#define FLYING "while flying"

/* The actions take the old key settings as aliases and keep their env
 * rows. fly() reads the captured controls through control_value, and the
 * Mods page rebinds them (mod-settings D). */
static const struct xbox_mod_control k_ctl[CTL_N] = {
    /* id, label, help, when, kind, defaults, aliases, env */
    [CTL_TOGGLE] = { "toggle", "Toggle flight", "Starts and stops the free camera.", NULL,
      XBOX_CTL_ACTION, k_toggle_def, k_toggle_alias, "RECOMP_CAMERA_FREE_TOGGLE" },
    [CTL_HUD] = { "hud", "Toggle HUD", "Shows or hides the HUD.", FLYING,
      XBOX_CTL_ACTION, k_hud_def, k_hud_alias, "RECOMP_CAMERA_FREE_HUD_KEY" },
    [CTL_FREEZE] = { "freeze", "Freeze game", "Stops and restarts the world.", FLYING,
      XBOX_CTL_ACTION, k_freeze_def, k_freeze_alias, "RECOMP_CAMERA_FREE_FREEZE_KEY" },
    [CTL_RESET] = { "reset", "Reset camera", "Puts the camera back on the game's.", FLYING,
      XBOX_CTL_ACTION, k_reset_def, k_reset_alias, "RECOMP_CAMERA_FREE_RESET_KEY" },
    [CTL_MOVE] = { "move", "Move", NULL, FLYING, XBOX_CTL_STICK, k_move_def, NULL, NULL },
    [CTL_LOOK] = { "look", "Look", NULL, FLYING, XBOX_CTL_STICK, k_look_def, NULL, NULL },
    [CTL_RISE] = { "rise", "Rise", NULL, FLYING, XBOX_CTL_BUTTON, k_rise_def, NULL, NULL },
    [CTL_SINK] = { "sink", "Sink", NULL, FLYING, XBOX_CTL_BUTTON, k_sink_def, NULL, NULL },
    [CTL_FAST] = { "fast", "Fast", NULL, FLYING, XBOX_CTL_BUTTON, k_fast_def, NULL, NULL },
    [CTL_SLOW] = { "slow", "Slow", NULL, FLYING, XBOX_CTL_BUTTON, k_slow_def, NULL, NULL },
    [CTL_MOUSE] = { "mouse", "Mouse", NULL, FLYING, XBOX_CTL_INFO, k_mouse_def, NULL, NULL },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Free camera",
    "Fly a detached camera around the stage", NULL, "1",
    k_set, SET_N, k_ctl, CTL_N
};

enum { ACT_TOGGLE, ACT_HUD, ACT_FREEZE, ACT_RESET, ACT_N };

static const struct xbox_mod_api *s_api;
/* camera.free on: the actions do something. Written on the guest thread
 * (init, on_enable), read there and by shutdown on the exit thread. */
static int s_on;
static int s_flying;                    /* guest thread */
static struct fc_cam s_cam;
static struct fc_freeze s_fz;
static int s_hud_hide_now;              /* render thread reads it */
static int s_act[ACT_N] = { -1, -1, -1, -1 };
static uint64_t s_last_ns;

static const struct xbox_mod s_mod;

/* One "[MOD camera.free] ..." line. */
static void cam_log(const char *fmt, ...)
{
    char buf[256];
    va_list ap;

    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    s_api->log(&s_mod, "%s", buf);
}

static int mem_ok(void)
{
    return s_api && s_api->mem;
}

#define G32(va) XBOX_MOD_MEM32(s_api, (va))
#define GF(va)  XBOX_MOD_MEMF(s_api, (va))

static int on_now(void)
{
    return __atomic_load_n(&s_on, __ATOMIC_ACQUIRE);
}

/* The settings as they are now: the menu changes them live. */
static void params_now(struct fc_params *p)
{
    p->speed = (float)s_api->setting(&k_desc, SET_SPEED);
    p->look_sens = (float)s_api->setting(&k_desc, SET_LOOK);
    p->mouse_sens = (float)s_api->setting(&k_desc, SET_MOUSE);
    p->fast = (float)s_api->setting(&k_desc, SET_FAST);
    p->slow = (float)s_api->setting(&k_desc, SET_SLOW);
    p->invert_x = s_api->setting(&k_desc, SET_INVERT_X) != 0;
    p->invert_y = s_api->setting(&k_desc, SET_INVERT_Y) != 0;
}

/* ---- the freeze ---------------------------------------------------------- */

static void freeze_on(void)
{
    if (!fc_freeze_start(&s_fz, G32(RUN_FLAG), G32(MENU_FLAG), G32(STOP_FLAG))) {
        cam_log("freeze: not now (run=%u menu=%u stop=%u)", G32(RUN_FLAG),
                G32(MENU_FLAG), G32(STOP_FLAG));
        return;
    }
    G32(STOP_FLAG) = 1;
    cam_log("freeze on");
}

static void freeze_off(void)
{
    uint32_t v;

    if (!s_fz.on)
        return;
    v = fc_freeze_stop(&s_fz);
    G32(STOP_FLAG) = v;
    cam_log("freeze off: 0xAF0EF4=%u (%u game writes while frozen)", v, s_fz.game_writes);
}

void free_cam_events_pre(void)
{
    uint32_t was, flag, v;
    int wrote;

    if (!s_fz.on || !mem_ok())
        return;
    /* The flag is 1 here unless the game wrote it since the last re-assert
     * (sub_00076030's snapshot restore, say): that value is the game's, so
     * it goes in instead of a stale restore. A 1 written there cannot be
     * told from the freeze's own (design.md Risks). */
    was = s_fz.restore;
    flag = G32(STOP_FLAG);
    v = fc_freeze_pre(&s_fz, flag, &wrote);
    if (wrote)
        cam_log("freeze: the game wrote 0xAF0EF4=%u outside the event window (was %u)", flag, was);
    G32(STOP_FLAG) = v;
}

void free_cam_events_post(void)
{
    uint32_t was, flag;

    if (!s_fz.on || !mem_ok())
        return;
    was = s_fz.restore;
    flag = G32(STOP_FLAG);
    if (fc_freeze_events(&s_fz, flag))
        cam_log("freeze: an event wrote 0xAF0EF4=%u (was %u); restored on unfreeze", flag, was);
    G32(STOP_FLAG) = 1;
}

void free_cam_freeze_tick(void)
{
    int wrote;
    uint32_t flag;

    if (!s_fz.on || !mem_ok())
        return;
    flag = G32(STOP_FLAG);
    if (fc_freeze_tick(&s_fz, flag, G32(RUN_FLAG), G32(MENU_FLAG), &wrote) == FC_FZ_KEEP) {
        G32(STOP_FLAG) = 1;
        if (wrote)
            cam_log("freeze: the game wrote 0xAF0EF4=%u; restored on unfreeze", flag);
    } else {
        G32(STOP_FLAG) = s_fz.restore;
        cam_log("freeze dropped: run=%u menu=%u stop=%u, put back %u", G32(RUN_FLAG),
                G32(MENU_FLAG), flag, s_fz.restore);
    }
}

void free_cam_stage_start(void)
{
    if (s_fz.on && mem_ok()) {
        uint32_t v = fc_freeze_drop(&s_fz);

        G32(STOP_FLAG) = v;
        cam_log("freeze dropped: the stage (re)started, put back %u", v);
    }
}

/* ---- toggle, seed, fly ------------------------------------------------------ */

static void hud_apply(int hide)
{
    __atomic_store_n(&s_hud_hide_now, hide, __ATOMIC_RELEASE);
}

/* The game's camera as the free camera's start: the eye it built last
 * (p - o), and its pitch and yaw (D2). */
static int seed(void)
{
    uint32_t cam = G32(CAM_PTR);
    int i;

    if (!cam)
        return 0;
    for (i = 0; i < 3; i++)
        s_cam.p[i] = GF(cam + 0x2C + i * 4);
    s_cam.pitch = GF(cam + 0x0C);
    s_cam.yaw = GF(cam + 0x10);
    return 1;
}

static void toggle(void)
{
    if (s_flying) {
        freeze_off();
        s_flying = 0;
        hud_apply(0);
        s_api->input_capture(0);
        cam_log("off");
        return;
    }
    if (!seed()) {
        cam_log("no game camera now");
        return;
    }
    s_flying = 1;
    s_last_ns = xbox_HostNowNs();
    /* camera.free_hud applies at the next activation: this one. */
    hud_apply(s_api->setting(&k_desc, SET_HUD) == 1);
    s_api->input_capture(1);
    cam_log("on at (%.1f %.1f %.1f) pitch %.3f yaw %.3f", s_cam.p[0], s_cam.p[1], s_cam.p[2],
            s_cam.pitch, s_cam.yaw);
}

/* One function per action, called by on_frame when the toolkit's host
 * action fires (its keys, chords and pad buttons). All run on the guest
 * thread. */
void free_cam_action_toggle(void)
{
    if (on_now() && mem_ok())
        toggle();
}

void free_cam_action_hud(void)
{
    if (s_flying) {
        int h = !__atomic_load_n(&s_hud_hide_now, __ATOMIC_ACQUIRE);
        hud_apply(h);
        cam_log("hud %s", h ? "hidden" : "shown");
    }
}

void free_cam_action_freeze(void)
{
    if (s_flying) {
        if (s_fz.on)
            freeze_off();
        else
            freeze_on();
    }
}

void free_cam_action_reset(void)
{
    if (s_flying && seed())
        cam_log("reset to the game camera");
}


static float analog(BYTE v)
{
    return v > XBOX_ANALOG_BUTTON_THRESHOLD ? (float)v / 255.0f : 0.0f;
}

/* A STICK control: its axes through the dead zone of the stick it reads,
 * so swapping Move and Look keeps each stick's own (7849 left, 8689
 * right, the XInput values the game's pad had). */
static void fly_stick(uint32_t k, float *x, float *y)
{
    struct xbox_ctl_value v;
    int dead;

    if (!s_api->control_value(&k_desc, k, &v)) {
        *x = *y = 0.0f;
        return;
    }
    dead = v.src == XBOX_CTL_SRC_RIGHT ? 8689 : 7849;
    *x = fc_axis(v.raw[0], dead);
    *y = fc_axis(v.raw[1], dead);
}

/* A BUTTON control: its largest binding, 0..255 (a key reads 255). */
static BYTE fly_button(uint32_t k)
{
    struct xbox_ctl_value v;

    if (!s_api->control_value(&k_desc, k, &v) || v.raw[0] <= 0)
        return 0;
    return v.raw[0] > 255 ? 255 : (BYTE)v.raw[0];
}

/* One frame of the captured controls. With the default bindings this is
 * the input the camera read from the merged pad before the controls could
 * be rebound: the larger of RT and X (E) rises, of LT and Y (Q) sinks,
 * White (C) is fast and Black (Z) slow. */
static void fly_input(struct fc_input *in)
{
    memset(in, 0, sizeof *in);
    fly_stick(CTL_MOVE, &in->lx, &in->ly);
    fly_stick(CTL_LOOK, &in->rx, &in->ry);
    in->up = analog(fly_button(CTL_RISE));
    in->down = analog(fly_button(CTL_SINK));
    in->fast = fly_button(CTL_FAST) > XBOX_ANALOG_BUTTON_THRESHOLD;
    in->slow = fly_button(CTL_SLOW) > XBOX_ANALOG_BUTTON_THRESHOLD;
}

static void fly(void)
{
    struct enhance_input_state st;
    struct fc_input in;
    struct fc_params par;
    uint64_t now = xbox_HostNowNs();
    float dt = (float)(now - s_last_ns) * 1e-9f;

    s_last_ns = now;
    fly_input(&in);
    s_api->input_state(&st);
    in.mouse_dx = (float)st.mouse_dx;
    in.mouse_dy = (float)st.mouse_dy;
    params_now(&par);
    fc_fly_step(&s_cam, &in, &par, dt);
}

static void on_frame(void *user)
{
    static void (*const action[ACT_N])(void) = {
        [ACT_TOGGLE] = free_cam_action_toggle,
        [ACT_HUD] = free_cam_action_hud,
        [ACT_FREEZE] = free_cam_action_freeze,
        [ACT_RESET] = free_cam_action_reset,
    };
    int k;

    (void)user;
    /* Dormant (inited off for the menu): the toolkit fires none of the
     * actions, and nothing here touches the guest. */
    if (!on_now())
        return;
    for (k = 0; k < ACT_N; k++)
        if (s_act[k] >= 0 && s_api->action_pressed(s_act[k]))
            action[k]();
    if (s_fz.on && (G32(RUN_FLAG) != 1 || G32(MENU_FLAG) != 0)) {
        uint32_t v = fc_freeze_drop(&s_fz);

        G32(STOP_FLAG) = v;
        cam_log("freeze dropped: run=%u menu=%u, put back %u", G32(RUN_FLAG),
                G32(MENU_FLAG), v);
    }
    if (s_flying) {
        if (!G32(CAM_PTR)) {
            /* The stage freed its camera: back to the game, which has none. */
            toggle();
            return;
        }
        fly();
    }
}

/* ---- HUD hide (D4) ----------------------------------------------------------- */

/* The back buffers: the colour offsets the flips presented (two or three). */
static uint32_t s_back[4];

static int is_back_buffer(uint32_t off, uint32_t presented)
{
    int i;

    for (i = 0; i < 4; i++)
        if (s_back[i] == presented)
            break;
    if (i == 4 && presented) {
        memmove(s_back + 1, s_back, sizeof s_back - sizeof s_back[0]);
        s_back[0] = presented;
    }
    for (i = 0; i < 4; i++)
        if (s_back[i] && s_back[i] == off)
            return 1;
    return 0;
}

/* The distinct matched batches, logged once each so the list in tasks.md
 * comes from a run. Render thread only. */
struct hud_sig { uint32_t hash, prim, blend; int depth; };
static struct hud_sig s_seen[32];
static int s_nseen;

static void note_match(const struct nv2a_batch_info *b)
{
    struct hud_sig s = { b->program_hash, b->prim,
                         (b->blend_sfactor << 16) | (b->blend_dfactor & 0xFFFF), b->depth_write };
    int i;

    for (i = 0; i < s_nseen; i++)
        if (!memcmp(&s_seen[i], &s, sizeof s))
            return;
    if (s_nseen < (int)(sizeof s_seen / sizeof s_seen[0]))
        s_seen[s_nseen++] = s;
    cam_log("hud batch: prog %08X prim %u idx %u blend %04X/%04X zwrite %d alphatest %d"
            " surface %ux%u @%08X flip %u",
            b->program_hash, b->prim, b->idx_count, b->blend_sfactor, b->blend_dfactor,
            b->depth_write, b->alpha_test, b->surface_w, b->surface_h, b->color_offset, b->flip);
}

static int hud_filter(const struct nv2a_batch_info *b, void *user)
{
    int back;

    (void)user;
    back = is_back_buffer(b->color_offset, b->present_offset);
    if (!__atomic_load_n(&s_hud_hide_now, __ATOMIC_ACQUIRE))
        return 0;
    if (b->program_hash != HUD_PROG_A && b->program_hash != HUD_PROG_B)
        return 0;
    if (b->depth_test || !b->blend || !back)
        return 0;
    note_match(b);
    return 1;
}

/* ---- the mod --------------------------------------------------------------- */

/* Off, from the Mods page mid-flight or not: the toggle-off path (camera
 * back to the game, the freeze dropped, the HUD shown, the pad given back).
 * On: the actions start doing something. On the guest thread, from the
 * next xbox_mod_frame; it may be told the state it is in already. */
static void on_enable(int on, void *user)
{
    (void)user;
    if (!on) {
        if (s_flying)
            toggle();
        else if (s_fz.on && mem_ok())
            freeze_off();
        hud_apply(0);
    }
    if (on == on_now())
        return;
    __atomic_store_n(&s_on, on, __ATOMIC_RELEASE);
    s_api->active(&s_mod, on);
    cam_log("%s", on ? "on" : "off");
}

static int init(const struct xbox_mod_api *api)
{
    struct fc_params p;
    int on;

    if (api->size < offsetof(struct xbox_mod_api, active) + sizeof api->active)
        return 1;   /* no v3 settings or v4 active: stay stock */
    s_api = api;
    /* Inited on, or dormant (off, the menu able to turn it on). The toolkit
     * printed "[ENHANCE] camera.free=" before this, inited or not. */
    on = api->setting(&k_desc, SET_ENABLE) != 0;
    __atomic_store_n(&s_on, on, __ATOMIC_RELEASE);
    s_act[ACT_TOGGLE] = api->control_action(&k_desc, CTL_TOGGLE);
    s_act[ACT_HUD] = api->control_action(&k_desc, CTL_HUD);
    s_act[ACT_FREEZE] = api->control_action(&k_desc, CTL_FREEZE);
    s_act[ACT_RESET] = api->control_action(&k_desc, CTL_RESET);
    /* The actions fire through the actions hook, which the menu arms when
     * it is on; with the menu off the camera's switch arms it, and the
     * toolkit re-evaluates it on a live switch. */
    api->actions_arm("camera.free");
    /* A mod that never reports is listed in [ENHANCE] mods= while it runs:
     * dormant, it does nothing. */
    api->active(&s_mod, on);
    api->on_frame(on_frame, NULL);
    api->batch_filter(hud_filter, NULL);
    api->on_enable(on_enable, NULL);
    if (on) {
        params_now(&p);
        cam_log("on: speed %g look %g mouse %g fast %g slow %g invert x %s y %s hud %s",
                p.speed, p.look_sens, p.mouse_sens, p.fast, p.slow,
                p.invert_x ? "on" : "off", p.invert_y ? "on" : "off",
                api->setting(&k_desc, SET_HUD) == 1 ? "hide" : "keep");
    }
    return 0;
}

/* Put the world and the pad back at exit; the memory stays (mod.h). */
static void shutdown_mod(void)
{
    if (s_fz.on && mem_ok())
        freeze_off();
    if (s_flying) {
        s_flying = 0;
        s_api->input_capture(0);
    }
    hud_apply(0);
}

static const struct xbox_mod s_mod = { "camera.free", init, shutdown_mod, &k_desc,
                                       XBOX_MOD_NEED_POKE };

const void *free_cam_mod(void)
{
    return &s_mod;
}

int free_cam_view(struct fc_cam *c)
{
    if (!s_flying)
        return 0;
    if (c)
        *c = s_cam;
    return 1;
}

void free_cam_frame(void)
{
    xbox_mod_frame();
}

#else /* no mod API: stock */

const void *free_cam_mod(void) { return NULL; }
int free_cam_view(struct fc_cam *c) { (void)c; return 0; }
void free_cam_frame(void) {}
void free_cam_action_toggle(void) {}
void free_cam_action_hud(void) {}
void free_cam_action_freeze(void) {}
void free_cam_action_reset(void) {}
void free_cam_events_pre(void) {}
void free_cam_events_post(void) {}
void free_cam_freeze_tick(void) {}
void free_cam_stage_start(void) {}

#endif
