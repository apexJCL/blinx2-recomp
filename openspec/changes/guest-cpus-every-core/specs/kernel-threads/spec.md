## MODIFIED Requirements

### Requirement: A title's threads share one CPU
With `RECOMP_GUEST_CPUS=one`, the runtime SHALL run the main guest thread and every thread the title creates through `PsCreateSystemThreadEx` on one host core, the lowest the process may use; with `=<n>`, on that core; with `=all` or unset, on every core. This game leaves the key unset, and the guest CPU lock (`RECOMP_GUEST_LOCK`) gives it the console's one CPU. The kernel timer thread and the device models' threads SHALL keep their own cores. On a host without thread affinity the runtime SHALL say so once and leave the threads alone.

#### Scenario: Two guest threads add to one global pool
- **WHEN** the title's main thread and a worker both run `slot = count; fill entry; count = slot + 1` on a shared global without a lock
- **THEN** the two never run inside that window at the same time, as on the console's one CPU (the guest CPU lock, pinned or not), and no entry is lost

#### Scenario: A host thread made by a pinned guest thread
- **WHEN** a pinned guest thread creates a host thread (the kernel timer thread from `KeSetTimer`)
- **THEN** that thread gets the process's CPU mask, not the guest core

#### Scenario: Movie audio at spin pacing on native Windows
- **WHEN** the boot movies play on native Windows 11 with `present.pacing = "spin"` and the key unset
- **THEN** `RECOMP_TRACE=apu_ring` reports no stale-lap replays on the movie's ring voice
