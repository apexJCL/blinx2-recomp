/*
 * glow_mod.h - the glow mod: fx.glow and fx.glow_intensity on the menu's
 * Mods page, live (openspec change glow-mod). On by default and stock at
 * its defaults.
 *
 * Without the layer, or with a toolkit before mod API v4, glow_mod is NULL
 * and main.c reads the two keys once at start, as before.
 */
#ifndef CAT_GLOW_MOD_H
#define CAT_GLOW_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v4 is not built. */
const void *glow_mod(void);

#endif
