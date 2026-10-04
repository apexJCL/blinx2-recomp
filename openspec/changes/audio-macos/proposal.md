## Why

The `audio` change made BLiNX 2 audible under Proton (x86-64 Windows) by trapping the APU's MMIO window and servicing each fault through the emulated MCPX APU. On macOS arm64 (the development host) the same title stayed silent: the fault decoder, the fault hook and the AC'97 write trap were x86-64/Windows-only, so `RECOMP_AC97_READY` was refused at boot. A two-route spike (`openspec/changes/audio/spike-results.md`, 2026-10-03) measured the alternatives and chose to keep the low-level model: the existing APU with SIGBUS/SIGSEGV trapping and an A64 decoder costs 2.16 us per trapped access on an M4 Max (about 1 ms per second of play in steady state), needs no lifter change, and serves future titles' DSOUND the same way.

## What Changes

- Toolkit: `src/platform/mmio_decode_a64.h`, the AArch64 twin of `mmio_decode.h` (si_addr gives the data address; the decoder reads width, direction, register, sign extension and writeback from the instruction word). `apu_mmio_hook.c` gains `apu_hook_handle_mmio_posix`; `xbox_memory_layout.c` arms the AC'97 bus-master write trap with `mprotect` and completes channel resets in `xbox_Ac97PosixFault`. Linux arm64 reads and writes the FP/SIMD registers through the `fpsimd_context` record in `uc_mcontext.__reserved` (compile-checked only; no Linux arm64 host here).
- Toolkit, shared APU model (found by the first speaker test, design.md "Findings"): `mcpx_apu_phys` resolves guest physical addresses above 64 MB to RAM up to the mapped size instead of folding them into the low 64 MB; `voice_resample` resamples by the voice's pitch instead of ignoring it; the frame thread produces no frame while the front end is trapped instead of a silent one. `apu_mmio_rd/wr` split 8-byte accesses; `[APU-VSTAT]` per-voice trace, `RECOMP_APU_SOLO`, `RECOMP_APU_VOICE_DUMP`. These change Proton's output as well and are verified there when the Linux/Proton host is back (tasks 5.3).
- cat: `scripts/audio_check.py` fails noise-like output (spectral flatness and high-frequency share per 1 s window; limits in `analysis/golden/audio.json`) and counts a zero run as a dropout only inside sound.
- Toolkit: `src/apu/apu_sdl2.c`, the POSIX device backend behind the `xa2_*` contract (`SDL_QueueAudio`, queue-depth pacing through `xa2_queued_samples`, the same `RECOMP_AUDIO_BUF_SAMPLES` x `RECOMP_AUDIO_BUF_COUNT` knobs). Headless runs (`RECOMP_HEADLESS=1`) take SDL's `dummy` driver unless `SDL_AUDIODRIVER` is set, so pacing and the WAV tap behave as with a device and nothing reaches the speakers.
- Toolkit: `qemu_clock_get_us`/`qemu_clock_get_ns` no longer overflow (`count * 1e6 / freq` with a nanosecond counter), which had the host-clock pacer and the `RECOMP_APU_TRACE` reporter running on a wrapped clock on POSIX.
- Toolkit: `tests/mmio_decode_a64` (real faults on a PROT_NONE page, exit 77 off POSIX arm64); the `[APU-IRQ]` trace line adds `se_frames` and `underruns`.
- cat: `src/main.c` routes APU-window and AC'97 faults from `posix_crash_handler` to the toolkit on POSIX arm64 (`HOST_CAN_SERVICE_MMIO`, `HOST_MMIO_POSIX`).

## Capabilities

### Modified Capabilities
- `audio`: the MMIO trapping requirement covers POSIX arm64 hosts; the pacing requirement names the SDL2 backend and its underrun line.

## Impact

- Hosts: macOS arm64 is audible; Linux arm64 compiles and should work (untested); x86-64 Linux is still refused (no x86-64 POSIX hook). Windows is untouched apart from the shared clock shim, whose results are identical where the old formula did not overflow.
- Branch `consolidate/env` (toolkit 5b1d8e9) makes `RECOMP_AC97_READY` default on for x86-64 Windows only and prints "audio unsupported on this host" elsewhere; when the two meet, `recomp_env.c`'s `default_on(values, RENV_AC97_READY, ...)` condition and the key's help text must include `!defined(_WIN32) && defined(__aarch64__)`, and `README.md`/`docs/pipeline/06-debugging.md` must say macOS arm64 is supported.
