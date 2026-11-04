# audio Specification

## Purpose
TBD - created by archiving change audio. Update Purpose after archive.

## Requirements

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
The APU frame thread SHALL submit one 256-sample granule per EP period and SHALL keep the device queue between a low and a high water mark (in samples, exact for any device buffer size). At or above the high mark it SHALL wait one EP period and re-check (no device callback), below the low mark it SHALL render ahead, and its render-ahead SHALL be bounded by the high mark: it SHALL never run more than the high mark's worth of audio ahead of the host monotonic clock. The high mark SHALL be capped so that a period submitted below it never fills a buffer the voice has no slot for. An intentional pause of the frame thread SHALL NOT count as an underrun. Underruns SHALL be counted and logged at most once per second as `[XA2] underrun x<count>` (Windows, XAudio2) or `[SDL3] underrun x<count>` (POSIX, SDL3). The device backend SHALL be XAudio2 on Windows and SDL3 on POSIX hosts (`apu_sdl.c`: an `SDL_AudioStream` opened with `SDL_OpenAudioDeviceStream` on the default playback device, fed with `SDL_PutAudioStreamData`, its depth read with `SDL_GetAudioStreamQueued`), behind one contract (`apu_xaudio2.h`), so the pacer and its tests are shared. The SDL3 backend SHALL ask for the device buffer of `RECOMP_AUDIO_BUF_SAMPLES` through `SDL_HINT_AUDIO_DEVICE_SAMPLE_FRAMES` before opening, SHALL log the granted size in its `audio initialized` line, and SHALL pace with the granted size when it differs. Under `RECOMP_HEADLESS=1` the SDL3 backend SHALL use a silent driver that drains the queue in real time unless `SDL_AUDIO_DRIVER` (or its alias `SDL_AUDIODRIVER`) names another. On SDL's dummy driver the queue depth SHALL come from the host monotonic clock's virtual device (`apu_vclock`), not from SDL's stream, which stays paused and empty, so headless pacing does not follow the dummy driver's sleep timing.

#### Scenario: Steady state
- **WHEN** a 60 s run of the title is dumped with `RECOMP_AUDIO_WAV`
- **THEN** the dump's sample count is within 0.5 % of 48000 x the wall-clock seconds between the first and last submission, and the log has no underrun line after the first second of sound

#### Scenario: Device stalls
- **WHEN** the fake device in the pacing unit test stops consuming for 100 ms
- **THEN** the frame thread stops submitting at the high mark and resumes within one granule after consumption resumes, with no samples dropped

#### Scenario: Headless run on macOS
- **WHEN** the title runs with `RECOMP_HEADLESS=1 RECOMP_AC97_READY=1` on macOS arm64 and neither `SDL_AUDIO_DRIVER` nor `SDL_AUDIODRIVER` set
- **THEN** the log has `[SDL3] audio initialized: driver dummy ... [silent: no device output]` and `[APU] Using SDL3 audio backend`, nothing is played, and the WAV tap holds the paced output

#### Scenario: Granted buffer differs
- **WHEN** `RECOMP_AUDIO_BUF_SAMPLES=300` is set and the device grants 512 frames
- **THEN** the `audio initialized` line reports `512 (asked 300)`, the marks are computed from 512, and the run passes `audio_check.py`

#### Scenario: Real sound on macOS
- **WHEN** the one permitted Mac run with `SDL_AUDIO_DRIVER=coreaudio` is made, after the user has been asked
- **THEN** the user hears clean attract audio, and the WAV tap passes `audio_check.py --log` with no host starvation

### Requirement: Buffer sizes are tunable and the defaults are measured
Device buffer length SHALL default to 512 samples on every host. Device buffer count SHALL default to 4, except in the Windows build running under Wine (`xbox_HostUnderWine()`), where it SHALL default to 6, the count chosen by the measurement. Both SHALL be overridable with `RECOMP_AUDIO_BUF_SAMPLES` and `RECOMP_AUDIO_BUF_COUNT` on every host. The pacing marks SHALL follow the resolved size and count. The chosen defaults SHALL be the smallest combination measured under Proton on the Deck that gives no underruns over the long bench and the golden scenarios; the measurement SHALL be recorded in `analysis/golden/audio.json` (`about`). When the Wine default applies, the `[XA2] XAudio2 initialized` line SHALL say so.

#### Scenario: Override
- **WHEN** `RECOMP_AUDIO_BUF_SAMPLES=1024 RECOMP_AUDIO_BUF_COUNT=3` is set
- **THEN** the boot log's `[XA2] XAudio2 initialized` line reports 1024 x 3 on any host

#### Scenario: Wine default
- **WHEN** the Windows build starts under Proton with neither key set
- **THEN** the `[XA2] XAudio2 initialized` line reports 512 x the Wine count and `(wine default)`, and the `[APU] Using XAudio2 audio backend` line reports the pacing marks for that count

