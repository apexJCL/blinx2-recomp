## MODIFIED Requirements

### Requirement: Setup fetches a pinned, verified toolchain
`blinx2 setup` SHALL create the project environment `.venv/` with uv from the committed `uv.lock` (CMake, Ninja and the toolkit's Python dependencies, each verified by the sha256 in the lockfile), using the uv on `PATH` as the dev-tooling specification says (setup never downloads uv). It SHALL fetch the llvm-mingw release named in `config/toolchain.env` for the host's OS and architecture (Windows x86-64/arm64, Linux x86-64/aarch64, macOS universal) and, on Windows hosts, the pinned portable NSIS, and SHALL clone the pinned public toolkit commit into the gitignored `external/xboxrecomp` when no toolkit is found. Every download SHALL be checked against a sha256 pinned in the repository before it is unpacked; a mismatch SHALL delete the download and stop. `blinx2 doctor` SHALL report each piece, the uv in use and whether `uv.lock` is in step, and which targets the host can package, and for anything it does not install itself (`makensis` on Linux and macOS, the Command Line Tools and the Homebrew libraries `game.toml` `[package] brew` names for the macos target, `sdl3`, `openssl` and `libepoxy` for this game) SHALL print the exact command to install it, and SHALL print the installed SDL3 version against the `sdl3` pin with a warning when its major.minor is older. The remaining prerequisites SHALL be Python ≥ 3.9, uv on `PATH`, git, the user's dump, and on macOS the Command Line Tools; pip and the venv module SHALL NOT be required.

#### Scenario: Fresh macOS host
- **WHEN** `blinx2 setup` runs on a macOS arm64 clone with no `third_party/` and no `.venv/`, and uv on `PATH`
- **THEN** llvm-mingw macos-universal is under `third_party/`, `.venv/` holds the locked cmake and ninja, and `doctor` lists windows, steamos and macos as packageable (or names the missing Homebrew package, `sdl3` among them, never `sdl2`)

#### Scenario: Installed SDL3 older than the pin
- **WHEN** `blinx2 doctor` runs on macOS with Homebrew's SDL3 at a major.minor older than `game.toml` `[toolchain] sdl3`
- **THEN** it prints the `sdl3:` line with both versions and a `warning:`, and the macos target stays packageable

#### Scenario: Linux host without makensis
- **WHEN** `blinx2 doctor` runs on a Linux host with no `makensis`
- **THEN** it reports steamos as packageable, windows as blocked on `makensis`, and prints the package-manager command, and `blinx2 package steamos` succeeds

#### Scenario: Tampered download
- **WHEN** a fetched archive's sha256 differs from its pin
- **THEN** setup deletes it, unpacks nothing, and exits non-zero naming the asset and both hashes

#### Scenario: Quarantined toolchain
- **WHEN** on macOS the toolchain's `bin/clang` carries `com.apple.quarantine`
- **THEN** setup and doctor print the command that clears it and do not clear it

### Requirement: Self-contained private bundle per target
`blinx2 package <windows|steamos|macos>` SHALL build the target's executable, stage one payload (the program, `game_files/` from the user's dump, `config.default.toml`, `launch.env.default`, `manifest.json`, `SHA256SUMS`, `README.txt`, `LICENSE`, `NOTICE`), and wrap it as:
- **windows:** `dist/BLiNX2-<version>-windows/` holding an NSIS installer `BLiNX2-<version>-setup.exe` and `game_files/` beside it;
- **steamos:** `dist/BLiNX2-<version>-steamos.tar` holding one folder with the payload plus `install.sh`, `install_lib.py` and `launch.sh`; it is the Windows build run under Proton and carries no SDL;
- **macos:** `dist/BLiNX2-<version>.dmg` holding `BLiNX2.app` (the game files and every non-system dylib inside it, `libSDL3.0.dylib` among them as an ordinary `otool -L` dependency, with no `libSDL2*` and no SDL companion entry) and an `Applications` symlink.

`config.default.toml` is the game's `packaging/config.default.toml`, staged beside the executable on Windows and steamos and in `Contents/Resources/` on macOS; it is read by the game at every launch and never copied into the user's data. Packaging SHALL refuse before building, naming the rename, when the game's packaging content holds `enhance.toml.default` and no `config.default.toml`. The payload SHALL exclude `default_analysis.json`, `UDATA/` and `TDATA/` from `game_files/`. The script SHALL refuse when generated code is missing or being regenerated, when `game_files/default.xbe` is missing or its title ID is not `0x4D530065`, and when the build is not a stock Release build unless an override is given, which the manifest records. The macOS `cat_recomp` SHALL remain the unchanged console build, byte-identical to `build/cat_recomp` before relinking, and the app SHALL pass `codesign --verify --deep --strict`.

#### Scenario: steamos bundle contents
- **WHEN** `blinx2 package steamos` completes and the tar is unpacked
- **THEN** the folder holds exactly the payload files (`config.default.toml` at its top level), `install.sh`, `install_lib.py`, `launch.sh` and `running_game.py`; `sha256sum -c SHA256SUMS` passes inside it; and `game_files/default.xbe` is byte-identical to the repo's

#### Scenario: Windows bundle contents
- **WHEN** `blinx2 package windows` completes
- **THEN** the folder holds `BLiNX2-<version>-setup.exe` and `game_files/`, the exe is under 2 GB, and `strings` of it names `BLiNX2.exe`, `cat_recomp.exe`, `uninstall.exe` and `config.default.toml`

#### Scenario: macOS app is self-contained
- **WHEN** `blinx2 package macos` completes on a macOS host
- **THEN** `otool -L` of `cat_recomp` and of every dylib in `Contents/Frameworks/` lists no path outside `/usr/lib`, `/System` and `@rpath`, `Contents/Frameworks/` holds `libSDL3.0.dylib` and nothing named `libSDL2`, `codesign --verify --deep --strict` passes, `Contents/Resources/config.default.toml` exists, and the app launches from the mounted DMG with `RECOMP_WINDOW_QUIT_AFTER=10` logging that file on its `[ENHANCE] config:` line

#### Scenario: Wrong or missing dump
- **WHEN** `game_files/default.xbe` is missing, or its certificate names another title
- **THEN** packaging refuses before building and names the path

#### Scenario: Non-stock build
- **WHEN** the CMake cache has `XBOXRECOMP_ENHANCE=OFF`, a non-empty `CAT_GEN_OPT` or a non-Release build type, and no override is given
- **THEN** packaging refuses and names the setting

#### Scenario: Game not yet renamed
- **WHEN** the game's `packaging/` holds `enhance.toml.default` and no `config.default.toml`
- **THEN** packaging refuses before building with a message naming both file names
