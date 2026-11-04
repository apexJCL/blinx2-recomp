# Tasks: bench-matrix

## 1. Toolkit
- [x] 1.1 `RECOMP_TRACE=prof` sampler (host_prof.c), env rows, ctest
      host_prof (Mac, Proton)
- [x] 1.2 cat `docs/env.md` rows for prof, prof_delay, prof_out

- [x] 1.3 D3D11 `RECOMP_WINDOW_QUIT_AFTER` and D3D11 batches in the pacing
      trace (4ec1a736)

## 2. CLI
- [x] 2.1 `bench-matrix plan` (matrix TOML to arms)
- [x] 2.2 `bench-matrix run` for mac and deck; `run-arm.ps1` for Windows
- [x] 2.3 `bench-matrix collect` (run.json, profile symbolisation, GPU
      samples)
- [x] 2.4 `bench-matrix analyse` (summary.json, summary.csv)
- [x] 2.5 tests and ruff

## 3. Game
- [x] 3.1 JSRF `config/bench/title.toml`

## 4. Runs
- [ ] 4.1 Mac 16 arms, Deck 12 arms, Windows 16 arms (the Spartan session)
      - [x] Mac 16 + s1-dsp0-43 --no-prof; Deck 12 profiled + 12 --no-prof
            (the profiler and run-to-run variance blur the Deck's fps)
      - [ ] Windows 16 + --no-prof: waits for the user to apply the patch
- [x] 4.2 `runs/bench-matrix/jsrf-title/summary.{json,csv}` and README
      (rerun after the PC block)
      - [x] Deck repeats: 2 more runs per arm without the sampler, arms
            interleaved (n=3), per-arm medians, spreads and good/bad
      - [ ] rerun again after the PC block
- [ ] 4.3 follow-up: a running-thread test under Wine (GetThreadTimes) so
      the Deck profile need not stop every thread; until then the Deck
      samples at 100 Hz

## 5. Review fixes (review)
- [x] 5.1 F1: the exe name and the ignored processes come from game.toml
      and the scene (`quiet_ignore`), not constants of the CLI; the
      Windows script takes the host's backend
- [x] 5.2 F2: frame times inside the window only (load gap apart),
      nearest-rank percentiles, no short last per-second bucket
- [x] 5.3 F7b: `rep` in run.json, per-arm n/median/min/max/MAD, the
      verdict threshold as a scene key, `disturbed` runs out of the arm
      figures by default
- [x] 5.4 F17: NOTICE in the game for the toolkit's LGPL code and
      dsp56300; the credits entry
- [x] 5.5 Deck CPU clock per core and the game's thread placement per
      second (cpu.tsv, threads.tsv); the first Deck repeats predate it

## 6. Runner and analyser follow-ups
- [x] 6.1 Spin share: `spin_share` per run (the scene's
      `[profile] spin_functions` over the samples outside the wait
      modules, i.e. what ran; the share of all samples stays in run.json
      as `share_all`) and per-core loads (`core_max_pct`,
      `cpu_process_cores`) in summary.csv
- [x] 6.2 D1: the Deck script stops its GPU and CPU samplers on any exit
      (EXIT trap; HUP/INT/TERM exit 130); the CPU sampler also quits when
      orphaned
- [x] 6.3 D2: Deck per-core logs (cores.tsv), every thread's core and
      allowed set (threads.tsv), other busy processes (busy.tsv); the
      sampler no longer logs itself
- [x] 6.4 Disturbance: the PC's quiet wait reads CPU from the perf
      counters (Get-Process missed SYSTEM and elevated processes and took
      0 as unknown); mid-run busy processes (every host) and focus loss
      (the PC) are recorded in run-info.json and mark the run
      `disturbed`, as does a quiet wait that gave up. No host ignores the
      game's own name: the mid-run checks skip the game by id (Deck
      sampler, Mac watch, PC runner), so a second game instance counts
      as busy, and one running before the start holds it
- [x] 6.5 Run directories carry the arm id (`<arm>-noprof-rN`); analyse
      lists run dirs whose name and run-info disagree (`misnamed`)
- [x] 6.6 Review2 P2-P6, P8: run-arm.ps1 checks paths, skips empty env
      values, `@R` by literal replace, case-sensitive env check, refresh
      rate filter, `exit 0`; header names the host
- [x] 6.7 T1 (toolkit fix/host-prof-dump-wait): the dump waits only on a
      sampling round in flight, not on the start delay; ctest
      host_prof_delay_test
- [x] 6.8 `bench-matrix series`: repeats for several hosts in one plan,
      `--order interleave|blocks`, done runs skipped; `windows --series`
      writes run-series.ps1 for the PC
- [x] 6.9 `bench-matrix compare BEFORE AFTER`: per host/arm/prof medians
      and deltas (fps, 1% low, p99, cores, spin share, core max, load
      gap) to compare.csv and compare.md (for the tracker item)
- [x] 6.10 Every bench run on every host uses borderless desktop
      fullscreen (`RECOMP_PRESENT_FULLSCREEN=1`, scene key
      `fullscreen = false` to opt out), recorded as `present_fullscreen`
      in run-info.json. Runs before this are windowed and do not compare
      directly with later ones
- [x] 6.11 Host order: remote hosts (PC, Deck) first, the Mac's arms
      last. A Mac run takes its locks first: the bench lock
      (`~/.recomp-mac.lock`), any local `quiet_locks` (none by default)
      and the local `run_wrapper` (here `notes/mac-run-lock.sh`, the
      `~/.recomp-mac-run.lock` run queue). Inside them it waits for no
      build tools and a quiet CPU, then runs the game in its own session,
      killed whole at the cap. `run_order`, `builds_at_start` and `locks`
      (only those held) in run-info.json
- [x] 6.13 Review fixes (review): series counts a run done
      only with its run.json and reruns one that failed (moved aside to
      `.failed-<time>`); compare blanks the cores change across different
      measures and flags windowed against fullscreen; `misnamed` checks
      the whole name; run-series.ps1 resumes (`-SkipDone`)
- [ ] 6.12 Smoke on hardware:
      - [ ] one fullscreen arm per host (Deck under gamescope, PC D3D11
            popup, Mac SDL fullscreen Space)
      - [ ] M5: the PC's mid-run perf counter query, on against off on the
            same arm (steady fps, 1% low); until then a possible bias
            against the tracker item PC baselines
      - [ ] one prof-on run on Proton or the PC, for the toolkit's
            host_prof dump change (fix/host-prof-dump-wait)
