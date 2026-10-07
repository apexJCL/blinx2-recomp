## Context

The walker collects a primitive's indices between `SET_BEGIN_END(prim)` and `SET_BEGIN_END(0)` into `s_gpu.idx[NV_MAX_INDICES]` (`uint16_t`). Four methods can feed it:
- `ARRAY_ELEMENT16` (0x1800) carries two 16-bit indices per word. The XDK's `DrawIndexedVertices` sends its whole index list this way, across as many method headers as it needs.
- `ARRAY_ELEMENT32` (0x1808) carries one index per word. The XDK uses it for the last index of an odd count. The walker has no case for it: the word goes to `note_unhandled` and the batch is one index short.
- `DRAW_ARRAYS` (0x1810) carries runs of start (24 bits) and count (8 bits, so at most 256 per word), expanded into consecutive indices.
- Inline and immediate vertex data are sized against `NV_MAX_INLINE` and then indexed `0..count-1`. The inline path drops a batch with more than `NV_MAX_INDICES` vertices outright (`count > NV_MAX_INDICES` goes to `out`). At the new cap that branch is unreachable: 65536 inline dwords hold at most 65536 vertices.

At END the batch goes to the backend's `on_draw` with `idx` and `idx_count`. The CPU fixed-function rasteriser walks `idx[]` directly. The CPU program path transforms every index into a static `XfVert xv[NV_MAX_INDICES]` (120 bytes each). Metal and D3D11 find `lo`/`hi` over the indices (initialised to `0xFFFF`, fine for 16-bit indices), expand the primitive into a triangle, line or point list with `nv2a_prim_to_list` into a static `uint32_t idx[NV_MAX_INDICES * 3]` (the fan and quad-strip cases produce up to `3n - 6`), copy vertices `lo..hi` into a vertex ring (Metal 16 MB, D3D11 8 MB) and the list into a 32-bit index ring (Metal 4 MB, D3D11 1 MB), and draw with 32-bit indices. Both ring allocators return NULL for a request larger than the ring, and the draw is then counted as skipped and dropped.

At the old cap of 4096, `ARRAY_ELEMENT16` and `DRAW_ARRAYS` stopped appending, and nothing was logged. `NV_MAX_INLINE` already went through the same fix (4096 to 64K, upstream 5c3a42c, "a batch past it was cut short with no sign").

### What the NV2A does

xemu's `nv2a_regs.h` documents the measurements behind its `NV2A_MAX_BATCH_LENGTH`: an Xbox 1.0 accepts a batch of at least `0x0FFFFF` elements; retail games send at least `0x410FA` (266,490) elements in one draw; a `DRAW_ARRAYS` start above `0xFFFF` raises an exception. xemu's cap was `0x1FFFF` until a retail title overran it, and is `0x07FFFF` now (`inline_elements` is a `uint32_t` array of that size; `ARRAY_ELEMENT16`, `ARRAY_ELEMENT32` and inline vertices all `assert` against it). Its `DRAW_ARRAYS` runs are kept separately, up to 1250 of them, which expanded is at most 320,000 indices and fits under the same cap.

Two things follow. The hardware sets no index limit a title would ever meet, so any cap here is ours and must sit above what titles are known to send. And vertices are 16-bit: a batch may reference at most 65536 distinct vertices, which bounds the vertex rings, while the index count is bounded only by the cap.

### Evidence (runs/horizon/)

| Run | What it shows |
|---|---|
| `lh-metal1/` (Metal, flip 2490) | the split reproduced: cyan to y ≈ 180, dark sea above (`view/before-2490.png`) |
| `lh-cpu1/` (CPU, `px` and a temporary vertex probe) | the pixels under the edge are written by two `prim 8, n 4096` batches; the near 7-strip and the far 191-strip only show where those quads are missing |
| `lh-cpu2/` (CPU, every vertex of the 4096 batches) | 28 quads per row, 36 full rows plus 16 quads, rows from y = 3872 up to y = 182; 704 of the 1024 quads are entirely off-screen |
| `watch1/` (Metal, `watch=0xF2A834`) | the game's quad-list count is `0x11F0` = 4592 indices |
| `lh-metal-fix/` (Metal, cap 65536) | cyan water to the horizon (`view/fix-2490.png`), as in xemu (`runs/stage1-water/frames/xemu_sea.png`) |
| `golden-fix/`, `golden-fix.txt` | Metal attract, stage1 and story: every frame CLOSE, golden exit 0 |

