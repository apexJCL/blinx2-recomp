# Tasks

- [x] `xbox_path_set_title_id`, called from `xbox_MemoryLayoutInit` with the certificate's id
- [x] Per-title default root in `xbox_path_init` (POSIX and Win32)
- [x] `xbox_path_adopt_legacy_saves`: copy UDATA/TDATA `<tid>` once, `.copying` then rename, marker
- [x] `tests/kernel_path` cases: adoption, failed copy and retry, stale copies, times, per-title default root (POSIX and Win32); links and a four-process race (POSIX)
- [x] Toolkit `src/kernel/README.md`; cat `docs/env.md` and env header rows
- [x] Two games with no `RECOMP_HDD_DIR` on the Mac: separate Cache dirs, a copied save found
- [x] Review fixes (review): failed copy hides nothing and retries, `.copying.<pid>`, links, times and flushes, Win32 overflow and `RECOMP_SAVE_DIR` agreement, docs
- [x] `kernel_path` ctest natively on Windows (bench host-win, PC lock)
- [x] Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL, cat pytest and ruff, build-all on the PC, Windows D3D11 golden built on bench host-win

## Results (2026-10-30, first round)

- Toolkit `feat/hdd-per-game` c1e87cc7: `tests/posix_ctest.sh` 0 FAIL (129
  pass, 3 skip, the rest n/a); `kernel_path` and `kernel_memory_bridge_posix`
  pass.
- cat: `uv run pytest scripts` 149 pass, 1 skip; ruff check and format clean.
- build-all on c1e87cc7: windows 6/6 natively on bench host-win
  (`runs/build-all/20261030-212332-hdd-per-game-win`), macos 6/6.
- Mac run check (`notes/hdd-per-game/macrun.sh`, headless CPU, no
  `RECOMP_HDD_DIR`, `XDG_DATA_HOME` on a clone of the shared root): BLiNX 2
  made `xboxrecomp/4d530065`, BLiNX 1 `xboxrecomp/4d530013`, each with its
  own `Cache`; each copied its own UDATA/TDATA once (marker written); a
  second BLiNX 2 run copied nothing and opened
  `U:\13C91777168C\blinx2data.bin` from the per-title root (its access time
  moved). The shared root was left as it was.
- Native Windows D3D11 golden, exe built on bench host-win (`cat_recomp.exe`
  e9a21f56fe0b, `notes/hdd-per-game/pc.sh`): attract pass-with-known,
  stage1 pass, story pass-with-known.

## Results after the review (2026-10-30)

- Toolkit `feat/hdd-per-game` c1973b7c: `tests/posix_ctest.sh` 0 FAIL (129
  pass, 3 skip, 18 n/a); `kernel_path` passes on the Mac with every new case.
- The Win32 backend ran natively for the first time: `kernel_path_test.exe`
  (llvm-mingw cross-build of c1973b7c) on bench host-win under the PC lock,
  `%TEMP%` and `%LOCALAPPDATA%` on `D:\bench\scratch\hdd-per-game-ctest`: OK,
  0 failures, 81 checks, including the default root from `%LOCALAPPDATA%`,
  the copy, a failed copy (a file held with no sharing, error 32) and its
  retry, stale copies and kept times. The first round's "both backends"
  meant the code was shared; only POSIX had run then.
- cat: `uv run pytest scripts` 149 pass, 1 skip; ruff clean.
- build-all on c1973b7c: windows 6/6 natively on bench host-win
  (`runs/build-all/20261030-223808-hdd-per-game-win`), macos 6/6
  (`runs/build-all/20261030-222817-hdd-per-game-mac`).
- Native Windows D3D11 golden (cat 4874acc, `notes/hdd-per-game/pc.sh`, runs
  in the shared `bench-logs/20261030-224600`, `-224927`, `-225308`): the
  bench verdict is REGRESSION on all three only because CLI main 81f028e
  wants `[ENHANCE] mods=none` and the toolkit (this branch and
  `posix-host/portability`) still logs `mods=camera.free` with
  `camera.free=off`; frames were not compared. Rechecked with
  `--allow-enhance mods=camera.free`: attract pass-with-known,
  stage1 pass, story pass-with-known, as in the first round.
  Flips/s 35.6, 33.4, 49.7 (first round 34.7, 33.5, 48.9).

## Results after the second review (2026-10-30)

Fixes in toolkit c2ea0ac7: an empty destination counts as absent (the game
makes an empty `TDATA/<tid>` at boot), so the retry is no longer defeated;
a folder saved into after a failed copy is kept, with no marker, and named
in the log for a copy by hand (`.legacy-saves-failed-<NAME>` notes); Win32
read-only files (flush and stale-tree delete); a refused `futimens` or
`utimensat` is a warning; the copy's top folder must be new; the root is
flushed before the marker and macOS uses `F_FULLFSYNC`.

Both branches rebased onto toolkit `posix-host/portability` 1fb81a14 and
cat main b4e9e29 before the final gates:

- Toolkit c2ea0ac7: `tests/posix_ctest.sh` 0 FAIL (130 pass, 3 skip, 18
  n/a, `usb_pad_game` included); `kernel_path` passes with the new retry
  cases.
- `kernel_path_test.exe` (cross-build of c2ea0ac7) natively on bench host-win
  under the PC lock: OK, 0 failures, 100 checks, the retry cases and the
  read-only save and stale tree included.
- cat: `uv run pytest scripts` 149 pass, 1 skip; ruff clean.
- Native Windows D3D11 golden (`notes/hdd-per-game/pc.sh`, no
  `--allow-enhance`, `[ENHANCE] mods=none` logged; shared
  `bench-logs/20261030-233436`, `-233741`, `-234142`): attract
  pass-with-known, stage1 pass, story pass-with-known.
  Flips/s 35.8, 33.5, 49.6. The run before the rebase (cat eb5a1e8,
  toolkit 1de470cf) gave the same verdicts.
