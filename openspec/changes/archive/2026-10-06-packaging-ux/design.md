## Context

packaging-deploy (merged in 333358e) gave every host one CLI (`blinx2.py`) and three private bundle targets. This change is about the experience of using it. A player should get from a fresh clone to an installable bundle with one command, see how far along it is, and get the game's own icon. The packaged game must also run as the player expects: with sound, no test settings, and their controller working.

Measured on the Mac from a fresh clone (packaging-deploy 9.1):

| Stage | Time |
|---|---|
| `setup` | 30 s |
| `analyze` | 2 min 34 s |
| `recomp` | 10 min 13 s |
| `build windows` | 5 min 43 s |
| `build macos` | 7 min 3 s |

What we found about the XBE's title image (`$$XTIMAGE` in the user's default.xbe):

- The section is 10240 bytes, starting with `XPR0`, with a total size of 10240 and a header size of 2048.
- The texture's format dword is `0x07710c29`. That decodes to format 0x0C (DXT1), 1 mip level, and log2 width and height of 7: a 128×128 image with 8192 bytes of data at offset 2048.
- The XBE has no `$$XSIMAGE` section. The certificate holds no image, only the title name and ids.

## Goals / Non-Goals

**Goals**
- One command from a fresh clone (or after a `git pull`) to a bundle. It does only the work that is needed, and its stock-build check cannot be tripped by the developer's own build dirs.
- A live, honest progress view, with full logs on disk.
- The game's icon on every target, never in git, with a game-free fallback.
- Tests that never touch the player's real data. Packaged defaults that give a working pad.

**Non-Goals**
- Changing the runtime's stock defaults (`pad_input.c`, the window, audio).
- Any toolkit change. The toolkit follow-ups are listed below.
- Steam library grid art beyond the shortcut icon. It is investigated (task 7.2) and only built if it is cheap and safe.
- Prebuilt or distributed bundles. Nothing changes about privacy.

## Decisions

### 1. The one-liner

`./blinx2` with no arguments means `./blinx2 package <native>`, where native is `macos` on Darwin, `steamos` on Linux and `windows` on Windows. `blinx2.cmd` with no arguments does the same. `package <target>` then runs a plan of steps, each skipped when it is already satisfied.

1. **setup.** Runs when `doctor_report(target)` lists a missing tool or toolkit for this target: llvm-mingw, cmake and ninja in the venv, the toolkit checkout at its pin with its Python deps, makensis for `windows`, or the Xcode command-line tools for `macos`.
   - Setup cannot install the Xcode command-line tools or a distribution's makensis. When those are missing, the step stops with doctor's one-line fix.
   - `--no-setup` turns the step off, for developers who manage their own toolchain (`XBOXRECOMP_DIR`).
2. **generate.** Runs `analyze` and then `recomp` when the generation key (below) is missing, differs from the current one, or the `.gen-regenerating` marker is present.
3. **build.** Builds the packaging build dir for the target (decision 2).
4. **package.** Runs the existing stage, refuse and wrap steps, now with the icon (decision 4).

A plan line is printed first, so the user knows what will run and why. For example: `plan: setup (no llvm-mingw) · generate (toolkit changed) · build · package`.

**Generation key.**

- The key is `src/recomp/gen.key.json`, beside `gen/`. It is gitignored and written only after `recomp` succeeds. **Every** stage command (`parse` … `recomp`, `analyze`, `all`) deletes it before it runs, not only `analyze`: a developer who reruns one stage by hand with other arguments has invalidated gen/ just as surely, and an interrupted run must always regenerate. The stages never read the key.
- It holds:
  - `xbe_sha256`: the sha256 of `game_files/default.xbe`.
  - `toolkit`: the toolkit commit, plus `-dirty<hash>` when `tools/` differs from HEAD. The hash covers `git diff HEAD -- tools/` **and** the contents of every untracked or ignored file under `tools/` that a stage reads. The one that exists today is `tools/recomp/output/icall_targets.json` (`ICALL_DB`), which `stage_disasm` feeds to `icall_feedback` when present; it is gitignored in the toolkit, so a diff alone misses it. It is listed in `inputs` (below) as a path plus sha256, or `"absent"`. Runtime-only toolkit edits do not stale gen/, since they change only the build.
  - `inputs`: `{relative path: sha256 | "absent"}` for every file outside `gen/` that a stage reads and `package` does not produce itself: `config/seed_functions.json`, `ICALL_DB`, the ghidra export when the stage ran, and anything else task 2.2 finds by reading the stage functions. Stage *outputs* under `analysis/` (`icall_seeds.json`, `disasm/`, `func_id/`, `abi/`) are not inputs: they are reproduced by the run. The key records an absent optional input as `"absent"`, so a file that appears later makes gen/ stale.
  - `argv`: the sha256 of the argument lists the stages would run, with `ROOT` and the toolkit dir replaced by placeholders. The stage functions are split so each returns its argv (`stage_x_argv(extra)`) and the runner calls it; this also gives the test a cheap snapshot (task 2.2). An argument or ordering change then stales gen/ by itself, with no constant to remember to bump. `GEN_KEY_VERSION` stays as a schema version for the key file's own format.
  - `extra`: the extra arguments `recomp` was run with. `package` requires `[]`; a hand run with extras is never "fresh" for packaging.
  - `ghidra`: whether the optional ghidra stage contributed.
