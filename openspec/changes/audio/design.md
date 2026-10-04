## Context

BLiNX 2 has no audio today. The title links XDK 5849 DSOUND (section `DSOUND`, VA `0x00331FA0..0x0033A32C`, translated into `src/recomp/gen/recomp_0099.c` and `recomp_0100.c`). Disc audio is CRI ADX/AIX, decoded by the translated CRI code (ADXT/ADXXB/AIXP) into DSOUND buffers and streams; FMVs are CRI Sofdec with the ADX track as the master clock (`analysis/research/blinx2-internals-and-fmv.md`). The translated DSOUND programs the MCPX APU through MMIO at `0xFE800000..0xFE87FFFF`.

What exists:

- Toolkit `src/apu/` is xemu's APU: the VP (256 voices, PIO methods at region `0x20000`), and the GP/EP DSPs stubbed to a passthrough mixdown (`apu_dsp.c`, "STUBBED - passthrough mode"). Output goes through `apu_xaudio2.c` (XAudio2 2.8; FAudio under Proton) with a waveOut fallback; POSIX builds have stubs that report no device.
- Toolkit `src/kernel/xbox_memory_layout.c`, under `RECOMP_AC97_READY`: marks the 512 KB APU window `PAGE_NOACCESS` (`APU: ... trapped for MMIO`), sets the AC'97 codec-ready bit at `0xFEC00130` so `DirectSoundCreate` does not fail with `DSERR_NODRIVER`, and arms a write trap on the AC'97 bus-master page.
- cat `src/main.c`: the VEH routes faults in `APU_TRAP_BASE..APU_TRAP_END` to `apu_hook_handle_mmio` (`src/apu/apu_mmio_hook.c`, an x86-64 MOV/MOVZX/TEST/CMP/OR/AND decoder), and Step 4 calls `mcpx_apu_init_standalone` when `RECOMP_AC97_READY` is set (`[BOOT] emulated APU up`). `HOST_CAN_SERVICE_MMIO` is Windows x86-64 only; the macOS SIGBUS handler reports and dies.
- `run-under-proton` task 3.3 ("run with `RECOMP_AC97_READY=1`") has never been run. Nothing in this path has been exercised by this title.

What the generated DSOUND does (read from `recomp_0099.c`/`recomp_0100.c`, read-only in the integration checkout):

