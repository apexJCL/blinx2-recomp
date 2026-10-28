## 1. Toolkit (`feat/heap-quarantine` off `posix-host/portability`)

- [x] 1.1 `RECOMP_HEAP_QUARANTINE` CONFIG row in `src/platform/recomp_env.h`
- [x] 1.2 FIFO, duplicate guard and drain-before-OOM in `src/kernel/xbox_memory_layout.c`
- [x] 1.3 `memory_regressions_heap_quarantine` ctest and README table
- [x] 1.4 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL (memory_regressions 6/6, with the oversize-block check)

## 2. cat (`feat/heap-quarantine`)

- [x] 2.1 `docs/env.md` row and Config count

## 3. Verify

- [ ] 3.1 JSRF on native Windows with `RECOMP_HEAP_QUARANTINE` set: the stage-entry hang does not recur over the user's play session (after the test)
- [ ] 3.2 Review before merge
