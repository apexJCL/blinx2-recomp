# packaging Specification

## Purpose
Defines the `blinx2` command-line tool and the private bundles it builds: pinned toolchain setup on any build host, the host × target matrix, regeneration when inputs change, the bundle formats, manifest and version, icons and names, and the guards that keep bundles and game data out of the repository.

## Requirements

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

### Requirement: Host × target matrix
The windows and steamos targets SHALL be packageable on Windows, Linux and macOS build hosts, from the one llvm-mingw Windows x86-64 executable. The macos target SHALL be packageable only on a macOS host; on any other host `blinx2 package macos` and `blinx2 build macos` SHALL refuse before doing any work, naming the reason and the targets that host can package.

#### Scenario: macos on Linux
- **WHEN** `blinx2 package macos` runs on a Linux host
- **THEN** it exits non-zero with one line saying macos needs a macOS host and listing windows and steamos

#### Scenario: Windows build on Linux
- **WHEN** `blinx2 build windows` runs on a Linux x86-64 host after `setup`
- **THEN** `build-win/cat_recomp.exe` is a PE32+ x86-64 executable with `cat_recomp.pdb` beside it

### Requirement: Bundles are valid whatever the build host
A bundle SHALL install correctly on its target regardless of the build host's filesystem. The steamos bundle SHALL be a tar written with explicit file modes (scripts executable) and no symlinks; staged shell scripts SHALL use LF line endings, and the packager SHALL fail if one contains a carriage return; the repository SHALL mark shell, Python and template files `eol=lf` in `.gitattributes`. The packager SHALL refuse a staged path containing a Windows reserved device name or a component ending in a dot or space.

#### Scenario: steamos bundle built on Windows
- **WHEN** the steamos tar built on an NTFS host is unpacked on the gaming PC
- **THEN** `install.sh` and `launch.sh` are executable and have LF line endings

#### Scenario: CRLF script
- **WHEN** a staged `install.sh` contains `\r\n`
- **THEN** packaging stops and names the file

### Requirement: Self-contained private bundle per target
`blinx2 package <windows|steamos|macos>` SHALL build the target's executable, stage one payload (the program, `game_files/` from the user's dump, `enhance.toml.default`, `launch.env.default`, `manifest.json`, `SHA256SUMS`, `README.txt`, `LICENSE`, `NOTICE`), and wrap it as:
- **windows:** `dist/BLiNX2-<version>-windows/` holding an NSIS installer `BLiNX2-<version>-setup.exe` and `game_files/` beside it;
- **steamos:** `dist/BLiNX2-<version>-steamos.tar` holding one folder with the payload plus `install.sh`, `install_lib.py` and `launch.sh`;
- **macos:** `dist/BLiNX2-<version>.dmg` holding `BLiNX2.app` (the game files and every non-system dylib inside it) and an `Applications` symlink.

The payload SHALL exclude `default_analysis.json`, `UDATA/` and `TDATA/` from `game_files/`. The script SHALL refuse when generated code is missing or being regenerated, when `game_files/default.xbe` is missing or its title ID is not `0x4D530065`, and when the build is not a stock Release build unless an override is given, which the manifest records. The macOS `cat_recomp` SHALL remain the unchanged console build, byte-identical to `build/cat_recomp` before relinking, and the app SHALL pass `codesign --verify --deep --strict`.

#### Scenario: steamos bundle contents
- **WHEN** `blinx2 package steamos` completes and the tar is unpacked
- **THEN** the folder holds exactly the payload files, `install.sh`, `install_lib.py`, `launch.sh` and `running_game.py`; `sha256sum -c SHA256SUMS` passes inside it; and `game_files/default.xbe` is byte-identical to the repo's

#### Scenario: Windows bundle contents
- **WHEN** `blinx2 package windows` completes
- **THEN** the folder holds `BLiNX2-<version>-setup.exe` and `game_files/`, the exe is under 2 GB, and `strings` of it names `BLiNX2.exe`, `cat_recomp.exe` and `uninstall.exe`

#### Scenario: macOS app is self-contained
- **WHEN** `blinx2 package macos` completes on a macOS host
- **THEN** `otool -L` of `cat_recomp` and of every dylib in `Contents/Frameworks/` lists no path outside `/usr/lib`, `/System` and `@rpath`, `codesign --verify --deep --strict` passes, and the app launches from the mounted DMG with `RECOMP_WINDOW_QUIT_AFTER=10`

