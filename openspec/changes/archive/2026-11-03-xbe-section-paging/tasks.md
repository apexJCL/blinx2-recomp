## 1. Toolkit (`feat/xbe-section-paging` off `posix-host/portability`)

- [x] 1.1 `src/kernel/xbe_sections.{c,h}`: register, load, unload, preload boot, resident tally
- [x] 1.2 Loader: register sections, defer non-preload ones, grow the map (`paging_map_size`), boot-time preload loads
- [x] 1.3 `bridge_XeSection` through the module; `xbox_SetSectionPaging`; `RECOMP_XBE_PAGING` CONFIG row
- [x] 1.4 `tests/xbe_sections` ctest (both modes, fresh reload, shared pages, preload, bad headers)
- [x] 1.5 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL

## 2. cat (`spec/xbe-section-paging`)

- [x] 2.1 This spec; `docs/env.md` row and Config count

## 3. Verify

- [x] 3.1 BLiNX 1 on Metal with paging: past the out-of-memory and the `3_plyrse.bin` read; the next failure recorded
- [x] 3.2 Metal goldens unchanged: BLiNX 2, JSRF. Burnout 3 is closed on the review's reading: with paging off, the code path copies, allocates and maps exactly as before
- [ ] 3.3 Deck/Proton golden slot (orchestrator)
- [x] 3.4 Review before merge (merge after fixes; M1, M2, L1-L5 and L8 done on the branch)
- [ ] 3.5 BLiNX 1 port: call `xbox_SetSectionPaging(1)` before `xbox_MemoryLayoutInit`. Check:
  - with `RECOMP_TITLE_KEVENTS` on, a KEVENT at `0x04000000` or above gets no host event, so check where the title allocates its events;
  - fixes and mods that write a non-preload section must hook after its `XeLoadSection`, because a boot-time write is lost at the first load;
  - the heap stops at the paging cap, so reservations above it never overlap heap blocks (the M1 fix, toolkit 64f30fd6).
