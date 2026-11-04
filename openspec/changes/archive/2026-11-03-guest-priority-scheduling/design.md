## Context

With `RECOMP_GUEST_LOCK=1` (`src/kernel/kernel_guest_cpu.c` in the toolkit)
one host thread at a time runs guest code. The lock hands the guest CPU over
in ticket order: at the quantum (4 ms, the back-edge preempt flag
`g_xbox_guest_cpu_preempt`), at spin-wait passes, at `NtYieldExecution`, and
for the length of each kernel call (the soft release). That keeps the
console's single CPU but not its scheduler. Priorities live only in host
thread priorities (toolkit b7e82411), which the lock overrides, and the
priority query returns 0 under the lock. CRI ADX's priority lock (JSRF
`sub_0013B0A0`/`sub_0013B0E0`, BLiNX 2 `sub_002ACBA0`/`sub_002ACBB0`)
depends on running at 15 with nothing else able to run.

## Decisions

**D1. Opt-in, debug tier.** `RECOMP_DEBUG=guest_sched=1` (row `GUEST_SCHED`
in `recomp_env.h`). It takes effect only with the guest CPU lock on and
`guest_priority` not 0; the lock's start-up line then ends with ", by guest
priority (guest_sched)". Off, the runtime behaves as before: the sched branches sit on a
static flag read once, and the few hooks that run anyway (record binding in
`thobj_alloc`, a wait's 0-timeout poll before it blocks) change no result.
The flag is resolved lazily at the first lookup, after the game's defaults
and `main.c`'s `RENV_GUEST_LOCK` are set and before any thread object
exists (checked in review). One line is not gated by the key: with the
lock on, a `[GUEST]` line marks each new longest wait for the guest CPU from
50 ms, key on or off, so the two can be compared.

**D2. Stored priority.** A table of 64 records `{thread object, increment,
suspend count}` beside the lock, found by the guest thread object
(`thobj_alloc` creates or resets one, freeing the object drops it; the main
thread and each bridge thread bind theirs before they join the guest CPU).
`KeSetBasePriorityThread` stores the increment normalised as NT does:
+16 and above saturate to time critical, -16 and below to idle, others clamp
to ±7. The level is 15, 1 or 8 + increment. `KeQueryBasePriorityThread`
returns the stored increment. Host thread priorities are not touched while
the feature is on.

**D3. Waiter order.** Waiters are a linked list of records on their own
stacks. The next holder is the waiter with the highest level, then the
lowest ticket, skipping suspended threads. Equal levels therefore keep the
current FIFO and round robin.

**D4. The holder keeps the CPU while it outranks every waiter.** A preempt
request is raised when the best waiter's level is above the holder's, or at
the quantum when levels are equal. A waiter back from a block or a kernel
call (a barger) counts one level higher, capped at 15: the +1 wake boost NT
gives a thread whose wait ended. So a barger equal to the holder preempts
at once, and one a level below waits like any lower waiter. At a
back edge, spin pass or yield the holder checks again under the lock: it
gives way only if it is suspended or the best waiter's level is at least its
own; otherwise it clears the flag and the refusal is counted (`refused` in
the stats and the pacing report).

**D5. Soft release.** A kernel call releases the guest CPU as today, but in
sched mode records the caller's thread and level, whether the call may block,
and the time. A waiter below that level may take the CPU at once when the
call blocks, after 2 ms otherwise, or at once when the release came from a
spin pass or is a host-kind release. File I/O blocks at once.
`KeDelayExecutionThread` (99) is short: a zero interval is a yield (a
switch only to a thread at the caller's level or above, as on the console),
and a real delay marks the caller blocked from the bridge. Waits (ordinals
158, 159, 233, 234, 235) and a contended critical section do not block at
once: their bridge first polls with a 0 timeout and only then marks the
caller blocked (`xbox_GuestCpuBlocked`), since a wait on a signalled object
returns on the console without a switch. Ordinals 223 and 230 are listed
as waits but are stubs that return at once.
`NtSuspendThread` (231) of another thread is only counted, so it is short;
a self-suspend marks the caller blocked. An admission past 2 ms is counted
per caller level in the pacing report and named in a `[GUEST]` line when the
caller is at 15, where it breaks the ADX lock.
`NtYieldExecution` (238) is a hand-off check of its own (D4). Short calls by a time-critical thread thus no longer
let lower threads in, which is the ADX lock's whole point.

**D6. Guest-side suspend.** `NtSuspendThread`, `NtResumeThread`,
`KeSuspendThread` and `KeResumeThread` on another guest thread count in the
record and return the previous count; the host thread is not suspended. A
suspended waiter is skipped; a suspended holder gives the CPU up at its next
back edge (the preempt check runs even with no waiters). Self-suspend marks the caller blocked, then takes
the existing path. A handle that is not a guest thread takes the existing
path; a resume of one is logged once, since the host then resumes a thread
the guest count never saw.
`PsCreateSystemThreadEx`'s CreateSuspended argument (arg 7) starts the
count at 1 in sched mode; off, it is still ignored as before. JSRF's spinner
`sub_0013B180` needs this: it is created suspended at +2 and loops on a
back edge with no kernel call.

**D7. A hang guard, and closing the model gaps.** A thread that spins at
a high level starves lower ones, as on the console, but the runtime spins
where the console blocked (spin pacing's frame wait, waits the bridges poll),
so some starvation here is a model gap and not the game's. A `[GUEST]` line
reports any wait over 1 s (rate limited, with the holder's last site), a
line marks each new longest wait from 50 ms, and a waiter kept off 4 s gets
one turn of max(quantum, 4 ms) (the valve), with a loud line and a count in
the report. The turn is reserved: once the valve picks a waiter, the fast
path will not hand the CPU to anyone else, and the waiter keeps the preempt
request up until it runs, so it gets the CPU at the holder's first hand-off
(fixed in re-review; before that, a returning holder could win the race).
The valve only stops a hang. It does fire today: 2, 2 and 10 times in the
Mac key-on goldens (attract, stage1, story; tasks 3.5), all from the gaps
below, and none on the Deck (tasks 3.6).

The gaps are closed by a task (tasks 4.1), not by the valve:
(a) no general spin-as-yield: a guest busy-wait keeps the CPU at its level
as on the console; (b) pacing parity: a lowered spin site (the frame wait) is a busy-wait on
the console, so under `guest_sched` a pass there admits only waiters at the
spinner's level or above, even while it sleeps on the host; today a sleep
pass is a blocking release, so `present.pacing` changes which threads run;
(c) measure the gap, then model its cause: log main's blocked time per frame
with the ordinal and caller, and disassemble the waits in D3D's Swap and
KickOff (`sub_002E6FE0` and callees). If the console blocks there every
frame, those waits block here too (or the matching host pacing wait counts
as a blocking release); if not, the starvation is faithful and only the
listen with sound decides. Known facts: the frame loop (`0x00060475`) waits on a
counter the vblank DPC bumps and spins on the console too; there a DPC
readies no level-6 thread above 8, so the spin itself is faithful. The ADX
worker runs only while main blocks; on hardware main very likely blocks in
D3D each frame on GPU-signalled events, while here the GPU thread runs ahead
and those waits find their objects signalled. Under spin pacing BLiNX 2
gives 5-9 blocking releases a second where a 60 Hz loop would give 60 or
more, and the level-6 worker waits over 1 s; under sleep pacing no wait
passes 1 s.

## Risks

- The feature changes timing for every thread when on. Goldens with the key
  on and off show whether BLiNX 2 is affected; Proton and native Windows
  are not covered by the Mac runs.
- CreateSuspended is honoured only in sched mode, so turning the key on
  changes start-up order for titles that create suspended threads.
- Windows host suspend of other guest threads is no longer used in sched
  mode; a thread outside the guest CPU (none known) would not stop. Windows
  thus changes more than POSIX, which never suspended, so native Windows
  runs are a gate (tasks 4.3 and 4.4).
- Livelock: a high-level thread that polls a lower one's work without
  blocking (a busy-wait on a flag the lower thread sets) never lets it run.
  The console has the same rule, so a game that does it relied on a block
  the runtime lost (D7's gaps); the valve turns that hang into a 4 s stall
  with a `[GUEST] valve` line naming both threads. This holds only with the
  re-review fix that reserves the valve's turn (D7); before it a spinning
  holder could take the CPU back at every hand-off.
- Lazy init: the flag is read at the first lookup, after the defaults and
  `main.c` set the lock (D1); a thread object made before that would have no
  record. Checked: the first `thobj_alloc` comes from the bridges, later.

- Starvation is real with the key on. BLiNX 2: CRI ADX's level-6 worker
  waits over 1 s at a time (3 times in the 25 s attract) behind the level-8
  main thread, whose frame wait is a guest busy-wait (`0x00060475`, the
  frame-counter loop) under spin pacing: about 22000 turns and 5-9
  blocking releases a second, none of which reach it. Under sleep pacing
  that loop releases the CPU and no such line appears. The console's loop
  spins too, so this may be faithful, but it needs a listen with sound
  (Proton, Windows) before any default. JSRF: its level-1 threads wait
  over 1 s often, as idle threads do, and once a level-10 thread waited
  1.3 s behind a level-15 holder.

## Verification

- `tests/guest_sched`: the switch and store, highest first with FIFO among
  equals, a time-critical lock/unlock, a higher waiter preempting, the soft
  release (short, past 2 ms, blocking) and suspended threads (skipped
  waiter, resume, suspended holder). Run 30 times in a row and in parallel
  without a failure.
- `tests/guest_sched_bridge`: a suspended spawn does not run until
  `NtResumeThread`, which returns the previous count.
- POSIX ctests 0 FAIL.
- BLiNX 2 Metal goldens with the lock on, key off and on. Phase 1 ran on
  toolkit 7fd07f0d (scheduler) and c1aacf58 (starvation line); the review
  fixes on cf14a796, rebased on posix-host/portability da8f65d8.
- JSRF on Metal reaches attract with the lock and key on.
- Before any default change: the gates in tasks §4 (a)-(f).
