## Why

The tracker item. On macOS, a first boot with an empty `RECOMP_HDD_DIR` crashed while
the game built its Z: cache. The open of `z:\blinx2_246.rec` failed with
0xC0000001, the game passed the INVALID_HANDLE_VALUE it got back to
NtQueryInformationFile, and `w32_handle_fd` read `o->kind` through it:
SIGSEGV at 0xFFFFFFFFFFFFFFFF (`runs/ITEM/mac-crash1.log`).

**Root cause: the open-file limit, not a leak.** A kernel trace of the same
boot (`runs/ITEM/base-256.log`) shows the pattern for every cache file:
open with options 0x60, query and set the size, NtClose, then open again
with 0x48 and keep that handle. NtClose does release the first handle's fd.
The game holds one handle per cache file for as long as it runs, as the
console's kernel allows, and a full cache is 363 files. macOS gives an app
launched from Finder a soft RLIMIT_NOFILE of 256, so the 247th to 249th
open (depending on what else is open) fails with EMFILE. A terminal launch
inherits the shell's limit, which is why earlier runs got past it.

Two defects sit on top of that:
- The POSIX file helpers trust any pointer they are given. The guest can
  pass INVALID_HANDLE_VALUE, a closed handle or one of the bridge's
  synthetic values (0xDEAD0001), and the bridge forwards untagged values
  unchanged.
- EMFILE maps to STATUS_UNSUCCESSFUL with win32 err=0, which reads like an
  unexplained failure in a tester's log.

## What Changes

- **Toolkit `src/platform/win32_compat.c`.**
  - A registry of live fd-backed file objects.
  - `w32_handle_fd`, `w32_handle_path` and `w32_handle_set_path` look a
    handle up there before they dereference it, so NULL,
    INVALID_HANDLE_VALUE, closed, synthetic and non-file handles get -1 or
    NULL. Every file HLE caller already turns that into
    STATUS_INVALID_HANDLE.
  - `w32_open_file_handles()` counts the live file handles.
  - `w32_raise_fd_limit()` raises the soft limit to the hard one, at most
    65536. On macOS it is also capped at `kern.maxfilesperproc`, with
    OPEN_MAX as the fallback.
- **Toolkit `src/kernel/kernel_thunks.c`.** `xbox_kernel_init` raises the
  limit on POSIX hosts before any game code runs, and logs it once at the
  info level.
- **Toolkit `src/kernel/kernel_file.c` (POSIX).**
  - EMFILE and ENFILE map to STATUS_TOO_MANY_OPENED_FILES (0xC000011F) with
    win32 err 4.
  - The first such failure prints one `[FILE] out of host file
    descriptors` line on stderr.
  - An open whose handle cannot be registered fails with STATUS_NO_MEMORY
    and does not leak the fd.
  - The IoStatusBlock of a failed open carries the same status as the
    return value.
- **Toolkit `src/kernel/kernel_file.c` (Win32).** ERROR_TOO_MANY_OPEN_FILES
  maps to STATUS_TOO_MANY_OPENED_FILES.
- **Toolkit `tests/kernel_file_handles/`.** A new POSIX ctest for handle
  validation, fd release over the cache's open/close/reopen pattern at 400
  files, the limit raise from 256, the exhausted-limit status, and a
  4-thread open/lookup/close loop (with an ASan option).

## Impact

- POSIX hosts (macOS and Linux). On the Win32 backend, and so on Proton
  and Windows, only the status for ERROR_TOO_MANY_OPEN_FILES changes:
  Windows has no such per-process limit for these handles.
- No env key, no renderer or audio change. Stock behaviour changes only
  where it failed before: an open that hit the limit now succeeds.
- The FATX deferred-overwrite table in kernel_file.c is indexed by fd and
  holds 4096 entries. An fd above that truncates at open, as before. With
  the higher limit, a title would need more than about 4000 open files to
  reach it.
- Upstream: title-agnostic toolkit code. It is a candidate for the PR set
  after the Burnout 3 gate.
