/*
 * lod_table.h - the maths of the lod mod (lod_scale.c; openspec change
 * lod-scale), pure C so scripts/test_lod_scale.py can drive it.
 *
 * sub_0019A2C0 picks a character's detail level from its screen radius in
 * 640x480 units, looked up in the (threshold, level) table at 0x450B08:
 * the first threshold above the radius gives the level. The mod divides
 * thresholds 1..4 by the render scale times a distance factor, so a model
 * reaches each level at the size on screen it had at 480 lines.
 */
#ifndef CAT_LOD_TABLE_H
#define CAT_LOD_TABLE_H

#include <stdint.h>

#define LOD_TABLE_VA  0x450B08u     /* (int32 threshold, int32 level) x 6 */
#define LOD_TABLE_N   5             /* entries the lookup reads (0..4) */
#define LOD_SCALED_N  4             /* thresholds 1..4; 0 stays the game's */

/* The stock table as the XBE ships it: threshold, level for entries 0..4. */
extern const int32_t lod_stock[LOD_TABLE_N][2];

/* Thresholds 1..4 for this render scale and distance:
 * max(1, lround(stock / (scale * distance))). scale <= 0 or a distance
 * that is not a positive number counts as 1. */
void lod_thresholds(unsigned scale, double distance, int32_t out[LOD_SCALED_N]);

/* 1 when words (LOD_TABLE_N pairs, as read at LOD_TABLE_VA) are the stock
 * table. */
int lod_table_is_stock(const int32_t words[LOD_TABLE_N][2]);

/* The stock thresholds 1..4: what the mod puts back when it is off. */
void lod_stock_thresholds(int32_t out[LOD_SCALED_N]);

/* The mod's hold on the table (design D5). have is what it last wrote,
 * stock at the start, so an off mod that never wrote writes nothing. */
struct lod_state {
    int checked;                    /* the stock table was seen */
    int dead;                       /* not ours any more: no write this run */
    int32_t have[LOD_SCALED_N];
};

enum lod_step_result {
    LOD_SAME,       /* want == have: nothing read or written */
    LOD_WROTE,      /* thresholds 1..4 now hold want */
    LOD_DEAD,       /* stopped earlier: nothing read or written */
    LOD_NOT_STOCK,  /* first write found a table that is not the stock one */
    LOD_FOREIGN     /* the table no longer holds have: someone else wrote it */
};

void lod_state_init(struct lod_state *st);

/* Bring thresholds 1..4 of the table at words (LOD_TABLE_N pairs of
 * little-endian words, the guest's LOD_TABLE_VA) to want. Before the
 * first write the whole table must be stock, after it thresholds 1..4 must
 * still be have; otherwise the state goes dead and the table is never
 * touched again, restore included. Threshold 0 and the level words are only
 * read. */
enum lod_step_result lod_step(struct lod_state *st, volatile uint32_t *words,
                              const int32_t want[LOD_SCALED_N]);

#endif
