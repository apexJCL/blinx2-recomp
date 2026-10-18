Worktrees: `wt/asynclog/cat` off `main` (e7c574c) and `wt/asynclog/xboxrecomp` off `posix-host/portability` (88874d6), both on a branch `fix/nv2a-trace-gate` (the spec is on `spec/async-log-writer`). No CLI change.

Raw Mac runs go in `xbox-recomp/runs/asynclog/`; the native Windows logs the user produces go in `xbox-recomp/runs/win11/<date>/`. Proton gates run on the Deck or the Linux/Proton host, whichever is up.

Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Mac runs are headless with `SDL_AUDIODRIVER=dummy`. The Linux/Proton runs go under `flock -w 3600 ~/.recomp-run.lock` (`blinx2 bench` takes it itself).

## 0. Spec review

- [x] 0.1 Written by the reviewer; revised 2026-10-14 after the user's answers (design.md Recommendation). No second pass before implementation.
- [ ] 0.2 Comment on the tracker items with the spec's commit sha and the gate list (`/tracker`).

## 1. Toolkit

- [x] 1.1 `src/kernel/xbox_memory_layout.c:3612`: `s_nv2a_trace` from `RENV_NV2A_TRACE` alone; the comment names 5b1d8e9 and says the executor reads its own key (D1).
- [x] 1.2 `xbox_memory_layout.c:1817`: the DMA_PUT line as one `snprintf` + `fputs`, same text; the `fflush` moves inside the `if`. The PCRTC line and `framebuffer_probe_tick` unchanged.
- [x] 1.3 `xbox_memory_layout.c:1787` and `src/kernel/nv2a_pb_exec.c`: the report gate from D1 (`nv2a` or `pb_scan` → `nv2a_pb_scan_report()`; else `fb_dump` → `nv2a_pb_exec_report_dump()`), with `nv2a_pb_exec_report_dump()` lifted out of `nv2a_pb_exec_report` and called by it.
- [x] 1.4 `src/kernel/kernel_bridge.c:4700` and `4767`: `[READ]` and `[WRITE]` under `RENV_FILE_TRACE` (a cached static like the other gates).
- [x] 1.5 `kernel_bridge.c:10826`: the periodic block under `RENV_KERNEL_SUMMARY`; `kernel_summary_report(why)` (print-once guard) registered with `atexit` and `recomp_exit_hook_add` at the first kernel call, called from `bridge_HalReturnToFirmware` beside `xbox_missing_summary("firmware")`, and from the watchdog report in `xbox_memory_layout.c` after the ICALL ring (D2). The block's text is unchanged, with `why` in its first line.
  - Done as `xbox_kernel_summary_report(why)` (kernel.h, the `xbox_kernel_*` naming of kernel_bridge.c's exports); the bugcheck paths in `kernel_hal.c` call it too, beside their `xbox_missing_summary("bugcheck")`.
- [x] 1.6 `src/platform/recomp_env.h`: the `FILE_TRACE` row (TRACE, `file`) and the `KERNEL_SUMMARY` row (TRACE, `kernel_summary`), help text from D2.
- [x] 1.7 Mac build, then `tests/posix_ctest.sh <build-dir>` with 0 FAIL.

## 2. Cat and docs

- [x] 2.1 `src/pad_input.c`: `log_host_state` and the rumble line under the `input` trace (the same cached check `trace_handles` uses); the `ports=`, scripted `buttons=` and `script done` lines stay. `scripts/vpad.py` docstring: the game side needs `RECOMP_TRACE=input`.
- [x] 2.2 `docs/env.md`: the `file` and `kernel_summary` rows, the reworded `nv2a` (with its Windows cost note), `pb_scan`, `pb_report_ms` and `input` rows, the `RECOMP_PB_EXEC` row's read sites; the intro's tier counts.
- [x] 2.3 `uv run pytest scripts`, then `uv run ruff check . && uv run ruff format --check .`.
  - 43 pass; `test_gitignore.py::test_the_dump_and_its_siblings_are_ignored` fails because `game_files` is a symlink in a worktree (`git check-ignore` refuses a path beyond a symlink); it fails the same way in `wt/deckbench/cat` at main.
- [ ] 2.4 `analysis/upstream/pr-stack-plan.md`: the arming fix and the one-call line under G2; the `[READ]`/`[WRITE]` gate and the exit-time kernel summary as a PR 3 offer; `file` and `kernel_summary` under fork-only; the deferred writer as its own PR if built (design.md D4).
  - `analysis/upstream/pr-stack-plan.md` is gitignored (untracked in the main checkout), so the edit is a proposed diff in `wt/asynclog/notes/pr-stack-plan.diff` for the orchestrator to apply.
- [ ] 2.5 TASKS.md (the orchestrator, at merge): the tracker item closed by this change; the deferred writer with its two triggers (design.md Recommendation) and the `xbox_kernel.log` note as follow-ups; the tracker item's native Windows figures before and after (the throwaway pair and the merged build's run).

