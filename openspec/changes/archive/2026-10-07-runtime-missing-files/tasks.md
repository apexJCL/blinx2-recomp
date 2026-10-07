Worktrees: `wt/<name>/cat` and `wt/<name>/xboxrecomp`, both on `feat/runtime-missing-files`. cat branches off `main`, toolkit off `posix-host/portability`. Raw runs go to `xbox-recomp/runs/missing-files/`, never inside a worktree. Build on the Mac with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Mac runs are headless with `SDL_AUDIODRIVER=dummy`, with scratch `RECOMP_HDD_DIR`/`RECOMP_SAVE_DIR` and a `cp -c` copy of `game_files` for any removed-file case. Never touch the main `game_files` or `~/Library/Application Support/BLiNX2`.

Order: the sections run top to bottom. Each toolkit section ends with a Mac build and the ctests that exist at that point (the gate in §8.1), so a step that breaks the build or an existing ctest is found before the next one starts. Game runs come after every ctest passes. BLiNX 2 is gated before Burnout 3.

## 0. Spec review (before any code)

- [x] 0.1 Fable reads this change (proposal, design, the kernel-file-io delta) and improves it in place, then commits the revision on `spec/runtime-missing-files`.
- [x] 0.2 The implementing agent resumes only from Fable's revised commit.

## 1. Toolkit: the path layer (D2, D3)

- [x] 1.1 `kernel_path.c`: add `xbox_path_tree()` (D2), outside the backend `#if`. It shares `resolve_symlink`, `xbox_partition_device_digit` and the `s_rules` walk with `xbox_translate_path`, prints nothing, and returns UNKNOWN for a relative name. Declare it in `kernel.h` with the `XBOX_TREE_*` values.
- [x] 1.2 `kernel_path.c`, POSIX backend: fill the thread-local last host path at the end of a successful translation, as the Win32 backend does (`xbox_remember_host_path`), so `xbox_LastHostPath()` reads the path just translated on every host.
- [x] 1.3 `kernel_file.c`: add `xbox_host_parent_exists()` for each backend (`GetFileAttributesW` + `FILE_ATTRIBUTE_DIRECTORY` on Win32, `stat` + `S_ISDIR` on POSIX). A path with no separator has no parent.
- [x] 1.4 Build; run the existing POSIX ctest dirs (`kernel_object_paths`, `kernel_fatx_overwrite`, `kernel_directory`, `kernel_bridge`).

## 2. Toolkit: the reporter (D1, D3, D4, D5)

- [x] 2.1 New `src/kernel/kernel_missing.c` and `.h`:
  - `xbox_missing_note`, `xbox_missing_summary`, `xbox_missing_counts` (D3);
  - the D1 early-outs before any lock;
  - the mutex-protected case-folded table (4096 slots, no allocation), with the parent test and the print outside the lock;
  - the four atomic counters;
  - the D4 lines and the `missing_list` file;
  - an `atexit` registration on the first note, and the once-only guard (atomic exchange).
  Add the file to the kernel target in CMake.
- [x] 2.2 `kernel_bridge.c`:
  - call `xbox_missing_note` from `bridge_create_file_impl` on failure (`is_probe = 0`) and from `bridge_NtQueryFullAttributesFile` (`is_probe = 1`);
  - call `xbox_missing_summary("firmware")` in `bridge_HalReturnToFirmware` next to `RECOMP_ICALL_FEEDBACK_DUMP()`.
- [x] 2.3 The other exit points (D5):
  - `d3d8_device.c` (three `WM_QUIT` pumps) and `nv2a_pb_d3d11.c` (`WM_CLOSE`): `recomp_exit_hook_run("window")` before each `ExitProcess(0)`, the platform hook the kernel sets to the summary (the D3D tests link without the kernel);
  - `kernel_hal.c`: `xbox_missing_summary("bugcheck")` before the `ExitProcess` of `KeBugCheck` and `KeBugCheckEx`;
  - `xbox_memory_layout.c`, the watchdog: the counts-only line before `_exit(3)`, next to `apu_wav_close_nowait`, with no lock.
- [x] 2.4 Build; run the existing ctests.

## 3. Toolkit: logging for every open path (D6)

- [x] 3.1 Move the `[FILE]` success/FAILED block and the `xbox_FileOpenHook` call from `bridge_NtCreateFile` into `bridge_create_file_impl`, taking the guest path from `name.Buffer` and keeping the text and the 159-character truncation word for word. `bridge_NtCreateFile` keeps the async note and the FMV hook. In the default mode, skip the FAILED line when `xbox_missing_is_reported` says the path is a reported high miss, and count it (D6); the hook is still called.
- [x] 3.2 Check: a BLiNX `@attract` log before and after (Mac, same binary options, `RECOMP_TRACE=missing=0` on the new build) has the same `[FILE]` and `[PATH]` lines in the same order, plus the NtOpenFile lines this change adds and nothing removed (with the report off, nothing is suppressed). Keep both logs in `runs/missing-files/`.

