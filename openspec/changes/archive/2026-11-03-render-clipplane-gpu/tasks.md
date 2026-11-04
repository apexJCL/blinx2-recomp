## 1. Constant and layout
- [x] 1.1 `nv2a_ps_consts.clip_mode[4]` at 544 (size 544 -> 560); `nv2a_ps_consts_fill` writes `0x10 | ((clip_plane_mode >> 4n) & 0xF)` for a `raw_mode` 5 stage, else 0; update the `_Static_assert`s (Metal `PS_AT`, size 560, `MsPsConsts.tex_bias` 560, sizeof 576; D3D11 `PS_ABI_SAME(clip_mode, clip_mode)`).
- [x] 1.2 `D3D8_MSL_PSCONSTS`, the HLSL cbuffer text in `d3d8_combiners_hlsl.c` and `nv2a_pb_d3d11.c`, and `NV2APSConstants` (`d3d8_combiners.h`) gain `uint4 clip_mode`; `d3d8_combiners.c` writes 0.

## 2. Emitters
- [x] 2.1 MSL and HLSL: per CLIPPLANE stage, discard where `any(select(t < 0, t >= 0, ge))` and the flag is set, at the end beside the alpha test (design 4); register stays 0.
- [x] 2.2 `fs_basic` / D3D11 `s_ps_src`: the same for stage 0 from `clip_mode.x`.
- [x] 2.3 d3d8_msl_split / d3d8_hlsl_split: re-record; extend `texmode_check` with the discard text.

## 3. Tests and checks
- [x] 3.1 nv2a_backend_smoke and d3d11_backend_smoke: a scene with a CLIPPLANE stage (a quad whose T0 crosses 0 along x, both sign settings), compared with the CPU path. d3d11_backend_smoke has no CPU compare: it probes the killed and kept halves (`clipplane_cases`). Both also draw stage 1 under a combiner (the 4n nibble shift; `clipplane1`, `t1`) and stage 0 with no combiners, checked by probes alone since the CPU path differs there (`clipbasic` on Metal, `t0 basic` on D3D11).
- [x] 3.2 Mac build, POSIX ctests, Metal goldens (attract, stage1, story) unchanged, and their [VSH] stage-mode census. (POSIX ctests 78 pass, 0 FAIL; Metal goldens pass at 43.5 / 34.2 / 53.8 flips/s, `runs/quick-wins/metal-golden`; census has no mode 5 in any scenario, only 0, 1 and 6, `runs/quick-wins/cpu-census`.)
- [x] 3.3 llvm-mingw cross build; Proton: d3d11_backend_smoke (with the 3.1 scene) and `blinx2 bench golden`. (Deck, GE-Proton11-7: d3d11_backend_smoke passes plain and with `RECOMP_D3D11_OCC=sync`, with the t0, t1 and no-combiner cases, `runs/quick-wins/review-fix/smoke2*.log`; bench golden runs 20261017-181939 / -182059 / -182250 pass.)
