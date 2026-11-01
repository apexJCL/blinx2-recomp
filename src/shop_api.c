/*
 * shop_api.c - the shop API's calls, its overrides and its fire hook
 * (shop_api.h; openspec change shop-api, design D1-D5).
 *
 * The tables live in the XBE's .data and only the guest thread reads them,
 * so every override is host state and on_frame, between two game frames,
 * writes the effective values (design D1). The game's own values are read
 * once, at the first on_frame while on, after a check that the tables are
 * the retail XBE's; a failed check leaves the API off for the session.
 *
 * Speed, life and the fire interval are immediates in the fire function
 * sub_001A0260 (ent_player_gun_fire), so its hook scales what one call
 * made: the pre hook notes the item pool's used bytes, the post hook
 * scales the shot slots the call took and moves the fire timer forward
 * (design D3). Both run inside the stage update, before the frame's
 * time-record step copies the pool, so a rewound shot comes back already
 * scaled (design D5).
 *
 * Off (the default): the hook is not called (the toolkit's rule for a
 * dormant mod) and on_frame writes nothing, except once after the switch,
 * to put back every value it changed (design D2).
 */
#include <stddef.h>
#include <string.h>
#include "shop_api.h"
#include "shop_api_logic.h"

#if defined(RECOMP_ENV_HAVE_ENHANCE_KEYS) && defined(__has_include)
#  if __has_include("mod.h")
#    include "mod.h"
#    if XBOX_MOD_API_VERSION >= 6
#      define SHOP_API_LIVE 1
#    endif
#  endif
#endif

static const char *const k_status_text[] = {
    [SHOP_OK] = "done",
    [SHOP_OFF] = "the shop mod is off",
    [SHOP_RANGE] = "out of range",
    [SHOP_GONE] = "no such entry",
    [SHOP_BUSY] = "not on the game thread",
};

const char *shop_status_text(enum shop_status s)
{
    return (unsigned)s < sizeof k_status_text / sizeof *k_status_text ? k_status_text[s] : "?";
}

int shop_item_count(void)
{
    return SHOP_ITEMS;
}

int shop_gun_count(void)
{
    return SHOP_GUNS;
}

int shop_gun_shot(int id)
{
    return shopl_gun_shot(id);
}

int shop_list_count(int list)
{
    return list >= 0 && list < SHOP_LISTS ? shopl_list_n[list] : 0;
}

#ifdef SHOP_API_LIVE

#include <xbox/xboxrecomp.h>     /* g_xbox_total_ram */

#define VA_FIRE         0x001A0260u     /* ent_player_gun_fire(player*) */
#define PCT_MIN         10
#define PCT_MAX         1000
#define GUN_IDS         (SHOPL_GUN_LAST + 1)

static const struct xbox_mod_api *s_api;
static const struct xbox_mod *s_owner;
static int s_on;                        /* any thread, relaxed */
static int s_ready;                     /* 0, 1, -1; release once s_game is read */
static struct shopl_game s_game;        /* written once, before s_ready = 1 */

/* Any thread, relaxed: -1 for none. */
static struct shopl_over s_over;
static int32_t s_speed[GUN_IDS], s_life[GUN_IDS], s_interval[GUN_IDS];
static int s_pct_price = 100, s_pct_ammo = 100, s_pct_power = 100;
static int s_pct_speed = 100, s_pct_interval = 100;

/* Guest thread only. */
static int s_written;                   /* the tables differ from the game's */
static uint8_t s_before[SHOPL_POOL_N];
static int s_pre_gun;                   /* the gun the pre hook saw, or 0 */
static uint32_t s_pre_plr;              /* and the player object it fired */
static shop_shot_fn s_shot_fn;
static void *s_shot_user;
static const void *s_guest;             /* &t_marker on the guest thread */
static _Thread_local char t_marker;
static _Thread_local int t_in_hook;

#define LD(x)       __atomic_load_n(&(x), __ATOMIC_RELAXED)
#define ST(x, v)    __atomic_store_n(&(x), (v), __ATOMIC_RELAXED)

