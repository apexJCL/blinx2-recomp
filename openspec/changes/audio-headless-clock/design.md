## Context

`mcpx_apu_pace_step` (toolkit `src/apu/apu_core.c`) paces the APU frame thread by the device queue. At or above the high mark it waits one EP period (256 frames). At or below the low mark it renders ahead. The queue depth comes from `xa2_queued_samples`. On POSIX hosts that is `SDL_GetQueuedAudioSize` in `apu_sdl2.c`, so the device's pull rate is the guest's audio clock.

With a real device, the pull rate is the device's crystal (0.9996 of 48 kHz on the test Mac). With SDL's dummy driver, the pull rate is a sleep loop: one buffer per `SDL_Delay`. That is 0.93-1.01 of 48 kHz in a standalone probe, and 1.0135 in the game at the default 512-frame buffer.

## Decisions

### D1. Replace the dummy driver's clock, not the pacing

Pacing by the queue is right for a real device, and the Proton path shares the same logic with XAudio2. Only the dummy driver's clock is wrong. So the fix lives in the SDL backend: when `SDL_GetCurrentAudioDriver()` is `dummy`, the backend keeps the SDL device open (so the init and shutdown paths are the same), pauses it, and never queues into it. A virtual device takes the samples.

Alternatives rejected:
- **Pace the APU by the host clock whenever the driver is dummy.** This takes the `apu_core.c` path with no queue, a second pacing model that the real hosts never run. A virtual queue keeps one model.
- **Set `SDL_AUDIO_DUMMY_TIMESCALE` or pick a buffer size that happens to land near 1.0.** The error depends on the load and on SDL's sleep, so no constant fixes it.

### D2. The virtual device

`apu_vclock` is plain C with no SDL, and every call takes the time `now_ns` as an argument, so the test can feed it a fake time.
- `submitted`: frames ever handed over.
- `anchor_ns`, `anchor_played`: the play position is `anchor_played + (now - anchor_ns) * rate / 1e9`, computed in 64-bit integer arithmetic from one anchor. So it never drifts, unlike a sum of per-call increments.
- **Dry:** when the position reaches `submitted`, the device has played everything. The position stops at `submitted` and the anchor moves to the time it ran dry. That is, it plays silence from then on, and the next submit starts playing at once.
- **Before the first submit** the device is dry. The first submit anchors at its own time.
- `queued = submitted - position`, and `played = position`.

This drains continuously, not one 512-frame buffer per callback. The pacing marks keep at least one buffer queued, and the underrun detector counts `queued == 0`, which a continuous drain reaches only when the guest really fell behind. So the detector's meaning is kept, and the old dummy's spurious underruns go away.

Thread safety: only the APU frame thread submits and queries (`mcpx_apu_pace_step` and the host stats in `apu_core.c`), so the clock takes no lock. `xa2_shutdown` does not touch it.

### D3. Scope

Only the dummy driver. A real driver keeps SDL's queue and its own clock, and the 1.0007 measured on CoreAudio stays. Windows (XAudio2) has no dummy path, because a headless Proton run plays through Wine's audio, so nothing changes there.

## Risks

- **Golden drift on the Mac.** The guest's audio IRQ cadence in headless runs changes from roughly 1.3% fast (and load-dependent) to exact. A golden that depends on audio timing could move. Mitigation: run the Metal goldens. A moved frame is judged against the Proton reference, which has always paced by a real device.
- **Speed.** The clock costs a `clock_gettime` per query, the same as today's `SDL_GetQueuedAudioSize` lock. No flips/s change is expected, and the goldens report flips/s.

## Verification

- `tests/apu_vclock` ctest, in `tests/posix_ctest.sh`.
- On the virtual path the `[AUDIO-HOST]` starve check reports only real dry spells (the frame thread falling behind), not the dummy driver's sleep jitter.
- An @attract A/B pair, old and new binary, dummy driver: ratio 1.0135 before, about 1.000 after.
- A real-output CoreAudio run on the new binary: still about 1.000 (the unchanged path).
- Metal goldens, `uv run pytest scripts`, and ruff.
- `blinx2 bench golden` on the Linux/Proton host as a no-change check. The rate ratio there should be 1.0003 as before.
