## 1. Repro and proof (before the fix)
- [x] 1.1 `@hub-stage1` preset: `@story-hub`, then the route from the hub into stage 1-1. Confirm the log shows the hub's 512x512 targets created before `stg0101` opens.
- [x] 1.2 A `RECOMP_TRACE=metal` line per decode sync (target address and size, texture offset and bytes, flip), so each of the repro's "2 decode syncs" names its target. Metal 1x and 3x headless runs on the integration build: `mem_dump` of 0x0169D000 and 0x0119B000 at stage start and after the first decode sync; frame dumps on the plates and barrels. The CPU path on the same route gives the reference frames and the reference dump of both blocks at the same flip. Record the `cmp -l` counts and whether the second Metal dump holds the hub image.
- [x] 1.3 Identify what stage 1 keeps in both ranges (texture offsets from `RECOMP_TRACE=tex=2` on the CPU path, vertex attribute offsets, and a `watch` on a word in the block to see which code writes it). Record whether the overwritten bytes are rendering data only or game state (water plates, collision), and so whether the water jitter can come from this change at all.

## 2. Shared helper and test
- [x] 2.1 `nv2a_backend_common.h` and `.c`: `struct nv2a_rt_own`, `nv2a_rt_own_reset()`, `nv2a_rt_own_drawn()`, `nv2a_rt_own_stale()`; addresses through the low 27 bits, ranges clamped to the memory window.
- [x] 2.2 ctest `tests/rt_alias` (POSIX and Windows): a buffer stands in for guest memory. A target drawn this flip is never stale; one not drawn and unchanged is kept; one whose bytes changed anywhere in pitch x h (first byte, last byte, a middle row) is stale; a rewrite to the same bytes is kept; a reset after a write-back makes the new bytes the reference; it rehashes at most once per flip (count the hash calls); a range at the top of the window does not read past it.

## 3. Metal
- [x] 3.1 `surface()`: reset ownership at creation from the seed's bytes; on reuse of a target not drawn this flip, check and drop a stale one (recreate it); retire overlapping targets (write back if unchanged, drop if stale), before the seed read.
- [x] 3.2 `rt_texture`, the `tex_bind` decode sync, `rt_free` and `metal_sync_guest`: skip and drop stale targets, and never `rt_sync` a stale target. `guard_open()` before hashing guarded pages.
- [x] 3.3 Reset ownership after each `rt_sync` (the flip write-back included); set `draw_flip` in `begin_pass` and on clears.
- [x] 3.4 `RECOMP_DEBUG=rt_alias_check=0` through `recomp_env`, a row in `docs/env.md`, the drop log line (first 20, with the reason) and the "stale drops" count in the present summary; a `metal_prof` row for hash time.
- [x] 3.5 `tests/nv2a_backend_smoke`: draw into a target, flip, rewrite its guest bytes, sample it: expect the new texels and no write-back; draw, flip, leave the bytes, sample: expect the rendered image (render-to-texture still works); create a target overlapping a dirty unchanged one: expect one write-back and the seed to show it.

## 4. D3D11
- [ ] 4.1 The same in `surface()` (reuse check, overlap retirement, which on D3D11 only drops, since it never writes back) and `rt_texture`, under the same key.
- [ ] 4.2 `d3d11_backend_smoke`: draw into a target, rewrite its memory from the CPU, sample it: expect the new texels; the render-to-texture case unchanged.

## 5. Gates
- [x] 5.1 Mac build, POSIX ctests (including rt_alias and nv2a_backend_smoke), Metal goldens (attract, stage1, story) unchanged.
- [x] 5.2 Task 1.2 rerun: the Metal dumps match the CPU dump, no decode sync on the stale target, and the plates and barrels match the CPU frames at 1x and 3x.
- [ ] 5.3 Water: rerun the water spot (user, or a preset if 1.3 finds one) and record whether the jitter is gone; if 1.3 found only rendering data in the blocks, record that the jitter is a separate issue for TASKS.
- [ ] 5.4 Proton (ask before taking the Linux/Proton queue): llvm-mingw build, d3d11_backend_smoke, `blinx2 bench golden`.
- [x] 5.5 Metal `metal_prof` hash cost and flips/s before and after on stage1 3x and on `@hub-stage1` (flag a 25% drop in flips/s or a 1.5x rise in raster ms); decide on the row-sampled hash from the numbers.

## Results (Mac, 2026-10-06; runs in runs/rt-alias/)
- 1.1 `@hub-stage1` reaches stage 1-1 from the hub by poking the hub's scene switch (the drill flags [0xEC4CF8]/[0xEC4CE0] cleared, else the loader picks mgtu_ts). Hub targets made at t~66 s, stg0101 at ~82 s, checkpoint at ~102 s.
- 1.2 Before (rt_alias_check=0): the user's "2 decode syncs" at the stage's first texture binds, targets 0x0119B000 (texture 0x81184C80 DXT1 512x512) and 0x0169D000 (texture 0x816B8000). Dumps of the contiguous window 0x81190000 in play against the CPU path: 994438 of 1048576 bytes differ in the 0x0169D000 MB and 28684 of the texture tail at 0x0119B000; after the fix, 0 and 0 (`memcmp.py cpu2 mb2 ma2`). Frames: barricade, cliffs and start pad are garbage before, right after (before_after.png).
- 1.3 What stage 1 keeps there (CPU path, tex log and dumps): about 55 DXT1/DXT3 stage textures fill the 0x0169D000 MB; the 0x0119B000 MB holds the tail of a 512x512 DXT1, the stage's two 256x256 water targets (drawn every flip) and zeros. No game state. The earlier "floats" reading came from the low-window VA, not the surface's contiguous memory. Verdict: the write-back corrupts textures only and cannot cause the water jitter; the jitter also shows on D3D11 (Steam Deck), which never writes guest memory, so it is a separate, backend-independent issue for TASKS.
- 5.1 POSIX ctests pass (rt_alias new; nv2a_backend_smoke with the new cases, and its `noalias` run shows they fail without the check). Metal goldens attract, stage1, story CLOSE/pass.
- 5.5 `@hub-stage1` at 3x, metal_prof: ownership hashes 0.16-0.17 ms/flip, on_flip 1.56-1.59 ms against 1.58-1.61 with the check off; same flip count in 150 s. The full hash stays.
- Deviations from the design: (a) the hash reads the resolved address (the contiguous window, where the seed and write-back go); only address compares use the low 27 bits. Hashing the low-window VA hashed the XBE's D3D section under the front buffer and dropped it every other flip. (b) A reset (creation, write-back) does not count as the flip's check: a title write later in the same flip would be missed (the smoke test's pattern fill showed it), so the bound is one check per flip plus one after each reset. (c) D3D11 marks a target drawn when surface() hands it out, so the target of the batch being drawn is never dropped mid-draw. (d) Front buffers are dropped when the title reallocates and clears them at scene changes (2-4 per run), as the risks section expects.
- Open: 4.2 d3d11_backend_smoke cases are written (syntax-checked with llvm-mingw; the smoke now commits its surface memory, since the backend reads it), 4.x and 5.4 wait for the Linux/Proton queue; 5.3 is moot (water is not this change).
