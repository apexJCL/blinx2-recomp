# kernel-threads Specification

## Purpose
Defines how the kernel bridge represents guest threads and their handles, per-thread TLS, and the 60 Hz vertical-blank clock the title's frame loop depends on.

## Requirements

### Requirement: Thread handles lead to guest thread objects
Every thread that PsCreateSystemThread or PsCreateSystemThreadEx spawns SHALL have a zeroed guest object of at least 0x124 bytes, with Header.Type 6. ObReferenceObjectByHandle SHALL return that object for the thread's handle, and NtCurrentThread (-2) SHALL return the calling thread's object. When the thread ends, by PsTerminateSystemThread or by returning from its start routine, ExitStatus at +0x120 SHALL be written before SignalState at +4 is set to 1. KeWaitForSingleObject and KeWaitForMultipleObjects on the object, and NtWaitForSingleObject on the handle, SHALL be satisfied once the thread has ended. The object SHALL stay valid while a handle or a reference to it remains.

#### Scenario: Waiting for the stage loader
- **WHEN** BLiNX 2 polls GetExitCodeThread for its stage loader thread (start 0x0005E410) after the loader calls PsTerminateSystemThread
- **THEN** the poll reads the loader's exit status instead of STILL_ACTIVE, and the title goes on to the stage 1-1 attract demo

### Requirement: Vblank runs at 60 Hz
The kernel timer SHALL raise the NV2A vblank interrupt, while the title enables it in PCRTC_INTR_EN_0 (toolkit 3b552c5), on an absolute 1/60 s schedule that does not depend on the timer thread's sleep granularity. The schedule SHALL be computed in nanoseconds from one epoch (vblank N due at epoch + N × 10⁹/60 ns, in integer arithmetic, so it never drifts). The timer thread SHALL sleep with a high-resolution host sleep to the earliest of the next vblank, the next due kernel timer and a 10 ms cap, and SHALL ask the host for an on-time wake where the host offers one (on macOS a time-constraint scheduling policy; if the host refuses, it logs one line and runs as a normal thread). After a stall of more than 100 ms, the schedule SHALL restart rather than fire the missed vblanks in a burst. When a DPC drain stops because the one-CPU gate is busy and DPCs remain queued, the next pass SHALL come within 1 ms. The drain SHALL still never wait for the gate. `RECOMP_DEBUG=vblank_clock=ms` SHALL restore the millisecond schedule, the millisecond sleep and the 10 ms re-poll.

#### Scenario: Vblank rate
- **WHEN** BLiNX 2 runs with vblank enabled
- **THEN** each `[NV2A] vblank N: last 600 in T ms` line reports a T of about 10000

#### Scenario: Even vblank gaps
- **WHEN** BLiNX 2 runs `@stage1` on an otherwise idle Mac (Metal) or on the Linux/Proton host under Proton (D3D11)
- **THEN** over the run's `[NV2A] vblank` 600-vblank windows, the median gap spread (max − min) is at most 3 ms and at least 80% of the windows lie within 16.67 ± 1.5 ms at both ends, windows overlapping a stage load or a logged schedule restart excluded; and the 3D flip interval's p95 − p5 is at most half of the same route with `vblank_clock=ms`, with p50 within 33.3 ± 0.5 ms on both

#### Scenario: Schedule unit test
- **WHEN** the `vblank_schedule` ctest drives the schedule with synthetic times: steady 60 Hz, a late tick of 50 ms, a stall of 150 ms and an epoch near 2⁶² ns
- **THEN** due times stay on the epoch grid without drift, the late tick fires once and catches up on the grid, and the stall restarts the schedule without a burst

#### Scenario: Old loop on request
- **WHEN** a run sets `RECOMP_DEBUG=vblank_clock=ms`
- **THEN** the timer loop behaves as before this change (millisecond schedule, millisecond sleep, 10 ms cap after a gate-busy drain)

### Requirement: The vblank interrupt does not hold the timer thread
The kernel timer thread SHALL block between vblank ticks. The PCRTC and PMC vblank bits that the guest's DPC waits on SHALL be cleared by a thread that blocks until it is armed, not by a polling loop on the timer thread.

#### Scenario: Timer thread idles with the pushbuffer executor on
- **WHEN** BLiNX 2 runs with `RECOMP_PB_EXEC=1` and a sampler profiles the process
- **THEN** almost all kernel-timer samples are in Sleep, and none show the DPC's ack spin at `0x002EA590`

### Requirement: Handle tokens stay unique per open handle
NtDuplicateObject SHALL give the duplicate a token of its own, even when the host returns the same HANDLE, so closing either handle leaves the other valid. Allocating and releasing tokens SHALL be serialised, so a thread that starts before its creator has stored the thread's token cannot be given a token that a file handle already holds.

#### Scenario: Duplicate outlives the original
- **WHEN** a thread handle is duplicated with NtDuplicateObject and the original is closed with NtClose
- **THEN** ObReferenceObjectByHandle on the duplicate still returns the thread object

### Requirement: Each thread's TLS block is where its TLS index says
When PsCreateSystemThreadEx is called with a nonzero TlsDataSize, the new thread SHALL have a zeroed block of that size of its own. `[fs:[4] + i*4]`, where i = -(TlsDataSize/4), SHALL be the block's first dword, and `[[fs:[0x28]] + 0x28]` (KTHREAD.TlsData) SHALL point at that same dword. No two live threads SHALL share a block.

