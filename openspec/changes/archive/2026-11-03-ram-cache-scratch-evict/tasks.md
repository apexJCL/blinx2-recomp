# Tasks

- [x] `make_room` in `kernel_ramfs.c`, used by `set_size` and directory create
- [x] Header, `recomp_env.h` row and `docs/env.md` row describe the rule
- [x] `kernel_ram_cache_over_cap_test` ctest
- [x] 5-1 REW A/B with a Cache dir over the cap matches the cache-off path
  (67/67 REW frames equal to the cache-off run; 119 seeds dropped, no DISK_FULL)
- [x] Gates: Mac build, POSIX ctests (128 pass, 0 FAIL), Windows build on the PC,
  build-all (12/12 pass on toolkit ebed232b)
- [x] Follow-up: per-game `<hdd>` default (filed as the tracker item)

Review fixes (review):

- [x] Drop only when the seed overflowed (`s_seed_overflow`); free space
  counts droppable seeds while it is set
- [x] Listed or queried seeds (`seen`) are never dropped; the A/B still
  matches (67/67, 119 seeds dropped), so the rule stays
- [x] Seeded directories are capped (`seed_dir`) and set the flag
- [x] ctests: subdirectory drop, listed and queried seeds kept, first open
  drops nothing, tie order, `under_cap` (flag clear) and `dir_over_cap`
