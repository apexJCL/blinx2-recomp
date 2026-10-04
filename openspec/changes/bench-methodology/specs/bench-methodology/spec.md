## ADDED Requirements

### Requirement: the Linux/Proton host runs the bench through bench.sh
Proton bench runs SHALL be started from the Mac with `scripts/bench.sh` (sync, build, run, logs) against the Linux/Proton host. Each run SHALL write its own `bench-logs/<stamp>/` directory.

#### Scenario: One run, one directory
- **WHEN** `scripts/bench.sh run` finishes
- **THEN** `bench-logs/<stamp>/` holds `run-info.txt`, `console.log`, `game-stdio.log`, `exit-code` and, when present, `xbox_kernel.log`

### Requirement: A bench run is reproducible from its record
Each run directory SHALL hold `run-info.txt` with the host, the Proton build, the full `RECOMP_*` environment, the exe sha, and the toolkit and cat commits plus the `gen/` provenance stamp the exe was built from.

#### Scenario: Rebuilding a run
- **WHEN** someone reads `run-info.txt` from an old run
- **THEN** it names the toolkit commit, the cat commit and the `gen/` stamp, so that the same exe can be rebuilt and checked against the recorded sha

### Requirement: The bench syncs only integration state
`bench.sh sync` SHALL refuse while `src/recomp/.gen-regenerating` exists, and SHALL sync only from the integration checkouts: cat on `main` and the toolkit on its integration branch.

#### Scenario: Regeneration in progress
- **WHEN** `src/recomp/.gen-regenerating` exists and `bench.sh sync` runs
- **THEN** it exits non-zero without copying anything

### Requirement: Movie windows are excluded from performance statistics
A frame SHALL be classed as a movie frame if it falls between the open and close of a `movie\*.sfd` file, or if it has 2 batches or fewer and one texture covering the viewport. Movie frames SHALL NOT count towards 3D statistics.

#### Scenario: Intro excluded
- **WHEN** a run plays the intro and then reaches the title stage
- **THEN** the report's 3D statistics start after `title_movie_1a.sfd` closes, and the intro frames are counted only under "movie"

### Requirement: 3D frames are reported with frame-time percentiles and dumps
For 3D frames the report SHALL give flips/s, p50/p95/p99 frame time in ms and fence releases per frame, from the per-flip log (`RECOMP_FLIP_LOG`). The report SHALL point to framebuffer dumps (`RECOMP_FB_DUMP`) of the same scenes, so that a fast but wrong frame is not counted as a success.

#### Scenario: 3D report
- **WHEN** a run with `RECOMP_FLIP_LOG=1` and `RECOMP_FB_DUMP` reaches a 3D scene
- **THEN** the report lists flips/s, p50/p95/p99 frame ms and fence per frame for the 3D frames only, with the dump file names next to them

### Requirement: Threads are attributed by role
Per-thread CPU figures SHALL be mapped to roles through the `[THREAD] tid=.. role=..` lines of the same run.

#### Scenario: Pegged thread is attributable
- **WHEN** `top -H` shows a thread above 90 % CPU
- **THEN** its tid maps to a role in the `[THREAD]` lines of the same run

### Requirement: Crash reports are symbolized offline
`bench.sh logs` SHALL produce `crash-symbols.txt` for every `[CRASH]` in a run, using the PDB shipped beside the exe.

#### Scenario: Crash in a run
- **WHEN** a run's log has a `[CRASH]` report
- **THEN** `crash-symbols.txt` names the guest function and native frames for it
