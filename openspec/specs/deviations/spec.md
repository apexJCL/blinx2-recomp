# deviations Specification

## Purpose
The register of deliberate deviations from Xbox hardware or retail behaviour. Each entry states what the port does instead, why, the risk, how to detect that it matters, and the exit criterion that would retire it, so that a tripwire log line is recognised as one.

## Requirements

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
- Risk: judder, and A/V drift: audio is on by default and Sofdec uses it as the master clock (xemu #1118).
- Exit: the D3D11 swap chain or the Metal presenter raises vblank from its own present, at the rate of the mode `AvSetDisplayMode` was given. Both backends are merged; neither does this yet.

#### Scenario: Audio and video drift
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
- Reason: the executor is on by default, but the mirror stays registered for two cases. Before the executor's first release, it is what lets D3D init's fence wait in `sub_002E8110` end. With `RECOMP_PB_EXEC=0`, still a supported switch, nothing consumes the pushbuffer, and the mirror is the only thing that ends that wait.
- Risk: while the mirror is on, the fence says work is complete before anything has read it (the lost-command race).
- Exit: `RECOMP_PB_EXEC=0` is dropped as a supported configuration, and a run with the executor on shows no mirror write before the first release (the executor alone ends every fence wait from boot). Then the registration is removed from `main.c`.

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
- Detect: `NtCreateFile` failures under `Cache\` (12 `...ipk err=2` in run `20261001-214200`; those came from the rename bug that `kernel-file-io` fixed, so a recurrence is a regression), or `IoDismountVolumeByName` (ordinal 91) being called.
- Exit: none planned. (Save games work through the UDATA/TDATA root and `RECOMP_SAVE_DIR`; `IoDismountVolumeByName` and `FscSetCacheSize` are bridged in the toolkit.)

#### Scenario: Cache write fails
- **WHEN** the game's writes under `Z:` fail or `IoDismountVolumeByName` is called
- **THEN** this deviation is reviewed first

### Requirement: Inferred register semantics
The ack tick SHALL set the five-bit fence field of PGRAPH `0x400B10` to the low five bits of the completed fence, where the completed fence is the first registered fence mirror's completed word, or, when no mirror is registered and the executor has released at least once, the executor's last released semaphore value. The field's shift SHALL be learned from adjacent pairs of a subchannel-nonzero method `0x0310` and `BACK_END_WRITE_SEMAPHORE_RELEASE` (the only shift in 0..7 at which the `0x0310` word holds the released value's low five bits): the first such pair sets it, and a different shift SHALL replace it only after three such pairs in a row. A release a stopped walk salvages SHALL NOT pair with a word before the stop. Until a pair has been learned the shift SHALL be 2 (bits 2..6). The register's other bits SHALL be left as they are, except that the previous field's bits SHALL be cleared when the shift moves.
- Reason: XDK D3D's wait-for-idle spins until the register's fence field equals the low five bits of its fence word, which reads as "the GPU's own copy of the last semaphore value has reached memory". D3D writes that copy itself, as the `0x0310` word it puts right before each release, and the field's place differs by XDK: bits 2..6 in 5849 (BLiNX 2, Burnout 3, Spartan, KUF), bits 0..4 in 5558 (BLiNX 1, SSX 3; change `blinx1-pgraph-fence`). JSRF's older D3D fences with the release alone and never reads the register. The fence word and the executor's last release are the same value from two sides once the executor writes the fence (change `spartan-semaphore-ctxdma`); a title that registers no mirror has only the executor's side. The register's name and the rest of the word (the pushbuffer position) are not modelled.
- Risk: a title that reads `0x400B10` differently, whose fences are not built as that pair, or whose fence word and semaphore object differ (the mirror's "NOT the semaphore target" case), waits on a value that is not its fence.
- Detect: the register's source is logged once (`NV2A fence mirror: ...` for a mirror, `NV2A PGRAPH fence: no fence mirror registered` for the executor), and the learned field once per change (`[GPU] fence field in PGRAPH 0x400B10 at bits a..b`). A wait-for-idle that spins with these lines present is a blocker, not noise.
- Exit: confirmed against a hardware reference (xemu's pgraph code or nv2a documentation), and the requirement rewritten as fact: the register latches the `0x0310` word.

#### Scenario: Contradicting log line
- **WHEN** a run logs a semaphore object whose base differs from the mirrored fence word (`NOT the semaphore target; mirror stays on`), or `surface_hits_image`
- **THEN** the run is treated as blocked until the assumption is fixed

#### Scenario: Register source
- **WHEN** a title boots with the executor on
- **THEN** exactly one of the two source lines appears before D3D's first wait-for-idle, and which one says whether the title registered a mirror

#### Scenario: XDK 5558 field
- **WHEN** a title's D3D writes `0x0310` with `(pb << 5) | (fence & 0x1F)` right before releasing `fence`
- **THEN** the executor logs `bits 0..4` and the tick writes the fence's low five bits there, so `((reg ^ fence) & 0x1F) == 0` holds once the fence completes

#### Scenario: XDK 5849 unchanged
- **WHEN** a title's D3D writes `0x0310` with `((pb << 3 | fence & 0x1F) << 2) | x` right before releasing `fence`
- **THEN** the field stays at bits 2..6, as before this change, and a pair that fits at two shifts changes nothing

#### Scenario: Stray pair
- **WHEN** the shift is set and one pair fits a different shift
- **THEN** the shift does not move, and the field stays where the title's wait reads it

### Requirement: POSIX span capped below the contiguous window
On POSIX the reservation for the base RAM view and its mirrors SHALL stop below `XBOX_CONTIG_BASE` (`0x80000000`), and a mirror that would overlap the contiguous window or the device apertures SHALL be skipped (toolkit `05718f8`, `819c96e`).
- Reason: at 128 MB, 28 mirrors cover the contiguous window, and mapping it fails (error 8).
- Risk: a guest access through a skipped high mirror faults instead of aliasing RAM.
- Detect: a fault at an address in a skipped mirror's range; the boot log names each skipped mirror.
- Exit: retired with devkit RAM (at 64 MB the mirrors fit below the window).

#### Scenario: Fault in a skipped mirror
- **WHEN** a crash report's fault address lies in a mirror the boot log says was skipped
- **THEN** the cause is this deviation, not the code at the fault

### Requirement: Keyboard and mouse as a Duke on port 0
The host keyboard and mouse SHALL be presented to the title as a Duke on port 0 (`toolkit:src/input/keyboard.c`, `mouse.c`): a stick key ramps to full deflection over `input.stick_ramp_ms` and two perpendicular keys are circle-normalised; a held walk key scales the stick; mouse motion between two polls becomes a stick deflection with a floor above the title's 0.4 deadzone and reads zero when the mouse rests; face buttons, shoulders, triggers and stick clicks from a key or a mouse button are 255 or 0.
- Reason: a PC has a keyboard and a mouse and often no controller; the title is unplayable without a port-0 pad, and its camera is the right stick.
- Risk: the triggers, which the title reads as analog, never report a partial pull from a key; a stick from keys has at most the ramp's resolution; the camera turns at a rate set by mouse speed rather than by a fixed angle per distance, so a flick is not a turn of a fixed size; a mouse at any speed turns at least at the floor's rate.
- Detect: a game mechanic that needs a half-pulled trigger or a held partial stick (none known; `analysis/bringup/input/analog-audit.md`, local); the `mouse` trace shows the model's output.
- Exit: none planned; the knobs (`stick_ramp_ms`, `walk_scale`, `mouse_sensitivity`, `mouse_min_deflection`) are the player's. Retired only if the title is found to need analog pressure from the keyboard, which would want a pressure modifier key.

#### Scenario: Suspected analog shortfall
- **WHEN** a move works on a controller and not on the keyboard
- **THEN** the trigger and stick values of the two runs are compared in the `[INPUT] host port=0` lines before anything else is suspected

### Requirement: Spin waits may sleep
With `present.pacing = "sleep"`, the guest busy-wait loops lowered at generation time (`config/spin_waits.json`; v1: `0x00060475` only) SHALL block in the host instead of spinning, waking on kernel signals or after at most 1 ms (`frame-pacing`). On hardware the CPU spins.
- Reason: the spin holds one host core at about 97% while it waits for the vblank count, which costs heat and battery and takes a core from the raster threads (`analysis/research/hot-threads-macos.md` §1a).
- Risk: a lowered loop whose condition is changed by something the kernel does not signal advances up to 1 ms late on each pass, so a wait in a tight hand-off could slow the title. On the console's one CPU, a spinning thread also delays other guest threads; on the host it does not, and that difference shrinks when the loop sleeps.
- Detect: in the `pacing` trace, more than 5% of a site's loop exits are on the timeout, or a pacing A/B flags flips/s or raster ms.
- Exit: none planned while sleeping saves a core. The deviation is retired for a site that is removed from the list, and for all sites if `present.pacing` returns to `spin` everywhere. Since the default flip (2026-10-12, `fps-pacing` D9) it is in effect for every player who does not select `spin`; `spin` remains the console-original timing, one key away (`[present] pacing = "spin"` in `config/config.toml`, or `RECOMP_PRESENT_PACING=spin`), the bundle's README.txt and `package` say so, and the goldens still run at `spin`.

#### Scenario: Site leaves on timeouts
- **WHEN** the `pacing` trace shows a lowered site with more than 5% of its loop exits on the timeout
- **THEN** the site is either excluded from `config/spin_waits.json` or given a wake at its writer, and this entry records which

### Requirement: GP and EP DSPs bypassed
The emulated APU SHALL run the VP and SHALL sum the mixbins directly into the output (toolkit `apu_dsp.c`, passthrough) instead of running the GP and EP DSP56300 programs the XDK uploads. This applies to the stub path only: a build without the APU DSP or a run with it off (see `apu-dsp`); by default the dsp56300 JIT runs the uploaded programs.
- Reason: xemu's DSP core is not in the toolkit; the XDK GP program is the XDK's own mixer, whose inputs are the same mixbins.
- Risk: no reverb, no HRTF/3D submix, no GP-side volume curves or limiter; any title that reads GP output or waits on a GP-written command block hangs or misbehaves.
- Detect: `[APU] DSP GP/EP initialized (STUBBED - passthrough mode)` at boot; a DSOUND wait that never completes shows in `RECOMP_THREAD_DUMP` inside the DSOUND section (`0x00331FA0..0x0033A32C`).
- Exit: a DSP56300 interpreter in the toolkit runs the uploaded programs, and the stereo output of the golden scenarios matches xemu's within the `audio.json` thresholds.

#### Scenario: Missing effect
- **WHEN** a sound is audible in xemu but absent or dry in the port
- **THEN** this deviation is checked first: the voice's bin routing in the trace tells whether it went only through an effect bin

### Requirement: Stereo mixdown of every routed bin
On the stub path the emulated APU SHALL mix the bins a voice is routed to into two output channels, so 5.1 AIX tracks and 3D voices play in stereo. `RECOMP_APU_MIXDOWN_ALL` selects the mixdown: `1` (default) the GP's measured gain staging (speaker bins at unity, crosstalk bins at half, the I3DL2 send dropped), `0` bins 0 and 1 only, `2` every bin at unity. With the APU DSP on, the GP mixes the output and the key is ignored.
- Reason: the EP's 5.1 and Dolby Digital output stages are bypassed with the DSPs, and the EEPROM reports stereo PCM.
- Risk: centre and LFE content is split between left and right by bin parity, not by channel, and relative levels differ from a proper downmix.
- Detect: an AIX 5.1 stream (the FMV tracks) sounds unbalanced compared with xemu's stereo output in the reference compare.
- Exit: the DSP exit above, or a channel-aware downmix once the bin assignment of the XDK's 5.1 routing is confirmed from the trace.

#### Scenario: Balance complaint
- **WHEN** the reference compare passes spectrally but a movie's dialogue is off-centre
- **THEN** the bin assignment of the AIX stream's voices is read from the trace and compared with the XDK's 5.1 bin map

### Requirement: Host-paced audio clock
The APU frame thread SHALL be paced by the host output device's queue (Decision 3 of the `audio` design), not by an emulated AC'97 link clock, and the AC'97 DMA ring the EP would feed SHALL never be read.
- Reason: the EP is bypassed, so there is no DMA ring; the device queue is the only clock that avoids drift between produced and consumed samples.
- Risk: the audio clock, the vblank timer (62.5 Hz) and the 60 Hz pacer are three independent clocks; Sofdec follows audio, so the video side shows the drift as judder.
- Detect: judder in movies with audio on and not with `RECOMP_AC97_READY=0`, or `[XA2] underrun` lines in steady state.
- Exit: vblank raised from the GPU backend's present at the mode's rate (the vblank deviation's exit) with the pacer retired, leaving audio and video on one host clock.

#### Scenario: Judder during a movie
- **WHEN** a movie judders with audio enabled and does not with `RECOMP_AC97_READY=0`
- **THEN** the voice positions (`RECOMP_APU_TRACE=1`) are compared with the flip log before the GPU backend is suspected

### Requirement: PIO FIFO always has space
`NV1BA0_PIO_FREE` SHALL read back `0x80` whatever has been written, so the title never waits for the VP to drain methods.
- Reason: methods are applied synchronously in the fault handler; there is no FIFO to fill.
- Risk: none known for this title (its polls only gate the next write); a title timing itself against the FIFO would run early.
- Detect: n/a.
- Exit: none planned.

#### Scenario: Poll
- **WHEN** DSOUND polls `0xFE820010`
- **THEN** the trace shows exactly one read per poll

### Requirement: DSOUND GP command wait short-circuited
The port SHALL run the generated `sub_003341BE` (XDK DSOUND, the GP command submit). On the stub path (with the APU DSP on, the GP answers its own doorbell and `apu_dsp_ack` is forced to 0), with `RECOMP_AC97_READY` set, the game's env defaults SHALL set `RECOMP_APU_DSP_ACK` to `auto`: the toolkit finds the GP doorbell (`<GP block> + 0x810`, `0x80A1C810` in BLiNX 2) from `GPSADDR`. The toolkit's APU frame thread then clears the word on every pass, which ends the spin at `loc_00334325` as the GP program would.
- Reason: the GP DSP is bypassed (requirement "GP and EP DSPs bypassed"), so without the ack nothing clears the doorbell and DSOUND init hangs on the first command (`spike-results.md`, 1.3). Before this, a hand-copied body in `src/recomp_manual.c` replaced the spin; the ack keeps lifted code out of the port.
- Risk: the title assumes that the GP ran the command (the GP-side state the descriptor list sets up, such as effect parameters or mixbin routing in GP memory) when nothing ran it. Any later DSOUND path that reads GP-written results back gets stale data. With `auto` the address follows `GPSADDR`, so a moved contiguous allocation no longer hangs the boot; an explicit address in the environment still can.
- Detect: `[APU] DSP doorbell ack: auto (...)` and a `[APU] DSP doorbell (auto): command 0x00000003 ...` line at boot (with an explicit address: `[APU] DSP doorbell ack: 1 address(es), first 0x80A1C810` and `[APU] DSP doorbell 0x80A1C810: command 0x00000003 acknowledged`). A hang in `sub_003341BE`, or in a tight wait elsewhere in `0x00331FA0..0x0033A32C` (`sub_00336EBE`, `sub_00336F07`, `sub_00336F6E`, `sub_0033765A`, `sub_00338E0D`, listed in `spike-results.md`), shows in `RECOMP_WATCHDOG_SECS` output.
- Exit: a DSP56300 interpreter runs the XDK's GP image and clears the doorbell itself.

#### Scenario: DSOUND init
- **WHEN** the title runs with `RECOMP_AC97_READY=1` and no `RECOMP_APU_DSP_ACK` in the environment
- **THEN** the boot log has the doorbell-acknowledged line and `[APU] started by the title`, and flips continue past DSOUND init
