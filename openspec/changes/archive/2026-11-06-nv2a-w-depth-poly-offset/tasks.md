Toolkit branch `fix/qrs-flicker` (worktree `wt/qrs-flicker/xboxrecomp`), from `fix/qrs-water` 3ff06e3c; it rebases onto `posix-host/portability` after the squash. ## 1. State and translation

- [x] 1.1 `nv2a_pb_state.h`, `nv2a_pb_exec.c`: track SET_CLIP_MIN (0x0394), SET_CLIP_MAX (0x0398) and SET_ZMIN_MAX_CONTROL (0x1D78), with their reset values.
- [x] 1.2 `nv2a_backend_common.{h,c}`: `nv2a_poly_offset_on`, `nv2a_depth_bias`, `nv2a_w_depth_on`, `struct nv2a_wdepth_consts` and `nv2a_wdepth_consts_fill` (design, decisions 4-6).
- [x] 1.3 ctest `nv2a_depth_state` for 1.2.

## 2. Shaders

- [x] 2.1 Vertex epilogues, MSL and HLSL: the `zw` output; in W mode (`spec_ctl.w`, `u[7]`), `pos.z = 0.5 * pos.w`.
- [x] 2.2 `NV2ACombinerState.w_depth`, and the W variants in `d3d8_combiners_msl.c` and `d3d8_combiners_hlsl.c`. With it 0, the text is byte-identical (a test compares the text for a sample of states with the flag off against the base).
- [x] 2.3 The shader tests compile a W variant (Metal on the Mac; HLSL through the existing HLSL compile test, if there is one). Done: `d3d8_msl_split` compiles it with Metal; `d3d8_hlsl_split` checks the HLSL text only. The HLSL compile (`d3dcompile_smoke`) runs on Windows, not on the Mac.

## 3. Backends

- [x] 3.1 Metal: the W flag in `fs_select`'s key; `vc.u[7]` from the shader chosen; the `WDepth` buffer at fragment index 1; `setDepthBias` for non-W polygon offset.
- [x] 3.2 D3D11: the same in `setup_pixel`, `set_vp` and a `b1` PS buffer; `DepthBias`, `SlopeScaledDepthBias` in the `rasterizer_state` key.
- [x] 3.3 The CPU backend still builds; its missing W path goes in TASKS.md.

## 4. Gates

- [ ] 4.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`); `tests/posix_ctest.sh` 0 FAIL; the Windows cross-build of the toolkit compiles the D3D11 changes. Done on the Mac: the build passes and the ctests show 155 pass, 0 FAIL. The D3D11 sources pass an llvm-mingw `-fsyntax-only -Wall` check. Open: a full Windows build and the HLSL compile.
- [x] 4.2 BLiNX 2 Metal goldens: bit-identical. Two passes are 8 of 8 CLOSE, with the same MAEs as the water tip within run noise. No W-buffer or polygon-offset line is logged in any scenario, so BLiNX 2 never takes either new path.
- [ ] 4.3 QR A/B (water tip vs this branch) at the billboard, cave, pillar and map-select globe spots, frame dumps under `runs/qrs-flicker/`. Done for the billboards and the globe: both are fixed (`runs/qrs-flicker/ab-summary/`). Deferred for the pillar and the cave (the coordinator, 2026-11-05: the billboards and the globe are the reported symptoms): the pad replay does not reach the same spot on both builds, and under `deterministic` it stays on the title screen (follow-up in 4.5).
- [x] 4.4 Metal flips/s on QR's W-buffered scenes, against the water tip. D3D11 flips/s: on the PC or the Deck, run by the coordinator. Metal: flips/s unchanged (the game paces it). GPU time over the race went from 1.61 to 1.85 ms per frame (+15%, two runs each), under the 1.5x flag.
- [ ] 4.5 TASKS.md follow-ups: W for `fs_basic` and `vs_pass` draws (and stock-shader fallbacks), line and point offsets, the CPU backend's W path, and a QR pad recorded under `deterministic` for the pillar and cave A/B (the flip-timed pad stays on the title screen there). Handed to the coordinator, since TASKS.md is on main.

Archived 2026-11-06 after the merge; the open items above moved to the tracker item.
