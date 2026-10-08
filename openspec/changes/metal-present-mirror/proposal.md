## Why

The D3D11 backend got three present fixes for Burnout 3 (toolkit 4773a01 and
4bfee1c): one render target per surface, grown in place across clip sizes; a
present cropped to the frame; colour clears bounded by the clip and
SET_CLEAR_RECT. The CLAUDE.md rule "backends agree" asks for the same on Metal
and the CPU path, and TASKS.md records the gap ("Metal and CPU mirror of the
D3D11 present fixes"; Fable runtime review 2026-10-06, section 5).

Where each path stands at toolkit a10f6d8:

| fix | D3D11 | Metal | CPU |
|---|---|---|---|
| one target per surface, grown | yes | no: keyed by (offset, w, h) (`surface()`), so the overlap rule writes back and retires a target at every clip change, and `present_target` wants the exact size | n/a: draws into guest memory, one surface by construction |
| present cropped to the frame | yes | n/a until targets grow; then no (layer blit and readback send `hw x hh`) | yes already: `present_copy` (fb_present_sdl.c) presents the walker's `p->w x p->h` from guest memory |
| colour clear bounded by clip | yes | no: loadAction Clear wipes the whole target | yes: `clear_surface` fills the clip |
| colour clear bounded by SET_CLEAR_RECT | yes | no | no |

On Metal the per-clip targets do not lose pixels the way D3D11 did (Metal
writes back before retiring), but each clip change costs a GPU wait, a
read-back and a re-seed, a scaled target loses its resolution through the box
filter at every change, and a flip whose frame size has no exact target
presents the guest bytes, which miss the draws of the last (dirty) target.
Burnout 3 does not boot on the Mac yet, so the smoke test is the evidence.

Written by Opus; Fable spec pass 2026-10-07 (this revision). Implementation
continues from this commit.

## What Changes

- **Metal: one render target per surface.** `surface()` reuses a target at the
  same offset and pitch when it covers the clip, and grows it in place
  otherwise (`rt_grow`): a new texture at the larger size, seeded from the
  guest bytes as a new target is, with the old contents blitted to its top
  left. A grow drops the target's cached depth attachment (`rt->dt`), ends
  any encoder on the old texture first, and rebuilds the self-copy texture.
  `present_target` and `metal_sync_guest` accept a target at least the
  frame's size.
- **Metal: the present shows the frame.** The layer blit, the readback window
  push and the smoke accessor use the walker's present extent, scaled to host
  pixels, not the whole target. The write-back and the fb guard still cover
  the whole target.
- **Shared clear box.** D3D11's `clear_box` moves to `nv2a_backend_common.h`
  as `nv2a_clear_box`: the surface clip, bounded by SET_CLEAR_RECT once the
  title has sent one, clamped to the target. D3D11, Metal and the CPU path
  all call it.
- **Metal: bounded colour clears.** A clear covering the whole target keeps
  the loadAction Clear (the stock path, unchanged); a partial one draws a
  solid full-screen triangle under a scissor in a loading pass, with
  visibility counting off for that draw.
- **CPU: SET_CLEAR_RECT.** `clear_surface` fills the clear box instead of the
  whole clip (the same box D3D11 has used since 4bfee1c).
- **Counters.** The Metal present summary line reports grows and partial
  clears, so a golden log shows whether BLiNX 2 takes either path at all.
- **Tests.** `nv2a_backend_smoke` gets the D3D11 smoke's clip cases (clip
  clear, clear-rect clear, crop after the 640x480 entries age out) plus a
  grow case at render.scale 1 and 2, each run on the CPU path and on Metal
  and compared exactly, and a `nv2a_pb_metal_shown` accessor for the crop.

Out of scope, recorded in TASKS: depth/stencil clears bounded by the clear
rect (still whole-target on D3D11 and Metal); a grown target sampled through
normalised (swizzled) coordinates (both backends map 0..1 over the grown
size); a 16-bit surface's grown margin (`rt_seed` seeds 32-bit surfaces
only, so the margin is cleared black, as D3D11's is); D3D11's missing
write-back path (Fable 2026-10-06, section 2).

## Impact

- Toolkit: `src/d3d/nv2a_pb_metal.m`, `src/d3d/nv2a_pb_d3d11.c` (the box moves
  out, no behaviour change), `src/kernel/nv2a_backend_common.h`,
  `src/kernel/nv2a_pb_exec.c`, `src/kernel/nv2a_pb_state.h` (comment),
  `tests/nv2a_backend_smoke/smoke.c`. The walker (`present_pick`,
  `present_note`, the flip counters) does not change.
- Behaviour: stock behaviour changes only where it was wrong (a clear outside
  its clip or clear rect, a flip of a grown target). No env key, no opt-in.
  A BLiNX 2 frame that clears whole clips and draws each surface at one clip
  size takes none of the new paths: the exact-size lookup still hits first,
  and a whole-target box keeps the load action.
- Goldens: Metal (attract, stage1, story) and D3D11 must keep their verdicts
  and paces at stock.
- Perf: Metal speed is what matters. Nothing new runs per draw; a partial
  clear is one scissored triangle per clear that used to be a load action,
  and a grow is one blit per surface per size step. The counters above make
  either visible; the bench flag is a 25% drop in flips/s.
