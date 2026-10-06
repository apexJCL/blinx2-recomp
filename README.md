# BLiNX 2 static recompilation

A static recompilation of the original Xbox game *BLiNX 2: Masters of Time &
Space* to native PC code. The game's x86 code in `default.xbe` is lifted to C
by the [xboxrecomp](https://github.com/apexJCL/xboxrecomp) toolkit and compiled
together with a host runtime: a replacement Xbox kernel, NV2A (GPU) pushbuffer
execution and APU/audio pieces.

**Status:** playable through stage 1 on Linux (Proton, Direct3D 11) using the Windows build |
boots and runs stage 1 on macOS (Apple silicon, Metal) | audio, real-device
input, saves and FMV in progress | **no game data included: bring your own copy**

![BLiNX 2 recompiled: stage 1 on the Metal backend](docs/images/hero.png)

<!-- TODO(link): releases page, once a release exists -->
<!-- TODO(link): demo video -->

## Screenshots

![Title screen](docs/images/title.png)

![Stage 1 gameplay](docs/images/stage1.png)

![Boss fight: the Giant Mandrake](docs/images/boss1.png)

<!-- TODO(screenshot): second boss fight or time-control effect -->
<!-- ![Boss fight 2](docs/images/boss2.png) -->

<!-- TODO(screenshot): attract mode -->
<!-- ![Attract mode](docs/images/attract.png) -->

<!-- TODO(screenshot): macOS, Metal backend in an SDL2 window -->
<!-- ![macOS Metal backend](docs/images/macos-metal.png) -->

<!-- TODO(gif): short gameplay clip -->
<!-- ![Gameplay clip](docs/images/gameplay.gif) -->

### Render scale

The optional enhancements layer can render the 3D at a multiple of the stock
640x480 (`render.scale` in `enhance.toml`, or `RECOMP_RENDER_SCALE`, 1 to 4;
Metal and Direct3D 11). The grid shows the same detail of stage 1 at 1x, 2x and
3x, taken from the Metal backend in a window at twice the stock size. Stock
behaviour, and the golden checks, stay at 1x.

![The same detail of stage 1 rendered at 1x, 2x and 3x](docs/images/render-scale.png)

## What this is

This repository holds the game-specific half of the project: the boot code,
hand-written replacements for a few XDK library functions, scripts for the
pipeline, benchmarks and golden-frame checks, and the design notes. The
generic half (the lifter and the host runtime) is the xboxrecomp toolkit.

<!-- TODO(diagram): architecture, default.xbe -> toolkit analysis/lift -> generated C -> compiled with host runtime (kernel, NV2A, APU) -> native binary -->
<!-- ![Architecture diagram](docs/images/architecture.png) -->

The toolkit is a fork, [apexJCL/xboxrecomp](https://github.com/apexJCL/xboxrecomp),
of [sp00nznet/xboxrecomp](https://github.com/sp00nznet/xboxrecomp). This
project needs changes that are only in the fork, so it builds against
apexJCL/xboxrecomp, not upstream.

## Current status

| Platform | Render backend | Status |
|---|---|---|
| Windows / Linux (Proton) | Direct3D 11 (DXVK under Proton) | Playable through stage 1. The tested route is a Windows x86-64 build run under Proton. |
| macOS (Apple silicon) | Metal, shown in an SDL2 window | Boots and runs the attract mode and stage 1. Audio is not available on macOS yet. |

Audio, real-device input, saves and FMV playback are in progress. See
`openspec/changes/`.

## Requirements

### Before you start

- [ ] Your own legally obtained copy of BLiNX 2: a dump of the disc, meaning
  `default.xbe` plus the rest of the game's files. This project does not
  provide or link to them.
- [ ] The game files placed in `game_files/` (git ignores it).
- [ ] Python 3.9 or newer and git. `./blinx2 setup` fetches the rest
  (CMake, Ninja, the Python packages, llvm-mingw and the toolkit fork at its
  pinned commit), checking each download against a pinned sha256.
- [ ] The platform tools below.

### Per platform

No minimum versions have been established; the "tested" entries are the versions
listed under [Tested with](#tested-with).

| Platform | OS | Toolchain | Dependencies | GPU backend | Status |
|---|---|---|---|---|---|
| macOS (Apple silicon) | tested: macOS 27.0 | Xcode Command Line Tools (tested: 27.0, Apple clang 21.0.0), CMake (tested: 4.4.3) | SDL2, OpenSSL (Homebrew; tested: sdl2-compat 2.32.72, OpenSSL 3.6.5), Python (tested: 3.14.8) | Metal | Boots, attract mode and stage 1; no audio |
| Windows x86-64 (native) | not tested | [llvm-mingw](https://github.com/mstorsjo/llvm-mingw) (clang + lld + mingw-w64, UCRT), CMake, Ninja (cross-compiled) | - | Direct3D 11 | Builds with llvm-mingw; tested only under Proton |
| Linux (Proton) | tested: Fedora 44-based, kernel 7.2 | Same Windows build, cross-compiled with llvm-mingw (tested: 20260922, clang 23.1.2) | Proton via `umu-run` (tested: GE-Proton11-7, umu-launcher 1.4.4) | Direct3D 11 via DXVK | Playable through stage 1 |

The pipeline and the Windows cross-build run on macOS, Linux or Windows
(building on a Windows host is untested). The macOS build needs a Mac.

## Tested with

| Platform | OS | Toolchain | Key dependencies | GPU / driver | Backend |
|---|---|---|---|---|---|
| macOS (Apple silicon) | macOS 27.0 (arm64) | Apple clang 21.0.0 (Command Line Tools 27.0), CMake 4.4.3, Ninja 1.13.2 | sdl2-compat 2.32.72, OpenSSL 3.6.5, Python 3.14.8 | Apple Silicon (M4) | Metal |
| Linux (Proton) | Fedora 44-based, kernel 7.2 (x86-64) | llvm-mingw 20260922 (clang 23.1.2), CMake 3.31.11, Ninja 1.12.1 (in a Fedora 42 container) | GE-Proton11-7 via umu-launcher 1.4.4, DXVK 3.1 (as bundled) | NVIDIA GeForce RTX 2060, NVIDIA proprietary driver 615.71 (Vulkan 1.4) | Direct3D 11 (DXVK) |
| Windows (native) | not tested | llvm-mingw | - | - | Direct3D 11 |

## Getting started

The layout used below:

```
cat/                 this repository
cat/game_files/      your disc dump: default.xbe and the game's files
```

One command-line tool, `blinx2` (`blinx2.py`, standard-library Python), runs
every step on macOS, Linux and Windows. To get a game you can install, run
one command:

```sh
./blinx2             # Windows: blinx2 (the blinx2.cmd wrapper)
```

It fetches the toolchain the first time, generates and builds whatever is
missing or out of date, and leaves a private bundle for this computer in
`dist/` (see [Install on your own machines](#install-on-your-own-machines)).
`./blinx2 package windows|steamos|macos` does the same for another target,
and `./blinx2 doctor` shows what this machine has and what it can package.
A cold run takes about 20 to 25 minutes; the next ones only rebuild.

**Developing the recomp itself** uses the separate steps:

```sh
./blinx2 setup       # once: .venv, llvm-mingw, the toolkit; ends with doctor
./blinx2 analyze     # parse the XBE, find functions, classify, recover ABIs
./blinx2 recomp      # lift to C: src/recomp/gen/
./blinx2 build       # macOS: build/cat_recomp; elsewhere: build-win/cat_recomp.exe
```

`./blinx2 <command> --help` lists the options. The optional `ghidra` stage
(slow, cached) only improves function names; it needs Ghidra
(`GHIDRA_HOME`) and a Python 3.13 venv with PyGhidra at `.venv-ghidra`.
`scripts/pipeline.sh <stage>` still works and runs the same code. `package`
builds in its own `build-pkg-macos/` and `build-pkg-win/`, with the stock
options, so your `build/` and `build-win/` keep whatever options you set.

### The toolkit

`setup` clones the toolkit fork
([apexJCL/xboxrecomp](https://github.com/apexJCL/xboxrecomp), branch
`blinx2/portability`) at the commit pinned in `config/setup-pins.json` into
`external/xboxrecomp`, unless one is already found. CMake, `blinx2` and
`scripts/bench.sh` look for it in this order:

1. `$XBOXRECOMP_DIR` (or `-DXBOXRECOMP_DIR=...` for CMake);
2. `external/xboxrecomp` inside this project;
3. `../xboxrecomp`, next to this project.

### Run on macOS (Metal)

```sh
./blinx2 build macos
RECOMP_PB_BACKEND=metal ./build/cat_recomp
```

Run it from this directory: the game files are looked up in `game_files/`
(or wherever `RECOMP_GAME_FILES` points). `RECOMP_PB_BACKEND` unset uses the
slower CPU rasteriser.

### Run on Linux under Proton, or on Windows (Direct3D 11)

```sh
./blinx2 build windows
```

Run `build-win/cat_recomp.exe` from this directory under Proton (for example
with `umu-run`; native Windows is untested), with
`RECOMP_PB_BACKEND=d3d11`.

`scripts/bench.sh` automates this on a remote x86-64 Linux host over SSH: it
syncs the toolkit and this project, builds in a distrobox, runs the game under
Proton and runs the golden-frame checks. See the comment at the top of the
script for its settings (`BENCH_HOST` and so on).

## Install on your own machines

`./blinx2` (or `./blinx2 package windows|steamos|macos`) makes a private
bundle in `dist/`: a Windows setup program, a tar with an installer for a
SteamOS-like Linux gaming PC (Proton, with a Steam entry, updates and
rollback), or a macOS `.dmg`. Saves and settings live outside the program
files and survive every update. [docs/packaging.md](docs/packaging.md) has
the steps for each machine.

A bundle contains your own copy of the game: keep it on your own machines.

## Configuration

The runtime reads its settings from environment variables, such as
`RECOMP_PB_BACKEND` (`cpu`, `metal`, `d3d11`, `null`) and `RECOMP_PB_EXEC`.
The full list, with defaults and the `RECOMP_TRACE` / `RECOMP_DEBUG` lists, is
in [docs/env.md](docs/env.md).

## Troubleshooting and known issues

- **macOS link error about the SDK:** `blinx2` sets
  `DEVELOPER_DIR=/Library/Developer/CommandLineTools` itself; set it when
  running CMake by hand.
- **Game files not found:** run the binary from this directory, with the files
  in `game_files/`, or point `RECOMP_GAME_FILES` at them.
- **Slow rendering on macOS:** with `RECOMP_PB_BACKEND` unset the CPU
  rasteriser is used; set it to `metal`.
- **No audio on macOS:** not available yet.
- Audio, real-device input, saves and FMV are still in progress.

## Repository layout

- `src/`: boot code (`main.c`), hand-written XDK replacements
  (`recomp_manual.c`), pad input and save seeding.
- `blinx2.py`: the command-line tool (setup, pipeline, build, package).
- `packaging/`: the installers, launchers and defaults the bundles carry.
- `scripts/`: the remote bench, golden-frame and audio checks, packaging
  helpers.
- `config/`: pipeline inputs, such as seed functions for the disassembler.
- `docs/`: notes, including the [environment variables](docs/env.md).
- `openspec/`: specs and change proposals.

`src/recomp/gen/` (the lifted code) is generated on your machine by the
pipeline and is never committed.

## Contributing

The project uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for
change tracking. Each piece of work is a change under `openspec/changes/<name>/`,
with a proposal, a design, tasks and spec deltas. Finished changes are archived
under `openspec/changes/archive/`, and their requirements are merged into
`openspec/specs/`. Departures from the original hardware's behaviour are
recorded as requirements in the `deviations` spec (introduced by the
`deviations-register` change).

Toolkit changes go to [apexJCL/xboxrecomp](https://github.com/apexJCL/xboxrecomp)
(fork of [sp00nznet/xboxrecomp](https://github.com/sp00nznet/xboxrecomp)),
branch `blinx2/portability`.

## Legal

This repository contains **no game data and no game code**:

- no game files, assets or saves;
- no lifted (recompiled) game code. `src/recomp/gen/` is generated on your
  machine by the pipeline and is never committed.

To build it you need your own legally obtained copy of BLiNX 2. BLiNX 2 and
its assets belong to their respective owners; this project is not affiliated
with them. A bundle made by `blinx2 package` contains your copy of the game
and code generated from it: it is for your own machines only, and is not
yours to redistribute.

## License and credits

MIT, see [LICENSE](LICENSE). Parts of `src/main.c`, `src/recomp_manual.c` and
`CMakeLists.txt` started from xboxrecomp's MIT-licensed new-game templates; the
license file carries that notice too.

The toolkit that the build links in statically carries LGPL-2.1 APU code
extracted from xemu. If you distribute a built binary, read [NOTICE](NOTICE)
first.

Built on [xboxrecomp](https://github.com/sp00nznet/xboxrecomp) by sp00nznet.