- `package` compares the recorded key with one computed now, field by field, and names the differing field in the plan line (`generate (toolkit changed)`, `generate (config/seed_functions.json changed)`). A missing key is `generate (no key)`.
- The key does not cover `gen/` being hand-edited. That is forbidden by the workspace rules, and `package` already records the gen digest in the manifest.

**Help.** argparse's epilog becomes two blocks:

- **Commands:**
  - `(none)`: package for this computer;
  - `package <target>`, `doctor`, `setup`.
- **Developer commands:** the pipeline stages, `build`, and `pins refresh`.

The developer commands keep working unchanged. `pipeline.sh` still wraps them.

### 2. Its own stock build (the stale-cache trap)

`package` never builds in `build/` or `build-win/`. It uses `build-pkg-macos/` and `build-pkg-win/` (the `steamos` target packages the Windows exe, so it shares `build-pkg-win/`), which `.gitignore`'s `build-*/` already covers. On every run it calls configure with the stock options, not only when the cache is absent:

```
-G Ninja -DCMAKE_BUILD_TYPE=Release -DXBOXRECOMP_ENHANCE=ON -UCAT_GEN_OPT
-DCAT_APP_ICON=<build-pkg-*/icon/...>   # decision 4
(+ the toolchain-file / LLVM_MINGW_ROOT / XBOXRECOMP_DIR args `build` already passes)
```

Re-running configure with the same values is a no-op for Ninja, so it costs about a second.

Why not reuse `build/`:

- It belongs to the developer, who may keep `XBOXRECOMP_ENHANCE=OFF`, `CAT_GEN_OPT` or a Debug type there on purpose. Flipping those behind their back would be a second trap.
- The cost is one extra full build, but only for someone who also builds by hand. A player has only the packaging dirs.

