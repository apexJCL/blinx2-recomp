Worktrees:
- `wt/occ-reports/xboxrecomp`: toolkit, branch `fix/occ-reports` off `posix-host/portability`.
- `wt/occ-reports/cat`: this spec, the `docs/env.md` rows, the `@story-idle` preset and `scripts/occ_flips.py`, branch `spec/occ-reports` off `main`.
- No b3 branch: the race gate runs from a b3 build against the toolkit worktree (`--stale-gen-ok`, provenance note).

Raw runs go in `xbox-recomp/runs/occ-reports/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`), builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Proton runs are on the Deck with a Mac-built exe copied over, under `flock -w 3600 ~/.recomp-run.lock` (memory note *deck-proton-bench*; `blinx2 bench` takes the lock itself). BLiNX 2 first on the Deck; one agent there at a time. The native Windows run (6.6) waits for the user's go and uses drive D (memory note *windows-pc-drive-d*). The diagnostic branch `diag/loadcat` (aaee8d6) is reference only; nothing from it is cherry-picked.

## 0. Spec review

- [x] 0.1 No Fable pass: the user dropped it on 2026-10-15. The Opus review (7.1) covers the code and this spec. The user's go for 6.6 is the one decision outstanding; it is not a prerequisite for 1-5.

## 1. Shared tracker (`nv2a_backend_common.{c,h}`, design D2)

- [x] 1.1 `nv2a_occ_flip(o)`: a flushing poll, the bounded wait (`settle_us`; default 8000 µs a frame since 8.7), then every report still pending settled with `nv2a_report_write(mem, va, last)` where `last` is the address's last completed count, else `NV2A_OCC_VISIBLE`; moved to `retired[NV2A_OCC_PENDING]` with its queries; `settled`, `stale` and `first` counters.
- [x] 1.2 `retired[]` polled wherever `pend[]` is: a result updates the last-count table and returns the queries, writes nothing to guest memory; entries older than `NV2A_OCC_LATE_US` dropped unread; the oldest dropped unread when full.
- [x] 1.3 The last-count table `NV2A_OCC_LAST = 64` of `{va, count}`, oldest replaced; filled by every completion (pending or retired) with the guest-size count.
- [x] 1.4 `nv2a_occ_set_delay(o, us)` honoured in `occ_ready()` (a result is not taken before `now - t0 >= delay`, sync mode included); `nv2a_occ_set_settle(o, us)`.
- [x] 1.5 The header comment on the tracker: the settle rule, the retired list, the one accepted window (design D2), with the LOAD GAME screen as the reason.

## 2. Backends

- [x] 2.1 D3D11: `nv2a_occ_flip(&s_occ)` in `d3d11_flip()` after `IDXGISwapChain_Present` and before `flip_log()`, and `nv2a_occ_settle(&s_occ)` from `d3d11_on_poll()` (design D8, D9); the top-of-flip `nv2a_occ_poll(&s_occ, 0)` stays. The scale-change path calls `nv2a_occ_settle` and drops `retired[]` before `nv2a_occ_set_scale`.
- [x] 2.2 Metal: `occ_settle(1)` (`nv2a_occ_flip`) in `metal_flip()` after `flush(1)`, not in `occ_after_wait()` (design D8), and `occ_settle(0)` (`nv2a_occ_settle`) from `metal_on_poll()` and the scale-change path. `metal_on_report()`'s commit at `GET_REPORT` unchanged.
  Done differently: `occ_after_wait()` also runs after the mid-frame `flush(1)` waits (ring full, readbacks), where a pending report must stay pending, and is skipped when there is no command buffer at the flip. So `metal_flip()` calls a new `occ_flip()` right after its `flush(1)`: it waits on the command buffers of reports still pending (committed at `GET_REPORT`, so stock Metal settles 0), then `nv2a_occ_flip(&s_occ)`. `occ_after_wait()` keeps its poll.
- [x] 2.3 Both backends read `occ_delay_us` and `occ_settle_us` once (with `occ_mode()`) and set them on the tracker.
- [x] 2.4 Flip log: `settled N (stale M, first K)` after `superseded` on both backends' lines, the totals in the end-of-run summary; `RECOMP_TRACE=zpass`: the first 64 settles (flip, address, count, age) and the eight-bucket age histogram in the summary (design D3).
- [x] 2.5 `nv2a_pb_state.h`: the `on_report` comment says a deferred report is written no later than the next `on_poll` returns, which the executor calls before a semaphore release after such a report and at the walk's end before GET (design D9).

