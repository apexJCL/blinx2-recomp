## Context

- The runtime runs each guest thread on a host thread of its own. Only code at DISPATCH_LEVEL and above, and the ISRs and DPCs, are serialised, through the one-CPU gate (`kernel_hal.c`, `irql_track_gated`); passive guest code runs in parallel on every core the process has.
- BLiNX 2 keeps its light pool in globals (`0xAACDFC` count, entries at `0x8E9088`, 36 bytes each) and adds to it from the main thread and from the loader thread it spawns per stage load, with a read-modify-write and no lock (`sub_00037CE0`, `recomp_0004.c`). On the console that is safe: one CPU, equal priorities, a quantum of milliseconds against a window of a few instructions. Other titles will have the same shape; nothing in the XDK tells a title to lock what one CPU protected.
- Evidence: `runs/water/c26f617-watch-16` (bad, `FF000000`), `-11..15` (good), the pool watch `bench-logs/20261007-134259` (both stacks writing `0xAACDFC` in lockstep, each `N -> N+1` twice), and the pinned A/B `runs/water/bench host/loop-px-a.out`.

## Decisions

1. **Pin the title's threads to one host core (this change).** `xbox_GuestThreadPin` at the three guest thread starts in `kernel_bridge.c` (guest-main in both thread modes, every bridge worker). The core is the lowest bit of the process mask, fixed, so a worker created from any core lands with the main thread; `=<n>` overrides it. One host preemption inside the window is as rare as a console quantum boundary was. This is the smallest change that gives the console's interleaving back, lands in the kernel for every title and every backend, and is testable standalone.
2. **Which threads stay off the core.** The kernel timer thread (DPCs, timer routines, the vblank) and the device models' threads (APU, OHCI, nv2a) deliver interrupts: on the console they ran between any two instructions of whatever thread was running, and the one-CPU gate already keeps them out of guest code at DISPATCH_LEVEL. Pinning them would put a DPC behind a main thread spinning in its frame wait, the latency class the m1hang work removed. The GPU, the audio mixer, the raster workers and the video pump are host services and keep their cores.
3. **Win32 semantics in the POSIX compat layer.** A new thread gets the process's mask, not its creator's (`thread_trampoline` applies the mask captured before any pin), and `GetProcessAffinityMask` reports that captured mask. Without this, on native Linux the timer thread created lazily from `KeSetTimer` by a pinned guest thread would inherit the guest core.
4. **macOS.** No thread affinity API. The pin returns failure, prints one line and leaves the threads alone. The race is live there; the Mac has not shown the symptom in the goldens, and a Mac A/B of the hub route (20 runs) is the follow-up measurement.
5. **A/B and visibility.** `RECOMP_GUEST_CPUS=all` is the switch; `[KERNEL] guest threads on one host core (cpu N)` prints once; `/proc/<pid>/task/*/status` `Cpus_allowed_list` under Proton shows which threads sit on the core.

## Alternative A: a guest-CPU token (BLX-31)

The portable form of the same guarantee: a token that a thread holds while it runs lifted code and drops at every kernel wait (`KeWaitFor*`, `NtWaitFor*`, `KeDelayExecutionThread`, the file and event waits, the vblank wait), at the lowered spin-wait yields, and on a quantum (released and retaken at the IRQ safe points when held longer than a quantum, so a busy thread cannot starve the others). Guest code then never runs on two threads at once, on every host including macOS, and the guarantee is deterministic rather than "as rare as a host tick". It is the console's scheduler in one lock. Its costs are the audit that every blocking path drops the token (a path that does not deadlocks the title), a lock pair around every bridge call, and the interaction with the one-CPU gate (a thread holding the token at DISPATCH_LEVEL also holds the gate; the ISR delivery on model threads needs the token or needs the gate to imply it). That is a spec of its own: filed as Plane BLX-31, with this change's pin as the fallback it replaces.

## Alternative B: a lock in the title (rejected)

A manual wrapper around `sub_00037CE0`/`sub_00037C50` with a host mutex makes the add atomic, but the pool is also reset in a dozen functions by a plain store, other titles have other globals, and the fix would live in cat for one symptom of a general host behaviour.

## Risks

- A title that depends on true parallelism for throughput: none does, the console had one CPU. A loader and an audio worker now share the core with a busy-waiting main thread; measured (tasks 3.x), with `=all` as the escape.
- Thread priorities: `KeSetBasePriorityThread` maps to host priorities that Proton does not enforce, so a worker that outranked main on the console gets a fair share here. Unchanged by this change.
- Burnout 3: more threads; a starved worker would show as a hang, not a pixel diff. One smoke before the merge.
