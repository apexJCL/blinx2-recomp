# pb-index-batch-cap: implementation notes

Branches `fix/pb-index-batch-cap`. Toolkit: off `posix-host/portability` 4773a01, with the prototype carried over as d43b654 and the implementation in ffb8a93. Cat: off `main` 3564cb4, with the spec (76e234b, Fable's pass b43bff5) and these notes. gen/ was not regenerated, because the lifter is unchanged between the prototype's base b0eb653 and 4773a01. Raw runs are in `xbox-recomp/runs/horizon/`.

## Where the implementation differs from the spec

- **D5: the D3D11 smoke had no vertex-array scenes to copy.** Its existing scenes are all `INLINE_ARRAY`. Both smoke tests therefore set up their own arrays: attr0 float4 and attr3 D3DCOLOR interleaved at a 20-byte stride, with `0x1720` offsets and the stride in bits 8 to 15 of `0x1760`. In the D3D11 smoke the arrays are at `VB_GUEST` 0x10200000 (VirtualAlloc). The D3D11 smoke has no CPU reference, so its index cases check pixels only, through `nv2a_pb_d3d11_pixel`.
- **D5: `elem32` uses axis-aligned rectangles.** The first version was three plain triangles. The CPU and Metal paths matched every probe but differed by 60 pixels along the slanted edges, and the POSIX smoke requires an exact match. The scene is now two rectangles of two same-coloured triangles each, plus a degenerate triangle that keeps the index count odd (15). The 15th index arrives as `ARRAY_ELEMENT32` and completes the green rectangle's bottom-left half, where the probe is.
- **Both new scenes were checked against the old walker** (cap 4096, no 0x1808 case). On the old walker, every probe past the cut reads the clear colour (0x603010), and the CPU and Metal frames still match exactly. That is the false pass D5 predicted.
- **`raster_batch_vsh_one` grows its scratch before counting the batch.** If the realloc fails, the batch is dropped and counted in `s_xv_fail`. The count prints on the summary line (`, N dropped for scratch`) only when it is non-zero, like the start-past-0xFFFF count.

## Gates

| Gate | Result |
|---|---|
| Mac build | ok |
| `nv2a_backend_smoke` (with guard and noalias) | 6 of 6 scenes identical, bigidx and elem32 probes pass on CPU and Metal |
| POSIX ctests `nv2a_zbuf`, `render_scale`, `nv2a_vsh`, `nv2a_combiner`, `rt_alias`, `nv2a_tex` | pass |
| cat `uv run pytest scripts`, ruff check and format | pass |
| Metal goldens (`golden-final.txt`) | exit 0, all 8 frames CLOSE |
| Metal horizon, lighthouse warp flip 2490 (`lh-metal-final/`) | cyan to the horizon, matches xemu |
| CPU horizon, the same warp (`lh-cpu-final/`) | cyan to the horizon, no `index batch over` |
| The Linux/Proton host Proton build and the 13 Proton ctests | pass; the `d3d11_backend_smoke` index probes pass |
| D3D11 goldens, `blinx2 bench golden` (`bench host-golden.log`) | pass: attract-cliff EXACT, the other 7 CLOSE |
| D3D11 horizon, the same warp (`lh-d3d11-final/d0041.png`, present 2461) | cyan to the horizon |
| Burnout 3 race under Proton, 900 s (`b3/20261006-221820-new-race/`) | reaches the race and renders it with the HUD, no [CRASH], `max 3909, 0 overflowed` |

Before/after sheet: `runs/horizon/view/horizon-before-after.png`. The top row is Metal before, Metal after and xemu. The bottom row is CPU before, CPU after and D3D11 after.

The attract-title Metal mae was 4.6 (limit 6.0, bad 0.13% against 0.20%). The prototype run had 1.9 and the batch merge 2.9, and D3D11 on this branch has 1.9. That spread is run-to-run drift on a frame whose sea is now drawn whole. Watch it if it recurs.

## `index batches` per run (task 2.3, 3.1, 3.3)

| Run | max | overflowed | 0x1808 in the unhandled list |
|---|---|---|---|
| Metal attract / stage1 / story | 4592 / 4592 / 175 | 0 | — |
| D3D11 attract / stage1 / story | 4592 / 4592 / 175 | 0 | 0 |
| CPU lighthouse warp | 4592 | 0 | — |
| Burnout 3 race (900 s) | 3909 | 0 | 0 |

The water grid is BLiNX 2's only batch over 4096, and it appears in the attract cliff scene too. Burnout 3 stays under the old cap and never sends `ARRAY_ELEMENT32`, so this change does not alter its rendering. No run counted a `DRAW_ARRAYS` start past 0xFFFF.

## Not run

- 2.7 Bench (flips/s and raster ms). The goldens' flip counts are in line with the prototype (Metal attract 2552 against 2631, stage1 3372 against 3444), but no bench was run.
- 3.3's before/after comparison for Burnout 3. Its max (3909) is under the old cap, so there is nothing to compare. The race is a single run on the new toolkit.
