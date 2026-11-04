/*
 * collision_mod.h - the collision overlay mod: the stage's collision
 * triangles around the player, drawn in the game's 3D view through the
 * mod API's 3D debug draw (openspec change collision-overlay). Off by
 * default; off is the stock game.
 *
 * Without the layer, or with a toolkit before mod API v8, collision_mod
 * is NULL and collision_mod_view does nothing.
 */
#ifndef CAT_COLLISION_MOD_H
#define CAT_COLLISION_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v8 is not built. */
const void *collision_mod(void);

/* From the view builders' wrappers (recomp_manual.c: sub_000292A0 for the
 * game camera, sub_0021B1F0), after the game built the view the stage's
 * models are drawn with: the mod reads the view and projection there and
 * hands the frame's drawing to the toolkit; the frame's last build wins.
 * One load and a return while the mod is off. */
void collision_mod_view(void);

#endif
