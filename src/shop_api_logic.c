/*
 * shop_api_logic.c - the shop API's pure rules (shop_api_logic.h).
 *
 * Every access goes through memcpy and a bounds check: the tables are
 * aligned, but pool slots (0x6C) and player objects (0x30C) put their
 * floats at any offset, and the view may be a test's short buffer.
 */
#include "shop_api_logic.h"

#include <string.h>

static uint8_t *host(const struct shopl_mem *m, uint32_t va, uint32_t n)
{
    if (m->base && va < m->size && n <= m->size - va)
        return m->base + va;
    return NULL;
}

static int32_t rd32(const struct shopl_mem *m, uint32_t va)
{
    int32_t v = 0;
    uint8_t *h = host(m, va, 4);

    if (h)
        memcpy(&v, h, 4);
    return v;
}

static float rdf(const struct shopl_mem *m, uint32_t va)
{
    float v = 0.0f;
    uint8_t *h = host(m, va, 4);

    if (h)
        memcpy(&v, h, 4);
    return v;
}

static int rd8(const struct shopl_mem *m, uint32_t va)
{
    uint8_t *h = host(m, va, 1);

    return h ? *h : 0;
}

/* Writes only a changed word, so the count says what an apply did. */
static int wr32(const struct shopl_mem *m, uint32_t va, int32_t v)
{
    uint8_t *h = host(m, va, 4);
    int32_t old;

    if (!h)
        return 0;
    memcpy(&old, h, 4);
    if (old == v)
        return 0;
    memcpy(h, &v, 4);
    return 1;
}

static void wrf(const struct shopl_mem *m, uint32_t va, float v)
{
    uint8_t *h = host(m, va, 4);

    if (h)
        memcpy(h, &v, 4);
}

static uint32_t cat_va(int i, uint32_t off)
{
    return SHOPL_CAT_VA + (uint32_t)i * SHOPL_CAT_SIZE + off;
}

static uint32_t gun_va(int i, uint32_t off)
{
    return SHOPL_GUN_VA + (uint32_t)i * SHOPL_GUN_SIZE + off;
}

static uint32_t shot_va(int i)
{
    return SHOPL_SHOT_VA + (uint32_t)i * SHOPL_SHOT_SIZE + SHOPL_SHOT_POWER;
}

const uint32_t shopl_list_va[SHOP_LISTS] = { 0x004938D0u, 0x00494598u, 0x00494C20u,
                                              0x004952F8u };
const int shopl_list_n[SHOP_LISTS] = { 43, 22, 23, 38 };

uint32_t shopl_list_va_of(int list, int idx, uint32_t off)
{
    if (list < 0 || list >= SHOP_LISTS || idx < 0 || idx >= shopl_list_n[list])
        return 0;
    return shopl_list_va[list] + (uint32_t)idx * SHOPL_LIST_SIZE + off;
}

/* Each list's last record carries its own index, and two prices as the
 * retail XBE has them (list 0 record 1, the TS-2000, 400; list 3 record 0,
 * 10). */
static int lists_check(const struct shopl_mem *m)
{
    int l, n;

    for (l = 0; l < SHOP_LISTS; l++) {
        n = shopl_list_n[l];
        if (!host(m, shopl_list_va[l], (uint32_t)n * SHOPL_LIST_SIZE) ||
            rd32(m, shopl_list_va_of(l, n - 1, SHOPL_LIST_INDEX)) != n - 1)
            return 0;
    }
    return rd32(m, shopl_list_va_of(0, 1, SHOPL_LIST_PRICE)) == 400 &&
           rd32(m, shopl_list_va_of(3, 0, SHOPL_LIST_PRICE)) == 10;
}

int shopl_check(const struct shopl_mem *m)
{
    return lists_check(m) && host(m, SHOPL_CAT_VA, SHOP_ITEMS * SHOPL_CAT_SIZE) &&
           host(m, SHOPL_GUN_VA, (SHOP_GUNS + 1) * SHOPL_GUN_SIZE) &&
           host(m, SHOPL_SHOT_VA, SHOP_SHOTS * SHOPL_SHOT_SIZE) &&
           rd32(m, cat_va(0, SHOPL_CAT_PRICE)) == 50 &&
           rd32(m, cat_va(0, SHOPL_CAT_CATEGORY)) == 0 &&
           rd32(m, cat_va(SHOP_ITEMS - 1, SHOPL_CAT_CATEGORY)) == 4 &&
           rd32(m, gun_va(0, 0)) == SHOPL_GUN_FIRST &&
           rd32(m, gun_va(SHOP_GUNS, 0)) == -1 &&
           rd32(m, shot_va(5)) == 10;
}

