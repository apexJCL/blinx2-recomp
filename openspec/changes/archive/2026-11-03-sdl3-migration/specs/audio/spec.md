## MODIFIED Requirements

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
