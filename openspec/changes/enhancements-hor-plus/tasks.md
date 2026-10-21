Worktrees: `wt/hor-plus/xboxrecomp` (branch `feat/hor-plus` off `posix-host/portability` 878d473a) and `wt/hor-plus/cat` (branch `feat/hor-plus` off `main` 4317f84).

- Raw runs go under `xbox-recomp/runs/hor-plus/`.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock`, with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Proton runs on the Deck through `blinx2 bench`.

## 1. Shared helpers (toolkit)

- [x] 1.1 `nv2a_backend_common`:
  - the `aspect_w/h`, `hud_mode` and `movie_mode` fields of `nv2a_host_opts`;
  - `nv2a_host_pad`;
  - the pad term in `nv2a_vp_consts_fill`;
  - `nv2a_aspect_full_width`, `_picture`, `_place` and `_anchor`.
- [x] 1.2 `nv2a_aspect.c`:
  - the gate and `nv2a_aspect_due`;
  - `nv2a_aspect_scan` (the interpreter);
  - `nv2a_aspect_full_tris`;
  - `nv2a_aspect_anchor_tris`, with pieces, the seed, cluster propagation and layout frames, plus `nv2a_aspect_layout_note`;
  - `nv2a_aspect_map` and `nv2a_aspect_box`.
- [x] 1.3 `enhance.c`: the `display.aspect`, `display.hud` and `display.movie` parsing and the summary lines. `recomp_env.h`: the three CONFIG rows, the `aspect` trace and the `metal_host_dump` debug key.
- [x] 1.4 MSL and HLSL combiners: `+ tex_scale[k].w` on u, behind key bit `rt_offset` (absent at stock).
- [x] 1.5 `tests/render_scale`:
  - the pad, mapping, box and placement cases;
  - the picture test;
  - the screen-layer test (`nv2a_aspect_layer_w`, and a scan at w 3 and at a depth per vertex);
  - the anchoring cases (quad, string, thirds, wide piece, empty);
  - cluster propagation over frames 1, 2 and 3 and stale frame 9;
  - layout frames 20 to 23.
- [x] 1.6 CPU rasteriser: one `display.aspect ... ignored` line (`nv2a_pb_exec.c`).

## 2. Metal (toolkit)

- [x] 2.1 `nv2a_pb_metal.m`. Change inventory, every site behind `rt->pad`, `n > 1` or a placement other than CENTRE:
  - `RenderTarget`'s `pad` and `n`; `rt_grow` and `rt_seed` into the centre columns; the depth target size;
  - the clear's pad offset;
  - the scan, full-width and picture tests;
  - placement, layout note, anchoring and runs (one `drawIndexedPrimitives` per run, each with its mapping and scissor);
  - `tex_scale` for padded sources;
  - the write-back from the centre columns (`write_back_scaled`);
  - the present extent;
  - the flip line (`hor+`, off-centre and split counts);
  - `metal_host_dump`;
  - the `[aspect.program]` trace.
- [x] 2.2 The corner-triangle batch: per-triangle full width (`nv2a_aspect_full_tris`), checked on the title screen.
- [x] 2.3 Edges mode: cluster propagation (the stage1 status panel), layout frames (the locker room), the picture test (the 16x16 fade quad that otherwise made every stage frame a layout frame) and screen layers (the panel's frame and lamps at w 3 and 2, which the w == 1 test left centred; `runs/hor-plus/trace6`).
- [x] 2.4 16:9 review on Metal. Side-by-side frames under `runs/hor-plus/review/` (never published):
  - 4:3, 16:9 centred and 16:9 edges, for the attract demo (title, movie), stage1 (3D and HUD), the story hub (a menu) and a cutscene;
  - `display.movie` set to `fit` and `fill` on the movie.
  Done in `runs/hor-plus/review/final` (rev3, toolkit 6074bb83): attract 600 and 1020, the movie at 600 (black, fit, fill), stage1 1800, and story 1140, 1560, 2040, 3600 and 4320.

## 3. Verification on the Mac (Metal)

- [x] 3.1 Stock: the Metal goldens `@attract`, `@stage1` and `@story` pass with the same verdicts as main, and no log has a `hor+` line. `runs/hor-plus/golden-stock`: attract, stage1 and story pass (toolkit rebased on 7b79ed3d).
- [x] 3.2 The toolkit POSIX ctests (`tests/posix_ctest.sh`), 0 FAIL. 79 pass. `apu_voice_lock` failed once at JOBS=8 (its wake-timing check, under load) and passed 3 of 3 alone.
- [x] 3.3 Cost (spec "Hor+ cost"): `RECOMP_TRACE=metal_prof,pacing` at stock, 16:9 centred and 16:9 edges, in `runs/hor-plus/perf2/`. Record GPU ms per flip, flip p50 and p95, and process CPU per scenario here. PB-PERF per flip after flip 10 (walk and draw, mean / p95 ms), metal_prof GPU ms per flip:

  | scenario | variant | walk | draw | GPU |
  |---|---|---|---|---|
  | attract | stock | 3.88 / 12.36 | 1.41 / 4.84 | 0.135 |
  | attract | centred | 3.90 / 13.82 | 1.43 / 5.08 | 0.123 |
  | attract | edges | 4.02 / 15.14 | 1.43 / 5.02 | 0.126 |
  | stage1 | stock | 8.71 / 18.70 | 3.81 / 6.08 | 2.268 |
  | stage1 | centred | 8.79 / 19.02 | 3.96 / 6.21 | 2.103 |
  | stage1 | edges | 8.74 / 18.55 | 3.92 / 5.92 | 2.078 |
  | story | stock | 3.27 / 9.34 | 0.93 / 2.62 | 0.529 |
  | story | centred | 3.43 / 10.71 | 0.93 / 2.69 | 0.533 |
  | story | edges | 3.48 / 10.61 | 0.94 / 2.73 | 0.535 |

  The worst ratio is attract edges' walk p95, at 1.22x; every figure is under the 1.5x limit. Process CPU is 113 to 128% in every variant, and flip counts match stock. Story centred is from `perf3` (perf2's run was slow throughout). The figures predate the screen-layer test, which runs further only for a batch whose first w is whole.

## 4. D3D11 mirror (toolkit)

- [x] 4.1 `nv2a_pb_d3d11.c`:
  - padded `RenderTarget` and `DepthTarget`, plus `rt_grow`;
  - the partial clear;
  - the gathered scan inputs (`vtx_input`, skipped when `nv2a_aspect_due` says no);
  - placement, layout note, anchoring and runs (`set_vp` + `DrawIndexed` per run);
  - `tex_scale.w` in the basic shader and `tex_uv`;
  - the `read_pixel` and `px_probe` offsets;
  - the present blit;
  - the `hor+` flip line.
- [x] 4.2 Cross-build with llvm-mingw on the Mac (`blinx2 build windows`). Clean on the rebased toolkit (`--stale-gen-ok`: the worktree's gen key, the same gen the Mac build uses).
- [x] 4.3 On the Deck under Proton:
  - `blinx2 bench golden` at stock, with the same verdicts as main;
  - 16:9 centred and edges `d3d11_dump` frames of `@stage1` and `@story`, compared with the Metal host dumps of the same flips;
  - the cost figures as in 3.3.

  Exe from the Mac cross-build at toolkit 671db696, Deck scratch `~/hor-plus-bench`, GE-Proton11-7:
  - Stock golden: attract, stage1 and story pass (bench-logs 20261017-195657, -195818, -200008). Flips/s 31.7, 30.6 and 47.0, as on the earlier tip (-194113, -194233, -194423). The bench's Proton test step is not run: it compiles on the host, and the Deck never builds.
  - 16:9 centred (-200158, -200349) and edges (-200537, -200727): back buffer 854x480, whole copy. Flips/s 30.6 and 46.9, the same as stock. The `d3d11_dump` frames (`runs/hor-plus/deck2/`) match the Metal host dumps for stage1 and story.
  - 16:10 centred stage1 (-200929): back buffer 768x480, 30.3 flips/s.
  - Before the window fix (-194644 to -195212), the windowed copy showed the left 640 columns of the 854-wide target.
- [x] 4.4 Window size (the user, 2026-10-17): the window takes the padded frame's shape on D3D11, SDL and Metal (`nv2a_host_window_w`, render_scale cases). Metal at 16:9 opens 1708x960 points (window shot `runs/hor-plus/win169b`). At 21:9, 2240x960 points is wider than the Mac screen and is clamped by macOS, which letterboxes the frame (`runs/hor-plus/uw`).

## 5. cat wiring and docs

- [x] 5.1 `docs/env.md`: the `RECOMP_DISPLAY_ASPECT`, `RECOMP_DISPLAY_HUD` and `RECOMP_DISPLAY_MOVIE` rows, plus the `aspect` trace and `metal_host_dump` (`scripts/test_env_doc.py`).
- [x] 5.2 `packaging/config.default.toml` `[display]`: the three keys, commented, at their defaults. Toolkit `docs/runtime/config.md`: the rows and the Hor+ section.
- [x] 5.3 `TASKS.md`:
  - the projection follow-up (pop-in at the edges) after free-camera M0;
  - the CPU backend ignores the keys;
  - `display.movie` `frame` and `blur` (design H7);
  - D3D11 status.
- [x] 5.4 `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`. 80 pass, plus the environmental `test_gitignore` failure (`game_files` is a symlink in a worktree; it passes in the main checkout). Ruff clean.

## 6. Review and merge

- [x] 6.1 Review of both branches (MERGE WITH FIXES). Fixed on the branch: toolkit 4228d248.
  - `flat_rt`: a full-width pass over an unpadded render target is centred (render_scale case). D3D11's self copy keeps the frame's pad, as Metal's does.
  - `rt_offset` cases in `d3d8_msl_split` and `d3d8_hlsl_split`.
  - `display.aspect` must be the whole value (`enhance_cfg` case for `16:9x`).
  - Documented in design.md Risks: the present crop for an extent narrower than the target, and the CPU backend's padded window (both TASKS follow-ups), Burnout 3's 640x464 frame (no pad), the `black` pads, occlusion counts and the w test.
  - Gates: posix_ctest 78 pass, 0 FAIL. Mac build and Windows cross-build clean (no new warnings). Metal stock `@attract` golden passes with no hor+ line (`runs/hor-plus/golden-fix`). A Metal 16:9 stage1 window shot at flip 1800 has the same placement as before the fix (`runs/hor-plus/fix169`); only the timer and the animation differ.
- [ ] 6.2 Squash-merge both branches; copy notes to `notes/hor-plus/`; remove the worktrees.

## 7. Deck artefacts at the old 4:3 edge

The user's Deck run (cat 9eb1445, toolkit f98fc579, D3D11 under Proton, 16:10, `hud = centred`, `movie = black`, scale 2, linear, fullscreen) showed four artefacts, all at x = 107 and x = 1173 of 1280, at scale 1 too. Worktrees `wt/hor-plus-fix/{xboxrecomp,cat}`, branch `fix/hor-plus-scale`; raw runs in `runs/hor-plus-fix/`.

- [x] 7.1 Causes:
  - **Hub stairs tearing on the right, and the hub's far edges.** The hub's stair pit and floor reflections are drawn as the mirrored 4:3 view into an unpadded 512 square and sampled at the fragment's screen position. In the pads that position is u < 0 or u > 1, which clamps to the square's edge column: a smeared seam at the old edge, on both backends and at any scale.
  - **1-1 water tint stops at the 4:3 edge.** The same pass. The sea and pond take their tint from the reflection square, so in the pads the water showed the clamped edge column; the edge is wavy because the water's normals perturb the lookup (user shot 212544: the pond's green ends at x = 75 of 900, the 4:3 edge).
  - **1-1 objects pop at the edges.** The guest's 4:3 frustum cull, as documented (design Non-Goals). Every 3D batch's host scissor already covers the pads and both backends draw all they are given; the guest submits within 2% of the stock batches at 21:9. Widening the cull needs the camera and projection build: not cheap, not built (follow-up after free-camera M0).
  - Checked and ruled out (coordinator lead): the SURFACE_CLIP scissor (72e5429a) and `nv2a_aspect_box` give these passes the full padded scissor; no 3D batch here had a clip box other than 0..w; CLIPPLANE (7b79ed3d) kills by texcoord plane distances, so it needs no pad remap.
- [x] 7.2 Fix (toolkit db83e597): `nv2a_host_pad` pads square targets as well as 4:3 ones, by the same share of the width (design H1). The mirrored pass reaches the pads through the centred mapping, and a batch sampling the square gets the usual `rt_offset`, so texel reads in [0, 1] are unchanged; full-width passes over the squares now stretch (none was found: 7.6). Stock and 4:3 keep pad 0, so stock output is unchanged; the HUD-in-pads guarantee is unchanged (2D placement does not change for 4:3 targets). `tests/render_scale`: pad cases for 512 and 256 at 16:9 and 16:10, 512x256 (no pad), 512 at 4:3 and stock (0).
- [x] 7.3 `display.hud` value `centred` becomes `centered`, no alias (toolkit 0d3f42ad, cat ff32ae3): an old `centred` is reported and the default (the same layout) is used. `enhance_cfg` cases.
- [x] 7.4 Before/after (16:10 and 16:9, Metal and Deck D3D11): `runs/hor-plus-fix/cmp/`
  - Deck D3D11 16:10 scale 2 hub stairs: `dst_b.png` (seam at x = 1406 of 1536) and `dst_a.png` (continuous).
  - Metal hub: `b_r.png` and `a_r.png`; 1-1 beach: `b_sea_l.png` and `a_sea_l.png`; the sea after the fix across both pads: `p3_02380.png`, `p2_02250.png`.
  - Deck D3D11 16:9 scale 1, 1-1: `d11-169b/` and `d11-169a/` frames.
  - The pond itself was not reached by a scripted walk; the sea uses the same reflection pass and is fixed.
- [x] 7.5 Gates: Mac build clean (pre-existing warnings only); `tests/posix_ctest.sh` 78 pass, 0 FAIL; cat pytest 119 pass plus the worktree-only `test_gitignore`, ruff clean; Metal stock golden attract, stage1 and story pass (bench-logs 20261017-224311, -224339, -224459). Deck D3D11 stock golden (Mac cross-build at toolkit 0d3f42ad, GE-Proton11-7) attract, stage1 and story pass at 31.8, 30.7 and 47.0 flips/s, as before the fix (bench-logs 20261017-224646, -224811, -225001); the bench's Proton test step is not run, as the Deck never builds.
- [x] 7.6 Review fixes (toolkit 992e6ad1):
  - D3D11 applied the `rt_offset` tex_scale only while drawing into a padded target; it now applies it whenever the sampled target is padded, as Metal does, through the shared `nv2a_rt_guest_read`.
  - Squares skip `display.hud = edges` (and its layout note) on both backends and are placed with `display.movie = black`: they are reflection, glow or shadow maps, never a HUD or a movie.
  - `tests/render_scale`: the 21:9 square (512 -> 192), small squares at 16:9 (1, 2, 4, 16 -> 0, 0, 1, 3), the frame's read edge reaching the padded square's edge through `nv2a_rt_guest_read` (within 1 texel: both pads round to whole pixels), and a full-width pass over a padded square with no `flat_rt` stretching.
  - Trace (`RECOMP_TRACE=aspect`, 16:9, Metal, hub then 1-1, `runs/hor-plus-fix/m169tr`): no 2D batch drew into or sampled a 256 or 512 square; the stretched passes sampling a render target are the 320x240 and 640x480 glow passes (C8AF571F, 489640CD), with no seam at x = 107 or 747.
  - Burnout 3 race at 16:9 on Metal (`runs/hor-plus-fix/b3m169h`): Hor+ on a 640x480 target with pad 107, the HUD on its 4:3 columns, nothing squeezed or seamed from the squares; a pre-existing seam from a glow composite over a guest-memory copy (TASKS). D3D11 untested on Burnout 3.
- [x] 7.7 Gates at toolkit 992e6ad1: `tests/posix_ctest.sh` 78 pass, 0 FAIL; Metal stock golden attract, stage1 and story pass (bench-logs 20261017-232807, -232833, -232952); Deck D3D11 stock golden (Mac cross-build at toolkit 992e6ad1, GE-Proton11-7) attract, stage1 and story pass at 31.7, 30.6 and 47.0 flips/s, unchanged (bench-logs 20261017-232807, -232926, -233117); the bench's Proton test step is not run, as the Deck never builds.
- Follow-ups (TASKS.md): the cull widening; a green slab in the outer 16:9 pads on 1-1, game geometry outside the 4:3 view, present before and after the fix; cube and 3D stages bound to a render target skip `tex_scale` and `rt_offset`; Burnout 3's glow-composite seam; Burnout 3 on D3D11.

## 8. HUD flicker, loading screen and water edge under `hud = edges`

The user's Deck run at 16:10 with `hud = edges` showed three faults: on single frames the 1-1 HUD drew centred, the loading screen's panels were cut and spread across the padded width, and the water's effect ended visibly at the viewport's edge. Worktrees `wt/hor-plus-edges/{xboxrecomp,cat}`, branch `fix/hor-plus-edges`; runs in `runs/hor-plus-edges/agent/`.

- [x] 8.1 Causes (Metal, 16:10, `RECOMP_TRACE=aspect`):
  - **HUD flicker.** The HUD program draws two-triangle quads parked off the layer, at x = 1e5 to 1e8, about every 2 to 2.5 s. The layout rule measured a piece's box unclipped, so such a quad passed "piece >= w*h/3", flagged its frame and the next as layout frames, and the HUD drew centred for those frames.
  - **Loading screen.** It is 40 to 48 one-tile batches (program 5474DB2A) with its panels parked off-screen before they slide in; no single piece reaches a third of the frame. Once the B2913952 backdrop stops (and with the warp out of 1-1 there is none), no rule fired and each tile was anchored to its own third.
  - **Water edge.** The water bumps its reflection read (1-1's BUMPENVMAP matrices move u by up to 0.106 of the square's width), so at the frame's edge it reads past the ratio's square pad and clamps to the square's edge column.
- [x] 8.2 Fix (toolkit 25848cb9), design H1 and H6 item 4:
  - `nv2a_aspect_piece_cover` clips a piece to the frame's height and to [0, w] (inside) and [-w, 2w] (parked panels); a piece more than 4w by 4h, or wholly beyond a frame's width or height off the layer, is off-layer: placed centred, not counted, not recorded.
  - A frame is a layout frame when one piece covers a third of the layer inside, or the pieces' clipped areas sum to the layer (to half of it the frame after a layout frame, so a slide-out stays centred). The sum is a count of area: measured gameplay HUDs reach 22 to 26%, dialogue 36%, the mission list 52%, the loading screen 110 to 163%.
  - Square pads add an eighth of the width a side (16:10: 512 -> 115, 256 -> 58; 16:9: 149, 75; 640x480 keeps 64), five texels of a 256 square beyond the bump offset; every read goes through `nv2a_rt_guest_read`, both backends.
  - `RECOMP_TRACE=aspect` prints `[aspect.layout]` with the rule that fired.
  - `tests/render_scale`: the new pad values, the frame's read edge w/8 inside the square's edges, off-layer rejections, the HUD staying left with an artefact, a tiled screen flagging, parked panels, the slide-out hysteresis, a busy HUD at 43% not flagging, recording during layout.
- [x] 8.3 Metal runs (16:10, edges, scale 2, `hud.pack`): `t6-final`, `t7-final`. Stage 1 layout frames 9-17, 163-216 and 226-779 (the loading screen through its slide-out), no gameplay frame flagged; story layout 708-3819 without the old gaps (522-587, 3273-3285), 3924-4312 the hub panel. The loading screen draws centred as one 4:3 screen (`t6-loading.jpg`), the dialogue HUD is steady (`t6-play.jpg`).
- [x] 8.4 Gates: Mac build clean (pre-existing warnings only); `tests/posix_ctest.sh` 80 pass, 0 FAIL; cat pytest 118 pass plus the worktree-only `test_gitignore`, ruff clean; Metal stock golden attract and stage1 pass (bench-logs 20261018-003013, -003040) at 43.9 and 33.8 flips/s, story NEWVIEW on the hub (the known timing flake, TASKS) then pass on rerun (20261018-003828, 53.6 flips/s). Stock keeps pad 0 and skips anchoring, so stock output is unchanged.
- [x] 8.5 Deck D3D11 stock golden (Mac cross-build at toolkit 25848cb9, GE-Proton11-7): attract, stage1 and story pass at 31.1, 30.6 and 46.8 flips/s against the tracker item's 31.7, 30.6 and 47.0 (bench-logs 20261018-004554, -004714, -004908; the Deck was busy, cpu stall about 9%); the bench's Proton test step is not run, as the Deck never builds.
- [x] 8.6 Deck D3D11 16:10, `hud = edges`, scale 2, stage 1 script (bench-logs 20261018-005156, 3200 flips in 105 s, 0 present mismatches; frames in `runs/hor-plus-edges/agent/deck-1610/`): layout frames 6-17, 163-217 and 227-801 as on Metal, none from 802 to 3200, and the HUD and dialogue stay on the edges in every dump (`jpg/sheet-play.jpg`, flips 900-1020 dumped in full); the loading screen draws centred as one 4:3 screen through its slide-out (`jpg/sheet-load.jpg`); the sea's tint reaches the left viewport edge with no clamped column (`jpg/frame_0018_sea_l.png`, `jpg/frame_0018_edge_zoom.png`).
- [x] 8.7 Review fixes (review, toolkit d0dd3a93):
  - The cover sum added pixel areas from targets of different sizes and compared them with the current target's area; it now adds each piece's share of its own target (`ext / (w h)`) against 1.0, or 0.5 the frame after a layout frame. Test: a quarter of the 640x480 frame plus a quarter of each of two 320x240 buffers is 75%, not a screen.
  - One triangle crossing the eye plane (a box of +-1e8) joined every piece on its rows, so a whole HUD batch became one off-layer piece and drew centred. The off-layer test runs per triangle before grouping; such a triangle joins no piece, is placed centred and does not count. Test: a +-1e8 quad in the same batch as a left-third HUD quad; the HUD stays left.
  - A stretched or covering batch keeps to the ratio's pad: drawn into a square it spans `nv2a_host_pad_ratio` (85 of 149 at 16:9), and reading a padded square it takes the same columns (`nv2a_rt_stretch_read`, D3D11 and Metal), so a full-width copy between the frame and a square lines up and the overscan stays out of it. 4:3 targets are unchanged (their ratio's pad is their pad). Tests: the map, the box and the read for a 512 square at 16:9, the frame's pad edge read the guest way landing on the stretch's edge column.
  - Burnout 3 at 16:9 on Metal (toolkit d0dd3a93, `RECOMP_TRACE=aspect`, the race-gate route on the private save fixture, PASS at 54.8 flips/s, race 53.0; runs in `runs/hor-plus-edges/agent/b3-race`): no 2D batch draws into a square. Its squares are 128x128 (202 wide with pads); every 2D batch is on the 640x480 frame, the 320x240 post buffer or the 160x120 glow buffers, and its stretched batches read the 640x480 frame only. A probe run that logged every 2D batch on a square target (`b3-probe`, not committed) logged none. The race renders at 854x480 with the world in the pads and the HUD on its 4:3 columns (`b3-race/race-06000.jpg`); the seam at x = 107 and 747 is the known glow-composite one (TASKS), untouched here.
  - The doc text says "centered" (config.md, env.md).
- [x] 8.8 Review-fix gates (toolkit d0dd3a93, cat f724196): `tests/posix_ctest.sh` 80 pass, 0 FAIL; cat pytest 119 pass plus the worktree-only `test_gitignore`, ruff clean; Metal stock golden attract, stage1 and story pass at 44.7, 33.5 and 52.9 flips/s (bench-logs 20261018-011830, -011857, -012017). Deck D3D11 stock golden (Mac cross-build, GE-Proton11-7): attract, stage1 and story pass at 31.8, 30.7 and 47.0 flips/s (bench-logs 20261018-065403, -065523, -065714; the Proton test step is not run, as the Deck never builds). Deck D3D11 16:10, `hud = edges`, scale 2, stage 1 script (bench-logs 20261018-070121, 3207 flips in 105 s; frames in `runs/hor-plus-edges/agent/deck-1610-r2/`): layout frames 5-17, 165-216 and 226-797 as in 8.6 and none after; the dialogue HUD stays on the edges (`f01000.jpg`), the title menu draws centred (`f00310.jpg`).
- Follow-ups (TASKS.md): the first early batches of a cover-sum screen can be anchored before the sum is reached (one frame); a batch over `NV2A_ASPECT_TRIS_MAX` (1024) triangles skips the layout check and is anchored as one piece by its bounds; the vertical bump clamp at the square's top and bottom is stock behaviour; the overscan A/B could not be made frame-exact on Metal, so the amount rests on the measured bump matrices.

## 9. No HUD option

The user (2026-10-18): Hor+ leaves the HUD alone, and the HUD shrink ideas are dropped too. Worktrees `wt/hor-plus-centered/{xboxrecomp,cat}`, branch `fix/hor-plus-centered`; runs in `runs/hor-plus-centered/`.

- [x] 9.1 Toolkit: the edges mode is gone: `nv2a_aspect_anchor_tris`, the pieces' union-find, the seed and inheritance across frames, the layout rules (`nv2a_aspect_layout_note`, `nv2a_aspect_piece_cover`, the cover sum), the `LEFT` and `RIGHT` placements, `enum nv2a_hud_mode` and `hud_mode`, the per-run draws on Metal and D3D11, the `[aspect.layout]` trace, the `display.hud` key and its `RECOMP_DISPLAY_HUD` row. The world side stays: the padded targets, the square overscan (the 1-1 water's bumped reads, H1), `nv2a_host_pad_ratio`, `nv2a_rt_stretch_read`, `nv2a_rt_guest_read`, `nv2a_aspect_full_tris` and the placement table.
- [x] 9.2 A stale `hud = ...` takes the generic `[ENHANCE] unused key display.hud, <file>:<line>` warning from `enhance_cfg_report_unused` and changes nothing; `tests/enhance_cfg` loads a 16:10 config with and without the line and checks the options are equal and the line is printed. The packaged `config.default.toml` prints no unused key.
- [x] 9.3 cat: `docs/env.md` (48 config rows), `packaging/config.default.toml`, design H6 (why there is no HUD option), the proposal and the spec ("HUD keeps its 4:3 layout").
- [x] 9.4 Gates at toolkit 3f720982 (no goldens, the user 2026-10-18):
  - Mac build and the Windows cross-build clean (pre-existing warnings only); `tests/posix_ctest.sh` 78 pass, 2 skip, 0 FAIL, `enhance_cfg` with the stale-key case among them; cat pytest 119 pass plus the worktree-only `test_gitignore`, ruff clean.
  - Deck D3D11 16:10, scale 2, stage 1 script, `RECOMP_CONFIG` a `config.toml` with `aspect = "16:10"` and `hud = "edges"` (Mac cross-build, GE-Proton11-7; bench-logs 20261018-080253, 3174 flips in 105 s): the one config line is `[ENHANCE] unused key display.hud, .../config.toml:3`, so the packaged `config.default.toml` (48 keys) prints none; `display.aspect=16:10 display.movie=black`; no `[aspect.layout]` line. The stage HUD and the dialogue box sit on their 4:3 columns with the world in the pads (`runs/hor-plus-centered/deck-1610/f01000.jpg`, `f02620.jpg`).
  - Burnout 3 16:9 Metal race gate (the route on the private save fixture): PASS at 58.2 flips/s, race 56.8 (54.8, race 53.0); 854x480 with the world in the pads and the HUD on its 4:3 columns (`runs/hor-plus-centered/b3-race/race.jpg`).
