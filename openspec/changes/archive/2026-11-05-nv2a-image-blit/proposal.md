# nv2a-image-blit: the 2D engine's image blits, copied on the GPU

## Why

Quantum Redshift draws its lens raindrops as opaque black discs on Metal
and D3D11. Each frame the game copies its 640x480 back buffer
with the NV2A 2D engine (NV062 CONTEXT_SURFACES_2D on subchannel 3,
NV09F IMAGE_BLIT on subchannel 2), then draws the drops as 2D quads that
sample the copy at 0x00A1C000. The executor dropped every method off
subchannel 0 as unhandled, so the copy never happened. The drops sampled
a surface nothing had written: black.

XDK D3D's CopyRects and its frame-copy paths use the same engine, so
other titles hit this gap too.

## What Changes

- **Executor (toolkit, `nv2a_pb_exec.c`, new `nv2a_2d.{h,c}`)**: decode
  `SET_OBJECT` on every subchannel (class from the instance through
  RAMHT), plus the NV062 surface, NV09F blit and NV012 beta methods,
  following xemu's pgraph. A blit is placed through the context DMA
  objects, checked against their limits and guest memory, and handed to a
  new backend hook `on_blit`. With no hook (CPU, null), the executor
  copies guest memory.
- **Metal and D3D11**: a SRCCOPY blit from a live render target becomes
  a texture copy into a "twin" target at the destination, with the
  source's geometry, Hor+ pads and render scale. A later draw samples the
  twin as it samples any target. Every other blit runs in guest memory,
  from the source written back, with the overlapping targets written back
  and retired and the texture cache told (D3D11 gains a synchronous
  write-back for this path only).
- **Executor**: a subchannel bound to an object whose class can't be read
  is class 0 (nothing), not the XDK layout's class; RAMHT lookups keep the
  last hit per handle.
- **Hor+ (separate commit)**: a centred 2D batch that samples a frame
  copy made in this flip, and whose texture coordinates track its own
  screen position, is stretched, so the drops cover the 16:9 wings and
  refract what lies under them.
- **ctest `pb_image_blit`**: decode, host box, the copy, the executor
  path through RAMHT and context DMA objects, the class fallback, the
  RAMHT cache and the placement rule.
- **Backend smokes** (`nv2a_backend_smoke` on Metal, `d3d11_backend_smoke`
  on Windows): twin made and refilled, eviction, retiring, `copy` expiry,
  the fallback write-back, render.scale 2 with pads.

## Capabilities

- `pushbuffer-executor`: ADDED "The 2D engine's image blits are executed".
- `gpu-backend`: ADDED "A blit from a render target is copied on the GPU".
- `enhancements`: MODIFIED "Hor+ batch placement" and "HUD keeps its 4:3
  layout".

## Impact

- Toolkit only: `src/kernel/nv2a_2d.{h,c}`, `nv2a_pb_exec.c`,
  `nv2a_pb_state.h` (`struct nv2a_pb_blit`, `on_blit`),
  `nv2a_backend_common.h`, `src/d3d/nv2a_pb_metal.m`,
  `src/d3d/nv2a_pb_d3d11.c`, `tests/pb_image_blit/`.
- A title that never uses the 2D engine sees no change. BLiNX 2 does use
  it: it copies its 640x480 frame to the AvSetDisplayMode framebuffer
  (0x000E7040) at a few flips (764, 890, 892, 3959, 3971 in its golden
  scenarios). Those copies become twins, and its goldens must stay as
  they are.
- No new env keys. The rule is stock behaviour (it fixes a missing
  feature); only the Hor+ stretch is an enhancement and follows
  `display.aspect`.
