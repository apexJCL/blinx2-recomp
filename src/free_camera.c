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
 * the merged pad and keyboard the game would have read, saved before that
 * (cat_pad_port0_last). The toolkit's api->input_state pad is not used:
 * it is fed by the toolkit's own pad read, which this title replaces.
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
 * camera.free = off (stock): one log line, nothing registered, so neither
 * a frame callback nor the draw filter exists.
 */
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "free_camera.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    define FREE_CAM_MOD 1
#  endif
#endif

#ifdef FREE_CAM_MOD

#include "mod.h"
#include "host_time.h"
#include "keyboard.h"
#include "input_names.h"
#include "xinput_xbox.h"

/* pad_input.c: port 0 as the game's last poll merged it (script, host pad,
 * keyboard), before the neutral pad replaced it. */
extern int cat_pad_port0_last(XBOX_GAMEPAD *out);

#define CAM_PTR    0x4B271Cu    /* the game camera struct */
#define RUN_FLAG   0x449F40u    /* 1 while the stage runs */
#define MENU_FLAG  0xAE73B4u    /* pause menu or retry */
#define STOP_FLAG  0xAF0EF4u    /* the event world stop */

/* The HUD's vertex programs (spike.md, the 2D pass). */
#define HUD_PROG_A 0x5474DB2Au
#define HUD_PROG_B 0xB2913952u

enum { KEY_TOGGLE, KEY_HUD, KEY_FREEZE, KEY_RESET, KEY_N };

static const struct xbox_mod_api *s_api;
static int s_on; /* camera.free=on: the actions do something */
static int s_flying;                    /* guest thread */
static struct fc_cam s_cam;
static struct fc_params s_par;
static struct fc_freeze s_fz;
static int s_hud_default_hide;
static int s_hud_hide_now;              /* render thread reads it */
static int s_key_vk[KEY_N];
static int s_key_prev[KEY_N];
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

static int key_code(const char *key, const char *def)
{
    const char *name = s_api->cfg_string(key, def);
    int code = 0, is_mouse = 0;

    if (xbox_InputNameToCode(name, &code, &is_mouse) && !is_mouse)
        return code;
    cam_log("%s=%s is not a key name; using %s", key, name, def);
    xbox_InputNameToCode(def, &code, &is_mouse);
    return code;
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
    hud_apply(s_hud_default_hide);
    s_api->input_capture(1);
    cam_log("on at (%.1f %.1f %.1f) pitch %.3f yaw %.3f", s_cam.p[0], s_cam.p[1], s_cam.p[2],
            s_cam.pitch, s_cam.yaw);
}

/* One function per action. The keyboard path below calls them; a later
 * host-action layer (keys, chords, extra pad buttons) calls the
 * same ones. All run on the frame thread, from on_frame. */
