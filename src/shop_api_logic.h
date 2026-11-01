/*
 * shop_api_logic.h - the shop API's pure part: BLiNX 2's catalogue, gun
 * and shot tables, the shots a fire call made and the fire timer, over a
 * plain memory view, so scripts/test_shop.py can run it against a fake
 * guest (openspec change shop-api, design Findings, D1-D4).
 *
 * Nothing here knows threads or the mod API: shop_api.c holds the state
 * and calls these on the guest thread.
 */
#ifndef CAT_SHOP_API_LOGIC_H
#define CAT_SHOP_API_LOGIC_H

#include <stdint.h>
#include "shop_api.h"

/* menu_shop_catalogue: records of 0x14 in .data, which the game never
 * writes. */
#define SHOPL_CAT_VA        0x004AACE0u
#define SHOPL_CAT_SIZE      0x14u
#define SHOPL_CAT_NAME      0x00u
#define SHOPL_CAT_PRICE     0x08u
#define SHOPL_CAT_CATEGORY  0x0Cu
#define SHOPL_CAT_VALUE     0x10u
#define SHOPL_CAT_WEAPON    7

/* The story shop's price lists (D10): records of 0x4C in .data, the price
 * at +0x30 and the record's own index at +0x34. The game never writes
 * them: menu_story_shop_build copies them into the stock at 0xE42600 on
 * entering the shop, which is what the shop draws and charges. */
#define SHOPL_LIST_SIZE     0x4Cu
#define SHOPL_LIST_PRICE    0x30u
#define SHOPL_LIST_INDEX    0x34u
extern const uint32_t shopl_list_va[SHOP_LISTS];
extern const int shopl_list_n[SHOP_LISTS];

/* The gun table: {id, capacity, kind, ammo per purchase}, ended by id -1
 * at record SHOP_GUNS. */
#define SHOPL_GUN_VA        0x00402860u
#define SHOPL_GUN_SIZE      0x10u
#define SHOPL_GUN_CAP       0x04u
#define SHOPL_GUN_KIND      0x08u
#define SHOPL_GUN_BUY       0x0Cu

/* The shot table, indexed by shot type; +0xC is power (damage x 10). */
#define SHOPL_SHOT_VA       0x004022E0u
#define SHOPL_SHOT_SIZE     0x24u
#define SHOPL_SHOT_POWER    0x0Cu

/* The player status the shop buys into (one per player), its characters
 * and the bytes a weapon buy writes. */
#define SHOPL_STATUS_VA     0x00E9DA40u
#define SHOPL_STATUS_SIZE   0x2A4u
#define SHOPL_STATUS_GOLD   0x14u
#define SHOPL_CHAR          0x40u
#define SHOPL_CHAR_SIZE     0x98u
#define SHOPL_CHAR_WEAPON   0x50u
#define SHOPL_CHAR_AMMO     0x53u
#define SHOPL_CHARS_VA      0x00EAE7D4u     /* a byte per player: its characters */
#define SHOPL_PLAYERS       4
#define SHOPL_CHARS_MAX     4

/* The item pool (ent_item_pool): 256 slots of 0x6C, +0 used. A player's
 * shot is item type 0x25 (0x24 for gun 32), its velocity three floats at
 * +0x2C and its life in frames a short at +0x12. */
#define SHOPL_POOL_VA       0x00B22E68u
#define SHOPL_POOL_N        256u
#define SHOPL_POOL_SIZE     0x6Cu
#define SHOPL_SLOT_TYPE     0x02u
#define SHOPL_SLOT_LIFE     0x12u
#define SHOPL_SLOT_VEL      0x2Cu
#define SHOPL_SHOT_ITEM     0x25u
#define SHOPL_SHOT_ITEM_B   0x24u

/* The player's object (0xCD2440 + i*0x30C): the weapon in hand, the fire
 * timer the gate counts in frames, ammo and capacity. */
#define SHOPL_PLAYER0_VA    0x00CD2440u
#define SHOPL_PLAYER_SIZE   0x30Cu
#define SHOPL_PLR_WEAPON    0x3Eu
#define SHOPL_PLR_TIMER     0x178u
#define SHOPL_PLR_AMMO      0x209u
#define SHOPL_PLR_CAP       0x20Au

/* Guns are ids 16..41; vacuums are below 16. */
#define SHOPL_GUN_FIRST     16
#define SHOPL_GUN_LAST      41

struct shopl_mem {
    uint8_t *base;
    uint32_t size;
};

