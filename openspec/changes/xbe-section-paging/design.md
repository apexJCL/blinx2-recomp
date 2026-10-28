## Context

The guest map is flat: VA equals the offset in one host mapping of
`g_xbox_map_size` (or RAM) bytes. The toolkit region (KDATA, TLS, the stack)
sits above `g_xbox_image_hi`, and the heap runs from the stack's end to the
top of the map. A section's VA range is therefore host memory whether or not
the title has loaded it, and nothing else may use that range: the title can
load the section at any time.

## Options

**(a) Paging alone.** Copy only the preload sections, and load the rest on
`XeLoadSection`. This matches the console, but on its own it frees nothing.
The deferred sections still own their VA in the flat map, the heap still
starts above `image_hi`, and BLiNX 1 still gets 12 MB.

**(b) Heap above the image, with a separate budget.** Grow the mapping past
RAM so the heap above the image is as large as the console's free RAM. This
alone fixes the out-of-memory, since 128 MB already does. But it leaves every
section loaded at boot, which the console never does. A title that patches a
section after loading it and expects fresh bytes on the next load would see
its own patches.

**Chosen: (a) and (b) together, opt-in.** Paging gives the console's load
semantics. The grown map gives the heap a place that does not collide with
section VAs. The size grows only as far as the console's free RAM at boot
(64 MB minus the preload bytes), rounded up to whole RAM sizes so the mirror
stride stays a multiple of 64 MB. For BLiNX 1 that is 128 MB, the same map
size BLiNX 2 and Half-Life 2 already run with.

## Decisions

- **Fresh copy on 0 -> 1.** The disc read on the console returns the image's
  bytes, and titles fix up pointers in a section after loading it. So the
  copy comes from the module's own copy of the image bytes, not from what is
  left in the VA range.
- **Bytes stay on 1 -> 0.** The console frees the pages, and an access after
  that faults. Zeroing here would only turn a console fault into silent
  zeroes. The next load recopies anyway.
- **Preload sections load at boot through the same path.** That gives them
  refcount 1 and counted shared pages, as on the console. A title can
  unload one and later reload it fresh.
- **Off by default.** Paging off, both calls only count, exactly as before.
  Titles that do not ask see no change. The `RECOMP_XBE_PAGING` key overrides
  the title's choice either way, for A/B runs.
- **Budget reported, not enforced.** Each load/unload edge logs how many
  sections are resident and their size. The heap is sized once, at boot, to
  what RAM holds after the preload sections, and loads do not change it. A
  limit would need the heap and the contiguous pool charged against the same
  64 MB, which neither does today.
- **Spin lock.** The console serialises section loads. Loads are rare, and a
  C11 `atomic_flag` keeps the module free of the host layer, so the ctest
  links it alone. A waiter yields after 64 spins, since the holder can be
  copying a 4 MB section.

## 64 MB assumptions

With paging, most of the heap sits above `0x04000000` while RAM stays 64 MB.
BLiNX 2's 128 MB layout already puts its heap there, so none of what follows
is new to the toolkit. The list says which 64 MB checks a heap address can
reach and what each one does above 64 MB.

- Handled above 64 MB:
  - the APU (`apu_core.c`): above 64 MB an address resolves through
    `apu_mapped_ram()`, which is the map size. `& 0x03FFFFFF` applies only
    past the map, so a DirectSound buffer on the heap does not alias low RAM;
  - `xbox_PhysNoteRamName`: ignores addresses at `XBOX_CONTIG_SIZE` and
    above. Harmless, because the APU path takes them first;
  - the GPU and `fb_present`: D3D surfaces and PVIDEO come from the
    contiguous window, not the heap.
- Different above 64 MB (the same as BLiNX 2 today):
  - `NtQueryVirtualMemory` is bounded by the compile-time `XBOX_TOTAL_RAM`.
    A heap page above it reads as one uncommitted page, not committed RAM;
  - title KEVENTs (`RECOMP_TITLE_KEVENTS`): a KEVENT at `0x04000000` or above
    gets no host event, so a wait on a heap-allocated event could hang. A
    port that turns on both paging and title KEVENTs has to check this
    (task 3.5).
- Not reached by heap addresses:
  - the `XBOX_TOTAL_RAM` checks in the section loader and the thunk VA
    check, which bound image VAs;
  - `MmQueryStatistics`, which reports RAM;
  - the trace and pushbuffer sanity bounds at `0x04000000`;
  - OHCI's below-64 MB page-map checks, the 64 MB contiguous window at
    `0x80000000` and its tiled alias at `0xF0000000`.
- Already sized from the map: the RAM mirrors (a 128 MB stride, as with
  `xbox_SetMapSize`), `bridge_va_mapped`, `bridge_free_guest_pages` and the
  `NtAllocateVirtualMemory` aliasing check.
- Reservations: the heap stops at the unrounded size (`g_xbox_heap_cap`,
  what RAM can back after the preload sections), and `xbox_ReserveAlloc`
  hands out VAs between that cap and the top of the map. Before the review
  fix both reached the top, so a large `MEM_RESERVE` in a fragmented heap
  was granted over live heap blocks.

## Risks

- A title that reads a non-preload section without loading it now sees
  zeroes. On the console it would fault, so such a title is broken there
  too. Paging is opt-in per title.
- The host keeps a copy of every section's bytes (50 MB for BLiNX 1).
- A game fix, mod or HLE patch that writes into a non-preload section at
  boot writes into zeroed memory, and the first `XeLoadSection` overwrites
  it. On the console such a write would fault. A patch to a non-preload
  section has to run after the load.
