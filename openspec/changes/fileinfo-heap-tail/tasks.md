## 1. Toolkit (`fix/fileinfo-heap-tail` off `posix-host/portability`)

- [x] 1.1 `xbox_FsVolumeInformation` and `XBOX_FILE_FS_VOLUME_INFORMATION`, `XBOX_FILE_INTERNAL_INFORMATION`, `STATUS_INFO_LENGTH_MISMATCH` in `kernel.h`
- [x] 1.2 Classes 1 and 6 on the Win32 and POSIX backends
- [x] 1.3 Classes 1 and 6 in the RAM cache
- [x] 1.4 Heap tail fold under reclaim
- [x] 1.5 `tests/kernel_file_info`; check in `tests/kernel_ram_cache`; check 3b in `tests/memory_regressions`

## 2. cat (`fix/fileinfo-heap-tail`)

- [x] 2.1 This spec

## 3. Verify

- [x] 3.1 Mac build, `tests/posix_ctest.sh` 0 FAIL
- [x] 3.2 BLiNX 2 Metal golden against the branch toolkit
- [x] 3.3 Deck golden (`blinx2 bench golden`)
- [x] 3.4 `sh notes/build-all.sh` with `TOOLKIT=wt/ITEM/xboxrecomp`
- [x] 3.5 KUF with `RECOMP_HEAP_RECLAIM=1` headless on Metal: no `unhandled class`, no `out of memory`, battle frames (`runs/kuf-v013/20-ITEM/`)
- [x] 3.6 Review before merge (fixes below)

## 4. Review fixes

- [x] 4.1 M1: fold only when the bump would pass the heap top, then retry; comment, design and check 3b to match, plus a check that a carve miss with room above still bumps past a free tail
- [x] 4.2 L1: check 3b folds two merged 4 MB blocks for a 9 MB request; README row
- [x] 4.3 L2: class 6 short buffer sets the status block (Win32, POSIX, RAM cache), with test checks
- [x] 4.4 L3: fold comment wording; L4: no tracker id in the ram cache test comment
- [x] 4.5 Gates again: Mac build, POSIX ctests, KUF run `runs/kuf-v013/23-ITEM-r2` (repeat `23-ITEM-r2b`), BLiNX 2 Metal golden, BLiNX 2 native Windows golden (the Deck was reserved)