static struct shopl_mem mem(void)
{
    struct shopl_mem m;

    m.base = s_api ? (uint8_t *)s_api->mem : NULL;
    m.size = (uint32_t)g_xbox_total_ram;
    return m;
}

static int on_guest_thread(void)
{
    return t_in_hook || (s_guest && s_guest == (const void *)&t_marker);
}

static int live(void)
{
    return s_api && s_api->mem && LD(s_on) && __atomic_load_n(&s_ready, __ATOMIC_ACQUIRE) == 1;
}

static void clear_overrides(void)
{
    int32_t *w = (int32_t *)&s_over;
    size_t i;

    for (i = 0; i < sizeof s_over / sizeof *w; i++)
        ST(w[i], -1);
    for (i = 0; i < GUN_IDS; i++) {
        ST(s_speed[i], -1);
        ST(s_life[i], -1);
        ST(s_interval[i], -1);
    }
}

/* A gun's percent with the mod's on top, in PCT_MIN..PCT_MAX. */
static int gun_pct(const int32_t *per_gun, int id, int mod_pct)
{
    int32_t g = id >= 0 && id < GUN_IDS ? LD(per_gun[id]) : -1;
    int64_t v = (int64_t)(g < 0 ? 100 : g) * mod_pct / 100;

    return (int)(v < PCT_MIN ? PCT_MIN : v > PCT_MAX ? PCT_MAX : v);
}

/* ---- the fire hook ----------------------------------------------------- */

static void pre_fire(struct xbox_mod_call *c, void *user)
{
    struct shopl_mem m;
    uint32_t plr;
    int id;

    (void)user;
    s_pre_gun = 0;
    if (!live())
        return;
    plr = XBOX_MOD_ARG32(s_api, c, 0);
    m = mem();
    if (plr < SHOPL_PLAYER0_VA || plr >= SHOPL_PLAYER0_VA + SHOPL_PLAYERS * SHOPL_PLAYER_SIZE)
        return;
    id = (int8_t)m.base[plr + SHOPL_PLR_WEAPON];
    /* Vacuums keep theirs (non-goal). */
    if (id < SHOPL_GUN_FIRST || id > SHOPL_GUN_LAST)
        return;
    shopl_pool_used(&m, s_before);
    s_pre_plr = plr;
    s_pre_gun = id;
}

static void post_fire(struct xbox_mod_call *c, void *user)
{
    struct shopl_mem m;
    uint32_t plr, shots[8];
    int id = s_pre_gun, n, i, speed, life, interval;
    float t;

    (void)user;
    s_pre_gun = 0;
    if (!id || !live())
        return;
    t_in_hook++;
    m = mem();
    /* The pre hook's checked pointer: the callee may have reused its
     * argument slot. */
    plr = s_pre_plr;
    speed = gun_pct(s_speed, id, LD(s_pct_speed));
    life = gun_pct(s_life, id, 100);
    interval = gun_pct(s_interval, id, LD(s_pct_interval));
    n = shopl_scale_shots(&m, s_before, speed, life, shots, (int)(sizeof shots / sizeof *shots));
    memcpy(&t, m.base + plr + SHOPL_PLR_TIMER, 4);
    t = shopl_fire_timer(id, t, interval);
    memcpy(m.base + plr + SHOPL_PLR_TIMER, &t, 4);
    if (s_shot_fn)
        for (i = 0; i < n && i < (int)(sizeof shots / sizeof *shots); i++)
            s_shot_fn(id, shots[i], s_shot_user);
    t_in_hook--;
}

/* ---- on_frame ---------------------------------------------------------- */

static void clamp_owned(const struct shopl_mem *m)
{
    int n = shopl_clamp_owned(m, &s_game);

    if (n)
        s_api->log(s_owner, "owned ammo down to capacity on %d character(s)", n);
}

