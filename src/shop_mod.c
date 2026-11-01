/*
 * shop_mod.c - the shop mod (shop_mod.h; openspec change shop-api, design
 * D7, D9).
 *
 * The mod owns the shop API (shop_api.c): attaching it registers the fire
 * hook, and its switch is the API's. On top it gives the player five
 * percents through the API's mod percents: every price, every gun's
 * capacity and ammo per purchase, every gun's shot power, shot speed and
 * busy frames between shots.
 *
 * RECOMP_DEBUG=shop_proof=<steps> logs the shop, player 0's gold and gun
 * each frame and every shot the hook scaled, and fires a gun on a schedule
 * for the design's live proof (proof_*).
 *
 * Off (the default, every golden): the hook does not run and the API's
 * on_frame writes nothing, so the tables stay the XBE's.
 */
#include <stddef.h>
#include "shop_mod.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define SHOP_MOD 1
#    endif
#  endif
#endif

#ifdef SHOP_MOD

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "enhance_menu.h"
#include "recomp_env.h"
#include "shop_api.h"
#include "shop_api_logic.h"

enum { SET_ENABLE, SET_PRICE, SET_AMMO, SET_POWER, SET_SPEED, SET_INTERVAL, SET_N };

static const char *const k_offon[] = { "off", "on", NULL };

static const struct xbox_mod_setting k_set[SET_N] = {
    /* name, key, env, aliases, label, help, unit, kind, live, flags,
     * def, lo, hi, step, choices */
    [SET_ENABLE] = { "enable", NULL, "RECOMP_SHOP", NULL, "Shop and weapons",
      "Change the shop's prices and the guns' ammo, power, shot speed and fire"
      " rate. Off puts the game's prices and stats back (a story shop already"
      " open keeps its prices until you leave) and owned ammo above a gun's"
      " capacity down to it; none of it is saved. Gold spent and weapons"
      " bought stay yours, as any purchase.",
      NULL, XBOX_SET_ENUM, ENHANCE_LIVE, XBOX_SET_ENABLE, 0, 0, 0, 0, k_offon },
    [SET_PRICE] = { "price_pct", NULL, "RECOMP_SHOP_PRICE_PCT", NULL, "Prices",
      "Every price in the shop, rounded to 10. A sale or trade-in pays from"
      " the price at that moment: the story shop buys back at half, so an"
      " item bought at a low percent and sold with the mod off pays half its"
      " stock price.",
      "%", XBOX_SET_INT, ENHANCE_LIVE, 0, 100, 10, 500, 10, NULL },
    [SET_AMMO] = { "ammo_pct", NULL, "RECOMP_SHOP_AMMO_PCT", NULL, "Gun ammo",
      "Every gun's capacity and the ammo a purchase gives, 1 to 99. From the"
      " next gun taken.",
      "%", XBOX_SET_INT, ENHANCE_LIVE, 0, 100, 50, 500, 10, NULL },
    [SET_POWER] = { "power_pct", NULL, "RECOMP_SHOP_POWER_PCT", NULL, "Gun power",
      "The damage of every gun's shots.",
      "%", XBOX_SET_INT, ENHANCE_LIVE, 0, 100, 50, 500, 10, NULL },
    [SET_SPEED] = { "speed_pct", NULL, "RECOMP_SHOP_SPEED_PCT", NULL, "Shot speed",
      "How fast every gun's shots fly; they reach as much farther.",
      "%", XBOX_SET_INT, ENHANCE_LIVE, 0, 100, 50, 300, 10, NULL },
    [SET_INTERVAL] = { "interval_pct", NULL, "RECOMP_SHOP_INTERVAL_PCT", NULL, "Gun recovery",
      "The frames a gun stays busy after a shot; lower fires faster. Not for"
      " the two lock-on guns.",
      "%", XBOX_SET_INT, ENHANCE_LIVE, 0, 100, 25, 100, 5, NULL },
};

static const struct xbox_mod_desc k_desc = {
    XBOX_MOD_DESC_VERSION, sizeof k_desc, "Shop",
    "Shop prices and gun stats", NULL, "1",
    k_set, SET_N, NULL, 0
};

/* The first checkpoint flag the proof's play frames count from (as in
 * entities_mod.c). */
