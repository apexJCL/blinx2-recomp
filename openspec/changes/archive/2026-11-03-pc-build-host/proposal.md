## Why

Every Windows exe is cross-built on the Mac with llvm-mingw today: the
post-merge exe for the Deck, `notes/build-all.sh`'s Windows leg, and the
test-install packages. A BLiNX 2 Windows build takes about 16 minutes at 8
jobs there, and it holds the Mac lock that the Metal goldens also need. The
Windows PC (`bench host-win`, Windows 11, 16 cores) sits idle between runs.

The user (2026-10-28): "do all the windows/proton builds on the windows
machine, just to test things are still working and stable". The tracker item makes
the PC a native build host whose exes feed the Deck (Proton), the PC's own
runs and the test-install packages.

## What changes

- CLI (`xboxrecomp-cli`, `feat/pc-build-host`): a new bench setting,
  `BENCH_BUILD_HOST`. When it is set, the step that `BENCH_BUILD=local`
  ran on this machine (`xbr build windows`) runs on that Windows host
  instead:
  - The controller sends the game, toolkit and CLI trees as git bundles. A
    bundle is incremental against the commits the host already has. gen/
    goes as a tarball, and only when it changed.
  - The host checks the trees out under `BENCH_BUILD_DIR/<slug>`. It runs
    `xbr setup --no-toolkit`, which fetches the game's pinned, sha256-checked
    llvm-mingw, CMake and Ninja into user space. Then it runs `xbr build
    windows` under the PC's `.bench-lock`.
  - The controller pulls the exe and runtime files back, checks each
    sha256, and puts them in `<windows build dir>/build-host/`.
  - `ship`, `run`, `golden`, `integrate` and the Deck paths take that exe
    unchanged. The provenance file names the build host.
- New verbs:
  - `bench buildhost build`: the build alone.
  - `bench buildhost run ARGS... [--pull REL]`: any CLI command on the host
    tree, such as `package windows`, with its output pulled back. It makes
    test-install packages from a PC-built exe.
- New settings: `BENCH_BUILD_DIR`, `BENCH_BUILD_LOCK`, `BENCH_BUILD_CLI`
  and `BENCH_BUILD_GAME_FILES` (the PC's own game files, linked into its
  tree by a junction for `package`). Each has a `bench --help` row; the
  doctor names the build host.
- `package --stale-gen-ok`: package gen/ as it is. `buildhost run package`
  adds it, because the build host has the Mac's gen/ but not the analysis
  that keys it, and would otherwise regenerate gen/ there without the
  Ghidra export, into different code.
- No change to the game repos, the toolkit or the generated code. The cat
  side is this spec. The CLAUDE.md and `notes/build-all.sh` changes are
  drafted for the orchestrator.

## What does not change

- The Mac still regenerates gen/: analyze and recomp need the analysis
  cache and the game files, which the build host never gets. It also still
  makes the Metal build.
- The Deck never compiles. It still gets only the exe and the changed
  runtime files, now from the PC's build.
- The Mac cross-build stays available: leave `BENCH_BUILD_HOST` unset.
