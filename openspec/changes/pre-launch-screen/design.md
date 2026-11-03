## Context

The operator asked on 2026-11-03 for the overlay menu to open before the game boots. The player sets the values that only apply at boot, then presses Start. A "don't show this at startup" option hides the screen next time.

This is a read-only spike. The code was read at toolkit `posix-host/portability` 2a27f0dc and cat `main` 0017bd8a. The language work was read from its draft change in `wt/language` (`language-setting`, not merged). Nothing was built or run.

Facts the design rests on:

- **Boot order** (cat `src/main.c`):
  - `main` / `WinMain` call `recomp_env_init()`, then `host_enhance_init()`, which calls `xbox_enhance_init()`. That reads every toolkit key into `nv2a_host_opts`, inits the mods, bakes the overlay atlas at `overlay.ui_scale` and arms the menu.
  - POSIX: `xbox_HostWindowMain(host_main)` then opens the SDL window on the main thread and starts `host_main` on the `guest-main` pthread. Windows: `host_main()` runs on the process main thread.
  - `host_main` loads the XBE, inits the memory layout (which starts the `nv2a-ack` thread), the APU, the kernel and the save paths. It then calls `xbe_entry_point()`.
- **Where the overlay draws:**
  - SDL and Metal (`fb_present_sdl.c`): the main loop presents whenever `nv2a_overlay_poll` reports a change, and with no frame it paints black under the overlay lists. So the menu already draws before the guest's first flip, if something steps it.
  - D3D11 (`nv2a_pb_d3d11.c`): `init()` creates the window, device and swap chain lazily, in `d3d11_flip`, on the `nv2a-ack` thread, and `pump()` drains that thread's messages at each flip. `ovl_present()` already draws over the whole back buffer when no frame was copied (`s_ovl_place` zero).
  - GDI (`fb_present.c`, the CPU backend on Windows): the window opens at the guest's first `AvSetDisplayMode`.
- **Who steps the menu:** the actions hook steps it, from the title's pad poll or from the flip tick (`enhance_actions_tick`, which reads the host pad itself when a port has not been polled for 100 ms). Before the guest neither runs.
- **Restart-class items** (`ENHANCE_LIVE_RESTART`): `set()` only records the value and the menu shows "applies at restart". A mod without `on_enable` toggles as `XBOX_MOD_RESTART`.

## Goals / Non-Goals

**Goals**
- List the settings that take effect only at boot, per game, and say which a pre-guest gate can apply.
- Say how the menu runs before the guest on each presenter, and what is behind it.
- Fit the rules: menu on by default, goldens at `RECOMP_MENU=0`, and no script or bench ever blocked.
- Say where "hide at startup" persists and how the player gets the screen back.
- A game-agnostic toolkit design, with a go/no-go and phases.

**Non-Goals**
- Runtime changes. P1 gets its own requirements when it starts.
- A separate launcher program (Go, a web view). The wizard stays a build tool (CLAUDE.md, wizard rules).
- Changing env-only keys (the backend, the game files and hdd paths, `RECOMP_AC97_READY`, the DSP JIT) from the screen. They are read once in `recomp_env_init()` and fixed before any window exists. They stay with `launch.env` and the wizard.

## D1. The settings that only apply at boot

"Read at" is where the value is fixed today. "At Start" says whether the gate (D2) can apply a change made on the screen, since no guest code has run by then.

### Toolkit keys (every game built with `XBOXRECOMP_ENHANCE`)

