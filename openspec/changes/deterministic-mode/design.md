## Context

Guest-visible clocks before this change, each reading the host itself:

| door | where | host source |
|---|---|---|
| KeQueryPerformanceCounter/Frequency | `kernel_hal.c` | QPC / QPF |
| KeQuerySystemTime | `kernel_hal.c` | wall clock anchored once, QPC between |
| KeQueryInterruptTime, KeInterruptTime export | `kernel_hal.c`, `kernel_bridge.c` | GetTickCount64 x 10^4 |
| KeTickCount export | `kernel_bridge.c` init, ack loop in `xbox_memory_layout.c` (1 ms) | GetTickCount |
| KeSystemTime export, NtSetSystemTime | `kernel_bridge.c`, `kernel_hal.c` | GetSystemTimeAsFileTime |
| rdtsc (`xbox_ReadTimeStampCounter`, called from gen/) | `kernel_hal.c` | QPC scaled to 733 MHz |
| absolute wait and delay due times | `kernel_sync.c`, `kernel_thread.c` | GetSystemTimeAsFileTime |
| relative wait and delay timeouts | same | host ms (WaitFor*Ex, Sleep) |
| kernel timers (`g_timers`) | `kernel_bridge.c` | QPC ms (paced) or GetTickCount64 |
| vblank schedule | `kernel_bridge.c`, `kernel_pacing.c` | host ns, 60 Hz grid |
| BLiNX 2's BlockUntilVerticalBlank pacer | cat `recomp_manual.c` | host ns |

Doors this change leaves open (phases 2-3):

| door | where | host source |
|---|---|---|
| NV2A PTIMER | `nv2a_core.c:196` | `qemu_clock_get_ns` |
| APU sample clock | `apu_core.c` | `qemu_clock_get_ns`, host consumed samples |
| MCPX free-running counters | ack loop in `xbox_memory_layout.c` | the loop's own rate |
| KSYSTEM_TIME High2Time | `kernel_guest_time_publish` | not written; a reader can't detect a torn read |
| state hash coverage | `guest_state_hash.c` | not a snapshot (host threads write while it reads); RAM only |

