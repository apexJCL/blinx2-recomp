## MODIFIED Requirements

### Requirement: A title's threads share one CPU
The runtime SHALL run the main guest thread and every thread the title creates through `PsCreateSystemThreadEx` on one host core, the lowest the process may use, unless `RECOMP_GUEST_CPUS=all` (every core) or `=<n>` (that core) says otherwise. The kernel timer thread and the device models' threads SHALL keep their own cores. On a host without thread affinity the runtime SHALL say so once and leave the threads alone.

#### Scenario: Two guest threads add to one global pool
- **WHEN** the title's main thread and a worker both run `slot = count; fill entry; count = slot + 1` on a shared global without a lock
- **THEN** the two never run inside that window at the same time, as on the console's one CPU, and no entry is lost

#### Scenario: A host thread made by a pinned guest thread
- **WHEN** a pinned guest thread creates a host thread (the kernel timer thread from `KeSetTimer`)
- **THEN** that thread gets the process's CPU mask, not the guest core
