## ADDED Requirements

### Requirement: Dot-product texture stages and cube maps are sampled on both GPU backends
The D3D11 and Metal backends SHALL generate the NV2A texture shader's dot-product modes (8 to 0x12) with xemu's arithmetic, in the stages each mode may occupy (`nv2a_dot_mode_ok`). A mode outside those stages SHALL be sampled as 2D.

- Each dot stage i SHALL compute `dot(T_i.xyz, map(input texel))`. The input stage SHALL come from `nv2a_stage_input`. `map` SHALL be the stage's field of `SET_DOT_RGBMAPPING` (0x1E74), which the executor keeps: with x the byte value, 1 is xemu's sign1 `(x - 128)/127`, 2 is sign2 `x >= 128 ? (x - 255.5)/127.5 : (x + 0.5)/127.5`, 3 is sign3 (two's complement over 127), and the other values pass the texel through.
- DOTPRODUCT SHALL keep its mode when its stage is disabled, since it reads no texture. It, DOT_ZW, BRDF and DOT_RFLCT_SPEC_CONST SHALL read 0.
- DOT_ST, DOT_STR_3D and DPNDNT_AR/GB SHALL read 2D, under the stage's `tex_scale`.
- DOT_RFLCT_DIFF, DOT_RFLCT_SPEC (the eye vector from T1.w, T2.w, T3.w) and DOT_STR_CUBE SHALL read a cube.

A stage whose mode reads a cube (CUBEMAP included), that is bound, and whose texture is a square `CUBEMAP_ENABLE` texture SHALL be decoded as six faces. Face f SHALL be decoded at `offset + f * nv2a_stage_face_stride`. Each backend SHALL cache it as one entry keyed as a cube, and SHALL bind it as a cube texture, but only for the combiners' shader. A batch on the basic shader SHALL read face 0 as 2D. A cube whose six-face span overlaps a live render target SHALL NOT be bound as a cube: its key, shader and bind SHALL take the 2D read on both backends, from the target where one starts at its offset. A cube-reading mode over a 2D texture SHALL read it at `remapCubeTo2D`.

The key (`nv2a_ps_stage_key`) SHALL hold the modes, the input stages, the dot mappings and the cube bits in the same layout on both backends. The MSL and HLSL generators SHALL emit the same arithmetic. The text for every state without a dot mode or a bound cube SHALL be unchanged. The CPU rasteriser keeps sampling these modes as 2D, recorded as a gap.

#### Scenario: Quantum Redshift's water
- **WHEN** Quantum Redshift's track-2 water, stage program 0x64621 with `SET_DOT_RGBMAPPING` 0x111, is drawn on Metal
- **THEN** the water is a translucent surface with ripples and reflections over the riverbed and the submerged ship, not one flat brown plane (runs/qrs-water/w01-base present 2850 against w05-fix-mlog present 2700, same place on the track)

#### Scenario: Decode, key and text (ctest)
- **WHEN** `tests/nv2a_dot` decodes the water's registers, with stage 1 disabled
- **THEN** the shader modes are 1, 0x11, 0x11 and 0x0C, and only stage 3 binds a cube
- **AND** the face stride is the 128-aligned span of the six DXT5 levels
- **AND** the key holds mapping 1 for stages 1-3 and the stage-3 cube bit
- **AND** the MSL and HLSL declare `tex3` as a cube, declare no `tex1` or `tex2`, and contain the three dots and the reflection vector
- **AND** with no cube bound they read `tex3` through `nv2a_cube_2d`
- **AND** the same modes without `bump_on` give the plain 2D text
- **AND** with the cube's faces under a live render target, the key has no cube bit and CUBEMAP reads 2D
- **AND** a DOT_RFLCT_DIFF stage 2 packs stage 3's input and mapping, and `nv2a_bump_sources` counts the dot and DPNDNT inputs

#### Scenario: Dot states compile (ctest)
- **WHEN** `d3d8_hlsl_split`, `d3d8_msl_split` and `d3dcompile_smoke` run the shared dot cases (`dot_cases.h`)
- **THEN** the HLSL text declares cubes exactly where the state binds one and applies no `alpha_only` fix-up to a stage that reads no texture, the MSL compiles with Metal, and on Windows the HLSL compiles with D3DCompile

#### Scenario: Environment cubes on a second title
- **WHEN** BLiNX 2 runs its golden scenarios on Metal and on D3D11
- **THEN** the verdicts pass within the golden limits
