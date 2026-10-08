## Why

The stage-1 pool and the mission-1 lake rendered dark under Proton on about one stage load in five (Steam Deck and the Linux/Proton host, build 20261007.1633). A write watch on a terrain vertex colour (`runs/water/88ad521-watch-9,10`, `c26f617-watch-11..16`) showed the game's own vertex-light bake (`sub_00045A50`) writing `FF000000` in a bad run and `FF5E5E4B` in a good one, from the same chain on the same thread: the bake was reading a mangled light pool. A watch on the pool count `0xAACDFC` (`bench-logs/20261007-134259`) showed why: at stage load the title spawns a loader thread (`PsCreateSystemThreadEx`, `sub_0005E410`), and both it (`sub_00048880`) and the main thread (`sub_000E7F90` → `sub_00037CE0`) add lights to the one global pool with `slot = count; fill entry; count = slot + 1`, interleaved, each transition written twice, so entries were lost. Terrain pieces baked from the mangled pool came out black, and the ground, both water reflection targets and the water lost their light.

The title is correct on the console: one CPU, and two threads of equal priority interleave only at a quantum boundary or a wait, never inside a few instructions. The host ran the two threads on two cores. No backend is involved; the candidate D3D11 commits only shifted timing.

## What Changes

- The toolkit runs a title's threads as the console's one CPU did, in its first form by pinning them to one host core: the main guest thread and every `PsCreateSystemThreadEx` worker take the lowest core the process may use (`xbox_GuestThreadPin`, `kernel_thread.c`). `RECOMP_GUEST_CPUS=all` leaves them on every core (the A/B), `=<n>` picks the core.
- Not pinned: the kernel timer thread (the title's DPCs and timer routines) and the device models' threads (ISRs under the one-CPU gate). They run lifted code too, but they stand in for interrupts, which on the console ran between any two instructions; the gate orders them against guest code at DISPATCH_LEVEL, and queuing them behind a main thread spinning in its frame wait is the m1hang latency.
- The POSIX compat layer gains `SetThreadAffinityMask` and `GetProcessAffinityMask` with Win32 semantics: a new thread gets the process's mask, not its creator's. macOS has no thread affinity, so the pin is a no-op there and says so once; the race stays live on the Mac (see design, alternative A, filed as BLX-31).
- A ctest, `tests/kernel_guest_cpu`, and a row in `docs/env.md`.

## Capabilities

### Modified Capabilities
- `kernel-threading`: a title's threads share one host core, as they shared the console's CPU; host service threads keep theirs.

## Impact

- toolkit: `src/kernel/kernel_thread.c`, `kernel_bridge.c` (the three thread starts), `kernel.h`, `src/platform/win32_compat.{c,h}`, `recomp_env.h`, `tests/kernel_guest_cpu`. Debug aids on the same branch: the write watch covers both views of a contiguous page on Win32, re-arms, names untrapped changes and samples the `RECOMP_PEEK` globals at the write.
- cat: `docs/env.md` rows, `TASKS.md` follow-up.
- Every title: Burnout 3 is more heavily threaded, so one B3 smoke under Proton before the merge and the full B3 gate before any upstream PR.
- Cost: the loader and any audio worker share the core with a main thread that busy-waits at `present.pacing=spin`; console-faithful, measured in the tasks (flips/s pinned vs `all`, stage 1 and the hub; flag a 25% drop).
