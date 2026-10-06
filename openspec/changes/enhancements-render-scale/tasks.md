Worktrees: `wt/enh-scale/xboxrecomp` (toolkit, branch `enhance/render-scale` off `posix-host/portability` c1fa5a4) and `wt/enh-scale/cat` (cat, branch `enhance/render-scale` off `main` 730cfa6). Raw runs under `xbox-recomp/runs/enh-scale/`, never inside a worktree. No Linux/Proton host run in this round (in use by another agent): the Proton tasks stay open and are listed last. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`; headless runs use `SDL_AUDIODRIVER=dummy`.

## 1. Pure helpers and options (toolkit)

- [x] 1.1 `nv2a_backend_common.{c,h}`: `struct nv2a_host_opts` with `nv2a_host_opts_set`/`nv2a_host_opts` (zero = stock); `nv2a_host_size` (max-dim clamp); `nv2a_present_rect` (nearest/linear fit, integer with the linear-fit fallback); `nv2a_upscale_nearest32`; `nv2a_downscale_box32`; `nv2a_occ_set_scale` with the ÷N² in `occ_ready` (rounded, non-zero stays ≥ 1, `NV2A_OCC_VISIBLE` untouched).
- [x] 1.2 `src/platform/recomp_exe_dir.c` + declaration in `recomp_env.h` (or a small `recomp_exe_dir.h`): `const char *recomp_exe_dir(void)` via `_NSGetExecutablePath`/`GetModuleFileNameA`/`/proc/self/exe`, directory part, cached, CWD fallback.
- [x] 1.3 `tests/render_scale` (new ctest, standalone like `tests/nv2a_tex`): identity at N = 1 for every helper; host size at N = 2..4 and the max-dim clamp; present rects for fit, integer (640x480 in 1920x1080 → 1280x960 centred), integer fallback (1280x960 in 1024x768 → linear fit), odd sizes, exact fit (`rect == output`); box downscale of known patterns (N = 2, 3) and the 16-bit conversion input; nearest upscale round-trip (upscale then box-downscale returns the input); occlusion scaling (0, 1, 3, 4, large, `NV2A_OCC_VISIBLE`) at N = 1 and 2. Verify: `ctest` passes on the Mac.

## 2. Layer caller and keys (toolkit)

- [x] 2.1 `recomp_env.h`: `RECOMP_PRESENT_FILTER`, `RECOMP_PRESENT_FULLSCREEN` (config tier, enhance keys block).
- [x] 2.2 `src/enhance/enhance.c` + `enhance.h`: `xbox_enhance_init(root, title)`: `enhance_cfg_init`, binds, reads `render.scale` (clamp 1..4 with a log line), `present.filter`, `present.fullscreen`, `display.aspect` (non-4:3 logged as not implemented), `nv2a_host_opts_set`, one `[ENHANCE]` line, `enhance_cfg_report_unused`. CMake: `xbox_enhance` links `xbox_kernel`; nothing links `xbox_enhance` but the `xboxrecomp` interface (check with `grep` in the CMake files).
- [x] 2.3 `tests/enhance_cfg`: cases for the new keys (env over file, invalid filter falls back to nearest with a report, scale out of range clamps, bool spellings for fullscreen) and for `recomp_exe_dir()` (non-empty, exists, is a directory). Verify: `ctest` passes.

## 3. Metal render scale (toolkit)

- [x] 3.1 `RenderTarget`/`DepthTarget` `hw, hh` from `nv2a_host_size`; allocation, viewport and `s_self` at host size (match on `hw, hh`); creation upload upscaled at N > 1, direct at N = 1; `nv2a_vp_consts_fill`, `tex_scale`, `present_target` and `write_back`'s `bpp` stay guest.
- [x] 3.2 Flip: at N > 1 one host readback (`hw x hh`) serves the window (`PresentPixels(px, hw, hh, hw*4, 4)`) and the write-back (box-downscaled to `w x h`, 32-bit at the guest pitch or R5G6B5); N = 1 keeps today's two direct paths unchanged.
- [x] 3.3 Visibility tracker scale set from the options at `nv2a_occ_init`.
- [x] 3.4 CPU backend (and null): one log line when scale > 1, renders at 1×.
- [x] 3.5 Mac build; toolkit POSIX ctest dirs touched (`render_scale`, `enhance_cfg`, `nv2a_tex`, `nv2a_backend_smoke`) pass.

## 4. E1 on the SDL presenter (toolkit)

- [x] 4.1 `fb_present_sdl.c`: read `nv2a_host_opts()` once at start; `linear` = `SDL_SetTextureScaleMode(tex, SDL_ScaleModeLinear)` at texture creation on the existing logical-size path; `integer` = logical size off, destination rect from `nv2a_present_rect` with `SDL_GetRendererOutputSize`, recomputed on frame-size or `SIZE_CHANGED`, scale mode linear only while the fallback applies; `SDL_WINDOW_FULLSCREEN_DESKTOP` when `present.fullscreen`. The default path's SDL calls are unchanged (review item).
- [x] 4.2 Verify on the Mac: a stock `RECOMP_WINDOW_SHOT` has the same letterbox geometry as `main`'s (frame rect position and size in the shot); one shot per filter in a resized window and one fullscreen, saved under `runs/enh-scale/e1/`; `integer` in a 1920x1080 output shows 640x480 at 1280x960 centred.

## 5. cat wiring and bench

- [x] 5.1 `CMakeLists.txt`: `set(XBOXRECOMP_ENHANCE ON CACHE BOOL ...)` (no FORCE) before the toolkit `add_subdirectory`; `src/main.c`: `#ifdef RECOMP_ENV_HAVE_ENHANCE_KEYS` → `xbox_enhance_init(recomp_exe_dir(), NULL)` after `recomp_env_init()` on both entry paths. Verify: cat builds with the default and with `-DXBOXRECOMP_ENHANCE=OFF`.
- [x] 5.2 `analysis/golden/golden.json` global env pins `RECOMP_ENHANCE_CONFIG=none`, `RECOMP_RENDER_SCALE=1`; `scripts/golden.py` fails a run whose log has `[ENHANCE] render.scale=` other than 1 or `display.aspect=` other than 4:3 (and says so in the verdict). Verify: `scripts/test_*.py` for golden pass, with a new case for the `[ENHANCE]` check (fails on a synthetic log with scale 2, passes at 1 and with no line).

