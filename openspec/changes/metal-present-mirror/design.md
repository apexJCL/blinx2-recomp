## Context

Toolkit 4773a01 and 4bfee1c (D3D11); Fable runtime review 2026-10-06,
section 5 (notes/fable-reviews/2026-10-06-runtime.md). The D3D11 code is the
reference: `surface()`'s second loop, `rt_grow`, `clear_box`/`clear_region`,
`present_extent`, `nv2a_pb_d3d11_shown`, and `clip_cases` in
tests/d3d11_backend_smoke/smoke.c. Parked Metal WIP: toolkit 051b3c4 on
fix/metal-present-mirror (`nv2a_clear_box`, `rt_texture_new`, `rt_seed`,
`rt_grow`, the second `surface()` loop, the clear shaders); it predates this
pass and misses D1's `rt->dt` reset and the unseeded-margin clear.

Where Metal differs from D3D11 and it matters here:

- Metal targets are seeded from guest memory and written back to it (lazily,
  `rt_sync`); D3D11 does neither. A grow must keep both true.
- Metal caches the depth attachment on the target (`rt->dt`, attached by
  `begin_pass` to every pass on it); D3D11 looks its DSV up per draw. Metal
  requires every attachment of a pass to have one size.
- Metal has no `ClearView`: a load action clears a whole attachment, and a
  pass has no render area. A sub-rectangle clear is a draw.
- The window takes the frame as a GPU blit into a slot the presenter makes
  at the size asked (`xbox_FramebufferWindowBackTexture(w, h)`, fbm_slot),
  or as a pixel push (`xbox_FramebufferWindowPresentPixels`) in readback
  mode. Neither knows the target; both show what they are given.

## Decisions

### D1. Metal grows a target the way D3D11 does, but seeds the margin

Same lookup as D3D11, in `surface()` after the exact (offset, w, h) match:
a target at the same offset and pitch, dropped if stale ("reuse"), reused if
it covers the clip, grown to the larger of each dimension otherwise. Another
pitch at the same offset stays a new allocation that the overlap rule
retires. `w`, `h` stay the clip extent (`clip_x + clip_w`, `clip_y +
clip_h`); the draw path keeps mapping guest pixels to NDC through `rt->w/h`
with the viewport at `rt->hw x rt->hh`, so a larger target keeps every
position, as on D3D11.

`rt_grow(rt, w, h)`, in this order:

1. `nv2a_host_size` for the new size; `keep` is whether the host factor is
   unchanged (`rt->hw == rt->w * n`). When it is not (a surface past
   METAL_MAX_DIM, 16384, takes a smaller factor), `rt_sync(rt, rt->pitch)`
   writes the old target back first: a blit cannot rescale, so the whole new
   texture is seeded from guest memory instead. `rt_sync` waits for the GPU
   and restores the ring positions itself; `surface()` runs before
   `ring_alloc` in `metal_on_draw`, so no vertex data is in flight.
2. End the open encoder when it is on this target (`s_enc_rt == rt`): a
   render command encoder must not outlive its attachment's swap, and the
   blit below needs no encoder open. The old texture stays alive until the
   command buffer that holds those draws and the blit retires it (Metal
   retains an encoded resource); the backend releases its own reference only
   after the blit is encoded, never while an encoder on it is open.
3. The new texture (`rt_texture_new`: BGRA8, RenderTarget | ShaderRead,
   Shared on unified memory, Managed otherwise). `rt_seed` fills it from the
   guest bytes at `rt->addr` as a new target is seeded (32-bit surfaces only,
   nearest-upscaled at scale > 1). A new MTLTexture's contents are
   undefined, so when the seed does not apply (a 16-bit surface, or
   `pitch < w * 4`) an empty pass with loadAction Clear to black and
   storeAction Store runs on the new texture first: the margin is then
   black, as D3D11's is, instead of garbage.
4. With `keep`: a blit of the old texture (`rt->hw x rt->hh`) to the new
   one's top left, in the frame's command buffer. `replaceRegion` runs now on
   the CPU and the blit later on the GPU, so the blit wins where they
   overlap: the drawn pixels, not the seed, survive.
5. Swap the texture; `w`, `h`, `hw`, `hh` take the new size; `dirty` and
   `presented` carry over; `last_use` is set by the caller. `rt->dt = NULL`:
   the cached depth buffer is the old size, and `begin_pass` would attach
   it to a larger colour attachment (a clear or a depth-less draw right after
   the grow would do that; a depth draw re-keys through
   `depth_target(rt->w, rt->h)` and would not). The next depth draw attaches
   a fresh buffer at the grown size, cleared as every fresh one is; D3D11
   does the same through its per-size lookup.
6. `rt_own_reset(rt)`: the ownership hash at the new height, over the bytes
   the seed read.
