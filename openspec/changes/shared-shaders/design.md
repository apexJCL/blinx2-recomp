# Design

## Reaching every game from the toolkit

Options weighed:

1. **A line in each game** (today). Forgotten by four of eight games. Rejected
   as the only mechanism; it stays for now only because of the sequencing below.
2. **Attach it to `xbox_enhance`** with an INTERFACE property or a generator
   expression. A library cannot make its consumer run a build step: the only
   route is `$<TARGET_FILE_DIR>` on a target the library does not know.
3. **Stage next to the toolkit's own build output.** The runtime looks beside
   the executable, and games choose their own output directory.
4. **Deferred scan (chosen).** `cmake_language(DEFER DIRECTORY
   ${CMAKE_SOURCE_DIR} CALL ...)` runs at the end of the top directory's
   configure, when every target exists; it walks `BUILDSYSTEM_TARGETS` and
   `SUBDIRECTORIES`, and stages each EXECUTABLE that reaches `xbox_enhance`
   through its link closure (`LINK_LIBRARIES`, then the
   `INTERFACE_LINK_LIBRARIES` of what it links) or asked by name. CMake 3.19
   has DEFER; every game requires 3.20. The first scan read only an
   executable's own `LINK_LIBRARIES`, so cat and KUF, which link just the
   `xboxrecomp` umbrella, were staged only by their own call (review of
   the tracker item). The closure also reaches the toolkit's own test harnesses, which
   link the umbrella and show no menu, so executables under the directory
   that included the module are staged only when asked by name. A game's own
   test executable on the umbrella is staged: a copy of a small directory,
   and the library comes from the one download cache.

The stage is a **custom target** with an `add_dependencies` edge, not a
post-build command: CMP0040 refuses `add_custom_command(TARGET)` for a target
made in another directory, and Burnout 3's executable is in `src/game`.
`$<TARGET_FILE_DIR>` in a custom target adds no dependency on the executable
(CMP0112), so the stage runs before the link, and also for `--target exe`.

New games get it from the template's `xbox_enhance` link with no extra line.
`<game> new` writes `stock_cmake` with `-DXBOXRECOMP_ENHANCE=ON` and
`-DXBOXRECOMP_APU_DSP=ON` (standing rules for every game), and its README stub
carries the mods table's Profile row, so a new game passes the check from day one.

## Sequencing: why the explicit calls stay for now

Game pins can only name public commits, and auto-staging stays local until the
next push round. A game built from its pin at `blinx2-v0.14.0` needs the call.
The function exists there (`cmake/librashader.cmake`, public 7a97fcd, private
a98c689). So all eight games keep or add a guarded call, and a follow-up after
the round removes them. Both orders work: the call only sets a target property
that the scan reads.

## The check

A shared feature missing from a game must fail visibly, without a framework and
without game constants in the CLI.

- **Data:** one table in `src/xboxrecomp_cli/shared_features.py`, CLI-held like
  `toolkit.FEATURE_FILES`. The toolkit cannot carry it: a game pinned at a public
  toolkit would not have the table until the next round.
- **One row per feature, with four probes:**
  - `toolkit`: a file the pinned toolkit must have; a toolkit predating the
    feature is a gap.
  - `stage`: the game's CMake sources call the staging function, or the toolkit
    stages by itself (a marker in the toolkit file).
  - `config`: a key in `packaging/config.default.toml`, commented rows counting.
  - `readme`: a line in the game's README's mods table.
  Each probe is data: a path and a pattern.
- **Applies to:** games that build the enhancements layer
  (`manifest.builds_enhance`); otherwise not applicable.
- **Surfaces:** `<game> features` prints a row per feature and exits 1 on a gap.
  The gaps also feed `layout.report` problems, so `doctor` shows them without
  changing its status and `public audit` and `export` refuse them, as with every
  other layout problem. `notes/build-all.sh` prints a report line that never
  fails the build, so a parked game on an old CLI (Spartan) cannot break it.
- **No waivers.** A game that truly cannot have a feature does not exist yet;
  add the mechanism with the first one.

The built exe is not probed: whether librashader arrived depends on a host
(offline configure has none), and the Windows verification covers it.

## Off the box: the bench ship and the build-host pull

The bench used to ship and pull the flat files beside the exe only. A run on a
bench host therefore had `librashader.dll` but no `shaders/`, and the Shaders
page showed the preset as missing. The shared layer has to work wherever the
exe runs, so the CLI fix is part of this change rather than a separate item:

- the PC build script emits `shaders/...` with its sha256;
- `buildhost pull` mirrors the directory, removing presets that are gone;
- `bench ship` sends each subdirectory on its own;
- `ship.ps1` seeds and removes stale files recursively under `shaders\`.


## docs/env.md

The toolkit's `RECOMP_PRESENT_SHADER` keys live in the toolkit's `recomp_env.h`.
A game's `docs/env.md` states it lists only that game's own keys, so the games
that gain shaders add no rows, and SSX 3, Burnout 3 and Quantum Redshift need no
new file. BLiNX 2's env.md predates that rule and keeps its rows.

## Screenshots

README images are curated, taken fresh and approved by the user before a public
push. This change attaches its comparison pairs to the tracker and adds no image
to any README.
