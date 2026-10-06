## ADDED Requirements

### Requirement: Each deviation is recorded with reason, risk and exit criterion
Every deliberate deviation from Xbox hardware or retail behaviour SHALL have one requirement in this capability. Each SHALL state what the port does, why, the risk, how to detect that it matters, and the exit criterion that retires it. A change that adds, alters or retires a deviation SHALL update this capability.

#### Scenario: New deviation
- **WHEN** a change makes the host behave differently from hardware on purpose
- **THEN** the same change adds a requirement here, and the code comment at the deviation names it

### Requirement: Devkit RAM (128 MB)
The host SHALL run with 128 MB guest RAM (`xbox_SetTotalRam(XBOX_DEVKIT_RAM)`, `main.c`) instead of the retail 64 MB.
- Reason: all 73 XBE sections are mapped at boot, including the 49 non-preload ones that XeLoadSection pages in and out on hardware. That paging is not modelled. At 64 MB the heap is about 14 MB, and the game fills it during its first archive loads. (`NtFreeVirtualMemory` used to leak every MEM_DECOMMIT; that bridge bug is fixed, `kernel-memory-and-files`.)
- Risk: memory-dependent bugs are masked or introduced: allocation-failure paths that never trigger, code that checks the RAM size, pointer layouts that differ from hardware.
- Exit: on-demand section loading through XeLoadSection exists, AND the title runs at 64 MB. (The third condition, `NtFreeVirtualMemory` freeing correctly, is met.)

#### Scenario: Suspected memory-size bug
- **WHEN** a bug looks memory-dependent (an allocation pattern, address wrap, a heap-top check)
- **THEN** it is retried at 64 MB first, and the result is recorded against this requirement

