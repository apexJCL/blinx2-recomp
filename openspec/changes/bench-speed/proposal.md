## Why

A warm `blinx2 bench integrate --golden` takes about 400 s and a Metal golden
pass on the Mac about 190 s, and both are often run twice: a scenario comes
back INCOMPLETE or flaky, and the only way to rerun it is the whole pass
(`notes/bench-speed/report.md`, BLX-36). The verdicts live only on the
controller's stdout, so nobody can measure how often each scenario flakes.
Every golden also re-runs the 17 Proton toolkit tests (about 100 s) even
when nothing they test changed, and every agent writes its own Mac runner
(20 copies under `runs/` and `notes/`), several of which stop by flip count
before an anchored frame and cause INCOMPLETEs of their own.

## What Changes

Report proposals P4, P2a, P5, P9 and P3, in that order (BLX-37):

- **P4 (CLI)**: `bench golden` writes each scenario's run checks, compare
  output and verdict to `bench-logs/<stamp>/golden.txt`, and appends one
  line per session to `bench-logs/golden-sessions.tsv`. `bench golden
  --only SCEN[,SCEN]` (also `integrate --golden --only`) runs only those
  scenarios.
- **P2a (CLI)**: `bench golden` and `integrate --golden` skip `bench tests`
  when the key (host toolkit tree digest, CLI commit and test script,
  Proton version, prefix version, llvm-mingw tag) matches the last pass
  recorded for that host tree in `bench-logs/tests-pass/`. One line says it
  was skipped and since which pass; `--tests` runs them anyway.
- **P5 (cat)**: `dump_slack` story 40 -> 100 and stage1 (unset, so 12) -> 60,
  from the anchor drift of every Metal run under `runs/`.
- **P9 (cat)**: `-Wno-parentheses-equality` on `src/recomp/gen/*.c` only,
  for clang (32.7k of the integrate log's 33.8k warnings).
- **P3 (CLI)**: `<game> golden run [SCEN...]`: the Mac golden runner. Headless,
  `SDL_AUDIODRIVER=dummy`, the Mac run lock, frames by `fb_dump_at`, stops
  once every frame's target (from the anchor it has seen) plus the window
  is dumped, warns when the host is loaded, checks and prunes like `bench
  golden`, run dirs in `bench-logs/`.

Not in this change: P1 (shorter limits, `min_flips` re-based), which needs
10 clean Proton runs after the current integration lands (tasks.md 6.1).

## Impact

- xboxrecomp-cli: `bench/__init__.py`, `bench/golden.py`, a new host
  script `tests_key.sh`, `golden.py` (`run`), a new `golden_run.py`, tests,
  README and help text.
- cat: `CMakeLists.txt`, `analysis/golden/golden.json`; `game.toml`'s
  `cli.commit` moves to the CLI merge.
- No runtime, renderer or toolkit change; goldens compare exactly as before.
