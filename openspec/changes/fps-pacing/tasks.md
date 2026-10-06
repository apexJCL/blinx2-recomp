Worktrees: `wt/pacing/cat` and `wt/pacing/xboxrecomp`, both on `feat/fps-pacing` (cat off `main` 4228612, toolkit off `posix-host/portability` 81be009). The default flip (section 9) gets its own branch, `feat/fps-pacing-default`, in both repos. Raw runs go to `xbox-recomp/runs/pacing/`, bench runs to `bench-logs/`, and neither ever goes inside a worktree. Build on the Mac with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. On the Mac, runs are headless with `SDL_AUDIODRIVER=dummy`.

## 0. Spec review (before any code)

- [x] 0.1 Fable reads this change (proposal, design, the specs) and improves it in place: thresholds (D8), the open questions, and the upstream shape. Fable commits the revision on `feat/fps-pacing` (2026-10-06; design.md "Decided").
- [x] 0.2 The implementing agent resumes only from Fable's revised commit, and states which open questions the user or Fable answered (all six are in design.md "Decided"; none went to the user).
  Resumed from 3e420a0; the six open questions are all answered in design.md "Decided" (Fable), none by the user.

## 1. Toolkit: the nanosecond vblank clock (D2)

- [x] 1.1 Add `xbox_HostNowNs` and `xbox_HostSleepNs` to `src/platform`: QPC with a high-resolution waitable timer (falling back to `Sleep`) on Windows, `CLOCK_MONOTONIC` with `nanosleep` on POSIX. Comments say why: the 15.6 ms Windows tick, and Wine.
- [x] 1.2 Factor the schedule into a pure function exported via `kernel.h`: epoch, count, the ns due time, the 100 ms restart. `kernel_vblank_tick` returns ns to the next edge, and keeps the `PCRTC_INTR_EN_0` hold, `g_vbl_tick_busy`, the arm-ack on claimed and declined vblanks, and the 600-vblank line format.
- [x] 1.3 Timer loop: sleep with `xbox_HostSleepNs` to the earliest of the vblank edge, the next kernel timer due and the 10 ms cap. Cap the next sleep at 1 ms after a gate-busy drain that leaves DPCs queued. Keep the profiler's `SLEEP_OVER` (µs) and `N_LOOPS` counters.
- [x] 1.4 `RECOMP_DEBUG=vblank_clock=ms` restores the previous loop exactly: a row in `recomp_env.h`, and the `docs/env.md` row in 7.1.
- [x] 1.5 New ctest `tests/vblank_schedule` (POSIX and Windows): a steady grid, a 50 ms late tick, a 150 ms stall restart, no drift over 10⁶ vblanks, and an epoch near 2⁶² ns (a host up for years). Runs on the Mac and under Proton (`tests/proton_run.sh`).
- [x] 1.6 cat `src/recomp_manual.c` uses the toolkit's `xbox_HostNowNs` and `xbox_HostSleepNs` instead of its own copies. The behaviour of `sub_002E0DB0` does not change.

## 2. Toolkit: the sleeping wait (D4, D5)

