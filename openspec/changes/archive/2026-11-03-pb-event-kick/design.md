## Context

The ack loop has two jobs between its 1 ms ticks:
- start the walk as soon as `PUT` moves;
- clear the KickOff flush bit once everything submitted has been executed.
  It must never clear it earlier: see the comment at `NV2A_KICK_REG`.

While a flip is held (`nv2a_pb_exec_flip_poll`) it does neither, until the
vblank count reaches the swap interval.

BLiNX's KickOff (`sub_002E7F30`) runs in this order:
1. set the bit;
2. spin at the lowered site `0x002E7F70` until the bit is clear;
3. store `PUT` (`MEM32(ecx+0x40) = edx`).

So the store comes a few instructions after the spin sees the clear, and no
spin pass follows it.

## Goals / Non-goals

- Goal: the walker thread off the CPU between kicks. The same kick latency,
  or close, and no lost wake-up.
- Goal: safe on any title. A title that cannot wake the walker gets the old
  poll, not a 1 ms stall per kick.
- Non-goal: the guest side of the spin, or trapping the guest's
  stores.

## Decisions

1. **Dekker handshake on one flag.**
   - The walker stores `armed` (seq_cst), fences, then checks for pending
     work. When there is none it sleeps.
   - A guest pass, after its own store, fences (seq_cst, in
     `RECOMP_SPIN_WAIT` and again in `xbox_SpinWait`), loads `armed`,
     checks for pending work, then takes the flag with a CAS and wakes the
     waker.
   - With a seq_cst fence on both sides, at least one side sees the other:
     the walker sees the work, or the guest sees `armed`. A wake that
     arrives before the walker blocks is latched by the waker.
   - The guest's fence came with the review. Without it the generated
     code's plain store and plain load of `armed` reorder (the store-buffer
     litmus); at spin pacing the next pass reads the flag again, but a loop
     that makes one pass and then sleeps (sleep pacing) lost about one poke
     in a thousand on the Mac. `tests/kick_wake` now runs that guest: one
     relaxed store, the fence, one relaxed load. It prints the unfenced
     loss beside the fenced run, which must be 0.
   - If the walker's timeout races a poke, the walker finds the flag already
     taken. It then waits for that wake, which is a few instructions
     behind, so the wake is not left latched to end the next sleep early.
     `tests/kick_wake` runs 20000 kicks with one poke per store and a 200 ms
     timeout. It checks that no sleep times out with work pending.
2. **Two arm values.**
   - `ARM_WORK`: pending work or a nudge ends the sleep.
   - `ARM_NUDGE`, used while a flip is held: the flush bit stays set until
     the vblank, so a work-armed sleep would return at once, and every
     KickOff pass would wake the walker for nothing. Only the nudge or the
     timeout ends a held sleep.
3. **The poke rides `RECOMP_SPIN_WAIT`.**
   - It is the one guest hook in the KickOff. The macro's condition gains
     `g_xbox_kick_armed`. At spin pacing that costs one call per pass, and
     only while the walker sleeps.
   - `xbox_SpinWait` pokes first. It returns at once when none of the old
     flags is set, so spin pacing stays a spin.
   - At sleep pacing the site sleeps as before, after the poke.
4. **The `PUT` watch.**
   - After each ack the walker spins up to 100 us (`KICK_WATCH_NS`) for
     `PUT` to move.
   - On the Mac the store lands in about 1 us (`put watch hits ... avg
     0.7-1.3 us`). A watch that runs out (the guest preempted between its
     spin and the store, mostly around host hitches) drops to the ~50 us
     poll for the rest of the tick, not to the sleep: no poke follows that
     store, and a walk that starts up to a tick late can cross a vblank.
     The flip hold samples the vblank count when the walk starts
     (`nv2a_pb_exec_walk_begin`), so that frame counts one vblank late and
     every later interval-2 frame is held one vblank: kickwait +16 ms per
     flip at the same 30 fps, until a later hitch shifts the grid back.
   - The 24.5 ms episode (tasks.md 3.4) is that shift, but the event wait
     is not what causes it. With injected hitches (SIGSTOP 30-60 ms every
     5 s, tasks.md 4.3) the poll arm slips the same way: the hitch itself
     makes the walk late. The poll after a watch miss stays, since it
     removes one source of late walks that only the event wait has. The
     hold finding its way back is the tracker item.
5. **Vblank nudge.**
   - `kernel_vblank_count` nudges the walker after it bumps the count. A
     held flip then releases at the vblank, as it did at the 50 us poll.
   - The held sleep takes the count read before the hold's poll. After it
     arms (seq_cst, then a fence) it reads the count again and returns at
     once when it moved: a vblank between the poll and the arm saw no flag
     and nudged nobody. The nudge fences before it reads the flag, the
     other half of that pair.
6. **Miss detection and fallback.**
   - A timeout that finds the flush bit set, or `PUT` past what the walker
     executed, with no flip held, is work the guest stored without poking.
     `PUT` counts too for a title that moves it without the flush
     handshake.
   - 3 such kicks in a row (`XBOX_KICK_WAKE_MISS_LIMIT`) turn the event wait
     off for the run, and a poked kick resets the count.
   - Titles without a lowered KickOff, and gen without the new macro,
     therefore end up on the old poll after 3 ms.
7. **Default off, `kick_event=1` to opt in.**
   - The acks happen in the same order and never earlier, so the change is
     latency only. But its gain on BLiNX is small (2 points of a core, Mac
     and Deck), JSRF cannot use it until the tracker item lowers its KickOff spin,
     and the round-1 review showed that a late walk can shift the flip
     hold's grid for the rest of a run. So it lands off, and is turned on
     when all of these hold:
     - The tracker item has landed and JSRF (or another title) shows a gain;
     - a soak with `RECOMP_TRACE=pacing` (the `flip hold: holds` count per
       window) shows no hold slip on the Mac, the Deck and native Windows.
8. **The host waker per host.**
   - POSIX: a mutex and a condition variable on the monotonic clock.
   - Wine: an SRW lock and a condition variable, both in-process futexes,
     whose millisecond timeout Wine honours. A waitable timer there is a
     wineserver object, two round trips a sleep.
   - Native Windows: the condition variable's timeout runs on the system
     clock interval, 15.6 ms when nothing raised the timer resolution, so
     the 1 ms tick could cost 15.6 ms. The waker there is an auto-reset
     event (the latch) and the high-resolution waitable timer for the
     timeout, at most one clock interval (0.5-1 ms) late. A Windows without
     that timer (before 10 1803) gets no waker, and the loop polls.
     Native Windows has not been run yet; it is part of the default-on
     soak.

## Risks

- A `PUT` store that is not preceded by a kick and is not followed by a
  lowered pass: the tick finds it up to 1 ms later, where the poll took
  ~50-110 us. Three in a row turn the event wait off (decision 6). The goldens and the `[PB-PERF]` kickwait check for this; see
  tasks.md.
- Hosts where the watch misses often (Wine scheduling): those kicks wait for
  the next pass or the tick. The miss rate is in the `[PACING]` line.
