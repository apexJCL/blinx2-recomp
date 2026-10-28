## 1. Toolkit

- [x] 1.1 `src/d3d/shader_cache.c/.h`: key, entry format, load with validation, store through a temporary and rename, prune.
- [x] 1.2 `nv2a_pb_d3d11.c`: compiler identity, `D3DCreateBlob`, load before and store after `D3DCompile`, the init and `shaders:` lines.
- [x] 1.3 `xbox_path_hdd_root()` in kernel_path (both halves) and its check in the `kernel_path` ctest.
- [x] 1.4 `RECOMP_DXBC_CACHE` row in `recomp_env.h`.
- [x] 1.5 ctest `shader_cache`: key fields and boundaries, off cache, nested mkdir, round trip, no temporaries left, another key under the same name, seven damaged shapes, store after damage, failed store, prune (stale temporary, cap, LRU after a hit, foreign files kept).

## 2. cat

- [ ] 2.1 `docs/env.md` Config row for `RECOMP_DXBC_CACHE`, Config count 63 to 64 (the orchestrator lands it with the merge).

## 3. Gates

- [x] 3.1 Mac build (macOS and Windows cross) of BLiNX 2 at the branch.
- [x] 3.2 POSIX ctests (`tests/posix_ctest.sh`), 0 FAIL.
- [x] 3.3 Deck: `blinx2 bench golden` twice in one bench tree (cold, then warm), all pass, and the `[d3d11] shaders:` lines show compiles in the first and cache hits in the second.
- [x] 3.5 The Windows half (`MoveFileExW`, `FindFirstFileW`, `_wutime`, `ft_secs`, the UTF-8 widening): `shader_cache_test.exe` cross-built and run once under Proton on the Deck (toolkit 76046e78), 0 failures.
- [x] 3.6 Review fixes (M1, L2-L4): env parsing like `recomp_env_on`, a relative directory turns the cache off, init probes that the directory can be written, prune counts only removals that worked, the DLL's file version in the compiler identity; ctest cases. Toolkit 6b4e8e7a: Mac builds, POSIX ctest 100 pass 0 FAIL, Deck BLiNX D3D11 golden pass (attract 51 misses under the new key, then hits).
- [x] 3.4 Metal golden: not needed (no Metal or shared renderer code changed).

## 4. Measurements

- [x] 4.1 Deck, JSRF title, s1-dsp0-43: n=3 each of cache off (`RECOMP_DXBC_CACHE=0`), cold (fresh directory) and warm (primed directory): `load_gap_ms`, flips/s, the `shaders:` lines.
- [x] 4.2 Deck profiled run, warm and off: the d3dcompiler share of steady samples.
- [ ] 4.3 PC (session the Spartan session): the same three arms on native Windows.