The temporary vertex probe (`px_verts=N` on the CPU path: every transformed vertex of each N-vertex program batch in the `px` flips) was not kept. It reused the D3D11 `px_verts` key with a new meaning. If it is wanted later, it should get its own key and a row in `docs/env.md`.

### Occlusion, ruled out

`Begin/EndVisibilityTest` are `sub_002E1C80` and `sub_002E1D20`, and `GetVisibilityTestResult` is `sub_002E0D20`. The game code calls them from:
- `sub_00040F30` and `sub_00041100` (proxy quads), with the result read in `sub_00040AB8`. The result is the visible fraction `count / area`, clamped to 1, and it scales the flare and glow sprites.
- `sub_00046CE0` (a screen-space quad around a projected point), with the result in the table `0x9FB930` and read by the player code `sub_00022DB0` (`count < threshold` skips it).

No sea or water draw reads either table. `metal_occ=fixed` makes every glow full strength, which is the extra cyan in `runs/stage1-water/frames/occ_cmp.png` (time-crystal glows), and it makes every player "visible", which changes game logic. The occlusion count semantics question (what is counted, scale, depth test) is therefore not on this bug's path. The NV2A comparison stays open as general fidelity work.

## Decisions

### D1: a fixed cap of `0x80000`, sized from the hardware evidence

Three shapes were weighed.

**Split-on-full** (draw what is collected, then carry on in a new batch) never drops anything, but it needs per-primitive carry rules: a list splits at a whole primitive (a multiple of 3 for triangles, 4 for quads, 2 for lines); a triangle or quad strip carries its last two vertices and splits at an even point so the winding parity holds; a fan or polygon carries its first and last vertices; a line strip carries one vertex and a line loop carries its first and closes at END. Each backend would then see one guest draw as several, which changes the per-draw counters and gives a visibility test more than one draw per batch. It is the right tool for a title that outruns any cap, and no such title is known: the largest retail batch on record is half of xemu's cap.

**Growing `idx` on demand** removes the cap but makes `idx` a pointer in a struct that `pb_vsh_ab` copies by value and that `nv2a_pb_gpu_state()` exposes to the backends and the smoke tests. A shallow copy would be correct today (the raster never writes `idx`), but it is a trap for the next reader, for a saving of 1 MB.

**A fixed cap** is one constant, follows the `NV_MAX_INLINE` precedent, and costs nothing per draw. The prototype's 65536 was justified as "16 times the largest batch seen" and as "one 16-bit index range", but the second is a vertex bound, not an index bound, and the first is now known to be short of a real title by a factor of four. The cap is therefore `0x80000` (524,288): xemu's `0x07FFFF` as a power of two, which also holds the largest `DRAW_ARRAYS` expansion xemu allows. D2 makes any residual overflow visible, and the `max` counter says how close a title comes. If a title ever reaches it, split-on-full is D3.

### D2: report overflow once, count it, and keep the high-water mark

`note_idx_overflow()` prints `[GPU] index batch over N indices: the rest is dropped` the first time an index is refused and counts each refused word or run (`s_idx_overflow`), mirroring `s_inline_overflow`. `draw_primitive` records the largest `idx_count` seen (`s_idx_max`). The periodic `[GPU]` summary (`nv2a_pb_exec_report`, every `RECOMP_PB_REPORT_MS`, default 10 s, while the NV2A trace is on) prints `index batches: max M, N overflowed` next to the draw and index totals, so a Burnout 3 or BLiNX log answers whether the title ever needed more than 4096 (or more than the new cap) without a probe. A `DRAW_ARRAYS` start plus count past `0xFFFF` is counted too (`s_idx_start_hi`) and printed on the same line when non-zero: the hardware raises an exception on such a start, so a non-zero count points at a decode bug in the walker or an upstream title doing something the Xbox would not have survived.

### D3: `ARRAY_ELEMENT32` is decoded

One case next to `ARRAY_ELEMENT16`: with `s_gpu.prim` set and room for one index, append `(uint16_t)param`; otherwise `note_idx_overflow()`. The truncation to 16 bits is the hardware's own vertex range (D1). The method was not in the top-10 unhandled ranking of the BLiNX 2 runs, which is weak evidence (the ranking shows ten methods unless `pb_unhandled_all` is set), and the cost of the case is six lines, so it goes in now rather than waiting for a title whose last triangle is missing. The smoke scene pins it (D5).

