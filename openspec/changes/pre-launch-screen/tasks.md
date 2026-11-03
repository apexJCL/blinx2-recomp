This change is the spike: its findings are `proposal.md` and `design.md`, and its only task is done. Phases P1 to P3 run later, each in its own toolkit worktree off `posix-host/portability` and a cat worktree, after the operator's go. They follow CLAUDE.md's workflow, and each gets its own review at merge. P1 writes its requirements (`specs/pre-launch-screen/spec.md`) before any code.

## 0. Spike

- [x] 0.1 Answer the tracker item's questions from the code (toolkit 2a27f0dc, cat 0017bd8a, the tracker item's draft): the boot-only keys per game (D1), the gate and the presenters (D2, D3), the rules (D4), persistence (D5), game-agnostic text (D6), the mod descriptors (D7) and Saves (D8). Verdict: go, in three phases.

## 1. P1: the gate (toolkit, then each game's one line)

- [ ] 1.1 Add the keys and their rows before any code reads them:
  - `menu.prelaunch` (bool) in `[menu]`, code default off, bound in `enhance_cfg.c`; `RECOMP_MENU_PRELAUNCH` in the `recomp_env.h` CONFIG tier;
  - `prelaunch_auto=<ms>` in the DEBUG tier (test only: press Start after `<ms>`);
  - rows in the toolkit config docs and in `cat/docs/env.md`. Bump that file's counts: "**Config** (112)" to 113, "Twenty-four of them belong to the toolkit's enhancements layer" to twenty-five with `RECOMP_MENU_PRELAUNCH` in the list, and "**Debug** (135)" to 136.
- [ ] 1.2 `recomp_env_any_tier(tier)`: true when any row of that tier is set, toolkit and game rows alike, walking the X-macro table. A ctest sets one toolkit and one game DEBUG key in turn.
- [ ] 1.3 `src/enhance/prelaunch.c`: `xbox_prelaunch_run(game_skip)`, `xbox_prelaunch_active()` and the skip rules of D4 (rule 5 through 1.2; rule 6 from `game_skip`; `prelaunch_auto` overrides rules 2, 3, 5 and 6). It logs one `[ENHANCE] menu.prelaunch=on|off|skip (<reason>)` line. A weak no-op stub covers builds without the layer and older pins.
- [ ] 1.4 The idle loop (D2): it opens the menu on the Start page, runs `enhance_actions_tick()` at about 60 Hz, ends on Start or on any menu close (after the unsaved-changes dialog), and stops itself. No poller outlives it. The button that pressed Start stays masked from the guest until released (D5).
- [ ] 1.5 `ENHANCE_ITEM_PREBOOT` and the apply pass: `system.language` (after the tracker item merges) and a new `storage.ram_cache` row. Check that nothing opens Z: before the gate. The log line `[ENHANCE] prelaunch applied: <keys>`. While the screen is up, the menu shows "applies at Start" on those rows.
- [ ] 1.6 `PAGE_START` and row safety (D6):
  - header, **Start** first and selected, "Show this screen at startup" (saved at once through `recomp_cfg_patch`), the pre-boot rows, then the restart rows;
  - the General page gets "Show the start screen at startup";
  - the `pre_guest` flag on items and mod rows. Unsafe rows (the entities and debug-menu actions, `camera.free`, guest pokes) are greyed out with "available in game" while `xbox_prelaunch_active()`.
- [ ] 1.7 D3D11: the optional `idle_present` backend hook, called from the ack loop while `xbox_prelaunch_active()`: `init()`, `pump()`, a clear to black, `ovl_present()` with no frame, `Present`. Add the window handshake (up or failed); the gate waits about 2 s, else `skip (no window)`. Nothing changes on SDL or Metal. GDI and headless skip, and TASKS gets a GDI follow-up.
- [ ] 1.8 ctests, with no window:
  - each skip rule and its log reason (rule 1 logs `skip (menu off)`), the env override, and `game_skip`;
  - the order: the pre-launch flag is set before the handshake wait, so `idle_present` can run during it;
  - the handshake: a hook that reports failure, and one that never reports, both end in `skip (no window)` within the timeout;
  - `prelaunch_auto` ends the gate, and the pre-boot apply pass calls the setters in order;
  - every registered row walked with the flag set: no unsafe set() runs;
  - the stub links.
