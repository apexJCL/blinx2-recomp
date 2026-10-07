Worktrees: `wt/horizon/cat` off `main` 3564cb4 and `wt/horizon/xboxrecomp` off `posix-host/portability` 4773a01, both on `fix/pb-index-batch-cap` (the spike branches `spike/horizon-occlusion` are kept). The prototype (cap 65536, overflow note) was carried over as toolkit d43b654; the implementation is ffb8a93. Results are in `notes.md`. Raw runs go to `xbox-recomp/runs/horizon/`. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Mac runs are headless with `SDL_AUDIODRIVER=dummy`. The Metal golden runner is `runs/horizon/tools/metal_golden.sh OUTDIR`. The Mac disk is tight: no second build tree.

## 0. Spec review and branch state

- [x] 0.1 This spec was not written by Fable, so Fable reads it and improves it, then commits the revision on the spec branch.
- [x] 0.2 Implementation continues only from Fable's revised commit.
- [x] 0.3 Merge `posix-host/portability` (4773a01, the D3D11 one-target-per-surface change) into the toolkit branch before any further gate: the prototype branched from b0eb653 and the D3D11 goldens must run with both.

## 1. Toolkit: the cap, the report and the 32-bit element (D1 to D4)

- [x] 1.1 `nv2a_pb_state.h`: `NV_MAX_INDICES` to `0x80000`. The comment gives the hardware facts (an Xbox 1.0 takes at least `0x0FFFFF` elements, retail titles send at least `0x410FA`, xemu's cap is `0x07FFFF`) and the BLiNX 2 grid as the case that found it; `idx` stays `uint16_t` because a `DRAW_ARRAYS` start above `0xFFFF` faults on the hardware.
- [x] 1.2 `nv2a_pb_exec.c`: `note_idx_overflow()` at the `ARRAY_ELEMENT16` and `DRAW_ARRAYS` paths, with one warning and a count (prototype).
- [x] 1.3 `nv2a_pb_exec.c`: `case NV097_ARRAY_ELEMENT32` (0x1808) appends `(uint16_t)param` with the same guard and note (D3).
- [x] 1.4 `nv2a_pb_exec.c`: `s_idx_max` (largest `idx_count` at `draw_primitive`) and `s_idx_start_hi` (`DRAW_ARRAYS` runs whose last index passes `0xFFFF`). `nv2a_pb_exec_report` prints `index batches: max M, N overflowed` after the draws line, and `, K starts over 0xFFFF` only when K is non-zero (D2).
- [x] 1.5 `nv2a_pb_exec.c`: `raster_batch_vsh_one`'s `xv` becomes a `static` pointer with a capacity, reallocated to `idx_count` on demand; a failed realloc skips the batch and counts it (D4).
- [x] 1.6 `nv2a_pb_metal.m` and `nv2a_pb_d3d11.c`: the `idx[NV_MAX_INDICES * 3]` expansion list becomes a heap buffer reallocated to `3 * idx_count`; the index ring is `3 * NV_MAX_INDICES * 4` bytes (6 MB) on both (D4). Metal's comment on the rings says why the index ring is sized to the cap and the vertex ring to the 16-bit vertex range.
- [x] 1.7 `tests/nv2a_backend_smoke/smoke.c`: scene `bigidx`, a grid of small pre-transformed quads from vertex arrays in guest memory (`0x1760`/`0x1720` as the D3D11 smoke's scenes do) with more than 4096 indices sent as `ARRAY_ELEMENT16`, colour A below index 4096 and colour B from 4096 on; the scene asserts a pixel inside a colour-B quad as well as the CPU/GPU match. Scene `elem32`, a triangle list whose last index arrives as `ARRAY_ELEMENT32`, asserts a pixel inside the last triangle (D5). Confirm both fail at the old cap (temporarily set `NV_MAX_INDICES` back and drop the 0x1808 case) before the change is committed.
- [x] 1.8 `tests/d3d11_backend_smoke/smoke.c`: the same two scenes, run under Proton by `blinx2 bench tests`.

## 2. Mac gates

- [x] 2.1 Mac build. Lighthouse warp on Metal, flip 2490: cyan water to the horizon (`runs/horizon/lh-metal-fix/`, 65536 prototype).
- [x] 2.2 Metal goldens: attract, stage1 and story pass (`runs/horizon/golden-fix.txt`, 65536 prototype).
- [x] 2.3 Repeat 2.1 and 2.2 on the final branch (cap `0x80000`, heap scratch, `ARRAY_ELEMENT32`). Read `index batches: max M` from each golden log and record M per scenario in the notes: it says which other batches were ever over 4096.
- [x] 2.4 The same warp on the CPU path (`RECOMP_PB_BACKEND=cpu`, about 8 minutes to flip 2490). Check the frame against `fix-2490.png` and that no `index batch over` line appears.
- [x] 2.5 POSIX ctests touched by the walker: `nv2a_backend_smoke` (with guard and noalias), `nv2a_zbuf`, `render_scale`, `nv2a_vsh`, `nv2a_combiner`, `rt_alias`, `nv2a_tex` (prototype).
- [x] 2.6 Repeat 2.5 on the final branch, with the two new scenes.
- [ ] 2.7 Bench: Metal flips/s and raster ms on the stage 1 golden run within the CLAUDE.md thresholds (no per-draw cost is expected; the realloc is once per high-water mark).
  - Archive note (2026-10-07): not run (notes.md, Not run); the golden flip counts are in line with the prototype. Moved to TASKS.md (the bench pass for today's merges).

## 3. Proton gates

- [x] 3.1 D3D11 goldens via `blinx2 bench golden`, and `blinx2 bench tests` for `d3d11_backend_smoke` with the new scenes. In each scenario's log read `index batches: max M, N overflowed` (N must be 0, and any `starts over 0xFFFF` is a bug to chase) and look for `0x1808` in the unhandled ranking (it must be gone).
- [x] 3.2 Stage 1 lighthouse warp on D3D11: the horizon frame matches Metal.
- [x] 3.3 Burnout 3 under Proton (max 3909, 0 overflowed; see notes.md): build `wt/b3-fork` against the toolkit branch and run a race (`./burnout3 bench`, run lock, BLiNX first, user's go). From `game-stdio.log` record `index batches: max M, N overflowed` and the `0x1808` count before and after. If M was over 4096 before the change, compare the track horizon and the far geometry against the pre-change run and against upstream's screenshots. Per `upstream-burnout3-gate` this does not hold the fork merge; it is required again on the exact PR head before the upstream PR.

## 4. Follow-ups to record in TASKS.md

- [x] 4.1 Split-on-full for batches over the cap (D1 carry rules), only if a title's `max` ever approaches `0x80000`.
- [x] 4.2 The occlusion count semantics against NV2A (zpass units, depth test, clip): general fidelity work, not this bug's cause.
- [x] 4.3 Close the horizon-split entry in TASKS.md (stage 1 item 4: the lead was occlusion, the cause was the index cap) and the water-jitter note's pointer to it.
  - Done 2026-10-07: 4.1 and 4.2 are TASKS.md follow-ups; the horizon split is closed there.

## 5. Merge

- [ ] 5.1 Fable merge review; its fixes go back to this branch's agent.
  - Archive note (2026-10-07): not done yet; the Fable merge reviews are batched (Fable quota). Listed in TASKS.md.
- [x] 5.2 Squash merge: toolkit `pb_exec: index batches up to 0x80000, ARRAY_ELEMENT32, overflow reported`; cat: this change plus the TASKS.md entries from section 4. Done 2026-10-06: toolkit d9a5c36 (from ffb8a93), cat d126f24 (from ca65931); the section 4 entries landed with the archive, 2026-10-07.
- [ ] 5.3 Post-merge: notes to `notes/horizon/`, the referenced runs stay in `runs/horizon/`, worktree removed, the Linux/Proton host `blinx2 bench integrate --golden`.
  - Archive note (2026-10-07): the orchestrator's post-merge step. The integrate after today's merges is running (TASKS.md); `wt/horizon` is still there.
