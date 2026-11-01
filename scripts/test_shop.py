#!/usr/bin/env python3
"""Tests for the shop API and the shop mod (mods."shop.*", openspec change
shop-api).

Compiles a driver against src/shop_api_logic.c over a fake guest memory
that holds synthetic catalogue, gun and shot tables and story price lists
(made-up values with the shapes and the few words the retail check reads),
and checks the rules: the retail check, price
rounding and the ammo and power clamps, apply and restore (only changed words written, buy never above capacity,
restore gives back every byte), the gun -> shot type map, the fire timer
moved only forward, the override checks per category, the shots a fire
made told from the pool diff and scaled, and the owned weapon bytes with
their player, character, weapon and ammo bounds. Then checks the keys:
each setting has a CONFIG env row and a docs/env.md row, the descriptor
names them, the golden check knows the switch's stock value, the hook
slot is listed, the sources are built and the mod is registered.

  python3 scripts/test_shop.py
  uv run pytest scripts/test_shop.py

The C tests skip when no C compiler is on PATH.
"""

import json
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

STATUS = ["OK", "OFF", "RANGE", "GONE", "BUSY"]

# setting name -> (env row, kind in the descriptor)
SETTINGS = {
    "enable": ("RECOMP_SHOP", "XBOX_SET_ENUM"),
    "price_pct": ("RECOMP_SHOP_PRICE_PCT", "XBOX_SET_INT"),
    "ammo_pct": ("RECOMP_SHOP_AMMO_PCT", "XBOX_SET_INT"),
    "power_pct": ("RECOMP_SHOP_POWER_PCT", "XBOX_SET_INT"),
    "speed_pct": ("RECOMP_SHOP_SPEED_PCT", "XBOX_SET_INT"),
    "interval_pct": ("RECOMP_SHOP_INTERVAL_PCT", "XBOX_SET_INT"),
}

