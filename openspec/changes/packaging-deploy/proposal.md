## Why

Today the game runs from a developer tree. You start `build/cat_recomp` or `build-win/cat_recomp.exe` from the project root, so that `game_files/` resolves against the working directory. That suits the bench and the goldens. It is not how a player keeps the game on the machine they play on, and the tree only builds on a macOS host set up by hand.

The user wants to build on whichever machine they have (Windows, Linux or macOS) and play on a SteamOS-like Linux gaming PC, on Windows, or on the Mac. Two examples: build on Windows and play on a SteamOS PC, or build on the Mac and play on the Mac. The build happens on the machine that owns the game, so it can produce a finished, self-contained bundle per target, game files included, in the shape a user of that platform expects:

- a Windows installer;
- an install script that adds the game to Steam;
- a drag-and-drop `.dmg`.

Each time the project moves forward, the user rebuilds, copies the bundle over and installs on top. Saves and settings are kept. Nothing is prebuilt or distributed. The repo gains the *capability* to build these bundles from the user's own dump, for the user's own machines, with as few manual installs as possible on any host.

## What Changes

- **One entry point on every host.** `blinx2.py`, a standard-library Python CLI at the repo root, has tiny wrappers: `blinx2` (sh) and `blinx2.cmd` (Windows). It owns everything a user runs:
  - `setup` fetches and verifies the toolchain for this host: llvm-mingw, CMake and Ninja (pip wheels into a project venv), the toolkit and its Python deps, and NSIS on Windows.
  - `doctor` reports what is present, what is missing, and which targets this host can build.
  - `parse` … `recomp` (or `analyze` plus `recomp`, or `all`), and `ghidra` (optional), are the pipeline stages.
  - `build [windows|macos]` builds the executable.
  - `package windows|steamos|macos` makes a bundle.

  `scripts/pipeline.sh` becomes a thin wrapper over the CLI for developers and existing notes. `scripts/package.sh` is never written.
- **Host × target matrix.**
  - The `windows` and `steamos` bundles build on any host. Both carry the same llvm-mingw Windows x86-64 exe.
  - `macos` builds only on a macOS host (Apple clang, `codesign`, `hdiutil`). The CLI refuses it elsewhere with one clear line.
