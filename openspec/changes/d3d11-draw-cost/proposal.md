## Why

BLiNX 2's 1-2 barricade intro and city view issue about 10,000 batches and
200,000 methods a flip. On the Deck (D3D11 on DXVK under Proton) the walker
took 28.7 ms of the 33.3 ms frame: 18.5 ms in the backend's `on_draw`
(1.87 us a batch) and 9.6 ms decoding methods. Frames ran at 29.1 fps, with
a p90 of 38 ms and 4.5% over 40 ms. The draw count is real game
work, so the cost is on our side. Metal on the Mac takes about half as long
for the same view.

## What Changes

Phase 1 (toolkit `perf/deck-draws`) removes the redundant per-batch
work:

- **The c[] write generation.** The executor bumps
  `nv2a_pb_vsh_consts_gen()` at every write of the vertex constants.
  D3D11 skips its 3 KB `memcmp` of c[] while the generation is unchanged
  since its last upload. Under Proton that compare cost 2.1 ms a flip,
  because Wine's `memcmp` works 8 bytes at a time. 94% of batches now skip
  it.
- **The output merger in the state shadow.** `OMSetRenderTargets` and
  `OMSetDepthStencilState` are called only when the target, depth view,
  depth state or stencil reference changes. Before, every batch made both
  calls: 2.1 ms a flip, down to 0.2 ms.
- **The per-batch clock reads.** `draw_primitive` read the clock twice a
  batch for the `[PB-PERF]` draw share even when nothing printed it. These
  reads are now taken only under `RECOMP_FLIP_LOG`. Under Wine they cost
  about 4% of the walker's time.

Phase 2 (not in this change) is the rest of the per-batch cost. See
design.md for what it is and what each step is worth:

- Native vertex formats for `S32K` (short, not normalised) and `CMP`
  (packed 11:11:10). These are expanded on the CPU to float4 today, about
  2.5 MB a flip and 1.7 ms of `fetch()`. They need shader-input changes in
  the HLSL and MSL generators.
- A memo for `setup_pixel`'s per-stage loop and its `build_stages`, about
  3.5 ms a flip together.
- The method decode (about 50 ns a method under Wine, about 10 ms a flip).
  This is shared with Metal and with JSRF's heavy views.
- Metal mirror (backends agree): Metal sends c[] with `setVertexBytes`
  (3 KB) every batch. It can use the same generation.

## Impact

- Toolkit: `nv2a_pb_exec.c`, `nv2a_pb_state.h`, `nv2a_pb_d3d11.c`, new
  ctest `tests/pb_vsh_cgen`.
- No new env keys. The skips follow the existing `RECOMP_D3D11_MEMO`
  switch, and `=0` turns them off for A/B.
- No change to output: each skip leaves the GPU state as the full path
  would.
