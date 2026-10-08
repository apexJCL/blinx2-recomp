## 1. Confirm the merged state
- [x] 1.1 Record in TASKS that nits 1 to 3 are in toolkit 6721c18 (merged in 4ec9f0a, an ancestor of a10f6d8), and that nit 1's dims ctest is in `tests/nv2a_tex`.

## 2. Test for the cache key (nit 2)
- [x] 2.1 If design D3 (a) is kept: add `nv2a_pb_exec_tc_stats()`, read-only, in `nv2a_pb_state.h` and `nv2a_pb_exec.c`.
- [x] 2.2 `tests/pb_tex_cache` (CMakeLists.txt, test_main.c), built from `src/d3d/CMakeLists.txt` on POSIX, as `nv2a_backend_smoke` is. Cases 1 to 5 from design D2.
- [x] 2.3 Check that the test fails on a deliberately broken key: temporarily put `levels` back in the match, or limit the fingerprint to the requested levels. Then revert. Result: the key mutation fails 8 checks. The fingerprint mutation fails 2, once the rewrite case decodes level 2 in an unchanged flip before the rewrite.

## 3. Docs
- [x] 3.1 `docs/env.md`: the `RECOMP_PB_BILINEAR` and `RECOMP_PB_MIPS` rows' source refs become `nv2a_pb_exec.c:2690` and `:2707`, or the lines at the branch tip.

## 4. Gates (design D4)
- [x] 4.1 Mac build, POSIX ctests.
- [x] 4.2 Skipped by the orchestrator: no rendering code changes (the hot path gains one counter, at a build).
- [x] 4.3 Skipped likewise.
- [x] 4.4 Skipped: pb_tex_cache is POSIX-only (src/d3d/CMakeLists.txt, `if(NOT WIN32)`) and not in the Proton test set, and goldens are not needed.
- [x] 4.5 TASKS: move "CPU mip/LOD nits" to Done with the shas.
