/*
 * hud_mod.c - the hud mod (hud_mod.h; openspec change hud-anchors).
 *
 * Every 2D sprite, glyph run and fade reaches the draw queue through
 * sub_00042190, which copies the caller's vertices into its pool before it
 * returns. The pre hook hands those vertices to the toolkit's HUD layer,
 * which finds the element by its call site in config/hud.toml (embedded
 * here at build time) and moves, clips or stretches it for the wide frame;
 * the post hook puts the caller's x and u back, since the helpers' stack
 * copies and the game's own buffers are drawn from again.
 *
 * The layer decides everything: while it is not active (4:3, the mod off,
 * no table) hud_apply returns at its first test and no vertex changes.
 */
#include <stddef.h>
#include "hud_mod.h"
#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 5
#      define HUD_MOD 1
#    endif
#  endif
#endif

#ifdef HUD_MOD
#include "enhance_menu.h"
#include "hud_table.h"          /* config/hud.toml, from CMake */

/* The pre and post do only hud_apply and hud_restore, so they are right as
 * they are while a mapping capture runs them with the mod off. */

/* sub_00042190: cdecl, vertices at ecx ({x, y, u, v} f32), the vertex
 * count first on the stack and the queue flag (0: queue 0, else queue 1)
 * fifth. */
#define HUD_ADD_VA      0x00042190u
#define HUD_ADD_ARG_N   0
#define HUD_ADD_ARG_Q   4

enum { SET_ENABLE, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

/* On by default, the one enhancement that is (the user's exception, design
 * A16): at 4:3 the layer is inactive and the game runs as stock, and on a
 * wide screen a HUD stranded in the middle is what nobody wants. The key is
 * mods."hud.enable" (off|on, as lod and debug_menu); display.hud_aspect and
 * display.hud_margin, which say where the edges are, belong to the
 * toolkit. */
static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_HUD", NULL, "HUD at the screen edges",
      "On a wide screen the radar, the time panel and the counters move out"
      " to the edges, as the game had them on a 4:3 TV. Does nothing at 4:3.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 1, 0, 0, 0, k_offon },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "HUD at the screen edges",
    "Keeps the HUD at the edges of a wide screen", NULL, "1",
    k_set, SET_N, NULL, 0
};

static const struct xbox_mod_api *s_api;

/* While the layer is inactive (4:3) this still reads two guest dwords
 * before hud_apply returns at its first test: about 1.5 CPU points at 16:9
 * on the PC, and the API has no cheaper "active" probe. Kept unless the
 * Deck's speed leg shows it. */
static void pre_add(struct xbox_mod_call *c, void *user)
{
    struct xbox_hud_call d;

    (void)user;
    d.vtx_va = c->ecx;
    d.n = XBOX_MOD_ARG32(s_api, c, HUD_ADD_ARG_N);
    d.flags = XBOX_HUD_RESTORE;
    d.queue = XBOX_MOD_ARG32(s_api, c, HUD_ADD_ARG_Q) != 0;
    d.tex = 0;
    s_api->hud_apply(c, &d);
}

static void post_add(struct xbox_mod_call *c, void *user)
{
    (void)user;
    s_api->hud_restore(c);
}

/* The Mods page's switch. The layer and this mod's hooks take the owner's
 * state at the next frame (the toolkit's hud_frame), so on and off land at
 * one flip, with every RESTORE of the frame before it already put back:
 * there is nothing left for the mod to do. Registering it is what makes
 * the switch live; without it the toolkit shows "applies at restart". */
static void on_enable(int on, void *user)
{
    (void)on;
    (void)user;
}

static int init(const struct xbox_mod_api *api)
{
    int n;

    if (api->size < offsetof(struct xbox_mod_api, hud_capturing) + sizeof api->hud_capturing)
        return 1;   /* no v5 HUD layer: the HUD stays where Hor+ puts it */
    s_api = api;
    n = api->hud_table((const char *)k_hud_table, sizeof k_hud_table);
    if (n < 0)
        return 1;   /* the layer said why */
    if (!api->hook(HUD_ADD_VA, pre_add, post_add, 0, NULL))
        return 1;
    api->on_enable(on_enable, NULL);
    return 0;
}

/* needs: the sprite add's hook and the wide aspect the layer reads, for
 * the enable gate (mod-connectivity-layer 4.2); nothing reads it yet. */
static const struct xbox_mod s_mod = {
    "hud", init, NULL, &k_desc, XBOX_MOD_NEED_HOOK | XBOX_MOD_NEED_ASPECT, NULL
};

const void *hud_mod(void)
{
    return &s_mod;
}
#else /* no mod API v5: stock */
const void *hud_mod(void)
{
    return NULL;
}
#endif
