## ADDED Requirements

### Requirement: APU MMIO is trapped and serviced on hosts that can decode faults
On an x86-64 Windows host (including Proton) and on a POSIX AArch64 host (macOS arm64; Linux arm64 by construction, untested), when `RECOMP_AC97_READY` is in effect, the host SHALL map the APU window `0xFE800000..0xFE87FFFF` so that every guest access faults, SHALL decode the faulting instruction (`mmio_decode.h` from the VEH record on Windows; `mmio_decode_a64.h` from the SIGBUS/SIGSEGV ucontext on POSIX) and service it through the emulated APU (`mcpx_apu_read`/`mcpx_apu_write`), and SHALL resume the guest after the instruction. The AC'97 bus-master page SHALL be write-trapped the same way so a channel reset completes on the write. The boot log SHALL contain `APU: ... trapped for MMIO` and `[BOOT] emulated APU up`. An access the decoder cannot service SHALL be logged as `[APU] MMIO decode fail` with the instruction bytes, and SHALL be treated as a bug, not skipped silently.

#### Scenario: DSOUND initialises against the emulated APU
- **WHEN** the title runs under Proton, or headless on macOS arm64, with `RECOMP_AC97_READY=1 RECOMP_APU_TRACE=1`
- **THEN** the log contains `[APUMMIO]` writes to the EP reset (`0x5FFFC`), the voice-list registers (`0x2054..0x2074`) and PIO methods (`0x202F8` onwards), followed by `[APU] started by the title`, and contains no `[APU] MMIO decode fail` line

#### Scenario: Host that cannot service MMIO
- **WHEN** the title runs on a host without fault decoding (x86-64 Linux) with `RECOMP_AC97_READY=1`
- **THEN** the boot log says `[ENV] RECOMP_AC97_READY: audio unsupported on this host; ignored`, the APU window stays a zeroed aperture, and the title boots as before

#### Scenario: A64 decoder is tested against real faults
- **WHEN** `tests/mmio_decode_a64` runs on a POSIX arm64 host
- **THEN** every covered load/store form (byte to quad, signed, pre/post-index, register offset, pairs, SIMD&FP) is serviced with the right width, direction, register and writeback, and the exclusive form is refused; off POSIX arm64 the test exits 77 (skipped)

### Requirement: The PIO FIFO never blocks the title
`NV1BA0_PIO_FREE` (`0x20010`) SHALL read back as at least 4 after masking the low two bits, so that the XDK's free-space polls (`sub_003349BC` and the other `0xFE820010` spins) complete on the first read.

#### Scenario: Poll completes
- **WHEN** DSOUND polls `0xFE820010` before a voice method write
- **THEN** the trace shows a single read per poll and the write that follows it

### Requirement: The hardware mixdown reaches the device
Samples produced by `mcpx_apu_dsp_frame` for a frame SHALL be the samples submitted to the output device for that frame. The monitor path SHALL add the software mixer and the test tone to those samples, never replace them. A unit test with a fake device SHALL fail if a non-zero DSP frame produces a silent submission.

#### Scenario: Voice audible
- **WHEN** a unit test places one voice's 32-sample frame in the DSP output and runs the monitor frame with no mixer activity
- **THEN** the samples handed to the device equal that frame (after mixdown), not zero

### Requirement: Output is paced by the device queue
The APU frame thread SHALL submit one 256-sample granule per EP period and SHALL keep the device queue between a low and a high water mark (in samples, exact for any device buffer size). At or above the high mark it SHALL wait one EP period and re-check (no device callback), below the low mark it SHALL render ahead, and its render-ahead SHALL be bounded by the high mark: it SHALL never run more than the high mark's worth of audio ahead of the host monotonic clock. The high mark SHALL be capped so that a period submitted below it never fills a buffer the voice has no slot for. An intentional pause of the frame thread SHALL NOT count as an underrun. Underruns SHALL be counted and logged at most once per second as `[XA2] underrun x<count>` (Windows, XAudio2) or `[SDL2] underrun x<count>` (POSIX, SDL2). The device backend SHALL be XAudio2 on Windows and SDL2 on POSIX hosts, behind one contract (`apu_xaudio2.h`), so the pacer and its tests are shared. Under `RECOMP_HEADLESS=1` the SDL2 backend SHALL use a silent driver that drains the queue in real time unless `SDL_AUDIODRIVER` names another.

#### Scenario: Steady state
- **WHEN** a 60 s run of the title is dumped with `RECOMP_AUDIO_WAV`
- **THEN** the dump's sample count is within 0.5 % of 48000 x the wall-clock seconds between the first and last submission, and the log has no underrun line after the first second of sound

#### Scenario: Device stalls
- **WHEN** the fake device in the pacing unit test stops consuming for 100 ms
- **THEN** the frame thread stops submitting at the high mark and resumes within one granule after consumption resumes, with no samples dropped