void shopl_read_game(const struct shopl_mem *m, struct shopl_game *g)
{
    int i, l;

    for (i = 0; i < SHOP_ITEMS; i++) {
        g->name[i] = (uint32_t)rd32(m, cat_va(i, SHOPL_CAT_NAME));
        g->price[i] = rd32(m, cat_va(i, SHOPL_CAT_PRICE));
        g->category[i] = rd32(m, cat_va(i, SHOPL_CAT_CATEGORY));
        g->value[i] = rd32(m, cat_va(i, SHOPL_CAT_VALUE));
    }
    for (i = 0; i < SHOP_GUNS; i++) {
        g->gun_id[i] = rd32(m, gun_va(i, 0));
        g->cap[i] = rd32(m, gun_va(i, SHOPL_GUN_CAP));
        g->kind[i] = rd32(m, gun_va(i, SHOPL_GUN_KIND));
        g->buy[i] = rd32(m, gun_va(i, SHOPL_GUN_BUY));
    }
    for (i = 0; i < SHOP_SHOTS; i++)
        g->power[i] = rd32(m, shot_va(i));
    memset(g->list_price, 0, sizeof g->list_price);
    for (l = 0; l < SHOP_LISTS; l++)
        for (i = 0; i < shopl_list_n[l]; i++)
            g->list_price[l][i] = rd32(m, shopl_list_va_of(l, i, SHOPL_LIST_PRICE));
}

void shopl_over_clear(struct shopl_over *o)
{
    memset(o, 0xFF, sizeof *o);
}

static int64_t scale(int32_t base, int pct)
{
    return ((int64_t)base * pct + 50) / 100;
}

/* At 100 % every value is the base itself: a price the game did not round
 * to 10 stays as it is. */
int32_t shopl_price(int32_t base, int pct)
{
    int64_t v;

    if (pct == 100 || base <= 0)
        return base;
    v = ((int64_t)base * pct + 500) / 1000 * 10;
    return (int32_t)(v < 10 ? 10 : v > 999999 ? 999999 : v);
}

int32_t shopl_ammo(int32_t base, int pct)
{
    int64_t v;

    if (pct == 100)
        return base;
    v = scale(base, pct);
    return (int32_t)(v < 1 ? 1 : v > 99 ? 99 : v);
}

int32_t shopl_power(int32_t base, int pct)
{
    int64_t v;

    if (pct == 100)
        return base;
    v = scale(base, pct);
    return (int32_t)(v < 0 ? 0 : v > 999 ? 999 : v);
}

static int32_t pick(int32_t over, int32_t game)
{
    return over >= 0 ? over : game;
}

int shopl_apply(const struct shopl_mem *m, const struct shopl_game *g,
                const struct shopl_over *o, const struct shopl_pct *p)
{
    int i, l, n = 0;

    for (i = 0; i < SHOP_ITEMS; i++) {
        n += wr32(m, cat_va(i, SHOPL_CAT_PRICE),
                  shopl_price(pick(o->price[i], g->price[i]), p->price));
        n += wr32(m, cat_va(i, SHOPL_CAT_VALUE), pick(o->value[i], g->value[i]));
    }
    for (i = 0; i < SHOP_GUNS; i++) {
        int32_t cap = shopl_ammo(pick(o->cap[i], g->cap[i]), p->ammo);
        int32_t buy = shopl_ammo(pick(o->buy[i], g->buy[i]), p->ammo);

        /* A capacity override below the game's ammo per purchase would
         * otherwise hand out more than the gun holds. */
        if (buy > cap)
            buy = cap;
        n += wr32(m, gun_va(i, SHOPL_GUN_CAP), cap);
        n += wr32(m, gun_va(i, SHOPL_GUN_BUY), buy);
    }
    for (i = 0; i < SHOP_SHOTS; i++)
        n += wr32(m, shot_va(i), shopl_power(pick(o->power[i], g->power[i]), p->power));
    for (l = 0; l < SHOP_LISTS; l++)
        for (i = 0; i < shopl_list_n[l]; i++)
            n += wr32(m, shopl_list_va_of(l, i, SHOPL_LIST_PRICE),
                      shopl_price(pick(o->list_price[l][i], g->list_price[l][i]), p->price));
    return n;
}