static void on_frame(void *user)
{
    struct shopl_mem m;
    struct shopl_over o;
    struct shopl_pct p;
    int32_t *src = (int32_t *)&s_over, *dst = (int32_t *)&o;
    size_t i;

    (void)user;
    if (!s_guest)
        s_guest = &t_marker;
    if (!s_api || !s_api->mem)
        return;
    m = mem();
    if (!LD(s_on)) {
        if (s_written) {
            shopl_restore(&m, &s_game);
            clamp_owned(&m);
            s_written = 0;
        }
        return;
    }
    if (s_ready == 0) {
        if (!shopl_check(&m)) {
            __atomic_store_n(&s_ready, -1, __ATOMIC_RELEASE);
            s_api->log(s_owner, "the shop tables are not the retail XBE's (0x4AACE0, 0x402860, "
                                "0x4022E0): off");
            return;
        }
        shopl_read_game(&m, &s_game);
        __atomic_store_n(&s_ready, 1, __ATOMIC_RELEASE);
        s_api->log(s_owner, "the retail shop tables are in");
    }
    if (s_ready != 1)
        return;
    for (i = 0; i < sizeof o / sizeof *dst; i++)
        dst[i] = LD(src[i]);
    p.price = LD(s_pct_price);
    p.ammo = LD(s_pct_ammo);
    p.power = LD(s_pct_power);
    i = (size_t)shopl_apply(&m, &s_game, &o, &p);
    if (i) {
        /* Once per change: a word the game wrote back would show here
         * every frame. */
        s_api->log(s_owner, "wrote %u table words", (unsigned)i);
        s_written = 1;
        /* A capacity just lowered (a percent or an override back down). */
        clamp_owned(&m);
    }
}

/* ---- the public calls -------------------------------------------------- */

enum shop_status shop_item_get(int idx, struct shop_item *out)
{
    struct shopl_mem m;
    uint32_t va;

    if (!live())
        return SHOP_OFF;
    if (!on_guest_thread())
        return SHOP_BUSY;
    if (idx < 0 || idx >= SHOP_ITEMS || !out)
        return SHOP_GONE;
    m = mem();
    va = SHOPL_CAT_VA + (uint32_t)idx * SHOPL_CAT_SIZE;
    out->name = s_game.name[idx];
    out->category = s_game.category[idx];
    memcpy(&out->price, m.base + va + SHOPL_CAT_PRICE, 4);
    memcpy(&out->value, m.base + va + SHOPL_CAT_VALUE, 4);
    out->game_price = s_game.price[idx];
    out->game_value = s_game.value[idx];
    return SHOP_OK;
}

enum shop_status shop_gun_get(int id, struct shop_gun *out)
{
    struct shopl_mem m;
    uint32_t va;
    int gi, shot;

    if (!live())
        return SHOP_OFF;
    if (!on_guest_thread())
        return SHOP_BUSY;
    gi = shopl_gun_index(&s_game, id);
    if (gi < 0 || !out)
        return SHOP_GONE;
    m = mem();
    va = SHOPL_GUN_VA + (uint32_t)gi * SHOPL_GUN_SIZE;
    shot = shopl_gun_shot(id);
    out->id = id;
    out->kind = s_game.kind[gi];
    out->shot = shot;
    memcpy(&out->capacity, m.base + va + SHOPL_GUN_CAP, 4);
    memcpy(&out->buy, m.base + va + SHOPL_GUN_BUY, 4);
    memcpy(&out->power,
           m.base + SHOPL_SHOT_VA + (uint32_t)shot * SHOPL_SHOT_SIZE + SHOPL_SHOT_POWER, 4);
    out->game_capacity = s_game.cap[gi];
    out->game_buy = s_game.buy[gi];
    out->game_power = s_game.power[shot];
    out->speed_pct = gun_pct(s_speed, id, LD(s_pct_speed));
    out->life_pct = gun_pct(s_life, id, 100);
    out->interval_pct = gun_pct(s_interval, id, LD(s_pct_interval));
    return SHOP_OK;
}

enum shop_status shop_item_set(int idx, int32_t price, int32_t value)
{
    enum shop_status st;

