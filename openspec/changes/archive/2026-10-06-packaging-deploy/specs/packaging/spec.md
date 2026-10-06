## ADDED Requirements

### Requirement: One CLI on every build host
The project SHALL provide `blinx2.py`, a Python (≥ 3.9) standard-library CLI at the repository root, with `blinx2` (POSIX sh) and `blinx2.cmd` (Windows) wrappers, as the single entry point for setup, the pipeline stages, building and packaging on Windows, Linux and macOS build hosts. The build path SHALL NOT need bash, rsync, `sha256sum`/`shasum`, `sysctl`/`nproc`, `uname`, `curl` or `tar` on the build host. `scripts/pipeline.sh` SHALL remain as a thin wrapper that forwards its stages to the CLI. The CLI SHALL pass the toolkit directory it resolved to CMake, and on macOS SHALL set `DEVELOPER_DIR` to the Command Line Tools when it is unset and they exist.

#### Scenario: Same commands on each host
- **WHEN** a user runs `blinx2 setup`, `blinx2 analyze`, `blinx2 recomp` and `blinx2 package steamos` on a Windows, Linux or macOS host
- **THEN** each command does the same work with the same outputs, and none calls a host-only tool other than the macOS-only ones for the macos target

#### Scenario: pipeline.sh still works
- **WHEN** a developer runs `scripts/pipeline.sh recomp`
- **THEN** it runs `blinx2.py recomp`, with the same outputs and the same `.gen-regenerating` marker as before

#### Scenario: Worktree build
- **WHEN** the CLI builds in a git worktree that has no `../xboxrecomp`, with `XBOXRECOMP_DIR` set
- **THEN** CMake builds against that toolkit

### Requirement: Setup fetches a pinned, verified toolchain
`blinx2 setup` SHALL create a project venv and install CMake, Ninja and the toolkit's Python dependencies from hash-pinned wheels, SHALL fetch the llvm-mingw release named in `config/toolchain.env` for the host's OS and architecture (Windows x86-64/arm64, Linux x86-64/aarch64, macOS universal) and, on Windows hosts, the pinned portable NSIS, and SHALL clone the pinned public toolkit commit into the gitignored `external/xboxrecomp` when no toolkit is found. Every download SHALL be checked against a sha256 pinned in the repository before it is unpacked; a mismatch SHALL delete the download and stop. `blinx2 doctor` SHALL report each piece and which targets the host can package, and for anything it does not install itself (`makensis` on Linux and macOS, the Command Line Tools and Homebrew libraries for the macos target) SHALL print the exact command to install it. The remaining prerequisites SHALL be Python ≥ 3.9 with venv and pip, git, the user's dump, and on macOS the Command Line Tools.

#### Scenario: Fresh macOS host
- **WHEN** `blinx2 setup` runs on a macOS arm64 clone with no `third_party/` and no `.venv/`
- **THEN** llvm-mingw macos-universal is under `third_party/`, `.venv/` holds the pinned cmake and ninja, and `doctor` lists windows, steamos and macos as packageable (or names the missing Homebrew package)

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