## 6. Verification at stock and at 2× (macOS, Metal)

- [x] 6.1 Stock identity: Metal goldens `@attract`, `@stage1`, `@story` on the layer-ON build pass with the same verdicts as `main`; record each frame's mae/bad-fraction beside `main`'s run in this file. `RECOMP_PB_FAST_AB` on the CPU backend, attract 60 s: zero mismatches (as on `main`).
- [x] 6.2 `golden.py` `[ENHANCE]` check exercised: one attract run with `RECOMP_RENDER_SCALE=2` must FAIL (size and the log check); the stock run must not.
- [x] 6.3 2× on Metal: attract and stage1 for 120 s each, no crash; window shots at 1× and 2× of the same flip in `runs/enh-scale/` (comparison pair, named by flip); `fb_dump_at` frames at 2× are 640x480 and within the golden limits via `golden.py` on that dump dir.
- [x] 6.4 Perf: flips/s, `[PRESENT]` ack-copy and upload ms/flip, `[PB-PERF]` flip ms at 1×, 2× and 4× (attract, `RECOMP_PRESENT_STATS=1`), recorded here; flag a 25% flips/s drop at 2× (memory rule) and decide whether the lazy write-back follow-up becomes a task.
- [x] 6.5 CPU backend at `RECOMP_RENDER_SCALE=2`: the ignore line appears once; `fb_dump_at` frames equal the 1× run's within the golden limits.

## 7. D3D11 render scale and E1 (toolkit; code and cross-build now, Proton later)

