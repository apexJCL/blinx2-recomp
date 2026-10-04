## Context

`xbox_MemoryLayoutInit` maps guest RAM and copies the XBE sections. It then builds, at fixed VAs:
- the fake Prcb (0x00761000)
- the fake TLS (0x00760000)
- the RW data pointer target (0x00700000)
- the TLS block (0x00770000)
- the kernel data exports (0x00740000, filled later by `kernel_bridge.c`)
- the main stack (0x00780000, 8 MB)

The bump heap starts right after the stack. Thread stacks and TIBs already come from the heap, which assumed the heap sits above the image. These are all compile-time macros used in about 80 places, mostly `XBOX_KERNEL_DATA_BASE + KDATA_*` in `kernel_bridge.c`.

## Goals / Non-Goals

**Goals:**
- No toolkit structure overlaps a loaded section, for any image size that fits.
- Identical addresses for titles that fit below 0x00700000 today.
- Every section in the header loads.

**Non-Goals:**
- Changing how large the heap is relative to RAM (it still runs to `XBOX_HEAP_TOP`).
- Per-thread TLS blocks.
- Devkit 128 MB policy.

## Decisions

1. **One movable region, offsets kept.** `g_xbox_region_base = max(0x00700000, align64K(g_xbox_image_hi))`. The existing structures keep their offsets from 0x00700000:
   - RW data +0x00000
   - kernel data +0x40000
   - TLS +0x60000
   - Prcb +0x61000
   - TLS block +0x70000
   - stack +0x80000

   Keeping the offsets is what makes the small-image case bit-for-bit identical. It also keeps the code change local: each `#define FAKE_*_VA 0x007x0000` becomes `g_xbox_region_base + offset`.
2. **Macros become runtime expressions, names kept.** `XBOX_STACK_BASE` expands to `g_xbox_stack_base`, `XBOX_STACK_SIZE` to `g_xbox_stack_size`, and `XBOX_KERNEL_DATA_BASE` to `(g_xbox_region_base + 0x40000)`. TOP and HEAP_BASE are already derived from those. One static initializer (`g_heap_next = XBOX_HEAP_BASE`) needs a constant, so the heap pointer is set in `xbox_MemoryLayoutInit` instead. `XBOX_KERNEL_DATA_SIZE` and the worker slice size and count stay constants.
3. **Layout is computed right after the section loop.** That's the first point where `g_xbox_image_hi` is known. Every user (TIB setup, stack init, heap print, `kernel_bridge` exports) runs after it.
4. **Stack sizing.** Let `avail = XBOX_HEAP_TOP - stack_base`. The stack is 8 MB if `avail - 8 MB >= 16 MB`. Otherwise it is `max(1 MB, avail - 16 MB)`, rounded down to 64 KB. A shrunken stack is logged. Real hardware gives the main thread the XBE's stack commit (64 KB for BLiNX 2), so 1 MB is generous. Worker slices (256 KB each) are only handed out while `(slot + 1) * 256 KB <= stack size`.
5. **Fit check is fatal.** If `avail < 1 MB + 1 MB` (stack floor plus a minimal heap), `xbox_MemoryLayoutInit` prints the image end, region base and RAM size, and returns FALSE. `main.c` already turns that into a `[FATAL]` startup error.
6. **Section cap.** The 64-section cap is dropped. The loop already stops at the first header that runs past the buffer, and skips sections outside RAM.

## Risks / Trade-offs

- **A title that relied on toolkit structures sitting inside its BSS.** Unlikely: they were placed there "in free BSS", by assumption, for small titles. Their addresses don't change for those titles.
- **A 1 MB main stack for BLiNX-sized images.** Deep recursion could overflow it. Guest stack overflows run into the scratch region below the stack, not into the image, and the crash report's esp range check flags them.
- **The heap shrinks for large images.** That's inherent: the 64 MB map can't hold more. Out-of-memory is already reported by `xbox_HeapAlloc`.

## Open Questions

### Result of the first boot (2026-10-01, toolkit commit af46dcb, `cat/analysis/bringup/layout-1.err` (local analysis, not published))

- The layout is as designed:
  - 73/73 sections loaded
  - region at 0x03040000, kernel data at 0x03080000, TLS at 0x030A0000/0x030B0000
  - 1 MB stack at 0x030C0000
  - heap 0x031C0000–0x04000000 (14 MB)
- The formula gives today's addresses for a small image (end 0x3B2FFF → 0x00700000/0x00740000/0x00780000/0x00F80000). For Half-Life 2 (end 0x009B68C0) the region moves to 0x009C0000, with an 8 MB stack.
- **The crash is unchanged.** It's still a write to guest 0x89DF3BF8 in `sub_002A02E0+0x2A8` (eax=esi=0x89DF3BC0, edi=0x00F30E80), on the boot thread, called from the game's main init thread. The overlap was real, but it was not the source of this pointer.
- **Probable cause, and the next blocker: recompiler coverage.** 25 indirect calls failed to resolve before the crash:
  - `0x002D702E` (three times) is a worker-thread routine passed to PsCreateSystemThreadEx. It is not a function start; it falls inside `sub_002D7024` (0x002D7024–0x002D7096). So the thread exits without running, and whatever it was meant to initialize stays garbage.
  - `0x0032401D`, `0x00324029`, `0x00324035`, `0x003340D7`, `0x003340E2`, `0x003355DF`, `0x003355EA` and others lie in the XGRPH and DSOUND library code sections, outside `.text`. The disassembly appears to cover `.text` only.
  
  Both are fixed at the recomp stage (function discovery: extra entry points and executable non-`.text` sections), not in the memory layout.
