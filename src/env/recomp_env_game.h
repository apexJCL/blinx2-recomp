/*
 * recomp_env_game.h - this game's own environment keys, added to the
 * toolkit's table (xboxrecomp src/platform/recomp_env.h, which includes this
 * file when RECOMP_ENV_HAVE_GAME_KEYS is defined; CMakeLists.txt sets it on
 * the recomp_env target). Same row format: X(ID, TIER, NAME, LEGACY, HELP).
 * Inventory with meanings: docs/env.md.
 */
#ifndef RECOMP_ENV_GAME_H
#define RECOMP_ENV_GAME_H

/* RECOMP_GAME_FILES and RECOMP_HDD_DIR: toolkit rows in a toolkit that
 * defines RECOMP_ENV_HAVE_FOLDER_ROWS (b3-public-release), game rows before
 * it, since a key defined twice does not compile and the public build pins
 * an older toolkit tag than a local build's checkout. Drop these two rows
 * (and this #ifndef) once [toolkit] in game.toml is past the toolkit merge. */
#ifndef RECOMP_ENV_HAVE_FOLDER_ROWS
#define CAT_ENV_FOLDER_KEYS(X) \
    X(GAME_FILES,        CONFIG, "RECOMP_GAME_FILES",        NULL, "game files directory (default: game_files/ in the working directory)") \
    X(HDD_DIR,           CONFIG, "RECOMP_HDD_DIR",           NULL, "emulated hard disk: partition images, saves, caches (default: the toolkit's save root, <data>/xboxrecomp/<title id>)")
#else
#define CAT_ENV_FOLDER_KEYS(X)
#endif

/* RECOMP_RUMBLE: a toolkit row since its v0.16 sync (RECOMP_ENV_HAVE_RUMBLE_ROW,
 * read there by the OHCI pad model), a game row before it, for the same
 * reason. pad_input.c reads it either way. Drop with the folder rows once
 * the pin is past that merge. */
#ifndef RECOMP_ENV_HAVE_RUMBLE_ROW
#define CAT_ENV_RUMBLE_KEYS(X) \
    X(RUMBLE,            CONFIG, "RECOMP_RUMBLE",            NULL, "0: no rumble")
#else
#define CAT_ENV_RUMBLE_KEYS(X)
#endif

