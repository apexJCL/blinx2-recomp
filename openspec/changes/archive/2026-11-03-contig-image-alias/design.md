## Where physical numbers come from

The toolkit has two storages that share physical numbers below 64 MB.

- **RAM.** The image and the heap are identity-mapped, so for them VA equals
  the physical number. `MmGetPhysicalAddress` on an image or heap address
  returns the address itself, and `xbox_PhysNoteRamName` records the page:
  - heap pages go in `g_phys_ram_named`, which a free clears;
  - image pages go in `g_phys_image_named`, which is never cleared.
- **The contiguous window.** It is 64 MB at guest `0x80000000`.
  `MmAllocateContiguousMemory[Ex]` hands out window pages through
  `xbox_ContiguousAllocEx`, a first-fit page arena. That arena keeps:
  - page 0 reserved;
  - a low reserve at 15-16 MB;
  - the GPU instance memory at the top.

  An exact-range request (`lowest..highest` equal to the size) pins its pages
  with `xbox_ContiguousClaim`. The physical number of window page `p` is
  `p * 4096`.

So, before this change, window page `0x1A7` and image address `0x1A7000` had
the same number. Each device decides alone which storage a number means:

| Device | Resolver | Order |
|---|---|---|
| APU structures | `mcpx_apu_phys` | >=64 MB RAM; named heap page -> RAM; live window page -> window; image -> RAM; below high-water -> window |
| APU sample data | `mcpx_apu_phys_data` | named image page -> image, else as above |
| OHCI data | `bus_resolve` | image first |
| OHCI descriptors | `bus_resolve_desc` | window first |
| NV2A | `dma_resolve` | below the arena's high-water -> window |

No single order is right for every title while numbers are shared. cde57b38
(BLiNX 2) needed the window before the image for APU structures. JSRF needed
the image for sample data. Darkwatch needed the image for OHCI data.

## Decision: keep blocks off the image, as the console does

On the console, a physical page has one owner, and the kernel's pool never
includes the pages the loader gave the image. Defaulting
`RECOMP_CONTIG_AVOID_IMAGE` on gives the arena that rule. Its first pass skips
image pages, so every block lands above the image, or below it when the image
starts high. The resolvers' orders then stop mattering for image numbers,
because a live window page and an image page never share one.

### Upstream note: the default flip is fork-only

4f3307f3 added the option off by default, so as not to move any game's
allocations without testing. This is a fork-side default flip with the same
switch. It deviates from upstream on purpose:

- The upstream README entry (`README.md`, "`RECOMP_CONTIG_AVOID_IMAGE=1` ...
  It's opt-in") is left as it is. It is upstream's changelog text and is
  true there; editing it in the fork would only drift from upstream.
- The fork's own record of the default is the recomp_env help text, the
  header comment and the `docs/env.md` row.
- The flip is argued in the upstream PR round, after BLiNX 1, BLiNX 2, JSRF
  and B3 have run on it, with the console argument and the JSRF case as the
  reason. Until then it stays fork-only.

### `=0` is the old order exactly

The switch gates both parts of the change: the first pass that skips the
image, and the refusal of named image pages in the fallback and top-down
paths. With `=0` neither applies, so the arena is the old first-fit bottom-up
order bit for bit, including blocks over pages the title named. The value is
off when it starts with `0`, `off`, `f` (`false`) or `n` (`no`); anything
else, including unset, is on. The first pass also jumps to the image's end
in one step instead of walking its pages, so a 50 MB image costs one
comparison per probe.

## Large images: the fallback

An image of about 50 MB (BLiNX 1, BLiNX 2) leaves about 14 MB above it. BLiNX
2's contiguous peak is about 25 MB, so the first pass fails, and a second pass
allows image pages. In that pass, and in the top-down path for huge requests,
`contig_page_free` refuses an image page that is already named. A page the
title names before any block takes it therefore stays single-owner even when
the arena runs short.

A page named after a block took it cannot be helped without moving a live
block, so it is the one remaining two-owner case:

- `xbox_PhysNoteRamName` reports it once per page, at most 8 lines per run.
- The rule reads sample data on it from the image. Sample data is
  what the title wrote through the VA it named.
- APU structures on it still read the window, which is cde57b38's order.

Evidence: BLiNX 1 with `RECOMP_XBE_PAGING=1` reports two such pages,
`0x0039A000` and `0x00423000`. Both are in its 9 MB `.data` section. The A/B
run with `RECOMP_CONTIG_AVOID_IMAGE=0` reports the same two pages, so the
collision predates this change, and the report only makes it visible. BLiNX
2's golden runs report none.

## Why the workaround stays

`xbox_PhysImageNameMap` and `mcpx_apu_phys_data` stay as a defence, for three
cases the arena cannot rule out:

1. A late-named page in a large image, as in BLiNX 1 above.
2. Exact-range claims. `xbox_ContiguousClaim` pins the pages a title demands,
   image or not, because the title asserts on the address.
3. `RECOMP_CONTIG_AVOID_IMAGE=0` A/B runs, which restore the old order.

In every other case the rule decides nothing, because a named image page never
has a live window page. It costs one table lookup per voice address.

## Limits (not in this change)

- **Heap aliasing.** Heap pages also share numbers with window pages. cde57b38
  handles them through the RAM-name map, which a free clears. One physical
  space for the heap and the arena, where each 4 KB number has one owner, is
  the complete fix. It touches the heap allocator and every device resolver,
  so it is a follow-up.
- **NV2A for large images.** With blocks above the image, BLiNX 2's high-water
  mark rises to about 64 MB. `dma_resolve` already takes the window for every
  number below it, so NV2A reads of heap numbers there resolve to the window,
  as they did for numbers below the old mark. The golden shows no change. The
  one-physical-space follow-up covers this as well.
- **Fallback order inside the image.** The fallback fills the image from the
  bottom: `.text` first, then `.rdata` and `.data`. Taking read-only sections
  first would keep blocks off `.data`, where titles name their DirectSound
  and USB buffers, and would remove BLiNX 1's late-named pages. That moves
  BLiNX 2's blocks again, and needs the section flags in the arena, so it is
  a follow-up with its own golden.

## Verification

- A ctest, `tests/contig_image_alias`, run on `tools/conformance/test.xbe`:
  - **named.** A named image page stays free through a fill of the whole
    arena. No block takes an image page while a run of its size is free
    elsewhere. The APU resolves the named page to the image for structures
    and for sample data.
  - **unnamed.** Unnamed image pages are the last resort, and they are used.
  - **unnamed** also checks that a request constrained to the image page
    gets it, and **named** that the same request is refused.
  - **late.** A page named after a block took it stays the block's.
    Structures read the window, and sample data reads the image. Once the
    block is freed, a request constrained to that page is refused.
  - **fill-named.** With `=0`, the first 1 MB block fills from the bottom
    over a named image page, the old order.
  - Not covered: the top-down path below a named page. It serves only
    requests over about 48 MB, and the test image is one page at `0x11000`.
- `memory_regressions contig-fill-image` keeps the old order covered with
  `=0`.
- JSRF: 1x -> 2x -> 3x -> 1x render-scale run on Metal.
  - No logged block overlaps the image. This is the deciding evidence: with
    no window block on the silence buffer's number, there is nothing for
    Metal's write-back to corrupt, whatever the resolver order.
  - The WAV is clean: no clipping, and no 80 dB tone.
  - Voices 64-67 read `0x001A77B0` from the image, at rms 0.
- Goldens and boots:
  - Goldens (Metal): BLiNX 2 and JSRF.
  - B3: race gate.
  - BLiNX 1: boots to attract with paging.