`cache_problems` still runs after the build, against the packaging cache. It does not look at `CAT_APP_ICON`, so the icon path in the cache is not "non-stock" (the stock check is about the game's behaviour, and the icon changes none). If it fails anyway (an option forced from the environment, or a stray `-D` passed through), the refusal names the option and prints the exact fix:

```
package: build-pkg-macos is not a stock build: XBOXRECOMP_ENHANCE=OFF (stock: ON)
  fix: ./blinx2 package macos --reconfigure    (or delete build-pkg-macos/)
```

`--reconfigure` deletes the packaging dir's `CMakeCache.txt` and `CMakeFiles/` and configures fresh. `--allow-debug` and `--allow-nonstock` stay as they are.

### 3. Progress view: hand-rolled, standard library only

**Chosen:** `scripts/progress.py`, a small view in plain ANSI. **Rejected:** `rich`, pinned in `requirements-setup.txt` with `--require-hashes`.

Why:

1. **Bootstrap.** The first long step a player sees is `setup` itself, downloading llvm-mingw (about 150 MB). That runs before any venv exists, so `rich` could not draw it.
2. **Pins.** It would add a dependency with per-platform wheel hashes to keep in `pins refresh`, for one screen.
3. **Size.** The view we need is about 200 lines: one bar, one status line and one log line.

The view has three modes:

- **tty.** Two lines, repainted at most 10 times a second with cursor-up plus `ESC[2K`:
  ```
  [3/4] build  windows  ████████████░░░░░░░░  612/1480  2:41
        ninja: Building C object src/recomp/gen/CMakeFiles/...
  ```
  The plan line stays above and finished steps scroll up as one summary line each (`✓ generate  12:47`). The bar width follows `shutil.get_terminal_size()`, and the text is truncated so nothing wraps. Glyphs: `█░✓·` only when `sys.stdout.encoding` is UTF-8; otherwise `#`, `-`, `ok` and `|`, so a cp1252 console never raises `UnicodeEncodeError`.
- **line.** For terminals without ANSI support. A single line, rewritten with `\r` and padded with spaces, which works in a legacy Windows console.
- **plain.** Used with `--plain`, when stdout is not a TTY, with `CI` set, or when `TERM=dumb`. One line per step start and end, plus a line every 10% at most. Nothing is rewritten, so logs and CI stay readable.

On Windows, tty mode is entered only after `SetConsoleMode(ENABLE_VIRTUAL_TERMINAL_PROCESSING)` succeeds through ctypes. If it fails, the view drops to line mode.

**Reading the child.** `run_step` starts the child with `stdout=PIPE, stderr=STDOUT` (one stream, so neither pipe can fill and deadlock) and reads it in binary on a reader thread, splitting on `\r` **and** `\n` (disasm rewrites its line with `\r`; Ninja and the rest use `\n`) and decoding with `errors="replace"`. Each fragment goes to the log file verbatim and to the parser. The main thread repaints every 100 ms from the parser's state, so elapsed time keeps ticking while a child is silent (recomp is silent for 30 s at a time). Parsers are regexes anchored at the fragment start, tolerant of a changing total (Ninja re-counts edges mid-build), and ignore anything they do not match; a parser that never matches leaves the bar in spinner mode, never an error. The child's stdout is a pipe, so tools print without colour on their own; `CLICOLOR_FORCE` and `FORCE_COLOR` are not set.

**Sources.** All of them come from output that exists today, so the toolkit is unchanged.

| Step | Progress source | Granularity |
|---|---|---|
| downloads (setup) | `Content-Length` vs bytes read in `download()` | per 64 KiB chunk |
| pip installs | one sub-step per requirement file | step |
| analyze: parse, funcid, abi, names | stage n/N | step |
| analyze: disasm | its `\r  <section>: … NN%` lines | per percent |
| recomp | `Translating N functions...` sets the total; `  [i/n] Translating …` (every 500, or every 100 on the other path) advances it | about 20 ticks over 10 min |
| build | `NINJA_STATUS="[%f/%t] "` set in the child's env, `[n/m]` parsed | per edge |
| makensis | `-V3` `File: "…"` lines vs the file count from `nsis_lists` | per file |
| hdiutil | `-puppetstrings` `PERCENT:` lines (`PERCENT:-1.000000` at the end means done, not an error) | per percent |
| codesign, staging, tar | step (staging counts files) | step or file |

Recomp ticks are coarse (about every 30 s), so the bar alone would look stuck. The bar still moves only on real ticks. Between them the view shows an **ETA text**, not a bar segment:

- `build-logs/timings.json` keeps the last duration of each step on this machine. With history the status reads `612/1480  2:41  ~7 min left`; the ETA is the remaining fraction of the recorded duration, rounded to a minute, and never counts below "under a minute".
- With no history, the view shows elapsed time and a spinner.

This was chosen over a dimmed "estimated" bar segment, which the first draft had: that is two kinds of truth in one bar, needs its own capping rules, and buys nothing a text ETA does not. A finer machine-readable progress line in the toolkit translator (`PROGRESS i n` every 1%) would make recomp ticks fine enough to drop the ETA. It is a toolkit change, so it is recorded as a follow-up and not done here.

**Logs.**

- Every child process writes its full stdout and stderr to `build-logs/<stamp>-<step>.log`. `build-*/` is already ignored. `build-logs/` is a plain directory, unrelated to `bench-logs/` (the symlinked bench store); it never goes there.
- On failure, the view clears and prints the step, its exit code, the last 40 lines and the log path.
- `--verbose` streams the child output as it does today, and implies plain mode.
- The newest 20 run stamps are kept. Older ones are pruned by name pattern, inside `build-logs/` only.

### 4. Game icon

`scripts/game_icon.py`, standard library only, also usable as a CLI (`python3 scripts/game_icon.py <xbe> <outdir>`):

1. **Find the image.** Use the section named `$$XTIMAGE`. Failing that, use `$$XSIMAGE` (save image). Failing that, there is no image.
2. **Parse XPR0.** The 12-byte file header is `XPR0`, total size, header size. It is followed by the texture's `D3DTexture` resource: `Common`, `Data`, `Lock`, `Format`, `Size` (five dwords, so `Format` is at byte 24), then the `0xFFFFFFFF` end marker. Pixel data starts at header size plus the `Data` offset (0 for the one-texture file we have).
   - The format field (bits 8–15) must be DXT1 (0x0C), DXT2/3 (0x0E) or DXT4/5 (0x0F). Width and height are `1 << ((fmt >> 20) & 0xF)` and `1 << ((fmt >> 24) & 0xF)`; the mip count is bits 16–19 and only level 0 is read. The user's `0x07710c29` decodes to DXT1, 1 mip, 128×128.
   - DXT textures are not swizzled on the Xbox, so blocks run in plain row order.
   - Any other format (swizzled ARGB, for example), a size over 1024, or a data length shorter than the blocks need counts as "no image" and falls back.
3. **Decode DXT.** Turn the blocks into RGBA8: BC1 with its 1-bit alpha (`c0 <= c1` selects the 3-colour mode), BC2, and BC3. This takes about 0.1 s for 128×128 in pure Python.
4. **Scale.** The source is 128×128, and we need sizes from 16 to 1024. The upscaler is a separable Catmull-Rom bicubic in premultiplied alpha, clamped to 0–255.
   - It was chosen over nearest-neighbour, which shows 8× blocks at 1024 and looks broken in the Dock and Finder. Title images are painted art, not pixel art.
   - It was chosen over Lanczos, which rings more on hard DXT block edges for little gain at 4–8×.
   - Downscaling to 16, 32 and 48 uses a box filter (area average).
   - 1024² separable Catmull-Rom in pure Python is on the order of 10–30 s (a million pixels, four channels, two passes of four taps). That is tolerable once, not on every run: the icon set is written to `build-pkg-*/icon/` beside an `icon.key` holding the XBE sha256 and a `game_icon.py` version constant, and is rebuilt only when that key differs. Task 3.2 measures the time; if it is over 30 s, the 1024 level is produced by Catmull-Rom to 512 followed by a 2× bilinear step, which is indistinguishable on a Dock icon.
5. **macOS shape.** For `.icns` only, the art is drawn at 824/1024 of the canvas in a rounded rectangle with a 185/1024 radius on a transparent canvas, following Apple's icon grid. Otherwise a square image shows square and slightly larger than every other Dock icon. `.ico` and the PNG stay full-bleed squares. **Decided by the user:** the rounded-rect layout, not full-bleed.
6. **Write the files.**
   - **PNG:** RGBA, 8 bit, through `zlib` and `struct`.
   - **`.icns`:** written in pure Python. The `icns` header holds PNG entries `icp4` (16), `icp5` (32), `ic07` (128), `ic08` (256), `ic09` (512) and `ic10` (1024, which is 512@2x). It works on any host and is testable without `iconutil`. The Mac gate checks it with `iconutil -c iconset` for a round-trip.
   - **`.ico`:** PNG-embedded entries at 16, 32, 48 and 256, which Vista and newer read.

The icon is used in each target:

| Target | Where |
|---|---|
| macos | `Contents/Resources/BLiNX2.icns` plus `CFBundleIconFile` in `Info.plist.in`. The launcher `exec`s `cat_recomp` inside the bundle, so the Dock shows the bundle icon. The DMG's own volume icon is not set (it is a nice-to-have). |
| windows | `BLiNX2.rc.in` (`1 ICON "BLiNX2.ico"`) compiled with llvm-mingw's `x86_64-w64-mingw32-windres` and linked into `BLiNX2.exe` (`build_launcher_exe` adds the `.res`/`.o`). The same `.rc` goes into `cat_recomp.exe` through the opt-in `CAT_APP_ICON` CMake option, because the taskbar shows the running window's process (cat_recomp), not the launcher. In CMake this is `if(CAT_APP_ICON AND WIN32) enable_language(RC); configure_file(... BLiNX2.rc); target_sources(cat_recomp PRIVATE <build>/BLiNX2.rc)`; the toolchain file sets `CMAKE_RC_COMPILER` to llvm-mingw's windres when CMake does not find it on its own. NSIS gets `!define MUI_ICON` and `MUI_UNICON`, and the Start-menu and desktop shortcuts name `BLiNX2.exe,0`. |
| steamos | `icon.png` (256) beside `launch.sh` in each version dir. Today `add_to_steam` passes the `<root>/BLiNX2` script to `steamos-add-to-steam`, which gives the shortcut no icon. The install now writes `<root>/BLiNX2.desktop` (`[Desktop Entry]`, `Type=Application`, `Name=BLiNX 2`, `Exec=` the root script, `Icon=<root>/current/icon.png`, `Terminal=false`, paths quoted per the desktop-entry spec) and passes that instead, because the helper accepts a desktop entry and Steam takes the shortcut's name and icon from it. That last point is verified on the gaming PC (task 7.2). If it does not hold, the fallback is the script as today, plus the grid `_icon` file from 7.2. The `.desktop` file is written only into the install root, never into the tree. |

`CAT_APP_ICON` defaults to empty. When it is empty, `CMakeLists.txt` adds nothing (no `enable_language(RC)`, no source), so stock and dev builds are byte-identical to today's. Only `package` sets it, and only in `build-pkg-win/` (macOS needs no exe resource).

**Where the icon lives.**

- It is game data. It is written to `build-pkg-*/icon/` and copied into bundles under `dist/`, and it is never written into the source tree. `.gitignore` already drops `*.png` (except `docs/images/`) and all of `build-*/` and `dist/`; it gains `*.ico` and `*.icns` so a stray copy can never be staged.
- `private_leaks` gains the icon names, so a staged-tree check flags any icon outside the bundle layout.
- Nothing from the icon goes into the docs or the public export either: no screenshot of the Dock icon in `docs/images/`. The gate screenshot lives in `runs/packaging-ux/`, outside every repo.
- Tests build a synthetic XPR0 in memory: a 16×16 DXT1, DXT3 and DXT5 image with known block colours, and a bad-magic case. No game bytes are ever used in tests.

**Fallback.** If there is no XBE, no section, an unknown format or a decode error, `game_icon.py` draws a generic icon in code: a neutral rounded square with a vertical gradient and no text or game data. `package` prints `icon: generic (<reason>)` and does not fail.

### 5. User data stays the user's in tests

What happened: a packaging-deploy DMG smoke test wrote `SDL_AUDIODRIVER=dummy` and `RECOMP_WINDOW_QUIT_AFTER=10` into the real `~/Library/Application Support/BLiNX2/config/launch.env`. That file is the user's to edit, and the launcher loads it last. The coordinator has restored it and kept a `.bak`.

The fix:

- **`BLINX2_DATA_DIR`.** The macOS launcher (`BLiNX2.in`) and the Windows launcher (`launcher.c`) read `BLINX2_DATA_DIR` from the environment. When it is set and non-empty, it replaces `~/Library/Application Support/BLiNX2` or `%LOCALAPPDATA%\BLiNX2` for every derived path: `hdd/`, `config/` and `logs/`. On steamos the data root is already the install root (`--root` and `BLINX2_ROOT`), and tests always pass a scratch root.
  - It is a launcher variable, read before the runtime starts. It is not a `recomp_env` key, because the runtime never sees it, so the "no raw getenv" rule (which is about fork code) does not apply.
  - It is documented in a new "Launcher variables" section of `docs/env.md` and in `docs/packaging.md`.
- **Tests.** Any test or gate that starts a packaged launcher sets `BLINX2_DATA_DIR` to a scratch directory, and on macOS also sets `HOME` to a scratch directory as a second guard. Test keys (`SDL_AUDIODRIVER=dummy`, `RECOMP_WINDOW_QUIT_AFTER`) go in the scratch `config/launch.env`. For the Finder and Dock check, the app is started with `open --env BLINX2_DATA_DIR=… --env HOME=…`.
  - A test runs the macOS launcher script with a fake `cat_recomp` that prints its environment. It asserts that `RECOMP_HDD_DIR`, `RECOMP_ENHANCE_CONFIG` and `RECOMP_STDIO_LOG` are all under the scratch dir, and that a sentinel real-data dir is left byte-identical.
  - The Windows launcher keeps its data-dir resolution in one small function and is checked in the Proton smoke test (task 7.3), where `BLINX2_DATA_DIR` points at a scratch dir and the game log lands there. No host-compiled test seam: `launcher.c` is about 150 lines of Win32 wide-string code, and an `#ifdef` harness would be larger than what it tests.
- **Workspace rule.** No agent or test writes to a real user-data folder. If a test cannot avoid it, it restores the folder byte-for-byte afterwards and says so in its report.

### 6. Pads and the keyboard in the packaged app

`src/pad_input.c` (lines 933–950) leaves host devices off by default except on `_WIN32`, because the macOS SDL path is unverified. Goldens and the bench rely on that and set their own keys, so the runtime default does not change.

The packaged defaults:

- **`launch.env.default.macos`** gains `RECOMP_HOST_PAD=1`. This takes the toolkit's SDL GameController backend, merged with no script. The user has already run the packaging-deploy app with `RECOMP_HOST_PAD=1` in their own `launch.env` and confirmed that the pad and the audio work, so the SDL path is verified; what remains is a re-check on the rebuilt app (task 6.3).
- **`launch.env.default.windows`**, also used by steamos, needs no pad key: the exe is `_WIN32` under Windows and under Proton. It gains `RECOMP_KEYBOARD=1`, **on by default (decided by the user)**, for these reasons:
  - The keyboard answers only for port 0.
  - It is merged on top of a real pad on that port: buttons are ORed and analog values take the max (`input_core.c`), so it never masks the pad.
  - It is read only while the game window has focus.
  - The cost is that port 0 always reports as connected. For a single-player game that is what we want.
  - The keys are: arrows for the d-pad; Z X A S for A B X Y; Enter for START; Backspace for BACK; Q and E for white and black; 1 and 3 for the triggers; numpad 8, 2, 4 and 6 for the left stick; I, K, J and L for the right stick. The implementer copies the map from the toolkit source (`src/input/xinput_device.c`, the `keyboard_on` path), not from this page.
  - These are listed in each target's README part.
- **On macOS, `RECOMP_KEYBOARD=1` does nothing.** `keyboard_on()` is `_WIN32`-only, and the toolkit's SDL backend has no keyboard hook. So it is not set there, and the macOS README says to use a controller.
  - Adding a keyboard to the SDL backend (from `SDL_GetKeyboardState`, through `input_backend.h`'s `keyboard` slot) is a toolkit follow-up, recorded in TASKS.md.
- **Verification.** The user has confirmed pad and audio in the macOS app with `RECOMP_HOST_PAD=1`. A final re-check on the rebuilt app with the default in place is still asked of the user (task 6.3). The agent itself checks:
  - the `[INPUT] sources: … host=on …` line in a scratch-data headless run;
  - the steamos and windows `[INPUT]` lines (`host=on keyboard=on`) in a Proton run, deferred with the Linux PC tasks.

### 7. Small follow-ups folded in

- **The AppleScript alert in `BLiNX2.in`.** `fail()` runs `osascript -e 'on run argv' -e 'display alert "BLiNX2 cannot start" message (item 1 of argv)' -e 'end run' -- "$*"`. The message is an argument, never script text, so quotes and backslashes in a path cannot break it or inject AppleScript. A test calls `fail` with `a "quoted" \ path` while `osascript` is stubbed on `PATH`, and checks the argv it received.
- **`pipeline.sh build` on Linux** maps to `blinx2 build`, whose host default there is `windows`, a cross-build to `build-win/`. This is now stated in `docs/packaging.md` and in the help text of `pipeline.sh`.

## Risks / Trade-offs

- **An extra build for developers who also package.** `build-pkg-*` duplicates about 7 minutes of build and about 1 GB on disk. This is accepted for correctness. The design says so in `docs/packaging.md`, and `--reconfigure` is the only knob.
- **A key that misses an input** would package a stale gen/. Mitigations:
  - the input list is tested against the files the stage commands open (task 2.2), and the toolkit's gitignored `ICALL_DB` is in it explicitly;
  - the stage argv hash stales gen/ on any stage change without a constant to remember;
  - every stage command deletes the key, and `./blinx2 analyze` always forces regeneration.
- **The ETA can be wrong.** It is text, not bar, and says `~`; the bar moves only on real ticks, so the view never claims work that has not been done.
- **Upscaled icons are soft at 1024.** That is inherent to a 128 px source. A hand-drawn icon would need game art we will not ship, so this is accepted.
- **Steam icon behaviour varies by client version.** The shortcut icon comes from the `.desktop` `Icon=`. Grid art is an investigation only (7.2).

## Open questions

None. The two the draft raised were decided by the user:

1. The `.icns` uses Apple's rounded-rect layout (decision 4.5), not full-bleed art.
2. `RECOMP_KEYBOARD=1` is on by default in the windows and steamos bundles' `launch.env.default` (decision 6).
