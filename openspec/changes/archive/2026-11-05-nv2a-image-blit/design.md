# Design: nv2a-image-blit

## D1. Decode in a standalone unit

`nv2a_2d.{h,c}` holds the state the title set (per subchannel: handle and
class; NV062: DMA objects, format, pitches, offsets; NV09F: operation,
points, size; NV012: beta) and the arithmetic (bytes per pixel, extent,
the guest copy, the host box). It has no executor state, so the ctest
checks it alone. Semantics follow xemu's pgraph.c and blit.c:

- pitch 0x304: source in bits 15:0, destination in 31:16;
- offsets: 27 bits;
- `NV09F_SIZE` with a non-empty rectangle runs the blit;
- the operation defaults to SRCCOPY. D3D sets it once at device init, and
  a pushbuffer picked up later never shows it.

With no `SET_OBJECT` seen on a subchannel, the class falls back to XDK
D3D's fixed layout (0 Kelvin, 2 IMAGE_BLIT, 3 SURFACES_2D). A subchannel
the title did bind, to a handle whose class can't be read (not in RAMHT,
or an instance outside guest memory), is class 0: its methods go
unhandled. The layout's class would run a blit off an object the title
never made one (`bound[]` keeps which subchannels saw a bind).

## D2. The executor owns binds, DMA objects and refusal

`twod_method` looks `SET_OBJECT` handles up through RAMHT
(`ctxdma_lookup`; class = first word & 0xFF) and binds 0x184/0x188 with
`ctxdma_bind`. `twod_blit`:

1. places each surface with `ctxdma_place` (base + offset);
2. refuses a blit past a limit, outside guest memory or over a write the
   executor refuses elsewhere (`surface_write_refused`);
3. refuses an operation other than SRCCOPY and BLEND_AND;
4. then calls `on_blit`, or `nv2a_pb_blit_guest` (copy plus
   `surf_mark_range`) when the backend has none.

Each refusal logs once. The first binds and blits log, so a title's 2D use
shows in its run log.

RAMHT lookups keep their last hit per handle (16 slots, keyed by handle
and `PFIFO_RAMHT`). A kept slot is used only while its entry still names
the handle; the instance words are read again each time, so a title that
rewrites an object is seen. A miss is never kept: the title may add the
entry later. `nv2a_pb_ramht_stats` counts scans and hits for the ctest.

## D3. A twin target, not a guest round trip

D3D11 never writes targets back to guest memory, and Metal does so only
lazily. A guest copy from a target would read stale bytes: black on
D3D11, a frame late on Metal. Both backends therefore copy texture to
texture:

- The source must be a live target whose pixel size matches the blit,
  not overlapping the destination, and SRCCOPY. The destination pitch
  need only hold the source's width (`dst_pitch >= w * bpp`): the twin
  takes the blit's destination pitch, so a copy into a wider buffer stays
  on the GPU too.
- The destination becomes a target with the source's w, h, pads, host
  size, scale and format and the destination pitch, marked `copy` with
  the flip that filled it (`copy_flip`). A twin already there with the
  same geometry is refilled. Other targets over the destination are
  written back and retired so nothing stale shadows it.
- `nv2a_2d_host_box` maps the rectangle to host texels. A whole-width blit
  from x 0 to x 0 copies the full padded width, so a Hor+ frame keeps its
  wings; a narrower one copies its guest columns at the render scale.
- The draw that samples 0x00A1C000 finds the twin through `rt_texture`,
  since a linear 0x11 texture at the target's pitch already reads a
  target (`nv2a_rt_tex_reads`).

Fallback: anything else (guest source, partial blit with no twin,
BLEND_AND) runs in guest memory. Both backends write the source target
back first and write back and retire the targets over the destination,
then the texture cache rehashes the destination (Metal `tex_cache_stale`,
D3D11 `blit_tex_stale`). The present summary counts both paths. On D3D11
the write-back is bounded by what the target holds (below).

| | twin copy | guest fallback |
|---|---|---|
| Metal | `copyFromTexture` in the frame's command buffer; no stall | `rt_sync` of the source and of each target over the destination: the lazy write-back it already does on eviction, one command-buffer wait each |
| D3D11 | `CopySubresourceRegion`; no stall | `blit_write_back`: a staging texture, `CopySubresourceRegion`, `Map` (a GPU sync), rows box-filtered at scale > 1 and packed to the target's format; the source's rectangle, and each full target over the destination, on this path only |

D3D11 had no write-back at all, so its fallback handed the guest copy
whatever the bytes were before the source was drawn (black), and a
partial blit over a target dropped the rest of the target. The staging
readback costs a sync; QR and BLiNX 2 never take this path (`0 in guest
memory`), so it is paid only by blits the GPU copy can't do.

**What D3D11 may write back.** Metal seeds a new 32-bit target from guest
memory (`rt_seed`), so its whole image is the guest's bytes plus what was
drawn. D3D11 never seeds: `surface()` makes a target black and `rt_grow`
fills the new area black. A whole-target write-back would put that black
over every guest byte the target never drew, which loses an atlas a
title drew into a corner of. So on D3D11:
- the fallback's source writes back only the blit's source rectangle
  (the bytes the copy reads), or, when the blit reads it at another
  pitch, the whole target only if it is `full`, else the guest copy reads
  guest memory as before this change;
