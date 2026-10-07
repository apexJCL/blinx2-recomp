## Context

Every guest file open goes through `bridge_create_file_impl` (`xboxrecomp/src/kernel/kernel_bridge.c:3809`). `bridge_NtCreateFile`, `bridge_NtOpenFile` and `bridge_IoCreateFile` all call it, and it calls `xbox_NtCreateFile` (`kernel_file.c:213` for Win32, `:1004` for POSIX). It already holds the guest path (`name.Buffer`, from `bridge_build_oa`), the access mask, the disposition, the options and the status: everything the report needs. No XAPI file function is HLE'd, so ADX streams, Sofdec movies, archives and saves all take this one path. Attribute probes go through `bridge_NtQueryFullAttributesFile` (`kernel_bridge.c:4529`).

`kernel_path.c` maps a guest path to a host path through a rule table (`s_rules`, `kernel_path.c:49`). Each rule's `to_save` field says which root a path lands in:
- **0, the game files dir:** `\Device\CdRom0\`, `D:\`, `Y:\`, `C:\`, `Partition2\` and `Partition1\`.
- **1, the HDD root:** `T:`, `U:`, `Z:` and partitions 3–5.
- **2, the user-data root:** `UDATA` and `TDATA`.

The table also has a partition-device rule (the `PartitionN.img` images). `resolve_symlink` first rewrites a drive letter the title linked itself. Wreckless, for example, links `Z:` to `Partition1\`.

Three facts about today's code shape the design:
- **Translation is not free to repeat.** The Win32 `xbox_translate_path` prints a `[PATH] <guest>` line on every call, and the HDD and user rules create their directories on every call. So the reporter must not translate again.
- **The last host path is already per thread.** `xbox_LastHostPath()` reads a `XBOX_THREAD_LOCAL` buffer that the Win32 translation fills (`kernel_path.c:175`, `:442`). The POSIX backend never fills it, so it reads empty there. This change makes POSIX fill it too; the reporter then reads the path the failed call just translated, on the same thread.
- **A relative open bypasses the rules.** A name relative to a `RootDirectory` handle (XDeleteSaveGame opens each child of its save directory that way) goes through `GetFinalPathNameByHandleW` on Win32 and through the "unrecognized path" fallback on POSIX. The classifier never sees a rule for it.

What the spike measured (BLiNX 2, Mac, headless, files removed from a reflinked `game_files`):

| removed | title's response |
|---|---|
| songs, ambience, jingles, movie audio (ADX) | plays on, silent there. A looping stream re-opens its file every loop (97 attempts in 100 s) |
| `title_movie_1a.sfd` | skips the movie |
| `demoplay\r01s01demo.dat` | 5 attempts, then the stage loads anyway |
| `media.ipk`, `logo_mgs.sfd` | 5 attempts, a fallback to loose files, then the title's own dirty-disc screen |

No case crashed or hung the host.

The spike also replayed its proposed rule over the ten logs. The high-confidence group held exactly the removed files plus two files the dump really lacked. The low group held only probes and loose-file fallbacks. Those two real misses (`song_TITLE.adx`, `song_R1tomtom.adx`) came from an older, incomplete copy of `game_files`. The re-extracted dump (2026-10-06 09:28, 486 files) has them. A BLiNX run on the current dump therefore reports no high-confidence miss at all.

## Goals / Non-Goals

**Goals**
- Any title, on any host: a failed open of a game file names the file once, in the log.
- No noise from the probes titles normally make. By default, nothing is printed for saves, caches, numbered scans or attribute queries.
- A summary with counts when the run ends, including when the title exits through `HalReturnToFirmware`, the user closes the window, the watchdog fires or the process crashes.
- The same behaviour on every host: Win32 (Windows and Proton), macOS and Linux.
- POSIX failed-open status and error codes that match Win32 and the console.

**Non-Goals**
- A list of the files a game *should* have. The user decided this, and the spike measured 44–67% static coverage with no closed set.
- An on-screen hint. The window-title suffix stays a possible follow-up, off by default.
- The `media_warning` removal, which is done in `feat/toolcli-2-shims`.
- An ISO-against-extraction check, which is optional and a separate change.
- Case-insensitive lookup on case-sensitive host filesystems (native Linux). There a wrong-case name reads as missing. This is a separate issue.

## Decisions

### D1. "Missing" is defined by the call, the tree and the parent directory

A failed open is a **miss** when all of these hold:
1. the status is `STATUS_OBJECT_NAME_NOT_FOUND` (0xC0000034) or `STATUS_OBJECT_PATH_NOT_FOUND` (0xC000003A);
2. it came through `bridge_create_file_impl`;
3. the disposition is `FILE_OPEN` (1);
4. the access mask has none of `GENERIC_WRITE` (0x40000000), `GENERIC_ALL` (0x10000000), `FILE_WRITE_DATA` (0x2), `FILE_APPEND_DATA` (0x4), `FILE_WRITE_ATTRIBUTES` (0x100), `FILE_WRITE_EA` (0x10) or `DELETE` (0x10000);
5. `FILE_DIRECTORY_FILE` (0x1) is not in the options;
6. the name is absolute: it starts with `\` or with `<letter>:`. A name relative to a `RootDirectory` handle is never a miss;
7. `xbox_path_tree` (D2) classifies the path as the game tree.

A miss is **high** confidence when the host parent directory of the translated path exists (as a directory). It is **low** when it does not.

Every one of these is a plain test on the arguments the bridge already has, so the ctest (tasks §6) drives each condition on and off and checks the outcome.

Why the parent directory: in every spike run, the false positives were opens under a directory the dump never has. Examples are the `media\event\` camera scan and the `media\se\` loose fallbacks; those files live inside `media.ipk`. Every real miss sat in a directory that exists (`adx\`, `movie\`, `demoplay\`, the root). A dump that lacks a whole directory lands in "low". It is still counted, and verbose mode names it.

After D7, high and low line up with the status on both backends: a high miss carries NAME_NOT_FOUND and a low miss PATH_NOT_FOUND. The reporter still tests the directory itself rather than reading the status, so the report does not change if D7 is reverted, and the ctest asserts both the classification and the status for the same two paths.

Rejected alternatives:
- **Report every failed open in the game tree.** That keeps the probe noise this change exists to remove.
- **Infer probes from the retry count.** BLiNX retries both kinds 5 times, so the count tells them apart in neither direction.
- **Classify by status alone.** Cheaper, but couples the report to the one commit that is meant to be revertable on its own.

### D2. The tree comes from the rule that translated the path

`int xbox_path_tree(const char *xbox_path)` in `kernel_path.c` returns `XBOX_TREE_GAME`, `XBOX_TREE_HDD`, `XBOX_TREE_USER`, `XBOX_TREE_DEVICE` or `XBOX_TREE_UNKNOWN`. It applies the same `resolve_symlink` and the same first-match walk over `s_rules` as `xbox_translate_path`, and prints nothing. It maps:
- `to_save` 0, 1 and 2 to GAME, HDD and USER;
- a bare device (`\Device\CdRom0` with nothing below it, or a `\Device\Harddisk0\PartitionN` that `xbox_partition_device_digit` accepts) to DEVICE;
- a relative name (D1 condition 6) and the unrecognised-path fallback to UNKNOWN.

It is defined once, outside the backend `#if`, because the table, `resolve_symlink` and `xbox_partition_device_digit` are shared. That way the classification and the translation can never disagree. (`bridge_create_file_impl` answers the bare CdRom0 device with a synthetic handle before any translation, so the DEVICE case is there for completeness and the ctest, not for a path the report sees.)

