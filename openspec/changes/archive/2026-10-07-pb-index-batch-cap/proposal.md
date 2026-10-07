## Why

In BLiNX 2 stage 1, the translucent cyan water near the shore ends in a hard edge, and the dark-green far sea shows above it. The edge is horizontal and steps up a few pixels at about 59% of the screen width, like an S. xemu shows cyan water all the way to the horizon. The split shows on Metal, on D3D11 (the Deck) and on the CPU path. The spike `stage1-water-spike` narrowed it to shared guest-visible state and named the occlusion queries as the lead. This change replaces that lead with the actual cause. Raw runs are in `xbox-recomp/runs/horizon/`.

- **The cyan layer is one quad-list draw.** At the lighthouse warp (`runs/stage1-water/scripts/warp_lhp.txt`, flip 2490, CPU path), the pixels below the edge are written by two `prim 8` (QUADS) batches of exactly 4096 vertices each. These are the same grid drawn twice with different texture coordinates. The near patch (7-vertex strip) and the far sea (191-vertex strip) only show through where those quads are missing.
- **The grid is cut at 1024 quads.** The vertex probe (`runs/horizon/lh-cpu2/`) shows a camera-facing grid of 28 quads per row. Its rows start far below the screen (y = 3872) and climb toward the horizon. The batch holds 36 full rows and then 16 quads of the 37th, at y ≈ 182. That partial row is the step in the edge, and its top is the edge.
- **The game asked for 4592 indices.** `sub_00219DC0` (`0x0021A790`) draws the grid with `DrawIndexedVertices(D3DPT_QUADLIST, [0xF2A834] & ~3, ...)`. A write watch on `0xF2A834` (`runs/horizon/watch1/`) shows that the game sets the count once, to `0x11F0` = 4592 indices (1148 quads).
- **The walker drops every index past 4096.** `NV_MAX_INDICES` is 4096 (`nv2a_pb_state.h`). `NV097_ARRAY_ELEMENT16` and `NV097_DRAW_ARRAYS` stop appending at that cap, and nothing is logged. The last 496 indices of the batch (124 quads: the other 12 of row 37 and four more rows) are lost. They are the farthest rows, which reach the horizon. All three backends draw the walker's `idx[]`, so all three show the split.
- **Occlusion is not the cause.** The game uses visibility tests for two things only: the sun flare and glow sprites (`sub_00040F30` draws them, `sub_00040AB8` reads them; the result scales the glow) and point visibility of players and objects (`sub_00046CE0`, read by the player code `sub_00022DB0`). Neither draws the sea. `metal_occ=fixed` brings back cyan *glows* (the time crystals), not water. Forcing every result visible also changes player logic, which is why the earlier `lh-fixed` run took a different path through the level.

With the cap raised (the prototype used 65536), the same Metal run (`runs/horizon/lh-metal-fix/f_flip_02490.bmp`, `view/fix-2490.png` against `view/before-2490.png`) draws cyan water to the horizon, as xemu does. The Metal goldens still pass.

### What the hardware allows

The cap has to be sized from the NV2A, not from this one grid. xemu's `nv2a_regs.h` (comment on `NV2A_MAX_BATCH_LENGTH`) records the measurements:

- On an Xbox 1.0, a batch of at least `0x0FFFFF` elements goes through without issue. There is no per-BEGIN/END index limit a title would notice.
- Retail games are known to send at least `0x410FA` (266,490) elements in one draw. xemu's own cap was `0x1FFFF` until such a title hit it; it is now `0x07FFFF`.
- `NV097_DRAW_ARRAYS` with a start above `0xFFFF` raises an exception on the hardware, so no retail title does it. The XDK's index buffers are 16-bit for the same reason: a batch can carry far more than 65536 *indices*, but never more than 65536 distinct *vertices*.

So 65536 would fix BLiNX 2 and still cut a known retail draw to a quarter. The cap goes to `0x80000` (524,288), xemu's bound rounded to a power of two, and the per-index scratch that would make that expensive stops being static.

## What Changes

