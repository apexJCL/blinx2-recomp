Worktrees:
- toolkit: `wt/xa2-depth/xboxrecomp` (branch `xa2-depth/queue` off `posix-host/portability`);
- cat: `wt/xa2-depth/cat` (branch `xa2-depth/spec`, this change).

How runs are done:
- Raw runs go under `xbox-recomp/runs/audio-wine-queue/`.
- Mac jobs run under `lockf -t 3600 ~/.recomp-mac.lock`, with `SDL_AUDIODRIVER=dummy` and `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- Deck runs need a slot from the orchestrator and go through the SSX 3 bench tree's `bench`.

## 0. Measure the count arms (no code)

- [x] 0.1 On the current build, using only the existing `RECOMP_AUDIO_BUF_COUNT` key, run arms A and B of design D3 (count 4 vs 6) with `RECOMP_TRACE=audio_host,apu_lock`. The priority arms wait for 1.x.
  1. Positive control first: loaded arm A must drain (an underrun, or `q_min` 0) in both runs. If it does not, raise the load as D3 says and re-run arm A before anything else.
  2. Then arm A idle x2, and arm B idle x2 and loaded x2.
  3. During one arm-A run, read the PipeWire quantum with `pw-top` (D4).

  Verification:
  - the D3 metrics table for A and B: `q_min` p1/p5 and seconds below 256, `gap_max_ms` p99 and max, underruns, frame-thread lock wait (total, max, waits over 10 ms), flips/s;
  - the load used;
  - the measured quantum.

  Result (2026-10-19, Deck, GE-Proton11-7, D3D11 at scale 2):
  - Build: the tree synced for the tracker item (recomp 82f7a42e on toolkit 08f8e5ee), which already has the count key.
  - Load: 7 busy loops. The positive control drained in both runs, so the load was not raised.
  - Quantum: the game's stream ran at quantum 256 (`pw-top`, ERR 0). The graph had `clock.quantum` 512 and `clock.min-quantum` 256.
  - Table: `analysis/golden/audio.json` (`about`).
  - Finding: count 6 removes the idle underruns, but under load it still drains, with 36 % fewer underruns than count 4. The frame thread's lock wait stays under 1 ms in every run, so cause (c) is ruled out.

## 1. Toolkit

- [x] 1.1 Move `XA2_BUF_SAMPLES_DEFAULT` and `XA2_NUM_BUFS_DEFAULT` out of the `_WIN32` block in `apu_xaudio2.c` into `apu_xaudio2.h`, and add `XA2_NUM_BUFS_WINE` and `xa2_default_buf_count(int under_wine)`.
  - `apu_sdl2.c` takes its defaults from the header.
  - `xa2_init` uses the resolver as the default, and its init line gains ` (wine default)` when that default applies.
- [x] 1.2 Name the thread: `qemu_thread_create` (`apu_shim.h`) calls `SetThreadDescription` through `GetProcAddress` with the name it is given.
- [x] 1.3 Add the priority key:
  - `recomp_env.h`: `X(AUDIO_THREAD_PRIORITY, CONFIG, "RECOMP_AUDIO_THREAD_PRIORITY", NULL, "audio: APU frame thread priority (normal, highest; Windows only)")`, and a DEBUG row `audio_thread_tc` that allows `time_critical`;
  - a parse function in `apu_xaudio2.h`;
  - `apu_core.c` calls `SetThreadPriority` after `qemu_thread_create` and logs the read-back value;
  - POSIX builds log once that the key is ignored.
- [x] 1.4 New header-only ctest `tests/xa2_defaults`, which builds on every host and is picked up by `tests/posix_ctest.sh`. Cases:
  - `xa2_default_buf_count(0)` is 4, and `xa2_default_buf_count(1)` is `XA2_NUM_BUFS_WINE`;
  - the pacing marks for 512 x 4, x 6 and x 8 (1024..2048, 1536..3072, 2048..4096);
  - the priority parse: `normal`, `highest`, `time_critical` with and without the DEBUG key, an unknown name, empty.
- [x] 1.5 Gates:
  - the Mac build;
  - `tests/posix_ctest.sh` with 0 FAIL, and `xa2_defaults` listed as passing, not n/a;
  - the Windows cross build;
  - the cross-built `xaudio2_test.exe` under Proton on the Deck, in the 2.x slot.

  Status (2026-10-19): 1.1-1.4 on toolkit `xa2-depth/queue` (8374ebd9, faed070a and the review fixes e7e8ce3e, on 4172ed25). Mac: `tests/posix_ctest.sh` 84 pass, 0 FAIL, `xa2_defaults` pass, on e7e8ce3e. The Windows build and `xaudio2_test.exe` cross-compile on the Mac with llvm-mingw (never on the Deck); the test runs under Proton in the 2.x slot.

## 2. Measure the priority route

- [x] 2.0 On the Deck with the 1.x build, check that `ps -L -o tid,nice,comm -p <pid>` shows `mcpx.apu_thread` (D2). If it does not, record how the thread is identified instead.

  Result (2026-10-19, e7e8ce3e, cross-built on the Mac):
  - `ps -eL` shows `mcpx.apu_thread` beside `ssx3_recomp.exe`.
  - `xaudio2_test.exe` under GE-Proton11-7 prints `XAudio2 regression: 0 failures`. `umu-run` swallows its stdout, so it was run with Proton's own `wine` on the same prefix.
- [x] 2.1 Arms C and D (design D3) on the 1.x build, with the same load and trace as 0.1, twice idle and twice loaded. Sample the APU thread's nice at t ≈ 60 s. Verification: the D3 table is complete for all four arms.

  Finding (2026-10-19): `highest` does not reach the Linux scheduler on the Deck.
  - The game logs `[APU] thread priority highest (read back 2)`, so the Win32 call succeeds.
  - `mcpx.apu_thread` still has nice 0, the same as the main thread.
  - The cause is that the `deck` user's `RLIMIT_NICE` is 0. Only the `gamemode` group gets `nice -10` (`/etc/security/limits.d/10-gamemode.conf`), and the user is not in it. Wine lowers a thread's nice for a raised Win32 priority only when `RLIMIT_NICE` allows it.
  - Raising that limit (the group or limits.d) would be a system change. Decided by the user (2026-10-19): the Deck's limit stays as stock. The priority key is not needed there, since 6 buffers is clean in normal play and the loaded arms were a synthetic stress test where the whole process loses CPU; the key stays an opt-in for native Windows.
  - So C and D ran loaded only (C ×2, D ×2), plus a same-build arm A (`Ae`) for parity with 0.1. The idle C and D arms were not run: with nice unchanged they would repeat A and B, and idle was not the problem in 0.1 (orchestrator, 2026-10-19).
  - D3 step 3 then adds arm E (count 8, normal), twice loaded and twice idle.

  Results: C ×2, D ×2, Ae and E ×4 on e7e8ce3e, in `analysis/golden/audio.json` (`about`). Raw rows are in `runs/audio-wine-queue/table02.tsv`.
- [x] 2.2 Rule D3 ends at step 3 with the floor reached (design D3 outcome).
  - `XA2_NUM_BUFS_WINE` stays 6. It is the smallest count with a clean idle long bench. Count 8 is eligible, but it also drains under load and adds 21 ms of lag. No toolkit change was needed.
  - Priority does not win, so there is no `xa2_default_priority`. The key stays opt-in, defaulting to `normal`.
  - The spec delta and proposal are amended, and D4 records the measured quantum and the unmeasured FAudio period.

  The rule as planned:
  - set `XA2_NUM_BUFS_WINE` (4, 6 or 8, within the D4 budget); the env text in `recomp_env.h` and `docs/env.md` names the macro, so only the define and the spec change;
  - if priority wins, add `xa2_default_priority(int under_wine)` with its tests and the ` (wine default)` log line;
  - amend this change's spec delta and proposal to match the outcome;
  - record the table in `analysis/golden/audio.json` (`about`).

## 3. Gates and merge

- [x] 3.1 BLiNX 2 golden on Metal (`blinx2 golden`) and under Proton (`blinx2 bench golden`). Verification: the verdicts are unchanged from main.

  Result (2026-10-19, toolkit e7e8ce3e, no count key):
  - Metal: attract, stage1 and story pass (45.3, 34.1 and 53.8 flips/s).
  - Deck D3D11: attract, stage1 and story pass. Flips/s were 31.5, 30.6 and 47.0, against 31.7, 30.7 and 47.0 on the integrate golden.
  - Each Deck run logs `6 x 512` with `(wine default)` and has 0 underruns (bench-logs 20261019-034553, -034713, -034904).
- [x] 3.2 Burnout 3 golden under Proton and on Metal. Verification: unchanged.

  Result (2026-10-19, b3 47f7fdd on e7e8ce3e):
  - Metal `race_gate.py` passes, at 54.1 race flips/s.
  - Deck D3D11 race: race reached, 57.9 race flips/s (58.8 overall), against 57.8 on the gate.
  - Present check: 0/28397 flips mismatched.
  - The run logs `6 x 512` with `(wine default)` and has 0 underruns (bench-logs 20261019-031632).
- [x] 3.3 SSX 3 long bench under Proton on the final defaults, once idle and once loaded. Verification:
  - idle: no `[XA2] underrun` and no second with `q_min` below 256;
  - loaded: fewer underruns than every count-4 loaded run (947 was the lowest). Every count drains under the synthetic load, so this is the step-3 floor rule D3 reached. The planned bar, `q_min` p1 above 0, was not met at 6 or at 8;
  - flips/s within 25 % of idle arm A.

  Result (2026-10-19, e7e8ce3e, no count key, `6 x 512` with `(wine default)` logged; rows in `runs/audio-wine-queue/gates/table03.tsv`):
  - Idle (20261019-032447): 0 underruns, 0 s below 256, `q_min` p1 1536, 60.0 flips/s.
  - Loaded (20261019-033512): 538 underruns, under 947; 45.6 flips/s, within 25 % of 60.0.
  - Lock wait was 0 in both runs.
- [x] 3.4 cat `docs/env.md`:
  - a row for `RECOMP_AUDIO_THREAD_PRIORITY` and one for `audio_thread_tc`;
  - the `RECOMP_AUDIO_BUF_COUNT` row notes the Wine default, and its source citation (`apu_xaudio2.c:83`) is updated to the new location.

  Then `uv run pytest scripts` and the ruff checks.
- [ ] 3.5 Review, then squash merges (the toolkit to `posix-host/portability`, then cat) and the post-merge Deck golden. TASKS gets:
  - the merge entry;
  - follow-ups for POSIX APU-thread priority and naming (`pthread_setname_np`; backends agree) and MMCSS "Pro Audio" on native Windows;
  - a native-Windows run when the user next boots it.
