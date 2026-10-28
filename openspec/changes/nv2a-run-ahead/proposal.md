## Why

The walker acks the KickOff flush (PFB 0x100410 bit 16) only once it has
caught up, so the title waits at every KickOff for the segment before it.
A frame costs the title's time plus the walk's. BLiNX 2 kicks about 26
times in a heavy frame, and on the Deck `@stage1-2-barricade` spends about
23 ms of a 35 ms heavy frame in that wait. On the console the GPU acks the
flush at once (xemu `pfb.c` and Cxbx-Reloaded `EmuNV2A_PFB.cpp` read
`NV_PFB_WBC` as 0). What bounds the CPU there is D3D's MakeSpace (GET) and
BlockOnTime (the fence and, past 8 KB behind, the PGRAPH notify
interrupt).

The tracker item is a spike: measure what run-ahead gains, behind a debug key that
defaults off, before the tracker item decides whether it becomes a default.

## What changes

- `RECOMP_DEBUG=run_ahead=N` (toolkit, default off). When it is on:
  - every ~4 KB of a walk that executes, GET is stored at a top-level
    method header;
  - at the same point, the flush is acked while fewer than N segments are
    submitted past the walk, and never while a flip is held.
- With the key on, D3D's `NOP` software method 5 (BlockOnTime's event)
  raises the PGRAPH notify interrupt the way xemu models it. The timer
  thread delivers it on vector 3 through the one-CPU gate (IRQ line
  `nv2a-gr`). The walk stalls for the handler for 50 ms at most. A notify
  that finds another still pending is queued behind it.
- A `[PACING]   run ahead:` line under `RECOMP_TRACE=pacing`, and an
  `[IRQ] nv2a-gr` line once that line has been used.
- One env.md row. One ctest, `tests/gr_notify`.

With the key off, nothing in this change runs. The flush is acked as
before.

## Impact

- toolkit: `src/kernel/nv2a_gr_notify.h` (new), `xbox_memory_layout.c`,
  `kernel_bridge.c`, `kernel_hal.c`, `kernel.h`, `nv2a_pb_exec.c`,
  `nv2a_pb_scan.c`, `src/platform/recomp_env.h`, `tests/gr_notify/`.
- cat: the `docs/env.md` row only. There is no game code or config.
- Follow-ups: the tracker item (the vblank jitter and the notify stall), the tracker item
  (the default).