#define VA_CKPT         0x00AE73FCu
/* The shop's state for player 0 (+0 state, +0x10 cursor), its lineup of
 * catalogue indices and their count (menu_shop, sub_00210660). */
#define VA_SHOP0        0x00EB3AF0u
#define VA_LINEUP0      0x00E97F68u
#define VA_LINEUP0_N    0x00EB3BF8u
#define VA_FIRE         0x001A0260u
#define LINEUP_LOG      4

static const int k_cat_log[] = { 4, 5, 21, 22, 23 };

static const struct xbox_mod s_mod;
static const struct xbox_mod_api *s_api;
static int s_on;                        /* guest thread */

/* ---- the proof driver (guest thread) ----------------------------------- */

static FILE *s_out;
static long o_gun = -1, o_fire = -1, o_every = -1, o_shots = -1, o_gold = -1, o_goldat = -1;
static uint32_t s_frame, s_play;
static int s_playing, s_fired;

static int32_t rd32(uint32_t va)
{
    return (int32_t)XBOX_MOD_MEM32(s_api, va);
}

static uint8_t *gm(uint32_t va)
{
    return (uint8_t *)s_api->mem + va;
}

static float rdf(uint32_t va)
{
    float f;

    memcpy(&f, gm(va), 4);
    return f;
}

static void proof_shot(int gun, uint32_t slot, void *user)
{
    float v[3];
    int16_t life;
    int i;

    (void)user;
    if (!s_out)
        return;
    for (i = 0; i < 3; i++)
        v[i] = rdf(slot + SHOPL_SLOT_VEL + 4u * (uint32_t)i);
    memcpy(&life, gm(slot + SHOPL_SLOT_LIFE), 2);
    fprintf(s_out, "#shot f%u gun %d slot %08X type %02X speed %.3f life %d timer %.2f\n", s_frame,
            gun, slot, *gm(slot + SHOPL_SLOT_TYPE),
            sqrt((double)v[0] * v[0] + (double)v[1] * v[1] + (double)v[2] * v[2]), life,
            (double)rdf(SHOPL_PLAYER0_VA + SHOPL_PLR_TIMER));
}

static void proof_log(void)
{
    int n = rd32(VA_LINEUP0_N), i, w = 0, a = 0;
    struct shop_gun g;
    uint8_t *p = gm(SHOPL_PLAYER0_VA);

    shop_owned_get(0, 0, &w, &a);
    fprintf(s_out, "F %u play %u shop %d cur %d gold %d own %d/%d gun %d ammo %d/%d timer %.2f |",
            s_frame, s_playing ? s_play : 0, rd32(VA_SHOP0), rd32(VA_SHOP0 + 0x10),
            rd32(SHOPL_STATUS_VA + SHOPL_STATUS_GOLD), w, a, (int8_t)p[SHOPL_PLR_WEAPON],
            p[SHOPL_PLR_AMMO], p[SHOPL_PLR_CAP], (double)rdf(SHOPL_PLAYER0_VA + SHOPL_PLR_TIMER));
    for (i = 0; i < LINEUP_LOG && i < n && n <= 40; i++) {
        int idx = rd32(VA_LINEUP0 + 4u * (uint32_t)i);
        struct shop_item it;

        if (shop_item_get(idx, &it) == SHOP_OK)
            fprintf(s_out, " %d:c%d:v%d:%d/%d", idx, it.category, it.value, it.price,
                    it.game_price);
    }
    /* A jetpack and the first vacuums, the shop's first page, so a run
     * that never reads the lineup still shows the prices it drew. */
    fputs(" | cat", s_out);
    for (i = 0; i < (int)(sizeof k_cat_log / sizeof *k_cat_log); i++) {
        struct shop_item it;

        if (shop_item_get(k_cat_log[i], &it) == SHOP_OK)
            fprintf(s_out, " %d:%d/%d", k_cat_log[i], it.price, it.game_price);
        else
            fprintf(s_out, " %d:-", k_cat_log[i]);
    }
    /* The story shop's Arms page: the TS-2000 and the TS-2100. */
    fputs(" | arms", s_out);
    for (i = 1; i <= 2; i++) {
        int32_t pr, gp;

        if (shop_list_price_get(0, i, &pr, &gp) == SHOP_OK)
            fprintf(s_out, " %d:%d/%d", i, (int)pr, (int)gp);
        else
            fprintf(s_out, " %d:-", i);
    }
    if (o_gun >= 0 && shop_gun_get((int)o_gun, &g) == SHOP_OK)
        fprintf(s_out, " | gun %d shot %X cap %d/%d buy %d/%d power %d/%d speed %d%% interval %d%%",
                g.id, g.shot, g.capacity, g.game_capacity, g.buy, g.game_buy, g.power,
                g.game_power, g.speed_pct, g.interval_pct);
    fputc('\n', s_out);
    if (!(s_frame % 30))
        fflush(s_out);
}

