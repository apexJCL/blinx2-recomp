Worktrees: `wt/fdlimit/xboxrecomp` (toolkit, `fix/mac-fd-limit` off
`posix-host/portability` 8c9f875b) and `wt/fdlimit/cat` (`fix/mac-fd-limit`
off `main` a359dd8) for this spec. Runs are in `xbox-recomp/runs/ITEM/`.

## 1. Diagnose

- [x] 1.1 Reproduce on the unfixed toolkit at soft 256 with a fresh hdd and a
      full kernel trace (`runs/ITEM/base-256.log`).
- [x] 1.2 Leak or limit: the 0x60 handle is closed and the 0x48 handle is
      kept, one per cache file. It is the limit (design.md Evidence).

## 2. Toolkit

- [x] 2.1 `win32_compat.c`: the live file-handle registry. `w32_handle_fd`,
      `w32_handle_path` and `w32_handle_set_path` validate before they
      dereference (D1). Add `w32_open_file_handles`.
- [x] 2.2 `win32_compat.c`: `w32_raise_fd_limit` (D2). Call it from
      `xbox_kernel_init` on POSIX hosts, with one info log line.
- [x] 2.3 `kernel_file.c` POSIX: map EMFILE/ENFILE to
      STATUS_TOO_MANY_OPENED_FILES with err 4, warn once on stderr, and
      handle a failed registration (D3).
- [x] 2.4 `tests/kernel_file_handles`: handle validation, fd release, the
      limit raise and the exhausted limit. Check that it fails on the old
      source.

## 3. Gates

- [x] 3.1 Mac build (cat worktree against the toolkit worktree).
- [x] 3.2 `tests/posix_ctest.sh`, 0 FAIL.
- [x] 3.3 Metal golden.
- [x] 3.4 Repro: fixed build, soft 256, fresh hdd. It gets past the cache
      and the fd count stays bounded.
- [x] 3.5 Review fixes:
  - the 65536 cap;
  - the failed-open IoStatusBlock status;
  - the Win32 ERROR_TOO_MANY_OPEN_FILES mapping;
  - the ctest skip and the thread loop.
- [ ] 3.6 Proton gates (orchestrator).

## 4. Follow-ups (to TASKS.md at the merge)

- [ ] 4.1 `w32_handle_path` and `w32_handle_fd` return a value that is used
      after the unlock. A concurrent rename or close can race it. This needs
      an API that holds a reference or copies the value out.
- [ ] 4.2 `xbox_NtClose` and `CloseHandle` dereference stale or synthetic
      non-NULL handles. Validate them against the registry first.
