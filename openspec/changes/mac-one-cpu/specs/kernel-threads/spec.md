## ADDED Requirements

### Requirement: Guest code runs on one thread at a time
With `RECOMP_GUEST_LOCK=1` (this game's default) the runtime SHALL let one guest thread run guest code at a time, on every host: the main guest thread, every thread the title creates through `PsCreateSystemThreadEx` (spawned or inline), and guest routines a kernel bridge runs on such a thread. A guest thread SHALL give the CPU up for the length of every kernel call and at every pass of a lowered spin-wait while another guest thread waits for it, and a release with a waiter SHALL hand the CPU to the longest-waiting thread. Interrupt service routines and DPCs SHALL run without it, on whichever thread runs them. With the switch off every operation SHALL be a no-op.

#### Scenario: Two guest threads add to one global pool
- **WHEN** the title's main thread and a worker both run `slot = count; fill entry; count = slot + 1` on a shared global without a lock
- **THEN** no entry is lost on any host, because the two never run guest code at the same instant

#### Scenario: A guest thread spins on another guest thread's flag
- **WHEN** a lowered guest loop spins on a word that only another guest thread writes, with no kernel call in the loop
- **THEN** each pass of the loop hands the CPU to the waiting thread, which writes the word, and the loop ends

#### Scenario: A kernel call lets the others run
- **WHEN** a guest thread enters a kernel bridge while another guest thread waits for the CPU
- **THEN** the waiter runs guest code for the length of the call, and the caller takes the CPU back before it returns to guest code

#### Scenario: The longest holds are named
- **WHEN** `RECOMP_TRACE=pacing` is on
- **THEN** the pacing summary reports the guest CPU's holds, waits and yields and the longest hold with the kernel ordinal or spin-wait address where it ended
