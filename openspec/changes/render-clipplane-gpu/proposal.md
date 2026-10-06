## Why

Texture-shader mode 5, CLIPPLANE, turns a stage into four user clip-plane distances: each component of the stage's interpolated coordinate kills the pixel at `>= 0` or at `< 0`, as SET_SHADER_CLIP_PLANE_MODE (0x17F8) picks per stage and component (xemu psh.c; toolkit e03f9ff, upstream 13c64d3). The CPU path does it (`stage_clip_kills`). The Metal and D3D11 backends do not: they bind no texture for the stage and the register reads 0 (toolkit 35e17dd), but every pixel survives. A title that uses user clip planes (portal or water cuts, mirror passes) draws geometry on the GPU paths that the hardware and the CPU path cut away. That breaks "Backends agree".

The Metal boss-scene sweep (2026-10-05, branch `metal-boss/fixes`) checked whether any reported defect was this: none was. Boss 1's sky, Boss 3's water, the Shadow Claw ellipse and the Silver Claw shapes all draw the same on the CPU path, which has the kill. So nothing on screen is known to need this yet. It is a bounded gap, recorded so the next title or scene that uses clip planes does not have to rediscover it.

## What Changes

- **A clip-plane constant for the combiner shaders.** `struct nv2a_ps_consts` gains `uint32_t clip_mode[4]`: per stage, the 4-bit nibble of SET_SHADER_CLIP_PLANE_MODE. It is appended at offset 416, so the D3D11 `NV2APSConstants` cbuffer and the Metal `PsConsts` grow by 16 bytes. Metal's own `tex_bias` moves from 416 to 432, with its `_Static_assert`s.
- **The emitters** (`d3d8_combiners_msl.c`, `d3d8_combiners_hlsl.c`): for a stage with `NV2A_TEXMODE_CLIPPLANE`, emit the four compares on `i.t<n>` and `discard_fragment()` / `discard`, before the stage's register is used. The register stays 0. The no-combiner shaders (`fs_basic`, D3D11 `s_ps_src`) do the same for stage 0 when its mode is 5.
- **The backends** pass `v->clip_plane_mode` into the constant (`nv2a_ps_consts_fill`), and select a combiner shader whose mode key already carries 5 (35e17dd). The legacy d3d8 HLE path (`d3d8_combiners.c`) sets `clip_mode` to 0 unless it has the register.

## Impact

- Toolkit only: `nv2a_backend_common.{h,c}`, the two emitters, `nv2a_pb_metal.m`, `nv2a_pb_d3d11.c`, `d3d8_combiners.c` (cbuffer layout).
- D3D11 can only be cross-built on the Mac. It needs a Proton run (d3d11_backend_smoke, the goldens) before merge.
- Goldens: no change expected. No BLiNX 2 scene seen so far sets mode 5: the [VSH] stage-mode census in every run of the 2026-10-05 sweep (Boss 1, 3, 4, 5, Shadow Claw; runs/metal-boss) shows modes 0, 1 and 6 only. attract, stage 1 and story were not censused; check them in task 3.2.
