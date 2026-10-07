## MODIFIED Requirements

### Requirement: One CLI on every build host
The toolchain CLI SHALL be the `xboxrecomp-cli` package (`xbr`), a Python (≥ 3.12, run through uv) standard-library program that reads the game's `game.toml`, as the single entry point for setup, the pipeline stages, building, packaging and driving the Proton bench host on Windows, Linux and macOS build hosts. The game SHALL ship `blinx2` (POSIX sh), `blinx2.cmd` and the `blinx2.py` bootstrap (standard-library Python ≥ 3.9) that find and exec the pinned CLI, so the user's commands do not change. The build path SHALL NOT need bash, rsync, `sha256sum`/`shasum`, `sysctl`/`nproc`, `uname`, `curl` or `tar` on the build host. The CLI SHALL pass the toolkit directory it resolved to CMake, and on macOS SHALL set `DEVELOPER_DIR` to the Command Line Tools when it is unset and they exist. The CLI SHALL carry no value specific to one game; `game.toml` carries them.

#### Scenario: Same commands on each host
- **WHEN** a user runs `blinx2 setup`, `blinx2 analyze`, `blinx2 recomp` and `blinx2 package steamos` on a Windows, Linux or macOS host
- **THEN** each command does the same work with the same outputs, and none calls a host-only tool other than the macOS-only ones for the macos target

#### Scenario: pipeline.sh still works
- **WHEN** a developer needs what `scripts/pipeline.sh recomp` or `scripts/bench.sh golden` did (the scenario keeps its old name; both scripts are gone)
- **THEN** `blinx2 recomp` or `blinx2 bench golden` does it, with the same outputs, the same `.gen-regenerating` marker and the same exit code

#### Scenario: One place for the commands
- **WHEN** a developer looks for how to run a pipeline stage or the bench
- **THEN** `blinx2 --help` and `blinx2 bench --help` list them, the repository has no `scripts/pipeline.sh` or `scripts/bench.sh`, and the code behind them is in `xboxrecomp-cli`

#### Scenario: Worktree build
- **WHEN** the CLI builds in a git worktree that has no `../xboxrecomp`, with `XBOXRECOMP_DIR` set
- **THEN** CMake builds against that toolkit

#### Scenario: Second game
- **WHEN** a project with its own `game.toml`, dump and wrapper runs `./<slug> setup`, `analyze`, `recomp` and `build`
- **THEN** the same CLI, at the commit that game pins, does the work with that game's values and no change to the CLI

### Requirement: Setup fetches a pinned, verified toolchain
`blinx2 setup` SHALL create the game's tools environment `.venv/` with uv from the game's committed `uv.lock` (CMake, Ninja and the toolkit's Python dependencies, each verified by the sha256 in the lockfile), using the uv on `PATH` (setup never downloads uv). It SHALL fetch the llvm-mingw release named by `toolchain.llvm_mingw` in `game.toml` for the host's OS and architecture (Windows x86-64/arm64, Linux x86-64/aarch64, macOS universal) and, on Windows hosts, the pinned portable NSIS, and SHALL clone the toolkit named by `[toolkit]` at its pinned commit into the gitignored `external/xboxrecomp` when no toolkit is found; the wrapper SHALL likewise have cloned the CLI named by `[cli]` at its pinned commit into `external/xboxrecomp-cli` when none is found. Every download SHALL be checked against a sha256 pinned in `config/setup-pins.json` before it is unpacked; a mismatch SHALL delete the download and stop. `blinx2 doctor` SHALL report each piece, the uv in use, whether `uv.lock` is in step, the CLI and the toolkit with their pins, and which targets the host can package, and for anything it does not install itself (`makensis` on Linux and macOS, the Command Line Tools and the Homebrew formulae `package.brew` names for the macos target) SHALL print the exact command to install it. The remaining prerequisites SHALL be Python ≥ 3.9 for the bootstrap, uv on `PATH`, git, the user's dump, and on macOS the Command Line Tools.

#### Scenario: Fresh macOS host
- **WHEN** `blinx2 setup` runs on a macOS arm64 clone with no `third_party/`, no `.venv/` and no CLI or toolkit beside it, with uv on `PATH` and `cli.url` set
- **THEN** the CLI and the toolkit are under `external/` at their pins, llvm-mingw macos-universal is under `third_party/`, `.venv/` holds the locked cmake and ninja, and `doctor` lists windows, steamos and macos as packageable (or names the missing Homebrew package)

#### Scenario: Linux host without makensis
- **WHEN** `blinx2 doctor` runs on a Linux host with no `makensis`
- **THEN** it reports steamos as packageable, windows as blocked on `makensis`, and prints the package-manager command, and `blinx2 package steamos` succeeds

#### Scenario: Tampered download
- **WHEN** a fetched archive's sha256 differs from its pin
- **THEN** setup deletes it, unpacks nothing, and exits non-zero naming the asset and both hashes

#### Scenario: Quarantined toolchain
- **WHEN** on macOS the toolchain's `bin/clang` carries `com.apple.quarantine`
- **THEN** setup and doctor print the command that clears it and do not clear it

### Requirement: Manifest and version
Each bundle SHALL carry `manifest.json` with the schema version, product and name, the bundle version, target, build time, the sources (`cat`, `toolkit` and `cli`, each with commit, branch, dirty flag and dirty-path count), the gen/ digest and file count, the build type, enhancement state, generated-code options, compiler and any overrides, the data layout version, the optional `"xbe"` note when the dump is not one `xbe.sha256` lists, and every file's path, sha256 and size; plus `SHA256SUMS` in `sha256sum` format. The version SHALL be `<UTC build time>-c<game sha7>-t<toolkit sha7>-g<gen digest 8>`, with `-dirty<hash>` appended when the game, the toolkit or the CLI tree has uncommitted changes, so two dirty builds of one commit with different changes get different versions. The manifest SHALL hold no absolute path, home directory or host name.

#### Scenario: Clean build version
- **WHEN** the game, the toolkit and the CLI trees are clean at commits A, B and C
- **THEN** the version is `<time>-c<A7>-t<B7>-g<digest8>` with no `-dirty`, and `sources.cli.commit` is C

#### Scenario: Two dirty builds of one commit
- **WHEN** two bundles are built from the same commit with different uncommitted changes in any of the three trees
- **THEN** their versions differ in the `-dirty<hash>` suffix

#### Scenario: No private data in the manifest
- **WHEN** a bundle is built on a machine whose home directory or host name would appear in a path
- **THEN** `manifest.json` contains neither, and `package` refuses to write a manifest that does
