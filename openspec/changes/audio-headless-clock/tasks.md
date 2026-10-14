## 1. Measure

- [x] 1.1 A/B on the Mac, @attract 45 s, dummy against coreaudio, same binary (`runs/audio30/base-{dummy,ca}`): 1.01347 against 1.00071.
- [x] 1.2 Standalone drain probe (`runs/audio30/probe/drain.c`): CoreAudio 0.9996, dummy 0.930-1.010 depending on the buffer size and load.

## 2. Toolkit

- [x] 2.1 `src/apu/apu_vclock.{c,h}`: a virtual 48 kHz device driven by an injected `now_ns` (design D2).
- [x] 2.2 `apu_sdl2.c`: on the dummy driver, pause the SDL device and route submit, queued, played and underrun through the clock (D1).
- [x] 2.3 `tests/apu_vclock` ctest: steady drain, dry then restart, no drift over an hour of jittered fake time.

## 3. cat

- [x] 3.1 `docs/env.md`: the `SDL_AUDIODRIVER` row (name the driver for real output, and the dummy driver is clocked).
- [ ] 3.2 TASKS.md entry (the orchestrator, at merge).

## 4. Gates

- [x] 4.1 Mac build, `tests/posix_ctest.sh` 0 FAIL (48 pass, apu_vclock 3 of 3; `runs/audio30/posix_ctest.log`).
- [x] 4.2 `uv run pytest scripts` (28 pass; test_gitignore fails only because a worktree's game_files is a symlink), ruff check and format.
- [x] 4.3 Ratio after (`runs/audio30/ab*`): dummy 1.00045 and 1.00025 (0.99909 in a run with two 23-30 ms frame-thread stalls under load), against 1.01203, 1.01059 and 0.99559 for the old binary in alternating pairs. Real CoreAudio on the new binary: 1.00053.
- [x] 4.4 Metal goldens, base vs new, interleaved (runs/audio30/ab-metal). Identical:
      attract-cliff fails on both with the same numbers (mae 0.528/0.547/0.510, bad
      0.1540%), the known BLX-84 re-record. story passes on 5 of 6 runs with
      story-menu identical (mae 0.807, bad 0.7487%); new1 was INCOMPLETE on host load.
      stage1 passes on new.
- [x] 4.5 `blinx2 bench golden` on the Linux/Proton host, and the Proton rate ratio. attract,
      stage1 and story pass; attract-cliff mae 0.471 and story-menu CLOSE. Proton
      ratio 1.00076 with 0 starves (XAudio2, unchanged path).