Host-only uses (logs, the profiler, KeStallExecutionProcessor's busy-wait)
stay on the host clock. The walker's flip pacing moved to the virtual
clock in the mode (D23).

## Decisions

### D1. One file owns the guest clock; the refactor is its own commit

`guest_time.c` holds the real-mode bodies moved verbatim, and every door
above calls it. Proven a no-op by the PC D3D11 golden on that commit with
the mode off.

### D2. Virtual time is a vblank count

`vns = v * 10^9 / 60` with `v` the count; every clock derives from `vns`:
interrupt time `vns/100`, tick `vns/10^6`, performance counter
`vns/100` at 10 MHz, system time `2004-01-01 + vns/100`, TSC at 733 MHz.
The count steps once per emulated vblank, in the timer thread's schedule
pass, before the interrupt is raised, so the vblank DPC and every thread it
wakes read the new time. Never per flip: a 30 fps and a 60 fps title need
no setting. With vblank interrupts off the schedule still steps the clock
without raising one; the old tick mode is run on the 60 Hz grid.

Fixed epoch and frequency because a title can seed a generator from the
date or scale by the counter's frequency, and either would differ by host. The console's own counter runs at the ACPI rate, 3,375,000 Hz (56,250
counts per vblank); phase 2 may switch to it if a title assumes that rate.

### D3. Waits end on virtual time

A timed wait converts its timeout to a due time on the interrupt-time clock
(`xbox_GuestTimeDue`), then waits in 1 ms host slices on the object until
the object signals or the clock passes the due time. A delay does the same
with SleepEx. Kernel timers keep virtual ms and fire in the pass that steps
past them. A short sleep (1 ms) therefore lasts until the next vblank,
which is what makes it repeatable and can slow a title that sleeps in a
loop; acceptable for a debug mode.

The step itself is still host-timed (D2), and a wait's thread wakes up to
1 ms after it: phase 1 removes the clock as a difference, not the order of
events within a vblank (phases 2-3).

### D4. Exports follow the steps

In virtual mode the step writes KeTickCount, KeInterruptTime and
KeSystemTime, so no export is a host-timed write behind the others. The
1 ms ack loop writes KeTickCount only in real mode: in virtual mode it
could read the tick before a step and store it after, writing the export
backwards.

The step runs on the kernel timer thread, which real mode starts at the
first KeSetTimer. In virtual mode the kernel bridge starts it at init
(`xbox_GuestTimeSetStepper`), so a title that waits with no timer armed
still sees the clock move and its wait ends.

### D5. Busy-waits on a frozen clock

A title that spins on the counter with no kernel call holds its thread
until the next vblank; on the timer thread (a DPC) it would wait for a step
that thread must make. `vt_ns` counts same-vblank reads per thread and logs
once at 10^6, so such a stall has a name. KeStallExecutionProcessor stays
on the host clock.

### D6. The state hash point is the pad poll

The replay's input is timed by port-0 polls (`g<poll>`), so the hash is
taken at the end of each poll, on the polling thread, before the poll clock
moves: for BLiNX 2 that is its own XInputGetState on the guest thread
(`usb_gamepad_game_record`), a guest-synchronous point. The toolkit's
`usb_gamepad` gets a poll hook; the kernel's `guest_state_hash.c` installs
it when `state_hash` is set. The hash is a 4-lane multiply-xor over 64 KB
pages, combined per poll; the page file is delta-encoded so the first
differing poll can be narrowed to pages, and `state_dump` writes the whole
RAM at chosen polls to diff the bytes.

## Phase 2 decisions

### D7. The guest CPU is a token on a ring; time moves when the guest is idle

With `RECOMP_GUEST_LOCK` on, the mode replaces the host-timed vblank
schedule with `kernel_guest_det.c`. The guest threads form a ring in
ring-slot order. The creator takes the new thread's slot while it holds the
token, not the new host thread, so the order is the same on every run; it
is creation order until an ended thread's slot is reused (D18). The
holder keeps the CPU through every kernel call that does not block. A
wait, a delay, a zero-interval delay, a contended critical section or a
lowered spin-wait passes it on, and so does a back edge: after a quantum of
4096 edges, or at once when the same edge repeats (a poll loop). When every
runnable thread has passed it once without progress, the guest is idle:

1. the GPU catches up to PUT (one granted NV2A round; a 'C' event);
2. if it had nothing to do, the clock steps one vblank (an 'S' event): the
   timer thread runs its pass (vblank interrupt, DPCs, due timers), then the
   APU runs 25 frames (`XBOX_DET_APU_FRAMES_PER_VBLANK`, 1500 Hz / 60).

Every device thread runs only between a grant and its done, with all guest
threads parked, so no device writes guest memory at a host-timed moment.
It cannot deadlock on time: a thread waiting for a timeout or a vblank is
idle, and the step comes. Without the guest lock the vblanks stay on the
host schedule (phase 1 behaviour).

BLiNX 2's `sub_002E0DB0` waits in the ring for the next step
(`xbox_GuestDetWaitVblank`) instead of polling host ns.

### D8. The mode is decided at the first guest join

`xbox_GuestDetOn` needs the guest lock's state, known only once the title's
main thread joins. Without the `deterministic` key the mode is off from the
first question, so a stock run never sees the undecided state. With it,
until the first join (`xbox_GuestDetUndecided`) the APU frame thread and
the NV2A ack loop do no work and nap 1 ms: a frame or a pass begun then
could still be running when the join turns the mode on, ungranted, and a
pause branch asleep on its untimed wait would miss the first grant and
hang `device_round` with the token held. Once decided, the mode never
changes. Those loops ask `xbox_GuestDetUndecided` first and read
`xbox_GuestDetOn` only after it: read the other way round, a join between
the two reads left a pass with the mode on taking the stock path, the same
hang (the delta review).

### D9. Thread bookkeeping in guest memory is carved by the creator

A worker's TIB and TLS block came from `xbox_HeapAlloc` at the new host
thread's start. Two workers created in one window took each other's
address from one run to the next (the first RAM divergence of the det
trace, S2059: a TIB at 0x03ee9000 in one run, 0x03f69000 in the other),
and every pointer to them followed. In the mode the creator allocates the
TIB in `bridge_spawn_thread`, in creation order. When the host thread
cannot be created, the creator frees that TIB and marks the slot dead
(`xbox_GuestDetThreadDrop`); a slot left new would count as runnable and
the ring would hand it the token for good.

### D10. A loop spinning on the clock counts as idle

The proposal kept a thread spinning with no kernel call out of "idle". Two
kinds proved to need it. A loop polling a device bit ends its quanta at one
edge every time, which D7 already counts as idle. A loop waiting for a time
by reading the clock does not: clip2 hung at vblank 6137 in an XDK library
loop (sub_0033492A under sub_00332F38) that raises and lowers IRQL and reads
KeQuerySystemTime each turn, with inner loops of varying length, so its
quanta ended at a different edge each time, counted busy, and the clock
never moved. A quantum that read the clock 64 or more times without it
moving (`xbox_GuestTimeFrozenReads`) now gives the token up as idle at one
site. On the console that loop ends when real time passes; here it ends at
the next step, and the decision depends only on edges and reads, both guest
progress, so it stays repeatable.

### D11. Tracing the divergence

`det_trace=<path>` writes one line per hand-off (`P passes from to site`),
step (`S n vblank ram_hash`) and catch-up (`C ...`), and per event the hash
of every 64 KB page (`<path>.pages`). `det_dump=S<n>,...` writes the guest
RAM at those events. Two runs diffed name the first event they part at,
the pages and the bytes (runs/deterministic-mode/p2/tools).
A divergence that moves between runs slips between named dumps, so
`det_snap=<from>-<to>:<va>[:...]` writes a few 64 KB pages (guest RAM or
the NV2A registers, which are plain memory outside the RAM hash) after
every event of a vblank window; the first differing record names the
hand-off whose quantum wrote it. In that window each `P` line also
carries the whole RAM's hash and each kernel call adds `K slot ordinal
caller eax`: when RAM agrees at a hand-off and the next quantum differs,
the difference came from outside RAM, and the call lines show which call
(and what it returned) it came through.

### D12. Host volume sizes are fixed in the mode

FileFsSizeInformation reported the host disk's free space. BLiNX 2 keeps
its free clusters >> 14 in a global (0x006580A4, set from sub_001B7AA0)
and leaves the converted double on the main stack, so stage1 runs t12 and
t13 parted at S2542 there and nowhere else: the host disk had changed by
about 640 MB between them. In the mode both backends report the fallback
geometry (1048576 clusters, half free). The RAM cache already answers from
its own bookkeeping, which is guest progress.

### D13. File times are fixed in the mode

On the PC, stage1 runs p1 and p2 parted at S1, the first step: one
FILETIME on the main stack (0x038BFD04) held the wall clock of each run's
start, to the microsecond. The bench creates a fresh HDD tree per run, so
every file and directory the boot queries carries its own creation time.
In the mode every file time the guest reads (basic, network-open and full
attributes, directory entries, on both backends and in the RAM cache) is
2004-01-01, the virtual clock's epoch. A title that sorts saves by date
sees them equal; the mode is a test mode.

### D14. Input scripts run on the virtual clock

With the scheduler and the host-state pins in, Mac stage1 pairs still
parted, at a different event each time (C43, C213, C48) but always in the
same two pages. `det_snap` over vblanks 2600-2700 named the quantum: the
main thread's, between a GPU catch-up and its next KickOff spin, writing
0x10 at 0x00ADC7B0. A watch there showed it is player 0's pad (START): the
script's "tap START" and "every 3" count host seconds (`now_s` in
`src/pad_input.c`), so a tap reached the pad state at vblank 2610 in one
run and a vblank later in the next. On the virtual clock (the mode, or
phase 1's virtual time) a script's seconds are guest seconds,
`KeQueryInterruptTime`'s. The host-time path is unchanged when the clock
is off.

### D15. A thread's end is published before it leaves the ring

With D14 in, Mac stage1 still parted in about half the runs (t28; then 3
of 6), always at the same hand-off during the stg0101 load: RAM was equal
at the pass before, yet the main thread's next quantum yielded in one run
and went on in the other. The pass hash and the `K` lines (D11) named the
input: the main thread polls a loader thread's end with
ObReferenceObjectByHandle, reads the thread object, and yields
(GetExitCodeThread); in the run that went on, the poll saw the end and
called NtClose. The ending thread parted from the ring first (at
PsTerminateSystemThread's release, or before its stack and object were
handled on a returning routine) and only then wrote ExitStatus and
SignalState, on host time, so the poller saw the end at whichever pass the
host got there. In the mode the ending thread keeps the token through
ordinal 258, frees its stack, signals its object, and parts after. With
the mode off the order is unchanged.

Waits on a thread had the same race (the review): KeWait and
NtWait on a thread object or handle tested the host thread handle, which
the host signals when the host thread ends, after the guest thread parted.
In the mode each thread object has a manual-reset event that the end sets
with SignalState, under the token, and those waits test it. `thobj_alloc`
creates that event only when the mode is on, so an object allocated before
the decision would have none. None is: the main thread's object comes from
`thobj_current` on its first kernel call, which follows its join at bridge
init (where the mode is decided), and workers' objects are allocated at
spawn, from guest code.

### D16. What an exact golden needs (CLI follow-up)

Phase 2 makes one host replay itself: the per-poll RAM hash log of a
scripted run is the same run after run (5.8). A golden that compares those
logs exactly, instead of frames within a tolerance, needs:

- A guest-defined end. A run that quits on host time
  (`RECOMP_WINDOW_QUIT_AFTER`) stops at a different poll each time, so two
  runs agree only over their common prefix. clip2 ends on the script's
  last step (`pad_quit`), which is a fixed poll and gives full logs that
  match line for line; stage1 and the other golden scripts need the same
  (quit on the script's end or on a vblank count).
- A reference per host OS. The Mac and the PC part at the first steps
  (RAM hash at poll 0, one page at `S25`), so a reference recorded on one
  host does not hold on the other until that cause is found.
- `state_hash` without `det_trace`. The trace hashes all of RAM at every
  step and catch-up (about 5 fps on the Mac); the per-poll hash alone runs
  near full speed and is what the golden compares. `det_trace`, `det_snap`
  and the `K` lines stay for finding a divergence.
- The compare in the CLI: `golden` runs the scenario with
  `deterministic` and `state_hash`, then compares the log (minus
  `#` lines) with the stored one and names the first poll that differs.

### D17. Where phase 2 stands (measured 2026-11-02)

Per-poll RAM hash logs (`state_hash`), mode on. Before the review fixes:
Mac build with every fix through D15, PC exe 41a97f0ad3c6. After them
(D8, D15's thread waits, D18): toolkit 643691a4, cat rebased on main, PC
exe 86f59833a96f (runs/deterministic-mode/p2):

| scenario | host | build | runs | result |
|---|---|---|---|---|
| stage1 | Mac | before | 6 | identical over the common prefix |
| stage1 | PC | before | 5 | identical over the common prefix |
| clip2 + `det_trace` | Mac | before | 5 | identical to step 1031 of 1735 (time limit) |
| clip2 + `det_trace` | PC | before | 5 | identical over 47k events (time limit) |
| clip2 | PC | before | 5 | identical, full clip (4073 polls) |
| clip2 | Mac | before | 5 | 4 identical, full clip; mf1 parts at poll 3982 |
| clip2 | Mac | after | 5 | identical, full clip, equal to the 4 above |
| clip2 | PC | after | 5 | identical, full clip, equal to the PC runs before |
| stage1 | PC | after | 5 | identical over the common prefix (2619 polls) |

In the odd Mac run before the fixes, RAM was equal at poll 3981 and the
next poll came one vblank early (30880 against 30881): one step more or
fewer fell between two polls with RAM agreeing, so the input came from
outside RAM, as in D15. The review named a candidate, waits on a thread
that ended on the host thread's handle (D15, second part). With that fix
in, 5 of 5 Mac runs match; that is fewer runs than it took to see the
split once, so it is a likely cause, not a proven one. If the split comes
back, the other candidate is the order in which async I/O and APC
completions land (left to the tracker item). The Mac and the PC still differ from
the first poll (D16).

### D18. Ring housekeeping (the review)

- Slots of ended threads are reused, lowest first. Threads end at fixed
  points of the ring now (D15), so the slot a new thread takes is the same
  on every run; never reusing them held a run to 256 thread creations, and
  BLiNX 2 starts loader threads on every stage load. The slot that holds
  the turn is never reused: a parting thread's slot is dead but keeps the
  turn while it steps with the lock dropped (below), and a thread given it
  would find the turn its own at its join.
- A thread that leaves while every other one is suspended steps the clock
  until one is resumed (what resumes it, a DPC or a timer, runs only on a
  step), and a resume with the ring empty hands the resumed thread the
  token. Before, the turn went to -1 and nothing stepped. The steps stop
  after 3600 (a minute of guest time) with a `[DET]` stall report and the
  turn left empty, so a resume that never comes cannot hold the parting
  thread for good.
- A timed wait due under 1 ms ahead (an absolute timeout rounds to 0 ms)
  is a ring wait. It fell into the host's 1 ms polling with the token held
  and the clock frozen, and hung.

## Phase 3 decisions

### D19. Pad record and replay already live in the toolkit

The tracker item asked to move pad record and replay out of BLiNX 2 into the
toolkit, so every game gets them. That move was done by the tracker item and
The tracker item: the script grammar, the recorder and the anchors are
`src/usb/pad_script.{c,h}`, and `src/usb/usb_gamepad.c` reads
`RECOMP_PAD_SCRIPT`, `pad_record`, `pad_clock`, `pad_anchor`, `pad_quit`
and `PAD_PRESS` for every game. A game reaches them in one of two ways:

- **The USB path.** The title's own XAPI drives the OHCI controller
  (`RECOMP_USB=1`; BLiNX 1, KUF, Burnout 3). Each report the controller
  builds goes through `usb_gamepad_report`, which records it and applies
  the script, and port 0's report is the poll the `g` clock counts.
- **The game tap.** A title that reads its pads through an XInput
  override (BLiNX 2's `src/pad_input.c`) calls `usb_gamepad_game_pads`
  once per XInputGetState and `usb_gamepad_game_press` and
  `usb_gamepad_game_record` for each pad. That is three calls with no
  logic of the game's own, so the game-specific hook stays this small.

So the files and the keys need no move, and the old ones still work:
the flip clock (`f`, clip and clip2) and the poll clock (`g`, clip3),
the anchors, the comment lines and `@end`. Phase 3 instead covers what the
second path lacked in the mode.

The file format, for reference: one entry a line (or a comma list in
the key); `#` starts a comment line; an entry is
`<clock><count>:<buttons>[:<hold>]`. The clock is `f` (executor flips),
`g` (port-0 polls) or none (host or virtual milliseconds), one clock a
file, set by its first timed entry. The buttons are names joined by `+`,
a `p2-` prefix for pad 2, sticks at a value (`lx=-12000`), and an analog
button's depth (`lt=97`). `<clock><count>:@open:<name>` is an anchor and
`<clock><count>:@end` is the record's end. The recorder writes a step
when it ends, so stick steps can be out of order; the parser sorts
nothing and ties each step to the last anchor at or before its start.

### D20. The USB controller is a granted device

In the mode, the OHCI thread ran on the host's 4 ms tick. So a USB
title's pad reports, the frame counter and the interrupt that wakes its
XAPI landed at host-timed points of the guest's frame, and a poll-clock
record counted host time. Now the controller is a scheduler device
(`XBOX_DET_DEV_OHCI`), the same as the timer and the APU (D7). It gets
one pass per vblank step, after the timer's round (the vblank interrupt
and the new time) and before the APU frames, with every guest thread
parked. Its `HcFmNumber` advances by the virtual milliseconds since the
last pass (16 or 17), not by the 4 ms tick. Until the mode is decided
the thread naps (D8). Once the mode is decided off, it keeps the host
tick, unchanged. BLiNX 2 does not start the controller, so its runs are
unchanged.

The frame clock's origin is read in the first granted pass, not when the
mode is decided. The nap can end on either side of the first vblank
step, and an origin one vblank early shifts every later frame number by
one between runs. While the controller is not Operational, each pass
moves the origin to the current virtual time, so no frames go by. Real
OHCI counts frames only while Operational. Without this, the first
Operational pass would add every millisecond since the mode was decided,
which on a slow boot is more than the 16-bit frame number holds. Passes
with MIE clear still count frames: the controller runs, it only does not
interrupt.

Some limits in the thread count passes, so in the mode they are counted
in vblanks, about 4 times as long. They stay as they are. These are their
values in virtual time:

| Limit | Passes | Host tick (4 ms) | Mode (one vblank) |
|---|---|---|---|
| IRQ hold-off at DISPATCH_LEVEL (`OHCI_IRQ_HOLDOFF`) | 500 | 2 s | about 8.3 s |
| Wait for Operational before the thread gives up | 1500 | 6 s | about 25 s |
| Settle before the next pad arrives | 50 | 200 ms | about 830 ms |
| StartOfFrame interrupts | 1 a pass | every 4 ms | once a vblank |

### D21. Millisecond scripts and PAD_PRESS on the virtual clock

`usb_gamepad.c` timed millisecond scripts (`8000:start`) and `PAD_PRESS`
by `GetTickCount`. D14 made BLiNX 2's own scripts count guest seconds.
In the mode the toolkit's do the same: `pad_ms()` reads
`xbox_GuestTimeMs` when the virtual clock is on, and the host tick count
otherwise. A script's start is a flag, not a zero time, because the
virtual clock reads 0 at its first step. Flip and poll scripts were
already on guest counts.

### D22. What phase 3 measured (2026-11-02)

Toolkit 42d7676f, outputs in `runs/deterministic-mode/p3/`:

- BLiNX 2, Mac, mode on: clip2 replayed 5 times through the toolkit
  path. The per-poll hash logs are identical (4073 polls each) and equal
  to phase 2's (`p2-fix2`). The old pads (clip, clip2, clip3) parse
  unchanged, and the `pad_script` ctest checks them when given as
  arguments.
- BLiNX 1, Mac, mode on (`RECOMP_GUEST_LOCK=1`): a 10-step scripted
  session recorded on the poll clock, then replayed twice from the
  record. Each replay re-records the same 10 steps at the same polls.
  The hash logs of the record and both replays are equal over their
  common prefix, past the record's `@end` at poll 10040. They end 2 to 5
  polls apart, because `pad_quit` posts the quit to the window and the
  title polls on until it closes. A guest-defined end (D16) would fix
  that.

### D23. The flip hold, pacing and device-thread TIBs in the mode

Found while porting the mode to Burnout 3 (toolkit fork branch
`fix/det-flip-hold`):

- **The flip hold reads the virtual clock.** It read the host vblank
  count and host nanoseconds, so a held flip was released at a different
  point of guest progress on every run, and runs with the same input
  drifted apart at the first held flip. In the mode
  `nv2a_pb_exec_flip_vblanks()` returns the virtual vblank count, and the
  hold's nanosecond reads (PUT read, flip poll, cancel, stall) use the
  virtual clock. So do the frame counter bump, `frame_counters_tick` and
  its flip stamp (`xbox_GuestTickCount`, which counts the first vblank's
  0 as 1, since 0 means "never"), and the event kick wake's vblank count.
- **Flip pacing is on by default in the mode.** The mode steps the clock
  only when no GPU work is left, so a title that flips without waiting
  for a vblank (a loading screen) keeps the GPU busy and stops its own
  clock; the hold is what lets a vblank in. `RECOMP_FLIP_PACING` unset
  means on in the mode (`xbox_FlipPacingMode`); `0` and `edge` still
  apply. Off the mode the default stays off.
- **Device threads take their TIB at the first grant.** The timer and
  OHCI threads allocated their guest TIB (and the timer its worker stack
  slice) at thread start, racing the main thread's first heap
  allocations, so the TIB's place in the heap, and every allocation
  after it, could move between runs. In the mode both take them in their
  first granted pass, when every guest thread is idle. Off the mode they
  are taken at thread start as before.

With these, BLiNX 2's clip2 replay stays identical over 5 Mac runs and
BLiNX 1's record and replays match. The hashes differ from D22's from
the first poll, because the TIBs now sit elsewhere in the heap.

## Risks

- A DPC that busy-waits on the clock on the timer thread hangs the mode
  (D5 names it).
- The hash reads RAM without the guest lock while host threads (loader,
  audio, GPU) may write it, so two equal runs can still differ in a page;
  phase 3 runs it under the lock and skips host-written ranges.
- Hashing all of guest RAM per poll takes a few ms on the guest thread and changes
  timing: compare runs that both hash.