# Synthetic tables, made up for the tests (no game data here). They keep
# the few words the retail check reads (catalogue record 0's price 50 and
# category 0, the last record's category 4, gun 16 first, shot type 5's
# power 10, story list 0 record 1's 400 and list 3 record 0's 10) and the
# shapes the rules need: gun 16 at index 0, gun 41 last, gun 17 sold but
# not in the gun table, a vacuum (10) among the weapon records, 15 and 39
# sold by none.
GUN_IDS = [16, *range(19, 37), 41]
GUNS = [
    (gid, cap, i % 4, cap // 2)
    for i, gid in enumerate(GUN_IDS)
    for cap in [8 if i == 0 else 20 if i == 1 else 10 * (i % 5 + 1)]
] + [(-1, -1, -1, -1)]
CATS = [0, 1] + [2] * 3 + [3] + [5] * 5 + [6] * 10 + [7] * 29 + [4] * 3
VALUES = (
    [10, 10, 1, 2, 3, 1, 2, 4, 6, 8, 10]
    + list(range(1, 11))
    + [*range(6, 15), 16, 17, *range(19, 35), 36, 41]
    + [10, 20, 30]
)
PRICES = [50, 200] + [100 + 50 * (i % 9) for i in range(2, 53)]
POWERS = [3 * i for i in range(30)]
POWERS[4], POWERS[5], POWERS[8] = 0, 10, 30
LIST_N = [43, 22, 23, 38]
LISTS = [[50 * ((3 * i + n) % 20 + 1) for i in range(n)] for n in LIST_N]
LISTS[0][:3] = [0, 400, 600]
LISTS[3][0] = 10
assert len(GUNS) == 21 and len(CATS) == len(VALUES) == len(PRICES) == 53


def _price(base, pct):
    """shopl_price, for the counts the tests expect."""
    if pct == 100 or base <= 0:
        return base
    return min(max((base * pct + 500) // 1000 * 10, 10), 999999)


def _c_array(name, rows):
    flat = [x for r in rows for x in (r if isinstance(r, tuple) else (r,))]
    return f"static const int32_t {name}[] = {{{', '.join(map(str, flat))}}};\n"


# A fake guest: 16 MiB holding the retail tables, player 0 with two
# characters and player 1 with none. Commands are read one per line and
# share the memory until `reset`; each prints one line.
DRIVER = (
    r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "shop_api_logic.h"

#define MEM 0x01000000u
"""
    + _c_array("k_guns", GUNS)
    + _c_array("k_prices", PRICES)
    + _c_array("k_cats", CATS)
    + _c_array("k_values", VALUES)
    + _c_array("k_powers", POWERS)
    + "".join(_c_array(f"k_list{i}", lst) for i, lst in enumerate(LISTS))
    + "static const int32_t *const k_lists[] = { k_list0, k_list1, k_list2, k_list3 };\n"
    + r"""
static uint8_t *g, *snap;
static struct shopl_mem m;
static struct shopl_game game;
static struct shopl_over over;
static struct shopl_pct pct = { 100, 100, 100 };

static void w32(uint32_t va, int32_t v) { memcpy(g + va, &v, 4); }
static int32_t r32(uint32_t va) { int32_t v; memcpy(&v, g + va, 4); return v; }
static void wf(uint32_t va, float v) { memcpy(g + va, &v, 4); }
static float rf(uint32_t va) { float v; memcpy(&v, g + va, 4); return v; }
static int16_t r16(uint32_t va) { int16_t v; memcpy(&v, g + va, 2); return v; }
static void w16(uint32_t va, int16_t v) { memcpy(g + va, &v, 2); }

static uint32_t cat(int i, uint32_t off) { return SHOPL_CAT_VA + (uint32_t)i * SHOPL_CAT_SIZE + off; }
static uint32_t gun(int i, uint32_t off) { return SHOPL_GUN_VA + (uint32_t)i * SHOPL_GUN_SIZE + off; }
static uint32_t shot(int i) { return SHOPL_SHOT_VA + (uint32_t)i * SHOPL_SHOT_SIZE + SHOPL_SHOT_POWER; }
static uint32_t lst(int l, int i, uint32_t off) { return shopl_list_va_of(l, i, off); }
static uint32_t slot(int i) { return SHOPL_POOL_VA + (uint32_t)i * SHOPL_POOL_SIZE; }
static uint32_t chr(int p, int c, uint32_t off)
{
    return SHOPL_STATUS_VA + (uint32_t)p * SHOPL_STATUS_SIZE + SHOPL_CHAR +
           (uint32_t)c * SHOPL_CHAR_SIZE + off;
}

static void reset(void)
{
    int i, a;

    memset(g, 0, MEM);
    for (i = 0; i < SHOP_ITEMS; i++) {
        w32(cat(i, SHOPL_CAT_NAME), i < 50 ? 0x00480000 + i * 0x20 : 0);
        w32(cat(i, SHOPL_CAT_PRICE), k_prices[i]);
        w32(cat(i, SHOPL_CAT_CATEGORY), k_cats[i]);
        w32(cat(i, SHOPL_CAT_VALUE), k_values[i]);
    }
    for (i = 0; i <= SHOP_GUNS; i++) {
        w32(gun(i, 0), k_guns[4 * i]);
        w32(gun(i, SHOPL_GUN_CAP), k_guns[4 * i + 1]);
        w32(gun(i, SHOPL_GUN_KIND), k_guns[4 * i + 2]);
        w32(gun(i, SHOPL_GUN_BUY), k_guns[4 * i + 3]);
    }
    for (i = 0; i < SHOP_SHOTS; i++)
        w32(shot(i), k_powers[i]);
    for (a = 0; a < SHOP_LISTS; a++)
        for (i = 0; i < shopl_list_n[a]; i++) {
            w32(lst(a, i, SHOPL_LIST_PRICE), k_lists[a][i]);
            w32(lst(a, i, SHOPL_LIST_INDEX), i);
        }
    g[SHOPL_CHARS_VA] = 2;
    g[SHOPL_CHARS_VA + 1] = 0;
    m.base = g;
    m.size = MEM;
    shopl_read_game(&m, &game);
    shopl_over_clear(&over);
    pct.price = pct.ammo = pct.power = 100;
    memcpy(snap, g, MEM);
}

int main(void)
{
    char line[256], cmd[32];
    int a, b, c, d;
    float f;

    g = calloc(1, MEM);
    snap = calloc(1, MEM);
    if (!g || !snap)
        return 1;
    reset();
    while (fgets(line, sizeof line, stdin)) {
        if (sscanf(line, "%31s", cmd) != 1)
            continue;
        if (!strcmp(cmd, "reset")) {
            reset();
            printf("ok\n");
        } else if (!strcmp(cmd, "check")) {
            /* retail, a short view, another image's first price, a story
             * list whose last record is not its own index */
            struct shopl_mem s = { g, SHOPL_SHOT_VA + 0x10 };
            int retail = shopl_check(&m), shrt = shopl_check(&s), other, list;

            w32(cat(0, SHOPL_CAT_PRICE), 60);
            other = shopl_check(&m);
            w32(cat(0, SHOPL_CAT_PRICE), 50);
            w32(lst(2, 22, SHOPL_LIST_INDEX), 0);
            list = shopl_check(&m);
            w32(lst(2, 22, SHOPL_LIST_INDEX), 22);
            printf("%d %d %d %d\n", retail, shrt, other, list);
        } else if (sscanf(line, "price %d %d", &a, &b) == 2) {
            printf("%d\n", shopl_price(a, b));
        } else if (sscanf(line, "ammo %d %d", &a, &b) == 2) {
            printf("%d\n", shopl_ammo(a, b));
        } else if (sscanf(line, "power %d %d", &a, &b) == 2) {
            printf("%d\n", shopl_power(a, b));
        } else if (sscanf(line, "pct %d %d %d", &a, &b, &c) == 3) {
            pct.price = a;
            pct.ammo = b;
            pct.power = c;
            printf("ok\n");
        } else if (sscanf(line, "lover %d %d %d", &a, &b, &c) == 3) {
            over.list_price[a][b] = c;
            printf("ok\n");
        } else if (sscanf(line, "list %d %d", &a, &b) == 2) {
            uint32_t va = lst(a, b, SHOPL_LIST_PRICE);

            printf("%d\n", va ? r32(va) : -1);
        } else if (sscanf(line, "over %31s %d %d", cmd, &a, &b) == 3) {
            int32_t *t = !strcmp(cmd, "price") ? over.price : !strcmp(cmd, "value") ? over.value
                       : !strcmp(cmd, "cap") ? over.cap : !strcmp(cmd, "buy") ? over.buy
                       : over.power;
            t[a] = b;
            printf("ok\n");
        } else if (!strcmp(cmd, "apply")) {
            printf("%d\n", shopl_apply(&m, &game, &over, &pct));
        } else if (!strcmp(cmd, "restore")) {
            int n = shopl_restore(&m, &game);

            printf("%d %d\n", n, memcmp(g, snap, MEM) == 0);
        } else if (sscanf(line, "item %d", &a) == 1) {
            printf("%d %d\n", r32(cat(a, SHOPL_CAT_PRICE)), r32(cat(a, SHOPL_CAT_VALUE)));
        } else if (sscanf(line, "gun %d", &a) == 1) {
            printf("%d %d\n", r32(gun(a, SHOPL_GUN_CAP)), r32(gun(a, SHOPL_GUN_BUY)));
        } else if (sscanf(line, "shotpow %d", &a) == 1) {
            printf("%d\n", r32(shot(a)));
        } else if (sscanf(line, "shot %d", &a) == 1) {
            printf("%d\n", shopl_gun_shot(a));
        } else if (sscanf(line, "gunidx %d", &a) == 1) {
            printf("%d\n", shopl_gun_index(&game, a));
        } else if (sscanf(line, "timer %d %f %d", &a, &f, &b) == 3) {
            printf("%g\n", shopl_fire_timer(a, f, b));
        } else if (sscanf(line, "icheck %d %d %d", &a, &b, &c) == 3) {
            printf("%d\n", shopl_item_check(&game, a, b, c));
        } else if (sscanf(line, "sells %d", &a) == 1) {
            printf("%d\n", shopl_sells_weapon(&game, a));
        } else if (sscanf(line, "shots %d %d", &a, &b) == 2) {
            /* slot 3 used before and after; 5 a new shot, 6 a new gun-32
             * shot, 7 a new item of another type; 9 used before only. */
            uint8_t before[SHOPL_POOL_N];
            uint32_t out[8];
            int n, i;

            g[slot(3)] = 1;
            g[slot(3) + SHOPL_SLOT_TYPE] = SHOPL_SHOT_ITEM;
            wf(slot(3) + SHOPL_SLOT_VEL, 7.0f);
            g[slot(9)] = 1;
            shopl_pool_used(&m, before);
            g[slot(9)] = 0;
            g[slot(5)] = 1;
            g[slot(5) + SHOPL_SLOT_TYPE] = SHOPL_SHOT_ITEM;
            wf(slot(5) + SHOPL_SLOT_VEL, 1.0f);
            wf(slot(5) + SHOPL_SLOT_VEL + 4, 2.0f);
            wf(slot(5) + SHOPL_SLOT_VEL + 8, -4.0f);
            w16(slot(5) + SHOPL_SLOT_LIFE, 60);
            g[slot(6)] = 1;
            g[slot(6) + SHOPL_SLOT_TYPE] = SHOPL_SHOT_ITEM_B;
            w16(slot(6) + SHOPL_SLOT_LIFE, 0x7000);
            g[slot(7)] = 1;
            g[slot(7) + SHOPL_SLOT_TYPE] = 0x10;
            w16(slot(7) + SHOPL_SLOT_LIFE, 60);
            n = shopl_scale_shots(&m, before, a, b, out, 8);
            printf("%d", n);
            for (i = 0; i < n && i < 8; i++)
                printf(" %d", (int)((out[i] - SHOPL_POOL_VA) / SHOPL_POOL_SIZE));
            printf(" | %g %g %g %d | %d | %g %d\n", rf(slot(5) + SHOPL_SLOT_VEL),
                   rf(slot(5) + SHOPL_SLOT_VEL + 4), rf(slot(5) + SHOPL_SLOT_VEL + 8),
                   r16(slot(5) + SHOPL_SLOT_LIFE), r16(slot(6) + SHOPL_SLOT_LIFE),
                   rf(slot(3) + SHOPL_SLOT_VEL), r16(slot(7) + SHOPL_SLOT_LIFE));
        } else if (sscanf(line, "oset %d %d %d %d", &a, &b, &c, &d) == 4) {
            int st = shopl_owned_set(&m, &game, a, b, c, d);
            int w = -1, am = -1, st2 = shopl_owned_get(&m, a, b, &w, &am);

            printf("%d %d %d %d\n", st, st2, w, am);
        } else if (!strcmp(cmd, "clamp")) {
            /* player 0: character 0 gun 16 with 20 (above its 8), character
             * 1 vacuum 10 with 5; then gun 17 (not in the table) with 50 */
            int n1, n2;

            g[chr(0, 0, SHOPL_CHAR_WEAPON)] = 16;
            g[chr(0, 0, SHOPL_CHAR_AMMO)] = 20;
            g[chr(0, 1, SHOPL_CHAR_WEAPON)] = 10;
            g[chr(0, 1, SHOPL_CHAR_AMMO)] = 5;
            n1 = shopl_clamp_owned(&m, &game);
            a = g[chr(0, 0, SHOPL_CHAR_AMMO)];
            b = g[chr(0, 1, SHOPL_CHAR_AMMO)];
            g[chr(0, 0, SHOPL_CHAR_WEAPON)] = 17;
            g[chr(0, 0, SHOPL_CHAR_AMMO)] = 50;
            n2 = shopl_clamp_owned(&m, &game);
            printf("%d %d %d %d %d\n", n1, a, b, n2, g[chr(0, 0, SHOPL_CHAR_AMMO)]);
        } else if (sscanf(line, "oget %d %d", &a, &b) == 2) {
            int w = -1, am = -1, st;

            g[chr(0, 1, SHOPL_CHAR_WEAPON)] = 24;
            g[chr(0, 1, SHOPL_CHAR_AMMO)] = 17;
            st = shopl_owned_get(&m, a, b, &w, &am);
            printf("%d %d %d\n", st, w, am);
        } else {
            printf("?\n");
        }
        fflush(stdout);
    }
    free(g);
    free(snap);
    return 0;
}
"""
)


# shop_api.c itself over a fake mod API (needs the toolkit's headers): the
# DRIVER's memory and helpers, a hook and on_frame that the commands call.
API_MAIN = r"""
#include <stdarg.h>
#include "mod.h"

size_t g_xbox_total_ram = MEM;

static xbox_mod_hook_fn s_pre, s_post;
static xbox_mod_frame_fn s_frame;
static uint32_t s_hook_va;
static int s_shots;
static struct xbox_mod k_owner = { "shop" };
static struct xbox_mod_api k_api;

static void fake_log(const struct xbox_mod *o, const char *fmt, ...)
{
    va_list ap;

    (void)o;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
}

static int fake_hook(uint32_t va, xbox_mod_hook_fn pre, xbox_mod_hook_fn post, uint32_t f, void *u)
{
    (void)f, (void)u;
    s_hook_va = va;
    s_pre = pre;
    s_post = post;
    return 1;
}

static int fake_on_frame(xbox_mod_frame_fn fn, void *u)
{
    (void)u;
    s_frame = fn;
    return 1;
}

static void on_shot(int gun_id, uint32_t va, void *user)
{
    (void)gun_id, (void)va, (void)user;
    s_shots++;
}

/* Player 0 fires gun 16 at timer 0: the call takes slot 5 for one shot at
 * speed 8 along x. The guest stack holds the player at [esp + 4]. */
static void fire(void)
{
    struct xbox_mod_call c;
    uint32_t esp = 0x00F00000u, plr = SHOPL_PLAYER0_VA;

    memset(&c, 0, sizeof c);
    c.esp = esp;
    w32(esp + 4, (int32_t)plr);
    g[plr + SHOPL_PLR_WEAPON] = 16;
    wf(plr + SHOPL_PLR_TIMER, 0.0f);
    memset(g + slot(5), 0, SHOPL_POOL_SIZE);
    s_pre(&c, NULL);
    g[slot(5)] = 1;
    g[slot(5) + SHOPL_SLOT_TYPE] = SHOPL_SHOT_ITEM;
    wf(slot(5) + SHOPL_SLOT_VEL, 8.0f);
    w16(slot(5) + SHOPL_SLOT_LIFE, 60);
    s_post(&c, NULL);
}

int main(void)
{
    char cmd[16];
    struct shop_item it;
    struct shop_gun gn;
    int32_t lp = -1, lg = -1;

    g = calloc(1, MEM);
    snap = calloc(1, MEM);
    if (!g || !snap)
        return 1;
    reset();
    k_api.version = XBOX_MOD_API_VERSION;
    k_api.size = sizeof k_api;
    k_api.mem = (uintptr_t)g;
    k_api.log = fake_log;
    k_api.on_frame = fake_on_frame;
    k_api.hook = fake_hook;
    if (!shop_api_attach(&k_api, &k_owner))
        return 1;
    shop_api_on_shot(on_shot, NULL);
    while (scanf("%15s", cmd) == 1) {
        if (!strcmp(cmd, "slot")) {
            printf("0x%08X %d\n", (unsigned)s_hook_va, shop_api_ready());
        } else if (!strcmp(cmd, "life")) {
            /* Off: SHOP_OFF. On before a frame: still SHOP_OFF (the game's
             * values are not read yet). After a frame: OK, written at the
             * next frame; off puts every byte back and drops the
             * override. */
            int a, b, c, d, e, f2;

            a = shop_item_set(0, 120, -1);
            shop_api_enable(1);
            b = shop_item_set(0, 120, -1);
            s_frame(NULL);
            c = shop_item_set(0, 120, -1);
            d = r32(cat(0, SHOPL_CAT_PRICE));
            s_frame(NULL);
            e = r32(cat(0, SHOPL_CAT_PRICE));
            shop_api_enable(0);
            s_frame(NULL);
            f2 = memcmp(g, snap, MEM) == 0;
            shop_api_enable(1);
            s_frame(NULL);
            printf("%d %d %d %d %d %d %d %d\n", a, b, c, d, e, f2, r32(cat(0, SHOPL_CAT_PRICE)),
                   shop_api_ready());
            shop_api_enable(0);
            s_frame(NULL);
        } else if (!strcmp(cmd, "pct")) {
            /* The mod's percents on top of an override; the reads give both
             * the value now and the game's. */
            shop_api_enable(1);
            s_frame(NULL);
            shop_api_pct(50, 200, 200, 100, 100);
            shop_item_set(1, 300, -1);
            s_frame(NULL);
            shop_item_get(1, &it);
            shop_gun_get(16, &gn);
            shop_list_price_get(0, 1, &lp, &lg);
            printf("%d %d %d %d %d %d %d %d %d %d\n", it.price, it.game_price, it.category, gn.shot,
                   gn.capacity, gn.buy, gn.power, gn.game_power, lp, lg);
            shop_api_pct(100, 100, 100, 100, 100);
            shop_api_enable(0);
            s_frame(NULL);
        } else if (!strcmp(cmd, "ranges")) {
            shop_api_enable(1);
            s_frame(NULL);
            printf("%d %d %d %d %d %d %d %d %d %d\n", shop_item_set(53, 1, -1),
                   shop_item_set(21, -1, 15), shop_gun_set(17, 10, 5), shop_gun_set(16, 0, -1),
                   shop_gun_set(16, 4, 5), shop_gun_set(16, -1, 9), shop_shot_power_set(30, 1),
                   shop_shot_power_set(5, 1000), shop_gun_scale(16, 5, -1, -1),
                   shop_gun_scale(15, 100, 100, 100));
            printf("%d %d %d %d %d %d\n", shop_list_price_set(4, 0, 1),
                   shop_list_price_set(1, 22, 1), shop_list_price_set(0, 1, 1000000),
                   shop_list_price_set(0, 1, 0), shop_list_count(3), shop_list_count(4));
            /* below -1, and an interval above 100 % */
            printf("%d %d %d %d %d %d %d\n", shop_item_set(1, -2, -1), shop_item_set(1, -1, -5),
                   shop_gun_set(16, -2, -1), shop_shot_power_set(5, -3),
                   shop_list_price_set(0, 1, -2), shop_gun_scale(16, -2, -1, -1),
                   shop_gun_scale(16, -1, -1, 150));
            shop_api_enable(0);
            s_frame(NULL);
        } else if (!strcmp(cmd, "fire")) {
            /* Gun 16 at speed 200 %, life 50 %, interval 50 %: the shot
             * twice as fast for half as long, the timer halfway to 13.
             * Off: the hook leaves it alone. */
            shop_api_enable(1);
            s_frame(NULL);
            shop_gun_scale(16, 200, 50, 50);
            fire();
            printf("%g %d %g %d |", rf(slot(5) + SHOPL_SLOT_VEL), r16(slot(5) + SHOPL_SLOT_LIFE),
                   rf(SHOPL_PLAYER0_VA + SHOPL_PLR_TIMER), s_shots);
            shop_api_enable(0);
            s_frame(NULL);
            fire();
            printf(" %g %d %g %d\n", rf(slot(5) + SHOPL_SLOT_VEL), r16(slot(5) + SHOPL_SLOT_LIFE),
                   rf(SHOPL_PLAYER0_VA + SHOPL_PLR_TIMER), s_shots);
        } else if (!strcmp(cmd, "clamp")) {
            /* A buy at ammo 500 %: gun 16 holds 40. Lowering the percent
             * brings it down to the table's 8; so does off. */
            int lowered, off;

            shop_api_enable(1);
            s_frame(NULL);
            shop_api_pct(100, 500, 100, 100, 100);
            s_frame(NULL);
            g[chr(0, 0, SHOPL_CHAR_WEAPON)] = 16;
            g[chr(0, 0, SHOPL_CHAR_AMMO)] = 40;
            shop_api_pct(100, 100, 100, 100, 100);
            s_frame(NULL);
            lowered = g[chr(0, 0, SHOPL_CHAR_AMMO)];
            shop_api_pct(100, 500, 100, 100, 100);
            s_frame(NULL);
            g[chr(0, 0, SHOPL_CHAR_AMMO)] = 40;
            shop_api_enable(0);
            s_frame(NULL);
            off = g[chr(0, 0, SHOPL_CHAR_AMMO)];
            printf("%d %d %d\n", lowered, off, r32(gun(0, SHOPL_GUN_CAP)));
            shop_api_pct(100, 100, 100, 100, 100);
        } else if (!strcmp(cmd, "busy")) {
            /* A read off the guest thread: on_frame ran on this thread, so
             * a second thread is needed; reads before any frame are BUSY
             * only through the marker, so this checks the guest path. */
            int w, a;

            shop_api_enable(1);
            s_frame(NULL);
            printf("%d %d\n", shop_item_get(0, &it), shop_owned_get(0, 0, &w, &a));
            shop_api_enable(0);
            s_frame(NULL);
        }
        fflush(stdout);
    }
    free(g);
    free(snap);
    return 0;
}
"""


def _toolkit_includes():
    """The toolkit's header directories ($XBOXRECOMP_DIR, external/xboxrecomp
    or ../xboxrecomp, as CMakeLists.txt finds it), or None."""
    for d in (
        os.environ.get("XBOXRECOMP_DIR") or os.path.join(ROOT, "missing"),
        os.path.join(ROOT, "external", "xboxrecomp"),
        os.path.join(ROOT, "..", "xboxrecomp"),
    ):
        if os.path.exists(os.path.join(d, "src", "enhance", "mod.h")):
            dirs = set()
            for sub in ("src", "include"):
                for dp, _, fs in os.walk(os.path.join(d, sub)):
                    if any(f.endswith(".h") for f in fs):
                        dirs.add(dp)
            return sorted(dirs) + [os.path.join(d, "src"), os.path.join(d, "include")]
    return None


@pytest.fixture(scope="module")
def api():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    inc = _toolkit_includes()
    if not cc or not inc:
        pytest.skip("no C compiler or no toolkit beside the project")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "api.c")
    exe = os.path.join(d, "api")
    with open(c, "w") as f:
        f.write(DRIVER[: DRIVER.index("int main(void)")] + API_MAIN)
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Werror", "-Wno-unused-function", "-Wno-comment"]
        + ["-DRECOMP_ENV_HAVE_ENHANCE_KEYS", "-I", SRC]
        + [x for i in inc for x in ("-I", i)]
        + [c, os.path.join(SRC, "shop_api.c"), os.path.join(SRC, "shop_api_logic.c"), "-o", exe],
        check=True,
    )

    def run(cmd):
        out = subprocess.run([exe], input=cmd + "\n", capture_output=True, text=True, check=True)
        return out.stdout.strip()

    yield run
    shutil.rmtree(d)


@pytest.fixture(scope="module")
def drv():
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("no C compiler")
    d = tempfile.mkdtemp()
    c = os.path.join(d, "drv.c")
    exe = os.path.join(d, "drv")
    with open(c, "w") as f:
        f.write(DRIVER)
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Werror", "-I", SRC, c]
        + [os.path.join(SRC, "shop_api_logic.c"), "-o", exe],
        check=True,
    )

    def run(*cmds):
        out = subprocess.run(
            [exe], input="\n".join(cmds) + "\n", capture_output=True, text=True, check=True
        )
        lines = out.stdout.strip().splitlines()
        return lines if len(cmds) > 1 else lines[0]

    yield run
    shutil.rmtree(d)


def test_check_knows_the_retail_tables(drv):
    # Retail passes; a view too short for the tables or another image's
    # first price writes nothing.
    assert drv("check") == "1 0 0 0"


def test_price_rounds_to_ten_and_clamps(drv):
    assert drv("price 50 100") == "50"  # 100 % is the base itself
    assert drv("price 55 100") == "55"
    assert drv("price 250 50") == "130"  # 125 -> 130
    assert drv("price 50 10") == "10"  # never below 10
    assert drv("price 0 50") == "0"  # a free item stays free
    assert drv("price 2000 500") == "10000"
    assert drv("price 999999 500") == "999999"


def test_ammo_and_power_clamp(drv):
    assert drv("ammo 4 50") == "2"
    assert drv("ammo 1 50") == "1"  # 0.5 rounds up, and never 0
    assert drv("ammo 50 500") == "99"
    assert drv("ammo 8 100") == "8"
    assert drv("power 30 150") == "45"
    assert drv("power 100 1000") == "999"
    assert drv("power 0 500") == "0"


def test_apply_writes_only_changes_and_restore_gives_back_every_byte(drv):
    out = drv(
        "apply",  # nothing set: nothing written
        "pct 50 100 100",
        "apply",
        "item 1",
        "item 0",
        "apply",  # again: nothing new
        "restore",
        "item 1",
    )
    assert out[0] == "0"
    # The catalogue's and the story lists' prices at 50 %: each word whose
    # rounded value differs (not a free one, nor a 10). Record 0's 50
    # becomes 30 (25 rounds up).
    changed = sum(_price(p, 50) != p for p in PRICES + [p for lst in LISTS for p in lst])
    assert out[2] == str(changed)
    assert out[3] == "100 10"
    assert out[4] == "30 10"
    assert out[5] == "0"
    assert out[6] == f"{changed} 1"
    assert out[7] == "200 10"


def test_story_lists_take_the_price_pct_and_overrides(drv):
    out = drv(
        "pct 50 100 100",
        "lover 0 2 1000",
        "apply",
        "list 0 1",  # the TS-2000: 400 -> 200
        "list 0 2",  # an override, then the percent: 500
        "list 0 0",  # free stays free
        "list 3 0",  # 10 -> 5 -> never below 10
        "list 1 22",  # past the list's end
        "restore",
        "list 0 2",
    )
    assert out[3:8] == ["200", "500", "0", "10", "-1"]
    assert out[8].endswith(" 1")
    assert out[9] == "600"


def test_overrides_and_buy_clamp(drv):
    out = drv(
        "over price 21 1234",
        "over value 21 24",  # weapon record: another gun the shop sells
        "over cap 0 3",  # gun 16: capacity 3, its buy of 4 must follow
        "over power 5 77",
        "apply",
        "item 21",
        "gun 0",
        "shotpow 5",
        "pct 100 200 200",
        "apply",
        "gun 0",
        "gun 1",
        "shotpow 5",
        "shotpow 4",
        "restore",
    )
    assert out[4] == "5"
    assert out[5] == "1234 24"
    assert out[6] == "3 3"
    assert out[7] == "77"
    assert out[10] == "6 6"  # 3 x 200 %, buy 4 x 200 % = 8 clamped to 6
    assert out[11] == "40 20"
    assert out[12] == "154"
    assert out[13] == "0"
    assert out[14].endswith(" 1")


def test_gun_shot_map(drv):
    shots = {16: 8, 19: 4, 20: 5, 21: 6, 26: 6, 27: 6, 32: 0, 37: 24, 38: 25, 41: 28}
    for gid, st in shots.items():
        assert drv(f"shot {gid}") == str(st), gid
    for gid in (0, 15, 42, -1):
        assert drv(f"shot {gid}") == "-1"
    assert drv("gunidx 41") == "19"
    assert drv("gunidx 17") == "-1"  # sold, but not in the gun table


def test_fire_timer_moves_only_forward(drv):
    # Gun 16: start 0, threshold 13; just fired, the timer at 0.
    assert drv("timer 16 0 50") == "6.5"
    assert drv("timer 16 0 100") == "0"
    assert drv("timer 16 0 200") == "0"  # never back
    assert drv("timer 16 13 50") == "13"  # already ready
    # Gun 19 starts at 18 and is busy to 29.
    assert drv("timer 19 18 50") == "23.5"
    # Gun 21: threshold 3.
    assert drv("timer 21 1 25") == "2.5"
    # 37 and 38 fire elsewhere; no gun: unchanged.
    assert drv("timer 37 0 50") == "0"
    assert drv("timer 5 0 50") == "0"


def test_item_check(drv):
    assert drv("icheck 0 100 50") == "0"  # hp: an amount
    assert drv("icheck 0 100 0") == "2"
    assert drv("icheck 0 100 101") == "2"
    assert drv("icheck 0 1000000 -1") == "2"
    assert drv("icheck 0 -1 -1") == "0"
    assert drv("icheck 21 -1 41") == "0"  # a weapon some record sells
    assert drv("icheck 21 -1 15") == "2"  # no record sells 15
    assert drv("icheck 21 -1 10") == "0"  # vacuum 10 is a weapon record
    assert drv("icheck 6 -1 6") == "0"  # category 5 holds 6
    assert drv("icheck 6 -1 7") == "2"
    assert drv("icheck 52 -1 77") == "0"  # category 4: an amount
    assert drv("icheck 53 -1 -1") == "3"
    assert drv("icheck -1 -1 -1") == "3"
    assert drv("sells 17") == "1"
    assert drv("sells 39") == "0"


def test_scale_shots_finds_new_shots_only(drv):
    out = drv("shots 200 50")
    count, vel, life6, rest = (s.strip() for s in out.split("|"))
    assert count == "2 5 6"
    assert vel == "2 4 -8 30"
    assert life6 == "14336"
    assert rest == "7 60"  # the old shot and the other item untouched
    out = drv("reset", "shots 100 1000")
    count, vel, life6, _ = (s.strip() for s in out[1].split("|"))
    assert vel == "1 2 -4 600"
    assert life6 == "32767"


def test_owned_get(drv):
    assert drv("oget 0 1") == "0 24 17"
    assert drv("oget 0 2").split()[0] == "3"  # player 0 has two characters
    assert drv("oget 1 0").split()[0] == "3"  # player 1 none
    assert drv("oget 4 0").split()[0] == "3"
    assert drv("oget -1 0").split()[0] == "3"


def test_owned_set(drv):
    assert drv("oset 0 0 16 8") == "0 0 16 8"
    assert drv("oset 0 0 16 9").split()[0] == "2"  # above gun 16's 8
    assert drv("oset 0 0 10 0") == "0 0 10 0"  # a vacuum
    assert drv("oset 0 0 10 1").split()[0] == "2"
    assert drv("oset 0 0 0 0") == "0 0 0 0"  # none
    assert drv("oset 0 0 39 1").split()[0] == "2"  # not sold
    assert drv("oset 0 0 17 99") == "0 0 17 99"  # sold, not in the table
    assert drv("oset 0 0 17 100").split()[0] == "2"
    assert drv("oset 0 1 16 -1").split()[0] == "2"
    assert drv("oset 0 2 16 1").split()[0] == "3"
    assert drv("oset 1 0 16 1").split()[0] == "3"
    # The capacity is the table's now, percents included.
    out = drv("pct 100 200 100", "apply", "oset 0 1 16 16")
    assert out[2] == "0 0 16 16"


def test_api_hooks_the_fire_function(api):
    assert api("slot") == "0x001A0260 0"


def test_api_lifecycle(api):
    # off, on before a frame, on: OFF OFF OK; the price written a frame
    # later; off restores every byte; on again: the override is gone.
    assert api("life") == "1 1 0 50 120 1 50 1"


def test_api_pct_on_top_of_overrides(api):
    # 300 at 50 %: 150; gun 16 cap 8 and buy 4 at 200 %; shot type 8's 30
    # at 200 %.
    # The TS-2000's 400 at 50 %: 200.
    assert api("pct") == "150 200 1 8 16 8 60 30 200 400"


def test_api_ranges(api):
    gone, rng = "3", "2"
    out, lists, neg = api("ranges").splitlines()
    assert out.split() == [gone, rng, gone, rng, rng, rng, gone, rng, rng, gone]
    assert lists.split() == [gone, gone, rng, "0", "38", "0"]
    assert neg.split() == [rng] * 7


def test_owned_ammo_clamps_to_capacity(drv):
    # Gun 16's 20 down to 8; the vacuum and a gun not in the table alone.
    assert drv("reset", "clamp")[1] == "1 8 5 0 50"


def test_api_clamps_owned_ammo_when_lowered_and_off(api):
    assert api("clamp") == "8 8 8"


def test_api_fire_hook(api):
    on, off = (s.split() for s in api("fire").split("|"))
    assert on == ["16", "30", "6.5", "1"]
    assert off == ["8", "60", "0", "1"]


def test_api_reads_on_the_guest_thread(api):
    # on_frame ran on this thread, so it is the guest's.
    assert api("busy") == "0 0"


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def test_env_rows():
    text = _read("src", "env", "recomp_env_game.h")
    for name, (env, _) in SETTINGS.items():
        m = re.search(r'X\(\w+,\s*CONFIG,\s*"' + env + r'",\s*NULL,\s*"([^"]*)"', text)
        assert m, f"{env}: no CONFIG row in recomp_env_game.h"
        assert f"mods.shop.{name}" in m.group(1), f"{env}: its row does not name the key"
    assert re.search(r'X\(SHOP_PROOF,\s*DEBUG,\s*"shop_proof"', text)


def test_env_doc_has_every_key():
    doc = _read("docs", "env.md")
    for name, (env, _) in SETTINGS.items():
        assert f"| `{env}` | `{env}`" in doc, f"{env}: no docs/env.md row"
        assert f'`mods."shop.{name}"`' in doc, f"shop.{name}: not in docs/env.md"
    row = re.search(r"\| \(none\) \| `shop_proof` \|.*", doc)
    assert row
    # The row cites the line that reads the key.
    m = re.search(r"cat:src/shop_mod\.c:(\d+)", row.group(0))
    assert m
    lines = _read("src", "shop_mod.c").splitlines()
    assert "RENV_SHOP_PROOF" in lines[int(m.group(1)) - 1]


def test_descriptor_declares_each_setting():
    text = _read("src", "shop_mod.c")
    for name, (env, kind) in SETTINGS.items():
        m = re.search(r'\{ "' + name + r'", NULL, "' + env + r'".*?\}', text, re.S)
        assert m, f"{name}: no descriptor row with env {env}"
        assert kind in m.group(0), f"{name}: not {kind}"
    assert "XBOX_SET_ENABLE" in re.search(r'\{ "enable".*?\}', text, re.S).group(0)
    assert '{ "shop", init, NULL, &k_desc' in text


def test_golden_knows_the_stock_value():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        stock = tomllib.load(f)["golden"]["enhance_stock"]
    assert stock.get("mods.shop.enable") == "off"


def test_hook_slot():
    with open(os.path.join(ROOT, "game.toml"), "rb") as f:
        mods = tomllib.load(f)["mods"]
    assert "0x001A0260" in mods["hook_functions"]
    assert "0x001A0260" in mods.get("no_st0", [])
    with open(os.path.join(ROOT, "config", "hook_functions.json"), encoding="utf-8") as f:
        assert "0x001A0260" in json.load(f)["mods"]["hook_functions"]
    assert re.search(r"#define VA_FIRE\s+0x001A0260u", _read("src", "shop_api.c"))


def test_built_and_registered():
    cmake = _read("CMakeLists.txt")
    for f in ("shop_api_logic.c", "shop_api.c", "shop_mod.c"):
        assert f"src/{f}" in cmake, f
    main = _read("src", "main.c")
    assert '#include "shop_mod.h"' in main
    assert "if (shop_mod())" in main


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