#### Scenario: Wrong or missing dump
- **WHEN** `game_files/default.xbe` is missing, or its certificate names another title
- **THEN** packaging refuses before building and names the path

#### Scenario: Non-stock build
- **WHEN** the CMake cache has `XBOXRECOMP_ENHANCE=OFF`, a non-empty `CAT_GEN_OPT` or a non-Release build type, and no override is given
- **THEN** packaging refuses and names the setting

### Requirement: Bundles never enter the repository or the public export
`dist/`, `*.dmg`, `*.exe`, `*.pdb`, `*.tar` and `*.nsi` SHALL be gitignored. `scripts/export-public.sh` SHALL fail when the exported commit tracks any path under `dist/` or any file with those extensions. `blinx2 package` SHALL end its output with a notice that the bundle contains the user's own copy of the game and is not to be shared, and `README.txt` SHALL open with the same notice.

#### Scenario: Bundle staged for commit
- **WHEN** `git status` runs after `blinx2 package`
- **THEN** nothing under `dist/` is untracked or staged

#### Scenario: Export with a tracked installer
- **WHEN** a test commit tracks `dist/x.exe` and `export-public.sh` runs on it
- **THEN** the export fails naming the path and writes no repository

### Requirement: Manifest and version
Every payload SHALL carry a `manifest.json` recording: schema, product, version and target; the build time; the cat and toolkit commits, branches and dirty state; the generated-code digest and file count; the build type, enhancements setting, generated-code options and compiler; the bundled host libraries (macOS); the data-layout version; and each file's path, size and sha256. The version SHALL be `<YYYYMMDD>.<HHMM>-c<cat7>-t<toolkit7>-g<gen8>`, with `-dirty<sha8>` appended when either tree has uncommitted or untracked changes, the hash derived from those changes. The manifest SHALL contain no host names, user names or absolute paths. `SHA256SUMS` SHALL hold the same hashes in coreutils format.

#### Scenario: Clean build version
- **WHEN** both trees are clean at cat `3b7dbb4…` and toolkit `fbfc46f…`, and the exe was built at 14:32 UTC on 2026-10-05
- **THEN** the version is `20261005.1432-c3b7dbb4-tfbfc46f-g<first 8 hex of the gen digest>`

#### Scenario: Two dirty builds of one commit
- **WHEN** two builds are packaged from the same commits with different uncommitted edits
- **THEN** their versions differ in the `-dirty<sha8>` suffix, and re-packaging either one unchanged reproduces its version

#### Scenario: No private data in the manifest
- **WHEN** a manifest is written
- **THEN** it contains neither the build machine's host name, nor `$HOME`, nor any absolute path

### Requirement: Launchers set the data location
Each target's launcher (`BLiNX2.exe` on Windows, `launch.sh` on steamos, `Contents/MacOS/BLiNX2` on macOS) SHALL point the game at user data outside the program files through `RECOMP_GAME_FILES`, `RECOMP_HDD_DIR`, `RECOMP_ENHANCE_CONFIG` and `RECOMP_STDIO_LOG`, SHALL read `launch.env.default` and then the user's `config/launch.env` with the user's values winning, SHALL copy `enhance.toml.default` to `config/enhance.toml` only when that file is absent, SHALL keep the newest `LOG_KEEP` logs, and SHALL start the game with the target's render backend (`d3d11` on Windows and under Proton, `metal` on macOS). The steamos launcher SHALL use `<root>/prefix` as its Wine prefix, pass paths in the `Z:` form, and refuse with a visible message when the game files or `umu-run` are missing. No launcher SHALL take or wait for any lock.

#### Scenario: Launch under Proton
- **WHEN** `<root>/BLiNX2` runs on the gaming PC after an install
- **THEN** the game starts through `umu-run` with `RECOMP_PB_BACKEND=d3d11` and `WINEPREFIX=<root>/prefix`, its log is under `<root>/logs/`, and `<root>/hdd/Partition0.img` exists afterwards