#define RECOMP_ENV_GAME_KEYS(X) \
    CAT_ENV_FOLDER_KEYS(X) \
    CAT_ENV_RUMBLE_KEYS(X) \
    X(SAVE_SEED,         CONFIG, "RECOMP_SAVE_SEED",         NULL, "seed the save dir from this save before boot") \
    X(BUILD_XBE,         CONFIG, "RECOMP_BUILD_XBE",         NULL, "the XBE a packaged build was made from (sha256 and verdict), printed at boot") \
    X(INPUT_SCRIPT,      CONFIG, "RECOMP_INPUT_SCRIPT",      NULL, "scripted pad: @preset, file or inline script") \
    X(INPUT_STRICT,      CONFIG, "RECOMP_INPUT_STRICT",      NULL, "1: a bad input script ends the run") \
    X(HOST_PAD,          CONFIG, "RECOMP_HOST_PAD",          NULL, "0/1: host gamepads in or out") \
    X(FPS_MODE,          CONFIG, "RECOMP_FPS_MODE",          NULL, "enhancements: fps.mode, lock30 only (lock60 and free are not available)") \
    X(GLOW,              CONFIG, "RECOMP_GLOW",              NULL, "enhancements: fx.glow, on|off (the mode-3 glow pass)") \
    X(GLOW_INTENSITY,    CONFIG, "RECOMP_GLOW_INTENSITY",    NULL, "enhancements: fx.glow_intensity, 0.0..2.0 (scales the glow layer)") \
    X(CAMERA_FREE,       CONFIG, "RECOMP_CAMERA_FREE",       NULL, "enhancements: camera.free, off|on (a hotkey toggles a free-flying camera)") \
    X(CAMERA_FREE_SPEED, CONFIG, "RECOMP_CAMERA_FREE_SPEED", NULL, "enhancements: camera.free_speed, 0.05..20, a multiplier of the fly speed (1)") \
    X(CAMERA_FREE_LOOK_SENS, CONFIG, "RECOMP_CAMERA_FREE_LOOK_SENS", NULL, "enhancements: camera.free_look_sens, 0.05..10, a multiplier of the look rate (1)") \
    X(CAMERA_FREE_MOUSE_SENS, CONFIG, "RECOMP_CAMERA_FREE_MOUSE_SENS", NULL, "enhancements: camera.free_mouse_sens, 0.05..10, a multiplier of the mouse look rate on top of camera.free_look_sens (1)") \
    X(CAMERA_FREE_INVERT_X, CONFIG, "RECOMP_CAMERA_FREE_INVERT_X", NULL, "enhancements: camera.free_invert_x, true|false, turn the free camera the other way (false)") \
    X(CAMERA_FREE_INVERT_Y, CONFIG, "RECOMP_CAMERA_FREE_INVERT_Y", NULL, "enhancements: camera.free_invert_y, true|false, pitch the free camera the other way (false)") \
    X(CAMERA_FREE_FAST,  CONFIG, "RECOMP_CAMERA_FREE_FAST",  NULL, "enhancements: camera.free_fast, 1..20, the speed multiplier while Fast is held (4)") \
    X(CAMERA_FREE_SLOW,  CONFIG, "RECOMP_CAMERA_FREE_SLOW",  NULL, "enhancements: camera.free_slow, 0.05..1, the speed multiplier while Slow is held (0.25)") \
    X(CAMERA_FREE_HUD,   CONFIG, "RECOMP_CAMERA_FREE_HUD",   NULL, "enhancements: camera.free_hud, keep|hide (the HUD while the free camera flies)") \
    X(CAMERA_FREE_TOGGLE, CONFIG, "RECOMP_CAMERA_FREE_TOGGLE", NULL, "enhancements: the bindings of action camera.free.toggle (alias camera.free_toggle), comma-separated; start and stop the free camera (F6,guide+y)") \
    X(CAMERA_FREE_HUD_KEY, CONFIG, "RECOMP_CAMERA_FREE_HUD_KEY", NULL, "enhancements: the bindings of action camera.free.hud (alias camera.free_hud_key); show or hide the HUD while flying (F7)") \
    X(CAMERA_FREE_FREEZE_KEY, CONFIG, "RECOMP_CAMERA_FREE_FREEZE_KEY", NULL, "enhancements: the bindings of action camera.free.freeze (alias camera.free_freeze_key); stop and restart the world while flying (End)") \
    X(CAMERA_FREE_RESET_KEY, CONFIG, "RECOMP_CAMERA_FREE_RESET_KEY", NULL, "enhancements: the bindings of action camera.free.reset (alias camera.free_reset_key); put the free camera back on the game's (Home)") \
    X(LOD,               CONFIG, "RECOMP_LOD",               NULL, "enhancements: mods.lod.enable, off|on (character detail levels follow the render scale)") \
    X(LOD_FOLLOW_SCALE,  CONFIG, "RECOMP_LOD_FOLLOW_SCALE",  NULL, "enhancements: mods.lod.follow_scale, true|false (divide the detail thresholds by the render scale)") \
    X(LOD_DISTANCE,      CONFIG, "RECOMP_LOD_DISTANCE",      NULL, "enhancements: mods.lod.distance, 0.5..4 step 0.25, how far detail holds (1)") \
    X(DEBUG_MENU,        CONFIG, "RECOMP_DEBUG_MENU",        NULL, "enhancements: mods.debug_menu.enable, off|on (the title's debug menu and stage select, opened from the in-game menu at PRESS START)") \
    X(DEBUG_MENU_KEY,    CONFIG, "RECOMP_DEBUG_MENU_KEY",    NULL, "enhancements: [input.actions] debug_menu.open, the bindings that open the debug menu at PRESS START (unbound)") \
    X(HUD,               CONFIG, "RECOMP_HUD",               NULL, "enhancements: mods.hud.enable, off|on (the HUD at the edges of a wide display.aspect; on by default)") \
    X(ENTITIES,          CONFIG, "RECOMP_ENTITIES",          NULL, "enhancements: mods.entities.enable, off|on (the entity API and the menu's enemy spawn, defeat and hp rows)") \
    X(ENTITIES_HP_SCALE, CONFIG, "RECOMP_ENTITIES_HP_SCALE", NULL, "enhancements: mods.entities.hp_scale, 1..10, class-1 enemy hp times this from the next area setup (1)") \
    X(ENTITIES_SPAWN_KEY, CONFIG, "RECOMP_ENTITIES_SPAWN_KEY", NULL, "enhancements: [input.actions] entities.spawn, the bindings that spawn a copy of the nearest enemy (unbound)") \
    X(ENTITIES_KILL_KEY, CONFIG, "RECOMP_ENTITIES_KILL_KEY", NULL, "enhancements: [input.actions] entities.kill, the bindings that defeat the nearest enemy (unbound)") \
    X(CRYSTALS,          CONFIG, "RECOMP_CRYSTALS",          NULL, "enhancements: mods.crystals.enable, off|on (BLiNX 1-style crystal sets in Sweepers stages)") \
    X(WALLS,             CONFIG, "RECOMP_WALLS",             NULL, "enhancements: mods.walls.enable, off|on (the player's sphere no longer slides through walls thinner than twice its radius)") \
    X(SHOP,              CONFIG, "RECOMP_SHOP",              NULL, "enhancements: mods.shop.enable, off|on (the shop API and the menu's price and gun stat percents)") \
    X(SHOP_PRICE_PCT,    CONFIG, "RECOMP_SHOP_PRICE_PCT",    NULL, "enhancements: mods.shop.price_pct, 10..500 step 10, every shop price in percent, rounded to 10 (100)") \
    X(SHOP_AMMO_PCT,     CONFIG, "RECOMP_SHOP_AMMO_PCT",     NULL, "enhancements: mods.shop.ammo_pct, 50..500 step 10, every gun's capacity and ammo per purchase in percent, 1..99 (100)") \
    X(SHOP_POWER_PCT,    CONFIG, "RECOMP_SHOP_POWER_PCT",    NULL, "enhancements: mods.shop.power_pct, 50..500 step 10, every gun shot's power in percent (100)") \
    X(SHOP_SPEED_PCT,    CONFIG, "RECOMP_SHOP_SPEED_PCT",    NULL, "enhancements: mods.shop.speed_pct, 50..300 step 10, every gun shot's speed in percent (100)") \
    X(SHOP_INTERVAL_PCT, CONFIG, "RECOMP_SHOP_INTERVAL_PCT", NULL, "enhancements: mods.shop.interval_pct, 25..100 step 5, the frames a gun stays busy after a shot in percent (100)") \
    X(INPUT_TRACE,       TRACE, "input",           "RECOMP_INPUT_TRACE",       "pad handles and states") \
    X(UNIMPL_BUDGET,     TRACE, "unimpl_budget",   NULL,                       "=n: [UNIMPL] lines per address before only hits 10, 100, ... (3)") \
    X(CAM_LOG,           DEBUG, "cam_log",         NULL,                       "=n: game camera, view, projection and cull planes every n-th view build") \
    X(CAM_FIX,           DEBUG, "cam_fix",         NULL,                       "=dx:dy:dz:dyaw:dpitch or hold[:n]: debug view through the game camera build") \
    X(APU_FAULT_BENCH,   DEBUG, "apu_fault_bench", "RECOMP_APU_FAULT_BENCH",   "=n: time n trapped APU accesses") \
    X(MEM_DUMP,          DEBUG, "mem_dump",        "RECOMP_MEM_DUMP",          "=va,bytes,prefix: guest memory dumps") \
    X(MEM_DUMP_EVERY,    DEBUG, "mem_dump_every",  "RECOMP_MEM_DUMP_EVERY",    "=s: mem_dump period, default 20") \
    X(ENTITIES_PROOF,    DEBUG, "entities_proof",  NULL,                       "=steps (+ separated): spawn:f, fill:f, kill:f, rew:f, spawnrew:f, tc:f, tcreq:r, tcdur:n, rewarea:n, setuponly:1, from:id, keep:1, atsrc:1, killany:1, out:file; the entity API's live proof and per-frame list log") \
    X(CRYSTALS_PROOF,    DEBUG, "crystals_proof",  NULL,                       "=steps (+ separated): seq:digits (| waits for a mission change), at:f, every:n, dup:n, rew:f, out:file; the crystals mod's live proof and record log") \
    X(SHOP_PROOF,        DEBUG, "shop_proof",      NULL,                       "=steps (+ separated): log:1, out:file, gun:id, fire:f, every:n, shots:k, gold:n, goldat:f; the shop API's live proof and per-frame shop and gun log") \
    X(WALLS_TRACE,       DEBUG, "walls_trace",     NULL,                       "=opts (+ separated): out:file, fix:0|1, probe:f, samples:n, rad:cr, wmax:cr, tp:k, at:f, depth:pct, for:n; the walls mod's collision trace and A/B probes (mod on)") \
    X(PAD_PEEK,          DEBUG, "pad_peek",        NULL,                       "=va:n[:x],...: guest dwords on every scripted pad poll") \
    X(THREAD_DUMP,       DEBUG, "thread_dump",     "RECOMP_THREAD_DUMP",       "dump every thread: SIGUSR1 (macOS), touch thread_dump.trigger (Windows)")

