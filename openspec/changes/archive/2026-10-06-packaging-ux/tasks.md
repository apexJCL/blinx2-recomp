## 0. Before implementation

- [x] 0.1 Branch `feat/packaging-ux` off cat main (1a6cf48), in its own worktree. No toolkit worktree: the toolkit is used read-only, and its follow-ups are listed in 8.
- [x] 0.2 Fable read and improved this spec (commit `openspec: packaging-ux review (Fable)`). Decided by the user: the icns uses the rounded-rect layout; `RECOMP_KEYBOARD=1` is on by default in the windows and steamos defaults; the macOS pad and audio are already confirmed with `RECOMP_HOST_PAD=1`, so 6.3 is a re-check.
- [x] 0.3 Standing test rule, from now on: every run of a packaged launcher sets `BLINX2_DATA_DIR`, and `HOME` too on macOS, to a scratch directory under the session scratchpad, never the real user-data folder (design 5).

Order: sections 1 (small, fixes a real bug), 2 (the one-liner), 3 and 4 (icon), 5 (progress view, the largest and the most cosmetic, so last), then the gates. One commit per section, each leaving `pytest scripts` green, so the branch can merge even if 5 is cut short.

## 1. User data, pads and small follow-ups

- [x] 1.1 `BLINX2_DATA_DIR` in `BLiNX2.in` and `launcher.c` (one small data-dir function each), with a "Launcher variables" section in `docs/env.md` and a note in `docs/packaging.md`.
- [x] 1.2 The macOS launcher data-dir test: run the script with a fake `cat_recomp` that prints its environment, a scratch `HOME` and data dir; assert `RECOMP_HDD_DIR`, `RECOMP_ENHANCE_CONFIG` and `RECOMP_STDIO_LOG` are under scratch and a sentinel "real" dir is byte-identical. The Windows launcher is checked under Proton (7.3); no host-compiled seam.
- [x] 1.3 `launch.env.default.macos`: `RECOMP_HOST_PAD=1`. `launch.env.default.windows`: `RECOMP_KEYBOARD=1`. Add the key map (copied from the toolkit source) to the windows and steamos README parts, and "use a controller" to the macOS README part. A test asserts the keys are in each default file.
- [x] 1.4 `BLiNX2.in` `fail()` through `on run argv`, with the stubbed-`osascript` test (`a "quoted" \ path` arrives unchanged).
- [x] 1.5 Docs: `pipeline.sh build` on Linux cross-builds Windows (in `docs/packaging.md` and the `pipeline.sh` help).
- [x] 1.6 Incomplete-dump warning (added by the coordinator after the menu-music investigation): `package_lib.missing_media` scans the XBE's name-like strings and lists those that look like files of `adx/`, `voice/` or `movie/` (same name family, with at least two files in that folder, and the same digit/letter shape as one of them) but are absent from `game_files/`. `doctor` and `package` print the list and say to extract the disc again; warn only, never refuse. The XBE has no file list (it builds `adx\%s.adx` from names held elsewhere), hence the heuristic. Synthetic fixture in `test_package_lib.py`; on the user's dump it lists 9 songs, 2 movies and 30 voice lines.

## 2. One-liner (`blinx2.py`, `blinx2.cmd`)

- [x] 2.1 Running with no arguments packages for the native target. `blinx2.cmd` with no arguments does the same.
- [x] 2.2 The generation key, `src/recomp/gen.key.json` (gitignored):
  - Split each stage into `stage_x_argv(extra)` plus the runner, so the argv hash and the test see the same lists.
  - `gen_key()`: `xbe_sha256`, `toolkit` (commit, `git diff HEAD -- tools/`, plus the contents of `ICALL_DB` when present), `inputs` (`seed_functions.json`, `ICALL_DB` or `"absent"`, the ghidra export when it ran; enumerate by reading the stage functions), `argv`, `extra`, `ghidra`, `GEN_KEY_VERSION`.
  - Every stage command deletes the key first; `recomp` writes it on success.
  - Tests: each listed input exists or is marked absent; changing each one, creating `ICALL_DB`, and changing a stage argv all make the key stale; a snapshot of the stage argvs (placeholders for ROOT and the toolkit) so a stage change is a visible test diff.
