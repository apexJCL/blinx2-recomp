Worktrees: `wt/snap-uv-fix/xboxrecomp` (branch `fix/snap-uv-swizzled` off `posix-host/portability`) and `wt/snap-uv-fix/cat` (branch `fix/snap-uv-swizzled`). ## 1. Toolkit

- [x] 1.1 The 2D guest-grid snap (`tex_scale.z = -N`, `nv2a_ps_consts_snap`) on both backends (c9399055).
- [x] 1.2 The `render.snap_2d` setting, the menu row, and 1x gradients for snapped stages (c0fb8284).
- [x] 1.3 `vary_z`: program batches off one depth are not snapped (10357824, 09617428).
- [x] 1.4 Stock text when off: the `SNAP_2D` macros, the `snap_2d` key bit, and the lazy snap variants (a69adea6).
- [x] 1.5 Merge `posix-host/portability` 74697552. `merge_on` is off under the snap, and `pb_draw_merge` has a case for it.
- [x] 1.6 The basic shaders move to `nv2a_basic_{hlsl,msl}.h`. The new `basic_shaders` ctest has the stock checksums and a Metal compile of `fs_basic` and `fs_basic_snap`. `d3dcompile_smoke` compiles both HLSL variants.
- [x] 1.7 `docs/runtime/config.md`: which batches are 2D, and merging off.

## 2. cat

- [x] 2.1 The `docs/env.md` row: one depth, centred or unpadded, merging off.

## 3. Gates

- [ ] 3.1 The POSIX ctests at 0 FAIL.
- [ ] 3.2 The JSRF dogenzaka D3D11 golden on the Deck twice, with a PC-built exe.
- [ ] 3.3 The BLiNX 2 Deck golden, and the BLiNX 2 and JSRF Metal goldens.
- [ ] 3.4 A Deck spot run with the snap on at scale 2: flips/s and a frame look.