| Key | In the menu | Read at | At Start | Notes |
|---|---|---|---|---|
| `system.language` | yes, RESTART | the kernel answers `XC_LANGUAGE` on each query; the title reads it once in its init | **P1: yes** | The gate re-reads the key into the kernel's value before `xbe_entry_point`. It is the reason for this change. |
| `storage.ram_cache` | no | `xbox_enhance_init` → `xbox_RamCacheEnable`; the store fixes at its first use, the guest's first open on Z: | **P1: yes** | P1 adds a row (a "System" group on the Render page, or the General page). P1 confirms that nothing opens Z: before the gate. |
| `display.aspect` | yes, RESTART | `xbox_enhance_init` → `nv2a_host_opts` (the window width, the host pad of the 4:3 targets) | **P2: yes, after a probe** | No guest target exists yet. Re-setting the options and resizing the window (SDL `SDL_SetWindowSize`, D3D11 `SetWindowPos` plus `present_resize`) should be enough. The probe checks that the HUD layer and the movie mode read it later, not at init. |
| `overlay.ui_scale` | yes, RESTART | the atlas bake at the first `nv2a_overlay_arm`, in `xbox_enhance_init` | **P2: yes** | The gate owns the draw while it runs. It can pause the presents, re-bake, and resume. That needs a re-bake entry in `nv2a_overlay`; today the scale is only accepted before the first arm. |
| `present.surface` | yes, RESTART | D3D11 `init()` (the swap chain size), the CAMetalLayer | **no** | Under D2 the D3D11 swap chain already exists when the screen shows. Rebuilding it is possible, but it buys little: the auto value follows gamescope. It stays "applies at restart" (P3 relaunch). |
| `present.fullscreen` | yes, FLUSH | live | live | Already applies at once. |
| `render.scale`, `present.filter`, `present.pacing`, `display.overscan`, `display.movie`, `render.aniso`, the pack toggles | yes | live or flush | live | No change. |
| `menu.enabled` | no (Files import notes it) | `enhance_menu_start` | n/a | The screen is the menu, so it needs the menu on. |
| `menu.prelaunch` (new) | yes | the gate | n/a | D5. |
| `textures.pack` (the file), `present.shader_lib`, `present.shader_lines` | no | `xbox_enhance_init` | no | File paths that a player edits in TOML. Out of scope. |
| Mods: `XBOX_MOD_RESTART` toggles and settings with live class restart | yes | `xbox_mod_init`, inside `xbox_enhance_init` | **P3: maybe** | A mod's start state would be decided again before the guest. Its init has run, but no guest hook has fired. This needs a mod API call and a check per mod. Today no BLiNX 2 or BLiNX 1 mod has a restart toggle: all of them have `on_enable`. |
| Env-only keys (`RECOMP_PB_BACKEND`, `RECOMP_GAME_FILES`, `RECOMP_HDD_DIR`, `RECOMP_AC97_READY`, ...) | no | `recomp_env_init`, before any window | no | Non-goal. |

### Per game

| Game | Its own boot-only keys | Restart-class menu rows today | After P1 / P2 |
|---|---|---|---|
| BLiNX 2 | `fps.mode` (only `lock30` exists: no choice to offer), `fx.glow`, `fx.glow_intensity` (read in `host_enhance_init`, not in the menu; `glow_configure` is a store, so a Game row could apply at Start) | `display.aspect`, `present.surface`, `overlay.ui_scale`; `system.language` once the tracker item lands (en, ja, de, fr, es, it) | language and RAM cache at Start (P1); aspect and overlay scale at Start (P2); surface at restart |
| BLiNX 1 | none beyond the toolkit's (`draw_distance` is live) | the toolkit's three; `system.language` (en, ja, fr, es) | same |
| KUF and the others in the pool | none known; each game's `host_enhance_init` is checked when it adds the gate call (tasks 1.9) | the toolkit's three | same |

A title's own item can join with no new API: an `ENHANCE_LIVE_RESTART` item that is also safe to apply before the guest sets a new flag, `ENHANCE_ITEM_PREBOOT`, and gives a setter. Before the gate opens the setter applies the value. After the gate opens the item stays restart-class, as today. The menu shows "applies at Start" for such a row while the screen is up.

## D2. The gate

A toolkit call, `int xbox_prelaunch_run(const char *game_skip)` (new `src/enhance/prelaunch.c`, a no-op stub without the layer). `game_skip` is the game's own skip reason, or NULL (D4 rule 6). The game calls it from `host_main` after `recomp_dispatch_init()` and **before `xbox_WatchdogStart()`** (cat `src/main.c:1325`), so the watchdog cannot fire while the player sits on the screen. Only `cat_pad_early_init()` and `xbe_entry_point()` follow it, and no guest code has run. By then:

- the XBE certificate is read: the title name and id for the header and the Saves page;
- the save paths are set (`xbox_path_init`), so the Saves page works;
- on Windows the ack thread exists (D3).