- [x] 2.3 The `package` plan: setup when needed (from `doctor_report(target)`), generate when stale, then build and package. It prints a plan line first, naming the stale field. Add `--no-setup`. When a fix setup cannot do itself (Xcode CLT, distribution makensis) is missing, stop with doctor's one-line fix.
- [x] 2.4 Packaging build dirs:
  - `build-pkg-macos/` and `build-pkg-win/` (steamos shares `build-pkg-win/`), configured on every run with the stock options (`Release`, `XBOXRECOMP_ENHANCE=ON`, `-UCAT_GEN_OPT`, `CAT_APP_ICON`);
  - `--reconfigure`;
  - the refusal message names the option and prints the fix command; `cache_problems` ignores `CAT_APP_ICON`.
  - `build/` and `build-win/` are never touched. A test with fake cmake proves that a `build/` cache with `XBOXRECOMP_ENHANCE=OFF` no longer blocks `package`.
- [x] 2.5 Help split into "Commands" and "Developer commands". Update the module docstring and `README.md` quick start to show only `./blinx2` and `blinx2.cmd`.
- [x] 2.6 `scripts/test_blinx2_cli.py`:
  - the no-arguments mapping per mocked platform;
  - plan skipping: everything present means build and package only;
  - a stale key means generate, with the field named;
  - no toolchain means setup first;
  - the packaging dir args;
  - the refusal text.

## 3. Game icon (`scripts/game_icon.py`)

- [x] 3.1 XBE section lookup (`$$XTIMAGE`, then `$$XSIMAGE`) and the XPR0 header parse (magic, sizes, `Format` at byte 24, `Data` offset, dimensions, bounds checks).
- [x] 3.2 BC1, BC2 and BC3 decode to RGBA8. The PNG writer. The Catmull-Rom upscale in premultiplied alpha. The box-filter downscale. Time the 1024 level; over 30 s, use Catmull-Rom to 512 plus a 2× bilinear step (design 4.4). Measured: the whole icon set takes 1.4 s on the Mac (Python 3.14), so no fallback step.
- [x] 3.3 The `.icns` writer (`icp4`, `icp5`, `ic07`, `ic08`, `ic09`, `ic10`, PNG entries) with the macOS rounded-rect layout. The `.ico` writer (16, 32, 48, 256, PNG entries).
- [x] 3.4 The generic fallback icon, drawn in code, and the `icon: generic (<reason>)` line. The `icon.key` cache in `build-pkg-*/icon/` (XBE sha256 plus the tool's version constant).
- [x] 3.5 `scripts/test_game_icon.py`:
  - a synthetic XPR0 (16×16 DXT1, DXT3 and DXT5) with known colours decodes exactly;
  - the BC1 1-bit alpha;
  - bad magic, an unknown format and a truncated data block fall back;
  - PNG, icns and ico structure checks (chunk CRCs, entry offsets and sizes);
  - scaling the image keeps a solid colour solid;
  - the cache key skips a rebuild and a changed XBE forces one.
- [x] 3.6 `private_leaks` and the staged-tree checks know the icon names. `game_icon.py` refuses an output dir inside the source tree, except `build-*/` and `dist/`. `.gitignore` gains `*.ico` and `*.icns`.

## 4. Icons in the bundles

- [x] 4.1 macos: `BLiNX2.icns` in `Resources`, plus `CFBundleIconFile` in `Info.plist.in`.
- [x] 4.2 windows: `packaging/windows/BLiNX2.rc.in`, compiled with llvm-mingw `windres` and linked into `BLiNX2.exe` (`build_launcher_exe`).
- [x] 4.3 `CMakeLists.txt`: the opt-in `CAT_APP_ICON` option (default empty, so nothing changes). When set on a Windows target it enables `RC`, configures the `.rc` into the build dir and adds it to `cat_recomp`; the toolchain file provides `CMAKE_RC_COMPILER` if CMake does not find it. Verify that a configure without it gives the same build as today (the `ninja -t commands` diff is empty).
- [x] 4.4 NSIS: `MUI_ICON` and `MUI_UNICON`, with the shortcuts naming `BLiNX2.exe,0`.
- [x] 4.5 steamos: `icon.png` in each version dir. `install_lib` writes `<root>/BLiNX2.desktop` (`Type`, `Name`, `Exec`, `Icon`, `Terminal`, quoted paths) and passes it to `steamos-add-to-steam`. Tests run against a fake root and a stubbed helper, and check the desktop entry's contents and the helper's argv.
- [x] 4.6 The shown name is just the game's (user decision): `package_lib.PRODUCT_NAME = "BLiNX 2"`, the one place it is written. Templates carry `@NAME@` (NSIS title, Section, shortcuts, finish page and `DisplayName`; `Info.plist` `CFBundleName`/`CFBundleDisplayName`; the macOS and steamos alert titles; `README.txt`); `launcher.c` gets it as `-DBLINX2_NAME`; the manifest records it as `name`, and the steamos installer reads it from there for the `.desktop` `Name` (the Steam shortcut's name). No "(recomp)" anywhere a player sees; `src/main.c`'s window title is changed on its own branch.

