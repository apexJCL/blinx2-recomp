## Why

Quantum Redshift (QR) flickers on Metal: billboards, the cave walls, the pillars and the map-select globe show torn patches that change from flip to flip. The diagnosis (runs in `runs/qrs-flicker/`, notes in `notes/qrs-flicker/`) found two causes, both in how the toolkit translates NV2A depth state:

1. **W-buffering is not emulated.** QR sets CONTROL0 (0x0290) bit 16, Z_PERSPECTIVE, on its 3D draws (CONTROL0 = 0x110001). The NV2A then stores the interpolated clip-space w, not z/w. The toolkit ignores the bit and writes the hyperbolic z/w. QR's projection puts almost all of the scene in a few ulps of z/w near 1, so coplanar and near-coplanar surfaces z-fight. A diagnostic build that wrote w as depth removed the tearing on the static countdown billboards; diff maps showed only the toggled pairs differ, at the z-fight sites.
2. **Polygon offset is ignored.** QR draws six decals per flip with SET_POLY_OFFSET_FILL_ENABLE (0x0338), factor -0.25 (0x0384) and bias -1 (0x0388). The toolkit stores these values and never applies them, so the decals fight the surface under them.

The user chose the faithful fix (2026-11-05): emulate the W-buffer as xemu does, and apply polygon offset.

## What Changes

- **W-buffered draws** (CONTROL0 Z_PERSPECTIVE set, a vertex program bound): the fragment shader writes depth from the perspective-interpolated w, as xemu does.
  - The clip range is honoured: SET_CLIP_MIN (0x0394), SET_CLIP_MAX (0x0398) and ZMIN_MAX_CONTROL (0x1D78). With CULL_NEAR_FAR the fragment is discarded outside [clip_min, clip_max]; otherwise w is clamped to that range.
  - Depth is stored as w / zmax, in the same normalised D32F format as today.
  - Polygon offset for these draws is applied in the fragment (bias plus factor times the w slope), because the hardware depth bias does not reach a shader-written depth.
  - Both GPU backends, Metal and D3D11.
- **Polygon offset for the other draws**: Metal `setDepthBias:slopeScale:clamp:`, D3D11 rasterizer `DepthBias` and `SlopeScaledDepthBias`. The bias is converted from NV2A depth units (1/zmax) to the D32F target, and the slope factor is scaled by the render scale.
- **Non-W draws are otherwise unchanged.** Their fragment shaders are byte-identical, so they keep early-Z, and BLiNX 2 output stays bit-identical (BLiNX 2 never sets Z_PERSPECTIVE or poly offset in its goldens).
- New pushbuffer state: SET_CLIP_MIN, SET_CLIP_MAX and ZMIN_MAX_CONTROL are tracked.
- A ctest (`nv2a_depth_state`) covers the translation: depth-bias units, slope scaling, the W constants and the clip-mode decode.

## Capabilities

### New Capabilities
- None (`skip_specs: true`). This is a fidelity fix to existing NV2A emulation.

### Modified Capabilities
- None.

## Impact

- Toolkit (`xboxrecomp`, off `posix-host/portability` once the tracker item lands; it starts on `fix/qrs-water` 3ff06e3c because both touch the same files):
  - `src/kernel/nv2a_pb_state.h`, `nv2a_pb_exec.c`: new state.
  - `src/kernel/nv2a_backend_common.{h,c}`: the vertex constants and the shared translation helpers.
  - `src/d3d/d3d8_vsh_msl.c`, `d3d8_vsh_hlsl.c`: the vertex epilogue outputs w.
  - `src/d3d/d3d8_combiners_msl.c`, `d3d8_combiners_hlsl.c`, `nv2a_basic_msl.h`, `nv2a_basic_hlsl.h`: the W fragment variants.
  - `src/d3d/nv2a_pb_metal.m`, `nv2a_pb_d3d11.c`: shader selection and the depth bias.
- Performance: W draws lose early-Z (the shader writes depth). The gate measures flips/s on QR's W-buffered scenes against the water tip.
- Games: QR is the first title seen using Z_PERSPECTIVE. BLiNX 2 does not set it, so its goldens must stay bit-identical.
