## Why

Texture-shader mode 5, CLIPPLANE, turns a stage into four user clip-plane distances: each component of the stage's interpolated coordinate kills the pixel at `>= 0` or at `< 0`, as SET_SHADER_CLIP_PLANE_MODE (0x17F8) picks per stage and component (xemu psh.c; toolkit e03f9ff3, which ports upstream 13c64d3). The CPU path does it (`stage_clip_kills`, `nv2a_pb_exec.c`). The Metal and D3D11 backends do not. Since toolkit 35e17dd1 their combiner key carries mode 5 (`nv2a_stage_ps_mode` reads `raw_mode`) and the emitters bind no texture for the stage and leave its register 0, but every pixel survives. `build_stages` in both backends (`nv2a_pb_metal.m` ~1287, `nv2a_pb_d3d11.c` ~1595) also binds the stage as mode 0, so the no-combiner shaders cannot tell a CLIPPLANE stage 0 from an empty one. A title that uses user clip planes (portal or water cuts, mirror passes) draws geometry on the GPU paths that the hardware and the CPU path cut away. That breaks "Backends agree".

The Metal boss-scene sweep (2026-10-05, branch `metal-boss/fixes`) checked whether any reported defect was this: none was. Boss 1's sky, Boss 3's water, the Shadow Claw ellipse and the Silver Claw shapes all draw the same on the CPU path, which has the kill. So nothing on screen is known to need this yet. It is a bounded gap, recorded so the next title or scene that uses clip planes does not have to rediscover it.

## What Changes

- **A clip-plane constant for the combiner shaders.** `struct nv2a_ps_consts` (`nv2a_backend_common.h`) gains `uint32_t clip_mode[4]`, appended after `bumpls` at offset 544, so it grows from 544 to 560 bytes. Per stage, it holds `0x10 | nibble` when the stage is in mode 5 (the nibble is the stage's 4 bits of SET_SHADER_CLIP_PLANE_MODE), else 0. The `0x10` flag is needed because nibble 0 is a valid plane setting (every component dies at `< 0`) and `tex_mode` reads 0 for a CLIPPLANE stage. The D3D11 `PsConsts` and the legacy `NV2APSConstants` grow with it. Metal's `MsPsConsts.tex_bias` moves from 544 to 560 and `sizeof(MsPsConsts)` from 560 to 576, with their `_Static_assert`s.
- **The emitters** (`d3d8_combiners_msl.c`, `d3d8_combiners_hlsl.c`): for a stage with `NV2A_TEXMODE_CLIPPLANE`, emit the four compares on `i.t<n>` / `i.tc<n>` (the `nv2a_clip_kills` helper, emitted once when some stage is CLIPPLANE) and `discard_fragment()` / `discard` at the end, beside the alpha test. The register stays 0. The no-combiner shaders (Metal `fs_basic`, D3D11 `s_ps_src`) do the same for stage 0 from `clip_mode.x`.
- **The backends** fill the constant from `s_vsh.clip_plane_mode` in `nv2a_ps_consts_fill`, gated on the stage's `raw_mode == 5`. The legacy d3d8 HLE path (`d3d8_combiners.c`, which fills `NV2APSConstants` on a fresh WRITE_DISCARD map) writes `clip_mode` 0, so it keeps its behaviour.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `gpu-backend`: CLIPPLANE stages kill pixels on the D3D11 and Metal backends, as on the CPU path.

## Impact

- Toolkit only: `nv2a_backend_common.{h,c}`, the two emitters and `d3d8_msl.h` (the MSL constant block), `nv2a_pb_metal.m`, `nv2a_pb_d3d11.c`, `d3d8_combiners.{h,c}` (cbuffer layout); tests `d3d8_msl_split`, `d3d8_hlsl_split`, `nv2a_backend_smoke`, `d3d11_backend_smoke`.
- D3D11 can only be cross-built on the Mac. It needs a Proton run (d3d11_backend_smoke, the goldens) before merge.
- Goldens: no change expected. No BLiNX 2 scene seen so far sets mode 5: the [VSH] stage-mode census in every run of the 2026-10-05 sweep (Boss 1, 3, 4, 5, Shadow Claw; runs/metal-boss) shows modes 0, 1 and 6 only. attract, stage 1 and story were not censused; task 3.2 checks them.
- Shader text: every combiner shader gains the constant in its block, so the recorded MSL and HLSL hashes change; only shaders with a CLIPPLANE stage gain code.

## Status

Corrected 2026-10-17 against toolkit 878d473a: the layout offsets (the spec said 416/432/448; bump and bumpls had moved `nv2a_ps_consts` to 544 bytes), the line references, how the backends bind a CLIPPLANE stage, and the `0x10` flag. Implementation on toolkit branch `fix/clipplane-gpu`.
