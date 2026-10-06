## Context

**How the game finds its files today** (cat `main` c3b7dbb, toolkit `posix-host/portability` fbfc46f):

- **XBE:** `src/main.c` loads `game_files/default.xbe` relative to the working directory and passes `"game_files"` to `xbox_path_init(game_dir, NULL)`. `D:\` and `\Device\CdRom0\` map there. Nothing writes there.
- **Save root:** cat passes `save_dir = NULL`, so the toolkit picks `%LOCALAPPDATA%\xboxrecomp` (Windows and Proton, which is *inside the Wine prefix*) or `$XDG_DATA_HOME/xboxrecomp`, else `~/.local/share/xboxrecomp` (POSIX, including macOS). It holds `Partition0..5.img` (sparse), `TitleData/`, `UserData/`, `Cache/`, `SystemData/`, and the UDATA/TDATA save games unless `RECOMP_SAVE_DIR` moves those. The root is named after the toolkit, not the title, so two titles share it.
- **`enhance.toml`:** `xbox_enhance_init(recomp_exe_dir(), NULL)` reads `<exe dir>/enhance.toml`; `RECOMP_ENHANCE_CONFIG=<path>|none` replaces it. Golden runs pin `none`.
- **Logs:** `RECOMP_STDIO_LOG=<path>` captures stdout and stderr (Proton drops them otherwise). `xbox_kernel.log` opens relative to the working directory.
- **Runtime files:** the exe only. Metal compiles shaders at run time; D3D11 loads `d3dcompiler_47.dll` from Proton. The llvm-mingw exe imports UCRT and system DLLs only.
- **The macOS build** is a console program (the `host-build` spec keeps it so) that links Homebrew dylibs dynamically: `libcrypto.4`, `libSDL2-2.0.0` (sdl2-compat, which itself links `libSDL3`) and `libepoxy.0`.
- **The dump** is 2.4 GB in 15 entries. `movie/` is 2.0 GB of SFD video, `adx/`, `media.ipk` and `lng_us.ipk` are about 110 MB each; none of it compresses. `default_analysis.json` is a pipeline artefact, not game data.
- **Defaults the bench sets** for a Proton run: `WINEPREFIX`, `GAMEID=umu-default`, `PROTONPATH=GE-Proton`, `RECOMP_PB_BACKEND=d3d11`, plus whatever `cmd_run` adds for a windowed run (task 4.1 copies that list).

**Building and the bench:** run-under-proton task 1.5 cross-built the Windows exe on the Mac with `third_party/llvm-mingw-20260922-ucrt-macos-universal` in 199 s. `bench.sh` builds the same tree on the Linux host under a shared `flock` on `~/.recomp-run.lock`; game runs take it exclusively. `bench.sh` already computes `tree_state` and `gen_digest_local`.

**The gaming host** (read-only, 2026-10-05): a SteamOS-like Linux gaming PC that boots into Game Mode. It has `/usr/bin/steamos-add-to-steam`, `umu-run`, `rsync`, `flock`, `python3`, and `GE-Proton11-7` in `compatibilitytools.d`. `~/Games` does not exist yet. The home filesystem is btrfs.

**Tooling per build host** (checked 2026-10-05):
- llvm-mingw 20260922 publishes UCRT builds for every host this change targets, each with a sha256 `digest` in the GitHub releases API: `-ucrt-x86_64.zip` and `-ucrt-aarch64.zip` (Windows), `-ucrt-ubuntu-22.04-x86_64.tar.xz` and `-ucrt-ubuntu-22.04-aarch64.tar.xz` (Linux, glibc ≥ 2.35; it runs on Fedora-based hosts), and `-ucrt-macos-universal.tar.xz`.
- CMake and Ninja ship as PyPI wheels (`cmake`, `ninja`) for Windows x86-64/arm64, manylinux x86-64/aarch64 and macOS universal2, so a project venv provides both with no system install.
- NSIS: `makensis` 3.13 is a Homebrew bottle on macOS (no Wine). Linux has it as a distribution package (`nsis` on Debian/Ubuntu/Arch, `mingw32-nsis` on Fedora). On Windows the official NSIS zip is portable (no installer, no admin). Inno Setup's compiler is a Windows program and needs Wine elsewhere, so it is not used. NSIS limits an installer to 2 GB, which the dump alone exceeds.
- The Linux gaming PC (an immutable, Fedora-based SteamOS-like distribution) has `python3` 3.14, `git`, `rsync`, `toolbox` and `distrobox` (a Fedora 42 box exists), and no `makensis` on the host.
- macOS: `hdiutil`, `codesign`, `otool` and `install_name_tool` come with the Command Line Tools; the macos target's SDL2, OpenSSL and libepoxy come from Homebrew. sdl2-compat does not link SDL3: it `dlopen`s it, trying `@loader_path/libSDL3.dylib` first.
- The toolkit's Python tools need `capstone` and `pefile` (plus `pytest`, `numpy` for its tests), all with wheels for the three host OSes. The toolkit is Windows-first upstream (`py -3 tools/...`).
- Ghidra only improves function names (`pipeline.sh ghidra`, then `names`). The hand-written overrides use `sub_<addr>` names, so the default path does not need it; the main checkout's current `gen/` was made with Ghidra names, so a build without Ghidra has a different gen digest and version.

## Goals / Non-Goals

**Goals**
- From a Windows, Linux or macOS build host, with one CLI and no manual installs beyond Python, git and (macOS) the Command Line Tools, produce one self-contained private bundle per target, game files included, in the native shape: a Windows installer, a steamos install script, a macOS `.dmg`.
- Installing a newer bundle on top keeps saves and settings on every target. Saves are never written, moved or deleted by any install, update, rollback or uninstall.
- The game's files, saves, logs and config live outside the program files and outside any Wine prefix. With nothing configured, the stock behaviour is unchanged.
- The installed game never interferes with the bench by locking; the bench detects it instead.
- Generic tracked files: no host names, user names or private paths; no bundle can enter the repo or the public export.

**Non-goals**
- Distributing binaries, release pages, CI artifacts, network auto-update, notarization, Flatpak or AppImage.
- Native Windows verification: the installer is built and smoke-tested under Proton only.
- Building the macos target on a non-macOS host (Apple toolchain, `codesign`, `hdiutil`).
- Deploying over ssh. The user copies the bundle (USB stick, network share, `scp`) and runs the installer on the target.
- Porting `bench.sh` and the golden-over-ssh harness to the CLI. They stay bash, driven from the Mac, unchanged apart from 8; a port is a follow-up.
- Fetching NSIS on Linux and macOS hosts: it comes from the package manager (see 1c).
- Save migration from today's default save root (an opt-in `--import-saves` on steamos only).
- Changing the toolkit.

## Decisions

### 1. One CLI on every build host

#### 1a. `blinx2.py`

A standard-library Python (≥ 3.9) CLI at the repo root is the only thing a user runs. `blinx2` (`#!/bin/sh`, `exec python3 "$(dirname "$0")/blinx2.py" "$@"`) and `blinx2.cmd` (`@py -3 "%~dp0blinx2.py" %*`, falling back to `python`) are the wrappers. Subcommands:

