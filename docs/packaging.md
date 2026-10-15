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

## The wizard

The short route. From the first release that carries it, each release has
a small program, the **build wizard**, for Windows, macOS and Linux (a
Steam Deck in Desktop Mode included), on the
[releases page](https://github.com/apexJCL/blinx2-recomp/releases):

| Your computer | Download | Open it |
|---|---|---|
| Windows x86-64 | `blinx2-wizard-<tag>-windows-x64.zip` | Unzip, run `blinx2-wizard.exe`. SmartScreen warns (it is not signed): More info > Run anyway. |
| Mac | `blinx2-wizard-<tag>-macos.zip` | Unzip (double-click), open `blinx2-wizard.app`. macOS refuses an app that is not notarized: System Settings > Privacy & Security > Open Anyway, or `xattr -dr com.apple.quarantine blinx2-wizard.app`. |
| Linux, Steam Deck | `blinx2-wizard-<tag>-linux-x64.tar.gz` | `tar -xzf` it and run `./blinx2-wizard`. |

`SHA256SUMS` on the same page has each download's sha256.

The wizard asks for your disc image or dump folder, the target and a few
options (render scale, fullscreen, frame pacing, keyboard and mouse, the
HUD texture pack), then does what the command route below does: it fetches
uv (and git on Windows) by sha256, clones this project at the release's
tag, and runs `./blinx2 package <target> --dump <your dump>`, showing its
progress. Everything it fetches and builds goes in one folder (about
15 GB), which you can change on its first page:

| Computer | The wizard's folder |
|---|---|
| Windows | `%LOCALAPPDATA%\blinx2-recomp` |
| macOS | `~/Library/Application Support/blinx2-recomp` |
| Linux | `~/.local/share/blinx2-recomp` |

At the end it shows the bundle; **Install now** runs the target's installer
on this computer (section 3, 4 or 5 below). The options you picked become
the data folder's `config/config.toml` on the first install, only when you
have none yet (nor an older version's `config/enhance.toml`): a later
install never replaces your settings (section 6).
Saves, settings and logs live in the data folder, as with every bundle.

At start the wizard asks GitHub whether a newer release exists and says so
(one request, three seconds at most; a box on its first page turns it off).
Running the wizard again later reuses its folder and rebuilds only what
changed. Delete the folder to remove everything it fetched (uv's cache
and its Python included); the installed game and your data folder are
separate, and the wizard refuses a folder that overlaps the data folder.

The command route below is the same build, by hand.

## 1. On the build machine

The build machine can be macOS, Linux or Windows. Each can package these
targets:

| Build host | windows | steamos | macos |
|---|---|---|---|
| macOS (Apple silicon) | yes (`brew install makensis`) | yes | yes |
| Linux x86-64 or aarch64 | yes (distribution `makensis`) | yes | no |
| Windows x86-64 or arm64 | yes (`setup` fetches NSIS) | yes | no |

### Prerequisites

`./blinx2` (`blinx2.py`) is a small bootstrap. The tool itself is
[xboxrecomp-cli](https://github.com/apexJCL/xboxrecomp-cli), at the release
`game.toml` pins (`[cli] tag`, locked to `[cli] commit`: a tag that names
another commit is refused). The bootstrap looks for it in this order:
1. `$XBOXRECOMP_CLI_DIR`.
2. `external/xboxrecomp-cli` in this checkout, used only at the pin. A
   clone the bootstrap made is moved to a new pin; any other checkout there
   at another commit is refused.
3. `../xboxrecomp-cli` beside this checkout.
4. Otherwise it clones it at the pin into `external/xboxrecomp-cli`, which
   needs git. A failed clone leaves nothing behind.

Everything else (CMake, Ninja, the Python packages, the llvm-mingw
cross-compiler, the toolkit) is fetched by `setup` into this checkout, each
download checked against a pinned sha256. The Python environment (`.venv/`)
is made by [uv](https://docs.astral.sh/uv/) from the committed `uv.lock`,
which pins every package by its sha256.

- **All hosts:** Python 3.9 or newer (for the bootstrap; uv gives the CLI
  the 3.12 it needs), uv on `PATH`, git, about 15 GB free,
  and your dump: `blinx2 import /path/to/BLiNX2.iso` (or the disc's folder)
  checks it is BLiNX 2 and puts it in `game_files/`, or copy the disc's
  files there yourself (`game_files/default.xbe` plus the rest; `blinx2
  PATH` imports and builds in one go). `setup` does not install uv; without it, `setup` and `doctor`
  print the command for your system:
  - macOS: `brew install uv`;
  - Linux, SteamOS included: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    (it installs into `~/.local/bin`), or the distribution's uv package;
  - Windows: `winget install --id=astral-sh.uv -e`.

  If uv has to fetch a Python for the environment (`.python-version` asks
  for 3.12 or newer), it checks the download against hashes built into uv.
- **macOS:** the Command Line Tools (`xcode-select --install`). For the macos
  target, Homebrew's `sdl2`, `sdl3`, `openssl` and `libepoxy`. For the windows
  target, `brew install makensis`.
- **Linux:** for the windows target, `makensis` from the distribution
  (`sudo apt install nsis`, `sudo dnf install mingw32-nsis`,
  `sudo pacman -S nsis`). On an immutable system (SteamOS, Fedora Atomic and
  similar), `makensis` goes in a toolbox or distrobox: build on the host,
  then run `blinx2 package windows --no-build` inside the box, which only
  stages the files and runs `makensis` (the build needs the host's `.venv`
  and llvm-mingw; the box needs only `makensis`). `blinx2 doctor` prints the commands.
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
./blinx2 setup              # .venv (uv sync from uv.lock), llvm-mingw, toolkit; ends with doctor
./blinx2 analyze            # parse the XBE, find functions, classify, recover ABIs
./blinx2 recomp             # lift to C: src/recomp/gen/
./blinx2 build [windows|macos]   # build-win/ or build/
```

Every stage invalidates `gen.key.json` and `recomp` writes it again, so a
stage run by hand with extra arguments always makes the next `package`
regenerate.

`setup` clones the toolkit at the commit pinned in `game.toml`
(`[toolkit] commit`). The pin must be at least as new as this tree
needs; if `build` fails on a missing toolkit header, point
`XBOXRECOMP_DIR` at a newer toolkit checkout (`setup` then leaves it
alone).

`blinx2 build` with no target builds `macos` on macOS and `windows` (into
`build-win/`) elsewhere; on Linux that is the cross-build, since Linux has
no native target of its own.

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

**Untested natively on Windows.** Under Proton on Linux, with the silent
switch (`/S`), these are tested: install, a launch to the D3D11 title and
attract screens, `BLINX2_DATA_DIR`, installing again on top, and uninstall
(the program folder goes, `%LOCALAPPDATA%\BLiNX2` stays byte for byte).
The interactive setup pages, the Start Menu and desktop shortcuts, and the
Settings > Apps entry are not tested, and neither is building on a Windows
host.

## 4. Steam Deck or Linux gaming PC (steamos)

The steamos bundle runs on a Steam Deck with stock SteamOS and on a Linux
gaming distribution that ships `umu-run`. The game runs under Proton
through `umu-run` (umu-launcher); a stock Steam Deck does not have it, and
the installer offers to download it (below). The installer and launcher are
xboxrecomp-cli's own, shared by every game it packages. From Desktop Mode:

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
`--import-saves DIR` (copies an older save root into an empty `hdd/`),
`--fetch-umu` and `--umu-dir DIR` (below). The install creates `config/`
when it is absent, so a setting can go in `config/launch.env` before the
first launch; it never changes what is in it.

**umu-run.** The installer and the launcher look for `umu-run` on PATH,
then in `~/.local/bin` (Game Mode's PATH lacks it), then in the copy the
installer downloaded. With none (a stock Steam Deck), the installer asks
whether to download umu-launcher 1.4.4, the release xboxrecomp-cli pins,
checked against its sha256; `--fetch-umu` does it without asking. The copy
goes to `~/.local/share/xboxrecomp/umu` (or `--umu-dir`), in the home
folder that SteamOS updates keep. `./install.sh status` shows which
`umu-run` the game uses; `UMU_RUN` in `config/launch.env` picks another.

**Steam.** The installer adds the stable launcher `~/Games/BLiNX2/BLiNX2`
as a non-Steam game, so the entry keeps working across updates. Without
Steam open, add it by hand: Steam > Games > Add a Non-Steam Game to My
Library > Browse > `~/Games/BLiNX2/BLiNX2`. Leave "Force the use of a
specific Steam Play compatibility tool" **off** for it: the launcher starts
Proton itself. Then play from Game Mode.

**Game Mode resolution (Steam Deck).** In Game Mode, open the BLiNX2
entry's Properties > General and set "Game Resolution" to **Native**
(Steam lists it as 1280x800, the Deck's panel), so Steam does not try to
scale the game's output. The game stays 4:3 with bars at the sides (widescreen is not
done yet); for a sharper picture set `scale = 2`, or leave it at 1 and turn
on FSR in the quick-access menu.

The first launch downloads the Steam Linux Runtime and GE-Proton and creates
the Wine prefix (`~/Games/BLiNX2/prefix`), which takes a few minutes. A
zenity or kdialog window says so (in Game Mode, also a notification) and
closes when the game starts; `LAUNCH_NOTICE=0` in `config/launch.env` turns
it off. The prefix holds nothing of yours and is recreated if deleted.

## 5. macOS

Open the `.dmg` and drag `BLiNX2.app` to Applications (replace the old one
to update). The game files are inside the app. To uninstall, drag it to the
Trash; your saves stay in `~/Library/Application Support/BLiNX2`.

The app is signed ad hoc on the Mac that built it, not notarized. Copied to
another Mac, Gatekeeper may refuse it: right-click > Open once, or
`xattr -dr com.apple.quarantine /Applications/BLiNX2.app`.

## 6. Settings

The game reads two settings files. `config.default.toml` ships in the
bundle beside the game (in `BLiNX2.app/Contents/Resources` on macOS) and
holds every option at its default; an update replaces it, so new options
and defaults reach you without a step. `config/config.toml` in the data
folder holds only what you changed and wins over the defaults; an update
never touches it. The first launch writes it as a short comment header
that says so, and an in-game Save will write there too. A
`config/enhance.toml` from an earlier version is renamed to `config.toml`
on the first launch, and the old `config/enhance.toml.default` copy is
deleted. Environment variables win over both files (docs/env.md).
The bundle's frame pacing defaults to `sleep` (the game's frame wait
sleeps until the next vblank, which saves CPU and battery); `spin` is the
console-original timing, where the wait holds a CPU core as on the Xbox. To
get it, put `[present]` and `pacing = "spin"` in `config/config.toml`, or
`RECOMP_PRESENT_PACING=spin` in `config/launch.env`; the bundle's README.txt
says the same, and `blinx2 package` prints it as a note.
`config/launch.env` holds your own
environment settings, `KEY=value` per line, read after the bundle's
`launch.env.default`. `logs/` keeps one log per launch, the newest
`LOG_KEEP` (10).

Controllers work as player 1 on every target, and so do the keyboard and
the mouse (`input.keyboard` and `input.mouse` in `config.default.toml`; the
keys are in the bundle's README.txt and `docs/input.md`, and
`[input.bindings]` in `config/config.toml` changes them). On macOS the app
also turns host pads on (`RECOMP_HOST_PAD=1`); the keyboard and the mouse do
not need it.

`BLINX2_DATA_DIR` moves the user-data folder for the macOS app and the
Windows launcher. It exists for tests, which must never touch your real
saves or `launch.env`: set it to a scratch folder whenever you start a
packaged game from a script (`open --env BLINX2_DATA_DIR=... BLiNX2.app`).

### Your HUD texture pack

The HUD, menus, icons and the Latin font are small textures the game
samples at 640x480; at `render.scale` 2 or 3 they are the blurriest thing
on screen. `blinx2 enhance hud` makes a pack of them at 4x from your own
game files (the set is `[enhance.hud]` in `game.toml`; an integer xBR
upscale, a few seconds), and it re-renders the Latin atlas from PT Sans
Narrow Bold (OFL 1.1), a narrow face close to the game's Arial Narrow Bold;
each glyph is drawn at one scale for the whole font, centred on the
stock glyph's box and on its baseline, so the layout holds (widths are
nudged towards the stock ones, and brackets span the stock box). macOS
ships it; on Linux and Windows install PT Sans Narrow (ParaType, a Google
Fonts family) for your user. `enhance hud` finds it in the system's font folders by name;
`--font` takes another file (`.ttf`, or a `.ttc` holding that face) or an
installed font's full name. Without a font the atlas is upscaled like the
rest:

```sh
./blinx2 enhance hud                   # or --font /path/to/PT_Sans-Narrow-Web-Bold.ttf
./blinx2 package macos --hud-pack      # or windows, steamos
```

`--hud-pack` copies `dist/enhance/hud/hud.pack` into the bundle's
`enhance/` folder and turns `textures.pack` on in its
`config.default.toml` (a pack is off unless that key names it). The game
reads that file on every launch, so the pack is on after a first install
and after an upgrade alike. For the stock HUD, put this in
`config/config.toml`:

```toml
[textures]
pack = "none"
```

Metal and D3D11
draw the pack; the CPU renderer ignores it. The pack is made from your
game files, like the bundle: keep it private, and never commit it (`*.pack`
is gitignored). `golden` runs never use one.

## 7. Troubleshooting

- **`blinx2 doctor`** names whatever is missing and how to install it.
- **"no uv on PATH":** install uv with the command `setup` printed (above,
  Prerequisites), open a new terminal so `PATH` picks it up, and run setup
  again. A `.venv` that already works keeps building and packaging without
  uv; only `setup` needs it.
- **"no xboxrecomp-cli":** the bootstrap found no CLI and could not clone
  it: git is missing, there is no network, or the pinned commit is not on
  the remote (the line above it says which). Clone
  `https://github.com/apexJCL/xboxrecomp-cli.git` beside this checkout, or
  set `XBOXRECOMP_CLI_DIR` to a checkout of it. `blinx2 doctor` shows which
  CLI commit runs, and whether it is the pinned one. If
  `external/xboxrecomp-cli` is "not the pin" and the bootstrap did not
  clone it, delete it, or point `XBOXRECOMP_CLI_DIR` at it to use it as it
  is.
- **"uv lock --check failed":** most likely someone changed
  `pyproject.toml` without re-locking. Update your checkout; maintainers run
  `blinx2 pins refresh` (or `uv lock`) and commit `uv.lock`. `.venv` is left
  as it was.
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
- **Music, voices or a movie are missing, or the game says the disc is
  dirty or damaged:** a file is missing from `game_files/`. The game's log
  (in `logs/`) names it on a `[FILE] missing` line, and the `[FILE]
  summary` line at the end counts them. `blinx2 import
  /path/to/BLiNX2.iso --check` lists what differs from the disc; `blinx2
  import /path/to/BLiNX2.iso --replace` puts the whole disc in again (or
  extract it into `game_files/` yourself), then rebuild.
- **steamos: "umu-run is not installed":** on a stock Steam Deck, run
  `./install.sh --fetch-umu` from the unpacked bundle, in Desktop Mode.
  `./install.sh status` names the `umu-run` the game uses.
- **steamos: nothing happens at launch:** the first launch downloads the
  runtime and Proton for a few minutes. `~/Games/BLiNX2/logs/umu.log` shows
  the progress, and the newest `logs/game-*.log` is the game's own log. If
  a first launch failed half-way (no network), launch again; if it keeps
  failing, delete `~/Games/BLiNX2/prefix`.
- **A setting seems ignored:** the game's log has one `[ENHANCE] config:`
  line naming the files it read (`config.default.toml`, then
  `config/config.toml`) with the keys each holds, or `none` when it read
  none. An `[ENHANCE] config error:` line names a file that failed to
  parse, which is then ignored, and `[ENHANCE] <key> = <value> from
  <variable>` lines name settings an environment variable overrode.
- **A bench run warns about a game outside the bench:** the installed game
  is still open on the same PC. Close it, or pass `--kill-game`.

## 8. Maintainers

`blinx2 pins refresh` rewrites `config/setup-pins.json` from the GitHub
API (the llvm-mingw tag comes from `game.toml`'s `[toolchain]`) and then runs
`uv lock --upgrade`, which re-resolves `uv.lock` against PyPI. Last, it
prints, beside the tags `game.toml` pins, the newest toolkit release
(`blinx2-v*`) and the newest xboxrecomp-cli release (`v*`), with a warning
when a remote tag no longer names the pinned commit. It never edits
`game.toml`. To move a pin, edit the `tag` and `commit` lines under
`[toolkit]` or `[cli]` together and test. Python dependencies are declared
in `pyproject.toml`: capstone and pefile stay on exact versions there, since
the lifter decodes with capstone and another version could change `gen/`.
Review the diff before committing: setup trusts these hashes.

The wizard's downloads: `./blinx2 wizard build --tag <tag>` (the CLI's
`docs/wizard.md`) makes the three archives and `SHA256SUMS` in
`dist/wizard/` from `game.toml`'s `[wizard]` table at that tag, all three
on a Mac (the Linux one through Docker). `.github/workflows/release-wizard.yml`
does the same on a `v*` tag push and attaches them to the release (a
draft release is made for the tag when it has none; publish it after a
look); it is the CLI's template with `blinx2` filled, so keep it
identical. A manual run (Actions > release-wizard > Run workflow) builds
read-only, without attaching, unless `release` is ticked. The `[wizard]` options must match
`packaging/config.default.toml` (`./blinx2 wizard config --json` checks).

Developer checks, from the dev group (`blinx2 setup --dev`, or any
`uv run`, which syncs it):

```sh
uv run pytest scripts       # this game's tests; the CLI's are in xboxrecomp-cli
uv run ruff check . && uv run ruff format --check .
git config blame.ignoreRevsFile .git-blame-ignore-revs   # skip the ruff format commit
```
