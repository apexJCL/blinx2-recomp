/*
 * entities_mod.h - the entities mod: owns the entity API (ent_api.h) and
 * puts it in the menu: spawn a copy of the nearest enemy, defeat the
 * nearest enemy, class-1 hp times n (openspec change entity-mod-api, D8).
 * Off by default.
 *
 * Without the layer, or with a toolkit before mod API v6, entities_mod is
 * NULL and the API answers ENT_OFF.
 */
#ifndef CAT_ENTITIES_MOD_H
#define CAT_ENTITIES_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v6 is not built. */
const void *entities_mod(void);

#endif