| Command | Does |
|---|---|
| `setup [--no-toolkit] [--dev] [--force]` | creates `.venv/` (the project venv), installs the pinned CMake, Ninja and toolkit deps with hash checking (`--dev` adds the toolkit's test deps), fetches llvm-mingw (and NSIS on Windows) with pinned digests, clones the toolkit at its pinned commit when none is found, and ends with `doctor` |
| `doctor` | one line per piece (found, version, source), then which targets this host can package and what is missing for the others; exit 0 when at least the steamos target is possible |
| `parse` `disasm` `funcid` `abi` `names` `recomp`, `analyze`, `all` | the pipeline stages, ported from `pipeline.sh` with the same inputs and outputs and the same `.gen-regenerating` marker |
| `ghidra` | optional: needs `GHIDRA_HOME` and a PyGhidra venv, as today; `analyze` runs `names` only when an export exists |
| `build [windows|macos] [cmake args]` | configures and builds `build-win/` (llvm-mingw) or `build/` (macOS host only); with no target, `macos` on a macOS host and `windows` elsewhere |
| `package windows|steamos|macos [options]` | section 3 |

Why one Python CLI: Python is already required by the toolkit, it is on every host this change targets (and on the SteamOS target), and it removes every host-only tool from the build path (1d). Bash scripts would need MSYS or WSL on Windows, which is the hoop the user wants gone.

**`pipeline.sh` stays, as a thin wrapper**: it maps its stage names onto `blinx2.py` (`build` → `build macos` on macOS, `build-win` → `build windows`) and keeps its usage header pointing at the CLI. Reasons: `bench.sh` messages, `TASKS.md`, openspec changes, memory notes and agents' habits all name `pipeline.sh <stage>`, and a wrapper keeps them true at no cost. All logic lives in the CLI, so there is one implementation. It is a dev convenience; the docs teach `blinx2`.

**Toolkit resolution** is the existing order (`XBOXRECOMP_DIR`, `external/xboxrecomp`, `../xboxrecomp`), and the CLI always passes `-DXBOXRECOMP_DIR=<resolved>` to CMake (a worktree has no `../xboxrecomp`; this bit the first worktree build). The toolkit tools run as `python -m tools.<name>` from the toolkit root with the project venv's interpreter. A toolkit `.venv` is no longer needed; `XBOXRECOMP_PYTHON` overrides the interpreter for anyone who keeps one.

#### 1b. `setup`: what it fetches, and how it is verified

- **Pins.** `config/toolchain.env` keeps `LLVM_MINGW_TAG=20260922` (bench.sh reads it, unchanged). `config/setup-pins.json` holds, per pinned artefact: URL, sha256 and size. Entries: each llvm-mingw asset of the tag listed in Context; the NSIS Windows zip; the toolkit repo URL and commit. A download whose sha256 differs from the pin is deleted and `setup` stops. Nothing unpinned is executed. `config/requirements-setup.txt` pins `cmake`, `ninja`, `capstone`, `pefile` (and, under `setup --dev`, `pytest`, `numpy`) with every platform wheel's hash, so `pip install --require-hashes --only-binary :all:` refuses anything else. Hash mode needs every transitive dependency pinned too: `pytest`'s (`iniconfig`, `packaging`, `pluggy`, plus `colorama` on Windows and `exceptiongroup`/`tomli` below 3.11) go in with environment markers; `cmake`, `ninja`, `capstone` and `pefile` have none. A maintainer-only `blinx2.py pins refresh` regenerates both files from the GitHub and PyPI JSON APIs; an offline test checks that every host × arch the CLI can select has an llvm-mingw pin (the tag's other assets are not pinned).
- **llvm-mingw** per host: Windows x86-64/arm64 → the `ucrt-x86_64` / `ucrt-aarch64` zip (`zipfile`); Linux x86-64/aarch64 → the `ubuntu-22.04` tar.xz (`tarfile`, keeps modes); macOS → `macos-universal`. Unpacked into `third_party/llvm-mingw-<tag>-ucrt-<host>/` with `.tag`, atomically (`.partial` then rename). Every archive member is checked before extraction (no absolute path, no `..`, no link pointing outside the tree), since Python < 3.12 has no `tarfile` extraction filter. On macOS a quarantine attribute (a browser download unpacked by hand) is reported with the `xattr -dr` fix, not cleared. On Windows the zip carries no executable-bit problem; on Linux `tarfile` restores modes.
- **CMake and Ninja**: the pip wheels in `.venv/`; the CLI puts `.venv/bin` (`.venv\Scripts`) first on `PATH` for builds. A system `cmake` ≥ 3.20 or `ninja` is used only if `--system-tools` is passed. The generator is Ninja; the Unix Makefiles fallback exists for `--system-tools` on Linux and macOS only, since a Windows host has no `make` (llvm-mingw ships none) and CMake's default there would be Visual Studio.
- **NSIS** (windows target only): Windows → the pinned portable zip (published on SourceForge; `urllib` follows the mirror redirect, and the sha256 pin is what makes the mirror trustworthy) into `third_party/nsis-<ver>/`. Linux and macOS → the package manager, which `setup` does not run: `doctor` prints the exact command for the host (`brew install makensis`, `sudo apt install nsis`, `sudo dnf install mingw32-nsis`, or on an immutable SteamOS-like host, inside a toolbox/distrobox). Why not a portable build there: NSIS publishes no Linux or macOS binaries, building it needs SCons and a C++ toolchain, and running the Windows `makensis.exe` under Wine is a bigger hoop than one package. The steamos target never needs NSIS.
- **The toolkit**: if no toolkit is found, `setup` clones the pinned fork and commit into `external/xboxrecomp` (gitignored, so it never enters the `-dirty` hash) with git. The pin is the public fork (`apexJCL/xboxrecomp`, branch `blinx2/portability`) and a commit on it, because that is what a fresh host can reach; the private `posix-host/portability` shas differ (scrubbed history), so `doctor` compares HEAD against the pin only for a clone `setup` made (marked by `external/xboxrecomp/.blinx2-pin`) and otherwise just reports the HEAD it found. The pinned commit is bumped as part of every public toolkit push; `pins refresh` reads it from the fork's branch head.
- **macOS target only**: `doctor` checks the Command Line Tools and Homebrew `sdl2`, `openssl`, `libepoxy` and `sdl3`, and prints the `brew install` line. `setup` does not run brew.
- **Prerequisites that remain**: Python ≥ 3.9 with `venv` and `pip` (on Debian-likes `python3-venv`), git, the user's dump in `game_files/`, and on macOS the Command Line Tools (plus Homebrew for the macos target); `makensis` from the package manager for the windows target on Linux and macOS. Nothing else.

#### 1c. Host × target matrix

| Build host | windows | steamos | macos |
|---|---|---|---|
| macOS arm64 | yes (llvm-mingw macos-universal, Homebrew `makensis`) | yes | yes |
| Linux x86-64 / aarch64 | yes (llvm-mingw ubuntu, distro `makensis`) | yes | refused |
| Windows x86-64 / arm64 | yes (llvm-mingw ucrt zip, portable NSIS) | yes | refused |

windows and steamos share one artefact, the llvm-mingw Windows x86-64 exe, so any host that can run llvm-mingw builds both. `package macos` on another host stops before any work with: `package macos needs a macOS host (Apple clang, codesign, hdiutil); this host can package: windows, steamos`. The CMake build for `macos` likewise refuses. The pipeline stages run everywhere.

#### 1d. Host-only tools replaced

| Was | Now (in the CLI) |
|---|---|
| `shasum` / `sha256sum` | `hashlib`. The gen digest reproduces `bench.sh`'s exactly: one `<sha256>  <name>` line per file directly under `gen/` (no dotfiles), sorted bytewise by name, then sha256 of those lines. Bytes are hashed as they are; if the toolkit writes CRLF on a Windows host, that tree's digest and version differ from a Mac build of the same code, and the manifest's `host` field says why |
| `sysctl -n hw.ncpu` / `nproc` | `os.cpu_count()` |
| `uname` | `platform.system()`, `platform.machine()` |
| `brew --prefix ghidra` / `sdl3` | `shutil.which("brew")` then `brew --prefix` only on macOS, only for the ghidra stage and the macos target |
| `rsync`, `cp -c` | `shutil.copytree`/`copy2`; on macOS a `clonefile` copy (`cp -c`) of `game_files/` when available, since it costs no space on APFS |
| `curl` | `urllib.request` |
| `tar -xJf` / `unzip` | `tarfile`, `zipfile` |
| `sed`, `awk`, `date` | Python |

The macOS-only steps (`otool`, `install_name_tool`, `codesign`, `hdiutil`) stay external because they only run on macOS. The steamos target's `install_lib.py` uses Python only (no rsync, no `sha256sum`); SteamOS-like systems ship Python 3 (Valve's own `steamos-add-to-steam` uses it).

#### 1e. Windows build host pitfalls

- **Executable bits and symlinks.** NTFS keeps neither, so the steamos bundle is written as a tar by `tarfile` with explicit modes (`0755` for `install.sh`, `launch.sh`; `0644` otherwise), uid and gid 0 with empty owner names (no host account name leaks into the tar), the exe's mtime on every member, and no symlinks inside; `current` and every other symlink exist only on the target, made by `install_lib.py`. `README.txt` also says `bash install.sh` works if a copy lost the bit.
- **Line endings.** `.gitattributes`: `*.sh`, `blinx2`, `packaging/steamos/*`, `packaging/macos/BLiNX2.in`, `*.py`, `*.env*`, `*.toml*` and `*.in` are `text eol=lf`; `*.cmd` is `eol=crlf`. The `eol` attribute wins over a user's `core.autocrlf=true`, which is the point: a Windows clone still checks those files out with LF. Files the CLI writes into bundles are written with `newline="\n"`, and the packager fails if a staged shell script contains `\r`.
- **Long paths.** The build tree nests deep (`build-win/xboxrecomp/src/...`). `doctor` on Windows warns when the repo path is longer than 60 characters or `LongPathsEnabled` is off, and suggests a short checkout path and `git config core.longpaths true`.
- **Reserved names.** `scripts/host_reserved_names.py` already keeps generated symbols off the Windows CRT's names. File names are a separate risk: the packager refuses a staged path whose component is a Windows reserved device name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`9`, `LPT1`–`9`, with any extension) or ends in a dot or space, on every host, since the windows bundle must install there.
- **Spaces in paths.** The CLI passes argument lists to `subprocess`, never shell strings; the NSIS script quotes every path; the launchers quote throughout.
- **Defender and SmartScreen.** Real-time scanning of ~900 MB of generated C slows a Windows build; `docs/packaging.md` suggests (does not perform) a Defender exclusion for the checkout. The unsigned `setup.exe` triggers SmartScreen ("Windows protected your PC" → More info → Run anyway) when it carries the Mark of the Web, which a browser or some network-share copies add and a USB copy does not; the docs say so, and `Unblock-File` clears it.
- **macOS `DEVELOPER_DIR`.** On macOS the CLI sets `DEVELOPER_DIR=/Library/Developer/CommandLineTools` for every build step when it is unset and that directory exists (the selected Xcode's linker cannot read the newer SDK), and `doctor` reports which one is in force. The user no longer exports it.

### 2. Version string

```
<YYYYMMDD>.<HHMM>-c<cat7>-t<toolkit7>-g<gen8>[-dirty<sha8>]
```

Date first so that `ls versions/` sorts in build order; the commits say what was built; the gen digest pins the lifted code, which git does not track. `-dirty<sha8>` is sha256 over `git diff HEAD` plus untracked, non-ignored file contents in both trees, so two dirty builds of one commit differ and a rebuild of one dirty state repeats. The timestamp is the exe's mtime, so re-packaging an unchanged build repeats the version. `scripts/package_lib.py` computes it; the CLI imports it.

### 3. One payload, three wrappers

`blinx2.py package <windows|steamos|macos> [--no-build] [--allow-debug] [--allow-nonstock] [--archive] [--out DIR]`:

1. **Build** (`build windows` for windows and steamos, `build macos` for macos) unless `--no-build`. Incremental, so a no-op costs seconds and the bundle cannot be stale against the tree it names.
2. **Refuse** when `src/recomp/.gen-regenerating` exists, `gen/` is empty, the CMake cache is not `Release` (`--allow-debug`), `CAT_GEN_OPT` is non-empty or `XBOXRECOMP_ENHANCE` is OFF (`--allow-nonstock`; the manifest records the override). Also refuse when `game_files/default.xbe` is missing or its certificate title ID is not `0x4D530065` (`package_lib.py xbe-title`).
3. **Stage the payload** in `dist/.stage-<target>/`:
   - the program: `cat_recomp.exe` and `cat_recomp.pdb`, or `cat_recomp` (macOS);
   - `game_files/`: every file under the repo's `game_files/` except `default_analysis.json`, `UDATA/` and `TDATA/` (pipeline and save artefacts, not the dump);
   - `enhance.toml.default` (every toolkit and game key at its stock value, in the TOML subset the enhancements layer reads) and `launch.env.default` (per target family, see 5);
   - `manifest.json`, `SHA256SUMS` (coreutils format over every payload file), `README.txt`, `LICENSE`, `NOTICE`.
4. **Wrap** per target (4): the windows folder, the steamos `.tar`, or the `.dmg`. `--archive` adds a `.zip` of the windows folder for transport; nothing in it compresses, so it is stored, not deflated.
5. **Print the notice** (the first paragraph of `README.txt`):

> This bundle contains your own copy of BLiNX 2 and code generated from it. It is for your own machines only. The game is not yours to redistribute: never share, upload or publish this bundle.

**Private artefacts.** `dist/` is gitignored, as are `*.dmg`, `*.exe`, `*.pdb`, `*.tar` and `*.nsi` (the tracked template is `installer.nsi.in`). `export-public.sh` gains a check that fails the export when the tree tracks any path under `dist/` or any file with those extensions, as a second line of defence behind `.gitignore`. The bundles never leave the user's machines.

### 4. The three bundle formats

**windows:** `dist/BLiNX2-<version>-windows/{BLiNX2-<version>-setup.exe, game_files/}`.

- **NSIS**, compiled by `makensis` on the build host (1b, 1c) from `packaging/windows/installer.nsi.in`. Inno Setup needs Wine to compile off Windows; NSIS does not.
- **The 2 GB limit** rules out embedding the dump. The installer embeds the program files (about 130 MB) and copies `game_files/` from its own directory (`$EXEDIR`) with `CopyFiles`, which is built in and has no size limit. The installer refuses with a message when `$EXEDIR\game_files\default.xbe` is missing. The user moves the folder as a whole and runs the exe inside it. Rejected: an NSIS sidecar `.7z` (needs the Nsis7z plugin, not in the Homebrew formula) and a 7-Zip SFX (its Windows SFX modules are not shipped on macOS).
- **Per-user install, no elevation:** `RequestExecutionLevel user`, `InstallDir $LOCALAPPDATA\Programs\BLiNX2`. The user can change it in the wizard. `SetCompressor zlib` (the embedded exe compresses a little; speed matters more than size).
- **What it installs** under `$INSTDIR`: `cat_recomp.exe`, `cat_recomp.pdb`, `BLiNX2.exe` (the launcher, 4b), `game_files\`, `launch.env.default`, `enhance.toml.default`, `manifest.json`, `SHA256SUMS`, `README.txt`, `LICENSE`, `NOTICE`, `uninstall.exe`. A Start Menu shortcut (and an optional desktop one) to `BLiNX2.exe`, and an Add/Remove Programs entry under `HKCU`. Installing on top of an older version overwrites the program files and `game_files\`, the same way every version.
- **4b. The launcher `BLiNX2.exe`** (`packaging/windows/launcher.c`, about 60 lines, `WinMain`, compiled by the CLI with the same llvm-mingw, `-municode -mwindows`): it reads `<exe dir>\launch.env.default` then `%LOCALAPPDATA%\BLiNX2\config\launch.env` (`KEY=value` lines, later wins, `#` comments), sets each with `SetEnvironmentVariableW`, then sets `RECOMP_GAME_FILES=<exe dir>\game_files`, `RECOMP_HDD_DIR=%LOCALAPPDATA%\BLiNX2\hdd`, `RECOMP_ENHANCE_CONFIG=%LOCALAPPDATA%\BLiNX2\config\enhance.toml` and `RECOMP_STDIO_LOG=%LOCALAPPDATA%\BLiNX2\logs\game-<stamp>.log`, creates those directories, copies `enhance.toml.default` to `config\enhance.toml` only when absent, keeps the newest 10 logs, and `CreateProcessW`s `cat_recomp.exe` with the working directory set to `logs\`. Why a C launcher and not a `.cmd`: a shortcut cannot set environment variables, a `.cmd` flashes a console, and a registry-wide `HKCU\Environment` entry would leak into every other recomp build on that machine. The launcher is packaging code, not the game: it produces the environment that `recomp_env` reads, so the no-raw-`getenv` rule does not apply to it.
- **The uninstaller** deletes the files it installed by explicit name (the list is generated into the `.nsi` from the manifest), `RMDir /r` only `game_files\`, then plain `RMDir $INSTDIR`. It never references `%LOCALAPPDATA%\BLiNX2\` and prints its path in the final page: the saves, config and logs stay.
- **Test host:** Proton on the Linux PC, in a scratch prefix, with `/S` (silent install) and `/S` on `uninstall.exe`. NSIS supports both natively.

**steamos:** `dist/BLiNX2-<version>-steamos.tar`, one uncompressed tar of `BLiNX2-<version>-steamos/{payload..., install.sh, install_lib.py, launch.sh, running_game.py}` written by `tarfile` with explicit modes and LF scripts (1e), so it is the same file from any build host. The user unpacks it on the gaming PC (Dolphin "Extract here" or `tar -xf`), which restores the modes. A plain folder is not offered: on a Windows build host it would lose the executable bits.

- **Installs the payload directly**, not the Windows installer under Proton. Why: no Wine runs during an install (a first Proton start takes a minute and needs a display), the program stays outside the Wine prefix (Steam and Proton recreate prefixes), a versioned tree gives update and rollback as a symlink switch, and it is the same staged payload as the Windows bundle, so there is one staging path.
- `install.sh` is a thin bash entry; `install_lib.py` (standard library, Python ≥ 3.9) does the work. Both are tracked under `packaging/steamos/` and copied into every steamos bundle, so the bundle needs nothing from the repo. Commands: `install` (default; also updates), `rollback [version]`, `status`, `list`, `uninstall`, with `--root DIR` (default `~/Games/BLiNX2`), `--keep N` (default 3), `--steam` and `--import-saves DIR`. Section 6 has the layout.
- **The Steam entry** (`--steam`): `steamos-add-to-steam <root>/BLiNX2` sends `steam://addnonsteamgame/<path>` to the running client, which writes `shortcuts.vdf` itself. It needs Desktop Mode: when `DISPLAY` and `WAYLAND_DISPLAY` are both unset, or Steam is not running, `install.sh` says "run this from Desktop Mode with Steam open" and continues the install without the entry. Where the helper is missing, it prints the manual steps (Steam → Games → Add a Non-Steam Game → Browse → `<root>/BLiNX2`). The registered path is the stable `<root>/BLiNX2` file, never a path under `versions/`, because `steamos-add-to-steam` resolves its argument with `realpath` and prune would later delete a versioned path. The shortcut runs natively: the docs say to leave "Force the use of a specific Steam Play compatibility tool" off, since the launcher starts Proton itself. Rejected: editing `shortcuts.vdf` (binary, Steam must be closed, Steam rewrites it, and a bug damages the user's whole shortcut list).

**macos:** `dist/BLiNX2-<version>.dmg` holding `BLiNX2.app` and an `Applications` symlink, made with `hdiutil create -srcfolder <staging> -format UDZO -volname "BLiNX2 <version>"`.

- `BLiNX2.app/Contents/{Info.plist, MacOS/BLiNX2 (launcher script), MacOS/cat_recomp, Frameworks/*.dylib, Resources/{game_files/, enhance.toml.default, launch.env.default, manifest.json, SHA256SUMS, README.txt, LICENSE, NOTICE}}`. The game files sit inside the app, so dragging the app is the whole install and replacing the app is the whole update. `cat_recomp` stays the unchanged console build (the `host-build` spec); the app wraps it.
- **Dylibs bundled.** The CLI walks `otool -L` from `cat_recomp` transitively over every path outside `/usr/lib` and `/System` (today `libcrypto.4`, `libSDL2-2.0.0`, `libepoxy.0`) plus `libSDL3.dylib`, which sdl2-compat `dlopen`s from `@loader_path` (a companion the walk adds by name), copies each into `Contents/Frameworks/`, sets its `-id` to `@rpath/<name>`, rewrites every reference with `install_name_tool -change` to `@rpath/<name>`, and adds `-add_rpath @executable_path/../Frameworks` to `cat_recomp`. The launcher script execs `cat_recomp` from the same directory, so `@executable_path` is `Contents/MacOS`. Done in the script with `otool` and `install_name_tool` only, no `dylibbundler` dependency. The manifest records the bundled libraries and their origin versions.
- **Signing:** `install_name_tool` invalidates the arm64 ad-hoc signatures, so after relinking the CLI signs each dylib, then `cat_recomp`, then the whole app (`codesign --force --sign - --deep`), and verifies with `codesign --verify --deep --strict`. No notarization: the app is for the user's own Macs. `README.txt` gives the `xattr -dr com.apple.quarantine` line for an app copied from another Mac, since Gatekeeper may still warn about an unsigned developer; a right-click Open works too.
- **The launcher script** (`packaging/macos/BLiNX2.in`) sets `RECOMP_GAME_FILES=<app>/Contents/Resources/game_files`, `RECOMP_HDD_DIR=~/Library/Application Support/BLiNX2/hdd`, `RECOMP_ENHANCE_CONFIG=.../config/enhance.toml`, `RECOMP_STDIO_LOG=.../logs/game-<stamp>.log`, sources `launch.env.default` then the user's `config/launch.env`, copies `enhance.toml.default` to `config/enhance.toml` when absent, creates the directories, keeps the newest 10 logs, `cd`s to `logs/`, and `exec`s `cat_recomp`. `RECOMP_PB_BACKEND=metal` comes from `launch.env.default`. Paths with spaces are quoted throughout.

### 5. Launchers and user settings

Every target has one launcher that derives every path, sources `launch.env.default` from the program files and then the user's `config/launch.env` (user wins, `KEY=value` lines only), and starts the game with the working directory in `logs/`. Settings are environment variables, not flags: `recomp_env` is the project's single settings path, and a launcher already owns the environment. There is no `enhance.toml` key for paths: the file's own location is one of them, and the layer can be built OFF.

`launch.env.default`, windows and steamos family:

```
RECOMP_PB_BACKEND=d3d11
# plus the keys bench.sh's cmd_run sets for a windowed Proton run (task 4.1)
PROTONPATH=GE-Proton          # steamos only, ignored on Windows
LOG_KEEP=10
```

macOS: `RECOMP_PB_BACKEND=metal` and `LOG_KEEP=10`.

The steamos `launch.sh` (`packaging/steamos/launch.sh.in`) additionally exports `WINEPREFIX=<root>/prefix`, `GAMEID=umu-default`, `PROTONPATH`, passes game paths in Wine's `Z:` form (`RECOMP_GAME_FILES=Z:<root>/game_files`, as `bench.sh` does for `RECOMP_SAVE_DIR=@run`), refuses with a `notify-send` (when a session exists) plus a non-zero exit when `game_files/default.xbe` or `umu-run` is missing, and `exec`s `umu-run "<root>/current/cat_recomp.exe"`. It takes no lock (section 8). The stable `<root>/BLiNX2` file is `exec "$(dirname "$0")/current/launch.sh" "$@"`.

**Config files are copied when absent, never merged.** Each launcher copies `enhance.toml.default` to `config/enhance.toml` the first time, and on every launch refreshes `config/enhance.toml.default` from the program files when it differs. The launcher does this, not the installer: no installer writes under `config/` (section 6), and the refreshed default still lands beside the user's file after the first launch of a new version. A key missing from the user's file reads as stock in `enhance_cfg`, so an update that adds a knob changes nothing for the user, and the user finds the new knob in the `.default`. A merger would be a hundred lines plus tests for discoverability alone, and it would have to touch the user's file, which this change avoids entirely. `launch.env` is user-authored from the start (the launcher reads the `.default` directly), so there is nothing to merge there.

### 6. Where things live, and what owns them

| Target | Program files (replaced by every install) | User data (never written by install, update, rollback or uninstall) |
|---|---|---|
| windows | `%LOCALAPPDATA%\Programs\BLiNX2\` (exe, pdb, launcher, `game_files\`, defaults, docs, uninstaller) | `%LOCALAPPDATA%\BLiNX2\{hdd,config,logs}\` |
| steamos | `<root>/versions/<v>/`, `<root>/current`, `<root>/state/`, `<root>/game_files/`, `<root>/BLiNX2`, `<root>/prefix/` | `<root>/{hdd,config,logs}/` |
| macos | `/Applications/BLiNX2.app` (game files inside) | `~/Library/Application Support/BLiNX2/{hdd,config,logs}/` |

- `hdd/` is `RECOMP_HDD_DIR`: partition images, `TitleData/`, `UserData/`, `Cache/`, `SystemData/` and the UDATA/TDATA save games. It is created by the game on first launch, not by an installer. No installer, launcher or uninstaller contains a code path that writes, renames or deletes under `hdd/`; the ownership test in `test_steamos_install.py` snapshots it around every command, and the installer smoke test on Proton plants a save before an install and an uninstall.
- **Outside every Wine prefix.** Under Proton the toolkit's default save root would be `prefix/drive_c/users/steamuser/AppData/Local/xboxrecomp`, and Steam or a Proton update can recreate a prefix. `RECOMP_HDD_DIR` points at `<root>/hdd` on the host filesystem, so the prefix holds nothing of value and `uninstall` may delete it. Steam's `compatdata` is never used: the shortcut runs `launch.sh` natively and the launcher starts Proton with its own `WINEPREFIX`.
- **steamos layout:**

```
~/Games/BLiNX2/
  BLiNX2                  # stable launcher, registered in Steam
  current -> versions/<v>
  versions/<v>/           # the payload minus game_files; hard-linked against the previous version
  game_files/             # bundle-owned: synced by checksum from the bundle on every install
  state/{history,layout}  # history: "<utc> install|rollback <old> -> <new>"
  prefix/                 # Wine prefix, created by the first launch; disposable
  hdd/  config/  logs/    # user data
```

`game_files/` is one copy at the root, not per version: it is 2.4 GB and the dump does not change. A sync by checksum (Python: copy a file when it is missing or its sha256 differs from the bundle's `SHA256SUMS`; remove files the bundle does not have) makes an install idempotent and corrects a damaged copy; removal is scoped to `game_files/` only.

- **`install.sh install`** on the target, in order: preflight (Linux x86-64, `umu-run` on `PATH`, free space ≥ 2 × payload, `state/layout` compatible, the root is not inside a dev tree, section 8); verify the bundle against `SHA256SUMS` (hashlib); create the directories that are missing; copy the program files into `versions/<v>.partial/`, hard-linking each file that is identical to the current version's, verify, then rename to `versions/<v>/`; sync `game_files/`;  create `current.new -> versions/<v>` and `os.replace` it over `current` (one `rename(2)`, atomic, which is why the switch is Python: GNU `mv -T` and BSD `mv -h` disagree); append to `state/history`; prune to `--keep` versions plus current plus the previous one, removing only directories whose `manifest.json` names this product and stale `.partial` dirs; `--steam`; report `old -> new`, kept and removed versions, the save path, and the notice. A failed verify or transfer removes the `.partial` directory and leaves `current` alone. A version already installed with identical `SHA256SUMS` is not transferred again, only switched to.
- **`rollback [version]`** switches `current` to the given version or the previous history entry and records it. **`status`** prints the current version and its commits, the kept versions, the data directories with `du`, whether `game_files/default.xbe` and `prefix/` exist, and whether a game process is running (section 8). **`list`** prints every version with build date and commits, marking current and previous. **`uninstall`** removes `versions/`, `current`, `state/`, `game_files/`, `prefix/` and `BLiNX2`, keeps `hdd/`, `config/` and `logs/`, prints their path, and reminds the user to remove the Steam shortcut in Steam. There is no flag that deletes saves.
- **`--import-saves DIR`** copies an existing save root's `UserData/`, `TitleData/` and UDATA/TDATA into `hdd/` once, only when `hdd/` is absent or empty. It is the only command that writes there, it is opt-in, and it never overwrites.

### 7. `RECOMP_GAME_FILES` and `RECOMP_HDD_DIR` in `main.c`

- Two CONFIG rows in `src/env/recomp_env_game.h` (game keys; no toolkit change) and two rows in `docs/env.md`.
- `host_main` resolves `game_dir = recomp_env(RENV_GAME_FILES)`, falling back to `"game_files"`, loads `<game_dir>/default.xbe`, and passes `game_dir` and `recomp_env(RENV_HDD_DIR)` (NULL when unset) to `xbox_path_init`.
- The missing-XBE `host_report_fatal` names the resolved path and its source: "from RECOMP_GAME_FILES" or "set RECOMP_GAME_FILES or run from the project root".
- One `[BOOT] game files: <dir>; hdd: <dir|toolkit default>` line follows the `xbox_path_init` line, printed only when either key is set. With both unset the log is line-for-line identical, which `golden.py` and the bench log checks rely on.
- `RECOMP_SAVE_DIR` keeps overriding UDATA/TDATA inside whichever save root is in force, so `@run` and `RECOMP_SAVE_SEED` keep working. The toolkit strips trailing separators; paths with spaces work, including the `Z:` form.
- No render or audio path reads these keys, so the backends need nothing to agree.

### 8. The installed game and the bench

- **The installed game takes no lock.** It is a final build for play. The draft's `RUN_LOCK` is dropped: a player should never see "a bench run is in progress".
- **The bench checks instead.** `scripts/running_game.py` (standard library; scans `/proc/*/cmdline` on Linux and `ps -axo pid=,command=` on macOS) lists processes whose command line names `cat_recomp.exe` or a `cat_recomp` executable, excluding the caller's own process tree. `bench.sh` calls it after taking the run lock and before starting a game, in `run_game`, which `run` and `golden` share (there is no separate `bench` command). Because every bench game run holds the lock exclusively, any match at that point is a foreign game: the installed copy, or a run started by hand. No path matching against the install root is needed. `golden.py` runs the same check on the Mac before its runs.
- **Warn, and kill only on request.** A match prints `bench: WARN a game is running (pid N: <cmdline>); close it or results will be noisy; pass --kill-game to end it` and continues, so a single forgotten window does not fail a long golden session. With `--kill-game` (or `BENCH_KILL_GAME=1` in `bench.env`), `bench.sh` sends SIGTERM to the matches, waits five seconds, sends SIGKILL to survivors, re-checks, and prints what it ended. Under Wine the matched pid is the Wine process hosting `cat_recomp.exe`, and ending it ends the game. `golden.py` only warns; it has no kill flag.
- **The bench log records it.** The warning goes into the run's `bench-logs/<stamp>/` as well, so a noisy result can be explained later.
- **Paths.** `install.sh` refuses a root that equals or lies under `BENCH_DIR` (default `~/xbox-recomp`, read from `~/xbox-recomp/cat/scripts/bench.env` when present) or that contains `.git`, `cat/` or `xboxrecomp/`, comparing realpaths. It never reads or writes the bench's prefix, toolchain or game files. It never takes or waits for the run lock: installing during a bench run is safe, since the bench never reads those files.
- **Testing the installed game on the Linux PC** happens from an agent session, which takes the lock as every agent run does (`flock -w 3600 ~/.recomp-run.lock`), so the test never collides with a bench run. The lock is the agent's, not the game's.

## Risks / Trade-offs

- **umu-run inside Steam Game Mode:** pressure-vessel nested under Steam's environment is the Lutris/Heroic pattern and normally works; task 7.6 verifies it. If it fails, `launch.sh` unsets `LD_PRELOAD` and the Steam runtime variables before `umu-run`.
- **First launch is slow** on steamos: the first launch creates the prefix (20–60 s). `install.sh` does not pre-create it, since that would start Proton from an installer. `README.txt` says so.
- **Script `CFBundleExecutable`:** an ad-hoc signed app whose main executable is a script works today. If a future macOS rejects it, the fallback is a 30-line C launcher compiled by the CLI, recorded as a follow-up if needed.
- **DMG size:** 2.4 GB, and `hdiutil` compresses for a few minutes to no effect; `UDZO` is kept because an uncompressed `UDRO` image is not smaller and `ULFO` is not readable by older Macs.
- **Windows is untested natively**, as a target and as a build host. The installer, launcher and uninstaller are exercised under Proton only. The CLI's Windows host branch (llvm-mingw zip selection, `.cmd` wrapper, NSIS zip, `Scripts\` venv layout, long-path and reserved-name checks) is covered by unit tests with fake toolchains and, if it proves practical, one smoke run of `blinx2.py doctor` and `setup` under Proton with the Windows embeddable Python. Everything else is marked "untested on a Windows host" in the docs. Also unit-test only: Linux aarch64 and Windows arm64 (asset selection), and whether Dolphin's "Extract here" (Ark) restores the tar's modes, which 9.4 checks once on the gaming PC; `tar -xf` is the documented fallback.
- **No-Ghidra builds differ from dev builds.** `names` only rewrites function names in `disasm/functions.json` after the functions are found, so a no-Ghidra tree lifts the same functions under `sub_<addr>` names: the gen digest and the version differ, trace and thread-dump output names functions differently, and behaviour does not. Nothing golden-related breaks: `golden.json` holds frame hashes and no version, and `bench.sh integrate` syncs `gen/` to the bench host before comparing digests, so a no-Ghidra tree integrates like any other. What is lost is only that two versions cannot be compared by their `g<gen8>` across the Ghidra/no-Ghidra line; the manifest records `ghidra_names: true|false` so the reason is visible. Task 2.7 boots a no-Ghidra build on the Mac to show it.
- **Pins age.** A pinned digest that no longer matches (a re-uploaded asset) stops `setup`; `pins refresh` is the maintainer fix. PyPI wheels for a new Python version may lag the pin; `setup` names the missing wheel and the Python version.
- **The sdl2-compat chain:** bundling `libSDL2` means bundling `libSDL3` too. The transitive walk covers it. Homebrew cannot be hidden from a test shell, so the smoke test checks that `otool -L` of every Mach-O in the app shows no `/opt/homebrew` path and that the app launches; the real proof is a launch on a Mac without Homebrew, which the user can do when one is at hand.
- **Disk on steamos:** 120 MB per kept version (hard-linked where unchanged) plus one 2.4 GB `game_files/` and sparse partition images. `status` prints real usage.
- **Dirty builds** install fine and are marked: `install.sh` prints a warning line for a `-dirty` version.

## Migration Plan

Nothing migrates automatically. The bench and goldens keep their layout with the keys unset; a first install creates an empty data root and the game creates `hdd/` on first launch; `--import-saves` is the opt-in path for the bench prefix's saves. To back out: `install.sh uninstall` (saves kept), the Windows uninstaller (saves kept), or drag the app to the Trash (saves kept in Application Support).

## Decided

1. **Windows bundle shape** (user, 2026-10-05): a folder, `BLiNX2-<version>-setup.exe` with `game_files/` beside it, built with NSIS through Homebrew `makensis`. NSIS caps an installer at 2 GB and the dump is 2.4 GB of incompressible video and audio, so one exe is not possible without Inno Setup, which needs Wine on the Mac.

2. **Build hosts** (user, 2026-10-05): Windows, Linux and macOS can all build; one stdlib Python CLI (`blinx2.py`) is the entry point on every host; no ssh deploy, bundles are copied by hand; `bench.sh` and golden-over-ssh are not ported now.

3. **`makensis` from the package manager on Linux and macOS** (Fable, 2026-10-05), and only for the windows target: NSIS ships no Linux or macOS binary, so the alternatives are building it (SCons plus a C++ toolchain) or Wine, both bigger hoops than one package that `doctor` names exactly.

4. **The steamos bundle is a tar, with no plain-folder option** (Fable, 2026-10-05): one shape means one code path and one set of tests, the tar is the same file from every host, and a folder option would be correct only on two of the three hosts.

## Open Questions

None that block implementation.