- [ ] 1.9 Each active game (BLiNX 2, BLiNX 1, KUF) and the new-game template:
  - `xbox_prelaunch_run(game_skip);` after `recomp_dispatch_init()` and before `xbox_WatchdogStart()` (cat `src/main.c:1325`);
  - a small helper that builds `game_skip` from the game's own automation keys. For BLiNX 2: `RECOMP_INPUT_SCRIPT`, the `*_PROOF` keys and `walls_trace`. Each other game lists its own;
  - `menu.prelaunch = true` in `packaging/config.default.toml` (decision 1);
  - `RECOMP_MENU_PRELAUNCH=0` in `analysis/golden/golden.json`'s env, checked by `scripts/test_config_default.py` beside `RECOMP_MENU=0`;
  - the optional `game.toml` `[prelaunch] intro`;
  - check each game's `host_enhance_init` for its own boot-only keys and record them in D1.
- [ ] 1.10 The CLI:
  - one shared env builder that sets `RECOMP_MENU_PRELAUNCH=0` for every verb that starts the game (`bench`, `bench golden`, `bench_matrix`, `bench_hw`, `audio_check`, `frames`, `pacing`, `hudmap/runs.py`, ...), with a test that every launcher goes through it;
  - golden's stock table gets `menu.prelaunch` (off or any skip; on fails), and `--allow-enhance` takes `menu.prelaunch`;
  - for the A/B in 1.12: an evaluation-only `bench golden --env KEY=VALUE` if none exists, refused by `golden record`;
  - `config_defaults.PORT`, the new-game `config.default.toml` template, `test_config_defaults.py` and `manifest.TOOLKIT_ENHANCE_KEYS` get `menu.prelaunch`;
  - `uv run pytest tests` and ruff.
- [ ] 1.11 The guest clock (D2): check that nothing on the gate path reads a guest clock (the TSC origin is set at its first call, `guest_time.c:266`, and the kernel time queries). Trace the first reads of each clock in one run with the screen held 10 s. If any read comes before `xbe_entry_point()`, the gate resets those origins as it returns, with a ctest.
- [ ] 1.12 Gates:
  - the Mac build, `tests/posix_ctest.sh` (0 FAIL), and `sh notes/build-all.sh` with `TOOLKIT=`;
  - the goldens on Metal, on the PC (D3D11 native) and through `blinx2 bench golden` on the Deck, all unchanged. Each run logs `menu.prelaunch=off` or `skip`;
  - one A/B on the PC and the Deck: a golden scenario with `RECOMP_MENU=1` and `prelaunch_auto=3000` against the same scenario with `RECOMP_MENU=1` and no screen, as an evaluation run (D4): the `golden plan` env plus the overrides, `golden check --allow-enhance menu.enabled=on --allow-enhance menu.prelaunch=on` on each leg, and `golden diff` between the legs. **Pass:** the golden frames match, and the D3D11 path runs `idle_present` → Start → first flip unattended;
  - hand checks of the screen (ping the operator before any play window):
    - Metal on the Mac, quiet;
    - native Windows D3D11, windowed and fullscreen;
    - the Deck in Game Mode with the pad only.

    For each: change the language at Start, the game boots in it, the Start press does not reach the title, hiding the screen persists, and the General row brings it back.

## 2. P2: more keys at Start

- [ ] 2.1 Probe `display.aspect` at Start: re-set `nv2a_host_opts`, resize the window (SDL, D3D11), and check that the HUD layer and the movie mode read the value after the gate. **Pass:** the 16:9 golden scenario's frames match a cold start at 16:9. Then mark it `ENHANCE_ITEM_PREBOOT`.
- [ ] 2.2 `overlay.ui_scale` at Start: a re-bake entry in `nv2a_overlay` while the gate holds the draw. A ctest checks the atlas size per scale.
- [ ] 2.3 Saves (D6): while `xbox_prelaunch_active()`, the import swaps without the quit and reports "Saves imported". The preview says "the game starts with these saves". The busy check, the backup and the staged swap stay. Hand check on the Deck: import a Mac save at Start and play it.
- [ ] 2.4 Gates as in 1.12, with the goldens only where the change touches what the game executes.

## 3. P3: the backdrop, then the optional items

- [ ] 3.1 (Deliverable; the operator, 2026-11-03.) The XBE title image (`$$XTIMAGE`) as the backdrop: read from the player's dump at run time, never shipped or cached in a public tree. An image quad in the overlay lists, drawn on Metal and D3D11. Black when the section is missing or does not decode. A ctest decodes a synthetic XPR.

Items 3.2 and 3.3 are optional and each needs its own go.
- [ ] 3.2 "Restart to apply": a relaunch of the same exe with the same arguments, for `present.surface` and the env-only keys. The operator decides the scope first.
- [ ] 3.3 Restart-class mod toggles decided at Start: a mod API call to re-apply a toggle before the first guest hook, then a check per mod. No BLiNX mod needs it today.
- [ ] 3.4 (Follow-up, not this change.) Extend `RECOMP_MODS_DESCRIBE=json` to the toolkit's and the title's items, so the wizard can offer the language at build time (D7).
