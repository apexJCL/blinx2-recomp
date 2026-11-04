/*
 * glow_mod.c - the glow mod, shown to players as "Bloom" (glow_mod.h;
 * openspec change glow-mod). Its id, keys and env rows keep the glow name so
 * players' configs and the goldens' enhance_stock still match.
 *
 * The weight of the game's mode-3 glow pass, as the sub_0005B7D0 wrapper in
 * recomp_manual.c applies it (glow.c has the maths). The wrapper scales the
 * weight on each call, so every setting is live: the mod only hands
 * glow.c the factor its settings make, at init and after each change.
 *
 * The mod's switch means "apply the glow settings": off, or never inited
 * (mods."glow.enable" off with the menu off), is the stock glow whatever
 * fx.glow says (design D1). The two settings keep their old keys, fx.glow
 * and fx.glow_intensity, and env rows (D2).
 */
#include <stddef.h>
#include "glow_mod.h"
#include "glow.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 4
#      define GLOW_MOD 1
#    endif
#  endif
#endif

#ifdef GLOW_MOD

#include "enhance_menu.h"

enum { SET_ENABLE, SET_GLOW, SET_INTENSITY, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, NULL, NULL, "Bloom settings",
      "Apply the two settings below. Off draws the game's own bloom.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 1, 0, 0, 0, k_offon },
    [SET_GLOW] = { "glow", "fx.glow", "RECOMP_GLOW", NULL, "Bloom",
      "The game's soft bloom over bright parts of the frame. Off draws the"
      " frame without it.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, 0, 1, 0, 0, 0, k_offon },
    [SET_INTENSITY] = { "intensity", "fx.glow_intensity", "RECOMP_GLOW_INTENSITY", NULL,
      "Bloom intensity",
      "How strong the bloom is: 1 is the game's, 0 none, 2 twice as strong.",
      "x", XBOX_SET_FLOAT, ENHANCE_LIVE, 0, 1, 0, 2, 0.05, NULL },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Bloom",
    "The game's bloom: on or off, and how strong", NULL, "1",
    k_set, SET_N, NULL, 0
};

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;
static int s_on;    /* guest thread only: init, then the mod frame */

/* glow.c's factor from the settings now, and the mods= line's state: the
 * mod is active only while it changes the frame (design D5). */
static void apply(void)
{
    int off = 0;
    double k = 1.0;

    if (s_on) {
        off = s_api->setting(&k_desc, SET_GLOW) == 0;
        k = s_api->setting(&k_desc, SET_INTENSITY);
    }
    glow_configure(off, k);
    s_api->active(&s_mod, glow_active());
}

static void on_setting(uint32_t idx, double value, void *user)
{
    (void)user;
    apply();
    /* With the switch off the value is kept for later, not applied. */
    if (idx == SET_GLOW)
        s_api->log(&s_mod, "glow %s%s", value != 0 ? "on" : "off",
                   s_on ? "" : " (dormant: the mod is off)");
    else if (idx == SET_INTENSITY)
        s_api->log(&s_mod, "intensity %g%s", value,
                   s_on ? "" : " (dormant: the mod is off)");
}

static void on_enable(int on, void *user)
{
    (void)user;
    if (on == s_on)
        return;
    s_on = on;
    apply();
    s_api->log(&s_mod, "%s", on ? "on" : "off (stock glow)");
}

static int init(const struct xbox_mod_api *api)
{
    s_api = api;
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    apply();
    if (glow_active())
        api->log(&s_mod, "on: glow %s, intensity %g",
                 api->setting(&k_desc, SET_GLOW) != 0 ? "on" : "off",
                 api->setting(&k_desc, SET_INTENSITY));
    api->on_setting(&k_desc, on_setting, NULL);
    api->on_enable(on_enable, NULL);
    return 0;
}

/* needs: the wrapper writes the guest's weight word for the call. */
static const struct xbox_mod s_mod = { "glow", init, NULL, &k_desc, XBOX_MOD_NEED_POKE, NULL };

const void *glow_mod(void)
{
    return &s_mod;
}

#else /* no mod API v4: main.c reads the keys */

const void *glow_mod(void)
{
    return NULL;
}

#endif
