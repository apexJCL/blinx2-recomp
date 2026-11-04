## Why

The entity spikes (`entity-system-spike` design, parts B
and C on branches `spike/entity` 9770730 and `spike/enemy-respawn` 4da65a8)
mapped BLiNX 2's enemy list and proved, with a throwaway mod, that a copy of
an enemy spawned mid-stage moves, attacks, rewinds and dies, and that a type
poke before the stage loads changes every enemy of that type. They also
found the traps: the spawn leaks a pool slot when it refuses, a spawn made
during or before a rewind is silently undone, ids stop at 0xFF, and the 34
cap is fixed. Today a mod that wants enemies has to repeat that knowledge
and those raw guest calls. The tracker item asks for one game-level API that
does it once, with the guards, and a mod that puts it in the menu.

## What Changes

- **Toolkit, mod API v6** (game-agnostic; one toolkit branch):
  - `guest_call`: call a lifted guest function by VA from a hook or an
    `on_frame` callback, with every guest register (`g_ebp`, `g_seh_ebp`,
    the x87 and SSE state included) saved and put back;
  - `guest_alloc`: a block of guest memory the guest heap never hands out,
    owned by the mod for the rest of the run.
- **cat, the entity API** (`src/ent_api.{c,h}`, the pure part in
  `src/ent_api_logic.{c,h}`): a C API for cat's own mods:
  - list and read the live enemies (host copies, read with `memcpy`);
  - spawn a copy of a listed enemy or of a stage's placement record, at a
    chosen place, run on the guest thread in the pre hook of the enemy
    update `sub_0004E700`, from placement records in API-owned guest memory
    kept until the area is set up again;
  - kill through the game's hit path `sub_00050800`;
  - type overrides (class 1's variant hp, the one type table known),
    applied before the stage's placements load and undone the same way;
  - the guards: no spawn or kill while `stage_play_mode` `0xAE46EC` is not
    0 (time control, among others), the cap and a class allowlist checked
    before the spawn is called, a liveness check every frame.
- **cat, the `entities` mod** (`src/entities_mod.c`): the API's owner and
  its face in the menu. Settings `enable` (off by default) and `hp_scale`,
  controls `spawn` and `kill` (unbound), a Status row. A debug-tier proof
  driver for the live runs.
- **Two permanent `[mods] hook_functions` slots**: `0x0004E700`
  (`ent_enemy_update_all`) and `0x000606F0` (`stage_area_setup`). They
  change gen, so this change takes goldens.

## What stays stock

- The mod defaults off. Off, it registers its hooks dormant and reads or
  writes nothing; stock runs log `[ENHANCE] mods=none`, and `game.toml`
  `[golden] enhance_stock` gains `"mods.entities.enable" = "off"`.
- The two hook slots run the function unchanged when no hook is live. The
  goldens are expected to pass unchanged; they run because gen changes.
- The cap stays 34 (C3). Raising it is not in this change.

## Impact

- Toolkit (`posix-host/portability`): `src/enhance/mod.{c,h}` (API v6),
  the register save shared with `kernel_hal.c`, a ctest, `docs/runtime/config.md`.
- cat: `src/ent_api*`, `src/entities_mod.c`, `src/main.c` mod table,
  `CMakeLists.txt`, `game.toml` (`[mods]`, `enhance_stock`), regenerated
  gen and `config/hook_functions.json`, env rows (`recomp_env_game.h`,
  `docs/env.md`), commented keys in `packaging/config.default.toml`,
  `config/symbols.toml` for any address the implementation names,
  `scripts/test_entities.py`.
- Later users: the engine bridge's runtime inspector (engine-bridge
  assessment, [2]) can read the same list; a BLiNX 1 port needs its own
  layouts behind the same calls (spike part B, BLiNX 1 table).