## 4. Toolkit: POSIX status (D7), its own commit

- [x] 4.1 POSIX `kernel_file.c`, `xbox_NtCreateFile` only:
  - `ENOENT` with an absent parent directory (`xbox_host_parent_exists`) returns `STATUS_OBJECT_PATH_NOT_FOUND`;
  - set `g_xbox_last_file_error` from errno: 2, 3 (also for `ENOTDIR`), 5, 80.
  `xbox_NtQueryFullAttributesFile` and `xbox_NtDeleteFile` are not touched on either backend.
- [x] 4.2 Commit 4.1 on its own (subject `kernel_file: POSIX reports a missing directory as PATH_NOT_FOUND`), so that it can be reverted separately. Every other toolkit change sits in other commits.

## 5. Keys and docs

- [x] 5.1 `src/platform/recomp_env.h`, appended after `VBLANK_CLOCK`:
  - `X(MISSING, TRACE, "missing", NULL, "missing game files, one line each and an exit summary; default on, =0 off, =all also absent directories, other trees and probes")`;
  - `X(MISSING_LIST, DEBUG, "missing_list", NULL, "=path: the unique missing files, written at each summary")`.
- [x] 5.2 cat `docs/env.md`: a row in the Trace table and one in the Debug table, with the read-at file:line. Bump the Trace and Debug counts in the header (`scripts/test_env_doc.py` checks them), and note in the intro that `missing` is the one trace key on when unset.
- [x] 5.3 Toolkit `README.md`, "Unreleased", under Kernel: one bullet for the `[FILE] missing` report and summary, `RECOMP_TRACE=missing`, and the POSIX PATH_NOT_FOUND status.

## 6. Tests

