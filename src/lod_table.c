/*
 * lod_table.c - the lod mod's maths (lod_table.h; design D4).
 */
#include <math.h>
#include <string.h>
#include "lod_table.h"

const int32_t lod_stock[LOD_TABLE_N][2] = {
    { 8, 0 }, { 24, 1 }, { 48, 2 }, { 80, 3 }, { 160, 4 }
};

void lod_thresholds(unsigned scale, double distance, int32_t out[LOD_SCALED_N])
{
    double k = (double)(scale ? scale : 1u);
    int i;

    /* NaN fails the test too: stock distance. */
    if (!(distance > 0.0))
        distance = 1.0;
    k *= distance;
    for (i = 0; i < LOD_SCALED_N; i++) {
        double t = (double)lod_stock[i + 1][0] / k;
        long v = lround(t);

        /* Never below 1: a threshold of 0 is above no radius, so its
         * level could never be picked. */
        out[i] = v < 1 ? 1 : (int32_t)v;
    }
}

int lod_table_is_stock(const int32_t words[LOD_TABLE_N][2])
{
    int i;

    for (i = 0; i < LOD_TABLE_N; i++)
        if (words[i][0] != lod_stock[i][0] || words[i][1] != lod_stock[i][1])
            return 0;
    return 1;
}

void lod_stock_thresholds(int32_t out[LOD_SCALED_N])
{
    int i;

    for (i = 0; i < LOD_SCALED_N; i++)
        out[i] = lod_stock[i + 1][0];
}

void lod_state_init(struct lod_state *st)
{
    st->checked = 0;
    st->dead = 0;
    lod_stock_thresholds(st->have);
}

enum lod_step_result lod_step(struct lod_state *st, volatile uint32_t *words,
                              const int32_t want[LOD_SCALED_N])
{
    int i;

    if (st->dead)
        return LOD_DEAD;
    if (!memcmp(want, st->have, sizeof st->have))
        return LOD_SAME;
    if (!st->checked) {
        int32_t w[LOD_TABLE_N][2];

        for (i = 0; i < LOD_TABLE_N; i++) {
            w[i][0] = (int32_t)words[2 * i];
            w[i][1] = (int32_t)words[2 * i + 1];
        }
        if (!lod_table_is_stock(w)) {
            st->dead = 1;
            return LOD_NOT_STOCK;
        }
        st->checked = 1;
    } else {
        /* A patch, a cheat or a later fix writing the table wins: the mod
         * neither overwrites nor "restores" values it did not put there. */
        for (i = 0; i < LOD_SCALED_N; i++) {
            if ((int32_t)words[2 * (i + 1)] != st->have[i]) {
                st->dead = 1;
                return LOD_FOREIGN;
            }
        }
    }
    for (i = 0; i < LOD_SCALED_N; i++)
        words[2 * (i + 1)] = (uint32_t)want[i];
    memcpy(st->have, want, sizeof st->have);
    return LOD_WROTE;
}
