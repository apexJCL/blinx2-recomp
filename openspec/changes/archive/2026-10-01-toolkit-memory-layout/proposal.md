## Why

The toolkit puts its own guest-side structures at fixed addresses chosen for small titles:
- a scratch region at 0x00700000: the RW data area, kernel data exports at 0x00740000, the fake TLS/Prcb, and the TLS block at 0x00770000
- the 8 MB main stack at 0x00780000
- the heap from 0x00F80000

BLiNX 2's image runs to 0x0303AC20 (73 sections, 48 MB). So every one of those structures lands inside the title's `.data`/BSS and later sections:
- The first heap allocation (1 MB, zeroed) wipes the end of `.data`, DOLBY and the start of DATED.
- Guest code then crashes in its heap routine on a corrupted pointer.

The section loader also stops at 64 sections, so BLiNX 2's last 9 (model data plus `$$XTIMAGE`) are never loaded.

This is host-independent. It blocks the macOS track and the Proton (Windows x86-64) track alike. The game side can't work around it, because the addresses are compile-time constants inside the toolkit's allocator, thread-stack and range-check code.

## What Changes

Toolkit (`../xboxrecomp`, branch `posix-host/portability`):
- **Runtime layout.** The toolkit region (scratch structures, then stack, then heap) starts at the first 64 KB boundary above the highest loaded section, and never below today's 0x00700000. For any title whose image ends below 0x00700000, every address is unchanged. `XBOX_STACK_BASE`, `XBOX_STACK_TOP`, `XBOX_STACK_SIZE`, `XBOX_HEAP_BASE` and `XBOX_KERNEL_DATA_BASE` become runtime values. Their macro names stay, so callers don't change.
- **Main stack size.** It stays 8 MB unless that would leave the heap under 16 MB. It then shrinks, down to a 1 MB floor. That is still 16 times what BLiNX 2's XBE asks for (64 KB stack commit).
- **Section loading.** All sections in the header are loaded; the old 64-section cap is replaced by the existing per-section bounds checks.
- **Fit check.** Boot fails with a clear error if the image plus the toolkit region don't fit in the mapped RAM.
- **Worker stack slices** (host-tick-driven titles) are only handed out while they fit inside the actual stack region.

The game side needs no change: `cat/src/main.c` already assigns `g_esp = XBOX_STACK_TOP`, which now reads the runtime value.

## Capabilities

### New Capabilities
- `guest-memory-layout`: where the toolkit places its own guest-visible structures (scratch region, main stack, heap) relative to the title image, and what happens when they don't fit.

### Modified Capabilities
<!-- none -->

## Impact

- **Code**:
  - `xboxrecomp/src/kernel/xbox_memory_layout.h`, `xbox_memory_layout.c`: layout globals, section loop, heap initialization, fake TIB/TLS addresses
  - `kernel_thread.c`: worker-slice guard
  - every other user keeps working through the same macro names
- **Other titles**: unchanged when the image ends below 0x00700000. Titles between 0x00700000 and 0x00F80000, such as Half-Life 2 at 0x009B68C0, get a stack and heap that no longer overlap them. Today their stack overlaps the image, which is the bug the thread-stack comment in `xbox_memory_layout.c` already describes.
- **BLiNX 2**:
  - scratch region at 0x03040000
  - 1 MB stack at 0x030C0000–0x031C0000
  - heap 0x031C0000–0x04000000 (14.25 MB)
- **Upstream**: belongs with the drafts in `cat/analysis/upstream/`.