void free_cam_action_toggle(void)
{
    if (s_on && mem_ok())
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

static void press(int k)
{
    static void (*const action[KEY_N])(void) = {
        [KEY_TOGGLE] = free_cam_action_toggle,
        [KEY_HUD] = free_cam_action_hud,
        [KEY_FREEZE] = free_cam_action_freeze,
        [KEY_RESET] = free_cam_action_reset,
    };

    action[k]();
}

static float analog(BYTE v)
{
    return v > XBOX_ANALOG_BUTTON_THRESHOLD ? (float)v / 255.0f : 0.0f;
}

static void fly(void)
{
    XBOX_GAMEPAD g;
    struct enhance_input_state st;
    struct fc_input in;
    uint64_t now = xbox_HostNowNs();
    float dt = (float)(now - s_last_ns) * 1e-9f;

    s_last_ns = now;
    memset(&in, 0, sizeof in);
    if (cat_pad_port0_last(&g)) {
        float lt = analog(g.bAnalogButtons[6]), rt = analog(g.bAnalogButtons[7]);
        float x = analog(g.bAnalogButtons[2]), y = analog(g.bAnalogButtons[3]);

        in.lx = fc_axis(g.sThumbLX, 7849);
        in.ly = fc_axis(g.sThumbLY, 7849);
        in.rx = fc_axis(g.sThumbRX, 8689);
        in.ry = fc_axis(g.sThumbRY, 8689);
        /* RT or X (E) rises, LT or Y (Q) sinks; white (C) fast, black (Z) slow. */
        in.up = rt > x ? rt : x;
        in.down = lt > y ? lt : y;
        in.fast = g.bAnalogButtons[5] > XBOX_ANALOG_BUTTON_THRESHOLD;
        in.slow = g.bAnalogButtons[4] > XBOX_ANALOG_BUTTON_THRESHOLD;
    }
    s_api->input_state(&st);
    in.mouse_dx = (float)st.mouse_dx;
    in.mouse_dy = (float)st.mouse_dy;
    fc_fly_step(&s_cam, &in, &s_par, dt);
}

static void on_frame(void *user)
{
    int k;

    (void)user;
    for (k = 0; k < KEY_N; k++) {
        int down = xbox_FramebufferKeyDown(s_key_vk[k]) != 0;
        if (down && !s_key_prev[k])
            press(k);
        s_key_prev[k] = down;
    }
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

static int init(const struct xbox_mod_api *api)
{
    static const char *const onoff[] = { "off", "on", NULL };
    static const char *const hud[] = { "keep", "hide", NULL };
    int on;

    s_api = api;
    api->cfg_bind_env("camera.free", RENV_CAMERA_FREE);
    api->cfg_bind_env("camera.free_speed", RENV_CAMERA_FREE_SPEED);
    api->cfg_bind_env("camera.free_look_sens", RENV_CAMERA_FREE_LOOK_SENS);
    api->cfg_bind_env("camera.free_hud", RENV_CAMERA_FREE_HUD);
    api->cfg_bind_env("camera.free_toggle", RENV_CAMERA_FREE_TOGGLE);
    api->cfg_bind_env("camera.free_hud_key", RENV_CAMERA_FREE_HUD_KEY);
    api->cfg_bind_env("camera.free_freeze_key", RENV_CAMERA_FREE_FREEZE_KEY);
    api->cfg_bind_env("camera.free_reset_key", RENV_CAMERA_FREE_RESET_KEY);
    on = api->cfg_choice("camera.free", onoff, 0) == 1;
    s_par.speed = (float)api->cfg_float("camera.free_speed", 1.0);
    s_par.look_sens = (float)api->cfg_float("camera.free_look_sens", 1.0);
    s_hud_default_hide = api->cfg_choice("camera.free_hud", hud, 0) == 1;
    s_key_vk[KEY_TOGGLE] = key_code("camera.free_toggle", "F6");
    s_key_vk[KEY_HUD] = key_code("camera.free_hud_key", "F7");
    s_key_vk[KEY_FREEZE] = key_code("camera.free_freeze_key", "F8");
    s_key_vk[KEY_RESET] = key_code("camera.free_reset_key", "F5");
    if (!(s_par.speed >= 0.05f && s_par.speed <= 20.0f)) {
        cam_log("camera.free_speed=%g out of range 0.05..20; using 1", s_par.speed);
        s_par.speed = 1.0f;
    }
    if (!(s_par.look_sens >= 0.05f && s_par.look_sens <= 10.0f)) {
        cam_log("camera.free_look_sens=%g out of range 0.05..10; using 1", s_par.look_sens);
        s_par.look_sens = 1.0f;
    }
    /* The golden check reads the game's keys from [ENHANCE] lines
     * (game.toml golden.enhance_stock), not from the [MOD] ones. */
    fprintf(stderr, "[ENHANCE] camera.free=%s\n", on ? "on" : "off");
    /* The init runs off as well (it reads its own key, so no follows), and
     * a mod that never reports is listed in [ENHANCE] mods= while it runs:
     * say whether it does anything, so a stock run logs mods=none. */
#if XBOX_MOD_API_VERSION >= 4
    if (api->size >= offsetof(struct xbox_mod_api, active) + sizeof api->active && api->active)
        api->active(&s_mod, on);
#endif
    if (!on)
        return 0;
    s_on = 1;
    api->on_frame(on_frame, NULL);
    api->batch_filter(hud_filter, NULL);
    cam_log("camera.free=on speed %g look %g hud %s keys %s %s %s %s",
            s_par.speed, s_par.look_sens, s_hud_default_hide ? "hide" : "keep",
            xbox_InputCodeName(s_key_vk[KEY_TOGGLE], 0), xbox_InputCodeName(s_key_vk[KEY_HUD], 0),
            xbox_InputCodeName(s_key_vk[KEY_FREEZE], 0),
            xbox_InputCodeName(s_key_vk[KEY_RESET], 0));
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

static const struct xbox_mod s_mod = { "camera.free", init, shutdown_mod };

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

int free_cam_pad_neutral(void)
{
    return xbox_mod_input_captured();
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
int free_cam_pad_neutral(void) { return 0; }

#endif
