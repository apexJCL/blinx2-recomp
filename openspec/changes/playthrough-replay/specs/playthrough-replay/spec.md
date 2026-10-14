## ADDED Requirements

### Requirement: A play session is recorded as the pad the title received
With `RECOMP_INPUT_RECORD=<file>` set, the host SHALL write a text recording (`# xbr-rec 1`) of port 0 keyed by a poll counter that counts every port-0 pad poll from the first (base 1), whether or not a script is on: `p N STATE` on every change of the merged state the title received (script, host pad, keyboard and mouse together, in the `[INPUT] buttons=` wording), starting with the first poll's state; `o N PATH` for each successful file open drained at that poll through the recorder's own cursor, which SHALL never consume an open a `wait open` step is waiting for; `m N VA V` for each transition of a dword named in `RECOMP_DEBUG=rec_watch=`, with VA printed `0x%08X` as the `[INPUT] mem` line prints it; `k N ..` with the `rec_probe` row every `rec_every` polls and at every `o` and `m`; `f N flip F vbl V` beside each `k`; `d N` at a prefix script's `script done`; and `# end N` at a normal exit. Header lines SHALL name the game, host, backend, the exe path, the time, the `RECOMP_*` environment, the watch and probe sets; shas are not the exe's to know and SHALL be added by the launchers. Setting the key SHALL install the file-open hook whether or not a script is set. The file SHALL be flushed at every `o`, `m` and `k`. With the key unset nothing is recorded and the poll path is unchanged.

#### Scenario: A scripted run records what it logged
- **WHEN** `@stage1` runs for 60 s on Metal with `RECOMP_INPUT_RECORD=rec.txt RECOMP_HOST_PAD=0 RECOMP_DEBUG=rec_watch=0xae73fc`
- **THEN** the `p` lines are `p 1 none` followed by the `[INPUT] t=.. buttons=` lines in order, the `o` lines include stg0101 and jingle_stagestart, the `m N 0x00AE73FC 0x1` poll equals the `poll=` of the `[INPUT] .. mem 0x00AE73FC = 0x1` line, and the preset's own `wait open` steps all matched

#### Scenario: A person's play is recorded after the prefix
- **WHEN** the recording run has `RECOMP_INPUT_SCRIPT=@stage1 RECOMP_HOST_PAD=1` and the person plays after `script done`
- **THEN** the file holds `d N` at the prefix's last poll and `p` lines after it that carry the pad's sticks and buttons, and a `# end` line when the game is quit

### Requirement: A recording lowers to a pad script cut at game events
`xbr replay lower` SHALL turn a recording into a script in the `input` grammar using the game's `replay.json` (named by `game.toml` `[replay] json`, or given with `--replay-json`): the prefix as `include @NAME` for a preset or a file prefix's steps copied, refusing a prefix whose last step is timed; then for each anchor the recording hit after `d` a `wait open TEXT timeout S` or `wait mem VA == V timeout S` step with `S = max(30, 3 × the recorded gap in seconds)` unless `--timeout-scale` says otherwise; then the recorded changes as `wait polls k` and actions, and a `probe` step at each `k` row. An anchor's `kind` SHALL be `check` (default: waited for and reported, the poll base unchanged) or `resync` (the polls that follow are re-based to the event's poll); `resync` SHALL be refused on an `open` anchor, since opens come from the loader and audio threads. `--no-anchors` SHALL emit one poll-relative segment from `d`. The tool SHALL write a `# segment NAME kind=K rec-flips F1-F2 rec-polls P1-P2` comment before each anchor and a `meta.json` beside the script. Addresses, event names, environment pins and the performance floor SHALL come only from the game data; the CLI and its tests SHALL contain none, and the tests' fixtures SHALL be synthetic (made-up addresses, invented log lines, no game output).