    if (!live())
        return SHOP_OFF;
    st = shopl_item_check(&s_game, idx, price, value);
    if (st != SHOP_OK)
        return st;
    ST(s_over.price[idx], price < 0 ? -1 : price);
    ST(s_over.value[idx], value < 0 ? -1 : value);
    return SHOP_OK;
}

enum shop_status shop_gun_set(int id, int32_t capacity, int32_t buy)
{
    int gi;

    if (!live())
        return SHOP_OFF;
    gi = shopl_gun_index(&s_game, id);
    if (gi < 0)
        return SHOP_GONE;
    if (capacity > 99 || capacity == 0 || capacity < -1 || buy > 99 || buy == 0 || buy < -1 ||
        (buy > 0 && buy > (capacity > 0 ? capacity : s_game.cap[gi])))
        return SHOP_RANGE;
    ST(s_over.cap[gi], capacity < 0 ? -1 : capacity);
    ST(s_over.buy[gi], buy < 0 ? -1 : buy);
    return SHOP_OK;
}

enum shop_status shop_shot_power_set(int type, int32_t power)
{
    if (!live())
        return SHOP_OFF;
    if (type < 0 || type >= SHOP_SHOTS)
        return SHOP_GONE;
    if (power < -1 || power > 999)
        return SHOP_RANGE;
    ST(s_over.power[type], power < 0 ? -1 : power);
    return SHOP_OK;
}

enum shop_status shop_list_price_get(int list, int idx, int32_t *price, int32_t *game_price)
{
    struct shopl_mem m;
    uint32_t va;

    if (!live())
        return SHOP_OFF;
    if (!on_guest_thread())
        return SHOP_BUSY;
    va = shopl_list_va_of(list, idx, SHOPL_LIST_PRICE);
    if (!va || !price || !game_price)
        return SHOP_GONE;
    m = mem();
    memcpy(price, m.base + va, 4);
    *game_price = s_game.list_price[list][idx];
    return SHOP_OK;
}

enum shop_status shop_list_price_set(int list, int idx, int32_t price)
{
    if (!live())
        return SHOP_OFF;
    if (!shopl_list_va_of(list, idx, 0))
        return SHOP_GONE;
    if (price < -1 || price > 999999)
        return SHOP_RANGE;
    ST(s_over.list_price[list][idx], price < 0 ? -1 : price);
    return SHOP_OK;
}

static int pct_bad(int32_t v)
{
    return v < -1 || (v >= 0 && (v < PCT_MIN || v > PCT_MAX));
}

enum shop_status shop_gun_scale(int id, int32_t speed_pct, int32_t life_pct,
                                int32_t interval_pct)
{
    if (!live())
        return SHOP_OFF;
    if (shopl_gun_shot(id) < 0)
        return SHOP_GONE;
    /* An interval above 100 % would mean moving the fire timer back,
     * which could fire again (D3), so it is refused, not ignored. */
    if (pct_bad(speed_pct) || pct_bad(life_pct) || pct_bad(interval_pct) || interval_pct > 100)
        return SHOP_RANGE;
    ST(s_speed[id], speed_pct < 0 ? -1 : speed_pct);
    ST(s_life[id], life_pct < 0 ? -1 : life_pct);
    ST(s_interval[id], interval_pct < 0 ? -1 : interval_pct);
    return SHOP_OK;
}

enum shop_status shop_owned_get(int player, int character, int *weapon, int *ammo)
{
    struct shopl_mem m;

    if (!live())
        return SHOP_OFF;
    if (!on_guest_thread())
        return SHOP_BUSY;
    if (!weapon || !ammo)
        return SHOP_GONE;
    m = mem();
    return shopl_owned_get(&m, player, character, weapon, ammo);
}

enum shop_status shop_owned_set(int player, int character, int weapon, int ammo)
{
    struct shopl_mem m;

    if (!live())
        return SHOP_OFF;
    if (!on_guest_thread())
        return SHOP_BUSY;
    m = mem();
    return shopl_owned_set(&m, &s_game, player, character, weapon, ammo);
}

