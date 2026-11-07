# BLiNX 2 for developers

How the port works, how to build and test it from source, and how to
contribute. Players want the [README](../README.md) and
[playing.md](playing.md).

**Contents:** [Architecture](#architecture) | [Build from source](#build-from-source) |
[The toolchain and its pins](#the-toolchain-and-its-pins) |
[Testing and goldens](#testing-and-goldens) |
[Environment variables](#environment-variables) |
[Documentation](#documentation) | [Contributing](#contributing)

## Architecture

```
game_files/default.xbe
   │  blinx2 analyze      parse the XBE, disassemble, find functions, recover ABIs   (xbr, xboxrecomp-cli)
   │  blinx2 recomp       lift x86 to C                                             (xboxrecomp tools)
   ▼
src/recomp/gen/*.c       the lifted game (generated on your machine, never committed)
   +  src/                this game's boot code, hand-written XDK replacements, pad input, save seeding
   +  xboxrecomp runtime  replacement Xbox kernel, NV2A pushbuffer executor (Metal, D3D11, CPU), APU audio
   │  blinx2 build        CMake + Ninja; llvm-mingw cross-compiles the Windows build on every host
   ▼
build/cat_recomp (macOS) or build-win/cat_recomp.exe (Windows, Proton)
   │  blinx2 package      a private bundle: macOS .dmg, Windows setup program, SteamOS tar with installer
   ▼
dist/
```

This repository holds the game-specific half: the boot code, hand-written
replacements for a few XDK library functions, the game's environment keys,
the packaging templates, the bench and golden-frame harness, and the design
notes. The generic halves live in two other repositories:

| Repository | Role |
|---|---|
| [apexJCL/xboxrecomp](https://github.com/apexJCL/xboxrecomp), branch `blinx2/portability` | The toolkit: lifter, host runtime (kernel, NV2A, APU), enhancements layer. A fork of [sp00nznet/xboxrecomp](https://github.com/sp00nznet/xboxrecomp); this project needs changes that are only in the fork. |
| [apexJCL/xboxrecomp-cli](https://github.com/apexJCL/xboxrecomp-cli) | `xbr`, the game-agnostic command-line tool. `./blinx2` is a standard-library bootstrap that runs it at the release `game.toml` pins. |

| Path | Contents |
|---|---|
| `src/` | boot code (`main.c`), XDK replacements (`recomp_manual.c`), pad input, save seeding, the glow toggle, this game's rows of the environment table (`env/`) |
| `game.toml` | everything the CLI knows about this game: names, paths, pipeline flags, packaging, bench, the HUD pack set, and the toolkit and CLI pins |
| `blinx2.py`, `blinx2`, `blinx2.cmd` | the bootstrap and its wrappers |
| `packaging/` | the launchers, defaults (`config.default.toml`, `launch.env.default.*`) and README parts the bundles carry |
| `config/` | pipeline inputs: seed functions, spin-wait sites, the download pins |
| `scripts/` | this game's helpers (input scripts, xemu references, the public export, `compare-bundles.py`) and their tests |
| `analysis/` | golden references (`golden/`), research notes, the pipeline's output |
| `docs/` | [environment variables](env.md), [packaging](packaging.md), the README images |
| `openspec/` | specs and change proposals |

## Build from source

The pipeline and the Windows cross-build run on macOS, Linux or Windows; the
macOS build needs a Mac. Builds are tested on these:

| Host | OS | Toolchain | Dependencies | Backend |
|---|---|---|---|---|
| macOS (Apple silicon, M4) | macOS 27.0 | Xcode Command Line Tools 27.0 (Apple clang 21.0.0), CMake 4.4 and Ninja 1.13 from the venv | Homebrew `sdl2` (sdl2-compat 2.32), `sdl3`, `openssl` (3.6), `libepoxy`; Python 3.14 | Metal |
| Linux x86-64 (Proton) | Fedora 44-based, kernel 7.2 | llvm-mingw 20260922 (clang 23.1.2), CMake and Ninja in a Fedora 42 distrobox | GE-Proton11-7 via umu-launcher 1.4.4, DXVK 3.1 (as bundled); NVIDIA GeForce RTX 2060 | Direct3D 11 (DXVK) |
| Windows x86-64 | not tested as a build host | llvm-mingw (fetched by `setup`), NSIS | Python from python.org, Git for Windows | Direct3D 11 |

No minimum versions have been established. Per host, before the first build:

- **All hosts:** Python 3.9 or newer for the bootstrap (uv gives the CLI the
  3.12 it needs), uv on `PATH`, git, about 15 GB free. uv: macOS
  `brew install uv`; Linux `curl -LsSf https://astral.sh/uv/install.sh | sh`;
  Windows `winget install --id=astral-sh.uv -e`.
- **macOS:** the Command Line Tools (`xcode-select --install`); for the macos
  target `brew install sdl2 sdl3 openssl libepoxy`; for the windows target
  `brew install makensis`.
- **Linux:** for the windows target, the distribution's `makensis` (`nsis` or
  `mingw32-nsis`); on an immutable system it goes in a toolbox or distrobox
  (`blinx2 doctor` prints the commands).
- **Windows:** a short checkout path (`C:\b2`) and
  `git config --global core.longpaths true`.

```sh
./blinx2 import /path/to/BLiNX2.iso   # once: the dump into game_files/ (or copy the files there by hand)
./blinx2 setup       # once: .venv (uv sync from uv.lock), llvm-mingw, the toolkit at its pin; ends with doctor
./blinx2 analyze     # parse the XBE, find functions, classify, recover ABIs
./blinx2 recomp      # lift to C: src/recomp/gen/
./blinx2 build       # macOS: build/cat_recomp; elsewhere: build-win/cat_recomp.exe (windows|macos picks)
```

`blinx2` sets `DEVELOPER_DIR=/Library/Developer/CommandLineTools` itself;
set it yourself when running CMake by hand on macOS.

`./blinx2 <command> --help` lists the options. `package` builds in its own
`build-pkg-macos/` and `build-pkg-win/` with the stock options, so your
`build/` and `build-win/` keep whatever options you set; it refuses a Debug
or non-stock build (`CAT_GEN_OPT`, `XBOXRECOMP_ENHANCE=OFF`) unless told
otherwise. The optional `ghidra` stage (slow, cached) only improves function
names; it needs Ghidra (`GHIDRA_HOME`) and a PyGhidra venv at
`.venv-ghidra`. Never edit `src/recomp/gen/` by hand: a function the
disassembler missed goes in `config/seed_functions.json`, then `analyze`
and `recomp` again (`recomp` alone misses new seeds).

Running the development build:

```sh
# macOS (Metal); RECOMP_PB_BACKEND unset is the slow CPU rasteriser
RECOMP_PB_BACKEND=metal ./build/cat_recomp
```

Run it from this directory: the game files are looked up in `game_files/`
(or wherever `RECOMP_GAME_FILES` points), and saves go to the toolkit's
default save root unless `RECOMP_HDD_DIR` says otherwise. Host pads are on
in every build on every host, except while an input script is set (unless `RECOMP_HOST_PAD=1`), so
scripted and golden runs never see one (`RECOMP_HOST_PAD=0` keeps them out).
The keyboard and the mouse come from
`build/config.default.toml` in every build, with or without host pads. Under
Proton, run `build-win/cat_recomp.exe` with `umu-run` and
`RECOMP_PB_BACKEND=d3d11`; host pads are on there by default.

The Python tests and the lint run from the locked dev environment
(`pyproject.toml`, `uv.lock`):

```sh
uv run pytest scripts
uv run ruff check . && uv run ruff format --check .
```

## The toolchain and its pins

`game.toml` pins every moving part; `setup` fetches them and `blinx2 doctor`
reports what is in use and whether it is the pin.

| Component | Pinned at | Where | Notes |
|---|---|---|---|
| xboxrecomp-cli (`xbr`) | tag `v0.20.0`, commit `d047f6c` | `game.toml` `[cli]` | The commit locks the tag: a tag moved to another commit is refused. |
| xboxrecomp toolkit (fork) | tag `blinx2-v0.13.0`, commit `40ed51d`, branch `blinx2/portability` | `game.toml` `[toolkit]` | Cloned into `external/xboxrecomp` by `setup`. |
| llvm-mingw | `20260922` (clang 23.1.2) | `game.toml` `[toolchain]`, hashes in `config/setup-pins.json` | Cross-compiles the Windows build on every host. |
| NSIS | `3.13` | `game.toml` `[toolchain]` | Fetched on Windows; Homebrew or the distribution elsewhere. |
| umu-launcher | `1.4.4` | the CLI | What the SteamOS installer offers to download on a stock Deck. |
| Python packages | `uv.lock` | `pyproject.toml`, `uv.lock` | capstone and pefile stay on exact versions: another capstone could change `gen/`. |

The toolkit is looked up in this order by CMake, `blinx2` and `blinx2 bench`:
`$XBOXRECOMP_DIR` (or `-DXBOXRECOMP_DIR=...`), then `external/xboxrecomp`,
then `../xboxrecomp` beside this checkout. The CLI: `$XBOXRECOMP_CLI_DIR`,
then `external/xboxrecomp-cli` (only at the pin), then `../xboxrecomp-cli`,
otherwise a clone at the pin into `external/xboxrecomp-cli`. Maintainers
move a pin by editing `tag` and `commit` together; `blinx2 pins refresh`
re-pins the downloads and prints the newest releases.

Both the CLI and the toolkit fork are public and MIT licensed (the toolkit
with the exceptions in its NOTICE). This project builds against the fork,
not upstream; upstream-bound changes are offered to sp00nznet/xboxrecomp as
pull requests.

## Testing and goldens

Three scripted scenarios are compared frame by frame against reference
frames (`analysis/golden/golden.json`, references in
`analysis/golden/frames/`) on every integration build, on both GPU backends,
at stock settings (the check fails a run whose log shows a non-stock
`[ENHANCE]` value):

| Scenario | Route | Run time | Backends |
|---|---|---|---|
| `attract` | title and attract mode | 75 s | Metal, D3D11, CPU |
| `stage1` | stage 1 gameplay | 105 s | Metal, D3D11 |
| `story` | the story route to the hub | 100 s | Metal, D3D11 |

```sh
./blinx2 golden run                 # Mac: the Metal build in build/, headless and silent, one scenario at a time
./blinx2 golden run --backend cpu   # the CPU rasteriser (slow; a reference path, not in the routine gates)
./blinx2 bench golden               # a Linux/Proton host over ssh: sync, build in a distrobox, run under Proton, compare
```

Verdicts land in `bench-logs/<stamp>.../golden.txt`. `./blinx2 bench --help`
lists the bench commands (`setup`, `sync`, `build`, `run`, `tests`, `pacing`,
`gc`, ...) and their settings (`BENCH_HOST` and so on). The CPU rasteriser
only has to keep building and passing one check after large merges; speed
and A/B work are Metal and D3D11.

The guest runs as on the console's one CPU: `RECOMP_GUEST_LOCK` (on in this
game) runs one guest thread at a time, released at kernel calls, on every
host, without pinning the threads to one core (`RECOMP_GUEST_CPUS=one` is
the A/B; on native Windows the pin made the movie audio crackle). The game
relies on it: two of its threads add stage lights to one list without a
lock, and on several cores they lost entries and left the ground and water
unlit.

## Environment variables

Every setting the runtime reads goes through one table, read once at startup,
in three tiers: **config** (one variable each), **trace**
(`RECOMP_TRACE=flip,tex,...`, printing only) and **debug**
(`RECOMP_DEBUG=pb_fast=0,fb_dump=/tmp/f_,...`, anything that changes
behaviour). The ones you meet first:

| Variable | Values (default first) | Meaning |
|---|---|---|
| `RECOMP_PB_BACKEND` | `cpu`, `metal`, `d3d11`, `null` | the renderer |
| `RECOMP_GAME_FILES` | `game_files/` in the working directory | where the dump is |
| `RECOMP_HDD_DIR` | the toolkit's save root | the emulated hard disk: saves, caches |
| `RECOMP_HOST_PAD` | unset: on, except in scripted runs | host gamepads in or out (`0`/`1`) |
| `RECOMP_KEYBOARD` | `input.keyboard`: on in `config.default.toml`, off with `RECOMP_CONFIG=none` and in scripted runs | the keyboard as pad 1 |
| `RECOMP_MOUSE` | `input.mouse`: as `RECOMP_KEYBOARD` | the mouse as pad 1 (motion is the right stick) |
| `RECOMP_AC97_READY` | on (x86-64 Windows/Proton; arm64 macOS and Linux); off on native x86-64 Linux | audio; `=0` turns it off |
| `RECOMP_INPUT_SCRIPT` | `@attract`, `@stage1`, `@stage1-enemies`, `@stage1-2`, `@stage1-2-barricade`, `@story-hub`, `@story-load`, `@story-idle`, a file | a scripted pad for reproducible runs |
| `RECOMP_HEADLESS` | `0`, `1` | no window, and silent (it sets `SDL_AUDIODRIVER=dummy` unless set) |
| `RECOMP_CONFIG` | `config/config.toml` (over `config.default.toml` beside the executable), a path, `none` | the player's config file; `none` reads no file, not even the defaults (the old name `RECOMP_ENHANCE_CONFIG` still works) |

The full list, with defaults, source references and the trace and debug keys,
is [docs/env.md](env.md). New keys get a row in the table
(`src/env/recomp_env_game.h` for this game's own) and a row in that file;
fork code has no raw `getenv`.

## Documentation

| Document | What it covers |
|---|---|
| [docs/packaging.md](packaging.md) | building and installing the bundles on every target, settings, the HUD pack, troubleshooting, maintainers' pins |
| [docs/input.md](input.md) | playing on keyboard and mouse: the default keys, rebinding, the mouse settings |
| [docs/frame-generation.md](frame-generation.md) | external frame-generation tools for a 60 fps look (unsupported): what each needs, what to expect from a 30 fps base, the settings that help |
| [docs/env.md](env.md) | every environment variable, by tier, with defaults and where it is read |
| [docs/known-gaps.md](known-gaps.md) | known gaps that are pending but not urgent (untested paths, unsettled questions): what each would look like in a bug report and where to start |
| [game.toml](../game.toml) | the manifest the CLI reads; the CLI's [docs/manifest.md](https://github.com/apexJCL/xboxrecomp-cli/blob/main/docs/manifest.md) documents each key |
| [analysis/golden/golden.json](../analysis/golden/golden.json) | the golden scenarios, their frames and tolerances |
| `openspec/` | specs (`specs/`), open changes (`changes/`) and the archive; the `deviations` spec records every departure from the original hardware's behaviour |
| [xboxrecomp-cli README](https://github.com/apexJCL/xboxrecomp-cli#readme) | `xbr`: starting a new game, the commands, the bench, how a game finds the CLI |
| [xboxrecomp README](https://github.com/apexJCL/xboxrecomp/tree/blinx2/portability#readme) | the toolkit: pipeline, runtime, `docs/runtime/config.md` (the `config.toml` keys) |

## Contributing

The project uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for
change tracking. Each piece of work is a change under
`openspec/changes/<name>/` with a proposal, a design, tasks and spec deltas;
finished changes are archived under `openspec/changes/archive/` and their
requirements merged into `openspec/specs/`. Departures from the original
hardware's behaviour are recorded as requirements in the `deviations` spec.

Rules that every change follows:

- opt-in features default off and never change stock behaviour; the golden
  checks always run at stock;
- a behaviour change on one GPU backend (Metal or Direct3D 11) is mirrored
  on the other, or recorded as a follow-up;
- generated code is never hand-edited; environment variables go through the
  table and `docs/env.md`;
- toolkit changes go to [apexJCL/xboxrecomp](https://github.com/apexJCL/xboxrecomp),
  branch `blinx2/portability`; CLI changes to
  [apexJCL/xboxrecomp-cli](https://github.com/apexJCL/xboxrecomp-cli).
