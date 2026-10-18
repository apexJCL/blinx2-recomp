## Context

The three nits already landed in toolkit 6721c18 (see proposal). This design covers only the missing test for nit 2 and the doc and TASKS cleanup.

`tc_bind(const Texture *t, uint32_t levels)` (`nv2a_pb_exec.c`, fast raster path) works like this:
- It looks up an entry by (offset, color, width, height, pitch).
- On a hit with `e->levels >= levels`, it reuses the entry. If the flip generation changed or the surface was written since the entry was last checked, it rehashes `tc_extent(t, e->levels)` bytes and clears `tile_ok` on a mismatch.
- On a hit with fewer levels, it rebuilds the entry in place with `levels` levels.
- On a miss, it takes the LRU victim.
- `s_tc_binds`, `s_tc_refp` and `s_tc_dropped` count its work. Today only the `RECOMP_DEBUG=pb_fast_ab` summary prints them.

## Decisions

### D1. A new ctest, not a case in nv2a_backend_smoke
`nv2a_backend_smoke` compares a GPU backend against the CPU rasteriser. It exits 77 (skipped) when the host has no backend, and its scenes are built around that comparison. The cache is CPU-path only. A separate `tests/pb_tex_cache` links `xboxrecomp`, runs the CPU path (`RECOMP_PB_BACKEND` unset, `pb_fast` on, which is the default), and never skips. It copies the few method-stream helpers it needs (surface, stage-0 texture setup, a quad, flip, and the pass-through vertex program from `d3d11_backend_smoke`) and does not share code with them. Only vertex-program batches take the path that mipmaps and caches (`raster_batch_vsh_one`, `fast_batch_setup`). Because it links `xboxrecomp`, it is wired into the toolkit build from `src/d3d/CMakeLists.txt` under `if(NOT WIN32)`, as `nv2a_backend_smoke` is, not as a standalone project.

### D2. What the test checks
Texture: A8R8G8B8, 16x16, 3 levels (16, 8, 4), swizzled. Each level is filled with a single colour: level 0 red, level 1 green, level 2 blue. The filter is MIN nearest-mip-nearest and MAG nearest, so each pixel takes one exact level colour and the checks need no tolerance.

1. **Mips used.** A screen quad 4x4 px in size maps the full texture, so its LOD is about 2: expect blue. A quad 16x16 px in size: expect red.
2. **Level 0 shared.** The same texture bound with `pb_mips`-equivalent level 0 only: MIN without a mip mode, so `stage_tc_levels == 1`. The same small quad must sample red, the level-0 texels from the 3-level entry. Check D3's entry count: no new entry was built.
3. **Mip data differs (the correctness side the brief names).** First, a flip with nothing changed: a level-0-only bind, then a mipmapped one that decodes level 2 (blue), and no drop. Then rewrite only level 2's bytes to yellow. In the next flip, draw the same two binds, level-0-only first. Expect red, then yellow, and one drop. The first bind already rehashes every level the entry holds, so the level-2 change must not survive behind a level-0 bind. Without the unchanged flip, rechecking only the requested levels would still pass: a hash over a shorter range always differs, so the drop happens anyway. The cache is only rechecked when FLIP_INCREMENT_WRITE advances the flip count, so the test's flip sends it before FLIP_STALL.
4. **Fewer levels first.** In a fresh texture slot, a level-0-only bind first, then a mipmapped bind. Expect the rebuild in the same slot (D3: entry count unchanged after the first build), then the right level colours.
5. **Different textures are not shared.** Same offset, different pitch or format: a separate entry, as before.

Pixels are read back from the colour surface in guest memory at the quad centres.

### D3. How the test observes entries
Pixel checks alone cannot tell "one entry" from "two entries that both decode level 0", and that difference is the whole point of nit 2. Options:
- (a) A read-only `void nv2a_pb_exec_tc_stats(struct nv2a_tc_stats *)` that copies the existing counters plus a count of live entries and builds. It costs nothing at runtime and is declared in `nv2a_pb_state.h`, the executor's header.
- (b) Parse the `pb_fast_ab` summary from stderr. This is fragile, and fast-AB doubles every batch.

Chosen: (a), as the orchestrator decided. Its entries, binds, builds and dropped counts come from `struct nv2a_pb_tc_stats`, and hits are binds minus builds. The hot path gains only `s_tc_builds++`, at a build.

### D4. Gates for a test-only change
No runtime code changes (D3's accessor only reads), so:
- Mac build with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`, and the POSIX ctests, the new one included.
- Goldens: the CPU and Metal goldens run once on the branch to show that nothing moved. They are cheap, and the brief asks for them. `./blinx2 golden --help` decides whether a CPU run is possible; CPU stage1 and story are skipped by design.
- CPU raster ms on one scene: recorded before and after for the record. Both sides are expected to be equal, because the runtime code is identical.
- The Linux/Proton host: `blinx2 bench tests` and `blinx2 bench golden` on "go", from the cat worktree pointing at the toolkit worktree.

## Risks

- Hand-built FORMAT and FILTER words for the test must match what `nv2a_stage_decode` reads. Mitigation: reuse the bit layout from the existing `tests/nv2a_tex` dims case, and assert that `stage_mip_build` engaged through case 1 (blue) before trusting cases 2 to 4.
- LOD at a 4x4 quad: if the rasteriser's LOD differs by rounding, case 1 may take level 1. Use 2x2 or 4x4 quads, and pick the size that gives an unambiguous level from the LOD formula in `stage_mip_build`'s consumer.