/* The game's values, read once (D1). */
struct shopl_game {
    uint32_t name[SHOP_ITEMS];
    int32_t price[SHOP_ITEMS], category[SHOP_ITEMS], value[SHOP_ITEMS];
    int32_t gun_id[SHOP_GUNS], cap[SHOP_GUNS], kind[SHOP_GUNS], buy[SHOP_GUNS];
    int32_t power[SHOP_SHOTS];
    int32_t list_price[SHOP_LISTS][SHOP_LIST_MAX];
};

/* The overrides, -1 for none (D1). */
struct shopl_over {
    int32_t price[SHOP_ITEMS], value[SHOP_ITEMS];
    int32_t cap[SHOP_GUNS], buy[SHOP_GUNS];
    int32_t power[SHOP_SHOTS];
    int32_t list_price[SHOP_LISTS][SHOP_LIST_MAX];
};

/* The mod's percents (D7), 100 for none. */
struct shopl_pct {
    int price, ammo, power;
};

/* A story list record's VA (off into the record), or 0 for none. */
uint32_t shopl_list_va_of(int list, int idx, uint32_t off);

/* 1 when the tables look as the retail XBE's do; 0 for another
 * image (nothing is written then). */
int shopl_check(const struct shopl_mem *m);
void shopl_read_game(const struct shopl_mem *m, struct shopl_game *g);
void shopl_over_clear(struct shopl_over *o);

/* Effective values: the base (an override, else the game's) times pct.
 * A price rounds to the nearest 10 and stays at least 10 (0 stays 0);
 * ammo stays in 1..99; power in 0..999. */
int32_t shopl_price(int32_t base, int pct);
int32_t shopl_ammo(int32_t base, int pct);
int32_t shopl_power(int32_t base, int pct);

/* Write every effective value into the tables: the number of words that
 * changed. Buy ammo never passes the capacity. */
int shopl_apply(const struct shopl_mem *m, const struct shopl_game *g,
                const struct shopl_over *o, const struct shopl_pct *p);
/* Put the game's values back: the number of words that changed. */
int shopl_restore(const struct shopl_mem *m, const struct shopl_game *g);

/* The gun table's record of a gun id, or -1. */
int shopl_gun_index(const struct shopl_game *g, int id);
/* The shot type a gun fires (the fire function's switch), or -1 for no
 * gun. */
int shopl_gun_shot(int id);
/* A gun's fire start and busy threshold, in frames of the fire timer;
 * 0 for no gun or one whose interval is not scaled (37, 38). */
int shopl_gun_interval(int id, float *start, float *threshold);
/* The timer after a fire with an interval of pct % (below 100): the frames
 * left to the threshold times pct / 100. Unchanged at 100 or above, for no
 * gun or a timer already at the threshold: moving it back could fire
 * again. */
float shopl_fire_timer(int id, float timer, int pct);

/* Checks an override for a record: SHOP_OK, or SHOP_RANGE for a price
 * outside 0..999999 or a value that names no item of the record's
 * category (amounts, categories 0, 1, 4: 1..100). -1 always passes. */
enum shop_status shopl_item_check(const struct shopl_game *g, int idx, int32_t price,
                                  int32_t value);
/* 1 when some catalogue record sells weapon id. */
int shopl_sells_weapon(const struct shopl_game *g, int id);

/* The pool's used bytes, for a pre hook. */
void shopl_pool_used(const struct shopl_mem *m, uint8_t used[SHOPL_POOL_N]);
/* The shots a fire call made: slots free in before and used now with a
 * shot's item type. Scales their velocity by speed_pct and their life by
 * life_pct (1..0x7FFF). Their slot VAs into out (at most max); the count. */
int shopl_scale_shots(const struct shopl_mem *m, const uint8_t before[SHOPL_POOL_N],
                      int speed_pct, int life_pct, uint32_t *out, int max);

/* A character's weapon and ammo (the bytes a buy writes): SHOP_OK or
 * SHOP_GONE for no such player or character. */
enum shop_status shopl_owned_get(const struct shopl_mem *m, int player, int character,
                                 int *weapon, int *ammo);
/* As a buy writes them: SHOP_RANGE for a weapon no record sells (0, none,
 * passes) or ammo outside 0..the gun's capacity (a vacuum takes 0; a gun
 * the table does not list, 0..99). */
enum shop_status shopl_owned_set(const struct shopl_mem *m, const struct shopl_game *g,
                                 int player, int character, int weapon, int ammo);

/* Every owned gun's ammo (the status bytes a buy wrote) down to the gun
 * table's capacity now: a buy at a raised ammo_pct must not outlive the
 * percent, or the mod, once the table is lowered or given back. Vacuums,
 * guns the table does not list and ammo at or below the capacity are left
 * alone. The number of bytes lowered. */
int shopl_clamp_owned(const struct shopl_mem *m, const struct shopl_game *g);
#endif