/* Game keys whose values contain commas (see recomp_env.h). */
#define RECOMP_ENV_GAME_COMMA_KEYS "mem_dump", "pad_peek",

/* Defaults this game gives toolkit keys, D(ID, "value"): used when neither
 * the key nor its old variable is set.
 *
 * GUEST_CPUS=one: every guest thread on one host core, as on the console.
 * The stage loader and the main thread add lights to one global pool with
 * "slot = count; fill; count = slot + 1"; on two cores the loops ran at
 * once, lost each other's entries and the terrain baked black (dark water,
 * 2026-10-07). The toolkit's default since v0.16 is every core, as
 * upstream's. RECOMP_GUEST_CPUS=all is the A/B.
 *
 * DISPATCH_GATE=1: the one-CPU DISPATCH gate. Device interrupts run at the
 * gate holder's safe points and queued DPCs on the guest thread, so D3D's
 * vblank DPC and the title never run guest code at once, as on the
 * console's one CPU. The fork ran this way unconditionally before v0.16;
 * upstream made it opt-in.
 *
 * FLIP_PACING=1: the pushbuffer walker and the KickOff ack hold after a
 * flip until the guest vblank reaches the swap's interval, as the NV2A's
 * FLIP_STALL does. Off, the stall completes at once and D3D's Swap returns
 * before the vblank it asked to wait for. Also the fork's behaviour before
 * v0.16.
 *
 * The DSOUND GP doorbell ack (apu_dsp_ack) was a game default until the
 * toolkit made `auto` its own default (chore/vanilla-cleanup): the doorbell
 * is GP scratch page 0 + 0x810, found from the GPSADDR table, which ends
 * the XDK DSOUND submit's spin at loc_00334325 (sub_003341BE). It was
 * 0x80A1C810, and reserving physical page 0 (upstream 423263b) moved it to
 * 0x80A20810. RECOMP_DEBUG=apu_dsp_ack=0 turns it off.
 *
 * CPUID_NO_SIMD=1: cpuid hides MMX, FXSR and SSE, as the fork did before
 * v0.16. Reported, D3DX's JPEG decoder switches to its MMX IDCT
 * (sub_00307F41), which no scene has ever run lifted; drop this once a
 * golden and a JPEG-heavy scene pass on both backends with SIMD reported.
 *
 * These rows came with the toolkit's v0.16 sync, as RECOMP_RUMBLE did, so
 * they are guarded the same way: a pin before that merge has none of them
 * and already behaves this way. Drop the guard with the rumble one. */
#ifdef RECOMP_ENV_HAVE_RUMBLE_ROW
#define RECOMP_ENV_GAME_DEFAULTS(D) \
    D(GUEST_CPUS,    "one") \
    D(DISPATCH_GATE, "1") \
    D(FLIP_PACING,   "1") \
    D(CPUID_NO_SIMD, "1")
#else
#define RECOMP_ENV_GAME_DEFAULTS(D)
#endif

#endif /* RECOMP_ENV_GAME_H */