- **Package.** `blinx2.py package <target>` builds the target, stages one payload, then wraps it under the gitignored `dist/`. The payload holds:
  - the exe or app, and the PDB;
  - the user's `game_files/`;
  - the default `enhance.toml` and `launch.env`;
  - `manifest.json`, `SHA256SUMS`, `README.txt`, `LICENSE` and `NOTICE`.

  The three wrappers:
  - **windows:** a folder, `BLiNX2-<version>-windows/`, holding an NSIS `BLiNX2-<version>-setup.exe` beside `game_files/` (decided by the user). The installer puts the program in `%LOCALAPPDATA%\Programs\BLiNX2\` and the user data in `%LOCALAPPDATA%\BLiNX2\`, and registers an uninstaller.
  - **steamos:** one file, `BLiNX2-<version>-steamos.tar`. Unpacked on the gaming PC, it holds the payload plus `install.sh`. `install.sh` installs or updates `~/Games/BLiNX2/` as a versioned tree with an atomic `current` switch and keeps three versions. With `--steam` it adds the game to Steam. It also offers `rollback`, `status`, `list` and `uninstall`. A tar keeps the scripts' executable bits and LF line endings whatever the build host's filesystem.
  - **macos:** `BLiNX2-<version>.dmg` with a drag-and-drop `BLiNX2.app`. The app carries the game files and the Homebrew dylibs it links, relinked and ad-hoc signed.
- **Moving a bundle is a plain copy.** There is no ssh deploy. The user copies the bundle by USB stick, network share or `scp`, then runs the installer on the target: `install.sh` from Desktop Mode on the gaming PC, `setup.exe` on Windows, a drag from the `.dmg` on the Mac.
- **Bundles are private.** They contain the user's game, which is not redistributable.
  - `dist/` and every bundle format are gitignored.
  - `export-public.sh` refuses to export a tree that tracks one.
  - Each bundle's `README.txt` opens with the notice.
- **Saves are never touched.** Install, update, rollback and uninstall never create, change or delete a save or the emulated hard disk, on any target. Saves live outside the program files and outside any Wine prefix, through `RECOMP_HDD_DIR`.
- **Configurable data location**, as game keys read through `recomp_env`:
  - `RECOMP_GAME_FILES=<dir>`: the dump;
  - `RECOMP_HDD_DIR=<dir>`: the emulated hard disk.

  Both are unset by default, which keeps today's behaviour byte for byte. Each target's launcher sets them.
- **The installed game and the bench.** The installed game never takes the bench run lock. `bench.sh` (and `golden.py` on the Mac) checks for a running game before a run and warns. With the opt-in `--kill-game` it ends the game.
- **Not ported now:** `bench.sh` and the golden-over-ssh dev harness stay bash, Mac-driven, and work as they do today, including reading `config/toolchain.env`. Porting them to the CLI is recorded as a follow-up.
- **Docs:** `docs/packaging.md` (per-host setup, the copy step, per-target install), a README section, `docs/env.md` rows for the two keys, and the CLI's own `--help`.

## How a user does it

**Prerequisites on any build host:**
- Python ≥ 3.9 and git;
- your own dump in `game_files/`;
- on macOS, the Command Line Tools (`xcode-select --install`), plus Homebrew `sdl2`, `openssl` and `libepoxy` for the macos target only;
- on Linux or macOS, a `makensis` package for the windows target only.

**Once per build host:**

```sh
./blinx2 setup            # Windows: blinx2 setup
./blinx2 doctor           # what this host can build, and what is missing
```

**Each version:**

```sh
./blinx2 analyze && ./blinx2 recomp     # when the pipeline, seeds or toolkit changed
./blinx2 package steamos                # dist/BLiNX2-<version>-steamos.tar
./blinx2 package windows                # dist/BLiNX2-<version>-windows/
./blinx2 package macos                  # dist/BLiNX2-<version>.dmg   (macOS hosts only)
```

**Gaming PC (Desktop Mode):**
1. Copy the `.tar` over by USB stick, network share or `scp`.
2. Unpack it: Dolphin's "Extract here", or `tar -xf BLiNX2-<version>-steamos.tar`.
3. In the unpacked folder, run `./install.sh --steam` the first time, and `./install.sh` for every later version.

Play from Game Mode. `./install.sh rollback` goes back one version.

**Windows:** copy the windows folder over as a whole and run `BLiNX2-<version>-setup.exe`. A newer setup run on top keeps the saves.

**Mac:** open the `.dmg` and drag `BLiNX2.app` to Applications, replacing the old one.

## Capabilities

### New Capabilities
- `packaging`:
  - the host CLI, its setup and doctor;
  - building on any host and the host × target matrix;
  - the common payload and the three bundle formats;
  - the manifest and version;
  - the private-artefact guards.
- `deployment`: what each installer does on its target. That covers the layout, user data and saves, the steamos versioned install, the Steam entry, rollback and uninstall.
- `bench-host`: the running-game check before bench and golden runs.

### Modified Capabilities
- `host-boot`: "Game file location" adds the optional `RECOMP_GAME_FILES` and `RECOMP_HDD_DIR` keys. Unset, the requirement is unchanged.

## Impact

- **Render backends:** none change. Launchers pick `d3d11` (Windows, Proton) or `metal` (macOS) through `RECOMP_PB_BACKEND`.
- **Build hosts:**
  - macOS arm64 builds all three targets.
  - Linux x86-64 or aarch64 builds windows and steamos. This is verified on the Linux gaming PC itself, in plain user space plus a distrobox for `makensis`.
  - Windows x86-64 or arm64 builds windows and steamos. There is no native Windows machine, so a Windows build host is covered by unit tests with fake toolchains only. The docs mark it "untested on a Windows host".
- **Targets:** the Linux/Proton gaming PC receives the steamos bundle. It is also where the Windows installer is smoke-tested, under Proton in a scratch prefix. The macOS target is tested on the Mac.
- **Goldens:** none move. The new keys are unset in every bench and golden run.
- **Toolkit:** no change. The CLI runs the toolkit's existing Python tools (`python -m tools.<name>`) from the project venv. Recorded, not acted on: the toolkit's default save root (`xboxrecomp`) is shared across titles.
- **Code:**
  - `src/main.c`: path resolution and the missing-XBE message.
  - `src/env/recomp_env_game.h`: two rows.
  - `packaging/windows/launcher.c`: a 60-line Windows launcher.
- **New files:**
  - `blinx2.py`, `blinx2`, `blinx2.cmd`;
  - `scripts/package_lib.py`, `scripts/running_game.py`;
  - `scripts/test_blinx2_cli.py`, `scripts/test_package_lib.py`, `scripts/test_steamos_install.py`, `scripts/test_running_game.py`;
  - `config/toolchain.env` and `config/setup-pins.json` (digests), `config/requirements-setup.txt` (hashed pip pins);
  - `packaging/`, `.gitattributes`, `docs/packaging.md`.
- **Changed scripts:**
  - `pipeline.sh` becomes a wrapper over the CLI.
  - `bench.sh` gets the toolchain tag, the running-game check and `--kill-game`; nothing else changes.
  - `golden.py` gets the running-game warning.
  - `export-public.sh` gets the bundle guard.
- **Other:** `.gitignore` gains `dist/`, `*.dmg`, `*.exe`, `*.pdb`, `*.nsi`, `*.tar`, `.venv/` and `external/`.
- **Legal:** no binaries, bundles or game data go in the repo or any release. The bundles exist only on the user's machines.
