# BLiNX 2 static recompilation

A static recompilation of the original Xbox game *BLiNX 2: Masters of Time &
Space* to native PC code. The game's x86 code in `default.xbe` is lifted to C
by the [xboxrecomp](https://github.com/apexJCL/xboxrecomp) toolkit and compiled
together with a host runtime: a replacement Xbox kernel, NV2A (GPU) pushbuffer
execution and APU/audio pieces. This repository holds the game-specific half:
the boot code, hand-written replacements for a few XDK library functions,
scripts for the pipeline, benchmarks and golden-frame checks, and the design
notes.

## Status

- **Windows / Proton (Linux):** playable through stage 1. The game's 3D is
  drawn by a Direct3D 11 render backend (DXVK under Proton). The tested route
  is a Windows x86-64 build run under Proton.
- **macOS (Apple silicon):** boots and runs the attract mode and stage 1 with
  a Metal render backend, shown in an SDL2 window. Audio is not available on
  macOS yet.
- Audio, real-device input, saves and FMV playback are in progress. See
  `openspec/changes/`.

## What is not included

This repository contains **no game data and no game code**:

- no game files, assets or saves;
- no lifted (recompiled) game code. `src/recomp/gen/` is generated on your
  machine by the pipeline and is never committed.

To build it you need your own legally obtained copy of BLiNX 2: a dump of
the disc, meaning `default.xbe` plus the rest of the game's files. They go in
`game_files/`, which git ignores.

## Toolkit

The build needs the xboxrecomp toolkit fork at
<https://github.com/apexJCL/xboxrecomp>, a fork of
[sp00nznet/xboxrecomp](https://github.com/sp00nznet/xboxrecomp). This project
needs changes that are only in the fork, so it builds against
apexJCL/xboxrecomp, not upstream. Use branch `blinx2/portability`; this
release was built and tested against commit `d54e083`:

```sh
git clone -b blinx2/portability https://github.com/apexJCL/xboxrecomp.git
git -C xboxrecomp checkout d54e083b65315735bbce1f772672d0d465f03265
```

CMake, `scripts/pipeline.sh` and `scripts/bench.sh` look for the toolkit in
this order:

1. `$XBOXRECOMP_DIR` (or `-DXBOXRECOMP_DIR=...` for CMake);
2. `external/xboxrecomp` inside this project;
3. `../xboxrecomp`, next to this project.

## Building

The layout used below:

```
xboxrecomp/          toolkit clone (or put it in cat/external/xboxrecomp)
cat/                 this repository
cat/game_files/      your disc dump: default.xbe and the game's files
```

### 1. Generate the code (macOS or Linux)

The pipeline runs the toolkit's Python tools. On macOS, run
`tools/macos/setup.sh` in the toolkit once to create its `.venv`. Then, from
this directory:

```sh
scripts/pipeline.sh analyze   # parse the XBE, find functions, classify, recover ABIs
scripts/pipeline.sh recomp    # lift to C: src/recomp/gen/
```

`scripts/pipeline.sh` with no arguments lists the stages. The optional
`ghidra` stage (slow, cached) improves function names.

### 2a. macOS (Metal)

Needs Xcode's Command Line Tools, CMake, SDL2 and OpenSSL (Homebrew). If
linking fails with an SDK mismatch, set
`DEVELOPER_DIR=/Library/Developer/CommandLineTools`.

```sh
scripts/pipeline.sh build                         # configures and builds build/
RECOMP_PB_EXEC=1 RECOMP_PB_BACKEND=metal ./build/cat_recomp
```

Run it from this directory: the game files are looked up in `game_files/`.
`RECOMP_PB_BACKEND` unset uses the slower CPU rasteriser.

### 2b. Windows / Proton (Direct3D 11)

The Windows build is cross-compiled with [llvm-mingw](https://github.com/mstorsjo/llvm-mingw)
(clang + lld + mingw-w64, UCRT):

```sh
cmake -S . -B build-win -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=cmake/llvm-mingw-x86_64.cmake \
    -DLLVM_MINGW_ROOT=/path/to/llvm-mingw \
    -DCMAKE_BUILD_TYPE=Release
cmake --build build-win
```

Run `build-win/cat_recomp.exe` from this directory, under Proton
(for example with `umu-run`) or on Windows, with
`RECOMP_PB_EXEC=1 RECOMP_PB_BACKEND=d3d11`.

`scripts/bench.sh` automates this on a remote x86-64 Linux host over SSH: it
syncs the toolkit and this project, builds in a distrobox, runs the game under
Proton and runs the golden-frame checks. See the comment at the top of the
script for its settings (`BENCH_HOST` and so on, in `scripts/bench.env`).

## Repository layout

- `src/`: boot code (`main.c`), hand-written XDK replacements
  (`recomp_manual.c`), pad input and save seeding.
- `scripts/`: the pipeline, the remote bench, golden-frame and audio checks.
- `config/`: pipeline inputs, such as seed functions for the disassembler.
- `analysis/golden/`: golden-frame hashes and audio thresholds. The reference
  frames themselves are game output and stay local.
- `openspec/`: specs and change proposals.

## Change tracking

The project uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) for
change tracking. Each piece of work is a change under `openspec/changes/<name>/`,
with a proposal, a design, tasks and spec deltas. Finished changes are archived
under `openspec/changes/archive/`, and their requirements are merged into
`openspec/specs/`. Departures from the original hardware's behaviour are
recorded as requirements in the `deviations` spec.

## License

MIT, see [LICENSE](LICENSE). Parts of `src/main.c`, `src/recomp_manual.c` and
`CMakeLists.txt` started from xboxrecomp's MIT-licensed new-game templates; the
license file carries that notice too. BLiNX 2 and its assets belong to their
respective owners; this project is not affiliated with them.

The toolkit that the build links in statically carries LGPL-2.1 APU code
extracted from xemu. If you distribute a built binary, read [NOTICE](NOTICE)
first.
