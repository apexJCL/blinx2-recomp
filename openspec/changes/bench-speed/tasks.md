## 1. P4: verdicts and --only (CLI)

- [x] 1.1 `bench golden` checks per scenario, writes `golden.txt` (run checks, compare, `verdict:` line) into each run dir and a line to `bench-logs/golden-sessions.tsv`.
- [x] 1.2 `bench golden --only SCEN[,SCEN]`, passed through by `integrate --golden`.
- [x] 1.3 Tests: --only filtering and its errors, the verdict word, the session line.

## 2. P2a: tests skip (CLI)

- [x] 2.1 `tests_key.sh` and the controller's key; record on pass in `bench-logs/tests-pass/`.
- [x] 2.2 Skip in `golden`/`integrate --golden` on a match, one line why; `--tests` forces.
- [x] 2.3 Tests: key match, mismatch per part, `unknown` never matches, --tests.

## 3. P5 and P9 (cat)

- [x] 3.1 `dump_slack`: story 100, stage1 60, with the drift numbers in the `_why`.
- [x] 3.2 `-Wno-parentheses-equality` on gen/ for clang.

## 4. P3: `golden run` (CLI)

- [x] 4.1 The runner: env, Mac lock (ancestor-aware), load warning, anchor-aware stop, check, prune.
- [x] 4.2 Tests: the stop logic (unanchored, anchored before and after the anchor, range cap), the lock, the env.
- [x] 4.3 Docs: CLI README and help; cat docs point to `golden run` instead of ad-hoc runners.

## 5. Gates

- [x] 5.1 CLI pytest + ruff; cat pytest + ruff.
- [x] 5.2 Mac: build cat main, `golden run` over all scenarios; verdicts and wall time vs the old runner.
  - 2026-10-09: worktree build (main + P9) 362 s, 0 `-Wparentheses-equality` (log 221 KB, 644 other warnings). `golden run`: attract pass 26.8 s, stage1 INCOMPLETE 79.0 s (first-3d 46 early, outside slack 40: now 60; rerun with `golden run stage1` pass 78.5 s), story pass 81.5 s. Old runner on main: 30.1 / 80.3 / 84.3 s, all pass. Passing runs keep 5.6-20 MB each after the prune (old runner: 84-232 MB).
- [ ] 5.3 the Linux/Proton host (slot from the orchestrator): integrate --golden twice (second skips tests), `--only story`, the integrate log's warning count.

## 6. Later

- [ ] 6.1 P1: shorter scenario limits and `min_flips` re-based on 10 clean Proton runs at the new limits, after the current integration lands.
- [ ] 6.2 Host-side early stop for Proton runs (`run_game.sh` ends at the last dumpat flip), sharing `golden run`'s stop logic.
