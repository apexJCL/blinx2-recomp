/*
 * speed_mod.h - the speed mod, shown as "Speed readout": a debug card with
 * the player's run speed as a ratio to a full straight push (openspec
 * change b2-full-diagonal-movement, D4). Off by default; it only reads the
 * guest.
 *
 * Without the layer, or with a toolkit before mod API v7 (the status
 * card), speed_mod is NULL.
 */
#ifndef CAT_SPEED_MOD_H
#define CAT_SPEED_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API is not built. */
const void *speed_mod(void);

#endif
