/*
 * recomp_env_game.h - this game's own environment keys, added to the
 * toolkit's table (xboxrecomp src/platform/recomp_env.h, which includes this
 * file when RECOMP_ENV_HAVE_GAME_KEYS is defined; CMakeLists.txt sets it on
 * the recomp_env target). Same row format: X(ID, TIER, NAME, LEGACY, HELP).
 * Inventory with meanings: docs/env.md.
 */
#ifndef RECOMP_ENV_GAME_H
#define RECOMP_ENV_GAME_H

#define RECOMP_ENV_GAME_KEYS(X) \
    X(GAME_FILES,        CONFIG, "RECOMP_GAME_FILES",        NULL, "game files directory (default: game_files/ in the working directory)") \
    X(HDD_DIR,           CONFIG, "RECOMP_HDD_DIR",           NULL, "emulated hard disk: partition images, saves, caches (default: the toolkit's save root)") \
    X(SAVE_SEED,         CONFIG, "RECOMP_SAVE_SEED",         NULL, "seed the save dir from this save before boot") \
    X(INPUT_SCRIPT,      CONFIG, "RECOMP_INPUT_SCRIPT",      NULL, "scripted pad: @preset, file or inline script") \
    X(INPUT_STRICT,      CONFIG, "RECOMP_INPUT_STRICT",      NULL, "1: a bad input script ends the run") \
    X(HOST_PAD,          CONFIG, "RECOMP_HOST_PAD",          NULL, "0/1: host gamepads in or out") \
    X(RUMBLE,            CONFIG, "RECOMP_RUMBLE",            NULL, "0: no rumble") \
    X(FPS_MODE,          CONFIG, "RECOMP_FPS_MODE",          NULL, "enhancements: fps.mode, lock30 only (lock60 and free are not available)") \
    X(GLOW,              CONFIG, "RECOMP_GLOW",              NULL, "enhancements: fx.glow, on|off (the mode-3 glow pass)") \
    X(GLOW_INTENSITY,    CONFIG, "RECOMP_GLOW_INTENSITY",    NULL, "enhancements: fx.glow_intensity, 0.0..2.0 (scales the glow layer)") \
    X(INPUT_TRACE,       TRACE, "input",           "RECOMP_INPUT_TRACE",       "pad handles and states") \
    X(UNIMPL_BUDGET,     TRACE, "unimpl_budget",   NULL,                       "=n: [UNIMPL] lines per address before only hits 10, 100, ... (3)") \
    X(APU_FAULT_BENCH,   DEBUG, "apu_fault_bench", "RECOMP_APU_FAULT_BENCH",   "=n: time n trapped APU accesses") \
    X(MEM_DUMP,          DEBUG, "mem_dump",        "RECOMP_MEM_DUMP",          "=va,bytes,prefix: guest memory dumps") \
    X(MEM_DUMP_EVERY,    DEBUG, "mem_dump_every",  "RECOMP_MEM_DUMP_EVERY",    "=s: mem_dump period, default 20") \
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
 * 2026-10-07). The toolkit's own default is the same; it is stated here so
 * this game's pinning does not depend on it. RECOMP_GUEST_CPUS=all is the
 * A/B.
 *
 * The DSOUND GP doorbell ack (apu_dsp_ack) was a game default until the
 * toolkit made `auto` its own default (chore/vanilla-cleanup): the doorbell
 * is GP scratch page 0 + 0x810, found from the GPSADDR table, which ends
 * the XDK DSOUND submit's spin at loc_00334325 (sub_003341BE). It was
 * 0x80A1C810, and reserving physical page 0 (upstream 423263b) moved it to
 * 0x80A20810. RECOMP_DEBUG=apu_dsp_ack=0 turns it off. */
#define RECOMP_ENV_GAME_DEFAULTS(D) \
    D(GUEST_CPUS, "one")

#endif /* RECOMP_ENV_GAME_H */
