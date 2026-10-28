/*
 * lod_scale.c - the lod mod (lod_scale.h; openspec change lod-scale).
 *
 * sub_0019A2C0 measures a character's screen radius in 640x480 units
 * whatever the render scale, so at 2x and 3x a model drops to its low
 * levels (no goggle geometry, blocky hands and feet, no shadow) as close
 * to the camera as at 480 lines. The mod rewrites thresholds 1..4
 * of the game's table at 0x450B08 (lod_table.c) so each level is reached at
 * the same size on screen as on the console.
 *
 * Threshold 0 is never written: level 0 is what the off-screen counter
 * (sub_00143F80) tests, so visibility and that logic stay the game's. The
 * game's split-screen factors scale the radius before the table and stay.
 *
 * Every write runs on the guest's thread from the mod frame (on_frame and
 * the on_enable callback both come from xbox_mod_frame), between the pad
 * poll and the frame's draws. The render scale has no change event; it is
 * read each frame (design D2).
 */
#include <stddef.h>
#include "lod_scale.h"
#include "lod_table.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 3
#      define LOD_MOD 1
#    endif
#  endif
#endif

#ifdef LOD_MOD

#include "enhance_menu.h"

enum { SET_ENABLE, SET_FOLLOW, SET_DISTANCE, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_LOD", NULL, "Detail follows resolution",
      "Characters keep their detailed models at the distance they had at 480p:"
      " goggles, gloves, boots and shadows at 2x and 3x. Follows the render"
      " scale setting, not the size drawn. Costs more draws.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
    [SET_FOLLOW] = { "follow_scale", NULL, "RECOMP_LOD_FOLLOW_SCALE", NULL,
      "Follow render scale",
      "Divide the detail distances by the render scale. Off: only the distance"
      " below applies.",
      NULL, XBOX_SET_BOOL, ENHANCE_LIVE, 0, 1, 0, 1, 0, NULL },
    [SET_DISTANCE] = { "distance", NULL, "RECOMP_LOD_DISTANCE", NULL, "Detail distance",
      "How far detail holds, on top of the render scale: 2 keeps it twice as far,"
      " 0.5 drops it at half the distance.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 1, 0.5, 4, 0.25, NULL },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Character detail",
    "Character detail levels follow the render scale", NULL, "1",
    k_set, SET_N, NULL, 0
};

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;

/* Guest thread only (init, then the mod frame), but for the best-effort
 * restore at exit (shutdown_mod). */
static int s_on;
static struct lod_state s_state;

/* Thresholds 1..4 into the table when they differ from the last write
 * (lod_step: the guards of design D5), and the log line that says so. */
static void put(const int32_t t[LOD_SCALED_N], unsigned scale, double dist)
{
    volatile uint32_t *w;

    if (!s_api->mem)
        return;
    w = (volatile uint32_t *)(s_api->mem + LOD_TABLE_VA);
    switch (lod_step(&s_state, w, t)) {
    case LOD_SAME:
    case LOD_DEAD:
        break;
    case LOD_WROTE:
        if (scale)
            s_api->log(&s_mod, "thresholds %d/%d/%d/%d/%d (scale %u, distance %g)",
                       lod_stock[0][0], t[0], t[1], t[2], t[3], scale, dist);
        else
            s_api->log(&s_mod, "stock thresholds back");
        break;
    case LOD_NOT_STOCK:
        s_api->log(&s_mod, "table at 0x%X is not the stock one (%d/%d/%d/%d/%d);"
                   " left alone", LOD_TABLE_VA, (int32_t)w[0], (int32_t)w[2],
                   (int32_t)w[4], (int32_t)w[6], (int32_t)w[8]);
        break;
    case LOD_FOREIGN:
        s_api->log(&s_mod, "table at 0x%X changed outside the mod (%d/%d/%d/%d);"
                   " left alone", LOD_TABLE_VA, (int32_t)w[2], (int32_t)w[4],
                   (int32_t)w[6], (int32_t)w[8]);
        break;
    }
}

static void put_stock(void)
{
    int32_t t[LOD_SCALED_N];

    lod_stock_thresholds(t);
    put(t, 0, 0.0);
}

static void on_frame(void *user)
{
    int32_t t[LOD_SCALED_N];
    unsigned scale;
    double dist;

    (void)user;
    if (s_state.dead)
        return;
    if (!s_on) {
        put_stock();    /* a no-op unless the mod wrote last */
        return;
    }
    /* render.scale changes live from the menu (a FLUSH item) and has no
     * event: one load a frame. It is the scale asked for; the CPU backend,
     * or D3D11 clamping a large window, may draw at less, and then the mod
     * keeps detail further out than the screen needs (design D2). */
    scale = s_api->setting(&k_desc, SET_FOLLOW) != 0 ? nv2a_host_render_scale() : 1u;
    dist = s_api->setting(&k_desc, SET_DISTANCE);
    lod_thresholds(scale, dist, t);
    put(t, scale, dist);
}

static void on_enable(int on, void *user)
{
    (void)user;
    if (on == s_on)
        return;
    s_on = on;
    s_api->log(&s_mod, "%s", on ? "on" : "off");
    /* The frame that follows (this one: on_enable runs from the same
     * xbox_mod_frame, before the frame hooks) writes or restores. */
}

static int init(const struct xbox_mod_api *api)
{
    if (api->size < offsetof(struct xbox_mod_api, on_setting))
        return 1;   /* no v3 setting getter: leave the table alone */
    s_api = api;
    lod_state_init(&s_state);
    /* Inited dormant (switched off, the menu able to turn it on) or on. */
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    if (s_on)
        api->log(&s_mod, "on: follow_scale %s, distance %g",
                 api->setting(&k_desc, SET_FOLLOW) != 0 ? "true" : "false",
                 api->setting(&k_desc, SET_DISTANCE));
    return 0;
}

/* Exit: the stock table back, best effort. This can run on the exit hook's
 * thread while a mod frame is still in flight, which may then write its
 * scaled values again or log a "changed outside the mod" line; neither
 * matters, since guest memory goes with the process (and after a crash
 * nothing runs here at all). s_on is left to the guest thread. */
static void shutdown_mod(void)
{
    put_stock();
}

static const struct xbox_mod s_mod = { "lod", init, shutdown_mod, &k_desc };

const void *lod_mod(void)
{
    return &s_mod;
}

#else /* no mod API v3: stock */

const void *lod_mod(void)
{
    return NULL;
}

#endif
