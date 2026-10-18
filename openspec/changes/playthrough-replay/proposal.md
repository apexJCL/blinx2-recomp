# Change: Record a playthrough once, replay it on every host

The user asked
on 2026-10-13 for a way to make the release soak tractable:
record a human playthrough once and replay it unattended on Mac/Metal,
Proton/D3D11 (the Linux/Proton host through `blinx2 bench`) and the Steam Deck. The tracker item
itself is now a manual smoke pass per platform; this change is phase 1 of
the automation that takes over after v1: one recorded stage replayed on all
three hosts with one check per host. The later phases are proposed as
follow-up changes in design § Follow-up changes, not part of this one.

## Why

Everything needed to replay a stage exists in pieces, and nothing records
one:

- **The script engine is already the right replayer.** `RECOMP_INPUT_SCRIPT`
  (`src/pad_input.c`, spec `input`) runs inside the title's own pad poll with
  event anchors (`wait open`, `wait mem`, `tap .. until`), poll-counted
  steps (`wait polls N`, `BUTTON/Np`) and timed steps. The title polls the
  pad once per game frame and advances a fixed 1/30 s of logic per frame
  (`docs/env.md`, `main.c`), so **poll index is game time**: a script
  written in polls replays the same game frames at any host speed. The
  presets and `scripts/shots/pad/*.txt` (every stage and boss through the
  debug stage select) prove the navigation half on all three hosts.
- **Nothing records what the title saw.** The host-pad line
  `[INPUT] t=.. host port=0 buttons=..` fires on change only, before the
  merge, with wall time and no poll index; `RECOMP_TRACE=input` logs pad
  handles, not states (`pad_input.c`; `input-real-devices` tasks 5.1/5.2
  were never built). A human session cannot be turned into a script today,
  and a file cannot start where a preset ends: `@name` resolves only as the
  whole `RECOMP_INPUT_SCRIPT` value.
