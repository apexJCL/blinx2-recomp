## Why

Some settings only take effect when the game starts. The language is read once, in BLiNX 2's init (`sub_0005F960`). The menu already marks `display.aspect`, `present.surface` and `overlay.ui_scale` "applies at restart". Today a player who wants French or 16:9 must start the game, open the menu, change the value, save, quit and start again.

The operator asked on 2026-11-03 for a launcher-like start instead. The overlay menu opens before the guest starts. The player changes values, then presses Start. A "Show this screen at startup" option hides it next time.

This change is the spike. It answers the item's questions from the code and gives a go/no-go and a phase plan. It changes no runtime code.

## Verdict

**Go**, in three phases. The menu can run before the guest's first instruction on every GPU path:

- On macOS (Metal and the SDL renderer), the window is open and the overlay draws on the main thread before the guest thread starts.
- On Windows and the Deck (D3D11), the window is created by the backend on the `nv2a-ack` thread, at the first flip. The pre-launch screen needs a small "idle present" hook there.

The gate sits in the game's `host_main`, just before `xbox_WatchdogStart()` and `xbe_entry_point()`. By then the XBE, the kernel, the save paths and the ack thread are up, and no guest code has run.

## What Changes

The spike's findings (`design.md`):

- **D1, the boot-only settings:** a table per key and per game. It says which keys a gate before the guest can apply (language, RAM cache, aspect, overlay scale), which need a restart anyway (`present.surface`, env-only keys such as the backend), and which are already live.
- **D2, the gate:** `xbox_prelaunch_run(game_skip)` (toolkit, game-agnostic; the game passes its own skip reason). It opens the menu on a Start page, steps it through `enhance_actions_tick()` at 60 Hz on the waiting thread, and returns when the player presses Start. While the gate is closed, the backend draws only the overlay, on black.
- **D3, the presenters:** no change on the SDL and Metal hosts (their main loop already draws the overlay with no frame). For D3D11, a new optional backend hook, `idle_present`, runs on the ack thread while the gate is closed. Its window stays the game's window for the rest of the run. A handshake turns a failed window into `skip (no window)` within about 2 s. GDI and headless skip the screen.
- **D4, never blocking a script:** the screen shows only when every check passes: `menu.enabled`, `menu.prelaunch`, a GPU presenter with a live window, no DEBUG-tier key (one table walk, not a hand list), and no game skip reason (BLiNX 2's `RECOMP_INPUT_SCRIPT`, ...). `RECOMP_MENU_PRELAUNCH=0` skips it; every game's golden.json and every CLI launcher (one shared env builder) set it. A test-only `prelaunch_auto=<ms>` row presses Start, so the gates can automate the screen. Each run logs one `[ENHANCE] menu.prelaunch=` line.
- **D5, persistence:** `menu.prelaunch` (bool) in `[menu]`. The code default is off (stock). Every game's `config.default.toml` ships it on, as with `menu.enabled` (the operator, 2026-11-03). The Start page's "Show this screen at startup" row and the in-game menu's General row write it. No hold-to-show at boot.
- **D6, game-agnostic:** the toolkit owns the gate and the Start page. Rows that need the guest (mod actions, `camera.free`) declare it and are greyed out before the guest. A game adds one call in `main.c` and may add a line of text (`game.toml` `[prelaunch]`). The new-game template gets the call too.
- **D7, the mod descriptors:** this does not replace the JSON. The pre-launch screen is the player's launcher, so the planned external launcher is no longer needed for players. `RECOMP_MODS_DESCRIBE=json` stays the machine interface for the wizard and the CLI.
- **D8, Saves:** before the guest starts, an import needs no busy check and no quit. The Saves page imports, and the game then starts on the new saves.

## Phase plan

1. **P1, the gate (toolkit plus each game's one line):** the gate, D3D11 `idle_present` with its handshake, Start page, `menu.prelaunch`, the skip rules, the pins, `prelaunch_auto` and the log line. It applies `system.language` and `storage.ram_cache` at Start. Gates: ctests for the skip rules, the handshake and pre-guest row safety; a check that no guest clock is read on the gate path; the goldens unchanged plus one `prelaunch_auto` A/B; hand checks on Metal, native Windows D3D11 and the Deck.
2. **P2, more keys at Start:** `display.aspect` and `overlay.ui_scale` apply at Start, each after a probe. The Saves page imports without quitting.
3. **P3:** the XBE's own title image (`$$XTIMAGE`, read from the player's dump at run time, never shipped) as the backdrop, a deliverable (the operator, 2026-11-03). Optional, each after its own go: a "restart to apply" relaunch for the keys that stay restart-only, and restart-class mod toggles decided at Start.

## Capabilities

### New Capabilities
- None in this spike. P1 adds a `pre-launch-screen` capability with requirements.

### Modified Capabilities
- None.

## Impact

- Docs only: `openspec/changes/pre-launch-screen/`.
- P1 touches the toolkit (`src/enhance/`, `src/d3d/nv2a_pb_d3d11.c`, the backend table, `recomp_env.h`), each active game's `main.c` and `config.default.toml`, and `docs/env.md`. Each game's `analysis/golden/golden.json` and `scripts/test_config_default.py` pin `RECOMP_MENU_PRELAUNCH=0`. It also touches the CLI: one shared env builder sets `RECOMP_MENU_PRELAUNCH=0` for every launcher, golden's stock table gets the `menu.prelaunch` line, and `config_defaults.PORT`, the new-game template, `test_config_defaults.py` and `manifest.TOOLKIT_ENHANCE_KEYS` get the key.
- Rules kept:
  - menu ON by default, with the screen shipped on in `config.default.toml` like the menu (the operator, 2026-11-03);
  - goldens run with `RECOMP_MENU=0`, so the screen cannot show;
  - benches and scripts never block (D4);
  - Metal and D3D11 behave the same; the CPU rasteriser on Windows (GDI) skips the screen with a log line, and TASKS gets a follow-up.
- Related: the tracker item (the language, whose `ENHANCE_LIVE_RESTART` item this applies at Start), the tracker item (Saves), mod-settings D9 (the descriptor dump), the memory note on mods exposing settings for a later launcher.
