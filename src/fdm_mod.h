/*
 * fdm_mod.h - the fdm mod, shown as "Full Diagonal Movement": the walk's
 * target speed follows the stick's full length, so a diagonal runs about
 * 1.69 times as fast as a straight line, as in BLiNX 1 (openspec change
 * b2-full-diagonal-movement). Off by default; off is the stock game.
 *
 * Without the layer, or with a toolkit before mod API v4, fdm_mod is NULL
 * and the walk stays stock.
 */
#ifndef CAT_FDM_MOD_H
#define CAT_FDM_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API is not built. */
const void *fdm_mod(void);

#endif
