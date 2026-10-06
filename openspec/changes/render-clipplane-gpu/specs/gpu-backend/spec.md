## ADDED Requirements

### Requirement: Clip-plane texture stages kill pixels on every render path
A texture stage in mode 5 (CLIPPLANE) SHALL kill the pixel on the D3D11 and Metal backends exactly as on the CPU path (`stage_clip_kills`): each of the four components of the stage's interpolated coordinate SHALL discard the pixel at `>= 0` or at `< 0`, as SET_SHADER_CLIP_PLANE_MODE (0x17F8) selects for that stage and component. The stage's register SHALL still read 0. A draw with no CLIPPLANE stage SHALL produce the same pixels as before.

#### Scenario: Smoke scene on Metal
- **WHEN** `nv2a_backend_smoke` draws a quad whose stage-0 coordinate crosses 0 along x, with stage 0 in CLIPPLANE mode, once for each sign setting
- **THEN** the Metal frame equals the CPU path's frame: the half of the quad on the killed side is not drawn

#### Scenario: Goldens unchanged
- **WHEN** the attract, stage1 and story goldens run on Metal and, under Proton, on D3D11
- **THEN** every frame keeps its verdict, since no BLiNX 2 scene seen so far uses mode 5