#### Scenario: User override survives an update
- **WHEN** the user's `config/launch.env` sets `RECOMP_PB_BACKEND=cpu` and a newer bundle is installed
- **THEN** the game starts with the CPU backend, and `config/launch.env` is byte-identical to before the install

#### Scenario: Existing enhance.toml is kept
- **WHEN** `config/enhance.toml` exists with `render.scale = 2` and a newer bundle is installed and launched
- **THEN** the file is byte-identical, `enhance.toml.default` beside it is the new default, and the game runs at `render.scale = 2`

### Requirement: One command packages for this host
Running `blinx2` with no arguments SHALL package for the host's native target: `macos` on macOS, `steamos` on Linux, `windows` on Windows. `blinx2.cmd` with no arguments SHALL do the same. `blinx2 package <target>` SHALL:
- run `setup` when the toolchain or toolkit that target needs is missing;
- regenerate `src/recomp/gen/` (analyze, then recomp) only when it is missing or stale;
- then build and package.

Before running anything, it SHALL print a plan naming each step it will run and why. When a prerequisite that `setup` cannot install is missing, it SHALL stop and print the one-line fix.

#### Scenario: Fresh clone to bundle
- **WHEN** a user runs `./blinx2` in a fresh clone on macOS, with only the game files in place
- **THEN** setup, generate, build and package run in order, and a DMG appears under `dist/`

#### Scenario: Nothing changed
- **WHEN** `./blinx2` runs again with no input changed
- **THEN** the plan lists only build and package, and no stage of the pipeline runs

### Requirement: Generated code is regenerated when its inputs change
The CLI SHALL record a generation key beside `src/recomp/gen/` once `recomp` succeeds. The key SHALL hold:
- the XBE's sha256;
- the toolkit commit, plus a hash of any uncommitted change under its `tools/`, including untracked or ignored files there that a stage reads (the icall database today);
- the sha256, or "absent", of every input file the pipeline stages read that the run does not itself produce;
- a hash of the argument lists the stages run;
- the extra arguments `recomp` ran with, which SHALL be empty for packaging.

Every pipeline stage command SHALL delete the key before it runs. `package` SHALL treat gen/ as stale when the key is absent or differs from the current one, or when the regeneration marker is present, and SHALL name the differing field in its plan line. The key and gen/ SHALL stay out of git.

#### Scenario: Toolkit icall database appears
- **WHEN** the toolkit's `tools/recomp/output/icall_targets.json` is created or changed after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Seed file edited
- **WHEN** `config/seed_functions.json` changes after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Interrupted generation
- **WHEN** a run is interrupted between analyze and the end of recomp
- **THEN** the next run regenerates, because the key is absent

### Requirement: Packaging uses its own stock build
`package` SHALL build in its own directories (`build-pkg-macos/`, `build-pkg-win/`). It SHALL configure them on every run with the stock options passed explicitly: Release, `XBOXRECOMP_ENHANCE=ON`, and `CAT_GEN_OPT` unset. It SHALL NOT read, configure or build the developer's `build/` or `build-win/`. If the packaging cache still fails the stock check, the refusal SHALL name each failing option and print the exact command that fixes it.

#### Scenario: Developer cache with enhancements off
- **WHEN** `build/CMakeCache.txt` has `XBOXRECOMP_ENHANCE=OFF` and the user runs `./blinx2 package macos`
- **THEN** packaging succeeds from `build-pkg-macos/`, and `build/CMakeCache.txt` is unchanged

#### Scenario: Forced non-stock option
- **WHEN** the packaging cache ends up non-stock
- **THEN** the refusal prints the option, its stock value, and the `--reconfigure` command

### Requirement: Help shows player commands first
`blinx2 --help` SHALL list the player commands (no arguments, `package`, `doctor`, `setup`) first, unchanged by this change. It SHALL list the pipeline stages, `build`, `pins` and `bench` under a separate "Developer commands" heading, with `bench` as one line that points at `blinx2 bench --help`. Every developer command SHALL keep its current behaviour.

#### Scenario: Help
- **WHEN** a user runs `./blinx2 --help`
- **THEN** `analyze`, `recomp`, `build` and `bench` appear only under "Developer commands", and the player block is byte-identical to the one before `bench` existed

