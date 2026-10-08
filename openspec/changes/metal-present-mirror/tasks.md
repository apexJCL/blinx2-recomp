Worktrees: `wt/metalmirror/cat` off `main` 5dd464d and `wt/metalmirror/xboxrecomp`
off `posix-host/portability` a10f6d8, both on `fix/metal-present-mirror`.
Parked toolkit WIP: 051b3c4 (see design, Context). Every toolkit task names
the function it lands in; "verify" lines are what the task's commit message
or the merge notes record.

## 0. Spec

- [x] 0.1 This spec was not written by Fable, so Fable reads it and improves it, then commits the revision on the spec branch (this commit).
- [x] 0.2 Implementation continues only from Fable's revised commit; rebase 051b3c4 on it and amend it per D1 (`rt->dt = NULL`, the unseeded-margin clear) before building on it.

## 1. Toolkit

- [x] 1.1 `nv2a_clear_box` in nv2a_backend_common.h; D3D11's `clear_region` calls it and `clear_box` goes (D2). Verify: `git diff` of nv2a_pb_d3d11.c is the call site only; `d3d11_backend_smoke` under Proton (3.1) passes unchanged.
- [x] 1.2 CPU `clear_surface` fills the clear box, swizzled and linear, 16- and 32-bit (D2, D5); the nv2a_pb_state.h comment says every path bounds by it. Verify: smoke cases 1 and 2 on the CPU path (1.6).
- [x] 1.3 Metal `surface()` second loop and `rt_grow` (D1, steps 1-7, including `rt->dt = NULL`, the black pass when `rt_seed` does not apply, `s_grows`); `present_target` and `metal_sync_guest` accept a covering target (D4). Verify: smoke cases 3 and 4; `ctest -R rt_alias` and `nv2a_backend_smoke_noalias` still pass (the ownership hash is reset at the new height).
- [x] 1.4 Metal partial colour clears (D3): `vs_clear`/`fs_clear`, `s_clear_pso[2]`, the scissored draw in `metal_on_clear`, visibility off for it and the pass ended after it while a query counts (S1 of the 2026-10-07 merge review; the scissor reset otherwise), the load-action fallback on a pipeline failure, `s_partial_clears`. Verify: smoke cases 1 and 2 on Metal; case 2 at scale 2 is covered by case 4's rect.
- [x] 1.5 Metal `present_extent` for the layer blit, the readback pushes and `s_shown_w/h` (D4); `nv2a_pb_metal_shown` for the smoke. Verify: smoke case 5; a windowed stage1 run on the Mac shows the frame as before (the window is a 640x480 fit; nothing grows in BLiNX 2, so the extent equals the target).
- [x] 1.6 `nv2a_backend_smoke` `clip_cases` (D7, cases 1-5), BUF3/BUF4 constants, the guest pattern re-filled before each path's run of cases 3 and 4, the header comment's case list. Verify: `ctest -R nv2a_backend_smoke` (default, `guard`, `noalias`) passes; each case prints a PASS line with its probe values, as the D3D11 smoke does, and the full-frame compare line.
- [x] 1.7 Metal present summary line reports `grows` and `partial clears`; flip_log untouched. Verify: the counters are 0 on a BLiNX 2 stage1 golden log, or 2.5 runs.

## 2. Mac gates

