## 1. Phase 1: toolkit `perf/deck-draws` off `posix-host/portability`

- [x] 1.1 `nv2a_pb_vsh_consts_gen()` bumped at every c[] writer (`nv2a_pb_exec.c`, `nv2a_pb_state.h`)
- [x] 1.2 D3D11: skip the c[] compare while the generation is unchanged
- [x] 1.3 D3D11: `OMSetRenderTargets` / `OMSetDepthStencilState` in the state shadow; `swap_resize` resets it
- [x] 1.4 per-batch clock reads only under `RECOMP_FLIP_LOG`
- [x] 1.5 ctest `tests/pb_vsh_cgen`
- [x] 1.6 Deck before/after in 1-2 (design.md)
- [x] 1.7 gates: Mac build, posix ctests, Metal golden, Deck D3D11 golden
- [ ] 1.8 native Windows golden at the PC's next Windows boot (owed)

## 2. Phase 2: toolkit `perf/deck-draws-2`

- [x] 2.1 Metal: send c[] by generation (backends agree), with the `build_stages` memo; `RECOMP_DEBUG=metal_memo=0` for A/B
- [ ] 2.2 native `S32K` and `CMP` vertex inputs (HLSL and MSL generators, D3D11 and Metal): deferred to a follow-up
- [x] 2.3 `setup_pixel` stage memo: `build_stages` keyed on the texture-register generation, and the stage loop's views kept while the stages, flip, texture cache and render targets are unchanged (D3D11)
- [ ] 2.3a Metal: the same stage-loop memo (follow-up; perf only, output unchanged)
- [x] 2.4 decode: a per-method "not vsh" bitmap ahead of `vsh_method`'s range chain; `note()` only under the survey
- [x] 2.5 ctest `tests/pb_vsh_cgen`: methods after the bitmap skip, ff_begin/ff_end generation and restore, texture-register generation (cxt_write and the A/B restore need a CPU surface: not covered)
- [x] 2.6 draw timing reads `perf_draw_on()` once (review LOW-4)
- [x] 2.7 Deck and Metal before/after in 1-2 (design.md)
- [x] 2.8 gates: Mac build, posix ctests, Metal golden, Deck D3D11 golden
- [ ] 2.9 native Windows golden at the PC's next Windows boot (owed)
- [ ] 2.10 cold interleaved Deck tail A/B (gates the release round, not the merge)