/* Fire gun o_gun from player 0 as the gate does: the gun and a full load
 * in the player's object, then the fire function, so a run fires without
 * a pad binding for the gun. */
static void proof_fire(void)
{
    uint32_t arg = SHOPL_PLAYER0_VA;
    struct xbox_guest_args a;
    uint8_t *p = gm(SHOPL_PLAYER0_VA);
    struct shop_gun g;

    p[SHOPL_PLR_WEAPON] = (uint8_t)o_gun;
    if (shop_gun_get((int)o_gun, &g) == SHOP_OK) {
        p[SHOPL_PLR_CAP] = (uint8_t)g.capacity;
        p[SHOPL_PLR_AMMO] = (uint8_t)g.capacity;
    }
    memset(&a, 0, sizeof a);
    a.stack = &arg;
    a.n_stack = 1;
    if (!s_api->guest_call(VA_FIRE, &a, NULL))
        s_api->log(&s_mod, "proof: fire call refused f%u", s_frame);
    else if (s_out)
        fprintf(s_out, "#fire f%u play %u gun %ld timer %.2f ammo %d\n", s_frame, s_play, o_gun,
                (double)rdf(SHOPL_PLAYER0_VA + SHOPL_PLR_TIMER), p[SHOPL_PLR_AMMO]);
}

static void proof_frame(void)
{
    s_frame++;
    if (o_gold >= 0 && (long)s_frame == o_goldat) {
        XBOX_MOD_MEM32(s_api, SHOPL_STATUS_VA + SHOPL_STATUS_GOLD) = (uint32_t)o_gold;
        s_api->log(&s_mod, "proof: player 0 gold %ld f%u", o_gold, s_frame);
    }
    if (!s_playing && XBOX_MOD_MEM32(s_api, VA_CKPT) == 1) {
        s_playing = 1;
        s_play = 0;
        s_api->log(&s_mod, "proof: play starts f%u", s_frame);
    }
    if (s_playing) {
        long f = (long)s_play;

        if (o_gun >= 0 && o_fire >= 0 && f >= o_fire && (o_shots < 0 || s_fired < o_shots) &&
            (f - o_fire) % (o_every > 0 ? o_every : 30) == 0) {
            s_fired++;
            proof_fire();
        }
        s_play++;
    }
    if (s_out)
        proof_log();
}

static long opt(const char *v, const char *name)
{
    size_t l = strlen(name);
    const char *p;

    for (p = v; p && *p;) {
        if (!strncmp(p, name, l) && p[l] == ':')
            return strtol(p + l + 1, NULL, 0);
        p = strchr(p, '+');
        if (p)
            p++;
    }
    return -1;
}

/* RECOMP_DEBUG splits on commas, so the steps are joined by '+'. */
static void proof_init(const char *v)
{
    char path[512] = "shop_proof.tsv";
    const char *o = strstr(v, "out:");

    if (o) {
        size_t l = strcspn(o + 4, "+");

        if (l >= sizeof path)
            l = sizeof path - 1;
        memcpy(path, o + 4, l);
        path[l] = 0;
    }
    o_gun = opt(v, "gun");
    o_fire = opt(v, "fire");
    o_every = opt(v, "every");
    o_shots = opt(v, "shots");
    o_gold = opt(v, "gold");
    o_goldat = opt(v, "goldat");
    if (opt(v, "log") > 0) {
        s_out = fopen(path, "w");
        if (!s_out)
            s_api->log(&s_mod, "proof: cannot write %s", path);
        else
            shop_api_on_shot(proof_shot, NULL);
    }
    s_api->log(&s_mod, "proof: log %s, gun %ld, fire %ld, every %ld, shots %ld, gold %ld at %ld",
               s_out ? path : "off", o_gun, o_fire, o_every, o_shots, o_gold, o_goldat);
}