The gate:

1. Decides whether to show (D4 rules 1 to 3, 5 and 6, which need no window). On off or skip it logs `[ENHANCE] menu.prelaunch=off|skip (<reason>)` and returns at once: one check, no wait.
2. Sets the pre-launch flag (`enhance_menu_set_prelaunch(1)`, read by `xbox_prelaunch_active()`), so the presenter starts drawing: on D3D11 this is what lets the ack loop call `idle_present` (D3). Only then, on D3D11, it waits for the window handshake: if `idle_present` has not reported a live window within about 2 s, or reports a failed one, the gate clears the flag, logs `skip (no window)` and returns, so a failed `init()` never leaves the game waiting behind no window. With the window up (at once on SDL and Metal) it logs `menu.prelaunch=on`, opens the menu with `enhance_menu_open(now)` on the Start page (D6), and wakes the presenter.
3. Loops on the calling thread at about 60 Hz: `enhance_actions_tick()`, then a 16 ms sleep. The tick already reads the host pad and keys when no title polls, and steps the menu under the menu-step lock. On SDL hosts the keyboard and pad events still arrive through the main thread's pump into the shared tables. On D3D11 they arrive through the window's `wnd_proc` on the ack thread (D3).
4. Ends when the menu closes with **Start**: the Start row, Start or A on that row, or Enter. Any other way of closing the menu also starts, since the game cannot sit behind a closed menu with nothing running. The menu's own unsaved-changes dialog runs first, as it does when the menu closes in play. Closing the window quits, as today.
5. Applies the pre-boot keys. It calls each `ENHANCE_ITEM_PREBOOT` setter with the value now in force, saved or session-only, and logs one `[ENHANCE] prelaunch applied: <keys>` line. It clears the flag and returns. The guest starts.

No guest thread, APU interrupt or vblank runs while the gate waits, so the screen costs no guest time. **That it moves no guest clock is not yet verified.** The guest TSC sets its origin at its first call (`xbox_ReadTimeStampCounter`, toolkit `src/kernel/guest_time.c:266`), and the kernel's time queries have origins of their own. If anything on the gate path (the menu, the overlay stats, the APU init, the presenter) reads one of them first, the guest would see the wait as elapsed time at its first read. P1 checks that nothing on the gate path reads a guest clock (tasks 1.11). If something does, the gate resets the origins as it returns. The APU is already up but idle, so the screen is silent.

The idle loop stops itself. No poller outlives the gate.

## D3. Presenters and what is behind the menu

| Host | Window before the guest | What draws | Change |
|---|---|---|---|
| macOS, Metal (`fb_present_metal.m`) | yes: the main thread opens it before `start_guest()` | the main loop: `fbm_present` with no frame paints black, then the overlay lists | none |
| macOS / Linux, SDL renderer (CPU backend) | yes | the main loop: `SDL_RenderClear` then `ovl_draw` over the whole output | none |
| Windows and the Deck, D3D11 | no: created at the first flip on `nv2a-ack` | new: the backend's optional `idle_present` hook, called by the ack loop while `xbox_prelaunch_active()`. It does `init()` (window, device, swap chain), `pump()`, a clear to black, `ovl_present()` with no frame, `Present`. After its first successful `Present` it sets a "window up" flag; if `init()` fails it sets "window failed". The gate waits on that handshake (D2 step 1). | small: one optional hook in the backend table, one branch in the ack loop, one handshake flag; one load when the gate is open |
| Windows, GDI (CPU backend) | no: at the first `AvSetDisplayMode` | — | skip with `menu.prelaunch=skip (no GPU presenter)`; follow-up in TASKS (the CPU path only has to build) |
| headless (`RECOMP_HEADLESS=1`, no display, null backend) | no | — | skip |

**Why the ack thread for D3D11.** A Win32 window receives its messages on the thread that created it. The D3D11 window pumps on `nv2a-ack` for the whole run. If the gate created it on the main thread, the game's flips would later pump on a thread that gets none of its messages. A second, short-lived launcher window was considered and rejected: it flashes between two windows, it loses fullscreen, and gamescope sees two surfaces. Creating the real window early through the hook keeps one window from the screen into play. It also means the first frame of the game draws into a window that already exists, which only moves `init()` earlier. The DXBC cache and the shader warm-up are unchanged.

