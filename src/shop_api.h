/*
 * shop_api.h - BLiNX 2's shop and weapons for cat's mods: the catalogue's
 * prices and items, the guns' capacity, ammo per purchase, shot power,
 * shot speed and life and fire interval, and the weapons the players own
 * (openspec change shop-api, design D1-D6).
 *
 * The API is live only while the `shop` mod (shop_mod.c) is on: it owns
 * the fire hook and on_frame. Another mod calls these functions and gets
 * SHOP_OFF while it is off. Off gives every table value back.
 *
 * Threads: overrides may be set from any thread and reach the game at the
 * next on_frame, between two game frames. Reads and shop_owned_set run on
 * the guest thread (a hook or on_frame) and answer SHOP_BUSY elsewhere.
 *
 * Nothing the API writes to the tables is saved: they are the XBE's .data.
 * Gold spent and weapons bought or set are the player's, as any purchase.
 *
 * Without mod API v6 in the toolkit every call answers SHOP_OFF.
 */
#ifndef CAT_SHOP_API_H
#define CAT_SHOP_API_H

#include <stdint.h>

#define SHOP_ITEMS  53      /* catalogue records */
#define SHOP_GUNS   20      /* gun table records */
#define SHOP_SHOTS  30      /* shot types */
#define SHOP_LISTS  4       /* the story shop's price lists */
#define SHOP_LIST_MAX 43    /* records in the longest list (list 0, the guns) */

enum shop_status {
    SHOP_OK,        /* done, or stored for the next frame */
    SHOP_OFF,       /* the shop mod is off, or the tables are not the retail XBE's */
    SHOP_RANGE,     /* a value out of range */
    SHOP_GONE,      /* no such record, gun, shot type, player or character */
    SHOP_BUSY       /* a read off the guest thread */
};

/* A catalogue record: what the shop shows and charges now, and the game's
 * own price and value. */
struct shop_item {
    uint32_t name;          /* the message pointer, 0 for records 50-52 */
    int32_t category;       /* 0 hp ... 7 weapon (design Findings) */
    int32_t price, value;
    int32_t game_price, game_value;
};

/* A gun: the table's values now and the game's, the shot type it fires
 * and its percents (shop_gun_scale times the mod's). */
struct shop_gun {
    int32_t id, kind, shot;
    int32_t capacity, buy, power;
    int32_t game_capacity, game_buy, game_power;
    int32_t speed_pct, life_pct, interval_pct;
};

/* Any thread. */
int shop_item_count(void);
int shop_gun_count(void);
/* The shot type gun id fires, or -1 for no gun (16..41 only). Guns 21, 26
 * and 27 share type 6. */
int shop_gun_shot(int id);

/* Guest thread: SHOP_OK and out filled, SHOP_OFF, SHOP_BUSY, SHOP_GONE. */
enum shop_status shop_item_get(int idx, struct shop_item *out);
enum shop_status shop_gun_get(int id, struct shop_gun *out);

/* Overrides, any thread. Each call sets both of its values; -1 gives the
 * game's back. SHOP_RANGE: anything below -1, a price outside 0..999999, a value no record of
 * the same category has (categories 0, 1 and 4 are amounts: 1..100), a
 * capacity outside 1..99, an ammo per purchase above the capacity, a power
 * outside 0..999, a percent outside 10..1000 (an interval above 100: a
 * gun only recovers faster, D3). */
enum shop_status shop_item_set(int idx, int32_t price, int32_t value);
enum shop_status shop_gun_set(int id, int32_t capacity, int32_t buy);
enum shop_status shop_shot_power_set(int type, int32_t power);
/* The inline stats of gun id's shots and fire, in percent: speed, life
 * (range is speed times life) and busy frames. Guns 37 and 38 keep their
 * interval (another fire path). */
enum shop_status shop_gun_scale(int id, int32_t speed_pct, int32_t life_pct,
                                int32_t interval_pct);

/* Guest thread: character `character` of player `player`'s weapon and
 * ammo, as the shop's buy writes them. A set takes effect from the next
 * stage (design open question 1); SHOP_RANGE for a weapon the catalogue
 * does not sell (0 is none) or ammo above its capacity. */
enum shop_status shop_owned_get(int player, int character, int *weapon, int *ammo);
enum shop_status shop_owned_set(int player, int character, int weapon, int ammo);

/* The story shop's price lists (design Findings, D10). The story shop does
 * not read the catalogue: it charges from four lists of its own, list 0
 * the guns (record 1 the TS-2000), lists 1-3 not yet named. It copies them
 * into its stock on entering, so a price set shows from the next visit,
 * and it buys back at half the price. Any thread: the records in a list, 0 for
 * no such list. */
int shop_list_count(int list);
/* Guest thread: the price now and the game's. */
enum shop_status shop_list_price_get(int list, int idx, int32_t *price, int32_t *game_price);
/* Any thread: a price in 0..999999, -1 for the game's (SHOP_RANGE
 * otherwise). The mod's price
 * percent applies on top, as for the catalogue. */
enum shop_status shop_list_price_set(int list, int idx, int32_t price);

const char *shop_status_text(enum shop_status s);

/* ---- for the owner (shop_mod.c) ---------------------------------------- */

struct xbox_mod_api;
struct xbox_mod;

/* From the owner's init: registers the fire hook and on_frame. 0 when the
 * toolkit has no v6 calls or the hook slot is missing (one log line). */
int shop_api_attach(const struct xbox_mod_api *api, const struct xbox_mod *owner);
/* The owner's switch. Off drops every override and percent and puts the
 * game's values back at the next on_frame. Any thread. */
void shop_api_enable(int on);
/* The mod's percents (design D7), applied on top of the overrides; each
 * 100 for none. Any thread. */
void shop_api_pct(int price, int ammo, int power, int speed, int interval);
/* 1 when the tables were read and pass the check, 0 before the first
 * on_frame while on, -1 when the check failed (another XBE). */
int shop_api_ready(void);

/* The live proof: called on the guest thread for each shot the fire hook
 * scaled, after the scaling. */
typedef void (*shop_shot_fn)(int gun, uint32_t slot_va, void *user);
void shop_api_on_shot(shop_shot_fn fn, void *user);

#endif