7. One log line per grow, the first 20 (`surface 0x%08X: WxH render target
   grown to WxH`), and `s_grows++` for the present summary.

The self-copy texture (`s_self`, `rt_texture`) is keyed by the source's host
size and is rebuilt on the next bind, so it needs nothing. The depth buffer
stays keyed by zeta and size (DT_MAX), as on D3D11.

### D2. One clear box for three paths

`nv2a_clear_box(g, w, h, box)` (static inline, nv2a_backend_common.h): the
clip `[clip_x, clip_x + clip_w) x [clip_y, clip_y + clip_h)`, intersected with
SET_CLEAR_RECT (`(max << 16) | min`, both inclusive, as xemu reads it) once
`clear_rect_set`, clamped to `w x h`. Returns 0 when empty. This is D3D11's
`clear_box` body unchanged (WIP 051b3c4 has it), so D3D11 behaviour does not
move. The CPU path passes the clip extent as `w x h` (guest memory has no
target size), so the clamp is a no-op there.

### D3. Metal partial clears are a draw, not a load action

`metal_on_clear`: `nv2a_clear_box(g, rt->w, rt->h, box)`. An empty box
encodes nothing (D3D11 does the same). A box that is the whole target
(`0, 0, rt->w, rt->h`) keeps `begin_encoder(rt, 1, c)`: a new pass with
loadAction Clear, the stock path, so a title that clears whole clips sees no
new work. Otherwise:

- The pass: the open one when `s_enc_rt == rt`, else `begin_pass(rt, 0,
  ...)` (loadAction Load, `rt->dt` attached when set). `begin_pass` already
  marks the target dirty and drawn for the ownership check; a clear into the
  open pass needs nothing more.
- The draw: a full-screen triangle from `vertex_id` (`vs_clear`), a fragment
  returning the clear colour (`fs_clear`, byte/255 so BGRA8Unorm stores the
  same bytes the CPU path writes and a load-action clear would), no blending,
  all channels written, cull off, the viewport at `rt->hw x rt->hh`, and the
  scissor at the box in host pixels (`x * hw / w`, as D3D11's ClearView
  rect; Metal rejects a scissor outside the attachment, and the box is
  clamped to the target so it cannot be). Depth and stencil untouched:
  `depth_state(0, 0)` on a pass with a depth attachment.
- Two cached pipelines, with and without the Depth32Float_Stencil8
  attachment, made on first use (`s_clear_pso[2]`); a failure logs once and
  falls back to a whole-target load-action clear, as D3D11 does without a
  11.1 context.
- Visibility: while a query counts on the pass (`s_occ_slot >= 0`), counting
  is switched off before the clear draw and back on at the same slot after
  it; a clear is not a zpass sample. Not testable by the smoke (it drives no
  occlusion queries); reasoned here.
- The scissor is reset to the whole target after the draw: encoder state
  persists for the pass and draws never set one.
- `s_clears++` as today, `s_partial_clears++` for the summary.

Alternatives: a load-action clear with a sub-rectangle does not exist on
Metal; `fillBuffer` is buffers only; a compute kernel is more code than a
scissored triangle and would need its own synchronisation with the pass.

### D4. The present shows the frame's extent

