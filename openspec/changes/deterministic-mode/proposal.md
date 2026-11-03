## Why

Two replays of the same pad record do not play the same game. The user's
clip3 take (`runs/sandwich-clip/user-clip3-20261101.pad`, poll clock) has
Blinx tunnel through a wall and land off-bounds; replayed on the Mac it
tunnelled and died twice on an idle host (g4065, g4066) and did not tunnel
at all under build load, where the stage load landed 9 polls later (g761
vs g752) with identical input. So host timing decides the outcome. Until
two runs of one input agree, a bug like the tunnel can't be bisected,
a fix can't be proven, and a golden can only compare pictures loosely.

Host time reaches the guest through many doors: the clocks it reads, the
waits it times out, the vblanks it is paced by, the order its threads get
the guest CPU, the loader's and the audio's host threads. Deterministic
mode closes them one phase at a time, measuring after each what still
differs.

## What Changes

Four phases (one item each):

1. **Virtual clock and state hash (this change in detail).**
   - Toolkit: every guest clock read goes through `src/kernel/guest_time.c`
     (a no-op refactor, its own commit). Behind the new debug key
     `RECOMP_DEBUG=deterministic` those clocks derive from a count of
     emulated vblanks: frozen between two, one 60 Hz period at each, fixed
     epoch (2004-01-01) and counter frequency (10 MHz). Timed waits, delays
     and kernel timers end on the same clock.
   - Toolkit: `RECOMP_DEBUG=state_hash=<path>` hashes guest RAM at the end
     of every port-0 pad poll (the clock a replay's input is timed by), with
     per-page hashes, skip ranges and full dumps at chosen polls.
   - cat: BLiNX 2's vblank pacer (`sub_002E0DB0`) waits on the virtual
     clock in that mode.
   - Measurement: clip3 and the stage1 golden scenario, each replayed twice
     on the PC with the mode on; the first poll whose hashes differ, the
     memory, its owner. The report lists what phase 2 must pin.
2. **Lockstep vblanks.** What the phase-1 report names; expected:
   vblanks raised in step with the guest (a vblank after N guest polls or
   when the guest idles, not on the host's 60 Hz), so the virtual clock no
   longer inherits host time through the vblank schedule. Lockstep must not
   deadlock: "idle" means every guest thread is blocked in a virtual wait
   (on an object, a delay or a timer, never a host-only wait), and only then
   does the stepper advance one vblank, which is what lets those waits end.
   A thread that spins without a kernel call never counts as idle (D5 names
   it). Doors still open for this phase: the NV2A PTIMER
   (`nv2a_core.c:196`, `qemu_clock_get_ns`), the KSYSTEM_TIME write order
   (the step writes High1Time and LowPart but not High2Time, so a guest
   reader's High1/High2 check can't catch a torn read), and the MCPX
   free-running counters the 1 ms ack loop ticks. Option: count the
   performance counter at the console's ACPI rate, 3,375,000 Hz (56,250
   counts per vblank; the value Cxbx-Reloaded and nboxkrnl return from
   KeQueryPerformanceFrequency), instead of 10 MHz, if a title scales by it.
3. **Ordered guest threads.** With one guest CPU
   (`RECOMP_GUEST_LOCK`), hand the lock over in a fixed order at kernel
   calls, and make the loader's and the audio's host-side completions land
   at fixed guest points. Doors still open for this phase: the APU sample
   clock (`apu_core.c`, `qemu_clock_get_ns` and the host's consumed-sample
   count), and the state hash itself, which is not a snapshot: it reads RAM
   while host threads write it, so it runs with the guest lock on and skips
   the host-written ranges. It also covers guest RAM only, not GPU, APU or
   host-side state.
4. **Replay check.** A `golden`/bench mode that replays a record
   twice and fails on the first differing hash; the tunnel bisect.

### Phase 1 result

The report (posted, "phase 1 report") shows two
mode-on replays of clip3, and two of the stage1 scenario, differ from
poll 0: the virtual clock is pinned, but vblanks are still paced by the
host's 60 Hz, so the guest reaches poll 0 after a different vblank count
(stage1: 120 against 122). The first differing pages are the clock
exports (KeTickCount, KeInterruptTime), the game's frame-time floats and
counters in .data, a D3D section word, the main thread's stack and a heap
block; from poll 1000 about 130 pages differ. Phase 2 (lockstep vblanks)
is the next door to close.

All of it is opt-in and debug-tier. Off, every read is the host's, exactly
as before. Goldens run with it off.

## Impact

- Toolkit `src/kernel/`: new `guest_time.{c,h}`, `guest_state_hash.{c,h}`;
  `kernel_hal.c`, `kernel_bridge.c`, `kernel_sync.c`, `kernel_thread.c`,
  `xbox_memory_layout.c` read the clocks through them. `src/usb/usb_gamepad`
  gets a poll hook. Four debug keys in `recomp_env.h`. A ctest
  `tests/guest_time`.
- cat: `src/recomp_manual.c` (the pacer), `docs/env.md` rows.
- No game knowledge in the toolkit; shaped for upstream.