- [x] 7.1 Targets, viewport and self-copy at host size; `read_pixel` coordinates scaled; `px_probe` MRTs at host size and coordinates scaled; occlusion scale at init.
- [x] 7.2 Present: `WM_SIZE` recorded in `wnd_proc`, `ResizeBuffers` at the next flip (ack thread, `s_back` released and re-acquired); direct `CopyResource` + back-buffer dump when sizes match and the filter is nearest/integer k = 1 (today's code); otherwise clear, full-screen-triangle blit (point/linear sampler, RT SRV on demand) into `nv2a_present_rect`'s viewport and `dump_frame` reading the RT; `present.fullscreen` → `WS_POPUP` at the primary monitor's size. The first-flip `[D3D11]` log line names the back-buffer size.
- [x] 7.3 llvm-mingw cross build of the toolkit and cat (`XBOXRECOMP_ENHANCE` ON and OFF). Verify: both link clean, no new warnings.

## 8. Docs

- [x] 8.1 cat `docs/env.md`: rows for `RECOMP_ENHANCE_CONFIG`, `RECOMP_RENDER_SCALE`, `RECOMP_DISPLAY_ASPECT`, `RECOMP_PRESENT_FILTER`, `RECOMP_PRESENT_FULLSCREEN` (config tier; the tier count in the header updated; `RECOMP_WINDOW_SCALE`'s row says "window size in points, see present.filter").
- [x] 8.2 toolkit `docs/runtime/enhance-config.md`: the config root is the executable's directory (and how `RECOMP_ENHANCE_CONFIG` overrides it), the two present keys, what scale does per backend (CPU ignores it), the sharper-post-pass caveat, dumps at host size under scale and goldens stock-only, `recomp_exe_dir` for other titles.
- [x] 8.3 cat `TASKS.md`: follow-ups (D3D11 Proton verification 9.x, Win32 GDI window E1, lazy write-back and zero-copy Metal present if 6.4 says so, fullscreen hotkey with `input-selection`, deviations row when `deviations-register` lands, `golden.py` downsample option as a nicety); `RESUME.md` notes the config root decision.

## 9. Review, merge and cleanup

- [ ] 9.1 Fable review of both branches before merge, with the R4 checklist: every new backend/presenter statement behind `scale > 1`, a non-default filter, `fullscreen` or a size mismatch; no link from `xbox_kernel`/`xbox_d3d8`/`xbox_video` to `xbox_enhance`; env rows present. Fixes go back to this branch's agent.
- [ ] 9.2 After merge: copy untracked notes to `notes/enhancements-render-scale/`, keep `runs/enh-scale/`, remove `wt/enh-scale` (`git worktree remove --force` + `rm -rf`), keep the branches; sync and rebuild the Linux/Proton host (`scripts/bench.sh integrate`) and run golden under the run lock; update `TASKS.md`.

## 10. Open: Proton verification (the Linux/Proton host, when free)

- [x] 10.1 D3D11 `scripts/bench.sh golden` at stock: attract, stage1, story pass with the same verdicts as `main`; `check_present_mismatch` passes; the first-flip line shows a 640x480 back buffer (or, if the compositor resized it, the run still passes).
- [x] 10.2 `RECOMP_RENDER_SCALE=2` attract:
  - [x] the `d3d11_dump` frame is 1280x960 and visibly sharper than the 1× frame (pair saved under `runs/enh-scale/d3d11/`);
  - [ ] window resized (`xdotool windowsize`) with each filter. **Blocked by Wine:** Wine 11's x11drv never applies an external resize, so the game gets no WM_SIZE (Proton verification below). Open in TASKS.md;
  - [x] fullscreen;
  - [x] flips/s 1× vs 2× against `render-gpu-backend` 3.2.
- [x] 10.4 Proton checklist (from the Fable review; each item a log line or a dump to look at):
  - The first-present `[D3D11]` line names the path actually taken: `copy` at stock 640x480; `copy` for 2x in a 1280x960 window with nearest or integer; `scaling blit` otherwise. Integer with an exact-size frame must say `copy`.
  - `xdotool windowsize` per filter (nearest, linear, integer): `window resized: swap chain WxH` appears, no `ResizeBuffers ... hr=` line and no `no back buffer` line; the frame is letterboxed or centred as the filter says.
  - The blit shaders compile (no `nv2a_present_vs`/`nv2a_present_ps` compile error) on Wine's d3dcompiler_47.
  - Draw state after the first blit: the next frame's draws are unaffected (the blit resets `s_sc_init`). Compare a stock-option frame before and after one resize.
  - `present.fullscreen` under Wine/Gamescope: a WS_POPUP at the monitor size, the frame placed by the filter, no exclusive-mode flicker.
  - The 2x `d3d11_dump` is 1280x960 (the RT), and `px_probe` coordinates hit the same guest pixels as at 1x.
  - Burnout 3 at stock and at 2x (10.3).
- [ ] 10.3 Burnout 3 (`b3/`) at stock and `RECOMP_RENDER_SCALE=2` under Proton: menu script runs, 1× unchanged, 2× renders (eyeball the dump); the upstream gate for the common and D3D11 parts.

## Results (2026-10-04, macOS Metal unless noted)

Toolkit `enhance/render-scale`: 10ed25c helpers, 55a7590 layer + keys + `recomp_exe_dir`, d0b1236 Metal, 5f4fec7 CPU log line, ea0f579 SDL E1, f3cba8f D3D11, 2317308 docs. Raw output: `xbox-recomp/runs/enh-scale/`.

**6.1 stock goldens, main (c1fa5a4 + 730cfa6) vs this branch** (mae R/G/B, bad fraction). All pass on both; exit 0.

| frame | main | branch |
|---|---|---|
| attract-title | CLOSE 2.905/1.915/1.622 | CLOSE 1.961/1.343/1.320 (wall-time cloud movie) |
| attract-cliff | CLOSE 0.192/0.209/0.226, 0.0042% | identical |
| stage1-stick | CLOSE 0.506/0.490/0.459, 1.25% | CLOSE 0.202/0.217/0.230, 0.0072% |
| stage1-enemies | CLOSE 4.867/4.637/3.962, 13.66% | CLOSE 7.902/7.351/6.044, 18.34% (limit 35%) |
| stage1-hud | CLOSE 1.353/1.251/1.082, 2.12% | CLOSE 1.448/1.306/1.154, 2.47% |
| story-tsedit (`*-story2`, `--slack 70`) | CLOSE 0.014/0.013/0.049 | identical |
| story-menu (`*-story2`, `--slack 70`) | CLOSE 0.807/0.654/0.617, 0.75% | identical |
| story-hub (`*-story2`, `--slack 70`) | CLOSE vs hub-a | CLOSE vs hub-b |

Story was INCOMPLETE on both main and the branch with the default dump slack (the anchor lands about 40–50 flips after the reference); both pass with `--slack 70`. This is a harness issue, not caused by this change. The differences between main and the branch are within the run-to-run spread of these timing-driven scenes. FAST_AB, CPU attract 60 s: main 4000 batches with 0 mismatches; branch 4000 batches with 0 mismatches.

**6.2** `golden.py` FAILs the 2× runs with `not a stock run (render.scale=2 ...)`. The stock runs pass.

**6.3** 2× attract and stage1, 120 s windowed: no crash (1×/2×/4× attract also 120 s, no crash). The comparison pair is `runs/enh-scale/compare/stage1-flip900-{1x,2x}.png`, with crops in `stage1-flip900-{1x,2x}-detail.png`. `fb_dump_at` frames at 2× are 640x480. Checked against the goldens with the `[ENHANCE]` line stripped:

| frame | result | measured | limits |
|---|---|---|---|
| attract-title | CLOSE | | |
| stage1-stick | CLOSE | mae 1.80, bad 3.79% | |
| stage1-enemies | CLOSE | | |
| attract-cliff | FAIL | mae 1.62, bad 3.05% | 0.5 / 0.5% |
| stage1-hud | FAIL | mae 4.18, bad 10.5% | 3.0 / 8% |

Deviation from the "within limits" wording: the diff masks (`compare/*-diffmask.png`) show only geometry edges and minified texture detail, which is the expected supersampling difference, and no shift or misplacement. The golden limits are tuned for stock rendering, which is why goldens stay stock-only.

**6.4 perf**, windowed, 3D flips, the game paced at 30 Hz:

| run | walk mean (ms) | on_flip mean (ms) | flips/s | ack copy (ms/flip) |
|---|---|---|---|---|
| attract 1× | 6.75 | 1.96 | 30.3 | 0.027 |
| attract 2× | 9.03 | 4.22 | 29.7 | 0.078 |
| attract 4× | 18.27 | 13.35 | 28.3 | 0.291 |
| stage1 1× | 7.81 | 1.75 | 29.1 | |
| stage1 2× | 10.52 | 4.17 | 28.4 | |

Wall p50 is about 32.5 ms everywhere. There is no 25% flips/s drop at 2×. The 4× on_flip of 13 ms (one readback, the box downscale and the upload) leaves little headroom, so the lazy write-back and zero-copy present goes into TASKS.md.

**6.5** CPU at 2×: the ignore line appears once, and the frames are 640x480. attract-cliff is CLOSE at 0.185 (as at 1×). attract-title is INCOMPLETE on pace, a known CPU harness artefact.

**4.2** Shots are in `runs/enh-scale/e1/`, attract flip 300.
- Stock shots at window scale 1 and 2 have the same frame rect as main's (the full 1280x960 and 2560x1920 outputs). The pixel differences between main and the branch (1.43% and 5.33%) are run-to-run content differences.
- `linear` differs from nearest in 6.40% of pixels and is visibly softer.
- `integer` at window scale 1 fills 1280x960 (k = 2). `integer` at render scale 4 falls back to a fit.
- In a 3840x2436 fullscreen output, `integer` gives 3200x2400 at (320,18), k = 5, centred. At 2× render it gives 2560x1920 at (640,258).
- The 1920x1080 output in the task wording was not available on this display. The unit test covers it (1280x960 centred).
- Under fullscreen `nearest` the frame appears left-aligned in the shot only because `SDL_RenderReadPixels` reads relative to the logical-size viewport. This quirk is in the unchanged stock path of the window-shot code (follow-up in TASKS.md).

**7.x D3D11 notes.**
- With stock options and an unresized 640x480 back buffer, the flip is today's code byte for byte: `CopyResource` for a 640x480 frame, and the overlap `CopySubresourceRegion` for another frame size. This is the R4 guarantee.
- A back buffer that the window or compositor resized now gets the scaling blit, and the dump reads the RT, even at stock options. Today it got the overlap copy.
- `integer` with an exact-size frame (k = 1) keeps `CopyResource`, as the design allows.
- Proton is not run this round (10.x).
- 7.3: llvm-mingw cat+toolkit builds link clean with `XBOXRECOMP_ENHANCE` ON and OFF; the Mac build with OFF also links. The only warning in a touched file is the pre-existing `writes_back` initializer (nv2a_pb_d3d11.c). Logs are in `runs/enh-scale/build-{win-ON,win-OFF,mac-OFF}.log`.

**Fable review fixes (2026-10-04).**
- Toolkit: 54d0c16 occlusion rounding at scale 3 (a count of 4 rounded to 0; it is now clamped to 1, with tests). 5b17037 D3D11: the first-present log names the path taken, a lost back buffer is guarded, stock is compared against the created size and windowed. 7c1839e Metal: the host readback is gated on a write-back or a window. cb5ac1a docs: the box filter works in gamma space.
- Not done, review item 3: a nearest blit that shrinks the frame stays point-sampled. `nearest` means nearest on both backends, and `linear` is the choice for a smooth downscale. Doing it in SDL would add output-size tracking to the stock path.
- Re-verified on the Mac: `render_scale`, `enhance_cfg`, `nv2a_tex` and `nv2a_backend_smoke` pass (4 scenes identical). Metal stock golden `@attract` and `@stage1` gave CLOSE on every frame (cliff 0.192 and stick 0.506, the same as main; hud 1.377 vs main 1.353) (`runs/enh-scale/fix1-*`). A 2x headless attract still writes back 640x480 dumps, and golden rejects it as not stock. llvm-mingw ON and OFF link, with only the pre-existing warning.

**Proton verification (2026-10-05, the Linux/Proton host, GE-Proton 11, KWin Wayland + XWayland).** The tree is ~/recomp-enhscale, with its own prefix. Raw output is in `runs/enh-scale/proton/`.

*Stock golden (`bench.sh golden`)*
- golden1 (toolkit cb5ac1a, cat b23a179): attract and stage1 pass. Story is INCOMPLETE: the anchors landed outside the dump window (tsedit -52, slot-list +491, hub -119). The same intermittent drift shows in the b3gate control history.
- golden3 (same build): **pass**. title CLOSE 1.955, cliff EXACT, stick 0.177, enemies 8.38, hud 1.149, tsedit 0.000, menu EXACT, hub CLOSE.
- golden4 (cat 9714bd5, the stdio fix): **pass**. title 1.956, cliff EXACT, stick 0.177, enemies 8.28, hud 1.194, tsedit 0.000, menu 1.231, hub CLOSE. Proton tests pass, and the present mismatch is 0 in every run.
- golden2 was cut off by the agent's own shell limit, not by the game.

*10.4 checklist*
- **First-present line.** Stock 640x480 says `copy`. At 2x windowed: `back buffer 640x480, frame 640x480 (1280x960 host), scaling blit`. Fullscreen: `back buffer 1506x847 ..., scaling blit`. All correct.
- **Resize per filter: blocked by Wine, not reachable from our code.**
  - Wine 11's x11drv logs `handle_state_change ... unexpected config` for every external resize and never applies it, so the game gets no WM_SIZE. This happens both for `xdotool windowsize` and for a KWin-scripted frameGeometry change (the path a border drag takes). The window does change size on screen (xwininfo 1000x672, 1600x972 ...); there is no `window resized`, no `ResizeBuffers hr=` and no `no back buffer` line.
  - The resize code itself is exercised by nothing under this Proton. It is recorded in TASKS.md.
- **Blit shaders compile** on Wine's d3dcompiler (vkd3d): no compile error or `FAILED` line in any blit run (2x windowed, fullscreen integer, fullscreen linear 2x).
- **Draw state after the first blit.** The px probe at flip 1141, long after the first blit, gives the same draw (prog F9BE5B67) and the same inputs at 1x and 2x: D0/T0-T3 within 1e-3, output 00ADA37C vs 00ACA37C. Golden-identical rendering continues after blits.
- **Fullscreen under Wine.** `present.fullscreen=1` creates a 1506x847 WS_POPUP back buffer (Wine's screen size at the 1.7 XWayland scale), with integer at 1x and linear at 2x. It runs clean: no errors, mismatch 0, wall p99 51 ms.
- **2x dump and px_probe.**
  - `d3d11_dump` frames are 1280x960 at 2x and 640x480 at 1x. px_probe reports `pos 640.5 480.5` at 2x vs 320.5 240.5 at 1x for the same guest pixel.
  - The 2x frame is visibly sharper: `runs/enh-scale/proton/compare/d3d11-{1x,2x}-detail.png`, dump 19 of each run.
- **Window shots** are not available: spectacle over ssh returns a blank frame under KWin. Placement is checked by the logs only.

*Found and fixed*
- Under Proton the `[ENHANCE]` lines were printed before the `RECOMP_STDIO_LOG` redirect and were lost, so golden.py could not flag a non-stock D3D11 run.
- Fix: cat 9714bd5 `main: set up RECOMP_STDIO_LOG before the enhancements layer reports`. Re-verified: the 2x Proton log has `[ENHANCE] render.scale=2 ...`, `enhance_nonstock` returns `render.scale=2`, and golden4 passes.

*Perf, D3D11 attract, 3D flips*

| run | walk (ms) | present (ms) | wall p50 (ms) |
|---|---|---|---|
| 1× | 11.55 | 0.92 | 33.2 |
| 2× | 11.71 | 1.22 | 32.7 |

There is no flips/s drop (30 Hz paced).

*Skipped* by instruction: Burnout 3 (10.3).