#### Scenario: Stage loader exits cleanly
- **WHEN** BLiNX 2 runs its cold attract sequence for 420 s, so that stage loaders #5 to #8 start and end
- **THEN** each loader's CRT exit path (sub_002D8294) frees its own per-thread data, and the process does not fault

### Requirement: Device interrupts never run alongside the one-CPU gate holder
A guest interrupt routine (vblank, APU, OHCI) SHALL NOT run on one host thread while another host thread holds the one-CPU gate (a thread at DISPATCH_LEVEL, a DPC or a KeSynchronizeExecution routine). When the gate is held, the interrupt SHALL be posted and run on the holder's thread at its next safe point: a kernel call, a spin-wait yield or the gate's release, taken before the gate is let go. It SHALL run on its own stack, at the device IRQL, with the holder's guest register state saved and restored, and SHALL NOT nest inside another posted routine. A post SHALL never be lost when the holder releases the gate while the post is made. Repeated posts of one vector before delivery SHALL coalesce. A holder that reaches no safe point within `irq_safe_ms` SHALL be logged with its thread and raise site, and the interrupt SHALL keep waiting unless `irq_safe_force` is set.

#### Scenario: Interrupt during a DPC
- **WHEN** the APU raises its interrupt while the timer thread is running the DSOUND DPC
- **THEN** the APU routine runs on the timer thread at the DPC's next kernel call or at the DPC's end, never in parallel with it

#### Scenario: Standalone test
- **WHEN** `tests/irq_safe_points` parks a gate holder half-way through a list edit while another thread posts an interrupt that edits the same list
- **THEN** the routine runs only inside the holder's next safe point call, on the holder's thread, and the same case with `irq_safe_points=0` records the routine running during the edit

#### Scenario: Results screen
- **WHEN** BLiNX 2 reaches the mission-1 results screen and the player continues
- **THEN** the game does not hang, and no wait log appears

#### Scenario: Vblank keeps its clock
- **WHEN** a guest thread holds the gate across several vblank ticks
- **THEN** the vblank counter advances for every tick, the ISR runs once at the holder's next safe point, and `last 600 in` stays at about 10000 ms

### Requirement: A DPC queued by an interrupt runs before guest code resumes below DISPATCH
A DPC queued by an interrupt routine SHALL run before a guest thread that raises to DISPATCH_LEVEL enters its critical region, and SHALL run at the release point of a guest thread that held the gate while the routine was queued, as on the console a DPC runs when the processor drops below DISPATCH before the interrupted thread resumes. It SHALL run on that guest thread, at DISPATCH_LEVEL, holding the one-CPU gate, with the thread's guest register state saved and restored, SHALL NOT run inside a posted interrupt routine, and SHALL NOT nest inside another drain. A device-model thread (APU frame thread, OHCI controller thread) SHALL NOT run a queued DPC. `KeInsertQueueDpc` SHALL wake the timer thread so a queue that no guest thread drains runs within a few milliseconds. `dpc_on_raise=0` SHALL restore the timer-thread-only drain.

#### Scenario: Stop list drained before Play
- **WHEN** the DSOUND interrupt appends an idle voice to the stopped-voice list and queues its DPC, and the title then calls Play on that voice
- **THEN** Play's raise to DISPATCH runs the DPC first, the voice is off the stopped list and the hardware list before Play re-links it, and the next idle trap for that handle inserts it once

#### Scenario: Standalone test
- **WHEN** `tests/dpc_order` delivers a gated interrupt on a model thread whose routine queues a DPC, and a guest thread then raises to DISPATCH
- **THEN** the DPC ran before the raise returned, on the guest thread, at DISPATCH, with the thread's registers unchanged; the same queue is not run by the model thread's release and is run by the lower of a guest holder that took the interrupt at a safe point; a queued DPC ends the timer thread's sleep within 2 ms; with `dpc_on_raise=0` the raise returns with the DPC still queued

#### Scenario: Bomb door, results screen, mission-3 boss
- **WHEN** the mission-1 door is opened with bombs, the mission-1 results screen is reached, or the mission-3 boss is defeated
- **THEN** the game does not hang, and no `[IRQ] wait` log appears, on Metal and on D3D11 under Proton

#### Scenario: Burnout 3 keeps its front-end pair
- **WHEN** Burnout 3 boots and reaches the vehicle select under Proton
- **THEN** no DPC runs on the APU frame thread, and the DSOUND DPC that waits on a trapped front-end method still completes

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

### Requirement: A title's threads share one CPU
The runtime SHALL run the main guest thread and every thread the title creates through `PsCreateSystemThreadEx` on one host core, the lowest the process may use, unless `RECOMP_GUEST_CPUS=all` (every core) or `=<n>` (that core) says otherwise. The kernel timer thread and the device models' threads SHALL keep their own cores. On a host without thread affinity the runtime SHALL say so once and leave the threads alone.

#### Scenario: Two guest threads add to one global pool
- **WHEN** the title's main thread and a worker both run `slot = count; fill entry; count = slot + 1` on a shared global without a lock
- **THEN** the two never run inside that window at the same time, as on the console's one CPU, and no entry is lost

#### Scenario: A host thread made by a pinned guest thread
- **WHEN** a pinned guest thread creates a host thread (the kernel timer thread from `KeSetTimer`)
- **THEN** that thread gets the process's CPU mask, not the guest core
