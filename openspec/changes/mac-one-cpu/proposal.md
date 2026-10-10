## Why

BLX-1 found BLiNX 2's light-pool race (`sub_00037CE0`: `slot = count; fill; count = slot + 1` from the main thread and the stage loader thread at once, count `0xAACDFC`) and closed it with a pin: every guest thread on one host core (`RECOMP_GUEST_CPUS`, openspec `guest-one-cpu`). Two things are left open:

- macOS has no thread affinity, so the pin is a no-op there (`[KERNEL] guest threads: this host sets no thread affinity`) and the race is live on the Mac. The Mac goldens have not shown dark water, which says the host's scheduling makes the window rarer there, not that it is closed.
- The pin only narrows the race where it works: the host still preempts at its tick, and a tick between the lifted load, add and store loses an entry. "As rare as on the console" rather than impossible (the upstream-sync review, design row 16).

Upstream v0.13.1 (synced on `sync/upstream-v0.13.1`) brings its own answer to the same problem, `RECOMP_GUEST_LOCK` (#160): one guest thread runs guest code at a time, the lock let go for the length of every kernel call. It gives the guarantee the console gave, deterministically, on every host including macOS. But as it stands it does not fit BLiNX 2: the Mac attract run paced at 23.1 fps against 58.3 with it on, and upstream's own note says a guest thread spinning on a flag another guest thread sets, with no kernel call in the loop, deadlocks under it.

The operator's rule is to build on upstream's mechanism where one exists. This change makes `RECOMP_GUEST_LOCK` work well on BLiNX 2 and turns it on, so the Mac gets the guarantee the pin gives elsewhere, and the pin can go once the Proton measurement says the lock alone paces as well.

## What Changes

- **The guest CPU schedules as the console did** (toolkit `src/kernel/kernel_guest_cpu.c`), keeping upstream's switch, entry points and rule: `RECOMP_GUEST_LOCK=1`, `guest_cpu_join`/`guest_cpu_part` at a guest thread's start and end, the lock released for the length of every kernel call and taken back after. A kernel call that returns at once switches nobody (the caller takes the CPU straight back); one that may block wakes the waiters; a thread past its quantum (`guest_quantum`, 4 ms) with another waiting hands over to the oldest waiter at its next call; a yield hands over at once. Upstream's plain critical section let a worker keep the CPU through a burst (p95 70 ms); a fair ticket lock switched at every call (12.7 flips/s). See design D2.
- **The lowered spin-wait passes are yield points at every pacing.** `RECOMP_SPIN_WAIT` (templates/runtime/recomp_types.h) also fires while another guest thread waits for the CPU (`g_xbox_guest_cpu_waiters`), and `xbox_SpinWait` hands the CPU over before it spins or sleeps and takes it back after. That is the console's quantum expiry at the one place lifted code already calls into the host inside a loop, and it ends the deadlock upstream's note describes for every lowered loop.
- **Guest code a bridge runs on a guest thread holds the CPU**: an APC completion routine (`NtUserIoApcDispatcher`), an unwind handler (`RtlUnwind`), a `KeSynchronizeExecution` routine, and a worker run inline (`RECOMP_WORKERS=inline`). The thunk dispatch takes the CPU back when it had it, not only at depth 0, so an inline worker's own kernel calls behave. ISRs and DPCs never take it, on any thread (upstream's rule; see design D4).
- **Diagnostics.** The `[PACING]` summary gains a guest-CPU line: holds, waits, yields, the longest hold and the longest wait with where the hold ended (kernel ordinal or spin-wait VA). `RECOMP_TRACE=guest_cpu[=ms]` logs each hold longer than ms (default 4) the same way. The longest holds name the guest loops that still need a `spin_waits.json` entry.
- **cat turns the lock on** (`src/main.c`, like `RECOMP_VBLANK`; an explicit `RECOMP_GUEST_LOCK=0` wins). The pin stays as the toolkit default on Win32 and Linux; `RECOMP_GUEST_CPUS=all` with the lock on is the Proton A/B that decides its retirement (owed to the bench agent, section 6 of tasks).
- **cat `config/spin_waits.json`** gains the sites the hold log names on the attract, stage 1 and story routes, then `blinx2 analyze && blinx2 recomp`. Expected first: `0x00334325` (the DSOUND submit's GP-doorbell spin in `sub_003341BE`, cleared by the APU frame thread, up to one APU frame per submit).
- A ctest, `tests/guest_cpu`: mutual exclusion of guest code (no lost update across 10^6 unlocked read-modify-writes from four guest threads), a deadlock-free spin on another guest thread's flag through the spin-wait yield, FIFO hand-off, the inline-callback case, kernel-call release, and the switch off.

## Capabilities

### Modified Capabilities
- `kernel-threads`: guest code runs on one thread at a time, released at kernel calls and spin-wait yields, on every host (adds to the `guest-one-cpu` pin, which stays where the host has affinity).

## Impact

- toolkit (`fix/mac-one-cpu` off `sync/upstream-v0.13.1`): `src/kernel/kernel_guest_cpu.c` (new), `kernel_bridge.c` (join/part/dispatch call into it; the four callback sites), `kernel_pacing.c` (`xbox_SpinWait` yield, the summary line), `kernel.h`, `templates/runtime/recomp_types.h` (the macro's third flag), `src/platform/recomp_env.h` (`guest_cpu` trace key, `guest_quantum` debug key), `tests/guest_cpu`, `CMakeLists.txt`. No lifter change: the generated C is unchanged, only the header it includes.
- cat: `src/main.c` default, `docs/env.md` rows (`RECOMP_GUEST_LOCK` now on, `guest_cpu` trace, the `RECOMP_GUEST_CPUS` note), `config/spin_waits.json`, regenerated `src/recomp/gen/`, `TASKS.md`.
- Burnout 3 and every other title: the lock stays off unless the title's main.c turns it on; the toolkit's defaults do not move.
- Cost: two lock operations per kernel call and per spin-wait pass with a waiter; a guest thread that computes for long without a kernel call holds the others off for that long (the console's quantum would not have). Measured in tasks 5.x; the lifter-inserted yield at loop back edges is the follow-up if a hold past 20 ms shows up on a route.
- Integration: the branch rebases onto `integrate/sync-dpc` (the BLX-2 DPC drain on guest threads). The drain runs inside the raise bridge, where the CPU is already released, so it needs nothing from this change (design D7).