- [x] 6.1 New ctest `tests/kernel_missing_report`. Over a temporary game dir it drives every D1 condition on and off and checks the outcome:
  - case-insensitive dedupe (`D:\adx\A.ADX` and `d:\adx\a.adx` are one path) and high/low by parent directory;
  - `FILE_OPEN_IF`, each write/append/delete access bit, `FILE_DIRECTORY_FILE`, a relative name, and a status other than the two NOT_FOUND values: none is reported or counted;
  - the HDD, user and device trees and a probe: reported only under `all`, counted as other/probe;
  - a `Z:` → `Partition1\` link classified as GAME;
  - `xbox_path_tree` over one path per rule, the bare devices, a relative name and an unrecognised path;
  - the 4096 cap: the 4097th unique path is counted, not named, and the cap line prints once;
  - the once-only summary (two calls, one line), `missing=0` (no line, no count) and the summary's counts for a known sequence;
  - repeats: after a high miss, `xbox_missing_is_reported` is 1 and the repeats counter rises per attempt; it stays 0 for low, other and probe paths, under `all`, under `0`, and for paths past the cap; several threads hammering the same and different paths leave the counts exact and the table consistent;
  - the `missing_list` file's format (`<class> <attempts> <guest> <host>`) and truncation on a second write;
  - a lock-free `xbox_missing_counts` read matching the summary.
- [x] 6.2 New ctest `tests/kernel_file_status`. Through `xbox_NtCreateFile` with a read-only `FILE_OPEN`: a missing file in an existing directory returns 0xC0000034 and `xbox_LastFileError()` 2; a file under a missing directory returns 0xC000003A and 3. Through `xbox_NtQueryFullAttributesFile`, both cases return 0xC0000034 (the backends agree and stay as they are). Assert the same on the Mac and under Proton.
- [x] 6.3 Run both on the Mac and under Proton (`tests/proton_run.sh`), plus the existing POSIX ctest dirs.

## 7. cat

- [x] 7.1 `src/main.c`, the common crash report: one `crash_printf` line `  [FILE] missing at crash: H high, L low` from `xbox_missing_counts`, printed only when H + L > 0, with no lock and no allocation, next to the `recent ICALL targets` block.
- [x] 7.2 `docs/packaging.md` troubleshooting: replace the "the dump looks incomplete" entry (left there by `feat/toolcli-2-shims` 1a0e8b7 for this change) with:
  - **Music, voices or a movie are missing, or the game says the disc is dirty or damaged:** a file is missing from `game_files/`.
  - The game's log (in `logs/`) names it on a `[FILE] missing` line, and the `[FILE] summary` line at the end counts them.
  - Extract the whole disc again.

## 8. Gates

- [x] 8.1 Mac build (CommandLineTools), the POSIX ctest dirs, and the new ctests, on the Mac and under Proton.
- [x] 8.2 Metal goldens (`scripts/golden.py`) on the Mac. Every golden matches.
- [x] 8.3 D3D11 goldens under Proton (`scripts/bench.sh golden`) on the Linux/Proton host, after `bench.sh integrate` of both branches. Every golden matches.
- [x] 8.4 BLiNX 2, Mac, the spike's cases re-run on a scratch copy of the current (complete) dump. Each run ends through `RECOMP_WINDOW_QUIT_AFTER` (the SDL host exits through `exit`, so the summary prints), not an `alarm` kill:
  - complete dump: no `[FILE] missing` line, no summary line, and the probe FAILED lines (camera scan, cache, saves) unchanged;
  - removed `adx\envse_r1_island_omote.adx` and `movie\title_movie_1a.sfd`: one `missing` line each, exactly once, one FAILED line each, and a summary of 2 high whose repeats count equals the attempts minus 2; with `missing=all`, one FAILED line per attempt again;
  - removed `media.ipk`: one `missing` line, the low count non-zero, and `missing=all` lists the fallbacks as `not found (no such directory)`;
  - removed `movie\logo_mgs.sfd`: one line, then the title's dirty-disc screen as before (an `fb_dump_at` frame, no screen capture);
  - `missing=0`: no new lines;
  - `missing_list=<path>`: the file holds the same paths as the lines.
- [x] 8.5 BLiNX 2 under Proton: one removed-file case (a copy of game files on the Linux/Proton host, under the run lock, BLiNX first). The same `missing` line appears as on the Mac, with `win32 err=2` on both hosts' FAILED lines. The run ends by the bench timeout, so no summary line is expected there; the summary under Win32 is covered by the ctest.
- [x] 8.6 **Burnout 3 under Proton (the control for the shared code, and the gate the user asked for):**
  - first a base run: the S6 route (boot, the menu's profile flow, a race; TASKS.md S6 round 3) on the `posix-host/portability` head without this branch, recorded in `bench-logs/`;
  - then the same route on the exact head of both branches, under the run lock, after BLiNX;
  - pass when it reaches the race as the base run did, the set of `[FILE] … FAILED` (guest path, status) pairs in the two logs is identical, and the complete dump prints no `[FILE] missing` line. Any added or changed FAILED pair is a regression from §2 or §3, since the Win32 backend is untouched;
  - record the run in `bench-logs/`.
  If Burnout 3 builds and boots on the Mac, run the same route there too: that is the only run that exercises §4 on Burnout 3. If it does not boot there yet, say so in TASKS.md as an open gate on §4.
  Result 2026-10-06 (host dir `~/xbr-assets`, driver `runs/missing-files/b3gate.sh`, compare `b3cmp.py`; b3 4788d52, gen 4118995396daf383 from current tools, dump `~/xbox-recomp/burnout_3` for both): base (posix-host/portability 4e9a2f2, `20261006-122823-base-race`) and new (4f35dea, `20261006-110030-new-race`) both reach the race (crash1.rws, E_djrace, tracks\US; 144 frames each on the host). FAILED pairs identical: `t:\$u\contentmeta.xbx` and `TDATA\FFFE0000\MUSIC\ST.DB`, both 0xC000003A. No `[FILE] missing` line. The Mac route was not run (B3 does not boot on the Mac yet): open gate on section 4.
  - Archive note (2026-10-07): the Mac route is still open, in TASKS.md as the open gate on section 4 (Burnout 3 does not boot on the Mac yet).
- [x] 8.7 Fable review of the merge. Its fixes go back to this branch's agent. Done: `notes/fable-reviews/2026-10-06-runtime.md` §1, no blocker. The two should-fixes are toolkit 99123b6 (`missing_list` written once; open successes only under `missing=all`) and cat a9e6262 (the env.md rows); CLI 9309837 adds both ctests to the Proton list.

## 9. After the merge

- [x] 9.1 Squash-merge both branches per the workspace rules, keep the branches, remove the worktrees, and sync and rebuild the Linux/Proton host, then run golden. Done 2026-10-06: toolkit f356dda (from 7690c89), cat 86bdcdf (from 25be705); the later post-merge integrates pass 8/8 goldens.
- [x] 9.2 Archive this change and sync the kernel-file-io delta into `openspec/specs/kernel-file-io/spec.md`.
- [x] 9.3 Update `TASKS.md`: close the menu-music item, record the optional ISO-against-extraction check (`tools/xiso/xdvdfs.py`) and the window-title hint as follow-ups that have not been started, and the Burnout 3 Mac run as an open gate on §4 if it did not happen. Done 2026-10-07 (the menu-music item closed: the re-extracted dump is complete).
