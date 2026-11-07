## Context

The NV2A's depth unit has two modes, chosen per draw by SET_CONTROL0 (0x0290) bit 16, Z_PERSPECTIVE:

- **Off (the default):** the depth value is the screen-space z the vertex program writes (z/w after the XDK epilogue), interpolated linearly across the triangle, in [0, zmax] (zmax 65535 for Z16, 2^24 - 1 for Z24S8).
- **On (a W-buffer):** the depth value is the clip-space w, interpolated with perspective correction. Precision is then spread evenly over the view range instead of being packed near the far plane.

The toolkit renders depth through the host's rasteriser. The vertex epilogue (`d3d8_vsh_msl.c`, `d3d8_vsh_hlsl.c`) maps the program's z to z/zmax in [0, 1] and multiplies by w, so the host divides it out again. It stores that in a D32F target (Metal D32F_S8, D3D11 D32_FLOAT_S8X24). Z_PERSPECTIVE is ignored, so a W-buffered game gets the hyperbolic z/w.

Quantum Redshift sets CONTROL0 = 0x110001 on all of its 3D draws. Its projection leaves most of the scene within a few ulps of 1.0 in z/w, so near-coplanar surfaces (billboards on their frames, cave walls, pillars, the globe's layers) z-fight and tear from flip to flip. A diagnostic build that wrote w as depth removed it (`runs/qrs-flicker/alt-count/`).

QR also sets the clip range and polygon offset:

| Method | Register | QR value |
|---|---|---|
| 0x0394 SET_CLIP_MIN | float, depth units | 0x407FFFFB (about 4.0) |
| 0x0398 SET_CLIP_MAX | float, depth units | 0x4B7FFFFF (2^24 - 1) |
| 0x1D78 SET_ZMIN_MAX_CONTROL | bits 7:4 ZCLAMP_EN: 0 cull, 1 clamp | 0x1 (cull) |
| 0x0338 SET_POLY_OFFSET_FILL_ENABLE | bool | 1 on six decal draws a flip |
| 0x0384 SET_POLYGON_OFFSET_SCALE_FACTOR | float | -0.25 |
| 0x0388 SET_POLYGON_OFFSET_BIAS | float, depth units | -1 |

The executor already stores 0x0338, 0x0384 and 0x0388 in `struct nv2a_pb_vsh` but no backend uses them. It does not track 0x0394, 0x0398 or 0x1D78.

### What xemu does (the reference)

From `hw/xbox/nv2a/pgraph/glsl/psh.c` and `pgraph.c` (xemu master, read 2026-11-05):

- W mode: `zvalue` is the perspective-correct w at the fragment. If `zvalue > 0`, it adds `depthOffset` (the bias) and `depthFactor * triMZ * zvalue^2` (the slope term, from a per-triangle slope of 1/w). Otherwise `zvalue = FLT_MAX`. A NaN becomes FLT_MAX.
- Both modes, when ZCLAMP_EN is CULL: discard if `zvalue` is outside [clip_min, clip_max]; when CLAMP: clamp it to that range.
- The depth is written from the shader: `zvalue / zmax` for a float target (`clipRange.y` is zmax), `floor(zvalue)` scaled for D16 and D24.
- The bias and factor count only when polygon offset is enabled for the primitive's fill mode (SETUPRASTER POFFSETFILLENABLE for filled triangles; the line and point enables for those modes), and only for triangle-family primitives.
- xemu notes the W slope term as "only partially implemented".

## Goals / Non-Goals

**Goals:**
- W-buffered draws store the interpolated w, honour the clip range and the ZCLAMP_EN mode, and take polygon offset, on Metal and D3D11.
- Polygon offset on the hardware depth bias for the other draws.
- Non-W draws without polygon offset run exactly the shaders and state they run today: the same fragment text, early-Z kept, BLiNX 2 goldens bit-identical.

**Non-Goals:**
- Writing depth from the shader for non-W draws (xemu does it for all draws; that would cost every game its early-Z for a fidelity gain no game here needs).
- The clip range for non-W draws. The toolkit's near and far policy (the host clipper, plus the depth-off far-plane rule in `nv2a_vp_consts_fill`) stays as it is.
- W-buffering for draws without combiners (`fs_basic`) and for pre-transformed draws without a vertex program (`vs_pass`). On hardware every draw with Z_PERSPECTIVE set stores w; these keep z/w here, a known gap (see Risks). QR has none (every W draw in `runs/qrs-flicker/mlog-race` programs the combiners and runs a vertex program). They go in TASKS.md as a follow-up.
- Line and point polygon offset (0x0330, 0x0334). Not seen in use.
- Float depth formats (CONTROL0 Z_FORMAT, bit 12). QR does not set it.
- The CPU rasteriser: it only has to build. Its gap goes in TASKS.md.

## Decisions

### 1. Which draws take the W path

A draw is W-buffered when all of these hold:
- CONTROL0 bit 16 is set;
- the depth test is on (with it off, the NV2A neither tests nor writes depth, and the toolkit's depth-off rule keeps the far plane open);
- the draw runs a vertex program (`d->program`), so its vertex output carries w (decision 3);
- the combiners are programmed, so it uses the generated fragment shader (decision 4).

The backend decides this when it selects the fragment shader. A W fragment variant that fails to compile falls back to the stock pair, with the vertex side switched off too, so the two always agree. On D3D11 a failed update of the W constants (b1) falls back the same way. Both backends then choose the hardware depth bias from the shader actually bound: a draw that ends up on any stock or debug shader keeps z/w and takes its polygon offset in hardware.

### 2. New state

`struct nv2a_pb_vsh` gains `clip_min`, `clip_max` (floats), `clip_set` and `zminmax_ctl` (raw). `nv2a_pb_exec.c` records them from 0x0394, 0x0398 and 0x1D78. `clip_set` has one bit per register: until a title writes one, its end of the range stays at the default (0 for the min, zmax for the max), so a title that writes only CLIP_MIN does not cull every W fragment.

### 3. Vertex side

The screen-space epilogue (MSL and HLSL) gains:
- an output `zw` (MSL `[[user(zw)]]`, HLSL `TEXCOORD6`, after oB1), equal to the clip w `pw`. The host interpolates it with perspective correction, which gives the true w at the fragment.
- in W mode, `pos.z = 0.5 * pos.w`. The host's near and far clip then never fires on z (z/w is 0.5), so the clip range alone decides which fragments survive, as on the NV2A. A vertex behind the eye (w <= 0) is still clipped by the host.

W mode is a uniform: `nv2a_vp_consts.u[7]` (`spec_ctl.w`), free today. The vertex text does not depend on it, so a program has one vertex shader for both modes. The extra output is unused by the stock fragment shaders, which read a prefix of the vertex output (MSL by attribute name, HLSL by register order), so non-W output is unchanged.

### 4. Fragment side

`NV2ACombinerState` gains `w_depth`, set by the backend; it is part of the shader cache key and hash, as `rect_snap` is. With `w_depth` 0 the generated text is byte-identical to today's. With 1:
- MSL: the stage-in struct is `VOut` plus `float zw [[user(zw)]]`; the function returns `struct FOut { float4 c [[color(0)]]; float d [[depth(any)]]; }`; the constants come in a new `constant WDepth &wd [[buffer(1)]]`.
- HLSL: `PS_IN` declares the whole `VS_OUT` layout up to `zw : TEXCOORD6` (register order must match); the function returns `PS_OUT { float4 c : SV_Target; float d : SV_Depth; }`; the constants come in `cbuffer WDepthCB : register(b1)`.
- The code, at the top of the function (uniform control flow, for the derivatives):

  ```
  float zv = i.zw;
  if (zv > 0.0) {
      zv += wd.w0.x + wd.w0.y * max(abs(dfdx(i.zw)), abs(dfdy(i.zw)));
  } else {
      zv = FLT_MAX;
  }
  if (isnan(zv)) zv = FLT_MAX;
  bool wkill = wd.w1.y != 0 && (zv < wd.w0.z || wd.w0.w < zv);
  zv = clamp(zv, wd.w0.z, wd.w0.w);
  ```

  and at the end, next to the alpha test: `if (wkill) discard`, then depth = `saturate(zv * wd.w1.x)`.
- Constants (`struct nv2a_wdepth_consts`, two float4s):

  | Field | Value |
  |---|---|
  | w0.x | the bias, when polygon offset applies (decision 5), else 0 |
  | w0.y | the factor times the render scale N, when polygon offset applies, else 0 |
  | w0.z, w0.w | clip_min, clip_max |
  | w1.x | 1 / zmax |
  | w1.y | 1 when ZCLAMP_EN is 0 (cull), 0 when 1 (clamp) |

- The slope term differs from xemu's form, `factor * triMZ * w^2`, where triMZ is the per-triangle slope of 1/w. This design uses the per-pixel slope of w itself. Since d(w) = -w^2 d(1/w), the two agree to first order. The host derivative is per host pixel; the NV2A's is per guest pixel, hence the factor N.

### 5. Polygon offset for non-W draws

Polygon offset applies when 0x0338 is set and the primitive is in the triangle family (triangles, strips, fans, quads, quad strips, polygons). The executor sets no line or point enables.

| | Metal | D3D11 |
|---|---|---|
| Call | `setDepthBias:slopeScale:clamp:` | rasterizer `DepthBias`, `SlopeScaledDepthBias`, `DepthBiasClamp` 0 |
| Constant | `bias * 2^24 / zmax` | the same, rounded to an int |
| Slope | `factor * N` | `factor * N` |

- The bias is in NV2A depth units, 1/zmax of the stored range. A float target's bias unit is 2^(e - 23), with e the exponent of the largest z in the triangle. For z in [0.5, 1), where 3D scenes sit, the unit is 2^-24. So `bias * 2^24 / zmax` gives the NV2A's offset exactly there: x1 for Z24, x256 for Z16. Nearer the camera (smaller z) it is smaller than the NV2A's. That is accepted: the offset only has to separate a decal from its surface.
- The slope term: NV2A's factor multiplies the depth slope per guest pixel; the host's per host pixel. So the factor is scaled by N.
- D3D11 keys its rasterizer-state cache on the two values. Metal sets the bias per draw, and only when it changes from the last value set in the encoder, so a stock draw issues no new call.

### 6. A standalone translation helper

The arithmetic lives in `nv2a_backend_common.{h,c}`, with no GPU dependency:
- `nv2a_poly_offset_on(v, prim)`: whether the offset applies;
- `nv2a_depth_bias(v, surface_format, scale, &bias, &slope)`;
- `nv2a_w_depth_on(v, program, combiners)`;
- `nv2a_wdepth_consts_fill(v, prim, surface_format, scale, &out)`.

A new ctest, `nv2a_depth_state`, checks them: the bias units for Z16 and Z24, the slope scaling at N = 1 and 3, the cull and clamp decode of 0x1D78, the clip range and zmax constants, the off cases (no enable, a line primitive, the depth test off), and the reset values.

## Risks / Trade-offs

- **Early-Z loss on W draws.** These draws write depth from the shader, so the GPU tests depth after shading. The gate measures QR flips/s on W scenes against the water tip on Metal. D3D11 needs the PC or the Deck, so the agent leaves that measurement to the coordinator.
- **The clip range culls.** With QR's CULL mode, fragments with w < 4 are discarded, as the NV2A discards them. If QR relies on something nearer the camera surviving, it shows in the A/B as a hole; xemu has the same behaviour.
- **Precision.** The stored value is w/zmax in a 32-bit float, finer than the NV2A's 24-bit integer (xemu floors to the integer for D24). Where the NV2A gives two surfaces equal depth, the float can still order them. That is less z-fighting than hardware, not more.
- **Mixed passes.** A W draw and a non-W draw (CONTROL0 bit 16 clear) that test against each other's depth compare w/zmax with z/zmax. On the NV2A the same mix compares raw w with raw z, so the behaviour matches for those.
- **Known gap: W draws off the W path.** A draw that sets Z_PERSPECTIVE but uses `fs_basic` or `vs_pass` (or falls back to a stock shader) keeps z/w, while the NV2A stores w for it. Against W draws in the same depth buffer it then compares z/zmax with w/zmax, which the hardware never does. QR has no such draws. A TASKS.md follow-up covers it.
- **D3D11 bias cache.** D3D11 keeps at most 16 biased rasterizer states. Past that a batch draws without its offset, and one stderr line says so the first time.
- **The same files as the tracker item** (QR water). This branch starts at `fix/qrs-water` 3ff06e3c and rebases onto `posix-host/portability` after that squash lands.
