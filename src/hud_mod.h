/*
 * hud_mod.h - the hud mod: BLiNX 2's HUD at the wide frame's edges under
 * Hor+ (openspec change hud-anchors, section 3).
 *
 * Without the layer, or with a toolkit before mod API v5, hud_mod is NULL
 * and no sprite is ever touched.
 */
#ifndef CAT_HUD_MOD_H
#define CAT_HUD_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v5 is not built. */
const void *hud_mod(void);

#endif