#### Scenario: Check and resync anchors
- **WHEN** a synthetic recording has `o 412 d:\stage_tex.bin`, `m 1133 0x00001000 0x1` and `p 1141 A=255`, and the game data names the open as a `check` anchor and the dword as a `resync` anchor
- **THEN** the script holds `wait open stage_tex.bin timeout ..` with the following polls still counted from `d`, later `wait mem 0x00001000 == 1 timeout ..`, then `wait polls 8` and `A=255` (1141 − 1133), and a test interpreter replaying the script reproduces the fixture's `p` lines

#### Scenario: Resync on an open is refused
- **WHEN** the game data marks an `open` anchor `"kind": "resync"`
- **THEN** `lower` exits 2 naming the anchor and the rule

#### Scenario: No game knowledge in the CLI
- **WHEN** `grep -nE '0x[0-9A-Fa-f]{5,}'` runs over `src/xboxrecomp_cli/replay.py` and `tests/test_replay_*.py`
- **THEN** it finds no guest address literal; every address the tool emits came from the game's `replay.json` or the recording

### Requirement: Replay is a strict scripted run on every host
A replay SHALL be the lowered script run through `RECOMP_INPUT_SCRIPT` with `RECOMP_INPUT_STRICT=1` and the game's `replay_env` (host devices off, `RECOMP_CONFIG=none`, stock scale, pacing and glow, `RECOMP_TRACE=flip,pacing=all,audio_host`), with no replay-only mode in the runtime. On the Mac `blinx2 replay run <name> --backend metal|cpu` SHALL use the launcher shared with `golden run` (its lock, headless dummy audio, run-directory layout) plus the `soak.py` stall rule (no flip for the stall window, also before the first; a thread dump, then stop), under `bench-logs/<stamp>-<backend>-replay-<name>/`, and `golden run`'s own behaviour SHALL not change. On the Linux/Proton host the recording SHALL be pushed explicitly (`bench sync` excludes `analysis/`) with `rsync -e 'ssh -o BatchMode=yes'` into `<BENCH_DIR>/cat/analysis/replay/<name>/`, and the replay SHALL run through `blinx2 bench run` with the replay environment in `BENCH_ENV`, which takes the run lock itself. For the Deck `blinx2 replay deck-cmd <name> --root R` SHALL print the `scp` of the script and of the package-data runner and the `ssh deck` command for the user to run in their own session against a scratch root holding a `blinx2 package` bundle, SHALL refuse a root under `~/Games`, and SHALL never run them.

#### Scenario: Mac replay run directory
- **WHEN** `blinx2 replay run stage1 --backend metal` finishes
- **THEN** the run directory holds `run-info.txt` with the replay environment, the exe sha256 and the cat and toolkit shas, `game-stdio.log`, `exit-code`, `save/` and `replay.txt` with the check's output, and `run-info.txt` records `RECOMP_HOST_PAD=0 RECOMP_KEYBOARD=0 RECOMP_MOUSE=0 RECOMP_INPUT_STRICT=1`

#### Scenario: Golden run unchanged by the shared launcher
- **WHEN** `tests/test_golden_run.py` runs after the launcher is shared
- **THEN** `golden run`'s environment, stop flip and exit codes are the ones the tests recorded before, and a fixture tail with no flip for the stall window yields STALL only for `replay run`

#### Scenario: Deck command is printed, not run
- **WHEN** `blinx2 replay deck-cmd stage1 --root ~/blx-scratch/replay` runs on the Mac
- **THEN** it prints `scp` lines for `replay.txt` and `deckrun.sh` and an `ssh deck` line and exits 0 without opening a connection, and the same with `--root ~/Games/BLiNX2` exits 2 with a refusal

