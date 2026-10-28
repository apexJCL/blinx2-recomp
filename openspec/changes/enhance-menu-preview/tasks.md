## Context

Phases of design.md "Migration Plan" as re-split in R5 (2026-10-21), one worktree set per phase
(`wt/<phase>/{cat,xboxrecomp,xboxrecomp-cli}`), one agent at a time.
Toolkit branches off `posix-host/portability`, CLI off `main`, cat off
`main`. Mac builds with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`;
Mac runs headless with `SDL_AUDIODRIVER=dummy` except the window-shot
checks, which open a window and no sound. Frame dumps and shots go to
`xbox-recomp/runs/enhmenu/`, never inside a worktree. Proton runs are on
the Deck (it replaced the Linux/Proton host on 2026-10-16). They wait for the
orchestrator's slot and take the Deck's flock (`blinx2 bench` takes it
itself).

## 0. Prerequisite

- [x] 0.1 The tracker item's `fix/hud-pack-text` (CLI 4ef7cd4 `enhance/xpr.py`, cat 1e5128f `lng_us` patterns) is reviewed and merged on its own; phases 1 and 7 rebase on it. Nothing of it is redone here.

## 1. Toolkit: live plumbing (D1, D2, D2b, D6 `textures.font` / `textures.text`)

- [x] 1.1 `nv2a_backend_common.{c,h}`: `nv2a_host_opts_request(o, mask)`, `nv2a_host_opts_apply()`, `nv2a_host_opts_gen()`; the pending struct under a mutex, one atomic pending flag read at the flip.
- [x] 1.2 Metal and D3D11 `on_flip`: call `apply` first; on `NV2A_OPT_SCALE` drop every render target (Metal with its write-back) and every texture entry; on `NV2A_OPT_PACK` bump the texture generation. Null and CPU backends call `apply` and re-log the "ignored" line on a scale change.
- [x] 1.3 `tex_bind` in both backends: `TexEntry.pack_gen`; a stale generation re-uploads like a changed hash. Same text in both files.
- [x] 1.4 `nv2a_tex_pack.{c,h}`: `set_enabled`, `set_kind_enabled`, the kind mask in `find`, `nv2a_tex_pack_gen()`, v2 reader (kind bits 0-1 art/FONT/TEXT, bit 4 `XRTP_FLAG_BC3`, other bits refused; a BC3 entry's byte count is the block count times 16 and is bounds-checked like texels), `entry->kind`, `entry->bc3`, per-kind counts for the log line.
- [x] 1.4a BC3 upload in both `tex_upload`s: a BC3 entry creates the host texture in `DXGI_FORMAT_BC3_UNORM` / `MTLPixelFormatBC3_RGBA` with block-row pitch and uploads the pack bytes as they are; the sampler and UVs are unchanged. The same text in both files.
- [x] 1.4b CLI (same phase, D13): `pack.py` writes v2 with the kind flags and `XRTP_FLAG_BC3`; `enhance/bc3.py`, a deterministic integer DXT5 encoder; `hud.py` assigns kinds (atlas FONT, `MIXF`/`XPR0` and `[enhance.hud] text` patterns TEXT, else art), a per-kind scale and BC3 choice, `[enhance.hud] languages` selection; `hud-pack.toml` gains per-kind counts and sizes. Tests: a BC3 block vector shared with `tests/tex_pack`; the kinds of a synthetic tree; `--list` shows kind and language.
- [x] 1.5 Miss ring: `nv2a_tex_pack_miss(hash, w, h, color, levels)` called from both `tex_upload`s only when a pack is loaded; 64 distinct entries with counts and the candidate/other flag; `RECOMP_TRACE=tex_pack` prints it every 600 flips; `nv2a_tex_pack_misses(out, n)` for the menu.
- [x] 1.6 `recomp_env.h`: `TEXTURES_FONT` and `TEXTURES_TEXT` rows; `enhance.c` reads both and applies them to the pack's kinds; the pack log line gains the per-kind counts, scales, the bc3 count and `textures.font=.. textures.text=..` when a pack is loaded (`ENHANCE_PACK_RE` still reads the path: it stops at the first space).
- [x] 1.7 ctests: `tests/host_opts_live` (request from another thread, apply at a fake flip, mask, generation), `tests/tex_pack` v2 cases (kind flags accepted, bit 2 refused, kind off = miss, a BC3 entry's byte count and the shared block vector, miss ring distinct and counted). Mac build and run; `tests/enhance_cfg` still 222 checks plus the new log lines.
- [x] 1.8 Docs: `docs/formats/texture-pack.md` v2 section (kinds, BC3, per-entry scale); `docs/runtime/enhance-config.md` `textures.font` and `textures.text` rows, the pack line, the `tex_pack` trace.
- [x] 1.9 Mac: stock Metal goldens unchanged (`blinx2 golden run --backend metal`), `textures.pack=none` in the log. `@stage1` with a v2 pack built from the branch's set (art 4x, text 2x BC3): the Mission Objectives title and lines come from the pack (sharp, dumped at that flip), the remaining misses listed with sizes and formats (`runs/enhmenu/misses-metal.txt`), the pack size recorded.

## 2. Configuration layering (P1): `config.default.toml` + `config.toml`, before the menu

- [x] 2.1 (Landed as its own change, `archive/2026-10-17-config-layering`, the tracker item.) Its own openspec change, landed before phase 3: `enhance_cfg_init` reads `config.default.toml` then the `config.toml` files, env on top, differences-only Save, automatic rename of an existing `enhance.toml` with one line; `RECOMP_CONFIG` with `RECOMP_ENHANCE_CONFIG` as the row's `LEGACY` name; launchers (SteamOS, Windows, macOS) stop copying the template and rename the user's file once; `blinx2 package` stages `config.default.toml` and `--hud-pack` writes into it; `packaging.md` §6, README, `enhance-config.md` → `config.md`, `docs/env.md`; `golden.json` pins `RECOMP_CONFIG=none`. ctest `enhance_cfg` cases for the two-file layering, the rename and differences-only writes. Enhancement and mod keys only: no `launch.env` row moves.
- [x] 2.2 Mac: stock Metal goldens unchanged with `RECOMP_CONFIG=none` (and once with the legacy `RECOMP_ENHANCE_CONFIG=none`); a developer `config/config.toml` with `scale = 2` is read over the build's `config.default.toml`; an old `enhance.toml` is renamed once with one line.

## 3. Toolkit: actions, overlay, live switching, menu (R1-R10; D3, D4, D5, D8)

Re-split on 2026-10-21 (design R5) and again on 2026-10-22.
The 2026-10-22 changes are:

- microui, the TrueType font and three geometry renderers replace the
  8x8 bitmap panel (R7, R8), so 3B is rewritten;
- new phases 3E (font and theme), 3F (mouse and cursor, R9) and 3G
  (the Save states page, R4);
- Guide + A and modifier chords in 3A (R10, R3 rule 7);
- SDL3 names throughout;
- no pause hook.

Round 2 (the review of `14f041d` and the user's answers, 2026-10-22)
adds:

- the tick's own host read (3A);
- Atkinson Hyperlegible, the README licence rows and the audit
  allow-list (3B.1);
- the exact env and doc rows per phase (3B, 3E, 3F, 3G);
- the pad-press cursor hide, the mouse close mask and capture on click
  (3F);
- the Mouse group on Controls (3D.3);
- the export folder (3G);
- the save-states `tasks.md` edit, made on this branch;
- 3B re-estimated at 4.25 days.

**Env and doc rows, the rule for every phase below.**

- **A key with an environment variable** gets three rows: an X-macro
  row in the `RECOMP_ENV_ENHANCE_KEYS` block of `recomp_env.h` (CONFIG
  tier), a row in the toolkit `docs/runtime/config.md` and README env
  table, and a row in cat's `docs/env.md` (5.4).
- **A file-only key** gets the `config.md` row and the `docs/env.md`
  row, with "none" in the Env column. It gets no `recomp_env.h` row.
  This follows the `[input]` precedent, where only the two switches
  have variables.
- **Every code default** is off or stock.

Estimates are in agent-days and include each phase's own gates. The
total for 3A to 6 is about 19 days (19.5 with phase 9), up from 17 at `14f041d` and 11.5 on 2026-10-21.

- **Development:** 3A, 3B and 3C may run in parallel, each in its own
  toolkit worktree. 3E may start once 3B has merged.
- **Merges:** in the order 3A, 3B, 3C, 3D, 3E, 3F, 3G, each rebased on
  the previous merge. They share `enhance.c`, `recomp_env.h`, `mod.h`,
  `fb_present_sdl.c`, `nv2a_pb_d3d11.c`, the window procedures and the
  `fbm_present` signature (R5). 3G also waits for save-states phase 4 and its 5.2.
- **Gates for every phase** (CLAUDE.md), before its merge:
  - the Mac build, the POSIX ctests and stock Metal goldens;
  - `blinx2 bench golden` on D3D11 under Proton on the Deck;
  - a Deck smoke run of the installed build;
  - the review.
- **Extra gates for 3B, 3E and 3F** (R5):
  - Metal and SDL-renderer window shots compared with the CPU
    reference raster of the same draw list;
  - a D3D11 host screenshot on the Deck, checked by eye;
  - an `fb_dump` with the menu open equal to one taken closed.

### 3A. Host actions (R3, R10), 2.5 days

- [x] 3A.1 `mod.h` glue section: `struct xbox_host_pad` and `xbox_enhance_pad_filter(port, host, st)`, beside `xbox_mod_input_captured`. It returns at its first test when disarmed. `input_core.c` calls it at the end of `xbox_InputGetState` with the host state read before the keyboard and script merge (the USB path: b3, ssx3, jsrf, spartan, kuf). `tests/input_keyboard` gains a filter case (rewrite and disarmed no-op). *Done in `tests/input_actions` instead: `input_keyboard` does not link `input_core.c`.*
- [x] 3A.1c cat glue (cat worktree, same phase): `src/pad_input.c` `cat_pad_get_state` fills `xbox_host_pad` from its backend read before merging `RECOMP_INPUT_SCRIPT` and the keyboard and mouse. It calls the filter on the merged state converted to `XBOX_INPUT_STATE` and writes the result back into the 18-byte gamepad. `scripts/test_*` case if the conversion is testable from Python, else a toolkit-side unit test of the conversion helper. *Done as `src/pad_pack.h` and `scripts/test_pad_pack.py`.*
- [x] 3A.2 `input_backend.h`: `host_extra`. The SDL3 gamepad backend routes `SDL_GAMEPAD_BUTTON_GUIDE` (already in the table as `XBOX_SDL_BUTTON_GUIDE`, unmapped to the guest) and reads `SDL_GAMEPAD_BUTTON_MISC1`, `RIGHT_PADDLE1`, `LEFT_PADDLE1`, `RIGHT_PADDLE2`, `LEFT_PADDLE2` and `TOUCHPAD` (15..20) with `SDL_GetGamepadButton` in a second loop (`XBOX_SDL_BUTTON_COUNT` stays 15 for the guest map). The XInput backend reads guide through `XInputGetStateEx` (ordinal 100, resolved by `GetProcAddress`, absent means 0). A new `xbox_input_backend_read_host(port, &host)` reads the guest buttons and `host_extra` off the poll thread: XInput through `XInputGetStateEx`/`XInputGetState` (thread safe), SDL3 through `SDL_GetGamepadButton` (SDL's joystick lock; the SDL main thread keeps pumping in the present loop). It publishes the result to the backend's atomic snapshot and clears it when no pad is open (R3, review F1). `input_names.c` gains the host-only names.
- [x] 3A.3 `src/enhance/enhance_actions.{c,h}`: the registry (64 actions), the binding parser (key with modifiers; `+` chord with `@ms`; `padN:` prefix; host-only singles; modifier chords such as `guide+a`), the R3 refusal rules with one warning each, the effective key map for rule 2 (compiled-in `xbox_key_map`, `[input.bindings]`, `walk_key`, `mouse_release_key`, modifiers included), hold timers, chord consumption in `*st`, rule 7 (modifier first, the guest member masked from its press until its physical release, a member pressed before the modifier passes and does not complete), a mask-until-release for the button that closed the menu, `[input] chord_delay_ms` (default 0), atomic fire counters, `enhance_actions_tick()` from the flip when the last poll is older than 100 ms (keys, host-only buttons and modifier chords, through its own `xbox_input_backend_read_host` call, only when armed; a tick fire marks the guest member consumed for the next poll). Arming by feature keys only (rule 6), the startup line `[ENHANCE] actions hook=off|on (<keys>)`, and `[ACTION] <name> via <binding>` on every fire, limited to 10 lines a second.
- [x] 3A.4 `[input.actions]` read by `enhance.c`. The R1 setters for `input.*` (mouse and stick feel, `walk_key`, `mouse_capture` on the window thread). The toolkit actions are `menu.open` (defaults `F10` and `guide+a`; until 3D it only logs), `overlay.stats` (no default; until 3B it only logs) and `shot.window`. `[input.bindings]` and `[input.actions]` are rebuilt live by a pointer swap on the poll thread. `enhance_input_init` stops rewriting the live table in place.
- [x] 3A.5 Mod API v2 (`XBOX_MOD_API_VERSION 2`, fields appended): `action_register`, `action_pressed`, `action_down`, `toast` (a log line until 3B). A v1 mod still loads. *Also `actions_arm(key)`, so a mod's enable key arms the hook (rule 6).*
- [x] 3A.6 Rows: `input.chord_delay_ms` gets an `INPUT_CHORD_DELAY_MS` row in `recomp_env.h` and a `config.md` row. `[input.actions]` is file-only and gets a `config.md` row. `docs/env.md` gets the rows in 5.4.
- [x] 3A.7 ctest `input_actions`:
  - a chord with a hold fires once, and a release before the hold fires nothing;
  - the consumed buttons are reported released until the physical release;
  - `guide+a` fires on A's press with Guide held, and A is never seen by the guest, also when Guide is released first;
  - A pressed before Guide passes and does not fire;
  - the button that closed the menu stays masked until release;
  - with no Guide from the backend, A passes unchanged;
  - a single guest button is refused, and so is a key in the effective map (`[input.bindings]`, `walk_key`, a default Ctrl modifier);
  - `chord_delay_ms` hides a chord completed inside the window;
  - a `RECOMP_INPUT_SCRIPT` pad never fires, while a kbm-script key does;
  - disarmed (`RECOMP_CONFIG=none`, a mod registered) logs `hook=off` and fires nothing;
  - a paddle single fires;
  - `guide+a` fires from the flip tick with no guest poll at all: a fake backend whose `read_host` reports Guide then Guide+A, with no `xbox_InputGetState` call, fires once, and the next poll masks A until release;
  - with no pad open, the tick clears the snapshot, so a modifier chord held before the pad went away does not complete;
  - a v1 mod table registers;
  - a live rebuild during a polling thread (TSan build when available).
- [x] 3A.8 Docs: `docs/runtime/config.md` `[input.actions]` section (grammar, rules 1 to 7, defaults, the per-host Guide table of R10 with each fallback, the Game Bar and macOS Home settings, the Deck and Steam Input paragraph); `src/input/README.md` hook and `host_extra` paragraphs.
- [x] 3A.9 Mac with a real pad (Xbox and DualSense; the user passed it 2026-10-26 with an Xbox One S and an 8BitDo Ultimate 2 in place of the DualSense), in BLiNX 2 through the cat glue:
  - F10, `guide+a` and `back+lthumb@400` log `menu.open`;
  - with `guide+a`, `RECOMP_TRACE=input` shows that A never reaches `cat_pad_get_state`'s output;
  - record whether macOS passes Home through, with the System Settings > Game Controllers state, in the phase notes and `config.md`;
  - a paddle or the touchpad fires a bound action;
  - from the moment both chord buttons are down, `cat_pad_get_state` reports neither, and a lone START still pauses;
  - the same chord check in one USB-path game (b3) through `xbox_InputGetState`.

  Then the phase gates.

### 3B. Overlay core, renderers and stats (R2, R7, R8), 4.25 days

The review's F13 re-estimate, up from 3 days. If the D3D11 renderer cannot be verified in this phase's Deck gate, it splits into 3B2 (0.75 day, verified in phase 6) with the same total.


- [x] 3B.1 Vendoring: `third_party/microui/` (microui.c and microui.h unmodified, `VERSION`), `third_party/stb/` (`stb_truetype.h`, `stb_image.h`), `third_party/fonts/atkinson-hyperlegible/` (Atkinson Hyperlegible Regular and Bold static TTFs, committed unmodified, with `OFL.txt`; the user, 2026-10-22). Licence files: `LICENSES/MIT-microui.txt`, `LICENSES/MIT-stb.txt`, `LICENSES/OFL-1.1-atkinson-hyperlegible.txt`, plus `NOTICE` entries and `LICENSES/README.md` rows. The toolkit `README.md` "License" table gets three rows: microui (MIT), stb (MIT or public domain) and Atkinson Hyperlegible (SIL OFL 1.1). A CMake step embeds the TTFs as a C array. Gate: the embedded fonts stay under 0.7 MB. Everything compiles only under `XBOXRECOMP_ENHANCE`, with relaxed warnings for the vendored files only. Audits:
  - Toolkit fork pushes: `notes/public-toolkit-map/round.py`'s tree-delta binary check and `README-rounds.txt` allow-list `third_party/fonts/atkinson-hyperlegible/*.ttf`. The orchestrator makes this change; the phase leaves it a note in `notes/public-toolkit-map/`.
  - cat's public export: unchanged, since the TTFs are toolkit files.
  - The CLI's `scripts/audit-public.sh`: not touched. The TTFs never enter `xboxrecomp-cli`, so no allow-list entry goes there.
- [x] 3B.2 `src/kernel/nv2a_overlay.{c,h}`: four layers (`STATS`, `TOAST`, `MENU`, `CURSOR`), a triple buffer per layer holding an `nv2a_ovl_list` in fixed arrays allocated at arm time (R7 caps), published by one atomic exchange; `visible` mask; the placement word written by the presenter; image slots with `gen`; `nv2a_overlay_toast` pushing to an 8-line lock-free ring that the presenting thread composes; the menu-step try-lock (R7 threads).
- [x] 3B.3 `src/kernel/nv2a_overlay_ui.c`: the microui context per writer, the text width and height callbacks over the atlas, the converter from microui commands to the draw list (rects on the white texel, rounded rects with the 1-pixel feather, glyph quads, images, the arrow and dot cursors, scissor commands, the overflow cut with one log line), and the code-default theme tokens and `ui_scale` of R8.
- [x] 3B.4 The font at arm time: stb_truetype bakes Regular at the R8 sizes for the first output height into a coverage atlas with 2x horizontal oversampling, published with `atlas_gen`; the `[OVERLAY] atlas <w>x<h> <ms> ms` line. (Rebakes, SemiBold, the Unicode range and the theme keys are 3E.)
- [x] 3B.5 Renderers:
  - Metal: an MSL pipeline compiled like `s_blit_msl`, per-layer vertex and index `MTLBuffer`s, `setScissorRect`, premultiplied blending, drawn after the frame triangle; `fbm_present` takes the layers argument (NULL when `visible == 0`).
  - D3D11: a shader pair through `D3DCompile`, dynamic buffers, blend and scissor rasteriser states, drawn after `present_blit` or the copy **and after `dump_frame()`**, with its own viewport and target on the stock copy path and `s_sc_init = 0`, and the touched state restored. When nothing was copied this present (`s_drawn` NULL, or no back buffer bound yet), it clears the back buffer to black before the overlay (review F9).
  - SDL3 renderer: `SDL_RenderGeometryRaw` per command with `SDL_SetRenderClipRect`, `SDL_BLENDMODE_BLEND_PREMULTIPLIED` (review F10) and the cached `SDL_FColor` array, drawn after `SDL_RenderTexture(frame)` and before `shot_save`; a moved `gen` sets `dirty` and posts the frame event.
  - Nothing runs when `visible == 0`. Record in TASKS (backends agree) that the D3D11 overlay refreshes only on guest flips (F-9), that D3D11 has no `RECOMP_WINDOW_SHOT` (F-10), and that the CPU GDI window has no overlay (F-2).
- [x] 3B.6 `src/kernel/nv2a_overlay_ref.c`: the CPU reference rasteriser (fixed-point edges, top-left rule, bilinear atlas, premultiplied blend, scissor), built for the ctests.
- [x] 3B.7 `src/kernel/nv2a_stats.{c,h}`: relaxed atomic counters, each site gated on the relaxed flag `nv2a_stats_on` (set while the strip, the Stats page or `RECOMP_TITLE_STATS` is shown) (flips, presents, draws, texture uploads, pack hits and misses) and a 128-entry frame-ms ring written at the flip. `xbox_title_format` reads the same counters.
- [x] 3B.8 The STATS layer composed on the presenting thread at 2 Hz and the TOAST layer, both with the R8 layout at the code-default theme. The `overlay.stats` key (bool, default off), its `OVERLAY_STATS` row (`RECOMP_OVERLAY_STATS`, CONFIG tier) in the `RECOMP_ENV_ENHANCE_KEYS` block of `recomp_env.h`, and its `config.md` and README env-table rows, the `[ENHANCE] overlay.stats=off|on` line, and the `overlay.stats` action toggling it.
- [x] 3B.9 ctest `overlay`:
  - the draw list of fixed test frames (checksum of vertices, indices and commands), and layout facts at 720 and 2160 lines;
  - the reference raster's checksum;
  - publish and hide per layer, `gen`, the `visible` mask, toast expiry;
  - two writer threads on two layers plus a reader thread, with no torn list (each list carries a checksum the reader verifies);
  - the menu-step try-lock between two threads;
  - the overflow cut;
  - stats sites inert with the flag clear;
  - disarmed: no context, no atlas, no allocation.
- [x] 3B.10 Mac: the Metal layer window and the SDL renderer (CPU backend). A `RECOMP_WINDOW_SHOT` with the strip on shows it and matches the reference raster within tolerance, and the `fb_dump` of the same flip has no strip. Flips/s with the strip on is within 5% of off, and with it off equal to before the phase (`runs/enhmenu/stats-metal.txt`). Then the phase gates.

### 3C. Live-switch completion (R1), 1.5 days

- [x] 3C.1 `NV2A_OPT_ANISO`, `NV2A_OPT_MOVIE` and `NV2A_OPT_OVERSCAN` mask bits, applied at the flip in both GPU backends (the overscan refusal with a wide aspect kept). Null and CPU backends accept them. *Movie and overscan too: aniso clamps to 0 or 2..16, a movie mode past `fill` and an overscan with a wide aspect are refused with one line each; the CPU and null backends re-log overscan as ignored.*
- [x] 3C.2 `fb_present_sdl.c` reads `present.filter` at each present (`SDL_SetTextureScaleMode` on change) and passes it to `fbm_present`. *The SDL renderer path sets the scale mode and the logical presentation (integer or letterbox) on a gen change; the Metal layer already read the filter per present.*
- [x] 3C.3 `present.fullscreen` live. SDL: `SDL_SetWindowFullscreen` on the SDL main thread when the host-opts gen moves. D3D11 (in v1 scope, the user, 2026-10-22): a style swap with `SetWindowPos` on the window thread, then `ResizeBuffers` at the next flip. If phase 6 shows a resize race, the menu says "applies at restart" on D3D11 and TASKS records the gap. *SDL: macOS fullscreen Spaces are off only when a live switch is armed (fullscreen configured, the overlay armed or `opts_at` set; the environment still wins), because a Spaces toggle in an app that is not frontmost does nothing yet reports success. Stock runs keep Spaces. D3D11: `fullscreen_switch` in `on_flip` on the walker thread, which owns the window; `WM_SIZE` records the size and `present_resize` runs at the next flip.*
- [x] 3C.4 Setter for `present.pacing` (`xbox_PacingSetMode`). The input setters are in 3A.4. *`xbox_enhance_set_pacing` in `enhance.c`.*
- [x] 3C.5 ctest `host_opts_live` cases for the new bits. Mac Metal checks: aniso 1 to 16 and back, overscan on and off, filter, fullscreen on and off, each within two flips. Then the phase gates. *Plus the `opts_at` debug key, which makes the menu's requests at given flips (`runs/overlay-3c/live/`).*

### 3D. Menu (D5, R4, R8, D8), 3 days

- [x] 3D.1 `src/enhance/enhance_menu.{c,h}`: the item table with each item's live class, `enhance_menu_add`, the pure state machine, and `enhance_menu_step` (input, then a microui frame, then publish, under the menu-step lock). Widgets: row, toggle pill, choice `< value >`, slider, info row, confirm row, scrolled list, tab strip. The R8 menu layout with the code-default theme. Pages: Render, Pack, Game, Mods, Stats, Controls, Debug, Save, Reset (Save states is 3G). Opened by the `menu.open` action. While open: a neutral pad, frozen packet number and repeat timing (D4). The guest keeps running; there is no pause hook (the user, 2026-10-22). *Eight tabs; Reset is a confirm row on the Save page; Save is F5 or Y anywhere. The closing poll is neutral too. Design: Phase 3D as built.*
- [x] 3D.2 Mods page: the toolkit keeps the mod table, init result and enable state. Mod API v2 `menu_add` and `on_enable`, with `on_enable` deferred to the next `xbox_mod_frame` on the guest thread. `mods.<name>` is a persisted bool, and a mod without `on_enable` shows "applies at restart". *`mods.<name>` under `[mods]`, quoted when dotted; a mod off by its key keeps its keys out of the unused-key report (0cf4bddf). cat's `camera.free` has no `on_enable`, so it shows "applies at restart".*
- [x] 3D.3 Controls page: each action with its bindings, plus capture (the next key, two-button chord held 400 ms, modifier chord, or host-only button, refused under the R3 rules) and clear. Live at once and persisted by Save. A Mouse group at the end (R4, review F4) holds `input.mouse_capture` as a choice item applied on the window thread, the release key (`F8`, from save-states 4.0) and `input.mouse_free_keys` as info rows, and the capture state (captured; free: click to capture; free: F9). `tests/enhance_menu` checks the group's rows and the capture-mode choice. *A capture writes source names and refuses a guest-bound key with a toast. The release key row shows the configured key (F9 until save-states 4.0); free keys read "none (3F)".*
- [x] 3D.4 Debug page: backend and presenter, host-opts gen, cache counts, the miss ring, the extra buttons seen this second (Guide included), the atlas size and missing-glyph count, and `shot.window` (disabled on D3D11 until F-10). *No cache or target counts (no backend exports them yet); missing glyphs "n/a (3E)"; the window shot row reads "RECOMP_WINDOW_SHOT only".*
- [x] 3D.5 `recomp_cfg_patch` (old 3.5): differences-only writes, including the `[input.actions]` arrays, `[mods]` and `[overlay]`.
- [x] 3D.6 The miss-ring snapshot at the flip (old 3.11). (The mouse suspend moved to 3F.) *A spin flag instead of a seqlock: the writer skips a flip when the reader is mid-copy.*
- [x] 3D.7 `recomp_env.h`: the `MENU` row (`menu.enabled`, `RECOMP_MENU`, CONFIG tier) and its `config.md` and README env-table rows. `[ENHANCE] menu.enabled=off`, or `on` with the `menu.open` bindings.
- [x] 3D.8 ctests `enhance_menu` (old 3.7, plus Mods toggle through `on_enable`, Controls capture and refusal, Save of an action binding, and each page's draw list against a checked-in checksum at 1080 lines) and `recomp_cfg_patch` (old 3.7).
- [x] 3D.9 Docs: `config.md` menu section with each key's live class (R1).
- [x] 3D.10 Mac Metal checks (old 3.9 and 3.10), plus the Mods page toggling a test mod and a binding captured from the Controls page surviving a restart. Then the phase gates. *`runs/overlay-3d/live/` L1-L4, P0/P1 (60.0 vs 60.0 flips/s menu closed vs open); stock Metal goldens pass with `menu.enabled=off` (`runs/overlay-3d/metal-golden-234427`).*
- [x] 3D.11 The tracker item: one input fires one action (`menu.open` never gives way, else written beats default, else first registered), the Controls capture refuses a binding another action owns with a toast naming it, a pad binding inside a longer one fires on release only when no longer one was held whole, and nothing fires during a capture or on port 0's next step after it. ctests `input_actions` (`test_one_input`, `test_longest_match`, `test_longest_spent`, `test_longest_ports`, `test_tick_rules`, `test_quiet`) and `enhance_menu` (`test_capture_owned`); `config.md` rules 8-10.

### 3E. Font and theme (R7, R8), 1.5 days

- [ ] 3E.1 The atlas worker: created lazily on the first rebake, coalescing requests to the last size, publishing by atomic pointer and `atlas_gen`, with the old atlas drawn scaled until then. The Bold weight. The Unicode range of R7 with the `.notdef` box and the missing-glyph counter. Atkinson Hyperlegible's coverage is checked against that range, and any gap is listed in `config.md`. Tabular digits in the layout.
- [ ] 3E.2 `[overlay]` keys: `ui_scale` (0.75 to 2.0, default 1.0, live), `stats_corner` (`tr`, `tl`, `br`, `bl`). `[overlay.theme]`: every R8 token, `font` and `font_bold` (paths relative to the install directory, 8 MB cap, parsed on the worker, a bad file keeps the embedded face with one warning). All of `[overlay]` and `[overlay.theme]` are file-only: `config.md` rows for `overlay.ui_scale`, `overlay.stats_corner`, each `overlay.theme.*` token, `overlay.theme.font` and `font_bold`, and no `recomp_env.h` row. Every code default is the stock look. `[ENHANCE] overlay theme=<default|game|user>` line.
- [ ] 3E.3 A per-game theme from the game's `config.default.toml`, under the player's `config.toml`. The R8 layouts of the stats strip and toasts (the fade at 30 Hz only while a toast fades).
- [ ] 3E.4 ctests: atlas bake and rebake, missing glyphs, a truncated TTF refused, theme parse and refusals, layout at 480, 720, 1080 and 2160 lines with `ui_scale` 0.75 and 2.0.
- [ ] 3E.5 Docs: `config.md` `[overlay]` and `[overlay.theme]`. Mac: a window resize and a fullscreen toggle with the menu open rebake without a stall on the poll thread (`RECOMP_TRACE=pacing`). Then the phase gates.

### 3F. Mouse and cursor (R9), 2 days

- [ ] 3F.1 The menu mouse snapshot (`struct xbox_menu_mouse`), written while the MENU layer is visible by `xbox_InputSdlMouseEvent` (absolute `x`, `y` times `SDL_GetWindowPixelDensity`, minus the placement origin) and by `xbox_InputMouseWin32Msg` (client pixels), before the `xbox_InputMouseOn()` gate, with `seq` bumped last. The SDL loop posts the frame event on motion while the menu is visible.
- [ ] 3F.2 Open and close: `xbox_InputMouseSuspend(1)` on open and `(0)` on close (old 3.12), the OS cursor hidden while open (`SDL_HideCursor`, Win32 `WM_SETCURSOR` in the client area answered with `SetCursor(NULL)`), a warp to the panel centre on the first open, and mouse-look suppressed while open. `input.cursor_hide` (`never` in code, `idle` in the shipped file, the user, 2026-10-22) and `input.cursor_idle_ms` (2000), with the timer on the window thread.
- [ ] 3F.2b Capture on click (R9; the user, 2026-10-22):
  - `input.mouse_free_keys` (a list of key names, code default `[]`): a listed key frees the capture and is not consumed (`xbox_InputMouseKey` returns 0 for it). It never grabs, and it is exempt from the rule-2 clash and the reserved-key warning.
  - In `click` mode, `xbox_InputMouseSuspend(1)` clears the grab, so the cursor stays free after the menu closes until the next click. `focus` mode restores as today.
  - The close mask (review F7): while suspended, `mouse.c` drops button and wheel edges. After a resume it drops a button's edges until that button has been released once.
  - The live setter for `input.mouse_capture` (R1) on the window thread.
- [ ] 3F.3 Menu interactions: hover sets D5's selection; a left click acts as A, and on `<` or `>` steps a choice; drag and a track click set a slider; the wheel steps a value or scrolls (ten steps with Shift); a right click is Back and closes at the top page; a click outside the panel does nothing; the hint line follows the last input device; a pad or key press hides the overlay cursor until the mouse moves again (review F4).
- [ ] 3F.4 The CURSOR layer composed by the presenting thread from the snapshot: `[overlay.cursor]` `style` (`arrow`, `dot`, `image`), `image` (PNG, at most 128x128, decoded with stb_image built `STBI_ONLY_PNG`, a bad file falls back to `arrow` with one warning), `hotspot`, `size`. Record in TASKS (backends agree) that the D3D11 cursor, F10 and clicks arrive at guest flips (F-9, which must also pump messages, and F-11; the user, 2026-10-22: "OK for v1, fix later").
- [ ] 3F.4b Rows. File-only, so a `config.md` row and no `recomp_env.h` row: `input.cursor_hide`, `input.cursor_idle_ms`, `input.mouse_free_keys`, `overlay.cursor.style`, `.image`, `.hotspot`, `.size`. `input.mouse_capture`'s `config.md` row notes the shipped `click`.
- [ ] 3F.5 ctests: the snapshot hand-off (clicks between two steps neither lost nor doubled, the wheel accumulator), hit tests and the click, wheel and right-click mapping through the menu, cursor image refusals (truncated PNG, too large), the idle-hide state machine, and the pad-press cursor hide. `tests/input_keyboard` mouse cases: a free key frees the capture and still reaches the binding; a free key never grabs; `click` mode stays free after suspend and resume until a click; `focus` mode restores; a button held through resume drives nothing until released; wheel edges are dropped while suspended. `tests/enhance_cfg`: the `mouse_free_keys` parse, an unknown key refused, Escape with no clash warning.
- [ ] 3F.6 Mac with a mouse and a trackpad, Metal and the SDL renderer: with `input.mouse_capture = "focus"`, open with the mouse captured: the cursor is free and drawn by the overlay, every page works by mouse, close restores relative mode, and mouse-look works again. With `"click"` and `mouse_free_keys = ["Escape"]`: the cursor is free at start and hides after 2 s, a click captures it, Esc frees it and pauses the game, and after the menu it stays free until a click; an owner PNG cursor from a local file shows; idle hide with `input.mouse` off. Then the phase gates.

### 3G. Save states page (R4), 0.75 day, after 3F and save-states phase 4 and 5.2

- [ ] 3G.1 The Save states page over the save-states slot store and API (`openspec/changes/save-states/`, its tasks 5.1 and 5.2): the list with PNG thumbnails decoded into image slots once per open, labels, times and the `quick` tag; an "unreadable" row with delete only; rearrange by pad (hold X and move) and by mouse (drag or the row buttons), written to `slots.json` through a temporary file and rename; delete with a confirm row.
- [ ] 3G.2 Export to `[states] export_dir`, default `<save dir>/exports/<game>/`, that is `<save root>/exports/<title_id>/` (the user, 2026-10-22: "Folder next to saves"), as `<title>-<label>-<yyyymmdd-hhmm>.xbrslot` with a toast naming the path, plus "Export to..." through `SDL_ShowSaveFileDialog` where it works (macOS, Linux desktop), its callback posting to the menu step, and an **Open folder** row (`SDL_OpenURL` on a `file://` URL; in Deck game mode the row says it is unavailable). Rows: `states.export_dir` gets a `STATE_EXPORT_DIR` row (`RECOMP_STATE_EXPORT_DIR`, CONFIG tier, beside the save-states `RECOMP_STATE_*` rows) in `recomp_env.h`, a `config.md` row, and a `docs/env.md` row in 5.4. Import from the `.xbrslot` files in that folder through the save-states header check, a refusal shown on the row and in a toast. Load and Save to a new slot through `xbox_StateRequest`, closing the menu.
- [ ] 3G.3 ctest over a temporary slot directory: order after a move, delete, export name, import of a slot from another XBE refused, import of a good slot appended with a new id. Mac pass with the pad and the mouse. Then the phase gates. The save-states change's `tasks.md` was edited on `spec/overlay-ui` (review F3): 5.1 and the UI half of 5.2 moved here, and 5.3 and 5.4 are blocked on this phase.

## 4. CLI: golden harness and pins

- [x] 4.1 `golden.py` `ENHANCE_STOCK`: `menu.enabled` and `overlay.stats` (stock `off`) and `manifest.TOOLKIT_ENHANCE_KEYS`. Tests: a log with `menu.enabled=on` or `overlay.stats=on` fails with no game.toml rows, `--allow-enhance menu.enabled=on` notes. The tracker item (CLI `chore/golden-stock-menu`, 0debd14); `game.toml [golden] enhance_stock` drops the two rows the tracker item pinned there, since the manifest now refuses them.
- [ ] 4.1a The rest of the old 4.1: `golden.py` `ENHANCE_STOCK`: `textures.font` and `textures.text` (stock `on`); `[ENHANCE] actions hook=on` fails unless `--allow-enhance` names a key in its list, and any `[ACTION]` or `[OVERLAY] atlas` line fails; `manifest.TOOLKIT_ENHANCE_KEYS`. Tests: `textures.text=off` fails, the longer pack line still yields the path.
- [ ] 4.2 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.

## 5. cat: game items and config (D9), 5A 1 day

- [ ] 5.1 `src/glow.{c,h}`: one atomic word for (active, factor); `glow_configure` live-safe; `scripts/test_glow.py` cases.
- [ ] 5.2 `src/main.c host_enhance_init`: register `fx.glow`, `fx.glow_intensity`, `fps.mode` INFO through `enhance_menu_add`.
- [ ] 5.3 **Depends on 4.1** (review S4): the CLI's `ENHANCE_STOCK` and `TOOLKIT_ENHANCE_KEYS` must know `menu.enabled` before this turns it on in the shipped default, or a golden run with the menu on passes the stock check; `RECOMP_CONFIG=none` guards the goldens only through the code default. `packaging/config.default.toml` (the renamed default, phase 2): `[menu]` table (enabled true), `[input.actions]` with `"menu.open" = ["F10", "guide+a", "paddle1", "back+lthumb@400"]` (the BLiNX 2 fallback chord, R10; this line landed with the tracker item, so 5A does not add it again), `[input]` `cursor_hide = "idle"`, `mouse_capture = "click"` and `mouse_free_keys = ["Escape"]` (the user, 2026-10-22), an `[overlay]` table with `ui_scale` and a commented `[overlay.theme]` and `[overlay.cursor]` example, and `font = "on"`, `text = "on"` beside the commented pack line; `analysis/golden/golden.json`: `RECOMP_MENU=off`; `game.toml [golden] enhance_stock` unchanged (toolkit keys live in the CLI table). The tracker item (2026-10-27) shipped `[menu] enabled = true`, `[overlay] stats = false`, `overlay.stats = "F3"` and the golden pins `RECOMP_MENU=0`, `RECOMP_OVERLAY_STATS=0` ahead of 4.1, on the user's decision (the closed menu changes no frame; the game loses only the chords that open it); the pins hold the goldens off without the CLI check, and the rest of this item stays open. `game.toml [enhance.hud]`: `languages` (the branch's `lng_us` patterns move under `us`; other `lng_*` the dump holds listed), `text` patterns for baked text outside `lng_*` (`sm_*`, `mgtu*`, read off the dump), `preview` defaults.
- [ ] 5.4 `docs/env.md`: rows for `RECOMP_MENU`, `RECOMP_OVERLAY_STATS`, `input.chord_delay_ms`, `[input.actions]`, `input.cursor_hide`, `input.cursor_idle_ms`, `input.mouse_free_keys` (and `input.mouse_capture`'s shipped value now `"click"`), `overlay.ui_scale`, `overlay.stats_corner`, `[overlay.theme]`, `[overlay.cursor]`, `states.export_dir`, the `actions` trace, `RECOMP_TEXTURES_FONT`, `RECOMP_TEXTURES_TEXT`, the `tex_pack` trace, and the Config count; `docs/packaging.md` (the menu, where Save writes, `config/enhance-hud.toml`, pack size by language and kind); README Configuration paragraph.
- [ ] 5.5 `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`; `test_env_doc.py` sees every new row.
- [ ] 5.6 Mac Metal `@stage1`: Game page toggles glow live (frame darker by 12-18 levels within one frame, as the glow spec's numbers), intensity slider, Save; stock goldens unchanged with `RECOMP_GLOW=on` pin intact.

### 5B. Free camera onto actions (R3), 0.5 day, after the tracker item merges and 3A

- [ ] 5B.1 `src/free_camera.c`: register `camera.free.toggle`, `.hud`, `.freeze` and `.reset` through API v2 with defaults `F6`, `F7`, `End` (orchestrator, 2026-10-22, follows from the user's F8 choice; the user may override) and `Home` (the user, 2026-10-22; F5 is the quick save), plus `guide+y` for `camera.free.toggle` (the user, 2026-10-22, a rule-7 modifier chord: Guide first). `on_frame` polls `action_pressed` and drops its own rising-edge code. `camera.free_toggle`, `free_hud_key`, `free_freeze_key` and `free_reset_key` stay as aliases with one log line.
- [ ] 5B.2 Register `on_frame` and `batch_filter` only when `camera.free` or `menu.enabled` is on, so a stock run keeps today's never-taken branch. Once registered they are gated on an atomic. The actions arm the filter only when `camera.free` is on (R3 rule 6). `on_enable` (called on the guest thread at the next frame) runs the toggle-off path (camera restored, freeze dropped, HUD shown). `free_speed` and `free_look_sens` become relaxed atomics, with Mods-page items for both (3D).
- [ ] 5B.3 `packaging/config.default.toml` `[input.actions]` rows for the four actions. `docs/env.md` and README free-camera paragraph. `scripts/test_*` cases. The `key` script step keeps working, because scripted keys reach `xbox_FramebufferKeyDown` and the actions read the same table. Confirm this or route the step through the action.
- [ ] 5B.4 Mac Metal `@stage1`: toggle from F6 and from the pad chord, toggle off from the Mods page mid-flight, rebind from Controls. Stock goldens unchanged (`camera.free` off, `actions hook=off`). Then the phase gates.

## 6. Proton on the Deck and Windows (D3D11), on the orchestrator's slot, 1.5 days

- [ ] 6.1 Build on the Mac and install on the Deck (builds never run on the Deck); `tests/host_opts_live`, `tex_pack`, `overlay`, `enhance_menu`, `recomp_cfg_patch`, `input_actions` under `tests/proton_run.sh` (add them to `bench/host/tests.sh`).
- [ ] 6.2 `blinx2 bench golden` on D3D11 with no key: unchanged; logs `menu.enabled=off`.
- [ ] 6.3 D3D11 `@stage1` with the pack and `RECOMP_MENU=on`: open (keyboard and pad), the stats strip, pack and font toggles, scale 1->2->3->1 (watch for a persistent target with stale pixels: if any, D3D11 scale becomes "at restart" and TASKS records it), filter, fullscreen toggle, Save; a `d3d11_dump` with the menu open has no panel; flips/s within 25%. Runs in `runs/enhmenu/d3d11-*`.
- [ ] 6.4 A Windows bundle made with `--hud-pack` installs; its `config.default.toml` has the menu and the pack on; Save writes only the changed keys into `config/config.toml`; an install over a bundle with `config/enhance.toml` renames it once.
- [ ] 6.5 Actions under Proton: with Steam Input off for the title, guide through `XInputGetStateEx` fires a bound action and `guide+a` opens the menu without the game seeing A. On the Deck (on "go"), a back grip bound in Steam Input to F10 opens the menu, and one bound to F6 toggles the free camera; the BLiNX 2 fallback chord opens it too. A `d3d11_dump` with the strip and menu open has neither.
- [ ] 6.6 The D3D11 renderer against a Metal shot of the same page by eye (host screenshot): rounded corners, text, the cursor. The mouse on the Win32 window under Proton: the capture is released and restored, the cursor is drawn and moves at guest flips (accepted for v1, the user, 2026-10-22; record the feel for F-9 and F-11), capture on click and Esc release, every page works by mouse. The Save states page on the Deck once 3G has merged.
- [ ] 6.7 Native Windows, only when the user boots it: `guide+a` with the Game Bar button setting on and off, recorded in `config.md`.

## 7. CLI: preview tool, upscale mode (D12-D15)

- [ ] 7.1 `enhance/filters/`: `xbr` gains 3x and parameters (`level`, `eq`, `weights`, `alpha_edge`); `epx` (2x/3x/4x), `lanczos` (fixed-point, 3 lobes, integer kernel table), `external` (command template on PNG files, sha256 of the tool, manifest note). `enhance/png.py` (stdlib `zlib` encoder and decoder). Tests: determinism across runs, known small images, 3x xbr line areas sum to 1 per output pixel.
- [ ] 7.2 `enhance/preview_cfg.py`: the `enhance-hud.toml` schema (D13: `[upscale]`, `[text]` with `languages`, `[override]`, `[font]`) with validation and a writer; `enhance hud --config FILE` (default `config/enhance-hud.toml` when present) applies per kind the scale, filter and BC3, then the overrides; records `config` path and sha in `hud-pack.toml`. Test: no config gives today's art and atlas payloads byte for byte; a config with `nearest` for one pattern changes that entry only; `[text] languages = ["us"]` leaves another language's entries out.
- [ ] 7.3 `enhance/preview.py` and `preview_page.html`: the `127.0.0.1` server (random port, `--port`, `--no-browser`, `/quit`), asset list grouped by kind and language with curated defaults (`[enhance.hud] preview`) and the size readout (entries, raw MB, BC3 MB per kind and language), crop and scale selection, side-by-side panels with parameters and per-panel time (raw beside BC3 for an entry), per-texture override, the runtime-log import (missed candidate hashes joined to the dump; hash-only rows for unknown ones), Save. No external resource in the page.
- [ ] 7.4 `main.py`/`helptext.py`: `enhance preview`; `docs/manifest.md`: `[enhance.hud] preview`; CLI README section. Tests drive the handlers with `http.client` on a synthetic game tree: list, render a crop with each filter, import a log, save and read the config back.
- [ ] 7.5 `uv run pytest tests`, ruff, `scripts/audit-public.sh main..HEAD` clean.

## 8. CLI: preview tool, font mode (D12, D13)

- [ ] 8.1 `enhance/fonts.toml` (three curated faces: PT Sans Narrow Bold, Roboto Condensed Bold, Fira Sans Condensed Bold, each a google/fonts entry with file, licence file and sha256) and `enhance/fontcache.py` (per-user cache dir, download on request with `urllib`, sha check, the licence file stored beside the font, never the tree). Test with a local `http.server` fixture serving a synthetic repository layout.
- [ ] 8.1a Font import: the page's drop zone and picker post a `.ttf`/`.ttc` to the server, stored in the cache under its sha256 with the face name read from `name` ID 4; `.otf` with CFF outlines refused with a line; the config records name and sha. Test: upload the synthetic font, pick its face, save, build.
- [ ] 8.1b Google Fonts: `enhance/gfonts.py` maps a family name or `fonts.google.com` URL to its `ofl/`, `apache/` or `ufl/` slug, reads `METADATA.pb` over `raw.githubusercontent.com/google/fonts/<commit>/` (a pinned commit recorded in the config), picks the static file of the requested weight (or the variable file's default instance, said on the page), downloads it and the licence file, records family, file, URL, licence file and both shas. First task: verify the repository layout and the `METADATA.pb` fields on three families and write them into the module's docstring. Tests against a local fixture of that layout.
- [ ] 8.2 `atlas.render` knobs: `size`, `weight` (synthetic stroke), `dx`, `dy`, `outline`, `shadow`, `overhang` with the touch check; defaults reproduce today's output byte for byte (test).
- [ ] 8.3 Preview page font mode: installed faces plus the curated list, stock row / fitted row / free-text line through the real fit, the knobs, the red touch marks, Save into `[font]`.
- [ ] 8.4 Owner check on the Mac: save a PT Sans config from the page, `blinx2 enhance hud --config config/enhance-hud.toml`, sha equals the no-config build (54fb5c0f at the current CLI) when every knob is at default; a config with `weight = 1` changes only the atlas entry. Metal `@stage1` with that pack, text readable, `runs/enhmenu/font-knobs/`.

## 9. Menu Controls page (folded into 3D.3), 0.5 day

- [ ] 9.1 Mac and Proton: rebind `menu.open` to `lthumb+rthumb@400`, `guide+b` and `F4` (not `F8`, the mouse release, nor `F5` and `F9`, the quick save and load). Do it from the Controls page with a real pad and with a mouse click on the binding, restart, and the new bindings open the menu. `config.md` Controls paragraph.

## 10. Baked-text re-render (D16): spike, then opt-in

- [ ] 10.1 Spike (own branch, `analysis/enhancements/text-rerender.md`): the Mission Objectives title and one line; string from a hand table; measure fill, outline, glow and shadow from the stock image; re-render with the chosen face through `atlas` and re-synthesise the style; compare by eye in the preview tool and in a Metal `@stage1` dump. Also look for the strings in the `lng_*` archives. Go/no-go recorded in TASKS.
- [ ] 10.2 On go: `[text] rerender`, per-entry opt-in, `config/text-strings.toml` edited in the preview tool, optional local OCR drafts (Tesseract as an external command), style knobs `glow` and `gradient`; a glyph the string does not explain keeps the upscaled pixels. Tests on synthetic captions.

## 11. Review and merge

- [ ] 11.1 Review per phase and merge (the user, 2026-10-11: the reviewer writes specs only); fixes back to the phase's agent.
- [ ] 11.2 After each merge: notes to `notes/enhmenu/`, runs to `runs/`, worktrees removed, branches kept, Deck sync and `blinx2 bench integrate --golden`, TASKS updated, cat `game.toml` re-pinned to the merged CLI sha (phases 4, 7, 8), the public pin gap (TASKS (c)) noted for the next push round.
- [ ] Before archive: rebuild specs/enhancements "Enhancements default to stock" from the current openspec/specs/enhancements text (config-layering and hud-pack wording, "Legacy pin still stock"), then re-apply this change's edits; openspec validate fails until then.