int shop_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner)
{
    if (api->size < offsetof(struct xbox_mod_api, guest_alloc) + sizeof api->guest_alloc) {
        api->log(owner, "the toolkit's mod API is older than v6: off");
        return 0;
    }
    s_api = api;
    s_owner = owner;
    clear_overrides();
    if (!api->hook(VA_FIRE, pre_fire, post_fire, 0, NULL)) {
        api->log(owner, "the hook slot 0x001A0260 is missing (game.toml [mods] hook_functions): off");
        s_api = NULL;
        return 0;
    }
    api->on_frame(on_frame, NULL);
    return 1;
}

void shop_api_enable(int on)
{
    /* Off drops every override first, so a call racing the switch cannot
     * leave one behind for the next time on. */
    if (!on)
        clear_overrides();
    ST(s_on, on ? 1 : 0);
}

static int clamp_pct(int v)
{
    return v < PCT_MIN ? PCT_MIN : v > PCT_MAX ? PCT_MAX : v;
}

void shop_api_pct(int price, int ammo, int power, int speed, int interval)
{
    ST(s_pct_price, clamp_pct(price));
    ST(s_pct_ammo, clamp_pct(ammo));
    ST(s_pct_power, clamp_pct(power));
    ST(s_pct_speed, clamp_pct(speed));
    ST(s_pct_interval, clamp_pct(interval));
}

int shop_api_ready(void)
{
    return __atomic_load_n(&s_ready, __ATOMIC_ACQUIRE);
}

void shop_api_on_shot(shop_shot_fn fn, void *user)
{
    s_shot_user = user;
    s_shot_fn = fn;
}

#else /* no mod API v6: every call refuses */

enum shop_status shop_item_get(int idx, struct shop_item *out)
{
    (void)idx, (void)out;
    return SHOP_OFF;
}

enum shop_status shop_gun_get(int id, struct shop_gun *out)
{
    (void)id, (void)out;
    return SHOP_OFF;
}

enum shop_status shop_item_set(int idx, int32_t price, int32_t value)
{
    (void)idx, (void)price, (void)value;
    return SHOP_OFF;
}

enum shop_status shop_gun_set(int id, int32_t capacity, int32_t buy)
{
    (void)id, (void)capacity, (void)buy;
    return SHOP_OFF;
}

enum shop_status shop_shot_power_set(int type, int32_t power)
{
    (void)type, (void)power;
    return SHOP_OFF;
}

enum shop_status shop_list_price_get(int list, int idx, int32_t *price, int32_t *game_price)
{
    (void)list, (void)idx, (void)price, (void)game_price;
    return SHOP_OFF;
}

enum shop_status shop_list_price_set(int list, int idx, int32_t price)
{
    (void)list, (void)idx, (void)price;
    return SHOP_OFF;
}

enum shop_status shop_gun_scale(int id, int32_t speed_pct, int32_t life_pct,
                                int32_t interval_pct)
{
    (void)id, (void)speed_pct, (void)life_pct, (void)interval_pct;
    return SHOP_OFF;
}

enum shop_status shop_owned_get(int player, int character, int *weapon, int *ammo)
{
    (void)player, (void)character, (void)weapon, (void)ammo;
    return SHOP_OFF;
}

enum shop_status shop_owned_set(int player, int character, int weapon, int ammo)
{
    (void)player, (void)character, (void)weapon, (void)ammo;
    return SHOP_OFF;
}

int shop_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner)
{
    (void)api, (void)owner;
    return 0;
}

void shop_api_enable(int on)
{
    (void)on;
}

void shop_api_pct(int price, int ammo, int power, int speed, int interval)
{
    (void)price, (void)ammo, (void)power, (void)speed, (void)interval;
}

int shop_api_ready(void)
{
    return 0;
}

void shop_api_on_shot(shop_shot_fn fn, void *user)
{
    (void)fn, (void)user;
}

#endif
