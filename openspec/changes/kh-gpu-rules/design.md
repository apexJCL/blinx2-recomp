## Context

- **Clears.** `nv2a_clear_box` (`nv2a_backend_common.h`) is the one rule the CPU path (`clear_surface`), D3D11 (`clear_region`) and Metal (`metal_on_clear`) share for every clear. `clear_rect_set` latches once the title sends `SET_CLEAR_RECT_HORIZONTAL/VERTICAL` (0x1D98/0x1D9C, inclusive max). It is never reset, because it is GPU state, not per-frame state.
- **Render targets.** A GPU render target is sized by the clip's far corner and grown by `rt_grow` when a later clip reaches further. One target can serve several clip extents in a frame (Burnout 3's 159x344 sub-clears of a 640x480 buffer).
- **Near clip.** The CPU path clips in screen space (`clip_tri`, Sutherland-Hodgman, used only by `raster_batch_vsh`) against a w ≥ 1e-5 plane, a ±16384-pixel guard band, and, with depth on, 0 ≤ z ≤ zmax. The GPU backends hand clip-space positions to the GPU, which always clips near.
- **Texture addressing.**
  - `SET_TEXTURE_ADDRESS` holds four bits per axis: 1 wrap, 2 mirror, 3 clamp-to-edge, 4 border, 5 clamp.
  - FORMAT bit 3 (BORDER_SOURCE) chooses between the texture's own border texels (0) and `SET_TEXTURE_BORDER_COLOR` (1).
  - Before this change every path mapped 4 to clamp-to-edge.
  - The CPU sampler has a live path (`sample_tex`, for screen-space draws) and a cached path (`texel_cached` over `wrap_signed`, for vertex-program draws).

## Decisions

### D1. The clear rect alone, clamped to the surface (fix a)

The box is `[rect_x0, rect_x1] × [rect_y0, rect_y1]` once a rect is set, else the clip. It is clamped to the surface, then to the w × h target the caller passes:
- swizzled surface (SURFACE_FORMAT type 2): `1 << ((format >> 16) & 0x1F)` by `1 << ((format >> 24) & 0x1F)`;
- pitch surface: the clip's far corner, `clip_x + clip_w` by `clip_y + clip_h`. xemu sizes a pitch surface this way, and the memory past it is not the surface's.

The helper computes the surface extent from the state it already receives. No caller has to compute it, so the three backends cannot drift apart.

Known limit: a GPU target sized by the clip can cut short a swizzled rect that reaches past the clip, because the target is smaller than the surface. Neither title does this (spike logs). Growing the target to the swizzled size on a clear is a follow-up (TASKS), not part of this change.

The smoke tests' clip-clear case used to rely on clip∩rect to clear only the clip while a full-surface rect was latched. It now sets the rect to the clip first, as D3D's `Clear` sends it. That is what titles do.

Rejected: #212's split, with the rect alone on swizzled surfaces and the clip on pitch ones. xemu has no such split, and #212 gives no reason for it beyond its one title.

### D2. Near plane always, far plane with depth on (fix b)

`clip_tri` uses `nplanes = depth ? 7 : 6`, and `clip_inside_all` tests z ≥ 0 from six planes and z ≤ zmax from seven. The far plane stays depth-on, as this path drew before, because 2D batches routinely carry z past zmax. Whether the NV2A culls beyond zmax with depth off is not settled. xemu's ZCLAMP CULL is not gated on the depth test, and the D3D11 and Metal paths clip far with depth off. That is a follow-up (tasks 3.3), not part of this change. The near plane sits at screen z = 0. That equals #211's c[59].z·w in clip space for the XDK's viewport, as the spike showed.

### D3. Border colour per backend (fix c)

`nv2a_stage_decode` keeps mode 4 only with BORDER_SOURCE = 1. With the texture as the source, the border is the texture's own border texels, which the fork does not decode. Clamp-to-edge stays the nearest stand-in, so the decoded mode is 3. The stage carries `border` (register 0x24 of the stage block, 0x1B24 + 0x40·n).

- **D3D11.** `D3D11_TEXTURE_ADDRESS_BORDER` takes any colour. Two stages with the same filter and modes but different colours need different sampler objects, so the cache entry stores the colour and matches on it. The colour counts only when an axis uses border, so a stray colour register does not multiply samplers.
- **Metal.** `MTLSamplerBorderColor` has three values: transparent black, opaque black and opaque white. The key gains 2 bits (the preset plus 1, or 0 for none). A colour that is not a preset falls back to clamp-to-edge, which is the pre-change behaviour, and logs once. Burnout 3's 0x00000000 is a preset. The gap for other colours goes in TASKS. Emulating it in the shader (testing the UV per tap) would cost every sampled stage.
- **CPU.**
  - `wrap_signed` returns −1 on a border axis off the texture, and `texel_cached` returns the border colour for −1, so bilinear blends into the border at the edge as the hardware does.
  - The live path's `tex_border_tap` does the same for screen-space draws.
  - The screen-space path used to clamp negative coordinates to 0 before sampling. On a border axis it now passes them as out of range (UINT32_MAX).
  - `border_on` (FORMAT bit 3) gates the live path, because that path reads raw `SET_TEXTURE_ADDRESS` with no decode in between.

Mirror (mode 2) on the CPU path stays a clamp. It is a separate fix, recorded in TASKS: Burnout 3's stage 0 uses it, and the GPU backends already mirror.

## Validation

- `tests/pb_clip_border` (POSIX, CPU path):
  - A quad whose z runs from −100 to +100 draws only its z ≥ 0 half, with depth off and on.
  - With a red 16x16 texture and UVs from −0.5 to 1.5, the taps left of, right of, above and below the texture are the border colour, nearest and bilinear. The test uses an odd colour (0xFF20C040) and 0x00000000. The middle is red.
  - With the texture as the source, the edge texel shows.
  - Against the base exec.c it fails 17 checks.
- `nv2a_backend_smoke` (Mac):
  - CC_RECT2: clip (100,100,160,120) with rect (50,50)-(399,299) clears (50,50)-(259,219). The run is stopped by the pitch surface's far corner, and the clip does not cut it.
  - Border cases: zero, white, odd colour (CPU only) and texture source. The CPU path is checked against fixed probes and then pixel-for-pixel against Metal.
- `d3d11_backend_smoke` (mingw exe under Proton on the Deck): the same rect case and three border colours, with D3D11 checked against the CPU path.
- BLiNX 2 goldens on Metal (`blinx2 golden run`) and D3D11 (`blinx2 bench golden` on the Deck) should pass unchanged.
- Burnout 3 A/B, base 70c43712 against the branch, on Metal and on Deck D3D11:
  - The same scripted path, frames dumped at the same flips.
  - Changed frames are attributed to border-sampled passes. Any other change is a regression to explain.
- Perf: flips/s on Metal and D3D11, base against branch, against the CLAUDE.md thresholds (25% flips/s, 1.5x frame ms).