### D4: per-index scratch on the heap, rings sized to the cap

At `0x80000` the static per-index arrays would be 60 MB on the CPU path and 6 MB in each GPU backend. Untouched BSS costs no resident memory, but it inflates every binary's reported size, the iPad build's headroom check (`ipados-self-build-only`) and the `pb_vsh_ab` copies for no benefit. So `xv` and the two expansion lists become `static` pointers with a capacity, reallocated to `idx_count` (or `3 * idx_count`) when a batch exceeds it, which happens once per high-water mark. A failed realloc skips the draw and counts it, the way a failed ring allocation already does.

The index rings are sized so an accepted batch always fits: `3 * NV_MAX_INDICES * 4` = 6 MB on both GPU backends (from 1 MB on D3D11 and 4 MB on Metal). The vertex rings stay as they are. Their bound is the 16-bit vertex range, not the cap: 65536 vertices as float4 streams are 1 MB per stream, and a batch using more streams than fit falls back to per-stream mapping on D3D11 and to a flush on Metal, as today.

### D5: the smoke scenes assert pixels, not only agreement

`nv2a_backend_smoke` and `d3d11_backend_smoke` compare the CPU rasteriser against a GPU backend fed the same method stream. Both read the walker's `idx[]`, so a truncated batch gives two identical, equally wrong frames and a pass. The new scenes therefore also check absolute colours: a grid of small pre-transformed quads (vertex arrays in guest memory via `SET_VERTEX_DATA_ARRAY_FORMAT`/`_OFFSET`, as the D3D11 smoke's existing scenes set up; indices via `ARRAY_ELEMENT16`) with one colour below index 4096 and another from index 4096 on, and a pixel read inside a quad past the cut; and a triangle list whose last index arrives as `ARRAY_ELEMENT32`, with a pixel read inside the last triangle. Both fail on the old walker (one by colour, one by a missing triangle).

### D6 (follow-ups found on the way)

- **Split-on-full** stays a follow-up (D1), gated on the `max` counter ever approaching the cap.
- **The grid wastes 704 of its 1024 quads below the screen.** That is the game's own design (xemu runs the same code). It stops mattering once the whole batch draws.
- **32-bit indices** are not needed: the hardware rejects a start above `0xFFFF` (D2 counts it instead).

## Risks

- **Memory.** 1 MB more in `s_gpu` and 2 MB in each of its two `pb_vsh_ab` static copies (debug A/B only); 2 MB more of index ring on D3D11, 2 MB on Metal. The per-index scratch is what the run's largest batch needs. BLiNX 2 at 4592 indices: about 540 KB on the CPU path, 55 KB per GPU backend.
- **Behaviour moves.** Any batch that was being cut now draws whole, and an odd-count indexed draw gains its last primitive. In BLiNX 2 the known case is the water grid. Goldens on all three paths decide whether anything else moved, and a moved golden is compared with xemu before it is re-blessed. The `max` counter in each golden log says whether any other batch was over 4096.
- **The toolkit branch is behind `posix-host/portability`.** The prototype (eb36251) branched before 4773a01 (D3D11: one render target per surface). The D3D11 goldens have to run on a tree with both, so the branch merges `posix-host/portability` first (task 0.3).
- **Burnout 3.** The upstream reference title may also have had batches over 4096; the `max` counter on its summary line shows it (`index batches: max M`). A change there is expected to be an improvement, and a race is compared with the pre-change run. Per the memory note `upstream-burnout3-gate`, this is a gate for the upstream PR set, not for the fork merge.

## Validation

- Before and after on the lighthouse warp, Metal, flip 2490: `runs/horizon/view/before-2490.png` and `fix-2490.png` (65536 prototype; the final cap re-runs it).
- Metal goldens on the Mac: `runs/horizon/golden-fix.txt` (prototype), re-run on the final branch.
- POSIX ctests (Mac): `nv2a_backend_smoke` (with guard and noalias), `nv2a_zbuf`, `render_scale`, `nv2a_vsh`, `nv2a_combiner`, `rt_alias`, `nv2a_tex` pass on the prototype; the new scenes are added and run.
- Still to run: D3D11 goldens and `d3d11_backend_smoke` under Proton (`blinx2 bench golden`, `blinx2 bench tests`), the CPU-path stage 1 horizon frame, and the Burnout 3 race under Proton with the `max` counter read from its log.