#### Scenario: Native hosts unchanged
- **WHEN** the Windows build starts on native Windows, or the POSIX build starts on macOS, with neither key set
- **THEN** the backend reports 512 x 4, as before this change

### Requirement: Deterministic WAV dump
When `RECOMP_AUDIO_WAV=<path>` is set, the toolkit SHALL write every sample it submits to the device, after mixdown, to a 48 kHz 16-bit stereo RIFF WAV at that path, and SHALL finalise the header on normal exit, watchdog exit and console close. `RECOMP_AUDIO_WAV_SECS=<n>` SHALL stop the dump after n seconds. The dump SHALL be byte-identical to the submitted samples: it is a tap, not a second render.

#### Scenario: Dump is checkable
- **WHEN** a run ends by the watchdog with `RECOMP_AUDIO_WAV` set
- **THEN** `<game> audio-check <path>` parses the file, reports duration, first sound, RMS per window, dropouts and clipping, and exits 0

### Requirement: Scripted checks against thresholds and a reference
`<game> audio-check` (the CLI's `audio_check.py`) SHALL verify a dump against `analysis/golden/audio.json`: sample-rate ratio, time of first sound within a window, no zero-run longer than 2 ms after first sound, clipping below a fraction, and, when a reference capture is present, envelope lag within 500 ms and per-band spectral correlation above the scenario's threshold. Dumps and references SHALL live under `analysis/golden/audio/` (gitignored); only `audio.json` is committed.

#### Scenario: Silent run fails
- **WHEN** a run produces a dump with no sample above the silence floor in the first-sound window
- **THEN** the check exits non-zero and names the scenario and the window

#### Scenario: Reference compare
- **WHEN** `analysis/golden/audio/<scenario>.ref.wav` exists
- **THEN** the check reports lag and per-band correlation, and fails below the threshold in `audio.json`

### Requirement: Voice positions are traced
With `RECOMP_APU_TRACE=1`, the APU SHALL log each active voice's play position every 60 frames (`[APU] voice <n> pos=<cur>/<len>`), so a later A/V measurement can fit samples played against flips.

#### Scenario: Positions advance
- **WHEN** a voice plays for 120 frames with `RECOMP_APU_TRACE=1`
- **THEN** the log has two `[APU] voice <n> pos=` lines for it, the second position past the first

### Requirement: Audio is on by default where the host can service it
The environment table (`recomp_env.c`) SHALL default `RECOMP_AC97_READY` to on for hosts that can service MMIO (x86-64 Windows, including Proton, and POSIX arm64) unless the environment sets it; `RECOMP_AC97_READY=0` SHALL turn the emulated APU off and keep the zeroed aperture. Hosts that cannot service MMIO SHALL be unaffected.

#### Scenario: Opt-out
- **WHEN** the title runs under Proton with `RECOMP_AC97_READY=0`
- **THEN** the boot log has no `emulated APU` line, no `APU: ... trapped` line, and the title boots as before this change

### Requirement: APU thread priority
`RECOMP_AUDIO_THREAD_PRIORITY` SHALL accept `normal` and `highest` and SHALL default to `normal` on every host. It is opt-in for hosts that honour it. `time_critical` SHALL be honoured only with the DEBUG-tier key `audio_thread_tc` on; otherwise it SHALL be reported once and treated as `highest`. When the key is set, Windows builds SHALL set the APU frame thread to the resolved priority at creation and log the value read back, or the error when the call fails; when it is unset, nothing SHALL be logged. Another value SHALL be reported once and treated as `normal`. POSIX builds SHALL report once that the key is ignored.

#### Scenario: Default is normal
- **WHEN** the Windows build starts with `RECOMP_AUDIO_THREAD_PRIORITY` unset
- **THEN** the APU frame thread keeps its normal priority and no priority line is logged

#### Scenario: Raised on Proton
- **WHEN** SSX 3 runs under Proton with `RECOMP_AUDIO_THREAD_PRIORITY=highest`
- **THEN** the log has `[APU] thread priority highest` with the value read back, and the `mcpx.apu_thread` task's nice on the Linux side drops below 0 only when the user's `RLIMIT_NICE` allows it (on a stock Deck it stays 0)

### Requirement: APU thread is named
On Windows builds the APU frame thread SHALL be named `mcpx.apu_thread` with `SetThreadDescription` when the host provides it (looked up at run time), so it can be identified on the Linux side under Wine.

#### Scenario: Named under Wine
- **WHEN** the Windows build runs under Proton on a host whose kernel32 exports `SetThreadDescription`
- **THEN** the APU frame thread shows as `mcpx.apu_thread` in the Linux task list (`/proc/<pid>/task/*/comm`)
