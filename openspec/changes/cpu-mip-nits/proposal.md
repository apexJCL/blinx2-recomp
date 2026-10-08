## Why

TASKS.md lists three nits from the Fable review of the CPU mip/LOD merge (toolkit 2736fda), to do after the upstream merge:

1. `nv2a_pb_exec.c`: exclude volume textures from mip selection, because `nv2a_tex_level_offset` assumes a 2D chain.
2. The CPU texture cache key includes `levels`, so level 0 is cached once per level count.
3. `recomp_env.h`: move `PB_MIPS` next to `PB_BILINEAR`.

All three are already on the integration branch. Toolkit 6721c18 (`pb_exec: CPU mip nits (volume textures, cache key, PB_MIPS row)`) landed through 4ec9f0a (`Merge nits/toolkit: CPU mip nits, D3D11 FPS title, seed_from_log, docs`). It is an ancestor of `posix-host/portability` a10f6d8, which the 2026-10-07 public round published and cat pins. Its state at a10f6d8:

- **Nit 1: done and tested.** `nv2a_stage_decode` fills `struct nv2a_stage.dims` from FORMAT's DIMENSIONALITY bits [7:4]. `stage_mip_build` keeps a stage with `dims == 3` on level 0, the same way it already treats cube maps. The `tests/nv2a_tex` ctest decodes a 2D, a 3D and a cube FORMAT and checks `dims` and `cube`.
- **Nit 2: done, not tested.** `tc_bind` matches an entry on offset, format, width, height and pitch, with no level count in the key. An entry that holds at least the requested levels serves the bind. Level 0 comes first in its layout, so the same entry serves a level-0 bind. An entry with fewer levels is rebuilt in its own slot, so no second copy of level 0 exists. The fingerprint and the written-since check cover every level the entry holds (`tc_extent(t, e->levels)`), so a rewrite of any level drops its decoded tiles, even when the current bind asks only for level 0. No test covers any of this. The texture cache is file-static in `nv2a_pb_exec.c`, so `tests/nv2a_tex` cannot reach it.
- **Nit 3: done.** The `PB_MIPS` row sits right after `PB_BILINEAR`. The "appended" comment is gone, because the key ids are compile-time only. cat's `docs/env.md` already lists `RECOMP_PB_MIPS` right after `RECOMP_PB_BILINEAR`. Both rows' source references are stale, though: they cite `nv2a_pb_exec.c:2590` and `:2679`, and the readers are now at :2690 (`pb_bilinear`) and :2707 (`pb_mips`).

The TASKS entry is therefore stale. The one gap left is a test for nit 2: the task brief says each fix gets a ctest where it can stand alone.

## What Changes

- **toolkit:** a new CPU-only ctest, `tests/pb_tex_cache`, drives `nv2a_pb_exec_method()` with a hand-written method stream, the way `nv2a_backend_smoke` does, with no GPU backend and no skip. It checks that the level-count-free key stays correct when mip data differs (see design D2). It changes no runtime code, except possibly one read-only stats accessor for the test (design D3).
- **cat:** update the two stale source references in `docs/env.md`, and move the TASKS entry to Done. The Done entry cites 6721c18 and 4ec9f0a and the new test's sha.
- No change to rendering, so no change to goldens or raster time (design D4).

## Capabilities

### Modified Capabilities
- None. This change adds test coverage and fixes docs for behaviour that has already merged.

## Impact

- toolkit: `tests/pb_tex_cache/` (new: `CMakeLists.txt`, `test_main.c`), built from `src/d3d/CMakeLists.txt` on POSIX hosts. `nv2a_pb_exec_tc_stats()` is declared in `nv2a_pb_state.h`.
- cat: `docs/env.md` (two cells), `TASKS.md`.