int shopl_restore(const struct shopl_mem *m, const struct shopl_game *g)
{
    struct shopl_over o;
    struct shopl_pct p = { 100, 100, 100 };

    shopl_over_clear(&o);
    return shopl_apply(m, g, &o, &p);
}

int shopl_gun_index(const struct shopl_game *g, int id)
{
    int i;

    for (i = 0; i < SHOP_GUNS; i++)
        if (g->gun_id[i] == id)
            return i;
    return -1;
}

/* The fire function's switch (tables 0x1A1C18 / 0x1A1C5C). */
int shopl_gun_shot(int id)
{
    switch (id) {
    case 16: return 0x8;
    case 19: return 0x4;
    case 21: case 26: case 27: return 0x6;
    case 22: return 0xA;
    case 23: return 0xB;
    case 24: return 0xC;
    case 25: return 0xD;
    case 28: return 0x7;
    case 29: return 0xE;
    case 32: return 0x0;
    case 36: return 0x14;
    case 37: return 0x18;
    case 38: return 0x19;
    case 41: return 0x1C;
    default: return id >= SHOPL_GUN_FIRST && id <= SHOPL_GUN_LAST ? 0x5 : -1;
    }
}

/* The gate's switch at 0x19FFB7 (tables 0x1A0228 / 0x1A0238). */
int shopl_gun_interval(int id, float *start, float *threshold)
{
    if (id < SHOPL_GUN_FIRST || id > SHOPL_GUN_LAST || id == 37 || id == 38)
        return 0;
    *start = id == 19 ? 18.0f : 0.0f;
    switch (id) {
    case 21: case 25: case 26: case 27: case 29:
        *threshold = 3.0f;
        break;
    case 19:
        *threshold = 29.0f;
        break;
    case 16: case 20: case 22: case 23: case 24: case 28: case 32: case 35: case 36:
    case 41:
        *threshold = 13.0f;
        break;
    default:
        *threshold = 10.0f;
        break;
    }
    return 1;
}

/* Only forward, toward the threshold: the gate fires when the timer before
 * the frame's step is below the start and the timer after it is not
 * (0x1A0039), so a timer moved back under the start would fire again. */
float shopl_fire_timer(int id, float timer, int pct)
{
    float start, thr, left;

    if (pct >= 100 || pct < 1 || !shopl_gun_interval(id, &start, &thr) || timer >= thr)
        return timer;
    left = (thr - timer) * (float)pct / 100.0f;
    return thr - left;
}

static int amount_category(int32_t cat)
{
    return cat == 0 || cat == 1 || cat == 4;
}

enum shop_status shopl_item_check(const struct shopl_game *g, int idx, int32_t price,
                                  int32_t value)
{
    int i;

    if (idx < 0 || idx >= SHOP_ITEMS)
        return SHOP_GONE;
    if (price < -1 || price > 999999 || value < -1)
        return SHOP_RANGE;
    if (value < 0)
        return SHOP_OK;
    if (amount_category(g->category[idx]))
        return value >= 1 && value <= 100 ? SHOP_OK : SHOP_RANGE;
    for (i = 0; i < SHOP_ITEMS; i++)
        if (g->category[i] == g->category[idx] && g->value[i] == value)
            return SHOP_OK;
    return SHOP_RANGE;
}

int shopl_sells_weapon(const struct shopl_game *g, int id)
{
    int i;

    for (i = 0; i < SHOP_ITEMS; i++)
        if (g->category[i] == SHOPL_CAT_WEAPON && g->value[i] == id)
            return 1;
    return 0;
}

static uint32_t slot_va(uint32_t i)
{
    return SHOPL_POOL_VA + i * SHOPL_POOL_SIZE;
}

void shopl_pool_used(const struct shopl_mem *m, uint8_t used[SHOPL_POOL_N])
{
    uint32_t i;

    for (i = 0; i < SHOPL_POOL_N; i++)
        used[i] = (uint8_t)rd8(m, slot_va(i));
}