- a target over the destination (overlap or eviction) writes back only if
  it is `full`; otherwise it is dropped with no write-back, as before
  this change, and logged as drawn in part.

`full` is set by a clear that covers the whole target (and the no-ClearView
path, which clears it all), reset when the target is made or grown, and
inherited by a twin from its source on a whole copy. Draws do not set it:
a draw's coverage is unknown without a vertex scan on every draw. Seeding
D3D11 targets as Metal does would also close the gap, but it changes
stock D3D11 behaviour on every new target (a staging upload each) and
was left out of a blit fix.

**Packing.** `nv2a_surf_pack_row` (backend common) packs a BGRA8 host row
to the surface format with its constant bits, as xemu's clear does:
X1R5G5B5_O1R5G5B5 writes X 1, Z1R5G5B5 X 0; X8R8G8B8 Z/O alpha 0/0xFF;
X1A7R8G8B8 Z/O the top 7 alpha bits under X 0/1; A8R8G8B8 and A8B8G8R8
as is. D3D11's `blit_write_back` uses it; Metal's `write_back` and
`write_back_scaled` use it for 16-bit formats (they packed every 16-bit
format as R5G6B5) and set the constant alpha bits of the 32-bit X formats
in place.

**Retire and `rt_alias_check`.** D3D11's surface overlap rule is gated
by `render.rt_alias_check` because it drops a target with nothing written
back. The blit's retire writes a full target back first (unless the title
rewrote the target, when its bytes win) and drops one drawn in part as
the overlap rule would, so it is not gated: a target left over the
destination would shadow what the blit wrote. Metal does the same,
writing back every target.

**Slots.** Each destination's twin takes one of the `RT_MAX` (16) target
slots on either backend while it lives. With every slot taken, the twin
evicts the least recently used target other than the source, written
back first. QR keeps one twin (0x00A1C000), BLiNX 2 one (0x000E7040).

**Write-back of a twin.** A twin is `dirty` (Metal) from birth: its image
exists only on the GPU, and an eviction or a present writes it back. That
is safe because every write-back of a twin goes through
`rt_drop_if_stale` first (eviction, overlap, `sync_guest` on present,
decode sync, a scale change, the blit paths). The ownership hash is reset
when the blit fills the twin, so a CPU write the title makes over it
afterwards drops the twin and the title's bytes win. A twin left alone
writes back exactly what the hardware blit wrote there. This is
BLiNX 2's case: its twin is the AvSetDisplayMode framebuffer, presented
and written back as the hardware would have it. The twin is not marked
drawn, so the stale check is not skipped in the blit's own flip. One gap
remains, as for every target: a check earlier in the same flip caches
its answer, so a CPU write later in that flip is seen at the next flip's
check, not at once.

## D4. Hor+ stretch for frame copies (separate commit)

At 16:9 the drop quads are narrow 2D batches, so the Hor+ rule centres
them and they cover only the 4:3 middle, each refracting the copy's
centre. They are a lens effect, not HUD. `nv2a_aspect_place_copy` turns
CENTRE into STRETCH when a 2D batch samples a frame copy where it lies.
The drops then spread over the wings and each samples the wide frame
where it lies; they are about 1.33x wider, which reads as a lens and not
a defect. The HUD keeps its 4:3 layout. Both backends call the same
inline.

A frame copy, for this rule (`aspect_copy_tracks` on each backend):
- a padded target a blit filled in this flip (`copy_flip`) and nothing
  has drawn into since. A copy from an earlier flip is a still frame
  (BLiNX 2's display-buffer copies, a pause screen), which a centred
  batch may show as a picture;
- sampled by a centred 2D batch whose texture coordinates track its own
  screen position (`nv2a_aspect_uv_tracks`): up to 32 of the batch's
  vertices, spread over it, run through the vertex program (or read as
  pass-through), and `uv * size - xy` must stay within an eighth of the
  frame plus 2 pixels in spread and a sixteenth of it in mean offset on
  each axis. The size is the texture's for a swizzled texture
  (normalised coordinates) and 1 for a linear one (texel coordinates).
  QR's drops (vs C8AF571F) sample (360.70, 464.03) at (361.2, 464.6):
  they track. A sprite or HUD element that maps a whole small texture
  over a few pixels does not, so it stays centred even if it samples a
  copy.

## Known limits

- Metal's 16-bit targets are not seeded either (`rt_seed` seeds 32-bit
  only), so its evict and overlap write-back of a 16-bit target drawn in
  part writes black over guest bytes it never drew. That predates this
  change (eviction did it already); follow-up in TASKS.
- `nv2a_aspect_uv_tracks` samples up to 32 vertices, so its spread
  tolerance is met more easily by a large batch whose outliers miss the
  sample. QR's drops are small batches; a larger mis-tracking batch could
  still be stretched.
- The RAMHT handle cache re-reads its slot on every hit, but a title
  that rehashes a handle into another slot and leaves the old entry valid
  is still served the old entry's object. No title seen moves a bound 2D
  object.

## Not done

- NV039 M2MF (QR binds it on subchannel 1 but sends no methods) and the
  other 2D classes (NV04 GDI, NV19 clip, NV044 pattern, NV043 ROP) stay
  unhandled and counted.
- The CPU backend gets the guest copy only; its sampled targets are guest
  memory already.