### Requirement: A replay is checked per segment
`xbr replay check <run-dir|log> --rec --script [--baseline run-dir]` SHALL report, per segment and for the run: a verdict in the order CRASH (the game's crash tag or a signal exit), DESYNC (an `[INPUT] .. desync` line, with segment, step and poll), STALL (the launcher's verdict), INCOMPLETE (ended before `script done`), EXIT, ok, plus TAINTED when a `host port=0` line appears in a replay log and NONSTOCK when an `[ENHANCE]` line is not stock; flips/s and p50/p95/max frame ms per segment from the `[PACING] flip N t_us` intervals between the segment's `flip=` bounds through `pacing_stats.py`'s parsers (its `[GPU] flip` timestamp-difference fallback, its 3D rule of more than 2 batches), with PERF only against `--baseline`, a run on the same host and backend, when flips/s drop 25 % or more or frame ms rise 1.5×, and a NOTE below the game's `perf.floor_flips` median; without a baseline the numbers, and the recording's `f` rows, print as information; the poll offset between recording and replay at every `check` anchor; the first probe row that differs from the recording (integers equal, floats within the game data's tolerance) with its address name and poll, DRIFT when the difference persists to the next anchor, and the frame counter's offset reported apart; audio starves and underruns per segment from the `audio_host` and `[XA2]` lines, or `n/a (dummy audio)`. Exit codes SHALL be 1 on CRASH, DESYNC, DRIFT or PERF, 2 on INCOMPLETE or STALL, 0 otherwise.

#### Scenario: Desync named
- **WHEN** a synthetic log holds `[INPUT] t=41.2 poll=1240 flip=1312 desync step 7/90: wait mem 0x00001000 == 1 timeout 30`
- **THEN** `check` prints `DESYNC segment stage-start step 7/90 poll 1240 flip 1312` and exits 1

#### Scenario: Perf flagged only against a same-host baseline
- **WHEN** a segment's `[PACING] flip` intervals give 21 flips/s and `--baseline` names a run on the same host whose segment gave 30, while the recording's `f` rows gave 30 on another host
- **THEN** the segment's row says `PERF flips/s 21.0 (baseline 30.0, -30 %)` and `check` exits 1; the same run without `--baseline` prints `flips/s 21.0 (rec 30.0)` as information and exits 0

#### Scenario: Probe divergence that recovers
- **WHEN** a `[PEEK]` row differs from the recording's `k` row in `player-pos` by more than the tolerance and the rows match again after the next anchor
- **THEN** the report names `player-pos` with both values and the poll and marks the segment `diverged, recovered at <anchor>` without DRIFT

### Requirement: Recordings and game data have fixed homes and stay private
Game data for replay SHALL live in cat: `config/replay.json` (anchors with kinds, watches, probes with types and tolerances, `record_env`, `replay_env`, `perf`, `prefixes`) named by `game.toml` `[replay] json`, and `[replay] dir` naming the recordings directory, `analysis/replay/`. `record_env` SHALL pin the frame rules to stock (`RECOMP_PRESENT_PACING=spin`, `RECOMP_RENDER_SCALE=1`, `RECOMP_GLOW=on`) while keeping the config file for the person's bindings, and `record` SHALL refuse a recording whose `[ENHANCE]` lines are not stock by `[golden] enhance_stock`. Each recording SHALL be a directory `analysis/replay/<name>/` with `rec.txt`, `replay.txt` and `meta.json`. Recordings SHALL be treated as game output and a person's play: gitignored with `analysis/*`, so `export-public.sh` (which exports `git ls-tree`) never sees them; `scripts/test_gitignore.py` SHALL assert it; the public-push audit SHALL name `analysis/replay`; they move only between the user's Mac, the Linux/Proton host and the Deck. `[replay]` SHALL enter cat's `game.toml` in the same commit that bumps `[cli]` to a release whose schema knows it, and the CLI schema SHALL accept a `game.toml` without `[replay]`.

#### Scenario: Recording never tracked
- **WHEN** a recording is made under `analysis/replay/stage1/`
- **THEN** `git check-ignore analysis/replay/stage1/rec.txt` exits 0, `git status` in cat is clean, and `scripts/test_gitignore.py` passes

#### Scenario: Non-stock recording refused
- **WHEN** the recording run's log shows an `[ENHANCE]` line with `render.scale 2`
- **THEN** `blinx2 replay record` prints the line and exits 1 without lowering

#### Scenario: Game without replay data
- **WHEN** a `game.toml` has no `[replay]` table
- **THEN** `xbr` validates it and `xbr replay lower` without `--replay-json` exits 2 with "no [replay] table in game.toml"
