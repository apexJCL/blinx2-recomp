## Why

BLiNX 2 keeps its developers' debug menu in the title's state machine
(title state 1: 1P_MISSION, 2P_MISSION, the VS modes, MINIGAME, ODEKAKE,
MODEL_EDIT, SHOP, GARAGE, MOVIE, ENDING, THEATER) and its SELECT A STAGE
list (state 0xB). A retail game never reaches them: only other debug states
lead there. Today an input script opens them with pokes (the `@stage1`
preset, `runs/enemy-respawn/go-5-1.txt`); a player cannot. The user wants
to jump to any stage by hand from the in-game overlay menu.

## What Changes

- **A new cat mod, `debug_menu`** (`src/debug_menu.c`, the pure part in
  `src/debug_menu_logic.c`), with a settings descriptor, default off:
  - `mods."debug_menu.enable"`: enum `off`/`on`, the mod's switch, live;
    env `RECOMP_DEBUG_MENU`;
  - a control `open` (host action `debug_menu.open`, unbound by default)
    and, on the mod's page of the overlay menu, an "Open the debug menu"
    row and a status row.
- Opening works only at the title's PRESS START (title state 0). The open
  request is queued from the menu's thread and done from the mod's frame
  callback on the guest thread: players-in-menu `[0xB22E3C]` = 1, player
  0's pad `[0xAE7A10]` = 0, cursors `[0x5EB630]` and `[0x5EB638]` = 0,
  state `[0x5EB620]` = 1. The team follows the stage picked, as in the
  game. Elsewhere the row's status says to go to the
  title first and the request only toasts that; the mod never forces a
  return to the title (no known safe path out of a stage or a menu).
- Entries that hang the port are skipped: while the debug menu
  shows, the mod moves the cursor past them in the direction it moved. Each
  one is filed as a follow-up.
- Off (the default and every golden): the init registers its callbacks
  dormant and writes nothing; `game.toml` `[golden] enhance_stock` lists
  `"mods.debug_menu.enable" = "off"`.

## Impact

- cat only: `src/debug_menu*.{c,h}`, `src/main.c` mod table,
  `CMakeLists.txt`, the env rows (`src/env/recomp_env_game.h`,
  `docs/env.md`), `packaging/config.default.toml` comments, `game.toml`,
  `scripts/test_debug_menu.py`; the input script's `key` step learns the
  arrows, Enter and Escape so a headless run can drive the overlay menu.
- No toolkit change: mod API v4 (`menu_add`, `on_frame`, `toast`, the
  descriptor) has all it needs.