- [x] 2.1 `src/kernel/kernel_pacing.c` and `.h`:
  - `g_xbox_spin_sleep`, `xbox_PacingSetMode`, `xbox_SpinWait(va)` (generation counter read only under the wait's lock, condition variable, a 1 ms timeout, no sleep at DISPATCH or while holding the gate) and `xbox_SpinWake()` (lock, increment, unlock, broadcast);
  - `xbox_IrqlThisThreadBlocksDpcs()` in `kernel_hal.c`, from the existing thread-locals `t_irql_counted` and `t_dispatch_gate_held`;
  - per-site atomic counters in a fixed table with an "other" bucket;
  - in-wait CPU (the thread's CPU clock across the wait) sampled on one call in 64 and scaled, plus the thread's total CPU for the summary.
- [x] 2.2 Wake points: the timer-thread pass (when it raised a vblank, ran a DPC or fired a timer), `xbox_IrqlLeaveInterrupt`, the executor's fence write and the ack tick's `0x400B10` update. Each costs one load at `spin`.
- [x] 2.3 `templates/runtime/recomp_types.h`: `RECOMP_SPIN_WAIT(va)`, with the declarations.
- [x] 2.4 New ctest `tests/spin_wait` covering:
  - the immediate return at `spin`;
  - the timeout bound with no signal;
  - no lost wake (a signal between the read and the wait);
  - the DISPATCH skip;
  - counters;
  - two waiters both woken by one signal.

  Mac and Proton.
- [x] 2.5 The `pacing` trace (D7):
  - the flip timestamp in ns at the executor's flip (`nv2a_pb_exec.c`, the `[GPU] flip` point);
  - the summary every 600 flips with process CPU (`GetProcessTimes` or `getrusage`) and per-site lines (counters, in-wait CPU, thread CPU);
  - `pacing=all` per-flip lines;
  - a `recomp_env.h` row.

## 3. Toolkit: generator detection (D3)

- [x] 3.1 `tools/recomp`:
  - the matcher in the block pass, run on every emitted body that contains the VA;
  - `--spin-waits FILE` (`auto`, `sites`, `exclude`);
  - the back-edge emission;
  - the error for a listed non-candidate, naming the VA, the body and the rule (a site must match in every body that contains it);
  - the `spin_waits.json` report in the `-o` directory.

  Nothing runs without the flag.
- [x] 3.2 `tools/recomp/test_spin_waits.py`: the positive and negative shapes, both selection modes, the listed non-candidate error, the byte-identical no-flag output, and a compile check of an emitted back edge. All cases are synthetic, with no title addresses.
- [x] 3.3 `pytest tools/recomp tools/disasm` is green on the Mac.
- [x] 3.4 Docs: `docs/pipeline/04-lifting.md` gets a section on the flag, the file format and the report.

## 4. Toolkit: the `present.pacing` key (D6)

- [x] 4.1 `src/enhance/enhance.c`:
  - read `present.pacing` as a choice (`spin`, `sleep`), defaulting to `spin`;
  - call `xbox_PacingSetMode`;
  - add `present.pacing=` to the `[ENHANCE]` line before `(display.aspect=...)`;
  - add the `RECOMP_PRESENT_PACING` row to `RECOMP_ENV_ENHANCE_KEYS`.
- [x] 4.2 Move `enhance_cfg_report_unused()` out of `xbox_enhance_init` and into the title, after its own keys. Update `enhance.h` and `docs/runtime/enhance-config.md`: the key table, the env table, the `[ENHANCE]` example, the `fps.mode` row with `RECOMP_FPS_MODE`, and the report-unused order.
- [x] 4.3 `tests/enhance_cfg`: a case for `present.pacing` from the file and from the environment, and one for a bad value.
- [x] 4.4 Toolkit commits follow `area: what changed`, one per part (platform, kernel clock, kernel pacing, recomp, enhance, docs), with author `the local identity` and the Co-Authored-By trailer.
  Deviation: the kernel clock, the pacing wait and the trace are one commit (e4740b4), not two; they share kernel_bridge.c and the ctests.

## 5. cat: `fps.mode`, the site list, scripts

- [x] 5.1 `src/env/recomp_env_game.h`: `FPS_MODE`, CONFIG, `"RECOMP_FPS_MODE"`. `src/main.c` `host_enhance_init`:
  - `enhance_cfg_bind_env("fps.mode", RENV_FPS_MODE)`;
  - read the choice, then print `lock30` or the one-line "not available ... using lock30";
  - call `enhance_cfg_report_unused()`.
- [x] 5.2 `config/spin_waits.json`: `auto: false`, `sites: [0x00060475]` with a note. `blinx2.py`: `recomp_cmds()` gains `--spin-waits`, and `gen_inputs()` gains the file. `scripts/test_blinx2_cli.py` covers the new input and argv.
- [x] 5.3 `scripts/golden.py`:
  - check `present.pacing` and `fps.mode` in `enhance_nonstock`;
  - add `--allow-enhance KEY=VALUE` (evaluation only; refused with `record`);
  - add `scripts/test_*.py` cases.

  `analysis/golden/golden.json` env gets `RECOMP_PRESENT_PACING=spin`.
- [x] 5.4 `scripts/pacing_stats.py` (stdlib) and `scripts/test_pacing_stats.py` (synthetic logs: percentiles, the 3D filter, both flags).
- [x] 5.5 `scripts/bench.sh pacing`: an A/B under one lock with the running-game check, three runs each, alternating, the report into `bench-logs/<stamp>/`. Add a `scripts/test_*.py` case for its argument handling if bench.sh tests exist for other commands.

## 6. cat: regenerate `gen/` (D10)

- [x] 6.1 Snapshot the current `gen/` hash (`bench.sh`'s gen hash) for the diff.
- [x] 6.2 With `XBOXRECOMP_DIR=…/wt/pacing/xboxrecomp`, run `scripts/pipeline.sh analyze`, then `scripts/pipeline.sh recomp`.
- [x] 6.3 Diff against main's `gen/`: the only changed lines contain `RECOMP_SPIN_WAIT(0x00060475u)`, on every body that has `loc_00060475`. The count must equal the number of `loc_00060475:` labels (261 on main today: 124 in `recomp_0010.c`, 137 in `recomp_0011.c`). Keep the recomp report's candidate list in `notes/pacing/` (untracked) for later lists.
- [x] 6.4 Confirm `blinx2 package --plan` (or its equivalent) names `toolkit`, `argv` and `config/spin_waits.json` as the stale reasons before regeneration, and none after.
  Checked with `blinx2.gen_stale_reasons()` (what `package` plans from): after a later toolkit commit it said `toolkit changed`; after `analyze` + `recomp` at toolkit 21b78c7 it says nothing, and gen/ is byte-identical to the first regeneration (hash 05a4954a...). The orchestrator's regeneration in main (11.3) clears it again after the merge.
- [ ] 6.5 `config/setup-pins.json`: set to the toolkit head that is being merged, as the last cat commit before merge.
  Open: the pin names the public toolkit (`apexJCL/xboxrecomp` `blinx2/portability`), whose commits only exist after the scrub and push, so it is set at merge time, not on this branch.

## 7. Docs

- [x] 7.1 `docs/env.md` rows:
  - `RECOMP_PRESENT_PACING` (enhancements layer; golden pins `spin`);
  - `RECOMP_FPS_MODE` (game; `lock60`/`free` unavailable, with the reason);
  - trace `pacing` (`=all`);
  - debug `vblank_clock=ms`.

  Update the tier counts and the enhancements-layer sentence.
- [x] 7.2 The README or docs entry for players: what `present.pacing = "sleep"` does, and that 60 fps is not available and why (a short paragraph pointing to the spike's finding).
- [x] 7.3 `TASKS.md` follow-ups:
  - D3D11 honouring the existing `RECOMP_PRESENT_VSYNC` as the SDL and Metal presenters do (backend parity; no new key);
  - the `sub_002E0DB0` pacer on the kernel's vblank edges (design "Decided", 3; small after 1.6, needs `audio_check.py` on both hosts);
  - the stage-loader yield loop;
  - more spin sites from the report.

## 8. Verification (feature branch, at `spin` unless noted)

- [x] 8.1 Mac build (cat and toolkit, Metal and CPU). Toolkit POSIX ctests including `vblank_schedule`, `spin_wait` and `enhance_cfg`. `pytest tools/recomp tools/disasm`. cat `scripts/test_*.py`.
- [x] 8.2 the Linux/Proton host (`bench.sh` from the worktree): mingw build, and Proton ctests via `tests/proton_run.sh`.
- [x] 8.3 Metal goldens `@attract`, `@stage1`, `@story` on the regenerated build: the same verdicts as main.
- [x] 8.4 Proton D3D11 goldens (`bench.sh golden`, which takes the run lock itself; BLiNX first): the same verdicts as main.
- [x] 8.5 Clock gate (D8): `@stage1` with `RECOMP_DEBUG=vblank_clock=ms` against the ns clock, both at `spin`, three runs each with at least 1,000 3D flips after the checkpoint, on Metal and Proton D3D11 (`bench.sh pacing` with the two environments; Mac via `pacing_stats.py`). Record every 600-vblank window and the 3D interval p5/p50/p95/max per run. Gate (medians of three): p95 − p5 at most half the ms arm's; p50 within 33.3 ± 0.5 ms on both arms; median window spread at most 3 ms and at least 80% of windows within 16.67 ± 1.5 ms, load and restart windows listed and excluded.
  Metal: PASS (p95-p5 0.14 vs 5.64 ms; p50 33.33 / 33.25; window spread 0.00 vs 8.9 ms, 100% vs 0% in tolerance; runs/pacing/clock-gate-metal.txt). Proton D3D11: PASS (0.35 vs 20.00 ms; p50 33.32 / 33.09; spread 0.10 ms, 100%; bench-logs/20261006-041432-pacing). The macOS timer thread needed a time-constraint policy (e9a701f; design Decided, 7): plain nanosleep overshot 3.7 ms on average. On the Mac this gate therefore measures the ns schedule plus that policy against the old loop.
- [ ] 8.6 Pacing A/B (`spin` against `sleep`), three runs each, on Mac Metal, Mac CPU, Proton D3D11 and Proton CPU (`bench.sh pacing`; Mac via `pacing_stats.py` with runs in `runs/pacing/`). Record in-wait CPU, thread CPU, process CPU, intervals, flips/s and raster ms. Check the 25% and 1.5x flags. Gate, on Metal and Proton D3D11: in-wait CPU at most 10%; process CPU down by at least 25 points; timeout exits at most 5% of the site's loop exits in every summary (mid-loop timeouts reported, not gated); flips/s and each percentile inside `spin`'s widened spread; nothing flagged. The CPU paths are recorded.
  First series: every check passed on Metal and Proton D3D11 except the first draft's "wakes outnumber timeouts", which cannot pass with the 1 ms timeout (3.5 to 4 mid-loop timeouts per signalled wake on both hosts). Fable's review replaced it with the loop-exit measure (design D4, D8).
  - Mac Metal, exit metric (toolkit e18a210, six 90 s runs, runs/pacing/m2-*, report runs/pacing/sleep-gate-metal-exits.txt): timeout exits 0 of ~2,393 per run (0.0%), in-wait 0.2%, process CPU 128% -> 56%, flips/s and p5/p50/p95 inside the spread, no flags. One check fails: the interval max, 36.81 ms (sleep runs 36.39 / 36.81 / 40.02) against a spin spread of [33.97, 36.55] (spin runs 34.47 / 35.71 / 36.05), 0.26 ms over. The first series had sleep's max inside (34.43 in [33.88, 35.44]). A single-flip statistic; reported for the orchestrator to decide (D8), not re-run here.
  - The Proton re-read with exit counts rides on section 9.
  The first series' numbers:
  - Mac Metal: in-wait 0.2%, process CPU 127% -> 56%, intervals and flips/s inside the spread, no flags; wakes ~11.9k vs timeouts ~42k per 2,430 flips (runs/pacing/sleep-gate-metal.txt).
  - Proton D3D11: in-wait 4.8%, process CPU 182% -> 141%, inside the spread, no flags; wakes ~7.6k vs timeouts ~30k (bench-logs/20261006-042551-pacing).
  - Mac CPU (recorded): ~5 flips/s, too few 3D flips for a [PACING] summary; max 249 vs 241 ms (runs/pacing/sleep-gate-cpu.txt).
  - Proton CPU (recorded): 2.42 flips/s both arms, process CPU 642% -> 638% (the rasteriser), in-wait 0.0%; p5/p95/max just outside the narrow spin spread (bench-logs/20261006-043639-pacing).
- [x] 8.7 `RECOMP_FPS_MODE=lock60` and `=free`: one line each, and frames equal to `lock30` (a short `@stage1` on Metal).
  lock60 and free each log one line and run lock30; @stage1 frames CLOSE (runs/pacing/fps-*).
- [x] 8.8 `audio_check.py` on a Proton `@attract` run at `spin` with the ns clock: no new starves.
  PASS: Proton @attract at spin, ns clock against `vblank_clock=ms`, 68 s each: 0 host starves on both, no dropouts, rate ratio 1.00032 / 1.00042 (bench-logs/20261006-050725 and -050843; WAVs in runs/pacing/audio/).
- [x] 8.9 Required for the toolkit merge (design "Decided", 2: the clock is unconditional, so every title pays for it): a Burnout 3 smoke under Proton with the fork's toolkit at the ns clock (`spin`, b3's own gen, no `--spin-waits`), boot → "Press START" → menu → race start, under the run lock after BLiNX. Race pace (flips/s) and the `[NV2A] vblank` gap range are recorded against a run with `vblank_clock=ms`; the pace must be unchanged within its spread. If Burnout 3 cannot run (the dump, the build), the orchestrator asks the user rather than skipping it. The binding upstream runs are 9.4 and 10.3.
  PASS: toolkit e9a701f, b3 4788d52 with its own gen, 420 s each (runs/pacing/b3/20261006-044800-P-race-ns and -045702-P-race-ms). Race pace 270-360 s: 26.94 flips/s (ns) against 26.81 (ms), every 15 s window within 0.5. Every 600-vblank window lasts 10000 ms on both; the ns gap range is 16.6-16.7 ms in most menu windows (ms: 15-18), 11-22 ms in the busy stretches at ~890% process CPU (ms: 7-25), and 6 of the 35 windows before vblank 21000 hold a 1.1-60 ms catch-up (ms: 11). From vblank 21600 both arms report 40-80 declined vblanks per window, the same on both clocks. The same screens at the same dump indices (Race Training, the race at 63 mph); the menu-panel artefact and the drop to ~3 flips/s after 360 s appear in both arms.
- [ ] 8.10 One Mac `audio_check.py` run with real sound, after asking the user, before section 9: the macOS timer thread runs under a time-constraint policy (Decided, 7), and Mac audio has only run with `SDL_AUDIODRIVER=dummy`. Not run on the fork branch (no sound on the Mac without asking).

## 9. Default flip to `sleep` (gated; separate branch `feat/fps-pacing-default`)

Do this only after section 11 has merged `feat/fps-pacing` and the upstream PR-E2 head has passed 10.3.

- [ ] 9.1 Metal goldens: all scenarios, three runs at `sleep` (`golden.py --allow-enhance present.pacing=sleep`) and three at `spin`. The same verdict for every frame; a frame exact in all three `spin` runs is exact in all three `sleep` runs.
- [ ] 9.2 Proton D3D11 goldens: the same as 9.1, through `bench.sh golden` with `BENCH_ENV` setting `sleep` and the allow flag.
- [ ] 9.3 Flip-indexed A/B on `@stage1` and `@story-hub` (`fb_dump_at` at the same flips, three runs per mode): for each flip, every `sleep`-against-`spin` difference is no larger than the largest `spin`-against-`spin` difference, and a flip identical across the `spin` runs is identical under `sleep`.
- [ ] 9.4 Burnout 3 under Proton on the exact PR-E2 head, at `sleep` and at `spin` (10.3): the same screens at the same flips, race pace within spread, no new `[AUDIO-HOST]` starves, and no site with more than 5% of its loop exits on the timeout; a site above that goes on b3's `exclude` list with its reason.
- [ ] 9.5 `audio_check.py` on a Proton BLiNX `@attract` run at `sleep`: no new starves.
- [ ] 9.6 Only if 9.1-9.5 all pass:
  - one toolkit commit, `enhance: present.pacing defaults to sleep`, with the docs;
  - one cat commit with the pin bump, the `docs/env.md` default, and an openspec change that amends `enhancements` ("Enhancements default to stock" gets a named exception for `present.pacing` with the evidence) and the exit of the `deviations` entry.

  `golden.json` keeps `RECOMP_PRESENT_PACING=spin`. Each commit body says it is reverted on its own to go back to `spin`.
- [ ] 9.7 If any check fails, no flip. Record the evidence and the failing check in `TASKS.md`, and leave the branch unmerged.
- [ ] 9.8 A Fable review of the default-flip branch, then a squash merge by the orchestrator, then the post-merge steps in section 12.

## 10. Upstream (opt-in extension; `analysis/upstream/pr-stack-plan.md`)

- [ ] 10.0 Both PRs are cut from fork commit e4740b4 by hunk (design D12), and each PR commit says "fork e4740b4 (part)". 10.1 takes `host_time.*`, `xbox_VblankSchedule`, `kernel_vblank_tick_ns`, `kernel_timer_loop_ns`, `kernel_fire_timers`, the `kernel_drain_dpcs` return, `vblank_clock` and the `vblank_schedule` ctest; 10.2 takes `xbox_SpinWait`/`xbox_SpinWake`, `xbox_IrqlThisThreadBlocksDpcs`, the four wake points, `RECOMP_SPIN_WAIT`, the `pacing` trace and the `spin_wait` ctest.
- [ ] 10.1 Clock: fold into PR-08 `up/08-vblank-pacer` if it is not yet filed, else cut `up/08b-vblank-ns` from `origin/main`. Use `cherry-pick -x`, the env sed to `getenv` (`RECOMP_VBLANK_CLOCK=ms`), and the `vblank_schedule` ctest.
- [ ] 10.2 Spin waits: `up/e2-spin-waits`, after PR-E1. It carries:
  - the generator flag, matcher, report and pytest;
  - `RECOMP_SPIN_WAIT` and `kernel_pacing.c` with the wake points;
  - the `spin_wait` ctest;
  - the mode from `getenv("RECOMP_PRESENT_PACING")` when the enhance layer is absent.

  No BLiNX addresses in code or tests. Public API named `xbox_Module_Function`.
- [ ] 10.3 Gate G on the exact head of each PR:
  - Mac ctests and `pytest tools/`;
  - the mingw build and Proton ctests;
  - Burnout 3 under Proton: upstream's b3 regenerated with `--spin-waits` in `auto` mode; boot → "Press START" → menu → race start plus the three `b3/_local/bench host.sh` scenes, at `spin` and at `sleep`; the `pacing` trace per site.

  Record the head and base shas and the run ids on the PR tracker. Any force-push re-runs Burnout 3.
- [ ] 10.4 Fable reviews each PR branch against upstream's `README.md` and `CONTRIBUTING.md` from `origin/main`, with a conform, argue or fork-only verdict per deviation. Fixes go to a sub-agent. The PR body states "tested under Proton only; native Windows untested" and that the work is AI-assisted. The noreply identity is used, and the delta is audited before any push.

## 11. Review and merge

- [ ] 11.1 Fable reviews `feat/fps-pacing` in both repos (code, specs, the measurements from section 8, and backend agreement). Fixes go back to this branch's agent, never to the main session.
- [ ] 11.2 The orchestrator merges the toolkit `feat/fps-pacing` into `posix-host/portability` as a squash merge, then cat `feat/fps-pacing` into `main` as a squash merge (one commit per feature, the branches kept), then sets `setup-pins.json` to the public mirror's commit (`apexJCL/xboxrecomp` `blinx2/portability`) once the toolkit has been scrubbed and pushed there, not to the local merge commit (6.5).
- [ ] 11.3 The orchestrator regenerates `gen/` in the main `cat/` checkout (`pipeline.sh analyze`, then `recomp`), because `bench.sh integrate` syncs that `gen/` and checks its hash.

## 12. After the merge

- [ ] 12.1 Copy the agent's untracked notes (the recomp candidate report, measurement sheets, scratch) to `notes/pacing/`.
- [ ] 12.2 Copy any run referenced by `golden.json`, the timeline, `RESUME` or `TASKS` to `runs/pacing/` with `cp -c`.
- [ ] 12.3 Remove the worktrees with `git worktree remove --force` (both repos), then `rm -rf wt/pacing`. Keep the branches.
- [ ] 12.4 `scripts/bench.sh integrate` (sync and rebuild the Linux/Proton host), then `bench.sh golden`.
- [ ] 12.5 Update `cat/TASKS.md` (done items, measured numbers, follow-ups from 7.3, the default-flip state) and `cat/RESUME.md`.
- [ ] 12.6 Sync the specs: `openspec sync` or archive `fps-pacing` once section 9's outcome is known.
