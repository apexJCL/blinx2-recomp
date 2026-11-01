/*
 * walls_mod.h - the walls mod: stops the player's collision sphere from
 * sliding through walls thinner than twice its radius (openspec change
 * collision-spike, task 1.7). Off by default; off is the stock game.
 *
 * Without the layer, or with a toolkit before mod API v6, walls_mod is
 * NULL and the collision stays stock.
 */
#ifndef CAT_WALLS_MOD_H
#define CAT_WALLS_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v6 is not built. */
const void *walls_mod(void);

#endif
