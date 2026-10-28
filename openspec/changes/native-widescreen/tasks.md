Worktrees: `wt/<name>/xboxrecomp` (a branch off `posix-host/portability`), `wt/<name>/cat` (off `main`), and the b3 and ssx3 game worktrees for the probe registration.

- Raw runs go under `xbox-recomp/runs/native-wide/`.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock`, with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Proton runs on the Deck through `blinx2 bench`.

## 1. Spike (done unless marked)

- [x] 1.1 The EEPROM path. `kernel_xbox.c:150` answers 0x03 in the `XGetVideoFlags` domain, and every title's `XGetVideoFlags` returns 0. Index 8 is queried only by `XGetVideoFlags` in all four games.
- [x] 1.2 Per game: the flag reads, the in-game options and the effect of the widescreen bit (proposal table). b3 at stock: byte 0x4D617D reads 0 for the whole attract (`runs/native-wide/peek`).
- [ ] 1.3 Burnout 3 runtime confirmation.
  - Done: `RECOMP_POKE=0x4D617C:0x100` holds the byte at 1 and the attract frames change (`runs/native-wide/poke`, frames 8, 12 and 16 against `peek`), but attract replays are not frame-locked, so the squeeze is not yet shown on a fixed scene.
  - To do:
    - repeat on a fixed scene (a race-gate route or the options menu) with and without the poke;
    - `RECOMP_WATCH=0x4D617D` while toggling "Aspect Ratio" in the options, to pin the menu's writer and whether the item is gated on the flag.
- [ ] 1.4 SSX 3 runtime confirmation: `video_flags=0x00010000` on a fresh profile seeds Anamorphic (0x33925C bits 20-21 = 2). The in-game setting switches 0x33925C as decoded.


## 2. CLI first (the manifest rejects unknown tables)

- [ ] 2.1 `manifest.py`:
  - a `[display]` table with `native = "anamorphic" | ""` (default `""`);
  - `"display.widescreen"` in `TOOLKIT_ENHANCE_KEYS` (`manifest.py:331`);
  - `docs/manifest.md`.
- [ ] 2.2 `golden.py`: `("display.widescreen", ENHANCE_WIDESCREEN_RE, "off")` in `ENHANCE_STOCK` (`golden.py:1050`). The token is `display.widescreen=off|native`, the effective value (design D10).
- [ ] 2.3 The wizard (design D9) uses the existing `choice` kind, so no new kind is needed. Optional: `labels` for `choice` (today range-only, `RANGE_KEYS`), with a pytest and a Go test.
- [ ] 2.4 CLI gates: `uv run pytest tests`, ruff check and format, and `wizard/check.sh` (gofmt, vet, test, staticcheck, the double build) if the Go side changed.
- [ ] 2.5 Merge the CLI, then bump the `[cli]` pin in cat, b3, ssx3 and spartan before any of them declares `[display]` or a `display.widescreen` option.

## 3. Dashboard video flags (toolkit)

- [ ] 3.1 `kernel.h`:
  - raw-domain `XC_VIDEO_FLAGS_*` (widescreen 0x00010000, 720p 0x00020000, 1080i 0x00040000, 480p 0x00080000, letterbox 0x00100000, PAL-60 0x00400000);
  - the names `XC_VIDEO_FLAGS_HDTV` and `XC_VIDEO_FLAGS_PAL_I` removed;
  - a grep that nothing else uses the old values.
- [ ] 3.2 The native fields of `nv2a_host_opts` (`native_active`, `native_va/size/mask/wide`, `present_filter_native`), all 0 without the layer.
- [ ] 3.3 `xbox_video_flags_raw()`:
  - 0 stock, `| WIDESCREEN` when `nv2a_host_opts()->native_active`;
  - `RECOMP_DEBUG=video_flags=0x...` replaces it, logged once;
  - no `enhance_*` call.
  - `kernel_xbox.c` returns it, with a comment on why stock is 0. Its header comment (line 122) is fixed.
- [ ] 3.4 ctest:
  - the stock value is 0;
  - native adds only bit 16;
  - the debug key wins;
  - a model of `XGetVideoFlags` (`(raw >> 16) & 0x5F`) gives 0 and 1;
  - a build without the layer gives 0.

## 4. Native widescreen (toolkit)

- [ ] 4.1 `recomp_env.h`:
  - CONFIG `DISPLAY_WIDESCREEN` (`RECOMP_DISPLAY_WIDESCREEN`, `display.widescreen`);
  - DEBUG `video_flags`;
  - TRACE `native`.
  - Three rows in `cat/docs/env.md`, and the tier counts on its line 5 (config, trace, debug) updated.
- [ ] 4.2 `enhance.c`:
  - `enhance_native_register()`, accepted only before `xbox_enhance_init`, and after it logged and ignored;
  - parse `off` / `native` in `xbox_enhance_init`;
  - fill the `nv2a_host_opts` fields;
  - "no native widescreen registered; ignored" when nothing registered;
  - leave `aspect_w/h` at 0:0 with the "ignored" line when native is active (design D2);
  - `present_filter_native` from `enhance_cfg_source_of("present.filter")` (design D5);
  - `display.widescreen=<effective>` in the `[ENHANCE]` line.
  - A ctest covers both registration orders.
- [ ] 4.3 The present (design D5):
  - `nv2a_present_dar()`;
  - `nv2a_present_rect()` gains `dar_num, dar_den`, with a header note on the integer branch's return value;
  - callers: `fb_present_metal.m:365` and `nv2a_pb_d3d11.c:3836` pass the dar, `fb_present_sdl.c:751` passes `w, h` and logs `display.widescreen ignored` once;
  - check every caller's use of the "whole" return.
- [ ] 4.3a `nv2a_host_window_w`: a native case, `round(h * 16/9) * scale` while `native_active`, fixed for the run. `fb_present_sdl.c:556` passes the 4:3 width, with a TASKS.md note beside the Hor+ CPU window follow-up. A test covers stock, Hor+ and native.
- [ ] 4.4 D3D11: the `stock` and `same` `CopyResource` paths (`nv2a_pb_d3d11.c:3905-3930`) also require `dar == w:h`. `internal_resize` makes the 854-wide swap chain under native. The window's initial size follows.
- [ ] 4.5 Metal: the internal drawable size at `fb_present_metal.m:155-161` is `nv2a_host_window_w` under native, and the frame is blitted stretched into it. The window's initial size follows.
- [ ] 4.6 Tests:
  - `nv2a_present_rect` with `dar == w:h` equals today's result over a size grid;
  - dar stock = w:h, native with the probe on = 16:9 and off = w:h;
  - the fit rects for 16:9, 16:10 and 21:9 windows, and the integer branch.

## 5. The games

- [ ] 5.1 b3 (after the pin bump in 2.5):
  - `game.toml [display] native = "anamorphic"`;
  - a `[[wizard.option]]` of kind `choice`, `config = "display.widescreen"`, values `off` and `native`, default `off`, with the 16:9 wording in the label and hint;
  - the registration in `host_enhance_init` before `xbox_enhance_init` (0x4D617D, byte, 1);
  - the `config.default.toml` line;
  - a `scripts/test_*.py` case for the boot line.
- [ ] 5.2 ssx3: the same, with 0x33925C, mask 0x300000, wide 0x200000, in `recomp/src/main.c`.
- [ ] 5.3 cat and spartan:
  - a `[[wizard.option]]` of kind `choice`, `config = "display.aspect"`, values `4:3`, `16:9`, `16:10`, `21:9`, default `4:3` (matching `cat/packaging/config.default.toml:18`; Spartan's defaults file gains the `[display]` lines);
  - `config.default.toml` gains `widescreen = "off"`.

## 6. Hor+ frame copies (the speed-blur seam)

Superseded by `hor-plus-fullscreen-fx`. The probe found the 320x240 texture at 0x80A98000 is an R5G6B5 render target the game draws into, which Metal decoded from guest memory (no 16-bit `rt_texture`). One shared rule, `nv2a_rt_tex_reads()`, binds it on both backends, so no blit provenance or CPU-copy match is needed for Burnout 3.

- [x] 6.1 Probe: see `hor-plus-fullscreen-fx/proposal.md`.
- [x] 6.2 The rule: `nv2a_rt_tex_reads()` in `rt_texture()` on Metal and D3D11.
- [x] 6.3 Tests: `render_scale` ctest.

## 7. Menu grid strip

- [x] 7.1 Probe: open the b3 menus at 16:9 with `RECOMP_TRACE=aspect`, and classify the backdrop as (a), (b) or (c) of design D7.
  the tracker item (`runs/b3-hor-seams/trace1`..`trace7`): none of the three. It is case (d), added to D7: program `1B73FAD1` draws the grid (x 0..656) and the selection lines (x -271..911) at w 0.1 with the depth test off, classed 3D, so their overhang reached the pads through the 3D scissor.
- [x] 7.2 The rule for (a) or (b), in both backends, with tests (the HUD's centred placement unchanged). For (c), record it under the frustum limit in TASKS.md.
  For (d): toolkit `fix/b3-hor-seams` (`nv2a_aspect_flat`, Metal and D3D11, ctests in `tests/render_scale`). The flat layer keeps its centred place and takes the 2D scissor. Evidence: see the tracker item.

## 8. Overrides (fallback; moved)

Moved to mod-connectivity-layer tasks section 3, which builds the overrides as the first stage of the placement order (overrides first, not after the generic rules). The items below are kept for their details and are done there.

- [ ] 8.1 `[aspect.program]` (program hash, as the trace prints it) and `[aspect.texture]` (address, format, size):
  - in `config.default.toml`;
  - read only under a wide aspect;
  - consulted before the generic rules (mod-connectivity-layer D5);
  - a trace line per hit.
  - Each entry is commented with its scene and trace line. It is checked to keep its address across two boots, and in a second scene to make sure no pooled reuse of that address (same format and size) takes it.
  - Address keys are masked to the low 27 bits, as `rt_texture` does.
- [ ] 8.2 A ctest for the overrides parser in `tests/enhance_cfg`: keys, classes, a bad class, a bad key.
- [ ] 8.3 Use them only for what sections 6 and 7 leave. If nothing is left, ship the parser with no entries.

## 9. Gates

- [ ] 9.1 Mac build and `tests/posix_ctest.sh` 0 FAIL. For cat: `uv run pytest scripts` and ruff. The CLI's gates (2.4).
- [ ] 9.2 Stock goldens unchanged (the kernel answer is shared by every game):
  - BLiNX 2 on Metal and `blinx2 bench golden` (D3D11) on the Deck;
  - b3 stock goldens on Metal and on the Deck (D3D11).
- [ ] 9.3 Hor+ smoke runs:
  - BLiNX 2 at 16:9 and 16:10, Metal and Deck: no regression of the fixes;
  - b3 at 16:9, 16:10 and 21:9, Metal and Deck: the seam and the strip are gone.
- [ ] 9.4 Native smoke runs on Metal and Deck (internal surface on the Deck):
  - b3 with `display.widescreen = native`: race and menu at 16:9; at 21:9 (pillarboxed 16:9); with the in-game aspect switched back to 4:3, where the stretch follows;
  - ssx3 with Off, 16:9 and Anamorphic in its menu: the stretch only on Anamorphic.
- [ ] 9.5 Proton run, since it touches the kernel and the renderer. Speed within the 25% flag on D3D11 and Metal.
- [ ] 9.6 Archive `enhancements-hor-plus` before this change: its MODIFIED "Enhancements default to stock" adds `display.aspect`, which the main spec's key list still lacks, and this change's version builds on it.
- [ ] 9.7 Review. After the merge:
  - sync the Deck and run golden (`blinx2 bench integrate --golden`);
  - copy the agent's notes to `notes/native-wide/`;
  - remove the worktree (`git worktree remove --force`, `rm -rf wt/<name>`), keeping the branch;
  - update TASKS.md.

## 10. Upstream

- [ ] 10.1 Fork-only for now (the user, 2026-10-18).
  - The define fix and `xbox_video_flags_raw` (stock 0) stay out of the next upstream PR round, and are revisited at the upstream re-assessment.
  - The toolkit comments, the commit bodies and `docs/runtime/config.md` text for the define fix carry no tracker ids.
  - The native mode, the present stretch and the classifier rules stay on the fork's enhancements layer.
