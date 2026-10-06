## MODIFIED Requirements

### Requirement: APU MMIO is trapped and serviced on hosts that can decode faults
On an x86-64 Windows host (including Proton) and on a POSIX AArch64 host (macOS arm64; Linux arm64 by construction, untested), when `RECOMP_AC97_READY` is in effect, the host SHALL map the APU window `0xFE800000..0xFE87FFFF` so that every guest access faults, SHALL decode the faulting instruction (`mmio_decode.h` from the VEH record on Windows; `mmio_decode_a64.h` from the SIGBUS/SIGSEGV ucontext on POSIX) and service it through the emulated APU (`mcpx_apu_read`/`mcpx_apu_write`), and SHALL resume the guest after the instruction. The AC'97 bus-master page SHALL be write-trapped the same way so a channel reset completes on the write. The boot log SHALL contain `APU: ... trapped for MMIO` and `[BOOT] emulated APU up`. An access the decoder cannot service SHALL be logged as `[APU] MMIO decode fail` with the instruction bytes, and SHALL be treated as a bug, not skipped silently.

#### Scenario: DSOUND initialises against the emulated APU
- **WHEN** the title runs under Proton, or headless on macOS arm64, with `RECOMP_AC97_READY=1 RECOMP_APU_TRACE=1`
- **THEN** the log contains `[APUMMIO]` writes to the EP reset (`0x5FFFC`), the voice-list registers (`0x2054..0x2074`) and PIO methods (`0x202F8` onwards), followed by `[APU] started by the title`, and contains no `[APU] MMIO decode fail` line

#### Scenario: Host that cannot service MMIO
- **WHEN** the title runs on a host without fault decoding (x86-64 Linux) with `RECOMP_AC97_READY=1`
- **THEN** the boot log says `RECOMP_AC97_READY is unsupported on this host ...; ignored`, the APU window stays a zeroed aperture, and the title boots as before

#### Scenario: A64 decoder is tested against real faults
- **WHEN** `tests/mmio_decode_a64` runs on a POSIX arm64 host
- **THEN** every covered load/store form (byte to quad, signed, pre/post-index, register offset, pairs, SIMD&FP) is serviced with the right width, direction, register and writeback, and the exclusive form is refused; off POSIX arm64 the test exits 77 (skipped)

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