`present_extent(rt, &cw, &ch)`: `rt->w x rt->h`, cut to the walker's `p->w x
p->h` when `p->offset == rt->offset`. Host extent `hcw = cw * hw / w`, `hch`
likewise. `present_target` accepts `rt->w >= p->w && rt->h >= p->h`, as
D3D11 does; `metal_sync_guest`'s exact-size lookup becomes the same covering
test (its most-recent-at-address fallback would find the grown target
anyway, but the rule should be the same one).

- Layer mode: `xbox_FramebufferWindowBackTexture(hcw, hch)` (the presenter
  makes the slot at the size asked and fits it to the window), and the blit
  copies `hcw x hch` from the target's origin.
- Readback mode, scaled: `xbox_FramebufferWindowPresentPixels(hpx, hcw, hch,
  rt->hw * 4, 4)`: the host readback stays the whole target (the write-back
  reads it too), the push names the region with the target's row pitch.
  Unscaled: `getBytes` of `(0, 0, cw, ch)`.
- The write-back, `guard_flip`, `host_readback` and the ownership hash keep
  the whole target: the guest surface is that large and the title may read
  any of it.
- `s_shown_w/h` record the last flip's extent for `nv2a_pb_metal_shown`.

### D5. CPU path

Crop: nothing to do (`present_copy` already reads `p->w x p->h`). Grow: n/a.
Clear: `clear_surface` loops over the clear box instead of the clip (WIP
051b3c4 has it, swizzled and linear, 16- and 32-bit). The CPU path needs this
on its own account (backends agree; D3D11 goldens already run with the
bound) and for the smoke, which compares the CPU frame to Metal's exactly.

### D6. The walker is the reference for what a flip shows; it does not change

`present_pick` keeps keying its surfaces by (offset, w, h): after a grow,
`p->w x p->h` is the largest fresh clip at the display address, not the
target size, and that is what D4 crops to. "Fresh" is `flips - last_flip <=
PRESENT_STALE_FLIPS` (120), and `s_gpu.flips` advances only at
FLIP_INCREMENT_WRITE (0x012C), as the XDK's swap pushes it, never at
FLIP_STALL alone. So when a title shrinks its clip, the present keeps the
larger extent until the larger entries age out (121 or more
FLIP_INCREMENT_WRITEs), on Metal exactly as on D3D11. The Metal smoke's
scenes send FLIP_STALL only, so its crop case must send 0x012C before each
0x0130 or `flips` never advances and nothing ages out.

### D7. Tests: nv2a_backend_smoke, the D3D11 clip cases and a grow

`clip_cases` in tests/nv2a_backend_smoke/smoke.c, run after the scenes and
before `writeback_cases` (the present state and BUF0 are then as the scenes
left them). Every case is one method stream sent twice, CPU path then Metal,
and the whole 640x480 frame compared exactly (`compare`), the CPU frame from
guest memory and Metal's from `nv2a_pb_metal_host_pixels` (scale 1: the
target as it is; no flip, so nothing is written back). Probes name the
pixels the D3D11 smoke checks.

1. Clip clear (D3D11 case 1): BUF0 at 640x480 cleared red; clip 160x120 at
   (100, 100) cleared blue. (50, 50) red, (150, 150) blue. On Metal the
   target stays one 640x480 (`nv2a_pb_metal_shown`: 640x480).
2. Clear rect (D3D11 case 2): clip 640x480, rect (300, 300)-(339, 339),
   cleared green; then the rect back to (0, 639)/(0, 479). (320, 320) green,
   (350, 350) red.
3. Grow: a fresh surface BUF3 (0x01600000: clear of BUF0-2, RTT0/RTT1 at
   0x01400000/0x01500000 and the zeta at 0x02400000, so the overlap rule
   never touches it), its guest bytes filled with the 0xFFFF00FF pattern
   before each path's run (after the CPU frame is saved: Metal's seed must
   read the pattern, not the CPU result, or a broken blit or clear draw
   would still match). Clip 320x240 cleared red (a 320x240 target); then
   clip 640x480 with rect (320, 240)-(639, 479) cleared green: the target is
   grown to 640x480. (100, 100) red (kept by the blit; the seed alone would
   leave the pattern), (400, 300) green (the partial clear draw), (400, 100)
   and (100, 300) the pattern (the margin seeded from guest bytes). The
   exact compare covers the seed, the blit and the clear at once.
   `nv2a_pb_metal_shown`: target 640x480.
4. Grow at render.scale 2 (`nv2a_host_opts_set`, as `writeback_cases` does,
   on a fresh BUF4 0x01740000, filled the same way): case 3's stream; the host pixels box-filtered
   (`nv2a_downscale_box32`) and compared exactly (solid colours survive the
   filter). This covers the scaled scissor and the same-factor blit. The
   other-factor path (`!keep`) needs a surface past METAL_MAX_DIM and is not
   covered; it reuses `rt_sync` and the whole-texture seed, both tested
   elsewhere.
5. Crop (D3D11's crop case): clip 320x240 on BUF0; 122 iterations of a black
   clear, FLIP_INCREMENT_WRITE (0x012C) and FLIP_STALL (0x0130). Then
   `nv2a_pb_metal_shown(BUF0)`: target 640x480, shown 320x240; and
   `nv2a_pb_present_state()` reports 320x240 for the CPU path, the
   cross-check that the walker aged the larger entries out. Clip back to
   640x480 afterwards.

`nv2a_pb_metal_shown(offset, &tw, &th, &sw, &sh)`: the target size at a
colour offset and the last flip's present extent, 0 when none, the shape of
`nv2a_pb_d3d11_shown`. The `guard` and `noalias` runs do not change.

## Risks

- A title that sets a clear rect smaller than its clip and expects the whole
  clip cleared would now differ on CPU and Metal; D3D11 has done this since
  4bfee1c and its goldens hold, and xemu bounds clears the same way.
- The partial-clear draw is new work on passes that used to be a load
  action; only partial clears take it, and the summary counter shows how
  many a golden run made. A BLiNX 2 run with non-zero grows or partial clears
  gets a pace check (tasks 2.5) before the merge.
- A grow mid-frame ends the open pass; that is one more encoder per grow,
  and grows happen once per surface per size step.
- `rt_sync` in the `!keep` path waits for the GPU inside `surface()`; it is
  the path a title takes only past METAL_MAX_DIM at the chosen scale.
