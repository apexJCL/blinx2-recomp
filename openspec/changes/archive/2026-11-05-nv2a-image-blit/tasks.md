# Tasks: nv2a-image-blit

Toolkit branch `fix/nv2a-image-blit` off `posix-host/portability`
(worktree `wt/qrs-rain/xboxrecomp`). The tracker item.

## 1. Executor
- [x] 1.1 `nv2a_2d.{h,c}`: decode, bpp, extent, guest copy, host box (D1)
- [x] 1.2 `SET_OBJECT` through RAMHT on every subchannel; NV062/NV09F/NV012
      in `twod_method`; context DMA placement and refusal in `twod_blit` (D2)
- [x] 1.3 `on_blit` hook; guest copy with `surf_mark_range` when absent

## 2. Backends (D3)
- [x] 2.1 Metal: twin target via `copyFromTexture`; guest fallback with
      `rt_sync` and `tex_cache_stale`; present counters
- [x] 2.2 D3D11: twin target via `CopySubresourceRegion`; guest fallback
      with `blit_tex_stale`; present counters

## 3. Hor+ (D4, own commit)
- [x] 3.1 `nv2a_aspect_place_copy` in `nv2a_backend_common.h`, called by
      both backends

## 4. Tests and gates
- [x] 4.1 ctest `pb_image_blit` (decode, host box, copy, executor, place)
- [x] 4.2 `tests/posix_ctest.sh`: 0 FAIL
- [x] 4.3 `notes/build-all.sh` with the toolkit worktree
- [x] 4.4 BLiNX 2 Metal golden and D3D11 native golden unchanged; report
      any 2D-engine binds in its log
- [x] 4.5 QR before/after frames, Metal and D3D11, 4:3 and 16:9
      (`runs/qrs-rain/`)
- [x] 4.6 Deck Proton golden: post-merge integrate (PC exe 9351fc6e), attract, stage1, story pass

## 5. Review fixes (review: merge after fixes)
- [x] 5.1 D3D11 fallback parity: source and overlapping targets written
      back (`blit_write_back`), GPU path widened to another destination
      pitch on both backends; costs in D3
- [x] 5.2 BLiNX 2's display-buffer blits in the gpu-backend spec and the
      proposal; the twin write-back safety argument in D3
- [x] 5.3 Hor+ copy rule: `copy_flip` expiry and `nv2a_aspect_uv_tracks`;
      QR rechecked at 16:9 on both backends
- [x] 5.4 Class 0 for a bound subchannel whose class can't be read; ctest
- [x] 5.5 Smoke cases on Metal and D3D11 (twin, eviction, retire, expiry,
      fallback write-back, scale 2 with pads)
- [x] 5.6 RAMHT handle cache; retire not gated by rt_alias_check (D3);
      RT-slot footprint (D3)

## 6. Second review (merge after one fix)
- [x] 6.1 D3D11 writes back only what a target holds: the source's
      rectangle, a target over the destination only when `full` (D3)
- [x] 6.2 `nv2a_surf_pack_row` with the formats' constant bits, on D3D11
      and Metal (D3)
- [x] 6.3 `pb_image_blit` units for `nv2a_aspect_uv_tracks`,
      `nv2a_aspect_uv_sample` and packing; smoke cases for drawn-in-part
      targets and sources, R5G6B5 and a wider destination pitch
- [x] 6.4 Known limits in D3: Metal 16-bit unseeded, uv sample tolerance,
      stale RAMHT entry
