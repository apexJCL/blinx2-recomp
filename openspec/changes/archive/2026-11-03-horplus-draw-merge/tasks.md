## 1. Toolkit (`fix/l2-slowdown` off `posix-host/portability`)

- [x] 1.1 `nv2a_merge_placed()`; `merge_placed` backend hook; `merge_on()` asks it under Hor+ or snap_2d
- [x] 1.2 D3D11 and Metal hooks (gate, depth, render-target stages)
- [x] 1.3 `tests/pb_draw_merge`: hook missing, 0 and 1 under Hor+, yes-yes-no mid-chain; `nv2a_merge_placed` cases
- [x] 1.4 Gates: `tests/posix_ctest.sh` 0 FAIL; PC D3D11 golden (attract and story pass-with-known the tracker item, stage1 pass)

## 2. cat (`fix/l2-slowdown`)

- [x] 2.1 This spec; `docs/env.md` `RECOMP_RENDER_SNAP_2D` row

## 3. Verify

- [x] 3.1 PC D3D11, stage 2 flyover at scale 3, aniso 2, 16:9: draws 8637 -> 3380, walk 17.2 -> 13.9 ms (4:3 at scale 3: 13.9), draw 10.1 -> 5.1 ms; merged 16:9 frames checked by eye
- [x] 3.2 Merged vs `pb_merge=0` frame A/B, 16:9, deterministic guest clock, stage 2 flyover, HUD and pause (`runs/l2-merge-ab/`): PC D3D11 29 flips 900..4200 bit-identical (39.4 vs 34.2 flips/s); Mac Metal 138 flyover/HUD flips, at most 6 px > 8 on single triangle edges (max 21, PSNR >= 74): merging turns a strip into an indexed triangle list, and Apple GPUs are not bit-invariant to vertex order within a triangle (edge coverage, interpolation) where D3D11 is, pause flips max <= 1; Mac Metal scale 3 snap_2d 108 flips, at most 1 px > 8 (max 21). Draws at flip 1200: 1868 merged vs 4363

## 4. Follow-ups

- [ ] 4.1 Fixed-function batches that draw through `ff_begin`'s synthesised program: merge under Hor+ and snap_2d too, once END can tell (design D2a). Only worth doing if a title's wide-view fixed-function draw counts show up in a profile.
