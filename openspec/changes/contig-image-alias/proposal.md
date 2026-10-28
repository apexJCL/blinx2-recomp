## Why

The tracker item found that JSRF's audio turns into a tone after a live render-scale
change. JSRF names DirectSound's silence buffer (`0x001A77B0`, inside its XBE
image) through `MmGetPhysicalAddress`. The contiguous allocator had also given
the window page with the same number (`0x801A7000`) to the title's second
framebuffer. Here the contiguous window (guest `0x80000000`) and the RAM the
image sits in are separate storage, so the number `0x001A7000` had two owners.
The APU resolved it to the window, and Metal's write-back after the scale
change put pixels into what the APU played as silence.

The tracker item fixed the symptom in the APU: sample data on a named image page reads
the image (`mcpx_apu_phys_data`, `xbox_PhysImageNameMap`). The cause is still
there. The arena fills from the bottom, through the image's physical range, so
every device model that holds only a physical number has to guess:

- APU: `mcpx_apu_phys` checks the page map before the image.
- OHCI: `bus_resolve` checks the image first for data buffers, and
  `bus_resolve_desc` checks the window first for descriptors.
- NV2A: `dma_resolve` takes the window for anything below the high-water mark.

On the console, the kernel never hands out a page the image uses, because a
physical page has one owner. Upstream already has the console order as an
opt-in (`RECOMP_CONTIG_AVOID_IMAGE`, 4f3307f3, for Darkwatch's OHCI case), but
it defaults off.

## What changes

- Toolkit (`fix/contig-image-alias` off `posix-host/portability`):
  - `RECOMP_CONTIG_AVOID_IMAGE` defaults on. Contiguous blocks stay out of the
    image's pages while the window has other room. `=0` (or `off`, `false`,
    `no`) restores the old order exactly, for A/B runs. This deviates from
    upstream's default; see the design.
  - Some images leave no other room: BLiNX 1 and BLiNX 2 are about 50 MB, in
    64 MB of physical numbers. Their fallback pass and the top-down path still
    use image pages, but never a page the title has named. With `=0` that
    refusal is off too, so named pages are taken as before.
  - A page named after a block took it gets a one-time report per page:
    `[CONTIG] image page 0x... named while a window block holds its number`,
    at most 8 lines per run. This case is the one left with two owners.
  - The rule stays as a defence for the late-named case and for
    exact-range claims (`xbox_ContiguousClaim`).
  - Tests:
    - a new `tests/contig_image_alias` ctest, with named, unnamed, late and
      fill-named (`=0`) modes;
    - a new `memory_regressions` mode, `contig-fill-image`, which keeps the
      old order covered.
- cat (`spec/contig-image-alias`): this spec, and the `docs/env.md` row for
  the new default.

## Impact

- JSRF, Burnout 3 and Darkwatch-sized images: no window page shares a number
  with an image page. All three device models see one owner per number.
- BLiNX 1 and BLiNX 2: the blocks that used to fill the bottom of the window
  now sit above the image first. They fall back into it only when that room
  runs out.
- The Metal goldens for BLiNX 2 and JSRF and the B3 race gate are unchanged.
- The physical numbers that titles see change for the blocks that moved.
  Game glue names window addresses only in comments, so no glue depends on
  the old numbers.
