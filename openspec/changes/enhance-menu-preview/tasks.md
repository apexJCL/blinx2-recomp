## Context

Phases 1-5 of design.md "Migration Plan", one worktree set per phase
(`wt/<phase>/{cat,xboxrecomp,xboxrecomp-cli}`), one agent at a time.
Toolkit branches off `posix-host/portability`, CLI off `main`, cat off
`main`. Mac builds with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`;
Mac runs headless with `SDL_AUDIODRIVER=dummy` except the window-shot
checks, which open a window and no sound. Frame dumps and shots go to
`xbox-recomp/runs/enhmenu/`, never inside a worktree. The Linux/Proton runs wait
for the orchestrator's "go" and hold `flock -w 3600 ~/.recomp-run.lock`.

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

- [ ] 2.1 Its own openspec change, landed before phase 3: `enhance_cfg_init` reads `config.default.toml` then the `config.toml` files, env on top, differences-only Save, automatic rename of an existing `enhance.toml` with one line; `RECOMP_CONFIG` with `RECOMP_ENHANCE_CONFIG` as the row's `LEGACY` name; launchers (SteamOS, Windows, macOS) stop copying the template and rename the user's file once; `blinx2 package` stages `config.default.toml` and `--hud-pack` writes into it; `packaging.md` §6, README, `enhance-config.md` → `config.md`, `docs/env.md`; `golden.json` pins `RECOMP_CONFIG=none`. ctest `enhance_cfg` cases for the two-file layering, the rename and differences-only writes. Enhancement and mod keys only: no `launch.env` row moves.
- [ ] 2.2 Mac: stock Metal goldens unchanged with `RECOMP_CONFIG=none` (and once with the legacy `RECOMP_ENHANCE_CONFIG=none`); a developer `config/config.toml` with `scale = 2` is read over the build's `config.default.toml`; an old `enhance.toml` is renamed once with one line.

## 3. Toolkit: overlay and menu (D3, D4, D5, D6, D8)

- [ ] 3.1 `src/kernel/nv2a_overlay.{c,h}` and `nv2a_overlay_font.h` (public-domain 8x8 font, credited in `NOTICE`): begin/rect/text/publish/hide, double buffer with an atomic swap, `gen`.
- [ ] 3.2 Presenters: SDL renderer (streaming texture, blend, `RenderCopy` into the frame rect); `fbm_present` (blend PSO, shared texture, second draw); D3D11 flip (blend state, dynamic texture, draw after the copy or blit, `s_sc_init = 0`). Nothing runs when `nv2a_overlay_frame()` is NULL. The D3D11 overlay draw runs after `dump_frame()`.
- [ ] 3.3 `input_core.c`: `xbox_InputSetHook`; called with the merged state at the end of `xbox_InputGetState`; NULL by default. `tests/input_keyboard` gains a hook case (rewrite and return code).
- [ ] 3.4 `src/enhance/enhance_menu.{c,h}`: the item table, `enhance_menu_add`, pages, the pure state machine (`enhance_menu_step(menu, event) -> redraw`), the renderer onto the overlay, the hook (chord with 400 ms hold, hotkey via `xbox_FramebufferKeyDown`, neutral pad while open, repeat timing), toolkit items for Render and Pack pages, Stats, Save, Reset.
- [ ] 3.5 `recomp_cfg_patch` in `recomp_cfg.c`: differences-only writes to `config.toml` (replace in place keeping the comment, append a missing key or header, delete a key for Reset and its header once empty), temp file and rename, re-parse check. Save writes the `config.toml` the layer read; dimmed when none (`RECOMP_CONFIG=none`); never touches `config.default.toml`.
- [ ] 3.6 `recomp_env.h`: `MENU`, `MENU_HOTKEY`, `MENU_CHORD` rows; `enhance.c` reads `menu.*`, logs `[ENHANCE] menu.enabled=off` or the on line, installs the hook only when on.
- [ ] 3.7 ctests: `tests/overlay` (rect and text pixels, publish/hide, gen), `tests/enhance_menu` (navigation, toggle/choice/range edits, the hook neutralises buttons and freezes the packet number while open, chord hold and release, hotkey, a game item added through the API, Save calls the patcher with the right keys), `tests/recomp_cfg_patch` (value after comment kept, quoted and dotted keys, CRLF, missing key appended under its header, missing header appended, a key deleted and its empty header removed, refusal on a parse mismatch).
- [ ] 3.8 Docs: `enhance-config.md` menu section (keys, controls, what is live and what is at restart, the pack page), `src/input/README.md` hook paragraph, `docs/runtime/README.md` link.
- [ ] 3.9 Mac Metal: `@stage1` with `RECOMP_MENU=on`: open with F10 and with BACK+START (a real pad), toggle the pack (text sharp/soft within one frame), scale 1->2->3->1 (frame rebuilt, no crash, no stuck target), filter, glow absent (toolkit only), Save then restart: `config/config.toml` holds only the changed keys and the new values are in force; `RECOMP_WINDOW_SHOT` of the open menu and `fb_dump` of the same flip: the dump has no panel. Flips/s with the menu open vs closed within 25% (`runs/enhmenu/metal-menu.txt`).
- [ ] 3.10 Mac: stock Metal goldens unchanged; log `menu.enabled=off`.
- [ ] 3.11 The Pack page reads the miss ring (`nv2a_tex_pack_misses`) only on the walker thread at the flip, copying a snapshot the menu thread then draws from, or the ring gains a lock first: it is written by the upload path without one (design, "Phase 1 as built" 9). `tests/enhance_menu` covers the snapshot.
- [ ] 3.12 The mouse while the menu is open (from `kbm-input` 7.3): call `xbox_InputMouseSuspend(1)` when the menu opens and `xbox_InputMouseSuspend(0)` when it closes, so motion and clicks do not drive the game under the menu and the cursor is not fought over; the hook's neutral pad already covers the keys. Verify: `tests/enhance_menu` case, and with the menu open `RECOMP_TRACE=mouse` logs no `[MOUSE]` lines.

## 4. CLI: golden harness and pins

- [ ] 4.1 `golden.py` `ENHANCE_STOCK`: `menu.enabled` (stock `off`), `textures.font` and `textures.text` (stock `on`); `manifest.TOOLKIT_ENHANCE_KEYS`. Tests: a log with `menu.enabled=on` fails, `--allow-enhance menu.enabled=on` notes, `textures.text=off` fails, the longer pack line still yields the path.
- [ ] 4.2 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.

## 5. cat: game items and config (D9)

- [ ] 5.1 `src/glow.{c,h}`: one atomic word for (active, factor); `glow_configure` live-safe; `scripts/test_glow.py` cases.
- [ ] 5.2 `src/main.c host_enhance_init`: register `fx.glow`, `fx.glow_intensity`, `fps.mode` INFO through `enhance_menu_add`.
- [ ] 5.3 `packaging/config.default.toml` (the renamed default, phase 2): `[menu]` table (enabled true, hotkey, chord) and `font = "on"`, `text = "on"` beside the commented pack line; `analysis/golden/golden.json`: `RECOMP_MENU=off`; `game.toml [golden] enhance_stock` unchanged (toolkit keys live in the CLI table). `game.toml [enhance.hud]`: `languages` (the branch's `lng_us` patterns move under `us`; other `lng_*` the dump holds listed), `text` patterns for baked text outside `lng_*` (`sm_*`, `mgtu*`, read off the dump), `preview` defaults.
- [ ] 5.4 `docs/env.md`: rows for `RECOMP_MENU`, `RECOMP_MENU_HOTKEY`, `RECOMP_MENU_CHORD`, `RECOMP_TEXTURES_FONT`, `RECOMP_TEXTURES_TEXT`, the `tex_pack` trace, and the Config count; `docs/packaging.md` (the menu, where Save writes, `config/enhance-hud.toml`, pack size by language and kind); README Configuration paragraph.
- [ ] 5.5 `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`; `test_env_doc.py` sees every new row.
- [ ] 5.6 Mac Metal `@stage1`: Game page toggles glow live (frame darker by 12-18 levels within one frame, as the glow spec's numbers), intensity slider, Save; stock goldens unchanged with `RECOMP_GLOW=on` pin intact.

## 6. Proton (D3D11), on "go"

- [ ] 6.1 Sync and build the branch set on the Linux/Proton host (own scratch tree); `tests/host_opts_live`, `tex_pack`, `overlay`, `enhance_menu`, `recomp_cfg_patch` under `tests/proton_run.sh` (add them to `bench/host/tests.sh`).
- [ ] 6.2 `blinx2 bench golden` on D3D11 with no key: unchanged; logs `menu.enabled=off`.
- [ ] 6.3 D3D11 `@stage1` with the pack and `RECOMP_MENU=on`: open (keyboard and pad), pack and font toggles, scale 1->2->3->1 (watch for a persistent target with stale pixels: if any, D3D11 scale becomes "at restart" and TASKS records it), filter, fullscreen toggle, Save; a `d3d11_dump` with the menu open has no panel; flips/s within 25%. Runs in `runs/enhmenu/d3d11-*`.
- [ ] 6.4 A Windows bundle made with `--hud-pack` installs; its `config.default.toml` has the menu and the pack on; Save writes only the changed keys into `config/config.toml`; an install over a bundle with `config/enhance.toml` renames it once.

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

## 9. Menu Controls page (D5, late)

- [ ] 9.1 `enhance_menu`: Controls page with `menu.chord` and `menu.hotkey` as CHOICE items and a Capture action (next two-button chord held 400 ms, or next F-key; a single button refused); live at once; Save persists them. ctest cases for capture, refusal and persistence.
- [ ] 9.2 Mac and Proton: rebind to `lthumb+rthumb` and `F9` from the menu with a real pad, restart, the new binding opens the menu; `enhance-config.md` Controls paragraph.

## 10. Baked-text re-render (D16): spike, then opt-in

- [ ] 10.1 Spike (own branch, `analysis/enhancements/text-rerender.md`): the Mission Objectives title and one line; string from a hand table; measure fill, outline, glow and shadow from the stock image; re-render with the chosen face through `atlas` and re-synthesise the style; compare by eye in the preview tool and in a Metal `@stage1` dump. Also look for the strings in the `lng_*` archives. Go/no-go recorded in TASKS.
- [ ] 10.2 On go: `[text] rerender`, per-entry opt-in, `config/text-strings.toml` edited in the preview tool, optional local OCR drafts (Tesseract as an external command), style knobs `glow` and `gradient`; a glyph the string does not explain keeps the upscaled pixels. Tests on synthetic captions.

## 11. Review and merge

- [ ] 11.1 Review per phase and merge (the user, 2026-10-11: the reviewer writes specs only); fixes back to the phase's agent.
- [ ] 11.2 After each merge: notes to `notes/enhmenu/`, runs to `runs/`, worktrees removed, branches kept, the Linux/Proton host sync and `blinx2 bench integrate --golden`, TASKS updated, cat `game.toml` re-pinned to the merged CLI sha (phases 4, 7, 8), the public pin gap (TASKS (c)) noted for the next push round.
- [ ] Before archive: rebuild specs/enhancements "Enhancements default to stock" from the current openspec/specs/enhancements text (config-layering and hud-pack wording, "Legacy pin still stock"), then re-apply this change's edits; openspec validate fails until then.