The ack loop already runs before the guest. It acks vblanks and polls KickOff, and with no guest it has nothing to do. The hook adds one acquire load per pass when the gate is closed, and nothing in a golden run, because the gate never opens there.

**Behind the menu:** black in P1 and P2. The header names the game (`nv2a_overlay_set_game`, already set from the XBE or `xbox_HostWindowSetTitle`). P3 draws the XBE's own title image (`$$XTIMAGE`, an XPR in the player's dump, the one `[package] icon = "xbe"` already reads) as the backdrop; the operator chose this on 2026-11-03 as a real P3 deliverable. It is read at run time from the player's dump and never shipped. It needs an image quad in the overlay lists, drawn by both GPU presenters, and falls back to black when the section is missing or does not decode.

## D4. Rules: never block a script

The screen shows only if all of these hold:

1. `menu.enabled` is on. Goldens run with `RECOMP_MENU=0`, and dev trees have no `config.default.toml`, so the menu is off and the screen cannot show. Golden's stock table already demands `menu.enabled=off`.
2. `menu.prelaunch` is on (D5), or `RECOMP_MENU_PRELAUNCH=1`.
3. `RECOMP_MENU_PRELAUNCH` is not `0`. This is a new CONFIG-tier row bound to `menu.prelaunch`. It is a second guard: a bench config that turns the menu on for an overlay test must still not wait. Every launcher sets it (see "Pins" below).
4. A GPU presenter is up and, on D3D11, its window handshake succeeds (D3).
5. **No DEBUG-tier key is set**, checked through a new `recomp_env_any_tier(RECOMP_ENV_DEBUG)` helper that walks the X-macro table, toolkit and game rows alike. A hand list would miss keys: the debug tier holds the pad and keyboard scripts and live pads (`pad_script`, `pad_record`, `pad_live`, `pad_press`, `pad_quit`, `kbm_script`), the timed pokes (`opts_at`, `mod_set_at`), every capture and dump (`window_shot`, `fb_dump*`, `fb_window_dump_every`, `hud_capture*`, `d3d11_dump`, `metal_host_dump`, `tex_dump`, `audio_wav`), the determinism checks (`deterministic`, `state_hash`, `det_trace`) and `watchdog`. Any of them means a script or a developer drives the run. A new DEBUG key is covered with no change here. Besides the tier: `RECOMP_HEADLESS`, `RECOMP_WINDOW_QUIT_AFTER` and `RECOMP_MODS_DESCRIBE` (which exits before any window anyway).
6. **The game has no skip reason.** Some automation keys are game keys in the CONFIG tier: BLiNX 2's scripted pad `RECOMP_INPUT_SCRIPT` (cat `src/env/recomp_env_game.h:40`), its `*_PROOF` keys and `walls_trace`. The toolkit cannot know them, so the game passes its reason as `xbox_prelaunch_run(game_skip)`, for example `"RECOMP_INPUT_SCRIPT"`, or NULL. Each game builds it in one small helper beside the call (tasks 1.9).

Skipping is always safe: the run then behaves exactly as it does today.

`RECOMP_MENU_PRELAUNCH=1` overrides only rule 2. It is for testing the screen by hand. Rules 4 to 6 still apply.

**Automating the screen itself.** The menu's `menu_input` key is a trace, not an injector, so nothing can press Start today. P1 adds one test-only DEBUG row, `prelaunch_auto=<ms>`. It is itself the automation, so it overrides rules 2, 3, 5 and 6 (the scenario's own pad script still runs after Start); rules 1 and 4 still apply. It opens the screen and presses Start after `<ms>`. Windows and Proton gates use it to drive `idle_present` → Start → first flip with no hand on the pad. One A/B run compares a golden scenario with `RECOMP_MENU=1` and `prelaunch_auto=3000` against the same scenario with `RECOMP_MENU=1` and no screen (the closed menu changes no frame). **Pass:** the golden frames match (tasks 1.8, 1.12).

