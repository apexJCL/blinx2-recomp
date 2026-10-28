## 1. Toolkit (fix/b3-glare off posix-host/portability)

- [x] 1.1 `occ_amend` and the `settled`/`amend` fields; disarm at `GET_REPORT`; `amended` in the summary
- [x] 1.2 `tests/occ_reports`: stale case updated, guards and rotation cases added
- [x] 1.2a Near-slot fallback (`NV2A_OCC_NEAR`, `beside` count) and its case
- [x] 1.2b Review: the borrow only for a lone test (no other report within `NV2A_OCC_NEAR` pending or issued in the same flip); cases for a borrowed 0, a crowd, a full `retired[]` and a scale change
- [x] 1.3 Mac build, `tests/posix_ctest.sh` 0 FAIL (llvm-mingw build too)

## 2. Verification

- [x] 2.1 Metal B3 race A/B with `occ_delay_us=12000` (unfixed, fixed, fixed without delay)
- [ ] 2.2 Native D3D11 B3 race at the user's settings
- [x] 2.3 BLiNX 2 Metal golden and Deck D3D11 golden unchanged: attract, stage1, story pass on both (Deck bench-logs 20261022-011242, -011424, -011758)
- [x] 2.4 Review round (lone-test borrow): posix ctests 0 FAIL; Metal B3 A/B with the delay 1 flare frame (was 3; 1 with no delay); BLiNX 2 Metal golden and Deck D3D11 golden pass (Deck bench-logs 20261022-014824, -014943, -015248)
