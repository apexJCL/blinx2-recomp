## ADDED Requirements

### Requirement: GP and EP DSPs bypassed
The emulated APU SHALL run the VP and SHALL sum the mixbins directly into the output (toolkit `apu_dsp.c`, passthrough) instead of running the GP and EP DSP56300 programs the XDK uploads.
- Reason: xemu's DSP core is not in the toolkit; the XDK GP program is the XDK's own mixer, whose inputs are the same mixbins.
- Risk: no reverb, no HRTF/3D submix, no GP-side volume curves or limiter; any title that reads GP output or waits on a GP-written command block hangs or misbehaves.
- Detect: `[APU] DSP GP/EP initialized (STUBBED - passthrough mode)` at boot; a DSOUND wait that never completes shows in `RECOMP_THREAD_DUMP` inside the DSOUND section (`0x00331FA0..0x0033A32C`).
- Exit: a DSP56300 interpreter in the toolkit runs the uploaded programs, and the stereo output of the golden scenarios matches xemu's within the `audio.json` thresholds.

#### Scenario: Missing effect
- **WHEN** a sound is audible in xemu but absent or dry in the port
- **THEN** this deviation is checked first: the voice's bin routing in the trace tells whether it went only through an effect bin

### Requirement: Stereo mixdown of every routed bin
The emulated APU SHALL mix every bin a voice is routed to into two output channels (even bins left, odd bins right; `RECOMP_APU_MIXDOWN_ALL`, default on), so 5.1 AIX tracks and 3D voices play in stereo.
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
- Detect: `scripts/av_sync.py` drift above 16.7 ms/min, or `[XA2] underrun` lines in steady state.
- Exit: vblank raised from the GPU backend's present at the mode's rate (the vblank deviation's exit) with the pacer retired, leaving audio and video on one host clock.

#### Scenario: Judder during a movie
- **WHEN** a movie judders with audio enabled and does not with `RECOMP_AC97_READY=0`
- **THEN** `av_sync.py` is run on the trace before the GPU backend is suspected

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
The port SHALL run the generated `sub_003341BE` (XDK DSOUND, the GP command submit). With `RECOMP_AC97_READY` set, `main.c` SHALL default `RECOMP_APU_DSP_ACK` to `0x80A1C810`, the GP doorbell (`<GP block> + 0x810`). The toolkit's APU frame thread then clears the word on every pass, which ends the spin at `loc_00334325` as the GP program would.
- Reason: the GP DSP is bypassed (requirement "GP and EP DSPs bypassed"), so without the ack nothing clears the doorbell and DSOUND init hangs on the first command (`spike-results.md`, 1.3). Before this, a hand-copied body in `src/recomp_manual.c` replaced the spin; the ack keeps lifted code out of the port.
- Risk: the title assumes that the GP ran the command (the GP-side state the descriptor list sets up, such as effect parameters or mixbin routing in GP memory) when nothing ran it. Any later DSOUND path that reads GP-written results back gets stale data. The address is observed, not derived: if the contiguous allocation moves, the boot hangs in `sub_003341BE`.
- Detect: `[APU] DSP doorbell ack: 1 address(es), first 0x80A1C810` and `[APU] DSP doorbell 0x80A1C810: command 0x00000003 acknowledged` at boot. A hang in `sub_003341BE`, or in a tight wait elsewhere in `0x00331FA0..0x0033A32C` (`sub_00336EBE`, `sub_00336F07`, `sub_00336F6E`, `sub_0033765A`, `sub_00338E0D`, listed in `spike-results.md`), shows in `RECOMP_WATCHDOG_SECS` output.
- Exit: a DSP56300 interpreter runs the XDK's GP image and clears the doorbell itself.

#### Scenario: DSOUND init
- **WHEN** the title runs with `RECOMP_AC97_READY=1` and no `RECOMP_APU_DSP_ACK` in the environment
- **THEN** the boot log has the doorbell-acknowledged line and `[APU] started by the title`, and flips continue past DSOUND init