#### Scenario: Headless run on macOS
- **WHEN** the title runs with `RECOMP_HEADLESS=1 RECOMP_AC97_READY=1` on macOS arm64
- **THEN** the log has `[SDL2] audio initialized: driver dummy ... [silent: no device output]` and `[APU] Using SDL2 audio backend`, nothing is played, and the WAV tap holds the paced output

### Requirement: Buffer sizes are tunable and the defaults are measured
Device buffer length and count SHALL default to 512 samples x 4 and SHALL be overridable with `RECOMP_AUDIO_BUF_SAMPLES` and `RECOMP_AUDIO_BUF_COUNT`. The chosen defaults SHALL be the smallest combination measured under Proton on the Linux/Proton host that gives no underruns over the golden scenarios; the measurement SHALL be recorded in `analysis/golden/audio.json` (`about`).

#### Scenario: Override
- **WHEN** `RECOMP_AUDIO_BUF_SAMPLES=1024 RECOMP_AUDIO_BUF_COUNT=3` is set
- **THEN** the boot log's `[XA2] XAudio2 initialized` line reports 1024 x 3

### Requirement: Deterministic WAV dump
When `RECOMP_AUDIO_WAV=<path>` is set, the toolkit SHALL write every sample it submits to the device, after mixdown, to a 48 kHz 16-bit stereo RIFF WAV at that path, and SHALL finalise the header on normal exit, watchdog exit and console close. `RECOMP_AUDIO_WAV_SECS=<n>` SHALL stop the dump after n seconds. The dump SHALL be byte-identical to the submitted samples: it is a tap, not a second render.

#### Scenario: Dump is checkable
- **WHEN** a run ends by the watchdog with `RECOMP_AUDIO_WAV` set
- **THEN** `scripts/audio_check.py <path>` parses the file, reports duration, first sound, RMS per window, dropouts and clipping, and exits 0

### Requirement: Scripted checks against thresholds and a reference
`scripts/audio_check.py` SHALL verify a dump against `analysis/golden/audio.json`: sample-rate ratio, time of first sound within a window, no zero-run longer than 2 ms after first sound, clipping below a fraction, and, when a reference capture is present, envelope lag within 500 ms and per-band spectral correlation above the scenario's threshold. It SHALL be invoked by `scripts/bench.sh` when `BENCH_AUDIO=1`, with the dump written into the run's log directory. Dumps and references SHALL live under `analysis/golden/audio/` (gitignored); only `audio.json` is committed.

#### Scenario: Silent run fails
- **WHEN** a run produces a dump with no sample above the silence floor in the first-sound window
- **THEN** the check exits non-zero and names the scenario and the window

#### Scenario: Reference compare
- **WHEN** `analysis/golden/audio/<scenario>.ref.wav` exists
- **THEN** the check reports lag and per-band correlation, and fails below the threshold in `audio.json`

### Requirement: xemu reference audio is captured only from the private instance
`scripts/xemu_ref.py --audio` SHALL capture the audio of the xemu instance it launched (private config copy under `~/xemu-ref`) to `analysis/golden/audio/<scenario>.ref.wav`, SHALL refuse to start when any `app.xemu.xemu` instance is already running, SHALL only ever stop its own instance, and SHALL never read or write the user's own xemu configuration or audio. The primary route is `SDL_AUDIODRIVER=disk`; the fallback is `pw-record` targeting the node whose process id is the private instance's.

#### Scenario: User's xemu is open
- **WHEN** `xemu_ref.py --audio` starts while another xemu instance exists
- **THEN** it exits with the existing refusal and captures nothing

### Requirement: A/V sync is measured against the Sofdec clock
With `RECOMP_APU_TRACE=1`, the APU SHALL log each active voice's play position every 60 frames (`[APU] voice <n> pos=<cur>/<len>`). `scripts/av_sync.py` SHALL combine those lines with the flip log and `fmv-playback`'s movie open/close lines to report the audio-to-video drift over each movie. Drift over the intro movies SHALL be under one video frame (16.7 ms) per minute, with no voice-position stall longer than one EP period while a movie plays.

#### Scenario: Intro movies
- **WHEN** the boot-to-title scenario runs with `RECOMP_APU_TRACE=1 RECOMP_FLIP_LOG=1`
- **THEN** `av_sync.py` reports a drift under 16.7 ms/min for each movie and exits 0

### Requirement: Audio is on by default where the host can service it
The environment table (`recomp_env.c`) SHALL default `RECOMP_AC97_READY` to on for hosts that can service MMIO (x86-64 Windows, including Proton, and POSIX arm64) unless the environment sets it; `RECOMP_AC97_READY=0` SHALL turn the emulated APU off and keep the zeroed aperture. Hosts that cannot service MMIO SHALL be unaffected.

#### Scenario: Opt-out
- **WHEN** the title runs under Proton with `RECOMP_AC97_READY=0`
- **THEN** the boot log has no `emulated APU` line, no `APU: ... trapped` line, and the title boots as before this change
