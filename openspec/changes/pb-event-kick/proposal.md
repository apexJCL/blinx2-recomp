## Why

The NV2A ack loop (toolkit `xbox_memory_layout.c`, `nv2a_ack_thread`) finds
the guest's GPU work by polling. Between its 1 ms ticks, while the title is
kicking, it reads `DMA_PUT` and the PFB flush bit (`0x100410`, bit 16) every
~50 us. D3D's KickOff raises that bit and spins until the loop clears it,
then stores `PUT`. The guest's stores are plain memory writes with no trap,
so the poll was the only way to see them. The tracker item measured its cost: a
50 us nap is 107-112 us under Wine and about 77 us on the Mac, and the
polling thread takes about 0.3 core on the Deck and 0.2 on the Mac, for a
title that kicks about a thousand times a second.

## What Changes

- **Toolkit**: with `kick_event=1`, between ticks the ack loop sleeps on a
  host waker (a new `XboxHostWaker` in `host_time.c`) until the guest has work for it.
  Three things wake it:
  - **the KickOff's own spin.** It is a lowered spin-wait site
    (`spin_waits.json`). `RECOMP_SPIN_WAIT` now also calls `xbox_SpinWait`
    while the walker sleeps (`g_xbox_kick_armed`), at either pacing. When
    work is pending (the flush bit set, or `PUT` past what the walker has
    executed), the pass pokes the walker;
  - **the `PUT` store right after an ack.** No guest pass follows that
    store, so the walker spins up to 100 us watching `PUT` after each
    clear;
  - **each vblank** (a held flip releases on the count). The 1 ms tick
    stays as the bounded fallback.
- **Fallback for titles that cannot poke**, such as one whose KickOff spin is
  not lowered (JSRF until the tracker item), or a gen built before this change. When
  3 kicks in a row are found by the tick instead of a poke, the loop polls
  as before for the rest of the run and says so once.
- **Template**: `recomp_types.h`'s `RECOMP_SPIN_WAIT` reads the new flag,
  so a game regenerates (`analyze`, then `recomp`). Old gen still compiles
  and runs, and falls back to the poll.
- **Opt-in**: `RECOMP_DEBUG=kick_event=1` (Debug tier) turns it on; the
  default stays the old poll (design.md, decision 7).
- **Trace**: with `RECOMP_TRACE=pacing`, a `[PACING]   kick wait:` line every
  600 flips. It gives the mode, the sleeps and what ended them, the `PUT`
  watch and the walker thread's CPU, in both modes.

The change is latency only: the same acks in the same order, with no
earlier ack, and both backends are equal (the change is below them). It
still lands off by default: the gain is small until the tracker item, and a late
walk can shift the flip hold's grid (design.md, decisions 4 and 7). The guest-side JSRF KickOff spin (`sub_001912A0`)
is the tracker item, not this change.

## Impact

- Toolkit: `src/kernel/nv2a_kick_wake.{c,h}` (new),
  `xbox_memory_layout.{c,h}`, `kernel_pacing.{c,h}`, `kernel_bridge.c`
  (vblank nudge), `platform/host_time.{c,h}`, `platform/recomp_env.h`,
  `templates/runtime/recomp_types.h`, `tests/kick_wake` (new ctest).
- Games: regenerate to get the poke. BLiNX's gen diff is the one macro line
  in `recomp_types.h`.
- cat: `docs/env.md` gets the `kick_event` row.
