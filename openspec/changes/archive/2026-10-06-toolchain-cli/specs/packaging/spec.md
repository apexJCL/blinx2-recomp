## MODIFIED Requirements

### Requirement: One CLI on every build host
The project SHALL provide `blinx2.py`, a Python (≥ 3.9) standard-library CLI at the repository root, with `blinx2` (POSIX sh) and `blinx2.cmd` (Windows) wrappers, as the single entry point for setup, the pipeline stages, building, packaging and driving the Proton bench host on Windows, Linux and macOS build hosts. The build path SHALL NOT need bash, rsync, `sha256sum`/`shasum`, `sysctl`/`nproc`, `uname`, `curl` or `tar` on the build host. The former `scripts/pipeline.sh` and `scripts/bench.sh` SHALL NOT return: the pipeline stages are `blinx2 <stage>` and the bench is `blinx2 bench`. The CLI SHALL pass the toolkit directory it resolved to CMake, and on macOS SHALL set `DEVELOPER_DIR` to the Command Line Tools when it is unset and they exist.

#### Scenario: Same commands on each host
- **WHEN** a user runs `blinx2 setup`, `blinx2 analyze`, `blinx2 recomp` and `blinx2 package steamos` on a Windows, Linux or macOS host
- **THEN** each command does the same work with the same outputs, and none calls a host-only tool other than the macOS-only ones for the macos target

#### Scenario: pipeline.sh still works
- **WHEN** a developer needs what `scripts/pipeline.sh recomp` or `scripts/bench.sh golden` did (the scenario keeps its old name; both scripts are gone)
- **THEN** `blinx2 recomp` or `blinx2 bench golden` does it, with the same outputs, the same `.gen-regenerating` marker and the same exit code

#### Scenario: One place for the commands
- **WHEN** a developer looks for how to run a pipeline stage or the bench
- **THEN** `blinx2 --help` and `blinx2 bench --help` list them, and the repository has no `scripts/pipeline.sh` or `scripts/bench.sh`

#### Scenario: Worktree build
- **WHEN** the CLI builds in a git worktree that has no `../xboxrecomp`, with `XBOXRECOMP_DIR` set
- **THEN** CMake builds against that toolkit

### Requirement: Setup fetches a pinned, verified toolchain
`blinx2 setup` SHALL create the project environment `.venv/` with uv from the committed `uv.lock` (CMake, Ninja and the toolkit's Python dependencies, each verified by the sha256 in the lockfile), using the uv on `PATH` as the dev-tooling specification says (setup never downloads uv). It SHALL fetch the llvm-mingw release named in `config/toolchain.env` for the host's OS and architecture (Windows x86-64/arm64, Linux x86-64/aarch64, macOS universal) and, on Windows hosts, the pinned portable NSIS, and SHALL clone the pinned public toolkit commit into the gitignored `external/xboxrecomp` when no toolkit is found. Every download SHALL be checked against a sha256 pinned in the repository before it is unpacked; a mismatch SHALL delete the download and stop. `blinx2 doctor` SHALL report each piece, the uv in use and whether `uv.lock` is in step, and which targets the host can package, and for anything it does not install itself (`makensis` on Linux and macOS, the Command Line Tools and Homebrew libraries for the macos target) SHALL print the exact command to install it. The remaining prerequisites SHALL be Python ≥ 3.9, uv on `PATH`, git, the user's dump, and on macOS the Command Line Tools; pip and the venv module SHALL NOT be required.

#### Scenario: Fresh macOS host
- **WHEN** `blinx2 setup` runs on a macOS arm64 clone with no `third_party/` and no `.venv/`, and uv on `PATH`
- **THEN** llvm-mingw macos-universal is under `third_party/`, `.venv/` holds the locked cmake and ninja, and `doctor` lists windows, steamos and macos as packageable (or names the missing Homebrew package)

#### Scenario: Linux host without makensis
- **WHEN** `blinx2 doctor` runs on a Linux host with no `makensis`
- **THEN** it reports steamos as packageable, windows as blocked on `makensis`, and prints the package-manager command, and `blinx2 package steamos` succeeds

#### Scenario: Tampered download
- **WHEN** a fetched archive's sha256 differs from its pin
- **THEN** setup deletes it, unpacks nothing, and exits non-zero naming the asset and both hashes

#### Scenario: Quarantined toolchain
- **WHEN** on macOS the toolchain's `bin/clang` carries `com.apple.quarantine`
- **THEN** setup and doctor print the command that clears it and do not clear it

### Requirement: Help shows player commands first
`blinx2 --help` SHALL list the player commands (no arguments, `package`, `doctor`, `setup`) first, unchanged by this change. It SHALL list the pipeline stages, `build`, `pins` and `bench` under a separate "Developer commands" heading, with `bench` as one line that points at `blinx2 bench --help`. Every developer command SHALL keep its current behaviour.

#### Scenario: Help
- **WHEN** a user runs `./blinx2 --help`
- **THEN** `analyze`, `recomp`, `build` and `bench` appear only under "Developer commands", and the player block is byte-identical to the one before `bench` existed

#### Scenario: Bench help
- **WHEN** a developer runs `./blinx2 bench --help`
- **THEN** it lists the bench commands, their options, the `BENCH_*` configuration table, the host layout and the rule that the command takes the run lock itself and is never wrapped in an outer `flock`

## REMOVED Requirements

### Requirement: An incomplete dump is reported, not refused
**Reason**: The user decided (2026-10-06) that missing assets are not listed or checked at build or package time. The check was a BLiNX 2 heuristic over the XBE's strings (`adx/`, `voice/`, `movie/` name families), so it was game-specific and could only guess.
Its scenario, "Songs missing from the dump", goes with it.
**Migration**: None for players: nothing was ever refused. `blinx2 doctor` and `blinx2 package` no longer print the "dump looks incomplete" warning. A game-agnostic runtime report of the files the game fails to open is specified separately, in the toolkit.
