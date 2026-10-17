## Evidence

- `runs/blx193/base-256.log`: the unfixed toolkit (8c9f875b) at soft limit
  256, with `RECOMP_KERNEL_LOG_BUDGET` raised. The open of
  `z:\blinx2_248.rec` fails with 0xC0000001, then SIGSEGV in
  `w32_handle_fd`. 259 NtClose calls for 248 files: each 0x60 handle is
  closed and each 0x48 handle stays open.
- `runs/blx193/fixed-256.log` and `fixed-256-lsof.txt`: the fixed build at
  soft 256 and hard unlimited, as from Finder. The limit is raised from 256
  to 138240 (65536 since the cap in D2). All 363 cache files are created.
  lsof shows 360 `.rec` fds and about 410 fds in all, flat for two minutes.
- `runs/blx193/fixed-hard256.log`: the fixed build with the hard limit also
  at 256, so there is nothing to raise. There is no crash. Opens from
  `blinx2_248.rec` on return 0xC000011F (win32 err=4), the warning prints
  once, and the game carries on with a partial cache.

## D1. Validate handles without dereferencing them

A file HANDLE on POSIX is a pointer to its `w32_object`. A magic field
would still mean reading through whatever the guest passed. Instead, live
file objects go into an open-addressing hash set keyed by the pointer
value:
- `w32_open_handle` inserts the object, and the final `obj_release`
  removes it, before the fd is closed.
- The lookup compares pointer values and never touches the object.
- The set grows at 50% load and rebuilds to drop tombstones.
- The value 1, the tombstone marker, is never a match.

One mutex covers the set lookup and the read of the object's `fd` or
`file_path` pointer. That is one uncontended lock per file call, which costs
nothing next to the syscall that follows. The lock does not cover what the
caller does next. The fd or path is used after the unlock, so a close or a
rename on another thread can still race it. That needs an API that holds a
reference or copies the value out (tasks.md, follow-ups).

NtClose and CloseHandle do not use the registry yet. A stale or synthetic
non-NULL handle passed to them is still dereferenced (follow-up too). The
crash in this change went through the query calls, not the close.

This covers file handles only. Events, threads and the other objects still
cast blindly. The bridge only hands those a handle from its own table, so
the guest cannot reach them with a raw value the way it reaches the file
calls.

## D2. Raise the limit in the toolkit, at kernel init

The limit matters to every title, not only BLiNX 2, so the raise goes in the
toolkit and not in the game's `main.c`. `xbox_kernel_init` runs before any
game code, after logging is set up, so the one info line lands in
`xbox_kernel.log`.

The target is the hard limit, capped at 65536. Linux hard limits set by
systemd are 524288 and up, and about 2^30 in some containers. The raised
soft limit is inherited by every child, where select() (FD_SETSIZE) and
loops that sweep every fd up to the limit break or crawl. A title needs a
few hundred, so 65536 is ample. On macOS the hard limit is usually
RLIM_INFINITY. setrlimit may refuse RLIM_INFINITY for RLIMIT_NOFILE (the
man page says it does; macOS 27 accepts it), and the kernel caps the
effective value at `kern.maxfilesperproc` anyway. So the target is that
sysctl from the start, then OPEN_MAX (10240) if even that is refused. The
function reads the limit back, so the log reports the value actually in
force. When the soft limit already equals the target, nothing is logged.

## D3. Name the failure

EMFILE and ENFILE become STATUS_TOO_MANY_OPENED_FILES with win32 err 4
(ERROR_TOO_MANY_OPEN_FILES). The Win32 backend's NtCreateFile maps
ERROR_TOO_MANY_OPEN_FILES to the same status, so both backends agree. The
first one also prints a stderr line with the live file-handle count, so a
tester's log shows the cause next to the failed open.

## Validation

- `tests/kernel_file_handles` (new, POSIX). Against the old source it
  faults on the INVALID_HANDLE_VALUE case. With the fix it passes. When
  the hard limit is below 464, the raise and the 400-file sections are
  skipped. A 4-thread open/lookup/close loop also runs clean under
  `-DXBOX_FILE_HANDLES_ASAN=ON`.
- `tests/posix_ctest.sh`, 0 FAIL.
- The Metal golden from the cat worktree, built against the toolkit
  worktree.
- The repro above at soft 256 with a fresh hdd.
- Proton gates: run by the orchestrator after review. On the Win32 file
  path, the only change is the new status mapping for
  ERROR_TOO_MANY_OPEN_FILES.
