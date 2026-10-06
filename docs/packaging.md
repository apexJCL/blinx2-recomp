# Building and installing BLiNX 2 on your own machines

`blinx2` builds the game from your own disc dump and packages it as a
**private bundle** for one of three targets:

| Target | Bundle | Installs to | Saves and settings |
|---|---|---|---|
| `windows` | `dist/BLiNX2-<v>-windows/` (a setup program with `game_files\` beside it) | `%LOCALAPPDATA%\Programs\BLiNX2` | `%LOCALAPPDATA%\BLiNX2\{hdd,config,logs}` |
| `steamos` | `dist/BLiNX2-<v>-steamos.tar` | `~/Games/BLiNX2` (Linux gaming PC, runs under Proton) | `~/Games/BLiNX2/{hdd,config,logs}` |
| `macos` | `dist/BLiNX2-<v>.dmg` | `/Applications/BLiNX2.app` | `~/Library/Application Support/BLiNX2/{hdd,config,logs}` |

**A bundle is private.** It contains your own copy of BLiNX 2 and code
generated from it. It is for your own machines only: never share, upload or
publish it. `dist/` is gitignored, and `scripts/export-public.sh` refuses a
commit that tracks a bundle.

Saves (`hdd/`), settings (`config/`) and logs (`logs/`) live outside the
program files. No install, update, rollback or uninstall writes them.

## 1. On the build machine

The build machine can be macOS, Linux or Windows. Each can package these
targets:

| Build host | windows | steamos | macos |
|---|---|---|---|
| macOS (Apple silicon) | yes (`brew install makensis`) | yes | yes |
| Linux x86-64 or aarch64 | yes (distribution `makensis`) | yes | no |
| Windows x86-64 or arm64 | yes (`setup` fetches NSIS) | yes | no |

### Prerequisites

Everything else (CMake, Ninja, the Python packages, the llvm-mingw
cross-compiler, the toolkit) is fetched by `setup` into this checkout, each
download checked against a pinned sha256.

- **All hosts:** Python 3.9 or newer, git, about 15 GB free, and your dump in
  `game_files/` (`game_files/default.xbe` plus the game's files).
- **macOS:** the Command Line Tools (`xcode-select --install`). For the macos
  target, Homebrew's `sdl2`, `sdl3`, `openssl` and `libepoxy`. For the windows
  target, `brew install makensis`.
- **Linux:** for the windows target, `makensis` from the distribution
  (`sudo apt install nsis`, `sudo dnf install mingw32-nsis`,
  `sudo pacman -S nsis`). On an immutable system (SteamOS, Fedora Atomic and
  similar), run the build in a toolbox or distrobox; `blinx2 doctor` prints
  the commands.
- **Windows:** Python from python.org (the `py` launcher) and Git for
  Windows. Use a short checkout path such as `C:\b2`, and run
  `git config --global core.longpaths true`; `doctor` warns when the path is
  long or `LongPathsEnabled` is off. Windows Defender scans every generated
  file, which slows the build; an exclusion for the checkout folder helps
  (Windows Security > Virus & threat protection > Exclusions). The CLI does
  not add one.

### Commands

On macOS and Linux run `./blinx2`; on Windows run `blinx2` (the
`blinx2.cmd` wrapper) or `py -3 blinx2.py`.

```sh
./blinx2                    # package for this computer: macos on a Mac,
                            # steamos on Linux, windows on Windows
./blinx2 package windows    # or steamos, or macos (macos needs a Mac)
./blinx2 doctor             # what this host has and which targets it can package
```

`package` (and plain `./blinx2`) first prints its plan, for example
`plan: setup (no llvm-mingw), generate (no key), build (build-pkg-macos),
package (macos)`, then runs only what is needed:

- **setup** when the toolchain or the toolkit is missing (`--no-setup` if
  you manage your own). Things setup cannot install (the Xcode Command Line
  Tools, Homebrew libraries, a distribution's `makensis`) stop the run with
  the command that installs them.
- **generate** (`analyze`, then `recomp`) when `src/recomp/gen/` is missing
  or out of date. `src/recomp/gen.key.json` records what gen/ came from: the
  XBE, the toolkit's tools, the seed files and the exact stage commands.
  The plan names whatever changed.
- **build** in `build-pkg-macos/` or `build-pkg-win/` (the steamos bundle
  carries the Windows exe), configured with the stock options on every run.
  Your own `build/` and `build-win/` are never touched, at the cost of a
  separate build if you also build by hand. `--reconfigure` starts the
  packaging tree afresh.

The app, the installer, the exe and the Steam shortcut carry the game's own
icon: its title image from `default.xbe`, written to
`build-pkg-*/icon/` (and into the bundle only; it is game data, never
committed). Without one, a plain generic icon is used and `package` says
why.

While it runs, `package` shows the plan step, a bar where the tools report
progress (downloads, Ninja, recomp, makensis, hdiutil), the elapsed time and,
from the second run on, an estimate of what is left. Every tool's full
output goes to `build-logs/<time>-<step>.log` (the newest 20 runs are kept);
when a step fails, its last 40 lines and the log's path are printed.
`--plain` prints one line per step instead (the default when the output is
not a terminal, or with `CI` set), and `--verbose` shows the tools' output
as they run.

The separate steps are developer commands (`./blinx2 --help` lists them
apart):

```sh
./blinx2 setup              # .venv, llvm-mingw, toolkit; ends with doctor
./blinx2 analyze            # parse the XBE, find functions, classify, recover ABIs
./blinx2 recomp             # lift to C: src/recomp/gen/
./blinx2 build [windows|macos]   # build-win/ or build/
```

Every stage invalidates `gen.key.json` and `recomp` writes it again, so a
stage run by hand with extra arguments always makes the next `package`
regenerate.

`setup` clones the toolkit at the commit pinned in
`config/setup-pins.json`. The pin must be at least as new as this tree
needs; if `build` fails on a missing toolkit header, point
`XBOXRECOMP_DIR` at a newer toolkit checkout (`setup` then leaves it
alone).

`scripts/pipeline.sh build` (for developers) runs `blinx2 build macos` on
macOS; on Linux it runs `blinx2 build`, whose default there is the Windows
cross-build into `build-win/`, since Linux has no native target of its own.

`package` always builds (incrementally), so a bundle always matches the tree
it names. `blinx2 <command> --help` lists the options. The optional
`ghidra` stage only improves function names; nothing needs it.

The version, for example `20261005.1412-c1a2b3c4-t5d6e7f8-g9a0b1c2d`, is the
build time, the game and toolkit commits and a digest of the generated code.
A build from uncommitted changes ends in `-dirty<hash>` and `package` warns.

`package` refuses a Debug build, a non-stock build (`CAT_GEN_OPT`, or
`XBOXRECOMP_ENHANCE=OFF`) and a dump that is not BLiNX 2. Its own build tree
is configured stock, so this only happens when an option is forced from
outside; the message prints the fix (`--reconfigure`). `--allow-debug` and
`--allow-nonstock` package anyway, and the manifest records it.

## 2. Moving the bundle

Copy it to the target machine any way you like: a USB stick, a network
share, `scp`. Keep it on your own machines.

## 3. Windows

Copy the whole `BLiNX2-<v>-windows` folder (the setup program reads
`game_files\` from the folder it runs in; `--archive` also writes a `.zip`
of it). Run `BLiNX2-<v>-setup.exe`. It installs for your user only, without
administrator rights, and adds a Start Menu entry (and optionally a desktop
one).

- **Update:** run a newer setup; it installs on top and keeps your saves.
- **Uninstall:** Settings > Apps > BLiNX 2. Your saves stay in
  `%LOCALAPPDATA%\BLiNX2`.
- **SmartScreen** may warn, since the programs are built on your machine and
  unsigned: More info > Run anyway. A folder that arrives as a downloaded
  `.zip` carries the Mark of the Web: right-click the `.zip` > Properties >
  Unblock before extracting, or run `Unblock-File` on it in PowerShell.
- `%LOCALAPPDATA%\BLiNX2\config\launch.env` takes your own settings as
  `KEY=value` lines (for example `RECOMP_PB_BACKEND=cpu`); `docs/env.md`
  lists them.

**Untested natively on Windows.** The installer, launcher and uninstaller
are tested under Proton on Linux only. Building on a Windows host is
untested too.

## 4. Linux gaming PC (steamos)

The game runs under Proton through `umu-run`, which SteamOS-like gaming
distributions ship. From Desktop Mode:

```sh
tar -xf BLiNX2-<v>-steamos.tar     # or Dolphin: right-click > Extract > here
cd BLiNX2-<v>-steamos
./install.sh --steam               # first time: install and add to Steam
```

If `./install.sh` says "permission denied" (an unpacker that dropped the
file modes), run `bash install.sh` with the same options.

| Command | Does |
|---|---|
| `./install.sh --steam` | first install; adds "BLiNX2" to Steam (Steam must be open) |
| `./install.sh` | every later version: installs beside the old ones and switches to it; keeps the newest 3 |
| `./install.sh rollback [version]` | back to the previous (or a named) version |
| `./install.sh status` | the installed version, the data folders and their sizes, a running game |
| `./install.sh list` | the installed versions |
| `./install.sh uninstall` | removes the program, keeps `hdd/`, `config/` and `logs/` |

Options: `--root DIR` (default `~/Games/BLiNX2`), `--keep N`,
`--import-saves DIR` (copies an older save root into an empty `hdd/`).

**Steam.** The installer adds the stable launcher `~/Games/BLiNX2/BLiNX2`
as a non-Steam game, so the entry keeps working across updates. Without
Steam open, add it by hand: Steam > Games > Add a Non-Steam Game to My
Library > Browse > `~/Games/BLiNX2/BLiNX2`. Leave "Force the use of a
specific Steam Play compatibility tool" **off** for it: the launcher starts
Proton itself. Then play from Game Mode.

The first launch creates the Wine prefix (`~/Games/BLiNX2/prefix`) and shows
nothing for 20 to 60 seconds. The prefix holds nothing of yours and is
recreated if deleted.

## 5. macOS

Open the `.dmg` and drag `BLiNX2.app` to Applications (replace the old one
to update). The game files are inside the app. To uninstall, drag it to the
Trash; your saves stay in `~/Library/Application Support/BLiNX2`.

The app is signed ad hoc on the Mac that built it, not notarized. Copied to
another Mac, Gatekeeper may refuse it: right-click > Open once, or
`xattr -dr com.apple.quarantine /Applications/BLiNX2.app`.

## 6. Settings

`config/enhance.toml` is copied from `enhance.toml.default` on the first
launch and then left alone. Every launch refreshes
`config/enhance.toml.default` from the installed version, so new options
show up there: compare the two files. `config/launch.env` holds your own
environment settings, `KEY=value` per line, read after the bundle's
`launch.env.default`. `logs/` keeps one log per launch, the newest
`LOG_KEEP` (10).

Controllers work as player 1 on every target. On Windows and the Linux
gaming PC the keyboard does too (`RECOMP_KEYBOARD=1` in
`launch.env.default`; the keys are in the bundle's README.txt). On macOS the
app turns host pads on (`RECOMP_HOST_PAD=1`) and the keyboard does not drive
the game yet.

`BLINX2_DATA_DIR` moves the user-data folder for the macOS app and the
Windows launcher. It exists for tests, which must never touch your real
saves or `launch.env`: set it to a scratch folder whenever you start a
packaged game from a script (`open --env BLINX2_DATA_DIR=... BLiNX2.app`).

## 7. Troubleshooting

- **`blinx2 doctor`** names whatever is missing and how to install it.
- **"checksum mismatch" during setup:** the download is deleted and nothing
  is unpacked. Retry; if it persists, the pinned file changed upstream.
- **llvm-mingw "quarantined" on macOS:** it came from a browser download;
  `doctor` prints the `xattr` line that clears it.
- **"gen/ is being regenerated":** a `recomp` is running or failed; run
  `blinx2 recomp` again.
- **The game says the files are missing:** the installed `game_files/` is
  incomplete. Install again (steamos and windows) or replace the app (macos).
  A dev build run from the checkout finds `game_files/` in the current
  directory, or wherever `RECOMP_GAME_FILES` points.
- **"the dump looks incomplete":** the XBE names songs, voice lines or
  movies that `game_files/` lacks (doctor and package list them). The game
  runs, silent where they would play. Extract the whole disc again into
  `game_files/`. The check is a heuristic and never blocks packaging.
- **steamos: nothing happens at launch:** the first launch takes up to a
  minute. `~/Games/BLiNX2/logs/` has the game's log and `umu.log`.
- **A bench run warns about a game outside the bench:** the installed game
  is still open on the same PC. Close it, or pass `--kill-game`.

## 8. Maintainers

`blinx2 pins refresh` rewrites `config/setup-pins.json` and the two
`config/requirements-*.txt` files from the GitHub and PyPI APIs (the
llvm-mingw tag comes from `config/toolchain.env`). Review the diff before
committing: setup trusts these hashes.
