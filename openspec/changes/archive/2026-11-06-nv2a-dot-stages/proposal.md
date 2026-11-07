# nv2a-dot-stages: the texture shader's dot-product modes and cube maps

## Why

On Quantum Redshift's track 2, the water draws as an opaque, flat brown
plane over the lower half of the screen and hides the submerged ship.
It is draw 0x42 of flip 2850 (runs/qrs-water/mlog2850c). Its
stage program `SET_SHADER_STAGE_PROGRAM` is 0x64621:

- stage 0: PROJECT2D on a normal map;
- stages 1 and 2: DOTPRODUCT (stage 1 is disabled: it reads no texture);
- stage 3: DOT_RFLCT_SPEC on a DXT5 cube map at 0x2B65700.

`SET_DOT_RGBMAPPING` is 0x111. The combiner writes `tex3 * diffuse`
with the diffuse alpha, and the vertex program sends the
tangent-to-world rows in oT1..oT3 with the eye vector in their w.

Both GPU backends sampled every texture-shader mode other than NONE,
PASSTHRU, CLIPPLANE and BUMPENVMAP as a 2D texture at (s, t). They also
bound a cube map as its face 0 alone. So stage 3 read one face of the
sky cube at almost constant coordinates: one brown colour over the whole
plane. A run that skips the draw shows the ship and the riverbed
(runs/qrs-water/w03-skipwater).

The dot-product modes are the NV2A's per-pixel reflection and lighting.
XDK titles reach them through D3D pixel shaders (texm3x3vspec,
texm3x3tex, texdp3, texreg2ar and the rest), so the gap is not QR's
alone. The same backends also demoted every CUBEMAP stage to a face-0 2D
read, which loses environment maps everywhere.

## What Changes

- **Executor**: keep `SET_DOT_RGBMAPPING` (0x1E74) in the vertex state.
- **Shared decode** (`nv2a_backend_common.h`):
  - `nv2a_stage_ps_mode` keeps the dot-product family (modes 8 to 0x12)
    in the stages each mode may sit in;
  - it keeps CUBEMAP over a square cube texture it can bind;
  - `nv2a_ps_stage_key` packs the modes, the input stages, the dot
    mappings and the cube bits for both backends' shader keys;
  - new helpers give the face stride and the cube extent.
- **Generators** (MSL and HLSL, twins): emit xemu's texture-shader
  arithmetic for the dot modes. This covers the dot products on the
  mapped input texel, DOT_ST, DOT_ZW (reads 0), DOT_RFLCT_DIFF,
  DOT_RFLCT_SPEC, DOT_STR_3D and DOT_STR_CUBE, and DPNDNT_AR/GB.
  A cube-reading mode declares a cube texture when its stage binds one.
  Over a 2D texture, the mode reads it at xemu's `remapCubeTo2D`.
- **Metal and D3D11**: decode all six faces of a cube texture into one
  cube texture, and bind it as a cube for the combiners' shader. A batch
  whose combiners' shader is missing keeps the face-0 2D read.
- **ctest `nv2a_dot`**: decode of the water's registers, the
  stage-placement rules, the face stride, the packed key and the
  generated text in both languages.

The D3D8 front end (`bump_on` 0) and the CPU rasteriser are unchanged.
The CPU path keeps sampling these modes as 2D (a gap, in TASKS).
