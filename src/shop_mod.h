/*
 * shop_mod.h - the shop mod: owns the shop API (shop_api.h) and puts five
 * percents in the menu: prices, gun ammo, power, shot speed and recovery
 * (openspec change shop-api, D7). Off by default.
 *
 * Without the layer, or with a toolkit before mod API v6, shop_mod is NULL
 * and the API answers SHOP_OFF.
 */
#ifndef CAT_SHOP_MOD_H
#define CAT_SHOP_MOD_H

/* The table entry main.c registers before xbox_enhance_init; NULL when
 * the mod API v6 is not built. */
const void *shop_mod(void);

#endif