int shopl_scale_shots(const struct shopl_mem *m, const uint8_t before[SHOPL_POOL_N],
                      int speed_pct, int life_pct, uint32_t *out, int max)
{
    uint32_t i;
    int n = 0, k;

    for (i = 0; i < SHOPL_POOL_N; i++) {
        uint32_t s = slot_va(i);
        int type;
        uint8_t *h;

        if (before[i] || !rd8(m, s))
            continue;
        type = rd8(m, s + SHOPL_SLOT_TYPE);
        if (type != SHOPL_SHOT_ITEM && type != SHOPL_SHOT_ITEM_B)
            continue;
        if (speed_pct != 100)
            for (k = 0; k < 3; k++) {
                uint32_t va = s + SHOPL_SLOT_VEL + 4u * (uint32_t)k;

                wrf(m, va, rdf(m, va) * (float)speed_pct / 100.0f);
            }
        h = host(m, s + SHOPL_SLOT_LIFE, 2);
        if (life_pct != 100 && h) {
            int16_t life;
            int64_t v;

            memcpy(&life, h, 2);
            v = scale(life, life_pct);
            life = (int16_t)(v < 1 ? 1 : v > 0x7FFF ? 0x7FFF : v);
            memcpy(h, &life, 2);
        }
        if (n < max && out)
            out[n] = s;
        n++;
    }
    return n;
}

static uint32_t char_va(const struct shopl_mem *m, int player, int character)
{
    if (player < 0 || player >= SHOPL_PLAYERS || character < 0 || character >= SHOPL_CHARS_MAX)
        return 0;
    if (character >= (int8_t)rd8(m, SHOPL_CHARS_VA + (uint32_t)player))
        return 0;
    return SHOPL_STATUS_VA + (uint32_t)player * SHOPL_STATUS_SIZE + SHOPL_CHAR +
           (uint32_t)character * SHOPL_CHAR_SIZE;
}

enum shop_status shopl_owned_get(const struct shopl_mem *m, int player, int character,
                                 int *weapon, int *ammo)
{
    uint32_t c = char_va(m, player, character);

    if (!c || !host(m, c, SHOPL_CHAR_SIZE))
        return SHOP_GONE;
    *weapon = rd8(m, c + SHOPL_CHAR_WEAPON);
    *ammo = rd8(m, c + SHOPL_CHAR_AMMO);
    return SHOP_OK;
}

enum shop_status shopl_owned_set(const struct shopl_mem *m, const struct shopl_game *g,
                                 int player, int character, int weapon, int ammo)
{
    uint32_t c = char_va(m, player, character);
    uint8_t *h;
    int gi;

    if (!c || !(h = host(m, c, SHOPL_CHAR_SIZE)))
        return SHOP_GONE;
    if (weapon < 0 || ammo < 0 || (weapon != 0 && !shopl_sells_weapon(g, weapon)))
        return SHOP_RANGE;
    /* A vacuum holds no ammo (the buy writes 0). A gun: the table's
     * capacity now (overrides and percents included), which is what the
     * stage copies into the player; one the table does not list (17, 18)
     * gets the code's default, so only the byte's game range holds. */
    gi = weapon >= SHOPL_GUN_FIRST ? shopl_gun_index(g, weapon) : -1;
    if (weapon < SHOPL_GUN_FIRST ? ammo != 0
                                 : ammo > (gi < 0 ? 99 : rd32(m, gun_va(gi, SHOPL_GUN_CAP))))
        return SHOP_RANGE;
    h[SHOPL_CHAR_WEAPON] = (uint8_t)weapon;
    h[SHOPL_CHAR_AMMO] = (uint8_t)ammo;
    return SHOP_OK;
}

int shopl_clamp_owned(const struct shopl_mem *m, const struct shopl_game *g)
{
    int p, c, gi, cap, n = 0;
    uint32_t va;
    uint8_t *h;

    for (p = 0; p < SHOPL_PLAYERS; p++)
        for (c = 0; c < SHOPL_CHARS_MAX; c++) {
            va = char_va(m, p, c);
            if (!va || !(h = host(m, va, SHOPL_CHAR_SIZE)))
                continue;
            gi = h[SHOPL_CHAR_WEAPON] >= SHOPL_GUN_FIRST
                     ? shopl_gun_index(g, h[SHOPL_CHAR_WEAPON])
                     : -1;
            if (gi < 0)
                continue;
            cap = rd32(m, gun_va(gi, SHOPL_GUN_CAP));
            if (cap >= 0 && h[SHOPL_CHAR_AMMO] > cap) {
                h[SHOPL_CHAR_AMMO] = (uint8_t)cap;
                n++;
            }
        }
    return n;
}
