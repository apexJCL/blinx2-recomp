/*
 * debug_menu.h - the debug_menu mod: opens the title's own debug menu and
 * its stage select from the in-game menu (openspec change debug-menu-mod).
 * Off by default.
 *
 * Without the layer, or with a toolkit before mod API v4, debug_menu_mod is
 * NULL and the title is never touched.
 */
#ifndef CAT_DEBUG_MENU_H
#define CAT_DEBUG_MENU_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v4 is not built. */
const void *debug_menu_mod(void);

#endif
