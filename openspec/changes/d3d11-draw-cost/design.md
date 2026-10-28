## Measurements

All runs are on the Deck (D3D11 under GE-Proton11-7) with
`@stage1-2-barricade`, fullscreen, and the heavy flips only
(batches >= 8000). Each build shipped from the Mac.

Walker profile at 250 Hz, baseline, busy samples: `nv2a_pb_d3d11.c`
21.8%, `nv2a_pb_exec.c` 15.4%, DXVK `d3d11.dll` 14.5%, `memcmp` 8.6%,
`nv2a_backend_common` 12.7%, `nv2a_pb_scan.c` 7.2%, stderr I/O from the
flip trace 6.4%, `RtlGetSystemTimePrecise` and QPC 3.7%.

`on_draw` phases, from temporary rdtsc timers (ms a flip at about 10.1k
batches; the patch is kept in `runs/deck-draws/d3d11-instrumented.patch`):

| phase | stock | phase 1 |
|---|---|---|
| pre (indices, raster state) | 1.0 | 1.2 |
| vb (stream copy and expansion) | 3.6 | 4.1 |
| ib | 0.5 | 0.5 |
| consts (c[]) | 2.3 | 0.6 |
| bind (OM, blend, IL, VB, VS) | 4.0 | 3.3 |
| of which OM targets and depth state | 2.1 | 0.2 |
| pixel (`setup_pixel`) | 6.1 | 7.0 |
| vp, draw | 0.9 | 1.0 |

Some phases grew with the extra timers (11 more rdtsc a batch). The
`[PB-PERF]` numbers below have no timers.

`[PB-PERF]` medians, `RECOMP_TRACE=flip,pacing,prof=250,prof_delay=50` on
both:

| | stock | phase 1 |
|---|---|---|
| batches | 9907 | 9816 |
| wall ms | 34.4 | 33.4 |
| wall p90 / p99 | 38.1 / 51.3 | 36.0 / 51.3 |
| flips over 40 ms | 4.5% | 5.7% |
| walk ms | 28.7 | 26.4 |
| draw ms (us/batch) | 18.5 (1.87) | 15.5 (1.58) |
| decode ms | 9.6 | 10.2 |
| fps | 29.1 | 29.9 |

## Decisions

1. **A generation, not a dirty flag.** Several readers could consume a
   dirty flag (D3D11, Metal, a dump), and a reader that clears it hides
   the write from the others. Each reader keeps the generation it last
   saw instead. Equal means no write since then. Different says nothing
   about the bytes, so D3D11 still compares then, because a title often
   rewrites the same matrices.
2. **Every writer bumps it.** The writers are the TRANSFORM_CONSTANT
   window, the viewport offset and scale mirrors, the fixed-function
   matrix windows, `ff_begin`/`ff_end` (they swap in the fixed-function
   constants and restore them), the CPU vertex program's `cxt_write`, and
   the fast-path A/B restore of `s_vsh`. `tests/pb_vsh_cgen` checks the
   method writers and that other methods leave the generation alone.
3. **OM in the state shadow without a generation bump.** The context holds
   a reference to the views it has bound, so the address of a bound view
   cannot come back as a new object. Every other binder in the file (the
   CPU pixel probe, the present blit, the overlay, `swap_resize`) already
   resets the shadow, and `swap_resize` now does it too.
4. **Vertex-buffer slot caching was tried and dropped.** Binding only the
   changed slot range was slower than one 16-slot call (IA 1.2 to 1.7 ms):
   the offsets move every batch, so little is skipped, and the compare loop
   costs more than DXVK's bind.

## Phase 2 notes

- `[DV]` counters: the expanded streams are all `S32K` (type 5, about
  1.1 MB a flip) and `CMP` (type 6, about 1.4-1.7 MB). None have offset 0
  or stride 0. `fetch()` takes 1.7 ms a flip. As native formats:
  - `S32K` becomes `R16G16B16A16_SINT` with an `int4` to `float4` in the
    shader;
  - `CMP` becomes `R32_UINT`, unpacked in the shader.
  Both need input-signature changes in `d3d8_vsh` HLSL and MSL, and
  Metal mirrors them.
- `setup_pixel`: stage loop 2.2-2.6 ms, `build_stages` 1.2-1.4 ms, PS
  constant fill 0.9-1.1 ms and PS constant upload 0.7-0.9 ms a flip. 187
  of about 10k batches change the PS constants, so a key on the inputs to
  the stage registers could skip most of the loop.