#### Scenario: Bench help
- **WHEN** a developer runs `./blinx2 bench --help`
- **THEN** it lists the bench commands, their options, the `BENCH_*` configuration table, the host layout and the rule that the command takes the run lock itself and is never wrapped in an outer `flock`

### Requirement: Long steps show live progress and keep full logs
The CLI SHALL show a live progress view, built from the standard library only, for downloads, generation, build and wrapping.
- Progress SHALL come from:
  - download byte counts;
  - the output the toolkit tools print today;
  - Ninja's `[n/m]` status;
  - makensis file lines;
  - hdiutil percentages.
- The bar SHALL move only on real updates. Between coarse updates the view MAY show a time estimate as text, marked as an estimate, from this machine's previous run of the same step.
- Every child process's full output SHALL go to a log file under `build-logs/`. On failure the CLI SHALL print the step, its exit code, the log's last lines and the log path.
- The view SHALL fall back to plain line output, with no carriage returns or escape sequences, when stdout is not a TTY, with `--plain`, when `CI` is set, or when `TERM=dumb`.
- On Windows, the ANSI view SHALL be used only after enabling virtual-terminal mode succeeds. Otherwise the view SHALL fall back to single-line updates.
- The view SHALL use ASCII glyphs unless stdout's encoding is UTF-8, and SHALL keep drawing (elapsed time, spinner) while a child prints nothing.

#### Scenario: Unrecognised output
- **WHEN** a step's child prints lines no parser matches
- **THEN** the view shows a spinner and elapsed time, the lines reach the log, and the step's exit code alone decides success

#### Scenario: Build failure
- **WHEN** the build step fails
- **THEN** the CLI prints the last lines of the build log and its path under `build-logs/`, and exits non-zero

#### Scenario: Piped output
- **WHEN** `./blinx2 | tee out.txt` runs
- **THEN** `out.txt` contains no carriage returns or ANSI escape sequences

### Requirement: Bundles carry the game's icon, never committed
`package` SHALL extract the title image from the user's XBE (`$$XTIMAGE`, else `$$XSIMAGE`), decode its XPR0 DXT1, DXT3 or DXT5 texture with the standard library, and write PNG, `.icns` and `.ico` files from it. The icon SHALL be used as:
- the macOS app icon;
- the icon resource of the Windows launcher and of the game exe;
- the NSIS installer and uninstaller icon;
- a PNG beside the steamos launcher, used for the Steam shortcut.

The icon is game data. It SHALL be written only to packaging build directories and private bundles, never to tracked paths, and `.gitignore` SHALL cover `*.ico` and `*.icns`. If extraction or decoding fails, packaging SHALL use a generic icon generated without game data, print the reason, and continue. Tests SHALL use synthetic textures only. Builds without the opt-in icon option SHALL be unchanged. The icon set SHALL be rebuilt only when the XBE or the icon tool changes.

#### Scenario: Title image present
- **WHEN** the XBE has a 128×128 DXT1 `$$XTIMAGE`
- **THEN** the DMG's app shows that image as its icon, and `BLiNX2.exe` and `cat_recomp.exe` contain `RT_GROUP_ICON` resources

#### Scenario: No usable image
- **WHEN** the image section is missing or in an unsupported format
- **THEN** packaging prints `icon: generic (<reason>)` and the bundle uses the generic icon

#### Scenario: Nothing committed
- **WHEN** a package run finishes
- **THEN** `git status` shows no icon file

### Requirement: The macOS alert passes its message as data
The macOS launcher's failure alert SHALL pass its message to `osascript` as a run argument, never as script text, so a message with quotes or backslashes displays verbatim.

#### Scenario: Quoted path
- **WHEN** the launcher fails with a message containing `"` and `\`
- **THEN** `osascript` receives the message unchanged as an argument

### Requirement: Players see only the game's name
Everywhere a bundle shows the product's name (the installer's title, the Add/Remove Programs entry, the shortcuts, the macOS app name, launcher alerts, the steamos desktop entry and Steam shortcut, README.txt, and the CLI's messages) it SHALL be the game's name, `BLiNX 2`, with no project suffix. The name SHALL be defined once and rendered into every template.

#### Scenario: Windows uninstall entry
- **WHEN** the windows bundle is installed
- **THEN** Add/Remove Programs lists `BLiNX 2`