/* ---- the mod ----------------------------------------------------------- */

static void pct_from_settings(void)
{
    shop_api_pct((int)s_api->setting(&k_desc, SET_PRICE), (int)s_api->setting(&k_desc, SET_AMMO),
                 (int)s_api->setting(&k_desc, SET_POWER), (int)s_api->setting(&k_desc, SET_SPEED),
                 (int)s_api->setting(&k_desc, SET_INTERVAL));
}

static void on_frame(void *user)
{
    (void)user;
    if (!s_on || !s_api->mem)
        return;
    if (o_gun >= 0 || o_gold >= 0 || s_out)
        proof_frame();
}

static void on_enable(int on, void *user)
{
    (void)user;
    shop_api_enable(on);
    if (on == s_on)
        return;
    s_on = on;
    s_api->log(&s_mod, "%s", on ? "on" : "off: the game's prices and stats are back");
}

static void on_setting(uint32_t idx, double value, void *user)
{
    (void)user, (void)value;
    if (idx != SET_ENABLE)
        pct_from_settings();
}

/* ---- the Status row (menu thread) -------------------------------------- */

static const char *status_get(const struct enhance_item *it, char *buf, size_t n)
{
    (void)it;
    if (s_api->setting(&k_desc, SET_ENABLE) == 0)
        snprintf(buf, n, "off: the game's prices and stats");
    else if (shop_api_ready() < 0)
        snprintf(buf, n, "off: this is not the retail game's data");
    else if (shop_api_ready() == 0 || !s_api->mem)
        snprintf(buf, n, "the game has not started");
    else
        snprintf(buf, n, "on: prices %d%%, ammo %d%%, power %d%%, speed %d%%, recovery %d%%",
                 (int)s_api->setting(&k_desc, SET_PRICE), (int)s_api->setting(&k_desc, SET_AMMO),
                 (int)s_api->setting(&k_desc, SET_POWER), (int)s_api->setting(&k_desc, SET_SPEED),
                 (int)s_api->setting(&k_desc, SET_INTERVAL));
    return buf;
}

static const struct enhance_item k_status_row = {
    "mods.shop.status", "Status", NULL, ENHANCE_ITEM_INFO,
    NULL, 0, 0, 0, NULL, NULL, status_get, ENHANCE_LIVE, ENHANCE_ITEM_NOSAVE,
    NULL, NULL
};

static int init(const struct xbox_mod_api *api)
{
    const char *proof = recomp_env(RENV_SHOP_PROOF);

    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc)
        return 1;   /* no v6 calls: the API stays off */
    s_api = api;
    /* First: the API's hook and on_frame, so this frame's tables are
     * written before the proof reads them. */
    if (!shop_api_attach(api, &s_mod))
        return 1;
    s_on = api->setting(&k_desc, SET_ENABLE) != 0;
    pct_from_settings();
    shop_api_enable(s_on);
    api->on_frame(on_frame, NULL);
    api->on_enable(on_enable, NULL);
    api->on_setting(&k_desc, on_setting, NULL);
    api->menu_add(&k_status_row);
    if (proof)
        proof_init(proof);
    if (s_on)
        api->log(&s_mod, "on: prices %d%%, ammo %d%%, power %d%%, speed %d%%, recovery %d%%",
                 (int)api->setting(&k_desc, SET_PRICE), (int)api->setting(&k_desc, SET_AMMO),
                 (int)api->setting(&k_desc, SET_POWER), (int)api->setting(&k_desc, SET_SPEED),
                 (int)api->setting(&k_desc, SET_INTERVAL));
    return 0;
}

static const struct xbox_mod s_mod = { "shop", init, NULL, &k_desc,
                                       XBOX_MOD_NEED_POKE | XBOX_MOD_NEED_HOOK };

const void *shop_mod(void)
{
    return &s_mod;
}

#else /* no mod API v6: stock */

const void *shop_mod(void)
{
    return NULL;
}

#endif