## 3. Keys and docs

- [x] 3.1 `recomp_env.h`: `X(OCC_DELAY_US, DEBUG, "occ_delay_us", NULL, ...)` and `X(OCC_SETTLE_US, DEBUG, "occ_settle_us", NULL, ...)` beside the occlusion rows.
- [x] 3.2 cat `docs/env.md`: the two Debug rows with their read-at sites, the Debug count 91 to 93; the `flip` and `zpass` trace rows mention the new fields. `uv run pytest scripts` (`test_env_doc`) and `uv run ruff check . && uv run ruff format --check .`.

## 4. Tests (design D4)

- [x] 4.1 `tests/occ_reports/` (CMake `project()`, `nv2a_backend_common.c` + `nv2a_tex_pack.c`, fake ops with a per-query ready time, a fake clock, a counting pool): the nine cases, plus the settle after a walk (D8), the per-frame budget and the late-result order guard (D9): 12, one `[occ_reports] name: PASS|FAIL` line each.
- [x] 4.2 Show cases 2, 3 and 6 failing on `posix-host/portability` (the report stays 0xFFFFFFFF across the flip) and all passing on the branch; both outputs in the notes.
  Base: `runs/occ-reports/ctest-base/base.log` (cases 2, 3, 6 rebuilt against 6c06ae4's tracker with a shim, the flip a non-flushing poll and the delay as query latency: all three FAIL on the report words); branch: `branch.log` beside it, nine PASS.
- [x] 4.3 `tests/d3d11_backend_smoke/smoke.c`: the cross-frame reuse case rewritten (report 3 complete at the top of the next frame: exact 100, stale 100 or first-time visible, counted); `s_cross_live` and its failure removed; the in-frame supersede and the 0 / 100 counts kept. Run on the Deck under Proton.
  Deck under Proton (Mac cross-built smoke, `runs/occ-reports/deck/smoke.log`): async and sync both exit 0, 0 wrong, 0 lost; async cross-frame exact 1, stale 178; sync exact 179. The Windows cross build also caught a broken string literal in smoke.c (fixed on the branch).

## 5. Harness (design D5)

- [x] 5.1 `@story-idle` in `src/pad_input.c` and `game.toml`'s `presets`, from `runs/loadcat/bin/loadgame-idle.txt`; the README preset row. Confirm once on the Mac that with the investigation's save the screen shows both characters (1509 batches a flip).
  Mac, branch build, `RECOMP_INPUT_SCRIPT=@story-idle` 60 s (`runs/occ-reports/mac/preset-storyidle-173144`): screen up at flip 471, 1509 batches x3077 of 3139 flips, 0 below 1400, settled 0. PASS.
- [x] 5.2 `scripts/occ_flips.py` and `scripts/test_occ_flips.py` (idle pattern passes, delay pattern fails, no flip lines exits 2, the floor is honoured). ruff clean.
- [x] 5.3 The case on the Mac (Metal, headless, 60 s, `RECOMP_TRACE=flip`, `RECOMP_DEBUG=occ_delay_us=16000`): base fails with the count of 157-batch flips recorded; branch passes, `stale` equal to the reports after the first flip. Without the delay: the branch's histogram equals the base's, `settled` 0. Logs in `runs/occ-reports/mac/`.
  The flip-only settle failed this (design D8); with the settle after each walk: base 16 ms 2914 flips below 1400 (157 x2839), branch 0 (settled 6116, stale 6113, first 3); 8 ms base 31 below, branch 0; no delay, branch 0 below and settled 0. Base binaries: `runs/loadcat/bin/cat_recomp-mac-diagocc3` (diag delay) and `-37d26ed`.
- [x] 5.4 The same on the Deck (D3D11, Mac-built exe, under the run lock). Logs in `runs/occ-reports/deck/`.
  Deck D3D11 (`runs/occ-reports/deck/harness.sh`, `RECOMP_PB_BACKEND=d3d11`, bench-logs 20261015-171853..172221): base (diag delay exe) 16 ms 2537 flips below 1400 (157 x2477); branch 16 ms 0 below, settled 5086 (stale 5085); branch no delay 0 below, settled 1551 of 5084 reports (30% at stock; ages <1 ms 274, <2 1924, <4 1968, <8 567, <16 328); branch `occ_settle_us=2000` 0 below, settled 2, 659 ms of settle wait over 60 s, mean frame wall 16.84 ms (same as without).

## 6. Gates (design D6)

- [x] 6.1 Mac build and `tests/posix_ctest.sh <dir>`: 0 FAIL, `occ_reports` in the list. Summary in `runs/occ-reports/`.
  61 pass, 1 skip, 15 n/a, 0 FAIL: `runs/occ-reports/ctest/posix-ctest-summary.txt`.
- [x] 6.2 BLiNX 2 Metal goldens on the Mac (attract, stage1, story) from a cat build against the branch (`--stale-gen-ok`, provenance note): verdicts unchanged, `settled` totals recorded (see 8.4), flips/s and mean frame ms against main's last runs (45.8 / 33.4 / 54.0 flips/s), flagged at a 25% drop or 1.5x rise.
  `runs/occ-reports/golden-metal.log` (d6ae77e): attract, stage1, story pass; 43.5 / 33.7 / 53.1 flips/s against 45.8 / 33.4 / 54.0 (host load 22-38 from other agents); settled 0 on every flip.
- [x] 6.3 BLiNX 2 D3D11 goldens on the Deck: `blinx2 build windows` on the Mac with a provenance file, copy to `~/blx-bench/cat/build-win/`, `blinx2 bench golden`. Verdicts as 20261015-154907 / -155027 / -155217; the per-scenario `settled` totals and the flips they fell on recorded; speed against the same runs. A frame that differs at a settled flip is examined on its own (design D6.2) before anything else moves.
  Exe sha256 62cc446a..., `runs/occ-reports/deck/golden.log`, bench-logs 20261015-170938 / -171058 / -171248: all pass (stage1-enemies-objectives mae 9.8, CLOSE, limit 16); flips 2370 (31.6/s) / 3203 (30.5/s) / 4693 (46.9/s) against 2400 (32.0) / ~3209 / ~4676. Settled at stock: attract 9172 of 20360 reports (stale 9080, first 92), stage1 15133 of 43379 (stale 15069, first 64), story 998 of 3551 (stale 994, first 4). No verdict moved, so no frame was examined on its own.
- [x] 6.4 Burnout 3 Metal race gate (`b3/scripts/race_gate.py`) on the Mac from a b3 build against the branch: pass, `settled` totals recorded. Logs in `runs/occ-reports/b3-mac/`.
  `runs/occ-reports/b3-mac/branch.out`: PASS, 7008 flips, race 53.0 flips/s, max gap 159 ms, audio ok; settled 0 of 565 reports.
- [x] 6.5 Burnout 3 D3D11 under Proton on the Deck: the gate's `--pad-script` variant with `RECOMP_TRACE=flip`, under the run lock, from a Mac-built exe: pass, `settled` totals recorded. Logs in `runs/occ-reports/b3-deck/`.
  Deck, Mac-built b3 exe (b3 d6eab90 + toolkit d6ae77e, `--stale-gen-ok`), the race pad script fullscreen, `runs/occ-reports/b3-deck/deck-run.sh` -> `branch/`: 16030 flips in 275 s (exit 124, the timeout), race loaded (1074 batches a flip at the end); 107 reports, all settled (stale 97, first 10), none late or pending.
- [ ] 6.6 **Native Windows, after the user's go:** base and branch Windows builds on drive D; `@story-idle` (or the pad script file) at `render.scale` 4 with `RECOMP_TRACE=flip,zpass`, 60 s each, no injected delay; `scripts/occ_flips.py` on each log; the `settled` / `stale` / `first` totals, the age histogram and flips/s recorded. Then branch runs with explicit `occ_settle_us` values 0 (the old no-wait behaviour), 2000 and 8000 (the default since 8.7) on the staged 797bbc9 exe, whose compiled-in default is 2000. The user runs them by hand: `run.cmd base1 base`, `run.cmd settle0 branch 0`, `run.cmd settle2000 branch 2000`, `run.cmd settle8000 branch 8000`. If the base shows no 157-batch flip, repeat with the user at the pad as they played it. The user looks at the screen on the branch build. Logs in `runs/occ-reports/win/`.
  Not run. A run started over ssh lands in session 0: `D3D11CreateDeviceAndSwapChain` fails with 0x887A0022 and the executor falls back to the CPU path, and the window timer never fires (`runs/occ-reports/win/session0-attempt/`). Launching into the console session needs a scheduled task (`schtasks /it`), which was refused. `runs/occ-reports/win/run.cmd` and base/branch exes (`runs/occ-reports/bin/cat_recomp-win-base-6c06ae4.exe`, `cat_recomp-win-d6ae77e.exe`) are staged in `D:\xbr\hgpr\occ`.
- [x] 6.7 CPU rasteriser builds (6.1 covers it); no CPU golden.

## 7. Review, merge, follow-ups

- [x] 7.1 Opus review of the toolkit branch (and this cat branch) before the merge; fixes go back to the branch's agent.
- [ ] 7.2 Merge: toolkit and cat with `git merge --squash` (one commit each naming the branch and tip sha). Then the post-merge steps: notes to `notes/occ-reports/`, referenced runs to `runs/` with `cp -c`, worktrees removed and branches kept (`diag/loadcat`'s worktree `wt/loadcat` goes through `notes/cleanup-derived.py` once the native Windows numbers are in `runs/occ-reports/`), the Deck `bench golden` on the merged tree.
- [ ] 7.3 TASKS.md: close BLX-145 with the gate numbers and the Windows before/after; the default of `occ_settle_us` (8000) confirmed or moved from the 6.6 A/B; follow-ups: the NV2A count semantics (already open), the in-frame readers if the Windows run shows the attract cliff's flares differ, the upstream candidacy with the visibility series (377f04a, 65b25c5).

## 8. Review fixes (design D9; review of toolkit d6ae77e and cat 498b360)

- [x] 8.1 The executor settles before the title can read: `reports_settle()` before `BACK_END_WRITE_SEMAPHORE_RELEASE` writes, and `nv2a_pb_exec_walk_end()` from `nv2a_pb_scan.c` before the stop salvage and before GET is stored (F1).
- [x] 8.2 `NV2A_OCC_SETTLE_US` 2000 in common code for both backends, 0 for none; Metal's unbounded `occ_pending_wait` removed, so both use the bounded loop; the budget per frame (`frame_wait_us`); `docs/env.md` rows (F2).
- [x] 8.3 `retired[]` polled without a flush; `on_poll` with nothing pending does only the no-flush poll (F3). Metal commits a query still in the open command buffer before waiting (F4). The scale change settles with `nv2a_occ_settle` / `occ_settle(0)` (F5).
- [x] 8.4 Spec, design D9, tasks and the trace text `settle (flip N)` (F6, F8). Mac gates on toolkit 797bbc9: posix ctest 0 FAIL (`occ_reports` 12 PASS); `@story-idle` 16 ms 0 flips below 1400 (base 2914), 8 ms 0 (base 31), no delay 0 with 76 of 6232 settled; Metal goldens attract pass 43.6 flips/s (13 of 67 settled), stage1 pass 33.3 (7548 of 33341), story 52.6 (35 of 2792; see the report for the story-hub view under host load 40-50).
- [x] 8.5 `tests/occ_reports`: the per-frame budget and the t0 order guard; the smoke's first-time check allows any gap over 250 ms (F7).
- [x] 8.6 Deck on the review tip (797bbc9, Mac-built exe f3b19dd2, main's 56cb1062 restored after): D3D11 goldens pass at 30 flips/s, settled 130 / 60 / 6 (design D9); harness at 16 ms 0 flips below 1400 (bench-logs 20261015-192213); smoke 0 FAIL in both modes; B3 race under Proton from a scratch copy of the game (`B3_GAME`), the same runner-limited check as 6.5 and no visibility tests on that route this run; the stage1 settle A/B (D9). The Windows branch exe in `D:\xbr\hgpr\occ\branch` replaced (scp only).
- [x] 8.7 The default `occ_settle_us` moved from 2000 to 8000 (toolkit 7181ea4) from the stage1 A/B on Metal and the Deck (design D9); `docs/env.md`, the spec and D9 updated; posix ctest 0 FAIL (`runs/occ-reports/ctest/posix-ctest-8000.log`). 6.6 can still move it before the merge.
