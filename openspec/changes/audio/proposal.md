## Why

There is no audio for this title. Disc audio is CRI ADX/AIX, decoded by translated CRI code into DSOUND buffers; the translated XDK DSOUND drives the MCPX APU through MMIO at `0xFE800000`, which is a zeroed aperture today, so the writes vanish and the free-space polls on `0xFE820010` would spin for ever if DirectSoundCreate got that far (it does not: the AC'97 codec reports not ready and DSOUND fails with DSERR_NODRIVER). `run-under-proton` task 3.3 (`RECOMP_AC97_READY=1`) has never been run. FMVs are CRI Sofdec with audio as the master clock, so until audio exists the movies have no clock to follow.

## What Changes

- On x86-64 Windows (Proton): the APU MMIO window trapped through the VEH and serviced by toolkit `src/apu` (xemu's VP; GP/EP stubbed), output through XAudio2 (FAudio under Proton), paced by the device queue. `RECOMP_AC97_READY=1` becomes the default on those hosts once pacing and A/V sync are measured; `=0` opts out.
- Toolkit fixes: the monitor path discards the DSP frame today (every hardware voice is silent even when the APU runs); queue-depth pacing; tunable buffer sizes; a WAV dump tap.
- Test harness: `RECOMP_AUDIO_WAV`, `scripts/audio_check.py`, `scripts/av_sync.py`, `bench.sh BENCH_AUDIO=1`, `xemu_ref.py --audio` (private instance only), thresholds in `analysis/golden/audio.json`.
- Deviations registered: GP/EP bypass (no reverb or 3D), stereo mixdown of every bin, host-paced audio clock, infinite PIO FIFO.
- macOS arm64 has no MMIO trapping, so no audio there; the design names the routes for a later change.

## Capabilities

### New Capabilities
- `audio`: audible, paced output of the translated DSOUND/APU path on Proton, with a deterministic dump and scripted checks.

### Modified Capabilities
- `deviations`: four new deviations (GP/EP bypass, stereo mixdown, host-paced clock, PIO FIFO).

## Impact

- cat: `src/main.c` (default flag, deviation comments), `scripts/bench.sh`, `scripts/audio_check.py`, `scripts/av_sync.py`, `scripts/xemu_ref.py`, `analysis/golden/audio.json`, `.gitignore`.
- toolkit (`audio/main`): `src/apu/apu_core.c`, `apu_xaudio2.c/.h`, `apu_dsp.c`, `apu_mmio_hook.c`, `apu_state.h`, new `apu_wav.c`, tests `tests/apu_monitor`, `tests/apu_wav`, `tests/mmio_decode`. All general, upstreamable.
- Depends on `run-under-proton` (the Proton run path and `tests/proton_run.sh`) and `fmv-playback` 2.1/3.2 (movie open/close log lines) for the A/V measurement.

## Status

In progress (reviewed 2026-10-06 in the openspec cleanup). The audio path is merged and on by default under Proton and on macOS arm64: the spike, the toolkit output path (phase 2), the GP doorbell ack (now `RECOMP_APU_DSP_ACK=auto`), APU interrupt delivery, `audio_check.py` with `audio.json`, and the default (7.1). The macOS arm64 port (`audio-macos`, archived) folded its spec text into this change's delta. Later fixes landed outside this change: the vblank pacer that every waiter wakes on (the Proton speech cutoff), the voice-cutoff checks, and the menu-music finding (an incomplete dump, not a runtime bug).

Still open, and the reason this change is not archived: the measured buffer defaults and the ~20 ms latency target (4.2, 4.3, 4.6), the steady-state rate measurement (4.4), `BENCH_AUDIO` in `bench.sh` (5.3), xemu reference audio (5.4, 5.5), A/V sync against the Sofdec clock (6.x) and the close-out (7.2-7.5). Archive when those are done or explicitly dropped; the requirements for them are still in the delta.
