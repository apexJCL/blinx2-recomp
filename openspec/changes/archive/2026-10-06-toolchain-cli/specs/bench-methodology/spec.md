## MODIFIED Requirements

### Requirement: Running-game check before a bench run
Before starting any game (`run`, `golden`, and every other command that launches through its shared run step), after taking the run lock, `blinx2 bench` SHALL look for any other process whose command line names `cat_recomp.exe` or a `cat_recomp` executable, through `scripts/running_game.py`. When one is found it SHALL print a warning naming the pid and command line, say that results will be noisy, and continue. With `--kill-game` or `BENCH_KILL_GAME=1` it SHALL end those processes (SIGTERM, five seconds, then SIGKILL), re-check, and print what it ended. The warning SHALL also be written into the run's bench-logs directory. `scripts/golden.py` SHALL print the same warning on the Mac and SHALL have no kill option. The installed game SHALL never take the run lock.

#### Scenario: Installed game running
- **WHEN** the installed game is running on the host and `blinx2 bench run` starts
- **THEN** the lock is taken, a `WARN` line names the game's pid and command line, the run proceeds, and the warning appears in `bench-logs/<stamp>/`

#### Scenario: Kill on request
- **WHEN** the installed game is running and `blinx2 bench run --kill-game` starts
- **THEN** the game process is gone before the bench's game starts, and the output names the ended pid

#### Scenario: No foreign game
- **WHEN** nothing else runs `cat_recomp` and `blinx2 bench run` starts
- **THEN** no warning is printed and the run is unchanged

#### Scenario: Detection is unit-tested
- **WHEN** `scripts/test_running_game.py` feeds synthetic process listings (a Wine `Z:\...\cat_recomp.exe` line, a macOS `.../BLiNX2.app/Contents/MacOS/cat_recomp` line, an unrelated `cat_recomp_tool` line, and the caller's own pid)
- **THEN** the first two match, the last two do not

## ADDED Requirements

### Requirement: The bench is driven from the blinx2 CLI
`blinx2 bench <command>` SHALL provide the commands `setup`, `sync` (`--game-files`, `--game-files=reflink`), `build`, `run`, `tests`, `golden` (`--record`, `--force`), `pacing` (`--scen`, `--runs`, `--gate`, two environments), `logs`, `symbolize`, `shell`, `all`, `integrate` (`--golden`, `--dirty`) and `doctor`, with `--kill-game` accepted by every command that runs the game, reading the same `BENCH_*` configuration from the environment and from `scripts/bench.env` (`KEY=value` lines) as `scripts/bench.sh` did. The controller SHALL be standard-library Python under `scripts/benchlib/`, loaded only for `bench`. It SHALL send each host action to the bench host as a shell script on the standard input of `ssh -o BatchMode=yes` (directly, inside `distrobox enter`, or inside the host's run lock), with the script bodies kept as files under `scripts/benchlib/host/`. Every verdict, exit code (0, 1, 3 for INCONCLUSIVE, 75 for an hour's wait on the lock), run directory layout and `run-info.txt` field SHALL be the ones `scripts/bench.sh` produced.

#### Scenario: Golden verdict parity
- **WHEN** `blinx2 bench golden` and the last `scripts/bench.sh golden` (61ea933) run on the same integration build on the bench host
- **THEN** they print the same `check` result, exit with the same code, and their `bench-logs/<stamp>/` directories hold the same file names with the same `run-info.txt` fields

#### Scenario: Integrate parity
- **WHEN** `blinx2 bench integrate --golden` runs from the integration checkout on the same cat and toolkit commits as the last `scripts/bench.sh integrate --golden` (61ea933)
- **THEN** the host's `bench-provenance.txt` and `build-win/provenance.txt`, the printed gen digest and the exe sha256 are equal, and the golden verdict is the same

#### Scenario: Integrate guards
- **WHEN** `blinx2 bench integrate` runs from a tree that is not on `main`, or that is dirty without `--dirty`, or whose `src/recomp/gen/` is empty, or whose `.gen-regenerating` marker exists
- **THEN** it refuses before syncing, with the message `bench.sh` gave for that case

#### Scenario: Remote scripts are compared
- **WHEN** `scripts/test_bench_cli.py` runs with a fake `ssh` and `rsync` first on `PATH`
- **THEN** for `sync`, `build`, `run`, `tests`, `symbolize`, `logs`, `integrate --golden` and `pacing`, each ssh invocation's arguments and its script body (after the variable prologue is parsed to values) are equal between `blinx2 bench` and the reference, and each `rsync` invocation's arguments are equal

#### Scenario: Checks are unit-tested
- **WHEN** `scripts/test_bench_checks.py` feeds fixture run directories (a clean run, a `[CRASH]`, exit 137 at the limit, an early exit, flips under the floor on a busy host, the same on an idle host, a killed survivor, a survivor still alive, a log without flip lines)
- **THEN** `check_run_end` and `check_present_mismatch` print the message and return the code `bench.sh` gave for each

### Requirement: The run lock is taken on the host, by the host script, and never nested
The bench run lock SHALL remain `~/.recomp-run.lock` on the bench host, taken inside the host-side script on file descriptor 9 (`flock -n`, else a report of the holder from `lslocks` and `flock -w 3600 -E 75`), shared for builds and exclusive for runs and tests, written with the run's line once held, released when that script ends, and never inherited by the game or by any child. The controller SHALL NOT take, wait on or inspect the lock. Runs inside a pacing series SHALL pass `BENCH_LOCK_HELD=1` and not wait again; the series hold SHALL remain the `systemd-run --user` unit with `BENCH_HOLD_MAX`. `blinx2 bench --help` and the docs SHALL state that the command takes the lock itself and is never wrapped in an outer `flock`. The toolkit's `PROTON_RUN_LOCK` SHALL stay unset inside `tests`.

#### Scenario: Lock held elsewhere
- **WHEN** another agent holds `~/.recomp-run.lock` and `blinx2 bench run` starts
- **THEN** the host prints who holds it, waits up to an hour, and either runs or exits 75 with `bench.sh`'s message; the controller itself never opens the lock file

#### Scenario: Pacing series
- **WHEN** `blinx2 bench pacing` runs three A/B pairs
- **THEN** the lock is taken once by the hold unit, the six runs start with `BENCH_LOCK_HELD=1`, and the hold is released at the end or after `BENCH_HOLD_MAX` seconds if the controller dies

#### Scenario: Hold script tested from its file
- **WHEN** `scripts/test_bench_hold.py` runs
- **THEN** it reads `scripts/benchlib/host/hold_lock.sh` directly, with no regex over a shell heredoc, and its two cases pass

### Requirement: bench doctor checks the bench without changing it
`blinx2 bench doctor` SHALL check, without changing anything: `ssh -o BatchMode=yes BENCH_HOST true`, `rsync` on the controller, the host's `umu-run`, the `BENCH_BOX` distrobox, the current lock holder if any, and the host's `bench-provenance.txt`. A controller with no `ssh` on `PATH` SHALL get one line naming the OpenSSH client to install. The bench host SHALL remain a Linux host running Proton through `umu-run`; macOS and Linux are the controlling hosts (Windows is a deferred follow-up).

#### Scenario: Doctor on a working setup
- **WHEN** `blinx2 bench doctor` runs from the Mac against the bench host
- **THEN** every line reports found or ok, the lock line names the holder or "free", and the exit code is 0

#### Scenario: No ssh
- **WHEN** `blinx2 bench sync` runs on a controller with no `ssh` on `PATH`
- **THEN** it exits non-zero with one line naming the OpenSSH client to install for that OS
