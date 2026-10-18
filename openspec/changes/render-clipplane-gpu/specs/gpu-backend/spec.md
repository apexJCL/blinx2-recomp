## ADDED Requirements

### Requirement: Clip-plane texture stages kill pixels on every render path
On a draw through the register combiners, a texture stage in mode 5 (CLIPPLANE) SHALL kill the pixel on the D3D11 and Metal backends exactly as on the CPU path (`stage_clip_kills`). On a draw without combiners, stage 0 in mode 5 SHALL kill the pixel on both backends by the same rule. Each of the four components of the stage's interpolated coordinate SHALL discard the pixel at `>= 0` or at `< 0`, as SET_SHADER_CLIP_PLANE_MODE (0x17F8) selects for that stage and component. The stage's register SHALL still read 0. A draw with no CLIPPLANE stage SHALL produce the same pixels as before.

#### Scenario: Smoke scene on Metal
- **WHEN** `nv2a_backend_smoke` draws a quad whose stage-0 coordinate crosses 0 along x, with stage 0 in CLIPPLANE mode, once for each sign setting
- **THEN** the Metal frame equals the CPU path's frame: the half of the quad on the killed side is not drawn

#### Scenario: Draw without combiners
- **WHEN** `nv2a_backend_smoke` (Metal) and `d3d11_backend_smoke` draw the same quads with COMBINER_CONTROL 0 and stage 0 in CLIPPLANE mode, once for each sign setting
- **THEN** the basic shader kills from `clip_mode.x` the way xemu does, and the four probes show the killed half missing on each quad
- **AND** the CPU path is not the reference here: its no-combiner rasteriser kills only a textured stage 0, a gap recorded as a follow-up in TASKS.md

#### Scenario: Goldens unchanged
- **WHEN** the attract, stage1 and story goldens run on Metal and, under Proton, on D3D11
- **THEN** every frame keeps its verdict, since no BLiNX 2 scene seen so far uses mode 5
