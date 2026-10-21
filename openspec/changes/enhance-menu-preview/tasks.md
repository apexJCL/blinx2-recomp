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

## 3. Toolkit: actions, overlay, live switching, menu (R1-R5; D3, D4, D5, D8)

Re-split on 2026-10-21 (design R5). Estimates are in agent-days and
include each phase's own gates.

- **Development:** 3A, 3B and 3C may run in parallel, each in its own
  toolkit worktree.
- **Merges:** in the order 3A, 3B, 3C, 3D, each rebased on the previous
  merge. They share `enhance.c`, `recomp_env.h`, `mod.h`,
  `fb_present_sdl.c`, `nv2a_pb_d3d11.c` and the `fbm_present`
  signature (R5).
- **Gates for every phase** (CLAUDE.md), before its merge:
  - the Mac build, the POSIX ctests and stock Metal goldens;
  - `blinx2 bench golden` on D3D11 under Proton on the Deck;
  - a Deck smoke run of the installed build;
  - the review.

### 3A. Host actions (R3), 2 days

- [ ] 3A.1 `mod.h` glue section: `struct xbox_host_pad` and `xbox_enhance_pad_filter(port, host, st)`, beside `xbox_mod_input_captured`. It returns at its first test when disarmed. `input_core.c` calls it at the end of `xbox_InputGetState` with the host state read before the keyboard and script merge (the USB path: b3, ssx3, jsrf, spartan, kuf). `tests/input_keyboard` gains a filter case (rewrite and disarmed no-op).
- [ ] 3A.1c cat glue (cat worktree, same phase): `src/pad_input.c` `cat_pad_get_state` fills `xbox_host_pad` from its backend read before merging `RECOMP_INPUT_SCRIPT` and the keyboard and mouse. It calls the filter on the merged state converted to `XBOX_INPUT_STATE` and writes the result back into the 18-byte gamepad. `scripts/test_*` case if the conversion is testable from Python, else a toolkit-side unit test of the conversion helper.
- [ ] 3A.2 `input_backend.h`: `host_extra`. The SDL2 backend routes `GUIDE` (already in the table, `input_map.h` ~67, unmapped to the guest) and reads `MISC1`, `PADDLE1-4` and `TOUCHPAD` (15..20) in a second loop (`XBOX_SDL_BUTTON_COUNT` stays 15 for the guest map). The XInput backend reads guide through `XInputGetStateEx` (ordinal 100, resolved by `GetProcAddress`, absent means 0). `input_names.c` gains the host-only names.
- [ ] 3A.3 `src/enhance/enhance_actions.{c,h}`: the registry (64 actions), the binding parser (key with modifiers; `+` chord with `@ms`; `padN:` prefix; host-only singles), the R3 refusal rules with one warning each, the effective key map for rule 2 (compiled-in `xbox_key_map`, `[input.bindings]`, `walk_key`, `mouse_release_key`, modifiers included), hold timers, chord consumption in `*st`, `[input] chord_delay_ms` (default 0), atomic fire counters, `enhance_actions_tick()` from the flip when the last poll is older than 100 ms (keys and host-only buttons only, from the backend's atomic snapshot, only when armed). Arming by feature keys only (rule 6), the startup line `[ENHANCE] actions hook=off|on (<keys>)`, and `[ACTION] <name> via <binding>` on every fire, limited to 10 lines a second.
- [ ] 3A.4 `[input.actions]` read by `enhance.c`. The R1 setters for `input.*` (mouse and stick feel, `walk_key`, `mouse_capture` on the window thread). The toolkit actions are `menu.open` (until 3D it only logs), `overlay.stats` (until 3B it only logs) and `shot.window`. `[input.bindings]` and `[input.actions]` are rebuilt live by a pointer swap on the poll thread. `enhance_input_init` stops rewriting the live table in place.
- [ ] 3A.5 Mod API v2 (`XBOX_MOD_API_VERSION 2`, fields appended): `action_register`, `action_pressed`, `action_down`, `toast` (a log line until 3B). A v1 mod still loads.
- [ ] 3A.6 `recomp_env.h`: the `INPUT_CHORD_DELAY_MS` row. `docs/env.md` gets the rows in the cat phase.
- [ ] 3A.7 ctest `input_actions`: chord with hold fires once; release before the hold fires nothing; the consumed buttons are reported released until the physical release; a single guest button is refused; a key in the effective map is refused (`[input.bindings]`, `walk_key`, a default Ctrl modifier); `chord_delay_ms` hides a chord completed inside the window; a `RECOMP_INPUT_SCRIPT` pad never fires while a kbm-script key does; disarmed (`RECOMP_CONFIG=none`, a mod registered) logs `hook=off` and fires nothing; a paddle single fires; a v1 mod table registers; a live rebuild during a polling thread (TSan build when available).
- [ ] 3A.8 Docs: `docs/runtime/config.md` `[input.actions]` section (grammar, rules, defaults, the Deck and Steam Input paragraph); `src/input/README.md` hook and `host_extra` paragraphs.
- [ ] 3A.9 Mac with a real pad (Xbox or DualSense), in BLiNX 2 through the cat glue: F10 and `back+lthumb@400` log `menu.open`. A paddle or the touchpad fires a bound action. From the moment both chord buttons are down, `cat_pad_get_state` reports neither (`RECOMP_TRACE=input`), and a lone START still pauses. The same chord check in one USB-path game (b3) through `xbox_InputGetState`. Then the phase gates.

### 3B. Overlay core, stats and toasts (R2), 2 days

- [ ] 3B.1 `src/kernel/nv2a_overlay.{c,h}` and `nv2a_overlay_font.h` (public-domain `font8x8_basic`, credited in `NOTICE`): the three layers, one writer each, a triple buffer per layer published by one atomic exchange, drawing through a canvas handle, `gen`, the `visible` mask, `nv2a_overlay_toast` pushing to an 8-line lock-free ring that the presenting thread composes. All of it compiles only under `XBOXRECOMP_ENHANCE`.
- [ ] 3B.2 `src/kernel/nv2a_stats.{c,h}`: relaxed atomic counters, each site gated on the relaxed flag `nv2a_stats_on` (set while the strip, the Stats page or `RECOMP_TITLE_STATS` is shown) (flips, presents, draws, texture uploads, pack hits and misses) and a 128-entry frame-ms ring written at the flip. `xbox_title_format` reads the same counters.
- [ ] 3B.3 Presenters. SDL renderer: one streaming texture per layer, drawn after the frame copy and before `shot_save`; a moved `gen` sets `dirty` and posts the frame event. `fbm_present`: a layers argument (NULL when `visible == 0`), a blended pipeline state, one texture per layer. D3D11 flip: draw after `present_blit` or the copy **and after `dump_frame()`**, with its own viewport and target on the stock copy path and `s_sc_init = 0`. Nothing runs when `visible == 0`. Record in TASKS (backends agree) that the D3D11 overlay refreshes only on guest flips (F-9) and that D3D11 has no `RECOMP_WINDOW_SHOT` (F-10).
- [ ] 3B.4 The STATS layer composed on the presenting thread at 2 Hz. The `overlay.stats` key (bool, default off), the `RECOMP_OVERLAY_STATS` row, the `[ENHANCE] overlay.stats=off|on` line, and the `overlay.stats` action toggling it.
- [ ] 3B.5 ctest `overlay`: rect and text pixels, publish and hide per layer, `gen`, `visible` mask, toast expiry, two writer threads on two layers plus a reader thread (no torn frame: each published frame carries a checksum the reader verifies), stats sites inert with the flag clear.
- [ ] 3B.6 Mac: Metal layer window and SDL renderer (CPU backend). A `RECOMP_WINDOW_SHOT` with the strip on shows it, and the `fb_dump` of the same flip has no strip. Flips/s with the strip on is within 5% of off (`runs/enhmenu/stats-metal.txt`). Then the phase gates.

### 3C. Live-switch completion (R1), 1.5 days

- [ ] 3C.1 `NV2A_OPT_ANISO`, `NV2A_OPT_MOVIE` and `NV2A_OPT_OVERSCAN` mask bits, applied at the flip in both GPU backends (the overscan refusal with a wide aspect kept). Null and CPU backends accept them.
- [ ] 3C.2 `fb_present_sdl.c` reads `present.filter` at each present (`SDL_SetTextureScaleMode` on change) and passes it to `fbm_present`.
- [ ] 3C.3 `present.fullscreen` live. SDL: `SDL_SetWindowFullscreen` on the SDL main thread when the host-opts gen moves. D3D11: a style swap with `SetWindowPos` on the window thread, then `ResizeBuffers` at the next flip. If the D3D11 half is not taken (question 4), the menu says "applies at restart" on D3D11 and TASKS records the gap.
- [ ] 3C.4 Setter for `present.pacing` (`xbox_PacingSetMode`). The input setters are in 3A.4.
- [ ] 3C.5 ctest `host_opts_live` cases for the new bits. Mac Metal checks: aniso 1 to 16 and back, overscan on and off, filter, fullscreen on and off, each within two flips. Then the phase gates.

### 3D. Menu (D5, R4, D8), 2.5 days

- [ ] 3D.1 `src/enhance/enhance_menu.{c,h}`: the item table with each item's live class, `enhance_menu_add`, the pure state machine, the renderer onto the MENU layer. Pages: Render, Pack, Game, Mods, Stats, Controls, Debug, Save, Reset. Opened by the `menu.open` action. While open: a neutral pad, frozen packet number and repeat timing (D4).
- [ ] 3D.2 Mods page: the toolkit keeps the mod table, init result and enable state. Mod API v2 `menu_add` and `on_enable`, with `on_enable` deferred to the next `xbox_mod_frame` on the guest thread. `mods.<name>` is a persisted bool, and a mod without `on_enable` shows "applies at restart".
- [ ] 3D.3 Controls page: each action with its bindings, plus capture (the next key, two-button chord held 400 ms, or host-only button, refused under the R3 rules) and clear. Live at once and persisted by Save.
- [ ] 3D.4 Debug page: backend and presenter, host-opts gen, cache counts, the miss ring, the extra buttons seen this second, and `shot.window` (disabled on D3D11 until F-10).
- [ ] 3D.5 `recomp_cfg_patch` (old 3.5): differences-only writes, including the `[input.actions]` arrays and `[mods]`.
- [ ] 3D.6 The miss-ring snapshot at the flip (old 3.11) and the mouse suspend while open (old 3.12).
- [ ] 3D.7 `recomp_env.h`: the `MENU` row (`menu.enabled`). `[ENHANCE] menu.enabled=off`, or `on` with the `menu.open` bindings.
- [ ] 3D.8 ctests `enhance_menu` (old 3.7, plus Mods toggle through `on_enable`, Controls capture and refusal, Save of an action binding) and `recomp_cfg_patch` (old 3.7).
- [ ] 3D.9 Docs: `config.md` menu section with each key's live class (R1).
- [ ] 3D.10 Mac Metal checks (old 3.9 and 3.10), plus the Mods page toggling a test mod and a binding captured from the Controls page surviving a restart. Then the phase gates.

## 4. CLI: golden harness and pins

- [ ] 4.1 `golden.py` `ENHANCE_STOCK`: `menu.enabled` and `overlay.stats` (stock `off`), `textures.font` and `textures.text` (stock `on`); `[ENHANCE] actions hook=on` fails unless `--allow-enhance` names a key in its list, and any `[ACTION]` line fails; `manifest.TOOLKIT_ENHANCE_KEYS`. Tests: a log with `menu.enabled=on` fails, `--allow-enhance menu.enabled=on` notes, `textures.text=off` fails, the longer pack line still yields the path.
- [ ] 4.2 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.

## 5. cat: game items and config (D9), 5A 1 day

- [ ] 5.1 `src/glow.{c,h}`: one atomic word for (active, factor); `glow_configure` live-safe; `scripts/test_glow.py` cases.
- [ ] 5.2 `src/main.c host_enhance_init`: register `fx.glow`, `fx.glow_intensity`, `fps.mode` INFO through `enhance_menu_add`.
- [ ] 5.3 `packaging/config.default.toml` (the renamed default, phase 2): `[menu]` table (enabled true, hotkey, chord) and `font = "on"`, `text = "on"` beside the commented pack line; `analysis/golden/golden.json`: `RECOMP_MENU=off`; `game.toml [golden] enhance_stock` unchanged (toolkit keys live in the CLI table). `game.toml [enhance.hud]`: `languages` (the branch's `lng_us` patterns move under `us`; other `lng_*` the dump holds listed), `text` patterns for baked text outside `lng_*` (`sm_*`, `mgtu*`, read off the dump), `preview` defaults.
- [ ] 5.4 `docs/env.md`: rows for `RECOMP_MENU`, `RECOMP_OVERLAY_STATS`, the `actions` trace, `RECOMP_TEXTURES_FONT`, `RECOMP_TEXTURES_TEXT`, the `tex_pack` trace, and the Config count; `docs/packaging.md` (the menu, where Save writes, `config/enhance-hud.toml`, pack size by language and kind); README Configuration paragraph.
- [ ] 5.5 `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`; `test_env_doc.py` sees every new row.
- [ ] 5.6 Mac Metal `@stage1`: Game page toggles glow live (frame darker by 12-18 levels within one frame, as the glow spec's numbers), intensity slider, Save; stock goldens unchanged with `RECOMP_GLOW=on` pin intact.

### 5B. Free camera onto actions (R3), 0.5 day, after the tracker item merges and 3A

- [ ] 5B.1 `src/free_camera.c`: register `camera.free.toggle`, `.hud`, `.freeze` and `.reset` through API v2 with defaults `F6`, `F7`, `F8` and `F5` (plus the pad chord the user picks, question 2). `on_frame` polls `action_pressed` and drops its own rising-edge code. `camera.free_toggle`, `free_hud_key`, `free_freeze_key` and `free_reset_key` stay as aliases with one log line.
- [ ] 5B.2 Register `on_frame` and `batch_filter` only when `camera.free` or `menu.enabled` is on, so a stock run keeps today's never-taken branch. Once registered they are gated on an atomic. The actions arm the filter only when `camera.free` is on (R3 rule 6). `on_enable` (called on the guest thread at the next frame) runs the toggle-off path (camera restored, freeze dropped, HUD shown). `free_speed` and `free_look_sens` become relaxed atomics, with Mods-page items for both (3D).
- [ ] 5B.3 `packaging/config.default.toml` `[input.actions]` rows for the four actions. `docs/env.md` and README free-camera paragraph. `scripts/test_*` cases. The `key` script step keeps working, because scripted keys reach `xbox_FramebufferKeyDown` and the actions read the same table. Confirm this or route the step through the action.
- [ ] 5B.4 Mac Metal `@stage1`: toggle from F6 and from the pad chord, toggle off from the Mods page mid-flight, rebind from Controls. Stock goldens unchanged (`camera.free` off, `actions hook=off`). Then the phase gates.

## 6. Proton on the Deck (D3D11), on the orchestrator's slot

- [ ] 6.1 Build on the Mac and install on the Deck (builds never run on the Deck); `tests/host_opts_live`, `tex_pack`, `overlay`, `enhance_menu`, `recomp_cfg_patch` under `tests/proton_run.sh` (add them to `bench/host/tests.sh`).
- [ ] 6.2 `blinx2 bench golden` on D3D11 with no key: unchanged; logs `menu.enabled=off`.
- [ ] 6.3 D3D11 `@stage1` with the pack and `RECOMP_MENU=on`: open (keyboard and pad), the stats strip, pack and font toggles, scale 1->2->3->1 (watch for a persistent target with stale pixels: if any, D3D11 scale becomes "at restart" and TASKS records it), filter, fullscreen toggle, Save; a `d3d11_dump` with the menu open has no panel; flips/s within 25%. Runs in `runs/enhmenu/d3d11-*`.
- [ ] 6.4 A Windows bundle made with `--hud-pack` installs; its `config.default.toml` has the menu and the pack on; Save writes only the changed keys into `config/config.toml`; an install over a bundle with `config/enhance.toml` renames it once.
- [ ] 6.5 Actions under Proton: with Steam Input off for the title, guide through `XInputGetStateEx` fires a bound action. On the Deck (on "go"), a back grip bound in Steam Input to F10 opens the menu, and one bound to F6 toggles the free camera. A `d3d11_dump` with the strip and menu open has neither.

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

- [ ] 9.1 Mac and Proton: rebind `menu.open` to `lthumb+rthumb@400` and `F4` (not `F9`, which is reserved for the mouse release). Do it from the Controls page with a real pad, restart, and the new bindings open the menu. `config.md` Controls paragraph.

## 10. Baked-text re-render (D16): spike, then opt-in

- [ ] 10.1 Spike (own branch, `analysis/enhancements/text-rerender.md`): the Mission Objectives title and one line; string from a hand table; measure fill, outline, glow and shadow from the stock image; re-render with the chosen face through `atlas` and re-synthesise the style; compare by eye in the preview tool and in a Metal `@stage1` dump. Also look for the strings in the `lng_*` archives. Go/no-go recorded in TASKS.
- [ ] 10.2 On go: `[text] rerender`, per-entry opt-in, `config/text-strings.toml` edited in the preview tool, optional local OCR drafts (Tesseract as an external command), style knobs `glow` and `gradient`; a glyph the string does not explain keeps the upscaled pixels. Tests on synthetic captions.

## 11. Review and merge

- [ ] 11.1 Review per phase and merge (the user, 2026-10-11: the reviewer writes specs only); fixes back to the phase's agent.
- [ ] 11.2 After each merge: notes to `notes/enhmenu/`, runs to `runs/`, worktrees removed, branches kept, Deck sync and `blinx2 bench integrate --golden`, TASKS updated, cat `game.toml` re-pinned to the merged CLI sha (phases 4, 7, 8), the public pin gap (TASKS (c)) noted for the next push round.
- [ ] Before archive: rebuild specs/enhancements "Enhancements default to stock" from the current openspec/specs/enhancements text (config-layering and hud-pack wording, "Legacy pin still stock"), then re-apply this change's edits; openspec validate fails until then.