## 5. Progress view (`scripts/progress.py`)

- [x] 5.1 The view with tty, line and plain modes:
  - mode selection (`--plain`, not a TTY, `CI`, `TERM=dumb`);
  - repaints at no more than 10 Hz from the main thread, so elapsed time ticks while the child is silent;
  - width-safe truncation; ASCII glyphs unless stdout is UTF-8;
  - Windows VT enable through ctypes, falling back to line mode.
- [x] 5.2 `run_step(name, argv, parser)`: `stderr=STDOUT`, a reader thread splitting on `\r` and `\n` with `errors="replace"`, tee to `build-logs/<stamp>-<step>.log`, feed the parser, and on failure print the exit code, the last 40 lines and the log path. Add `--verbose` (implies plain), and prune to the newest 20 stamps inside `build-logs/` only.
- [x] 5.3 Parsers, each a regex anchored at the fragment start and tolerant of a changing total:
  - Ninja `[n/m]` (setting `NINJA_STATUS`);
  - recomp `Translating N functions...` and `[i/n]`;
  - the disasm `NN%` lines, which arrive through `\r`;
  - makensis `-V3` `File:` lines against the `nsis_lists` count;
  - hdiutil `-puppetstrings` `PERCENT:` lines, with `-1` as done.
  - Download bytes go through `download()`'s chunk loop.
- [x] 5.4 The ETA text from `build-logs/timings.json`, written after each successful step; a spinner when there is no history. The bar never moves on an estimate.
- [x] 5.5 Wire the plan steps of 2.3 through `run_step`.
- [x] 5.6 `scripts/test_progress.py`:
  - each parser on captured sample lines (synthetic, no game names beyond the tool format), including a non-matching stream that leaves the view in spinner mode;
  - mode selection and the ASCII fallback;
  - plain mode never emits `\r` or ESC;
  - the failure tail;
  - log pruning stays inside `build-logs/`;
  - a stalled fake child (sleeps 1 s, prints nothing) still gets repaints.

## 6. Mac gates

