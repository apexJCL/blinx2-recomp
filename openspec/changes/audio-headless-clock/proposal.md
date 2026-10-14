## Why

BLX-30: the first "real sound" Mac run (fps-pacing 8.10, `runs/pacing/flip/au-attract-{spin,sleep}/`) read a rate ratio of 1.0137 at spin and 1.0106 at sleep, against a tolerance of 0.005, with 20-24 SDL queue underruns in 80 s. Proton reads 1.0003.

**Root cause: that run never reached the speakers.** It ran with `RECOMP_HEADLESS=1` and removed `SDL_AUDIODRIVER` from the environment, expecting SDL's default driver. But `apu_sdl2.c` sets `SDL_AUDIODRIVER=dummy` whenever the run is headless and the variable is unset, so the log says `driver dummy ... [silent: no device output]`. The 1% is the SDL dummy driver's clock, not CoreAudio's.

Measured on 2026-10-11 (`runs/audio30/`), as an @attract A/B pair taken back to back, 45 s each, same binary:

| driver | rate ratio | underruns |
|---|---|---|
| dummy (headless default) | 1.01347 | 0 |
| coreaudio (real output, ADAM D3V at 48 kHz over USB) | 1.00071 | 0 |

A standalone probe (`runs/audio30/probe/drain.c`) that keeps the SDL queue between 1024 and 2048 frames, like `mcpx_apu_pace_step`, shows the same thing without the game. CoreAudio drains at 0.9996 of 48 kHz (the device's own crystal). The dummy driver drains at anything from 0.930 to 1.010, depending on the buffer size and the load. SDL3's dummy device (via sdl2-compat 2.32.72 on SDL 3.4.16) sleeps a fixed time per buffer, rounded to whole milliseconds, and never corrects for the sleep's overshoot. It is a sleep loop, not a 48 kHz clock.

The CoreAudio output therefore needs no fix. The headless runs do. They are every Mac golden, audio_check run and bench run. In them the APU's pacing (`mcpx_apu_pace_step` reads the queue depth) follows a clock that runs 1-7% off and moves with the load. So the guest mixes audio at a rate the real game never sees, the audio_check rate gate cannot be used on a Mac dump, and an A/B between two headless runs can differ only because the machine was busier.

## What Changes

- **A virtual 48 kHz device for SDL's dummy driver.** When the SDL backend opens the `dummy` driver, it stops queueing into SDL. Instead a small clock module (`apu_vclock.c`) plays the submitted samples against `CLOCK_MONOTONIC` at exactly 48000 frames a second. `xa2_queued_samples`, `xa2_samples_played` and the underrun detector read that clock. An empty queue lets the clock run on, as a device playing silence does. Real drivers (CoreAudio, PulseAudio, PipeWire) are unchanged.
- **A ctest** (`tests/apu_vclock`) for the clock with an injected time: steady drain, drain to empty and restart, no drift over a long run.
- **The harness note.** `cat/docs/env.md` already says `RECOMP_HEADLESS` forces the dummy driver. The env row now also says that a headless run with real output must name the driver (`SDL_AUDIODRIVER=coreaudio`), and that the dummy driver is clocked by the virtual device.

## Impact

- Toolkit: `src/apu/apu_sdl2.c`, new `src/apu/apu_vclock.{c,h}`, `src/apu/CMakeLists.txt`, new `tests/apu_vclock/`.
- cat: `docs/env.md` (the `SDL_AUDIODRIVER` row), this change, TASKS.
- Behaviour: headless POSIX runs only (the dummy driver). The guest's audio pacing in them now follows a true 48 kHz clock, so APU timing can shift slightly against the old dummy timing. The Metal goldens are the gate for that. Windowed Mac play, and any run that names a real driver, is unchanged.
- Windows/Proton (XAudio2, `apu_xaudio2.c`), the Deck and the Linux/Proton host: no code change. They are run only as a regression check.
- No new env key: this fixes a broken clock rather than adding a feature, so there is nothing to opt in to.
