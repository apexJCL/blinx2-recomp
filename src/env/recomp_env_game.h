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
    X(INPUT_TRACE,       TRACE, "input",           "RECOMP_INPUT_TRACE",       "pad handles and states") \
    X(UNIMPL_BUDGET,     TRACE, "unimpl_budget",   NULL,                       "=n: [UNIMPL] lines per address before only hits 10, 100, ... (3)") \
    X(APU_FAULT_BENCH,   DEBUG, "apu_fault_bench", "RECOMP_APU_FAULT_BENCH",   "=n: time n trapped APU accesses") \
    X(MEM_DUMP,          DEBUG, "mem_dump",        "RECOMP_MEM_DUMP",          "=va,bytes,prefix: guest memory dumps") \
    X(MEM_DUMP_EVERY,    DEBUG, "mem_dump_every",  "RECOMP_MEM_DUMP_EVERY",    "=s: mem_dump period, default 20") \
    X(THREAD_DUMP,       DEBUG, "thread_dump",     "RECOMP_THREAD_DUMP",       "dump every thread: SIGUSR1 (macOS), touch thread_dump.trigger (Windows)")

/* Game keys whose values contain commas (see recomp_env.h). */
#define RECOMP_ENV_GAME_COMMA_KEYS "mem_dump",

/* Defaults this game gives toolkit keys, D(ID, "value"): used when neither
 * the key nor its old variable is set. The GP doorbell (GP scratch page 0 +
 * 0x810): the toolkit's APU frame thread clears it on every pass, which
 * ends the XDK DSOUND submit's spin at loc_00334325 (sub_003341BE) as the
 * GP program would. `auto` derives the page from the GPSADDR scatter-gather
 * table the title programs (toolkit src/apu/apu_dsp.c), so the address
 * follows the contiguous allocator: it was 0x80A1C810, and reserving
 * physical page 0 (upstream 423263b) moved it to 0x80A20810. A fixed
 * address can still be given instead. RECOMP_DEBUG=apu_dsp_ack=0 turns it
 * off. */
#define RECOMP_ENV_GAME_DEFAULTS(D) \
    D(APU_DSP_ACK, "auto")

#endif /* RECOMP_ENV_GAME_H */
