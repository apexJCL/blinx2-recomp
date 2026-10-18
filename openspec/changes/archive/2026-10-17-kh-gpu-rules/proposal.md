## Why

The koenhendriks GPU spike (`notes/kh/gpu.md`, spike branch `spike/kh-gpu` c36f3a14, runs in `xbox-recomp/runs/kh-gpu/`) compared upstream PRs #211 and #212 with the fork's renderer. It found three places where the fork differs from the hardware rule as xemu models it:

- **(a) Clear rect.** `nv2a_clear_box` bounds a colour clear (depth and stencil clears do not go through it) by the surface clip intersected with `SET_CLEAR_RECT`. xemu, and #212 on swizzled surfaces, clear the clear rect alone, clamped to the surface. #212's SSX 3 case clears 128x128 under a 124x124 clip, and the texture is sampled clamped, so our rule leaves a 2-pixel ring uncleared on all three backends. The spike logged every clear in BLiNX 2 and a Burnout 3 race: neither title sends a rect that reaches past its clip, so their frames do not move. For them this is a fidelity change only.
- **(b) Near clip on the CPU path.** The CPU rasteriser's vertex-program path clips at z ≥ 0 only when the depth test is on. The NV2A clips there regardless of the depth test (xemu's ZCLAMP CULL), and D3D11 and Metal already do. #211 clips near always. A depth-off batch that crosses the near plane draws its in-front part on the CPU path only. The spike's always-on variant passes the BLiNX 2 CPU goldens.
- **(c) Border address mode.** Mode 4 (border) is mapped to clamp-to-edge on every path. Burnout 3 uses it on stages 0-3 with FORMAT's BORDER_SOURCE bit set and a border colour of 0x00000000, so taps past the texture return the edge texel instead of transparent black. Stage 0 also uses mirror (mode 2), which the CPU path clamps.

## What Changes

- **Clear rect alone, clamped to the surface, on every backend.** `nv2a_clear_box` uses the clear rect once the title has set one, and the clip only before that. It clamps the box to the surface extent: 1 << log2 per axis for a swizzled surface (SURFACE_FORMAT), or the clip's far corner for a pitch surface (xemu sizes a pitch surface that way). It also clamps to the render target it is given. The CPU path bounds its memory check by the same extent. We adopt #212's rule, not its code, and extend it to pitch surfaces.
- **Near plane always clips on the CPU path.** `clip_tri` uses six planes with depth off (the guard band plus z ≥ 0) and seven with depth on (plus z ≤ zmax). This is #211's rule, inside the fork's existing screen-space clipper; #211's code is not taken.
- **Border colour on D3D11, Metal and CPU.** `nv2a_stage_decode` keeps mode 4 when BORDER_SOURCE selects the colour, and carries `SET_TEXTURE_BORDER_COLOR` (0x1B24 + 0x40·n). With the texture as the source it keeps the clamp-to-edge stand-in.
  - D3D11: `D3D11_TEXTURE_ADDRESS_BORDER` with `BorderColor`. The colour joins the sampler cache key on the axes that use it.
  - Metal: `ClampToBorderColor`, when the colour is one of Metal's three presets (0x00000000, 0xFF000000, 0xFFFFFFFF). Any other colour clamps to the edge and logs once.
  - CPU: the live sampler, the decoded-texture cache and the screen-space path return the border colour for taps off the texture.
- **Tests.**
  - A new POSIX ctest, `tests/pb_clip_border`, covers the vertex-program path: the near plane with depth off and on; the border colour, nearest and bilinear; and the texture as the source.
  - `nv2a_backend_smoke` and `d3d11_backend_smoke` gain a clear-rect-past-the-clip case and border cases, each compared between the CPU path and the GPU backend.
- **No env key.** All three changes follow the hardware rule, with no switch, as for other fidelity fixes.

## Impact

- Toolkit only:
  - `src/kernel/nv2a_backend_common.{h,c}`, `nv2a_pb_exec.c` and `nv2a_pb_state.h`;
  - `src/d3d/nv2a_pb_d3d11.c` and `nv2a_pb_metal.m`;
  - the tests above.
- One commit per fix on `fix/kh-gpu-rules` off `posix-host/portability` 70c43712.
- BLiNX 2: no frame should move (the spike found no rect past the clip, no depth-off near crossing on the GPU paths, and no border mode). Goldens on Metal and Deck D3D11 confirm it.
- Burnout 3: the border fix changes the passes that sample past their texture's edge. A frame A/B, base against branch, on Metal and Deck D3D11, shows which surfaces move.
- Backends agree. The Metal border gap for colours that are not presets is recorded in TASKS.
- Upstream: this supports #211's near rule and #212's clear rule. Once both games pass, the border colour can be offered with the mirror work (#210).