- Decode: 47-53 ns a method under Wine. `vsh_method`'s range-check chain
  and `nv2a_pb_scan.c`'s `note()` (about 3.4% of the walker) are the first
  targets. This is shared with Metal and JSRF.

## Phase 2 results

Toolkit `perf/deck-draws-2`. Deck, `@stage1-2-barricade` under GE-Proton11-7,
`RECOMP_TRACE=flip,pacing,prof=250,prof_delay=50`, 120 s runs. Medians over
heavy flips (8000 batches or more):

| | base-1 | base-2 | decode + stages (after-1) | (after-2) | + stage loop (after-3) |
|---|---|---|---|---|---|
| batches | 9756 | 9727 | 9958 | 10043 | 10052 |
| wall ms | 33.4 | 33.4 | 33.4 | 33.4 | 33.4 |
| walk ms | 26.5 | 26.0 | 25.1 | 25.5 | 24.4 |
| draw ms (us/batch) | 15.8 (1.62) | 15.6 (1.60) | 15.1 (1.51) | 15.5 (1.54) | 14.4 (1.43) |
| decode ms (ns/method) | 10.0 (52) | 9.9 (51) | 9.4 (46) | 9.4 (46) | 9.4 (46) |
| wall p90 / p99 | 36.2 / 44.7 | 35.6 / 50.1 | 37.8 / 50.3 | 38.6 / 51.2 | 40.6 / 49.1 |
| flips over 40 ms | 2.1% | 5.6% | 8.4% | 8.5% | 11.2% |
| fps | 29.9 | 29.9 | 30.0 | 30.0 | 30.0 |

Per batch, the walk is 7-9% cheaper; decode is 10% cheaper per method. The
stage-loop memo serves 88% of the heavy flips' batches (8.8k of 10.0k).

The tail is not attributed. Counting flips over 40 ms in run order
(base-1, after-1, base-2, after-2, after-3, back to back) gives 17, 61,
45, 60, 79. That is not monotonic, but in each adjacent pair the after
run is worse than the base before it. Base-1 was not cold either: it
waited 162 s on the lock behind a JSRF bench, and other Deck goldens ran
during the series. The slow stretches fall on the same scripted flips in
every run (about 1450-1570 and 1860-1980). They lengthen from 5-7 flips
(base-1) to 34-36 (after-3). Inside them, draw and decode both run 35-40%
slower, while uploads, rehashes and the memo hit rate match the fast
flips. That points to a clock or power state rather than more work on
the CPU, but run order confounds it. Heat is one reading. The governor or
APU power budget answering a lighter walk is another, and that one would
be an effect of this change. The tracker item settles it: a cold, interleaved ABBA
series with 3 or more runs per arm, idle gaps between runs,
`scaling_cur_freq` and the APU temperature logged through each run, and a
`d3d11_memo=0` arm on the after exe to isolate the memo. If the after
arm's over-40 ms share stays more than 2 points above base, investigate
before shipping. The tracker item gates the release round, not this
merge. The medians above stand.

Metal (Mac, headless, the same script; `metal_memo=0` against the
default on one build, so the decode change is in both):

| | memo off | memo on |
|---|---|---|
| batches | 10054 | 10026 |
| walk ms | 17.1 | 15.7 |
| draw ms (us/batch) | 9.72 (0.97) | 8.33 (0.83) |
| decode ms | 6.60 | 6.57 |
| wall p90 / p99 | 33.6 / 34.7 | 33.4 / 34.3 |
| flips over 40 ms | 0.4% | 0.0% |

What each change does:
- Decode: `vsh_method` answers from the method alone, so a bitmap of
  methods it declined sends them straight to the main switch (about 40
  compares each); `note()`'s count runs only for the survey.
- `build_stages` (D3D11 and Metal) reruns only when the texture-register
  generation (`nv2a_pb_tex_regs_gen`, moved only by a changed value),
  the shader program or the contiguous arena's high-water mark (what
  `dma_resolve` depends on) moved.
- Stage loop (D3D11): the views of the last loop stand while the stages,
  flip, texture cache (uploads, frees) and render-target set (made,
  grown, dropped, reformatted) are unchanged and no stage was a render
  target. Samplers are still looked up per batch. `[D3D11] flip` lines
  give the hit count (`memo N`).
- Metal c[]: an encoder keeps its bindings, so buffer 1 is sent again only
  for a new encoder, a new generation, or after a non-program draw put vc
  there.

Not done: native `S32K`/`CMP` inputs (about 1.7 ms; needs a per-input type
in the VS key and both shader generators) and the Metal stage-loop memo.