`blinx2 golden` and `bench golden` cannot run these legs as they are: golden.json pins `RECOMP_MENU=0` and the stock check demands `menu.enabled=off`. The A/B is an evaluation run instead:

- each leg runs the scenario with the env lines from `golden plan` and then the leg's overrides (`RECOMP_MENU=1`, and `RECOMP_DEBUG=...,prelaunch_auto=3000` in leg B). Later values win, so the overrides replace golden.json's `RECOMP_MENU=0`. `bench golden` gets an evaluation-only `--env KEY=VALUE` for this if it has none, and `golden record` refuses runs made with it;
- each leg is checked with `golden check --allow-enhance menu.enabled=on --allow-enhance menu.prelaunch=on --log SCEN=LOG SCEN=DIR`. That is golden's existing evaluation path: the stock check skips the allowed keys and notes the run. P1 adds `menu.prelaunch` to the keys `--allow-enhance` takes;
- then `golden diff` compares the two legs' dumps frame by frame, so the pass does not rest on the references alone.

The log line names the reason (`skip (menu off)` for rule 1, `skip (debug key pad_script)`, `skip (RECOMP_INPUT_SCRIPT)`, `skip (RECOMP_MENU_PRELAUNCH=0)`, `skip (no GPU presenter)`, `skip (no window)`, `off`). A golden run has `RECOMP_MENU=0`, so it logs `skip (menu off)` and nothing else. The golden check adds `("menu.prelaunch", ..., "off")` beside `menu.enabled`, where any `skip` counts as stock and `on` fails.

**Pins.** Every launcher states the key, not only the bench:

- **Goldens:** the menu is pinned per game in `analysis/golden/golden.json`'s env (`RECOMP_MENU=0`, checked by cat `scripts/test_config_default.py:165-183`). Each game's golden.json gains `RECOMP_MENU_PRELAUNCH=0`, and the same test checks it.
- **The CLI:** `bench`, `bench golden`, `bench_matrix`, `bench_hw`, `audio_check`, `frames`, `pacing`, hudmap (`hudmap/runs.py`) and every other verb that starts the game take their env from one shared builder, which sets `RECOMP_MENU_PRELAUNCH=0`. P1 adds the builder where a verb still builds its own env, with a test that every launcher goes through it.
- **Shipping it on (decision a):** `menu.prelaunch = true` goes in each game's `config.default.toml`, the CLI's `config_defaults.PORT` and the new-game `config.default.toml` template, with `test_config_defaults.py` updated. `manifest.TOOLKIT_ENHANCE_KEYS` gains `menu.prelaunch`.

## D5. Persistence and getting it back

- **The key:** `menu.prelaunch = true|false` in `[menu]`. The code default is `false` (stock, opt-in rule). Every game's `config.default.toml` ships `true` beside `enabled = true`. **Decided by the operator on 2026-11-03:** on by default for players, like the menu, while benches, goldens and scripts always skip (D4).
- **Hiding it:** the Start page has a toggle row "Show this screen at startup". Turning it off and starting saves only that key at once, through the same `recomp_cfg_patch` write Save uses, so a player who changed nothing else still gets their choice kept. The menu's other unsaved values follow the normal dialog.
- **Getting it back:**
  - the in-game menu's General page has the same row, "Show the start screen at startup", which applies at the next start;
  - `RECOMP_MENU_PRELAUNCH=1` in `launch.env` or the shell;
  - the player's `config/config.toml`.
- **No hold-to-show.** An earlier draft showed the screen once when the menu.open binding was held at boot. It is dropped. A hold check would have to wait for input before deciding, against D2 step 1's "one check, no wait". On D3D11 there is no window to take keys before the hook runs. The toolkit's bindings (F10, Guide+A, paddle1; `enhance_actions.c:2153`) are not reachable at boot on the Deck: Steam keeps Guide, and R4 → F10 needs a focused window. The General row and the env key cover getting the screen back.
- **Held buttons at Start.** The button that pressed Start (A, Start, Enter) is masked from the guest until it is released, so it does not also land on the title's first menu. It reuses the masking the menu already applies to the presses of its own chords.

## D6. Game-agnostic, and the Start page

