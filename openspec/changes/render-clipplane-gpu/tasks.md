## 1. Constant and layout
- [ ] 1.1 `nv2a_ps_consts.clip_mode[4]` at 416; `nv2a_ps_consts_fill` writes `(clip_plane_mode >> 4n) & 0xF`; update the size `_Static_assert`s (Metal 416 -> 432, MsPsConsts tex_bias 432, sizeof 448).
- [ ] 1.2 `D3D8_MSL_PSCONSTS`, the HLSL cbuffer text in `d3d8_combiners_hlsl.c` and `nv2a_pb_d3d11.c`, and `NV2APSConstants` (`d3d8_combiners.h`) gain `uint4 clip_mode`.

## 2. Emitters
- [ ] 2.1 MSL and HLSL: per CLIPPLANE stage, `if (any(select(t < 0, t >= 0, mask)))` discard; register stays 0.
- [ ] 2.2 `fs_basic` / D3D11 `s_ps_src`: the same for stage 0.
- [ ] 2.3 d3d8_msl_split / d3d8_hlsl_split: re-record; extend `texmode_check` with the discard text.

## 3. Tests and checks
- [ ] 3.1 nv2a_backend_smoke: a scene with a CLIPPLANE stage (a quad whose T0 crosses 0 along x, both sign settings), compared with the CPU path. Metal on the Mac.
- [ ] 3.2 Mac build, POSIX ctests, Metal goldens (attract, stage1, story) unchanged.
- [ ] 3.3 llvm-mingw cross build; Proton: d3d11_backend_smoke (with the 3.1 scene) and `blinx2 bench golden`.
