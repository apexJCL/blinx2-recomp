Worktrees: `wt/apulock/cat` off `main` (3e22f85) and `wt/apulock/xboxrecomp` off `posix-host/portability` (9ffdb52). Both are on `fix/apu-lock-hold`. The CLI test-list change goes in `wt/apulock/xboxrecomp-cli` off `main` on the same branch name.

Raw Mac runs go in `xbox-recomp/runs/apulock/`. The Linux/Proton scratch tree is `~/xbox-recomp-apulock`.

Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Mac runs are headless, with `SDL_AUDIODRIVER=dummy`, under `notes/mac-run-lock.sh`. The Linux/Proton runs go under `flock -w 3600 ~/.recomp-run.lock` (`blinx2 bench` takes it itself).

## 0. Spec review

- [x] 0.1 This spec was not written by the reviewer. The reviewer reads it, improves it and commits the revision on the spec branch.
- [x] 0.2 Implementation starts only from the revised commit.

## 1. Measurement (done before the spec)

- [x] 1.1 Toolkit trace `RECOMP_TRACE=apu_lock` (`src/apu/apu_lockstat.{c,h}`, `APU_LOCK_TRACE` row): hold, wait and se_frame stage histograms. Committed as toolkit 1c2c233; its `docs/env.md` row is in the spec commit.
- [x] 1.2 Proton 5-1 idle with the APU trace (`bench-logs/20261012-125300`, `20261012-125657`) and without it (`20261012-130003`). Mac Metal with the APU trace (`runs/apulock/m-before-51`) and without it (`runs/apulock/m-lockonly-51`). Figures are in design.md.

## 2. Toolkit

- [x] 2.1 `src/apu/apu_shim.h`: `qatomic_or64`, `qatomic_and64` and `qatomic_load64`, with `_InterlockedOr64`/`_InterlockedAnd64` under `_MSC_VER` and `__atomic_*` otherwise (D1). A comment says why the existing `qatomic_or` cannot serve a 64-bit word on MSVC.
- [x] 2.2 `src/apu/apu_vp.c`: `voice_lock` as an atomic or/and with no `d->lock` and no cond signal; `is_voice_locked` through `qatomic_load64` (D1, D2). The comment says why: posted PIO writes; the VP does not read the bit; xemu's wait that the port dropped (link the xemu lines); the RMW race that option C would close.
- [x] 2.3 `src/kernel/kernel_prof.h`: a one-line note that `XBOX_PROF_WAIT_APULOCK` has had no caller since this change and is kept for log comparability (D1).
- [x] 2.4 `src/apu/apu_vp.c` and `apu_core.c`: the 64 KB trace buffer with its dropped-lines marker, `vp_trace_positions`, `vp_stat_report` and the ring monitor's lines through it, and `mcpx_apu_vp_trace_flush()` called after the frame thread's per-frame unlock beside `apu_lockstat_flush()` (D3).
- [x] 2.5 Lockstat trace (task 1.1): update its header comment for D1 (the voice path no longer takes the lock, so the `voice` holder and taker lines are gone; `APU_LOCK_VOICE` can go or stay as a reserved name). Keep the `xa2` stage: it is what shows the Wine XAudio2 submit cost.
- [x] 2.6 `tests/apu_voice_lock/`: built on `tests/apu_lifecycle`'s bring-up (`mcpx_apu_init_standalone`, fake RAM, fake `xa2_*`), with `VPVADDR` set into the fake RAM. The no-wait, no-lost-update and no-wake cases as design.md Validation describes them (case 3 counts early returns). Run the negative control on the old `voice_lock` and record its output in the branch notes.
- [x] 2.7 Mac build, then `tests/posix_ctest.sh <build-dir>` with 0 FAIL.

## 3. CLI and cat