- The toolkit owns:
  - the gate, the D3D11 hook, the key and env row, and the skip rules;
  - the Start page, a new `PAGE_START` shown only while the flag is set. Its rows: a header with the game's name; a **Start** action, first and selected; "Show this screen at startup"; then a short list of the settings that apply at Start, the `ENHANCE_ITEM_PREBOOT` rows plus the restart rows marked "applies at restart" so players see why. The toolbar shows every other page as usual, so Render, Saves, Mods and the game's page are all one press away.
- **Rows that need the guest.** Some rows act on guest state that does not exist yet: the entities and debug-menu mods' actions, `camera.free`, any row that pokes guest RAM or calls a guest function. Each item and mod row declares whether it is safe before the guest (a new `pre_guest` flag; the default is unsafe for actions and safe for plain values that only record a setting). While `xbox_prelaunch_active()`, the unsafe rows are greyed out with "available in game" and their set() is not called. A ctest walks every registered row with the flag set and checks that no unsafe set() runs.
- The game adds one line in `host_main` (`xbox_prelaunch_run(game_skip);` before `xbox_WatchdogStart()`), and the new-game template gets the same line. A toolkit without the gate gets a weak stub, guarded the way `ENHANCE_MENU_HELP` guards `.help`, so a game can add the call before its toolkit pin moves.
- Per-game text comes from `game.toml`: an optional `[prelaunch] intro = "..."` line under the header. The CLI passes it as it does the language list (D3, a CMake cache variable on one source). With no line, the screen shows only the game's name. The language list itself comes from the tracker item's `[system] languages`, with no second copy.

## D7. The mod descriptors (mod-settings D9) and the "later launcher"

The memory note from 2026-10-27 planned an external launcher fed by `RECOMP_MODS_DESCRIBE=json`. This change **covers the player's side of that plan**. The pre-launch screen is the launcher, in the game's own window, and it shows every page, the mods included. It works in SteamOS Game Mode, where no second program can open. No separate launcher needs to be filed.

The JSON stays. It is the machine interface for programs that edit `config.toml` without starting the game: the wizard's options page, `xbr` config tooling, the tracker's settings audits. A follow-up (not in these phases) could extend the dump to the toolkit's and the title's items, so the wizard can offer the language at build time.

## D8. Saves before the guest

The Saves page's import swaps the save trees, then quits (`recomp_quit_post("saves_import")`) so the game cannot overwrite the import from RAM. On GDI, which has no quit poster, the player has to quit by hand.

On the pre-launch screen no guest code has run, so no save handle is open and nothing is cached in RAM. P2 makes the import skip the quit when `xbox_prelaunch_active()`. It reports "Saves imported", stays on the screen, and the game then starts on the new saves. The busy check, the backup and the staged swap stay as they are. The import's preview names the difference ("the game starts with these saves" instead of "Import and quit"). Export needs no change.

This is the one clear user-visible win beyond the language: moving saves to the Deck no longer needs a restart.

## Risks

- **D3D11 window created early.** `init()` reads `present.surface`, `present.fullscreen` and the aspect when it runs. Under the gate it runs before the player's changes, which is why surface stays restart-only and aspect needs P2's resize. The DXBC cache, the shader warm-up and the window title all work from the ack thread as they do now. The P1 hand check covers native Windows and Proton.
- **Gamescope (the Deck in Game Mode)** shows the window as soon as it exists. Today that is the first frame, a black screen during boot, so nothing changes for the player.
- **Mods' init has run before the screen.** A mod that reads a key at init and has no `on_enable` would not see a change made on the screen. Its rows keep "applies at restart" until P3.
- **A frozen screen with no input device:** keyboard and mouse always work in a window, and closing the window quits.
- **A failed D3D11 window:** the handshake (D3) turns it into `skip (no window)` within about 2 s, and the game boots as today.
- **A launcher missed by the pins:** the shared env builder and its test (D4), plus rule 5's DEBUG-tier check, cover it twice.

## Decisions (the operator, 2026-11-03)

1. Every game ships `menu.prelaunch = true` in its `config.default.toml`: on by default for players, like the menu. Benches, goldens and scripts always skip.
2. The P3 title-image backdrop is in: a real P3 deliverable, read from the player's dump at run time and never shipped.
