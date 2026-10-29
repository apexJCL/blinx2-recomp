## Why

Kingdom Under Fire: Heroes (CLI v0.13.0) stops right after character select
on two toolkit bugs. Both are still on `posix-host/portability`
(92cc7a3c). Experiment patches proved them in the KUF runs
(`notes/kuf-v013/toolkit-experiments.diff`).

1. XAPI `GetFileInformationByHandle` queries `FileFsVolumeInformation` (1),
   then `FileInternalInformation` (6), then `FileNetworkOpenInformation`
   (0x22), and fails as a whole when one of them does. Both disk backends
   answered classes 1 and 6 with `STATUS_NOT_IMPLEMENTED` (logged as
   `unhandled class 1`). KUF ignores the failure, takes stack garbage as the
   file size, reads 512 bytes of `install_image.dds`, and its texture load
   ends on the fatal stop screen.
2. With `RECOMP_HEAP_RECLAIM=1`, KUF frees a 32 MB block that ends at the
   bump cursor, then asks for 33558528 bytes. No free block is big enough,
   and the bump path only looks above the cursor (11.9 MB), so the request
   fails while `[HEAP] exhausted` reports a 44.7 MB free run. KUF throws a
   C++ exception and crashes.

## What changes

- `src/kernel/kernel_file.c`, both backends (Win32 and POSIX):
  - `NtQueryVolumeInformationFile` answers `FileFsVolumeInformation` through
    a shared `xbox_FsVolumeInformation`: NT layout, no label (FATX has none),
    the host volume's serial (Win32 `dwVolumeSerialNumber`, POSIX `st_dev`).
    A buffer under 24 bytes gets `STATUS_INFO_LENGTH_MISMATCH`; a label that
    does not fit is cut with `STATUS_BUFFER_OVERFLOW`, as NT does.
  - `NtQueryInformationFile` answers `FileInternalInformation`: the file
    index (Win32 `nFileIndexHigh:Low`, POSIX `st_ino`). Under 8 bytes:
    `STATUS_INFO_LENGTH_MISMATCH`.
- `src/kernel/kernel_ramfs.c` (the opt-in RAM cache, on by default for
  BLiNX 1): the same two classes, the node id as the index.
- `src/kernel/xbox_memory_layout.c`, `heap_alloc_locked`, reclaim path only:
  when no free block fits and the bump from the cursor would pass the heap
  top, free blocks that end at the cursor give it back (`heap_fold_free_tail`)
  and the bump is retried, before the quarantine drain and out of memory. A
  bump that fits leaves the tail alone.
- Tests: new `tests/kernel_file_info`, a check in `tests/kernel_ram_cache`,
  check 3b in `tests/memory_regressions`.

## Not changed

- The heap with reclaim off: the fold runs only under reclaim, and
  `memory_regressions_default` pins that a larger request still bumps past
  the free tail.
- The heap with reclaim on while the bump fits: check 3b pins that a larger
  request still bumps past a free tail when there is room above.
- Every class that was answered before.

## Impact

- Only titles that query classes 1 or 6 see a difference on the file side;
  BLiNX 2 does not (golden unchanged expected).
- Heap addresses change only under `RECOMP_HEAP_RECLAIM`, and only for a
  request that would otherwise run out of heap. A title that works today
  keeps its addresses: JSRF, which defaults reclaim on, depends on which
  address a free hands back.