- **`NV_MAX_INDICES` goes from 4096 to `0x80000`** (`src/kernel/nv2a_pb_state.h`), with the hardware and retail figures above in the comment. `s_gpu.idx` stays `uint16_t` (vertices are 16-bit on this hardware) and grows from 8 KB to 1 MB.
- **Per-index scratch is heap memory grown on demand, not BSS.** The CPU program path's `XfVert xv[NV_MAX_INDICES]` (120 bytes per index, 60 MB at the new cap) and the Metal and D3D11 `uint32_t idx[NV_MAX_INDICES * 3]` expansion lists (6 MB each) become `static` pointers reallocated to the batch at hand. A title that never sends a big batch never pays for one.
- **The GPU index rings hold one maximal batch.** `ring_alloc` (Metal) and `ring_map` (D3D11) return NULL when a request is larger than the whole ring, and the draw is then skipped with only a counter. The index rings go to `3 * NV_MAX_INDICES * 4` = 6 MB (D3D11 is 1 MB today, Metal 4 MB), so an index list the walker accepts is one the backend can draw.
- **`NV097_ARRAY_ELEMENT32` (0x1808) is decoded.** The XDK sends the last index of an odd-count `DrawIndexedVertices` as one 32-bit element. The walker treats it as unhandled, so such a batch loses its last index: the last triangle of a list, or the last quad. The fix is one case, the same shape as `ARRAY_ELEMENT16`.
- **Index overflow is reported.** A batch that still passes the cap prints `[GPU] index batch over N indices: the rest is dropped` once and is counted, the same way `INLINE_ARRAY` overflow already is. The walker also keeps the largest `idx_count` it has seen, and the periodic `[GPU]` summary line prints both (`index batches: max M, N overflowed`), so a log answers "did this title ever need more than 4096" without a probe. A `DRAW_ARRAYS` start above `0xFFFF` is counted on the same line: the hardware rejects it, so a non-zero count means a decode bug, not a title to support.
- **The backend smoke tests pin the cap and the 32-bit element.** `tests/nv2a_backend_smoke` (POSIX: CPU against Metal) and `tests/d3d11_backend_smoke` (Windows: CPU against D3D11, run under Proton by `blinx2 bench tests`) each get a scene with an indexed quad list of more than 4096 indices whose quads past index 4096 have their own colour, and a scene whose last index arrives as `ARRAY_ELEMENT32`. The comparison of CPU against GPU cannot see a truncation, because both read the same `idx[]`, so each scene also asserts the colour of a pixel inside a quad past the cut. Both scenes fail on the old walker.
- **Stage-1 horizon frame as a regression check.** The lighthouse warp at flip 2490 goes into the change's notes as the before/after pair. Promoting it to a golden is left to the golden owner, because the warp needs `poke` steps.

Out of scope: splitting an over-long batch into several draws (design.md D3). The cap is now above every batch the hardware is known to have been given, and the warning and the `max` counter make a residual visible, so split-on-full waits for a title that needs it. Widening `idx` to 32 bits is dropped as a follow-up: the hardware itself rejects a 32-bit start.

## Impact

- Toolkit: `src/kernel/nv2a_pb_state.h` (the cap), `src/kernel/nv2a_pb_exec.c` (the `ARRAY_ELEMENT32` case, the overflow note at the three index paths, the heap `xv`, the summary line), `src/d3d/nv2a_pb_metal.m` and `src/d3d/nv2a_pb_d3d11.c` (heap expansion list, index ring size), `tests/nv2a_backend_smoke/smoke.c` and `tests/d3d11_backend_smoke/smoke.c` (the new scenes).
- Behaviour: a batch that used to be cut is now drawn whole, and an odd-count indexed draw keeps its last primitive. Stock behaviour changes only where the old behaviour was wrong. No env key and no opt-in.
- Goldens: the three Metal scenarios pass on the 65536 prototype (`runs/horizon/golden-fix.txt`) and run again on the final cap. D3D11 under Proton and the CPU path still need to run.
- Memory: 1 MB more in `s_gpu` (plus its two static copies in the `pb_vsh_ab` debug path), 2 MB more of GPU index ring on D3D11 and 2 MB on Metal. The per-index scratch costs what the largest batch of the run needs (BLiNX 2: 4592 indices, about 540 KB on the CPU path and 55 KB per GPU backend), not what the cap allows.
- Performance: none per draw. Loops run to `idx_count`, not to the cap; the realloc happens once per high-water mark.
- Upstream: a title-agnostic walker fix. Burnout 3 runs on it under Proton before it joins the PR set (see tasks 3.3 and the memory note `upstream-burnout3-gate`); that run is not a gate for the fork merge.
