/*
 * lod_scale.h - the lod mod: character detail levels that follow the render
 * scale (openspec change lod-scale). Off by default.
 *
 * Without the layer, or with a toolkit before mod API v3, lod_mod is NULL
 * and the game's table is never touched.
 */
#ifndef CAT_LOD_SCALE_H
#define CAT_LOD_SCALE_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v3 is not built. */
const void *lod_mod(void);

#endif
