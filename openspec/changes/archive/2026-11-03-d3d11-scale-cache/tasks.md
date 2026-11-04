## 1. Toolkit (`fix/d3d11-scale-cache` off `posix-host/portability` 18607bd9)

- [x] 1.1 `scale_drop` in `src/d3d/nv2a_pb_d3d11.c` keeps `s_tc` and `s_tc_hint`; comment and log line updated
- [x] 1.2 `tests/d3d11_backend_smoke` case `scale_cache_cases`: for scales 2, 3 and 1, the flip after the change uploads no texture, samples the cached checker right and reuploads exactly once when a texel is rewritten after the change, and samples RTT_B cleared to a colour of its own per scale at a 64-times-scale host size (review L1, L2) (needs a D3D11 device: built on the Mac, run on the Deck under GE-Proton11-7; passes in both occlusion modes)
- [x] 1.3 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL

## 2. cat (`spec/d3d11-scale-cache`)

- [x] 2.1 This spec

## 3. Verify

- [x] 3.1 Deck (GE-Proton11-7), JSRF `opts_at` 1x to 2x to 3x to 1x, base and fix: first-flip ms and uploads after each change; frames before and after each change compared. Base (`bench-logs/20261027-180628`) 716/213/158 ms (88/79/61 uploads), fix (`bench-logs/20261027-180904`) 575/19/17 ms (1/0/0 uploads); all 9 dumped frames byte-identical to base
- [x] 3.2 BLiNX 2 D3D11 golden on the Deck (`blinx2 bench golden`): attract, stage1 and story pass
- [x] 3.3 BLiNX 2 Metal golden pass, attract, stage1 and story (D3D11-only change; the Mac binary does not build `nv2a_pb_d3d11.c`)
- [x] 3.4 Review: merge, with the two smoke gaps L1 and L2 fixed (`notes/ITEM/review-ITEM.md`)