- [x] 6.1 Unit tests:
  - the new suites;
  - the existing 45 packaging tests (`test_blinx2_cli`, `test_package_lib`, `test_running_game`, `test_steamos_install`);
  - all of `pytest scripts` with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`.
- [x] 6.2 A fresh clone into the session scratchpad, with the user's dump linked as an APFS clone, then a single `./blinx2` (the native macos target), from nothing to a DMG.
  Done: 18:55 from nothing to a DMG (setup 0:19, toolkit 0:02, disasm 0:27, funcid 1:38, abi 0:11, recomp 9:31, build 5:46, app and DMG 0:58).
  - Record the progress view: a terminal capture of the tty mode, plus a `--plain` run's log.
  - Record the plan line, and the total time against the packaging-deploy 9.1 sum.
  - The Mac's own `build/` (if any) stays unchanged.
- [x] 6.3 The app icon in Finder and the Dock: mount the DMG, then `open --env BLINX2_DATA_DIR=<scratch> --env HOME=<scratch>`, with a scratch `launch.env` holding `SDL_AUDIODRIVER=dummy` and `RECOMP_WINDOW_QUIT_AFTER=20`. Take a screenshot to `runs/packaging-ux/` (outside every repo). Run `iconutil -c iconset` on the `.icns` as the round-trip check.
  Done except the screenshot: the agent has no screen-recording permission, so the Dock and Finder icon is for the user to check. Info.plist names BLiNX2.icns and "BLiNX 2"; `iconutil` gives 6 images; the log shows `host=on`; the real Application Support folder was untouched. The real-controller check is the user's.
  - Check that `[INPUT] sources: … host=on` is in the scratch log.
  - The user has already confirmed pad and audio with `RECOMP_HOST_PAD=1` in the packaging-deploy app. Ask the coordinator for one final re-check of the rebuilt app with the new defaults (controller, sound, on their own data).
- [x] 6.4 A second `./blinx2` with nothing changed: the plan is build and package only, Ninja does no work, the icon is not rebuilt, and it takes under a minute before the wrap step.
  Done: plan "build, package"; Ninja no work; icon cached; 3 s before the wrap step, 61 s in all (hdiutil 58 s).
- [x] 6.5 `./blinx2 package windows` on the Mac: `BLiNX2.exe` and `cat_recomp.exe` carry the icon (`llvm-objdump --section=.rsrc`, or `llvm-readobj --coff-resources`, shows the `RT_ICON` and `RT_GROUP_ICON` entries). The NSIS setup.exe carries it too. The icon file in `build-pkg-win/icon/` matches the extracted PNG.
  Done: 5:10 in all; both exes and the setup.exe have ICON and GROUP_ICON, and every `.ico` image sits byte for byte in both exes; the plain log has no CR or ESC.
- [x] 6.6 A grep of the commit diffs finds no `.png`, `.ico` or `.icns` and no game bytes. `git status` is clean of icon files after a package run.
  Done: no media or binary files in the diff since 1a6cf48; `git status` clean after both package runs.

## 7. Linux PC (deferred: the Linux PC is held by other agents; folded into packaging-deploy 9.x)

- [x] 7.1 With 9.3: `./blinx2` on the PC (native steamos) from a fresh clone. The progress view under Konsole, and over ssh, where it uses plain mode.
  Done: the plain run over ssh is in 9.3. Under a pty (Python's `pty`, as Konsole would give) the tty view repaints with ANSI codes and the rerun takes 6 s. Konsole itself is for the user to see. The recomp bar sat at 0 for the whole step on both hosts (the translator prints no `[i/n]` lines without `-v`); fixed on `fix/packaging-linux-gates`.
- [ ] 7.2 With 9.4 and 9.5: the steamos install shows the icon in Steam (the `.desktop` route, else the grid `_icon` fallback; record which). A Proton run logs `[INPUT] sources: … host=on keyboard=on`. Investigate the `shortcuts.vdf` appid and `config/grid/` files; build grid art only if it needs no Steam restart and no write to `shortcuts.vdf`, else record a follow-up.
  - Archive note (2026-10-06): the Steam half waits for the user with packaging-deploy 9.5 (TASKS.md).
  Partly done: every Proton run logs `[INPUT] sources: script=off host=on keyboard=on`. The icon in Steam waits for 9.5. `steamos-add-to-steam` only opens `steam://addnonsteamgame/<path to BLiNX2.desktop>`, so whether Steam takes the entry's `Icon=` shows only then. Grid art is a follow-up: Steam reads `userdata/<id>/config/grid/<appid>_icon.*` keyed by the shortcut's appid, which only exists once Steam has written `shortcuts.vdf`.
- [x] 7.3 With 9.6: the windows bundle under Proton shows the installer icon and the exe icon, the latter in the file manager and through `wrestool` if available. `BLiNX2.exe` with `BLINX2_DATA_DIR` set writes its log and saves under that dir and nothing under `%LOCALAPPDATA%\BLiNX2`.
  Done: `BLiNX2.exe` and `cat_recomp.exe` from both setups carry ICON and GROUP_ICON (`llvm-readobj`; no `wrestool` on the PC). The `BLINX2_DATA_DIR` run is in 9.7. The icon as the file manager shows it is for the user to see.

## 8. Follow-ups (recorded in TASKS.md, not done here; 8.1 and 8.2 are toolkit changes)

- [ ] 8.1 A keyboard in the SDL input backend (`input_backend.h` `keyboard` slot from `SDL_GetKeyboardState`), so `RECOMP_KEYBOARD=1` works on macOS.
  - Archive note (2026-10-06): follow-up, in TASKS.md.
- [ ] 8.2 An optional `PROGRESS i n` machine line from the recomp translator, every 1%, making the ETA text in 5.4 unnecessary.
  - Archive note: follow-up, in TASKS.md.
- [ ] 8.3 The macOS SDL pad path is confirmed by the user. Consider changing `pad_input.c`'s unset default on non-Windows hosts, keeping goldens unaffected since they set their own keys.
  - Archive note: follow-up, in TASKS.md (waits for the user's confirmation).
