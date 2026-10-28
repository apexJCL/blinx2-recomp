# Change: Keep the D3D11 backend's compiled shaders on disk

The D3D11 backend compiles every vertex program and
combiner shader it meets with `D3DCompile`, and nothing it compiles outlives
the process. Under Proton that compiler is Wine's `d3dcompiler_47`, at tens
of milliseconds a shader, so every launch pays the same compiles again,
mostly in one burst at the first 3D scene. This change stores each compiled
blob in a per-game directory beside the saves and hands it back the next
time the same source is compiled with the same compiler and flags.

## Why

- **The load gap is compiling.** In the JSRF title-scene bench on the Deck
  (`runs/bench-matrix/jsrf-title/deck/s1-dsp0-43/game-stdio.log`) the
  backend compiles 28 vertex programs in a run: 1 at present 1, **24
  between presents 2400 and 2700** (the load into the title scene, the
  `load_gap_ms` the bench matrix reports), and one each at 2700, 3000 and
  3600. The combiner count stays at 16. BLiNX 2's stage 1-1 shows the same
  shape (27 vertex programs inside its 875-890 ms first 3D frame,
  shader-precompile proposal).
- **The in-memory caches already work; the steady compiles are first
  sightings.** `s_vs` (`VS_MAX` 128, keyed by program hash, no eviction)
  and `s_rc` (`RC_MAX` 64, LRU) hold everything the title scene uses: no
  evictions happen in those runs, so the compiles after the load are
  programs the run had not seen yet, and only a cache that outlives the
  process removes them.
- **The bytes are the compiler's own.** A hit is the blob the same
  `d3dcompiler_47.dll` produced for the same source, target, entry and
  flags, so what is drawn cannot change; it only arrives sooner.
- **The shader-precompile change left this as its follow-up.**
  Its design defers a "DXBC blob store" with requirements (a compiler
  fingerprint in the key, a checked header since DXVK does not verify the
  DXBC checksum, unique temporaries with rename, a size cap). This change
  is that store, on its own, without the record list or the preload
  thread: it helps every launch after the first with no harvested list.

## What Changes

- **Toolkit** (`posix-host/portability`):
  - `src/d3d/shader_cache.c/.h`: a portable C11 store. The key is the
    compiler identity, target, entry, both flag words and the source; the
    entry file holds the whole key and is compared byte for byte, so a
    hash collision is a miss. Damaged entries are removed and compiled
    again; stores go through a unique temporary and a rename; a prune at
    open drops stale temporaries and keeps the directory under 64 MB.
  - `nv2a_pb_d3d11.c` `compile()`: load before `D3DCompile`, store after it;
    a hit becomes a blob through `D3DCreateBlob`. The compiler identity is
    the loaded DLL's path, size and write time. Counts and times appear in
    a `[d3d11] shaders:` line at present 1 and every 300th.
  - `xbox_path_hdd_root()` (kernel_path): the save root the backend puts
    its directory under, `<hdd>/ShaderCache/dxbc`, a name no guest path
    maps to.
  - `RECOMP_DXBC_CACHE` (Config tier): unset, `1` or `on` is the default
    directory; `0` or `off` turns it off; any other value is the directory.
  - ctest `shader_cache`: key fields, round trip, collisions, seven damaged
    entry shapes, failed stores and the prune.
- **cat**: the `docs/env.md` row for `RECOMP_DXBC_CACHE`.
- **Metal: nothing.** Its load gap is already 0.31-0.35 s on the M4 Max
  (macOS keeps a per-binary shader cache keyed by source and options, the
  shader-precompile measurements), and what is left there is the combiner
  MSL front end, which a blob store would not touch.

## Impact

- On by default: an exception to the CLAUDE.md opt-in rule that the user
  approved on 2026-10-23 (design D8). `blinx2 bench golden` leaves `RECOMP_HDD_DIR` unset, so its
  cache sits in the bench prefix's default save root: a first golden in a
  new bench tree starts cold and later scenarios hit what earlier ones
  stored; a second golden in the same tree runs warm throughout. Both pass
  (tasks 3.3). The bench matrix copies a fresh hdd per run, so it is cold
  unless a run points the key at a kept directory.
- The save root gains `ShaderCache/dxbc/` (a few MB). Installers and
  `--import-saves` treat the hdd directory as the player's; the cache is
  safe to delete at any time.
- No CLI change is needed. The launchers' `RECOMP_HDD_DIR` already gives
  each game its own directory.
