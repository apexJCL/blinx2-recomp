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
The kernel timer SHALL raise the NV2A vblank interrupt, while the title enables it in PCRTC_INTR_EN_0 (toolkit 3b552c5), on an absolute 1/60 s schedule that does not depend on the timer thread's sleep granularity. After a stall of more than 100 ms, the schedule SHALL restart rather than fire the missed vblanks in a burst.

#### Scenario: Vblank rate
- **WHEN** BLiNX 2 runs with vblank enabled
- **THEN** each `[NV2A] vblank N: last 600 in T ms` line reports a T of about 10000

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