- [x] 3.1 `xboxrecomp-cli`: add `apu_voice_lock` to the standalone list in `bench/host/tests.sh` and to the step text in `bench/__init__.py`. Then `uv run pytest tests` and the ruff checks.
- [x] 3.2 `docs/env.md`: the `apu_lock` row (spec commit). After 3.1 lands, the `game.toml` pin moves to its sha. The orchestrator moves the pin at merge.
- [x] 3.3 `TASKS.md` (the orchestrator does this at merge):
  - correct the figures (trace-inflated; about 11 ms/s, 0.37 ms per frame, without the trace) and say it is not the cause;
  - add follow-up: VP cost, 78 us per se_frame on the Linux/Proton host against 26 us on the Mac (12% of a core under Proton; the hypothesis list from design.md Non-goals). Ask the orchestrator to file it as the next lead;
  - add follow-up: option C, the VP honouring `voice_locked`, with the RMW race it closes.
- [x] 3.4 `analysis/upstream/pr-stack-plan.md`: add the lock-free `voice_lock` and its ctest to PR 6 (APU), and the trace flush with it; the `apu_lock` trace to PR 8 as a maybe.
- [x] 3.5 `uv run pytest scripts`, then `uv run ruff check . && uv run ruff format --check .`.
  43 pass; ruff check and format clean. `test_gitignore` fails only because `game_files` is a symlink in this worktree (`fatal: pathspec 'game_files/default.xbe' is beyond a symbolic link`, exit 128).

## 4. Runs and gates

- [x] 4.1 Mac Metal, 5-1 idle and Mission 1-2: `[APU-LOCK]` and `[APUMMIO-STATS]` before and after, plus flips/s and frame ms.
- [x] 4.2 Proton on the Linux/Proton host: the same runs, with and without `RECOMP_TRACE=apu`. Check that the voice taker line has gone, that the hold max stays under 1 ms with the APU trace, that the handler us/access has fallen (with the trace, and at the 0.55 us floor without), and record `pace_waits` before and after as measured.
  Done (branch notes, the Linux/Proton host section): voice line gone in all four after runs; hold max with the APU trace 0.95 ms (5-1) and 1.05 ms (Mission 1-2), down from 48.4 ms and 4.5 ms; us/access 9.43 -> 0.03 and 5.53 -> 0.06 with the trace (without it the toolkit prints no `[APUMMIO-STATS]`, so the floor is the Mac figure only); `pace_waits` per 5 s 4953 -> 937 and 1370 -> 938. 30.0 flips/s in every after run, no perf flag.
- [x] 4.3 `blinx2 bench tests` under Proton includes `apu_voice_lock`, with 0 FAIL.
- [x] 4.4 Goldens:
  - Metal: `./blinx2 golden run` with `XBOXRECOMP_DIR` set;
  - D3D11: `blinx2 bench golden`;
  - `audio-check` on the golden runs, against the previous golden's figures. Any movement reopens option C before merge.
  Done: Metal attract/stage1/story pass; D3D11 pass on 45713c4 (bench-logs 20261012-175506, -175626, -175816); audio-check before/after on the Mac, no movement.
- [x] 4.5 Burnout 3 under Proton on the exact toolkit head (sha in the notes): vehicle select and one race (the old `voice_lock` freeze path), with an `[APU-LOCK]` excerpt.
  Done on toolkit 45713c4 (bench-logs/20261012-180059): race reached, 14559 race flips at 57.4/s, no fault, 0/29234 present mismatches; frame holder max 246 us with no contention around the one mid-race 520 ms gap (flip 22538, t=383 s), which is not d->lock.
- [x] 4.6 Steam Deck: ask the user for one before/after pair in 5-1 idle (`RECOMP_TRACE=apu_lock`, flips/s). If it cannot happen before merge, the Deck figure in the proposal stays a projection and TASKS says so. Done 2026-10-13 (runs/apulock-deck/): voice-lock wait 8.5 ms/s (0.28 ms per frame) to 0, pace_waits 6400 to 938 per 5 s, flips/s locked at 30.0 on every arm.
- [x] 4.7 Review, then fixes on the branch.