- Polls `NV1BA0_PIO_FREE` at `0xFE820010` (`eax &= ~3; cmp eax, 4; jb`) in at least nine functions (`sub_003349BC`, `sub_003349F3`, `sub_00335150`, `sub_00336ADD`, `sub_00336D7D`, `sub_00337EF1`, `sub_00337FC4`, `sub_00338939`, and the `-25034736` form, which is the same constant). On a zeroed aperture these spin for ever; the VP read path returns `0x80`, which satisfies them.
- Resets and uploads the GP and EP: `MEM32(0xFE85FFFC) = 1` (EPRST, `sub_00338103`), a write to `0xFE83FF10`, `GPOFBASE0..3 -> GPOFCUR0..3` copies, YMEM uploads relative to `0xFE836000` (`sub_003341BE`), FIFO base/max-SGE registers (`0x2048`, `0x20D4/0x20DC/0x20E0`), and the `0xFE804028` (EPOFEND0) loop.
- Programs voice lists (`0x205C/0x2064/0x2068/0x2070/0x2074`) and voices through PIO methods (`0xFE8202F8` SET_CURRENT_VOICE, `0x300`, `0x31C`, `0x43C`, `0x808`).
- Writes `IEN` (0x1004): 0x00, then 0xD8, then 0xD9 (spike-results, run B), and `FETFORCE1` = `SE2FE_IDLE_VOICE`, so every voice that goes idle traps the front end. Boot does not need the interrupt, but playback does: only the ISR on vector 5 (`sub_00334DBF` -> `sub_00334D23`) reads the trapped `FEDECMETH`/`FEDECPARAM`, takes the voice off its list and sets `FECTL` back to free running. Without delivery the first idle voice halts the VP for good (task 4.1's first run: under a second of frames, then silence). `FEVINTSTS` (0x40) makes the ISR queue the notification DPC.

Two toolkit defects found while reading, both blocking:

1. `mcpx_apu_monitor_frame` (`apu_core.c`) zeroes `d->monitor.frame_buf` before rendering the software mixer and the test tone into it, in both the XAudio2 and the waveOut arms. `mcpx_apu_dsp_frame` has already written the VP/DSP mixdown into that buffer (`frame_buf[off+i]`, `off = (ep_frame_div % 8) * 32`). The hardware voices never reach the device. It also submits 1024 samples per 256-sample period and `xa2_submit_samples` drops when `BuffersQueued >= 3`.
2. `queued_bytes_low = 1024 / high = 3072` are set and never read; the frame thread is paced only by `throttle()` (`EP_FRAME_US = 5333` per 8 frames) with no feedback from the device queue, so it will drift from the device clock and either underrun or drop.

## Goals / Non-Goals

Goals:

- Audible, correctly paced audio for the title under Proton on the Linux/Proton host (the priority host), from the translated DSOUND through the emulated APU, with no title-specific patches to DSOUND itself unless the GP handshake forces one.
- A deterministic test harness: a WAV dump knob, scripted checks (silence, dropouts, rate, tolerant comparison against xemu), and A/V sync measurement against the Sofdec frame index.
- Every deviation from the hardware (GP/EP bypass, stereo mixdown, host pacing) recorded in `deviations`.
- Every risk retired by evidence in the first phase, before the larger work starts.

Non-Goals:

- Audio on macOS arm64. There is no MMIO trap route there; this design names the options and leaves them for a later change.
- Reverb, HRTF/3D, 5.1 output, Dolby Digital encode. The EEPROM already reports stereo PCM (`tests/kernel_audio_setting`).
- A DSP56300 interpreter for the GP/EP. Only if the spike proves the title cannot start without one (Decision 2).
- Changing the recompiler output or the MEM macros.

## Decisions

### 1. Emulate at the APU MMIO level (xemu VP, GP/EP stubbed), not HLE of DSOUND

Chosen: run the translated DSOUND as it is and service its register traffic with toolkit `src/apu`, through the VEH route that already exists. Host output through XAudio2, which is FAudio under Proton.

Alternatives considered:

- HLE of DSOUND (replace `DirectSoundCreate` and the `IDirectSound8`/`IDirectSoundBuffer8`/`IDirectSoundStream` methods with host code over `src/audio/dsound_device.c`). Rejected:
  - The XDK objects are COM vtables that the translated title and CRI code call through guest function pointers. Every method would need a guest-callable thunk registered at a guest address, for buffers and for streams (CRI ADXXB uses `IDirectSoundStream` with packet lists; `dsound_device.c` implements streams as buffers and has no 3D, no mixbins, no notifications). None of it exists and none of it has callers in cat or the toolkit.
  - It contradicts `xdk-library-hle`: XDK libraries are translated, and only hardware-bound entry points are overridden, by guest address, in `src/recomp_manual.c`.
  - It is title-specific (DSOUND 5849's object layouts), where the APU is the same for every title.
  - The expensive part (ADX decode) is already guest code and works either way; HLE saves nothing there.
- Emulating the GP/EP DSPs faithfully (port xemu's DSP56300 core). Not chosen now: large, and the Xbox GP program is the XDK's own mixer, whose outputs are the same mixbins the passthrough already sums. Kept as the exit of the "GP/EP bypass" deviation and as fallback for Decision 2.

Consequence: the toolkit does the work; cat contributes the VEH, boot flags, deviations and tests. Toolkit changes stay general (no title constants).

### 2. The GP DSP handshake is a gate, decided by the spike's trace

The XDK DSOUND resets the GP/EP, uploads their programs and FIFO setup, then likely waits for the GP to acknowledge (a command block in guest RAM, or a GP register). The stub never answers. Three ways out, in order of preference, chosen after reading `[APUMMIO]` trace of the real run:

1. Nothing needed: the title polls only `PIO_FREE` and register read-backs the VP already models. Proceed.
2. A general toolkit answer: if DSOUND spins on a GP/EP register (for example `GPRST`/`EPRST` reading back 0, or a FIFO cursor), model that register in `apu_dsp.c` as the hardware would present it after the program ran (reset bit clears, `GPOFCUR` advances with `EPOFEND`). General, upstreamable.
3. A cat override: if DSOUND spins on a guest-RAM command block the GP program would write, override that one wait function in `src/recomp_manual.c` by guest address (`xdk-library-hle` policy), returning the "done" status. Title-specific, recorded in `deviations`. `RECOMP_APU_DSP_ACK=<addr>` (a per-frame dword clear, documented as a hack for Wreckless) is the probe used to find the address, not the shipped fix.

If none of these applies (the GP output is consumed by the title, not just waited on), the DSP56300 port is scheduled as its own change.

### 3. Threading and timing model

- Guest threads touch the APU only through MMIO faults; each fault is serviced synchronously on the faulting thread by `apu_hook_handle_mmio` -> `mcpx_apu_read/write`, and execution resumes after the instruction. VP method writes are therefore ordered as the title issued them.
- One host frame thread (the existing one in `apu_core.c`) runs `mcpx_apu_dsp_frame` for 32-sample frames at 48 kHz. It reads voice state, SGEs and sample data from guest RAM, as the hardware does; the only shared host state with the fault path is the register file and voice lists, under the existing APU lock. The lock is held for the register access, never across the frame render.
- Pacing: the frame thread is paced by the device queue, not by `EP_FRAME_US` alone. Every 256 samples (one EP period, 5.333 ms) it submits one granule to a ring; the submit path keeps between `low` and `high` samples queued on the voice (`queued_bytes_low/high`, which existed unused; the marks are computed in samples, so device buffers that are not multiples of 256 keep exact marks, and `high` is capped where one more period could fill a buffer the voice has no slot for). At or above `high` it waits one EP period and re-checks; there is no device callback. Below `low` it renders ahead, bounded by `high` against the host monotonic clock, so a stalled device cannot run the APU ahead of guest time. A pause of the frame thread (`pause_requested`) drains the queue on purpose and is not counted as an underrun.
- The frame thread idles (`pause_requested`) until the title writes `SECTL`/`FECTL` (`[APU] started by the title`). Stays as is.
- APU interrupts are delivered (task 4.7), by the toolkit's upstream design (591dcb9 and follow-ups). `update_irq` sets `ISTS` as xemu does and raises a line flag when it asserts `GINTSTS`. After each frame the APU frame thread calls the vector 5 ISR itself, on a guest worker stack slice with its own TIB, with the APU lock dropped (level-triggered: the driver acks before it resumes the front end, so the ack re-latches `FETINTSTS` and the ISR runs again on the next frame). The VP raises at most one idle-voice trap at a time, so `FEDECPARAM` is not overwritten before the ISR reads it.
- While a guest thread holds a raised IRQL (`KeSynchronizeExecution`, a DPC), delivery is held off for up to 50 frames; the driver's ISR and its synchronize routines both update `ctx+0x4B8`. The DPC queue has its own lock. APU physical addresses in a page the contiguous allocator has handed out resolve into the 0x80000000 window, where the driver keeps the voice array, SGEs and notifiers. That holds inside the image's physical range too (BLiNX 2's image runs to 0x0303AC20 and the voice array is at 0x009E8000); upstream's image and high-water rules apply only after that. IRQL is per thread (`XBOX_THREAD_LOCAL` is `__thread` under MinGW), and a `KfLowerIrql` that raises sets the level but is never counted, so the raised count that gates delivery cannot leak.

### 4. Host output, buffer sizing, latency

- XAudio2 2.8 through `apu_xaudio2.c`; under Proton this is FAudio over SDL2/PipeWire. Format fixed at 48 kHz, 16-bit stereo (`XA2_SAMPLE_RATE`, `XA2_CHANNELS`). waveOut stays as the fallback on Windows; POSIX stays stubbed.
- Granule 256 samples (5.33 ms, one EP period). Device buffers of 512 samples (10.7 ms), up to 4 queued: 43 ms worst-case output latency, 21 ms typical (starting point; target ~20 ms worst case, task 4.6). Today's 1024 x 3 is replaced. Defaults are env-tunable (`RECOMP_AUDIO_BUF_SAMPLES`, `RECOMP_AUDIO_BUF_COUNT`) so the numbers can be set from measurement on the Linux/Proton host (PipeWire's default quantum is 1024/48000 = 21 ms; FAudio may need the 4 x 512 floor). The task that tunes them records the measurement and the final defaults.
- Underruns are counted and logged once per second at most (`[XA2] underrun x%u`) so the harness can assert on them.
- What macOS needs later (out of scope): an output backend (SDL2 audio, already a dependency of the OpenGL path; `win32_compat.h` already reserves the waveOut stubs for it), and an MMIO route. Three routes, to be decided in a later change: (a) arm64 load/store decode in the SIGBUS handler, the same shape as the x86-64 hook; (b) the recompiler emitting `mmio_read32/write32` calls for constant device addresses (every DSOUND access found so far is a constant or a constant base in a register); (c) range-checked MEM macros (costly for every access). (b) is the attractive one because it also removes the fault cost on Windows, but register-indirect loops like `edi = 0xFE804028` need (a) or (c) as a backstop.

### 5. Audio as the Sofdec clock

Sofdec's player advances video by the ADX stream's play position, which it reads through DSOUND `GetCurrentPosition`/`GetStatus`; the XDK implements those by reading voice state the VP writes back into guest RAM. With the VP paced as in Decision 3, the audio clock is the host device clock, and video follows it. Two consequences:

- The vblank deviation (62.5 Hz timer, `deviations`) and the 60 Hz pacer are independent clocks; drift against audio is expected and is what the measurement quantifies. Sofdec drops or repeats frames to follow audio, so the symptom is judder, not desync, unless the voice position stalls.
- Measurement: with `RECOMP_APU_TRACE=1` the APU logs each voice's play position every 60 frames (`[APU] voice %u pos=%u/%u`), and `fmv-playback` logs movie open/close and the flip index (`RECOMP_FLIP_LOG=1`). The ratio of samples advanced to flips over the intro movies gives the drift; target is under one video frame (16.7 ms) per minute and no stall longer than one EP period while a movie plays.

### 6. Deviations (recorded in `specs/deviations/spec.md`)

- GP/EP bypass: mixbins summed directly; no reverb, no HRTF/3D, no GP post-processing.
- Stereo mixdown of every routed bin (`RECOMP_APU_MIXDOWN_ALL`, even bins left, odd right): AIX 5.1 tracks and 3D voices land in stereo.
- No Dolby Digital encode; the EEPROM already reports stereo PCM, so the title never asks for it.
- Host-paced audio clock: the APU frame rate is the device clock, not the AC'97 link; the AC'97 DMA ring the EP would feed is never read, the mixdown is taken directly.
- `PIO_FREE` always reports space (`0x80`): the PIO FIFO is infinite, so the title never waits on the VP.

### 7. Test harness

- Dump knob: `RECOMP_AUDIO_WAV=<path>` makes the toolkit write exactly the samples handed to the device (post-mixdown, 48 kHz s16 stereo) to a WAV, header finalised on shutdown, watchdog exit and `SIGINT`/console close; `RECOMP_AUDIO_WAV_SECS=<n>` caps it. The dump is a tap on the submit path, so what is checked is what was played. With the same guest inputs the dump is deterministic up to host scheduling of the first granule. `apu_wav_write` does its file I/O under the APU lock (`d->lock`, which the frame thread holds except while it waits): a diagnostic-only cost, paid only while `RECOMP_AUDIO_WAV` is set; a slow disk then delays MMIO faults that need the lock. The watchdog's `_exit` skips `atexit`, so it calls `apu_wav_close_nowait` first (bounded wait on the WAV lock).
- Checks (`scripts/audio_check.py`, numpy only): duration against wall time (sample-rate ratio within 0.5 %); first non-silent sample; RMS per 100 ms window; zero-runs longer than 2 ms after the first sound (dropouts); clipping fraction; and against a reference: envelope cross-correlation to find the lag (bounded, 500 ms), then per-band spectral correlation of 1 s windows with thresholds in `analysis/golden/audio.json` (committed, like `golden.json`; the WAVs stay in `analysis/golden/audio/`, gitignored).
- Runner: `scripts/bench.sh` gains `BENCH_AUDIO=1`, which sets `RECOMP_AUDIO_WAV` into the run's log directory under the existing run lock and runs the checks after the run; the scenarios are the golden ones (`golden.json` `scenarios`), plus the pad presets that reach in-game sound (`@stage1`).
- Reference: `scripts/xemu_ref.py --audio` captures the private xemu instance's output on the Linux/Proton host. Primary route `SDL_AUDIODRIVER=disk` (`SDL_DISKAUDIOFILE` in the capture directory, passed with `flatpak run --env=`), which is deterministic and needs no PipeWire node; fallback `pw-record --target` on the node whose `application.process.id` is the private instance's child pid. The script already refuses to start when any `app.xemu.xemu` instance is running and only ever kills its own; that stays. Captures are game output: local, gitignored, never published.
- Unit tests (toolkit ctest, run under `tests/proton_run.sh` as today): `tests/apu_monitor` (the DSP frame reaches the submitted samples; pacing keeps the queue between low and high with a fake device), `tests/apu_wav` (dump format and finalisation), `tests/mmio_decode` extended with every instruction form the spike trace shows.

## Risks / Trade-offs

- [GP handshake hang] DSOUND init spins on something the stub never answers. -> Retired by the Phase 0 spike: the trace shows exactly which address spins (`RECOMP_WATCHDOG_SECS` + `RECOMP_THREAD_DUMP` name the spinning function). Decision 2 picks the fix; nothing later is started until it is chosen.
- [Decoder gap] An access form the x86-64 hook does not decode (`[APU] MMIO decode fail`) kills the title. -> The spike greps for the line; each missing form goes into `apu_mmio_hook.c` with a `tests/mmio_decode` case. The generated code is C compiled by MSVC/clang-cl, so the forms are few.
- [Fault cost] Every MMIO access is a VEH round trip (microseconds under Wine). DSOUND init issues thousands, steady state issues tens per frame. -> Counted in the spike (`[APUMMIO]` count and `RECOMP_TRACE_PROFILE` on the DSOUND functions); if steady state exceeds 1 ms per video frame, the constant-address accessor route (Decision 4, macOS (b)) is pulled forward.
- [FAudio under Proton] Device creation, buffer granularity or callbacks differ from Windows XAudio2. -> Phase 2 first task is a device smoke test under umu-run (`tests/xaudio2` against the real device, 1 s tone, WAV tap checked), before any pacing work.
- [A/V drift] Sofdec follows audio, the pacer follows the host clock. -> Measured in Phase 4 before `RECOMP_AC97_READY` defaults on; the vblank deviation's exit (vblank from present) is the long-term fix, not this change.
- [Guest RAM races] The frame thread reads voice structures the title is writing. -> Same as hardware; the VP reads each field once per frame and tolerates torn values the way xemu does. No new locking across guest RAM.
- [Toolkit scope] The fixes are upstream changes. -> All toolkit work is general (no title constants, env-tunable), tested with ctest, and on `audio/main` for one PR.

## Migration Plan

1. Phase 0 spike (one run on the Linux/Proton host, by the user or a sub-agent with run permission): `RECOMP_AC97_READY=1 RECOMP_APU_TRACE=1`. Decides Decision 2 and the decoder gaps. No code ships from it.
2. Toolkit fixes and tests (monitor path, pacing, WAV tap), runnable without the game.
3. Output and pacing tuned under Proton; harness scripts; xemu reference capture.
4. A/V sync measured; deviations registered; `RECOMP_AC97_READY` defaults on under Proton (`RECOMP_AC97_READY=0` opts out); non-MMIO hosts keep today's "unsupported on this host; ignored" line.
5. Golden audio thresholds committed; `bench-stays-current` rebuild and golden.

Rollback: unset the default (one line in `main.c`); every other piece is behind the flag or a test.

## Decisions from the user (2026-10-02)

1. GP handshake: if the spike shows DSOUND waiting on a GP-written command block, a title-specific override in `src/recomp_manual.c`, recorded as a deviation, is approved for the first audible build. The DSP56300 port stays the documented way out.
2. Latency: 43 ms is not enough. Task 4.6 targets about 20 ms worst case.
3. The spike (phase 1) runs on the Linux/Proton host through the audio sub-agent, under the run lock.