- **Timed replay drifts; poll-anchored replay does not, between events.**
  Load times differ per host (stage 1: 1.3 s Mac Metal, 2.25 s Proton from
  "leaving title" to the stage jingle), movies run on the audio clock, and
  the loading loop keeps bumping the game frame counter `0xAE7180`, which
  two `srand` sites seed from (`0x1618B1`, `0x161A86`). Wall-clock steps
  split golden runs before (`@stage1`'s 2 s tap phase, `pad_input.c:174`);
  poll-counted holds fixed the stage-1 walk to 0/3569 frame mismatches. The
  game-route spec already demands that every screen exit end on a game
  event; a replay needs the same, plus care not to re-base on events other
  threads time (file opens from the loader and audio threads).
- **The checks exist, scattered.** `scripts/soak.py` has the
  verdict ladder (STALL > CRASH > EXIT > INCOMPLETE > ok), the stall rule
  and the Mac launcher; `golden_run.py` and `bench/host/run_game.sh` have
  the locks, the run directories and the end checks; `[PACING] flip N t_us`
  (trace `pacing=all`) carries per-flip intervals that `pacing_stats.py`
  already parses; `[AUDIO-HOST]` carries starves; `[CRASH]` is the crash
  tag in `game.toml`. None of them knows a stage boundary, so no tool
  reports "stage 1-1: 29.8 flips/s p95 36 ms, no starves" per host.
- **A wait never times out.** A `wait mem` that never comes true blocks
  forever; only `soak.py`'s hang cap ends such a run. A replay that lost
  sync must say so, at the step that lost it.

## What Changes

- **Recording.** A new game key `RECOMP_INPUT_RECORD=<file>` writes, from
  the pad poll, the merged port-0 state the title received (script, host
  pad, keyboard and mouse together, after the merge) on every change, keyed
  by a port-0 poll counter that counts whether or not a script is on,
  together with the file opens (through the recorder's own cursor; the hook
  is installed when the key is set) and watched-dword transitions
  (`RECOMP_DEBUG=rec_watch=VA,..`) at their poll, a probe row of guest
  dwords every N polls and at each event (`rec_probe=VA:N[:x],..`, the
  `pad_peek` syntax: `:x` for integers), the flip and vblank counts, and the
  poll at which a prefix script reported `script done`. Keyboard and mouse
  need no channel of their own: the mouse is a stick and a key is a button
  by the time the title polls.
- **Lowering.** `xbr replay lower` (CLI, stdlib) turns a recording into a
  pad script in the existing grammar: `include @stage1` for the prefix,
  then the anchors named in the game's `config/replay.json` as
  `wait open TEXT timeout S` or `wait mem VA == V timeout S`, each of kind
  `check` (waited for, offset reported, poll base kept) or `resync`
  (re-bases the polls that follow; only on main-thread `mem` states), and
  between them the recorded changes as `wait polls k` plus actions, with
  `probe` steps where the recording probed. The script is text a person can
  read, trim and splice.
- **Replay** is `RECOMP_INPUT_SCRIPT=<lowered script>` with
  `RECOMP_INPUT_STRICT=1`: no new replay mode. The engine gains
  `include @NAME`, `timeout SECS|Np` on `wait` and `tap .. until` steps, a
  `probe` step that prints the probe row now, and `poll=N flip=F` on its
  step, probe and desync lines. A timed-out wait logs
  `[INPUT] t=.. poll=N flip=F desync step k/n: <step>` and, under strict,
  ends the process with status 4 (`_exit`, not `exit`: the poll runs on a
  guest thread).
- **Checks.** `xbr replay check <run-dir>` reads one run's log and reports
  per segment: verdict (crash, desync, stall, incomplete, ok; tainted by
  host input; non-stock), flips/s and p50/p95 frame ms from the
  `[PACING] flip` intervals between the segment's flip bounds through
  `pacing_stats.py`'s parsers, probe divergence against the recording
  (first differing row and address; the poll offset at every anchor; the
  frame counter apart), audio starves and underruns when the `audio_host`
  trace is on. PERF flags (CLAUDE.md's 25 % flips/s drop, 1.5× frame ms)
  apply only against a baseline run on the same host and backend; other
  hosts' numbers are information.
- **Hosts.** Mac: `blinx2 replay run <name> --backend metal` through the
  launcher shared with `golden run`, which gains `soak.py`'s stall rule.
  the Linux/Proton host: the recording is pushed with `rsync` (`bench sync` excludes
  `analysis/`), then `blinx2 bench run` with the replay environment in
  `BENCH_ENV`; the bench takes its own lock. Deck: `blinx2 replay deck-cmd
  <name>` prints the `scp` and `ssh <bench-host>` commands for the user to run in
  their own session against a scratch install root holding a `blinx2
  package` bundle (never `~/Games/BLiNX2/hdd`, never unasked); the runner
  script ships as CLI package data; logs come back by `scp` and go through
  the same `check`.
- **Placement and order.** Machinery that knows no address is the CLI's
  (`xbr replay`, with synthetic test fixtures because the CLI is public).
  Game data is cat's: `config/replay.json` (anchors with kinds, watches,
  probes with types, the record and replay environments, the performance
  floor, the prefixes) and one `[replay]` table in `game.toml`, added in the
  same commit that bumps `[cli]` to the release whose schema knows it, after
  the CLI's public round; `[toolkit]` is bumped likewise for the one new
  accessor. Recordings live in `analysis/replay/<name>/`, gitignored with
  the rest of `analysis/` and so never exported; they are game output and a
  person's play. The recording run itself is pinned to stock frame rules.
- **Scope.** Phase 1 only: the recorder, `include`, `timeout`, `probe`,
  `lower`, `check`, `run`, `record`, `deck-cmd`, `config/replay.json`, and
  one recording of stage 1-1 from `@stage1` replayed on all three hosts with
  the findings written up. `bench replay`, a stage library with `report`
  and baselines, frames at anchors, RNG pinning on evidence, `soak.py`
  integration and Burnout 3 are follow-up changes (design § Follow-up
  changes), filed in the tracker by task 0.2.

## Capabilities

### New Capabilities
- `playthrough-replay`: the recording format, the lowering with anchor
  kinds, the per-host harness, the checks, and where recordings and game
  data live.

### Modified Capabilities
- `input`: the pad the title sees can be recorded per poll; `include
  @NAME`; `wait` and `tap` steps take a `timeout`; a `probe` step; step
  lines carry `poll=` and `flip=`; a desync is logged and ends a strict
  run with status 4; the requirement text now lists `wait until`, `poke`,
  `memdump`, `BUTTON/Np` and `every Np`, which the engine already had.

## Impact

- **Game (`cat`)**: `src/pad_input.c` (poll counter, open hook on record,
  recorder, `include`, `timeout`, `probe`, log fields),
  `src/env/recomp_env_game.h` (`RECOMP_INPUT_RECORD`, `rec_watch`,
  `rec_probe`, `rec_every`), `docs/env.md` rows and counts,
  `config/replay.json` (new), `game.toml` (`[replay]`, `[cli]` and
  `[toolkit]` bumps in one commit), `scripts/test_gitignore.py` (one case),
  `scripts/soak.py` unchanged, `.gitignore` unchanged (`analysis/*` already
  local).
- **Toolkit** (`posix-host/portability`): `xbox_FlipCount()` beside
  `xbox_VblankCount()`, a relaxed atomic read of the walker's flip count;
  nothing else. Stock behaviour does not change: with the keys unset the
  poll path is as today. The CPU backend keeps building.
- **CLI (`xboxrecomp-cli`)**: new `src/xboxrecomp_cli/replay.py` (`lower`,
  `check`, `run`, `record`, `deck-cmd`) and `replay/deckrun.sh` package
  data; `golden_run.py` shares its launcher and gains the stall rule;
  `manifest.py` learns the optional `[replay]` table; tests under `tests/`
  on synthetic fixtures; a tagged release before cat's pin bump.
- **Goldens**: unaffected. `golden.json` pins stay; the replay environment
  is its own; the Metal and D3D11 goldens are run to show the engine change
  on the poll path moved nothing.
- **Performance**: the recorder writes one short line per state change and
  one per probe interval, on the poll thread, through a buffered `FILE`;
  off by default. Phase 1 measures `@stage1-enemies` flips/s with the
  recorder on and off.
- **Burnout 3**: unaffected until `b3-replay`; the recording format and
  `xbr replay` are already game-agnostic. Its build and race smoke run on
  the toolkit branch are the CLAUDE.md gate for the accessor.