### Requirement: Vertical blank from the host timer
`main.c` SHALL set `RECOMP_VBLANK=1` unless the environment already sets it. Vector 3 fires from the toolkit's kernel timer on an absolute 1/60 s host schedule (`kernel-threads`), not phase-locked to the pacer or to the executor's flips.
- Reason: the main loop (`sub_0005F960`, spinning at `0x00060475`) waits for the frame counter at `0xAE7388`, which only the title's vblank callback (`sub_000604A0`) moves, from D3D's vblank DPC.
- Risk: judder, and A/V drift once audio exists (Sofdec uses audio as the master clock; xemu #1118).
- Exit: the GPU render backend's Present path (the D3D11 swap chain; Metal later) raises vblank from its own present, at the rate of the mode `AvSetDisplayMode` was given.

#### Scenario: Drift once audio exists
- **WHEN** a movie plays with audio and the ADX position drifts from the video frame index
- **THEN** this deviation and the pacer are the first suspects

### Requirement: BlockUntilVerticalBlank is a 60 Hz pacer
`sub_002E0DB0` (D3DDevice_BlockUntilVerticalBlank) SHALL be overridden in `src/recomp_manual.c` to sleep to the next 60 Hz boundary on a host monotonic clock, instead of waiting on the vblank KEVENT at device + 0x1DBC, whatever mode `AvSetDisplayMode` was given. The boundaries SHALL be shared by every caller (one epoch, vblank N at epoch + N periods), so each waiting thread wakes on every vblank as the KEVENT would wake it, not every other one.
- Reason: the original waits on an event that the ISR's DPC sets, and the function clears it with a plain store to SignalState that the host event shadowing it never sees (`src/recomp_manual.c`).
- Risk: a second 60 Hz clock, independent of the vblank timer; a fixed 60 Hz in 50 Hz or 30 Hz modes.
- Exit: retired together with "Vertical blank from the host timer", when vblank comes from a real present.

#### Scenario: Two clocks
- **WHEN** frame pacing shows judder with a period of a few seconds
- **THEN** the beat between the pacer and the vblank timer is checked before anything else

### Requirement: Fence mirror as fallback only
`main.c` SHALL keep `xbox_Nv2aMirrorFence(0x2F1FB8, 0x2C, 0x30)` registered. The mirror SHALL step aside once the executor releases onto the same word, and SHALL stay on otherwise.
- Reason: with the executor off, nothing consumes the pushbuffer, and the fence wait in `sub_002E8110` never ends. With it on, the mirror still unblocks D3D init before the first release.
- Risk: while the mirror is on, the fence says work is complete before anything has read it (the lost-command race).
- Exit: the executor is on by default (it is, since the env consolidation), and the handover line has been seen on both hosts for several consecutive runs.

#### Scenario: Handover not seen
- **WHEN** a run with the executor on never logs `fence word ... now written by the executor; mirror off`
- **THEN** the semaphore points somewhere other than `dma_resolve` expects, and that is investigated before trusting any frame

### Requirement: Lazy KEVENT shadowing
The kernel bridge SHALL give a guest KEVENT first seen by KeSetEvent, KeSetEventBoostPriority, KePulseEvent, KeResetEvent or KeWait* a host shadow, with type and initial state taken from its DISPATCHER_HEADER (toolkit `0e948f5`).
- Reason: D3D builds its vblank event (`0x002F3D7C`, .bss) inline, never through KeInitializeEvent, and the bridge used to hand a guest pointer to host `SetEvent`.
- Risk: an object that is not an event but has a plausible header would be shadowed as one.
- Exit: none planned. Keep it, and upstream it.

#### Scenario: Non-event object
- **WHEN** a wait on a lazily shadowed object behaves unlike an event (a mutant or semaphore pattern)
- **THEN** the shadow's type decision is checked against the guest header

### Requirement: Utility drive not mounted; Z: is a host cache directory
`main.c` SHALL clear the XBE init flag MOUNT_UTILITY_DRIVE on every host, and the path layer SHALL map `Z:` to `<save_dir>/Cache`.
- Reason: with the flag set, XAPI opens the raw disk `\Device\Harddisk0\partition0`, which the toolkit backs only on Windows and only with an image that does not ship. On POSIX the boot falls to the dashboard with XLD_ERROR_INVALID_HARD_DISK.
- Risk: the cache partition is not formatted, sized or dismounted as on hardware. xemu #858 (a crash while a movie loads) may involve cache-partition state.
- Detect: `NtCreateFile` failures under `Cache\` (12 `...ipk err=2` in run `20261001-214200`), or `IoDismountVolumeByName` (ordinal 91) being called.
- Exit: none planned. (Save games work through the UDATA/TDATA root and `RECOMP_SAVE_DIR`; `IoDismountVolumeByName` and `FscSetCacheSize` are bridged in the toolkit.)

#### Scenario: Cache write fails
- **WHEN** the game's writes under `Z:` fail or `IoDismountVolumeByName` is called
- **THEN** this deviation is reviewed first

### Requirement: Inferred register semantics
The ack tick SHALL set PGRAPH `0x400B10` bits 2..6 to `(completed fence << 2) & 0x7C`, and the executor SHALL treat the semaphore and surface DMA objects as covering physical memory from base 0.
- Reason: the Swap path's wait loop reads `0x400B10` against the fence, and the DMA objects resolve to the right words under base 0. Both are inferences from one title. The register's name and other bits are not confirmed.
- Risk: a title that reads `0x400B10` differently, or a DMA object with a non-zero base, writes to the wrong memory. `surface_hits_image` exists because the base-0 assumption once overwrote code.
- Detect: each assumption is logged on first use. A log line that contradicts it is a blocker, not noise.
- Exit: confirmed against a hardware reference (xemu's pgraph code or nv2a documentation), and the requirement rewritten as fact.

#### Scenario: Contradicting log line
- **WHEN** a run logs a DMA object with a non-zero base, or `surface_hits_image`
- **THEN** the run is treated as blocked until the assumption is fixed

### Requirement: POSIX span capped below the contiguous window
On POSIX the reservation for the base RAM view and its mirrors SHALL stop below `XBOX_CONTIG_BASE` (`0x80000000`), and a mirror that would overlap the contiguous window or the device apertures SHALL be skipped (toolkit `05718f8`, `819c96e`).
- Reason: at 128 MB, 28 mirrors cover the contiguous window, and mapping it fails (error 8).
- Risk: a guest access through a skipped high mirror faults instead of aliasing RAM.
- Detect: a fault at an address in a skipped mirror's range; the boot log names each skipped mirror.
- Exit: retired with devkit RAM (at 64 MB the mirrors fit below the window).

#### Scenario: Fault in a skipped mirror
- **WHEN** a crash report's fault address lies in a mirror the boot log says was skipped
- **THEN** the cause is this deviation, not the code at the fault