## 3. Runs and gates

- [x] 3.1 Mac Metal: `blinx2 golden run` (attract, stage1, story) with `XBOXRECOMP_DIR` set; `audio-check` against the previous golden; the default-run log checks and the key checks of design.md Validation (`nv2a`, `kernel_summary`, `fb_dump` alone, `unimpl_trap`). Logs and the golden logs' sizes before and after in `runs/asynclog/mac/`.
  - `runs/asynclog/mac/`: golden attract/stage1/story PASS; golden logs 1.4/4.8/4.7 MB (runs/padslot, 2026-10-13 main) -> 0.77/2.0/3.0 MB (the rest is the `flip` trace the golden pins); audio-check stage1 PASS (median -31.7, max -18.3 dBFS) and attract PASS (-32.9/-24.8), as apulock measured. `default/`: no gated line, `[KERNEL] summary (exit)` last. `trace-nv2a-ks/`: 8.4k kick lines in 35 s, 19 periodic blocks, 3 `[GPU]` reports, `summary (watchdog)` in the hang report. `fbdump/`: 12 pictures, no `[GPU]`/`[PB]` text. `file-unimpl/`: `[READ]`/`[WRITE]` back; the `[UNIMPL]` line is the last game line.
- [x] 3.2 Proton (Deck or the Linux/Proton host): `blinx2 bench integrate --golden`; one run left to the watchdog with `RECOMP_DEBUG=watchdog` to see the kernel summary in its report.
  - Steam Deck (GE-Proton), exe from the Mac cross-build (cat 4e64f89, toolkit d08db85, sha256 6a619a75...): `blinx2 bench golden` tests pass (26 suites), attract/stage1/story PASS (bench-logs 20261014-141807, -141928, -142119), no gated line in their logs. Watchdog run (`RECOMP_DEBUG=watchdog=40`, bench-logs 20261014-142737): `[KERNEL] summary (watchdog)` in the hang report, exit 3 as designed.
  - Re-run on the review head (cat b13ed9b, toolkit 88e7936, exe sha256 91f770e1...): Proton tests pass (26 suites; `kernel_summary_report` is not in the CLI's Proton list), attract/stage1/story PASS (bench-logs 20261014-150546, -150706, -150858), no gated line. Mac at the same head: POSIX ctests 55 pass / 0 FAIL, Metal golden attract/stage1/story PASS (`runs/asynclog/mac/golden3/`), audio-check stage1 PASS (-31.6/-18.7 dBFS) and attract PASS (-33.1/-24.3) (`runs/asynclog/mac/audio3/`).
- [ ] 3.3 Native Windows, the user's PC: one 1-2 run of the merged build with `RECOMP_TRACE=pacing`, read with `blinx2 pacing-stats`; p95 within 1-1's band, the log size, the sound by ear; recorded on the tracker item with the throwaway pair. Flag a 25% flips/s drop or 1.5x frame-ms rise as a blocker.
- [x] 3.4 Burnout 3 under Proton on the exact toolkit head (sha in the notes): boot, front end, one race; the log ends with the exit lines and the kernel summary.
  - Toolkit 88e7936, b3 56574b4 with gen/ regenerated, own Deck tree `~/blx-bench-b3`, profile save copied from the Deck install. Proton (Deck, D3D11): boot -> menu -> Single Event race PASS, 57.5 flips/s in the race, no `[FAULT]` (bench-logs 20261014-151552). macOS/Metal: race_gate.py fast PASS, 54.4 flips/s (`runs/asynclog/b3/mac-gate/`).
  - Kernel summary: a b3 `--seconds` exit prints `[KERNEL] summary (exit)` on the Mac (exit()), but not under Proton, where b3's `run_end()` calls `ExitProcess` without `recomp_exit_hook_run()` (bench-logs 20261014-152442). SIGINT stops print none on either host. A b3-side follow-up; the toolkit's exit paths are as designed.
- [x] 3.5 Review, then fixes on the branch.
  - Fixes: toolkit 453fdf6 (the periodic report runs for its report-only keys too) and 88e7936 (`tests/kernel_summary_report` ctest for the once-only summary and the `[READ]` gate); cat b13ed9b (docs). Gates re-run on those heads (3.2, 3.4).

## 4. After the merge

- [ ] 4.1 Copy the branch notes to `notes/asynclog/`; copy any run RESUME, TASKS or golden.json cites to `runs/` with `cp -c`.
- [ ] 4.2 Remove the worktrees (`git worktree remove --force` plus `rm -rf wt/asynclog`), keep the branches.
- [ ] 4.3 Proton host: sync, rebuild, `blinx2 bench integrate --golden`; then TASKS.md.
