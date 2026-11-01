/*
 * crystals_mod.h - the crystals mod: BLiNX 1-style crystal sets in BLiNX 2
 * (a row of four in pickup order; three of one colour give that time
 * control, four give it twice), feeding BLiNX 2's own stock and caps
 * (openspec change crystal-sets). Sweepers stages only. Off by default.
 *
 * Without the layer, or with a toolkit before mod API v6, crystals_mod is
 * NULL and the crystals stay stock.
 */
#ifndef CAT_CRYSTALS_MOD_H
#define CAT_CRYSTALS_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v6 is not built. */
const void *crystals_mod(void);

#endif
