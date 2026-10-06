## ADDED Requirements

### Requirement: Running-game check before a bench run
Before starting any game (`run`, `golden`, and every other command that launches through its shared run step), after taking the run lock, `scripts/bench.sh` SHALL look for any other process whose command line names `cat_recomp.exe` or a `cat_recomp` executable, through `scripts/running_game.py`. When one is found it SHALL print a warning naming the pid and command line, say that results will be noisy, and continue. With `--kill-game` or `BENCH_KILL_GAME=1` it SHALL end those processes (SIGTERM, five seconds, then SIGKILL), re-check, and print what it ended. The warning SHALL also be written into the run's bench-logs directory. `scripts/golden.py` SHALL print the same warning on the Mac and SHALL have no kill option. The installed game SHALL never take the run lock.

#### Scenario: Installed game running
- **WHEN** the installed game is running on the host and `bench.sh run` starts
- **THEN** the lock is taken, a `WARN` line names the game's pid and command line, the run proceeds, and the warning appears in `bench-logs/<stamp>/`

#### Scenario: Kill on request
- **WHEN** the installed game is running and `bench.sh run --kill-game` starts
- **THEN** the game process is gone before the bench's game starts, and the output names the ended pid

#### Scenario: No foreign game
- **WHEN** nothing else runs `cat_recomp` and `bench.sh run` starts
- **THEN** no warning is printed and the run is unchanged

#### Scenario: Detection is unit-tested
- **WHEN** `scripts/test_running_game.py` feeds synthetic process listings (a Wine `Z:\...\cat_recomp.exe` line, a macOS `.../BLiNX2.app/Contents/MacOS/cat_recomp` line, an unrelated `cat_recomp_tool` line, and the caller's own pid)
- **THEN** the first two match, the last two do not