- [x] 2.1 Build with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`, no new warnings in nv2a_pb_metal.m.
- [x] 2.2 POSIX ctests in the toolkit build dir, all of them (`nv2a_backend_smoke*`, `rt_alias`, the kernel tests): no new failure or skip.
- [x] 2.3 cat `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`.
- [x] 2.4 gen/ regenerated against the toolkit worktree (`blinx2 analyze` then `blinx2 recomp`); Metal goldens attract, stage1, story at stock (`blinx2 golden`): same verdicts, every anchored frame within `max_pace_diff` (0.10) of its reference pace.
- [x] 2.5 Perf: the stage1 run's present summary (1.7) is read. With 0 grows and 0 partial clears the golden pace check is the measurement. With either non-zero, a stage1 bench at 1x against the last recorded Metal flips/s: the flag is 25% or more below (CLAUDE.md), and the number goes in the merge notes either way.

## 3. Proton gates (on the orchestrator's go, one agent on the Linux/Proton host)

- [x] 3.1 `blinx2 bench tests` (d3d11_backend_smoke covers the moved clear box; rt_alias and the rest unchanged).
- [x] 3.2 `blinx2 bench golden`: D3D11 verdicts and paces unchanged.

## 4. Follow-ups for TASKS.md

- [ ] 4.1 Depth/stencil clears bounded by the clear rect (D3D11 and Metal).
- [ ] 4.2 A grown target sampled with normalised coordinates (D3D11 and Metal).
- [ ] 4.3 A 16-bit surface's grown margin is black, not the guest bytes (Metal; D3D11's is black for every surface). Metal's `!keep` grow (the host size changes with the factor) also loses a 16-bit target's old contents: written back as R5G6B5, not re-seeded. D3D11's `rt_grow` copies host pixels unscaled when the host factor changes, where Metal writes back and re-seeds. Both are reachable only past METAL_MAX_DIM at the chosen scale (5 or more); merge review round 4, follow-ups 2 and 3.
- [ ] 4.4 The Metal grow on Burnout 3, once it boots on the Mac: the 640x464 / 623x401 / 159x344 clips, the grow and partial-clear counts per frame, and the pace against D3D11's. Check the partial clears inside an occlusion query too: since S1 each one spends a slot of the query (two when the clear opens its own pass, whose slot counts nothing), and past OCC_QSLOTS (16) the query overflows and reports visible.
- [x] 4.5 Remove the "Metal and CPU mirror" Pending entry's first two bullets from TASKS.md at the merge; the third (D3D11 write-back, hash cost) stays.
- [ ] 4.6 The CPU walker's zpass count for a 100x100 pre-transformed quad is 10100, not 10000 (`occ_case` prints it): with the occlusion count semantics item.
- [ ] 4.7 A pixel-level pin for the Metal crop (the blit or push extent, or the slot size), paired with the D3D11 uv_scale test (merge review round 4, follow-up 1).

## Results (Mac, 2026-10-07)

Toolkit: f3b328b (clear box, CPU), 0352697 (Metal), 01bb92f (smoke), on
fix/metal-present-mirror, rebased onto 217b61d (built from a10f6d8); 051b3c4 was folded into them per 0.2.
Raw logs: `xbox-recomp/runs/metalmirror/`.

- 1.1: nv2a_pb_d3d11.c changes only the call site (the box body moved verbatim).
- 1.6: all five clip cases PASS on CPU and Metal, exact full-frame compares;
  with partial clears forced to whole-target, clip clear, clear rect and grow
  FAIL (the cases catch the bug). `nv2a_backend_smoke`, `_guard`, `_noalias` pass.
- 2.1: Mac build ok, no warnings in nv2a_pb_metal.m.
- 2.2: every POSIX ctest dir that configures passes (ctest/summary.txt; the
  NOCONFIG/NOBUILD set is the Windows-only one), plus the in-tree
  input_map, d3d8_msl_split, d3d8_hlsl_split and nv2a_backend_smoke (3/3).
- 2.3: 25 passed; ruff check and format clean.
- 2.4: gen/ regenerated (analyze + recomp) against the toolkit worktree.
  Metal goldens: attract 2/2, stage1 3/3, story 3/3 CLOSE, golden exit 0, every
  pace within 10% (stage1 29.0/29.4/29.3 fps vs 28.4/29.5/29.6).
- 1.7/2.5: the present summary shows 0 grows and 0 partial clears on attract,
  stage1 and story, so BLiNX 2 never takes the new paths; the golden pace
  check is the measurement and no bench is needed.
- Rebased onto toolkit 7fb919c and cat eec914f (merge-tree clean, no lifter
  change, so gen/ stands): Mac build ok; in-tree nv2a_backend_smoke 3/3,
  pb_tex_cache, input_map and the split tests pass. The goldens above ran on
  the pre-rebase build.
- Rebased again onto toolkit 217b61d and cat df63d64 (merge-tree clean): Mac
  build ok, in-tree tests pass.
- 3.1 (the Linux/Proton host, host tree ~/xbr-metalmirror): `blinx2 bench tests` 15/15 pass,
  d3d11_backend_smoke and _occ_sync included (runs/metalmirror/bz-tests.log).
- 3.2: `blinx2 bench golden` passes, 8/8 CLOSE, every pace within 10%, 0
  present mismatches (2432, 3270, 4727 flips), no crash; bench-logs
  20261007-063537, -063656, -063847. The "game process is running" warnings
  were other agents' Mac runs, not on the host.

## Merge review fixes (fix/metal-mirror-review, 2026-10-07)

Fable round 4 (notes/fable-reviews/2026-10-07.md): S1 and S2 on toolkit
7bc1d3c and e68689f, on posix-host/portability dce73d4 (first written off
a0b9a55).

- S1: the partial clear ends the counting pass (design D3). `occ_case` in
  nv2a_backend_smoke: Metal 20000. It pins the new slot after the clear
  (10000 without it) and the clear's exclusion (22500 when counted); the
  set-once rule is not observable on Apple silicon (the pre-fix code also
  reads 20000 on an M4 Max).
- S2: the CPU halves of the clip clear and clear rect run before the backend
  check in nv2a_backend_smoke, and, since that test builds on macOS only,
  `cpu_clip_cases` in d3d11_backend_smoke runs them under Proton.
- Nit: D1 step 2 says the grow ends any open encoder.
- Nit: the D3D11 present summary counts grows and partial clears (d27aa68).
- Opus review of 7bc1d3c/e68689f (MERGE): nits 1, 6 and 7 in toolkit 3cb97da
  (smoke comments, the occ_case poll, the clear rect's inclusive max edge
  probed at (339,339) and (340,339) in both smokes); nits 2, 3, 5 and 8 here.