`Partition1\` (E:) counts as GAME because the toolkit maps it to the game dir. Wreckless loads its assets through a `Z:` → `Partition1\` link. The cost is that a title probing `E:\` for something of its own would show up. The parent-directory rule makes those low confidence, so they appear only in verbose mode.

### D3. The reporter: `kernel_missing.c`

```c
void     xbox_missing_note(const char *guest_path, uint32_t status,
                           uint32_t access, uint32_t disposition,
                           uint32_t options, int is_probe);
void     xbox_missing_summary(const char *why);   /* "exit", "firmware", "window", "bugcheck"; ends the line under all */
void     xbox_missing_counts(uint32_t *high, uint32_t *low, uint32_t *attempts);
```

- **Callers.** `bridge_create_file_impl` calls it on every failure with `is_probe = 0`, after `xbox_NtCreateFile` returns and on the same thread. `bridge_NtQueryFullAttributesFile` calls it with `is_probe = 1` (disposition and options passed as `FILE_OPEN` and 0, so a probe fails only the probe test).
- **Mode.** The reporter reads `RECOMP_TRACE=missing` once:
  - unset or `1`: the default;
  - `0`: off, and nothing is recorded;
  - `all`: verbose.
- **Early out.** Conditions 1, 3, 4, 5 and 6 of D1 are checked before anything else, so a write open, a create or a relative name costs a few compares and no lock.
- **Host path.** The reporter reads `xbox_LastHostPath()`, the thread-local buffer the failed call just filled. It never calls `xbox_translate_path` (Context: a second `[PATH]` line and directory creation). The POSIX `xbox_translate_path` starts filling that buffer, widening each byte as the FMV hook narrows it; non-ASCII host directories are out of scope on both hosts (the FMV hook has the same limit). On Win32 the reporter narrows it the same way for printing.
- **Unique paths.** A fixed table of 4096 slots, open addressing, keyed by the case-folded guest path (FATX names are case-insensitive), each slot holding the folded guest path (160 bytes, the per-attempt line's truncation), the host path (`MAX_PATH`), the class and the path's attempt count. It is static storage, about 2.4 MB (4096 slots of about 596 bytes: the guest path, its folded key, the host path and the counts), with no allocation. Past the cap, misses are counted (`unnamed`) but not named, and one line says so the first time; their repeats cannot be recognised and keep printing (D6).
- **Repeat check.** `int xbox_missing_is_reported(const char *guest_path)` is a lookup only: it returns 1 when the path is already in the table as a high-confidence miss and the mode is the default. `bridge_create_file_impl` asks it before printing the per-attempt FAILED line (D6). It takes the same mutex for the probe and touches nothing else.
- **Order of work on a new path.** Fold, probe the table under the mutex; if the path is new, insert it, release the mutex, then test the parent directory and print. The `stat` therefore runs once per unique path, never per attempt, and never under the lock.
- **Parent directory.** `int xbox_host_parent_exists(const xbox_host_char *host_path)` is added to `kernel_file.c` for each backend: `GetFileAttributesW` with `FILE_ATTRIBUTE_DIRECTORY` on Win32, `stat` with `S_ISDIR` on POSIX. The parent is the host path cut at its last separator; a path with no separator has no parent and is low.
- **Counters.** Six `uint32_t` (high paths, low paths, other paths, attempts, repeats not printed, unnamed paths past the cap) updated with atomics (`InterlockedIncrement` / `__atomic_add_fetch`), so the crash handler and the watchdog read them with no lock. `attempts` counts every failed open that passed D1 conditions 1–7, high or low, named or past the cap. `repeats` counts the FAILED lines D6 left out.
- **Printing.** Each line is one `fprintf(stderr, …)` with one `fflush`, outside the mutex, like the per-attempt line today. Two threads may interleave lines, never characters within a line.

### D4. What is printed

| mode | per-path line (first time only) | summary |
|---|---|---|
| default | high: `  [FILE] missing <guest> -> <host>` | `  [FILE] summary: H game files missing, L not found under absent directories, A failed opens, R repeats not printed (RECOMP_TRACE=missing=all lists them)`. Printed when H > 0, so a complete dump whose only misses are probes prints nothing; `, R repeats not printed` is dropped when R = 0 and the parenthesis when L = 0 |
| `all` | high as above. Low: `  [FILE] not found (no such directory) <guest> -> <host>`. Other trees and probes: `  [FILE] not found (<tree>[, probe]) <guest> -> <host>` with `<tree>` one of `hdd`, `user`, `device`, `unknown`, `game` | the same counts (R is always 0: verbose prints every attempt), plus `, O other` and `, P probes` when non-zero. Printed when any path count is non-zero |
| `0` | nothing | nothing |

`<guest>` is the guest path as the title spelled it, truncated like the per-attempt line (159 characters). `<host>` is the translated host path. Lines are indented two spaces like every other `[FILE]` line.

The existing per-attempt `[FILE] … FAILED` line keeps its text word for word. It moves into `bridge_create_file_impl`, and in the default mode its repeats for a reported path are left out (D6).

The default-on lines follow the "opt-in features default OFF" rule because they are stderr only: no guest-visible change, no file written. A run on a complete dump prints nothing new.

`missing_list` (D8) writes, at each summary point, one line per unique path: `<class> <attempts> <guest> <host>` with `<class>` one of `high`, `low`, `other`, `probe` and `<attempts>` the number of failed opens of that path, separated by single spaces, the file truncated on each write. A guest path never contains a space on FATX, so the first three fields split on spaces; the host path is the rest of the line.

### D5. When the summary prints

Every exit the host controls, in the places that already handle the same problem:

- **`atexit`**, registered on the first note. Covers `main` returning, `exit`, and the SDL window closing or `RECOMP_WINDOW_QUIT_AFTER` firing (`fb_present_sdl.c:840` calls `exit(0)`).
- **`bridge_HalReturnToFirmware`**, next to `RECOMP_ICALL_FEEDBACK_DUMP()` (`kernel_bridge.c:1699`), for the same reason that dump is there: on Win32 this path ends in `ExitProcess`, which skips `atexit`. On POSIX `ExitProcess` is `exit()` (`win32_compat.c:1314`), so `atexit` *does* run after it. That is why the once-only guard below is required and not a nicety: without it every POSIX firmware exit prints the summary twice.
- **The Win32 window close.** `d3d8_device.c` (three `WM_QUIT` pumps, `:143`, `:460`, `:1393`) and `nv2a_pb_d3d11.c` (`WM_CLOSE`, `:282`) call `ExitProcess(0)` directly, so a user closing the window on Windows or Proton would get no summary. Each site calls `recomp_exit_hook_run("window")` first. That is a one-slot hook in the platform layer (`src/platform/recomp_exit_hook.h`), which the kernel sets to `xbox_missing_summary` with its `atexit` registration. The D3D library cannot name the kernel: its standalone tests (`d3d8_gamma`) link it without the kernel, and a direct call broke their Windows link.
- **`KeBugCheck` and `KeBugCheckEx`** (`kernel_hal.c`) end in `ExitProcess(code)` too, so each calls `xbox_missing_summary("bugcheck")` first. Guest code calls them, never from inside the report's lock, so the summary may take it to write `missing_list`.
- **The watchdog** (`xbox_memory_layout.c:2594`) ends in `_exit(3)` and already finalises the WAV dump by hand for that reason. It prints one counts-only line, `  [FILE] missing at watchdog: H high, L low`, from `xbox_missing_counts`: the frame thread it is reporting on may be wedged anywhere, including inside the reporter's mutex, so this path takes no lock.
- **cat's crash handler** (the common report in `cat/src/main.c` that prints `[CRASH] Access violation` and `recent ICALL targets`) prints `  [FILE] missing at crash: H high, L low` through its own `crash_printf`, only when H + L > 0, with no lock and no allocation, following host-crash-diagnostics' "Diagnostics must not mask the fault".
- **A guard flag** (atomic exchange) makes `xbox_missing_summary` print at most once per run, whichever caller gets there first. The counts-only lines are not guarded; they can appear once each in addition to the summary.

A run killed from outside (a `timeout` kill, SIGTERM, SIGKILL, `alarm`) prints no summary. Its per-path lines are already in the log. `bench.sh` and `golden.py` end their runs this way, so a gate that wants the summary line must end the run through `RECOMP_WINDOW_QUIT_AFTER` on the SDL host or through the title.

### D6. Logging for every open path

The `[FILE] <path> … FAILED` / `[FILE] <path> (disp … opts … from …) -> 0x…` block moves from `bridge_NtCreateFile` into `bridge_create_file_impl`, together with the `xbox_FileOpenHook` call. The guest path comes from `name.Buffer`, which `bridge_build_oa` already filled from the same `OBJECT_ATTRIBUTES`; the 159-character truncation stays. That way `NtOpenFile` and `IoCreateFile` both log and feed the scripted-pad hook.

`bridge_NtCreateFile` keeps the async-handle note and the `RENV_FMV_HOST` hook, which need the handle written by `bridge_create_file_impl`. The only ordering change is that the `[FILE]` line now prints before anything the host FMV player prints. That player runs only under `RECOMP_FMV_HOST`, which is off by default.

BLiNX also opens through NtOpenFile: the partition devices, `U:\`, `d:\tank_tex.ipk` and its `z:` cache temporaries, which printed nothing before. With the report off, its log is the old one with those NtOpenFile lines added and nothing removed or reordered (implementation check, tasks §3.2: 13 added lines in a 60 s `@attract`, 0 removed).

**Repeats of a reported path are not printed (user decision, 2026-10-06).** A looping stream that re-opens a missing file printed one FAILED line per attempt (97 in the spike's worst case). In the default mode:
- the first failed attempt at a path prints its FAILED line as today, followed by the `[FILE] missing` line;
- once a path is in the table as a high-confidence miss, later FAILED lines for it are left out and counted (`repeats`), and the summary says how many;
- `xbox_FileOpenHook` is still called on every attempt, so scripted pads see each one.

What is not suppressed, and why:
- **Low, other and probe paths.** The default mode does not report them, so their FAILED lines are the only trace of them. They are short runs (5 per path in every spike log).
- **Paths past the 4096 cap.** The table cannot recognise them; they are counted as `unnamed`.
- **`RECOMP_TRACE=missing=all`.** Verbose prints every attempt, so nothing is lost when debugging a title. Its summary reports `0 repeats not printed`, and `missing_list` carries each path's attempt count.
- **`RECOMP_TRACE=missing=0`.** The report is off, nothing is recorded, and every FAILED line prints exactly as before this change.

Two threads failing the same new path at once may both print a FAILED line: the check and the insert are separate lock holds. That costs at most one extra line per racing thread, never a lost `missing` line.

### D7. POSIX open status and error code match Win32

In POSIX `xbox_NtCreateFile`, when `open` fails with `ENOENT` and the parent directory of `host_path` does not exist (`xbox_host_parent_exists`, D3), the status is `STATUS_OBJECT_PATH_NOT_FOUND`. The Win32 backend already returns this through `ERROR_PATH_NOT_FOUND` (`kernel_file.c:310`), and so does the console. The guest's IO_STATUS_BLOCK already gets the returned status (`bridge_create_file_impl` writes `st` on failure), so nothing else changes there.

`g_xbox_last_file_error` gets the Win32 code:
- 2 (`ERROR_FILE_NOT_FOUND`) for `ENOENT` with the parent present;
- 3 (`ERROR_PATH_NOT_FOUND`) for `ENOENT` with the parent absent, and for `ENOTDIR`;
- 5 (`ERROR_ACCESS_DENIED`) for `EACCES`/`EPERM`;
- 80 (`ERROR_FILE_EXISTS`) for `EEXIST`;
- 32 is never produced on POSIX.

The `[FILE] … FAILED` line then reads `win32 err=2 ERROR_FILE_NOT_FOUND` on every host.

**Scope: the open path only.** `xbox_NtQueryFullAttributesFile` and `xbox_NtDeleteFile` return NAME_NOT_FOUND for a missing file *and* a missing directory on Win32 today (`kernel_file.c:670`, `:423`), and POSIX does the same. The two backends already agree there, and the Win32 backend is the control for the Burnout 3 gate, so neither is touched. (`g_xbox_last_file_error` is one plain global shared by every thread on both backends; that is a pre-existing race in the per-attempt line and is left as it is.)

This is the one guest-visible change. A title that branches on PATH_NOT_FOUND versus NAME_NOT_FOUND now sees on the Mac and Linux what it already sees under Proton. The risk is a title that worked on POSIX only because of the wrong status. So it is its own commit, and it is gated on BLiNX 2 (Mac, Metal goldens) and on Burnout 3 under Proton. The Proton run exercises the Win32 backend, which this decision does not change: it is the control that proves the shared code (D3, D6) did not move Burnout 3, and it cannot exercise D7 itself. D7 on Burnout 3 is covered only by a Mac run, which happens when Burnout 3 boots there; until then TASKS records it as an open gate.

### D8. Keys

| tier | key | values | meaning |
|---|---|---|---|
| trace | `missing` | unset/`1` (default), `0`, `all` | the missing-file report (D4) |
| debug | `missing_list` | `=path` | at each summary point, write the unique misses as `<class> <guest> <host>` lines (truncating). Debug tier because it writes a file |

Both rows go in `RECOMP_ENV_KEYS` with no old alias (`NULL`), appended after `VBLANK_CLOCK` and before the enhancement and game hooks, so every existing id keeps its value. The trace tier says "printing only", which fits `missing`. Its row text says "default on; =0 off", because it is the one trace key that is on when unset. `docs/env.md` gains a row in each table, the tier counts in its header go up by one each (`scripts/test_env_doc.py` checks them), and its intro notes that `missing` is on when unset.

### D9. Hosts agree

The reporter, the classifier and the moved log block are host-independent C in the bridge and the path layer. The backend-specific pieces are:
- `xbox_host_parent_exists` (D3), written to give the same answer for the same tree on both;
- the D7 status mapping, POSIX only, which makes POSIX match what Win32 already does;
- the POSIX fill of the thread-local last host path (D3), which makes POSIX match what Win32 already does;
- the window-close summary sites (D5), Win32 only, because the SDL window exits through `exit()` and `atexit` covers it.

Win32 covers Windows and Proton. POSIX covers macOS and Linux. The ctests (tasks §6) run on the Mac and under Proton (`tests/proton_run.sh`), and assert the same statuses, error codes and lines on both.

The render backends (CPU, D3D11, Metal) are untouched apart from the four one-line exit hooks.

### D10. Upstream README adherence

The toolkit README describes the kernel as "Xbox kernel → Win32" and lists only the Python tests. Nothing in this change contradicts it; two parts are fork-only until the POSIX host lands upstream:
- D7 and the thread-local fill are in the POSIX backend, which upstream does not have.
- The keys use the fork's `recomp_env` table. An upstream port would carry a `getenv` spelling (`RECOMP_MISSING_FILES`) in place of the two rows.

The reporter, the classifier, the moved log block and the exit hooks are host-neutral and could go upstream as they are. The README's "Unreleased" changelog gets one bullet under Kernel, as fork commits do for runtime behaviour the user can see (ec7e243 is the pattern).

## Risks / Trade-offs

- **Startup cost.** None. Work happens only on a failed open, which is rare: 14–230 per 100 s in the spike. The table is static (about 2 MB for 4096 slots of two `MAX_PATH` strings) and touched only on a miss.
- **Lock order.** `xbox_missing_note` takes its own mutex only to probe and insert in the table. The `stat` and the print happen outside it. It holds no kernel lock, and the caller holds none of its locks.
- **Case-sensitive Linux filesystems.** Wrong-case names report as missing. That is arguably correct, since the title would fail there too. Case folding is a separate change.
- **A title with a whole directory missing** reports only counts by default. The summary line says how to list them (`missing=all`).
- **PATH_NOT_FOUND on POSIX** could change a title's branch. The Burnout 3 gate under Proton covers the shared code; D7 itself on Burnout 3 waits for a Mac boot (D7). The change can be reverted on its own (separate commit, tasks §4).
- **Repeats are hidden by default** (D6). A log reader who needs every attempt sets `missing=all`; a script that counted FAILED lines for a reported path reads the summary's attempt count or `missing_list` instead. Pads use the hook, which still sees every attempt.

## Migration Plan

Toolkit branch `feat/runtime-missing-files` off `posix-host/portability`, and cat branch `feat/runtime-missing-files` off `main`. Squash-merged per the workspace rules. Land it after `feat/toolcli-2-shims` merges, because both touch `docs/packaging.md`'s troubleshooting list (that branch deliberately left the entry for this change).

Rollback:
- the report: `RECOMP_TRACE=missing=0`;
- the status change: revert its commit.

## Open Questions

None. The user settled these (2026-10-06):
1. The dump is complete now.
2. Low-confidence lines are verbose-only.
3. PATH_NOT_FOUND ships with the report and is gated on Burnout 3.
4. Repeats of a reported path's FAILED line are not printed by default; verbose prints all of them (D6).
