# Tasks: nv2a-dot-stages

Toolkit branch `fix/qrs-water` off `posix-host/portability` 7775ac0f
(worktree `wt/qrs-water/xboxrecomp`). The tracker item.

## 1. Shared decode
- [x] 1.1 `SET_DOT_RGBMAPPING` kept in `nv2a_pb_vsh.dot_rgbmapping`
- [x] 1.2 `nv2a_dot_mode_ok`, `nv2a_mode_cube`, `nv2a_stage_cube_bind`,
      face stride and cube extent, `nv2a_stage_dot_map` (D1, D3)
- [x] 1.3 `nv2a_stage_ps_mode`: the dot family from `raw_mode`, CUBEMAP
      over a bindable cube (D2, D3); `nv2a_ps_stage_key` (D4)

## 2. Generators (D1)
- [x] 2.1 MSL and HLSL: `nv2a_dotmap`, `nv2a_cube_2d`, each dot mode,
      cube declarations from `tex_cube`, nothing declared for stages
      that sample nothing

## 3. Backends (D3)
- [x] 3.1 Metal: six-face decode, `tex_make_cube`, cube cache entries,
      black cube fallback, binds gated on the combiners' shader
- [x] 3.2 D3D11: six-face decode, `TEXTURECUBE` array of six, cube cache
      entries, black cube fallback, 2D rebind when the basic shader runs

## 4. Tests and gates
- [x] 4.1 ctest `nv2a_dot`; Metal compile cases for every dot mode in
      `d3d8_msl_split`; `docs/reset-statics.md` rows
- [x] 4.2 `tests/posix_ctest.sh`: 0 FAIL (154 pass; wt/qrs-water/ctest2.log)
- [x] 4.3 BLiNX 2 Metal goldens: attract, stage1, story pass
      (runs/qrs-water/b2-golden-metal.log)
- [x] 4.4 QR Metal before and after at the water (runs/qrs-water/cmp-fix)
- [x] 4.5 QR rain still refracts at present 1650
      (runs/qrs-water/cmp-fix/rain-present1650.png)
- [x] 4.7 Review fixes (review of 83845669): cube over a live
      render target read as 2D (`cube_rt`, D5); dot cases shared by
      `d3d8_hlsl_split`, `d3d8_msl_split` and `d3dcompile_smoke`;
      `nv2a_bump_sources` and the key cover the dot inputs and DIFF's
      stage 3; sign2 wording (D1); D3D11 2D rebind before the debug
      shaders; no `alpha_only` or texture bind for zero-reading stages
      (toolkit 0959f7f2; ctest 154 pass, wt/qrs-water/ctest3.log; Metal
      goldens runs/qrs-water/b2-golden2.log; QR runs/qrs-water/cmp-review)
- [x] 4.8 Re-review fixes (0959f7f2): `stages_cube_rt` drops a
      stale overlapping target (`rt_drop_if_stale`, "cube") on both
      backends; D3D11's stage-loop memo is not kept when the loop dropped
      a target (toolkit c188a635; ctest 154 pass, wt/qrs-water/ctest4.log;
      Metal goldens runs/qrs-water/b2-golden3.log; QR runs/qrs-water/w08-rereview)
- [ ] 4.6 D3D11: native Windows and Proton runs of QR's water, and the
      BLiNX 2 D3D11 goldens (orchestrator: PC and Deck)

## 5. Follow-ups (TASKS)
- [ ] 5.1 CPU rasteriser: dot-product modes and cube maps
- [ ] 5.2 HILO formats for the dot mappings; DOT_STR_3D past slice 0

Archived 2026-11-06 after the merge; the open items above moved to the tracker item.
