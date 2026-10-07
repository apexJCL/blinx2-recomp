## Why

When a dump lacks a file, the game does not crash. It goes silent, skips a movie or shows its own "There's a problem with the disc you're using" screen. Nothing tells the player or the developer which file caused it. The missing-assets spike (`spike/missing-assets` 90a53f7, `openspec/changes/missing-assets-spike/spike.md`; raw runs in `xbox-recomp/runs/missing-assets/`) ran BLiNX 2 ten times on the Mac with files removed and measured four gaps:

- **Failed opens repeat, and nothing sums them up.** `bridge_NtCreateFile` prints a `[FILE] … FAILED` line on every attempt. One missing looping ambience made 97 lines in 100 s. No line counts the misses or reports them at exit.
- **Real misses are mixed in with normal probes.** BLiNX scans numbered camera files until an open fails (`media\event\EVCAMST0101_005.CAM`). It rebuilds its `z:` texture cache on a miss and probes `U:`/`T:` save metadata. All of these look like misses in today's log.
- **Two open paths say nothing.** `NtOpenFile` and `IoCreateFile` share `bridge_create_file_impl` but print no `[FILE]` line. `NtQueryFullAttributesFile` prints nothing either.
- **Mac and Linux lose detail.** The POSIX backend never sets `g_xbox_last_file_error`, so every line says `win32 err=0`. It also returns `STATUS_OBJECT_NAME_NOT_FOUND` when the parent directory is absent, where Windows (and the console) return `STATUS_OBJECT_PATH_NOT_FOUND`.

Burnout 3 had the same failure. In S6 round 2 (TASKS.md), an incomplete dump showed its disc-error screen, and the error went away only after the dump was re-extracted.

The user decided (2026-10-06) that missing assets are not listed or checked at build or package time. If a file is missing, the runtime says so in a way that works for any game. The spike found one rule that is title-agnostic and separated real misses from probes in all ten runs.

## What Changes

- **A missing-file report in the toolkit kernel, for every title and host.** A guest open counts as a miss when all of these hold:
  - it fails with NAME_NOT_FOUND or PATH_NOT_FOUND;
  - it is a read-only `FILE_OPEN` of a non-directory;
  - its name is absolute (not relative to a `RootDirectory` handle);
  - its path, after the title's own drive links are resolved, falls in the game-files tree.

  A miss is *high confidence* when its parent directory exists on the host, and *low* otherwise.
  - **Default:** one `[FILE] missing <guest> -> <host>` line per high-confidence path, and one summary line with counts when the run ends.
  - **Verbose (`RECOMP_TRACE=missing=all`):** also prints low-confidence lines, misses in the HDD, save and cache trees, and failed attribute probes.
  - `RECOMP_TRACE=missing=0` turns the report off.
  - `RECOMP_DEBUG=missing_list=<path>` writes the unique misses to a file.

  The report prints log lines only and never changes what the guest sees.
- **Every bridged open path logs its failures.** The per-attempt `[FILE] … FAILED` line moves from `bridge_NtCreateFile` into `bridge_create_file_impl`, so `NtOpenFile` and `IoCreateFile` print it too. Its text does not change. In the default mode, once a path has been reported by a `[FILE] missing` line, its later FAILED lines are not printed; they are counted, and the summary says how many. `RECOMP_TRACE=missing=all` prints every attempt (design D6).
- **POSIX failed opens match Windows.** In `xbox_NtCreateFile`, `ENOENT` with an absent parent directory returns `STATUS_OBJECT_PATH_NOT_FOUND`, and `g_xbox_last_file_error` carries the Win32 code (2 or 3). The Win32 backend already does both, and stays untouched. Attribute queries and deletes keep returning NAME_NOT_FOUND on both backends, as they do today. A title can see this status change, so it ships as its own commit and is gated on Burnout 3 under Proton as well as on BLiNX 2.
- **The summary prints on every exit path the host controls.** `atexit`; `HalReturnToFirmware`; `KeBugCheck`/`KeBugCheckEx`; the Win32 window close, which ends in `ExitProcess` and skips `atexit`; the watchdog's `_exit`; and cat's crash handler (the last two print counts only, without a lock). A run killed from outside prints no summary; its per-path lines are already in the log.
- **Docs.** Two rows go in the toolkit `recomp_env.h` table and in `docs/env.md`. One bullet goes under the toolkit README's "Unreleased" changelog. In `docs/packaging.md`, the "the dump looks incomplete" troubleshooting entry becomes a pointer to `[FILE] missing` in the game's log.

Not in this change:
- **The BLiNX-specific `media_warning` / `missing_media` removal** is in toolchain-cli phase 2 (`feat/toolcli-2-shims`, packaging delta "An incomplete dump is reported, not refused"). That branch left `docs/packaging.md`'s entry and `docs/env.md` for this change (1a0e8b7).
- **An ISO-against-extraction check** using `tools/xiso/xdvdfs.py` stays optional, and would be a separate change if wanted.
- **On-screen hints.** The title's own disc-error screen already covers the misses that stop play.
- **A build-time asset manifest.** The spike measured 44–67% static coverage with no closed set, so it is rejected.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kernel-file-io`: adds the missing-file report, logging for every bridged open path, and console-faithful status for a missing parent directory.

## Impact

- **Toolkit (`xboxrecomp`, branch off `posix-host/portability`):**
  - `src/kernel/kernel_path.c`: a `xbox_path_tree` classifier, and the POSIX backend fills the thread-local last host path that Win32 already fills.
  - New `src/kernel/kernel_missing.c` and `.h`.
  - `src/kernel/kernel_bridge.c`: `bridge_create_file_impl`, `bridge_NtQueryFullAttributesFile` and `bridge_HalReturnToFirmware`.
  - `src/kernel/kernel_file.c`: the POSIX open status and error code, and a host parent-directory test for both backends.
  - `src/kernel/kernel_hal.c`: the summary before the `ExitProcess` of `KeBugCheck` and `KeBugCheckEx`.
  - `src/kernel/xbox_memory_layout.c`: one counts line before the watchdog's `_exit`.
  - `src/d3d/d3d8_device.c` and `src/d3d/nv2a_pb_d3d11.c`: the summary before each window-close `ExitProcess`, through a platform exit hook (`src/platform/recomp_exit_hook.c`) the kernel sets.
  - `src/platform/recomp_env.h`: two rows.
  - `README.md`: one "Unreleased" bullet.
  - Two new ctests.
- **cat:**
  - `src/main.c`: one counts line in the crash handler.
  - `docs/env.md`.
  - `docs/packaging.md`.
- **Behaviour:**
  - The guest sees no change on Windows and Proton.
  - On Mac and Linux the guest sees PATH_NOT_FOUND where it saw NAME_NOT_FOUND, for an open whose parent directory is absent.
  - The log gains at most one line per missing game file plus one summary line. No new `[PATH]` line and no new per-attempt line on any host.
  - Goldens compare frames, so they are unaffected. The gates still run them.
