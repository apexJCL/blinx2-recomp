## ADDED Requirements

### Requirement: Bump-environment texture stages are sampled on both GPU backends
A texture stage in texture-shader mode 6 (`BUMPENVMAP`) or 7 (`BUMPENVMAP_LUMINANCE`) SHALL be sampled by the D3D11 and Metal backends at `(s, t) + M * (du, dv)`, where `(du, dv)` are the input stage's blue and green taken from unsigned bytes back to two's complement over 127 (xemu's `sign3`), `M` is the stage's bump matrix, and the offset is added in the coordinate's own units before the stage's `tex_scale`. Mode 7 SHALL further scale all four channels of the sampled texel by `input.red * BUMP_ENV_SCALE + BUMP_ENV_OFFSET`. The input stage SHALL be stage 0 for stage 1 and the stage named by bits 16-19 and 20-23 of `SET_SHADER_OTHER_STAGE_INPUT` for stages 2 and 3, clamped to an earlier stage, through one shared helper. The four matrix registers (`SET_TEXTURE_SET_BUMP_ENV_MAT`, 0x1B28..0x1B34 of the stage) SHALL be read as m00, m01, m11, m10, so `du' = m00*du + m10*dv` and `dv' = m01*du + m11*dv`; this order is one hardware fact held in the shared decode and generators, never in a per-title quirk. The HLSL and MSL generators SHALL emit the same arithmetic, and the stock text for every other mode SHALL be unchanged. The CPU rasteriser keeps sampling these modes as plain 2D, recorded as a gap.

#### Scenario: Decode and constants
- **WHEN** a stage's register block holds `(a, b, c, d)` at offsets 0x28..0x34, `e` at 0x38 and `f` at 0x3C
- **THEN** `nv2a_stage_decode` yields `bump = {a, b, c, d}`, `bump_scale = e`, `bump_offset = f`, and `nv2a_ps_consts_fill` places them in `bump[n]` and `bumpls[n].xy` for both backends

#### Scenario: Generated text, both languages
- **WHEN** stage 1 is in mode 6 fed by stage 0 and stage 2 in mode 7 fed by stage 1, with `bump_on` set
- **THEN** the HLSL and the MSL each contain the two dot products on `bump[n].xw` and `bump[n].yz`, the 127 divisor, the offset added before `tex_scale`, and for stage 2 the luminance scale on the whole texel; the MSL compiles with Metal on the Mac; the same state without `bump_on` emits the plain 2D sample

#### Scenario: Water on a second title
- **WHEN** BLiNX 2's stage-1 ocean (attract and stage1 scenarios) and Boss 3 ripple are drawn on Metal and on D3D11
- **THEN** the water regions change against main's references while nothing else in the frame moves beyond its run-to-run spread, the error against the xemu captures does not rise, and the two backends agree within the golden limits

#### Scenario: Slots a frame can confirm
- **WHEN** the `bump` trace logs the matrices BLiNX 2 and Burnout 3 write
- **THEN** a diagonal matrix counts as confirming slot 2 only; the transpose of slots 1 and 3 is counted as confirmed by frame only if a title writes a matrix with `m01 != m10` and that scene matches xemu under the m00, m01, m11, m10 reading, otherwise it stays open in TASKS

### Requirement: Anisotropic filtering follows one rule on both backends
With `render.aniso = N` (2..16) set, the D3D11 and Metal samplers SHALL use anisotropic filtering with `MaxAnisotropy = N` only for a stage whose texture has more than one mip level, whose minification filter is linear, whose mip filter is not none, that is not a cube map, and when point sampling is not forced; min, mag and mip filters SHALL be linear under it on both backends. Every other stage SHALL keep the stock sampler. The anisotropy SHALL be part of each backend's sampler key in the same bit position (35), and SHALL be read at start.

#### Scenario: World sharper, screen-aligned content unchanged
- **WHEN** the stage-1 fly-over runs with `RECOMP_RENDER_ANISO=16` on Metal and on D3D11
- **THEN** a window shot shows the ground sharper at grazing angles than at stock, and the HUD, render targets read back and movie frames are unchanged

#### Scenario: Off by default
- **WHEN** no key is set
- **THEN** no sampler on either backend is anisotropic and the `[ENHANCE]` line reads `render.aniso=0`
