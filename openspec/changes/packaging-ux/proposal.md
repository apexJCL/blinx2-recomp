## Why

packaging-deploy made a private bundle possible on every host, but the user's first runs from a fresh clone showed what it costs to get there:

- **Too many steps.** A player runs `setup`, `analyze`, `recomp`, `build` and `package` in order, and has to know which ones to rerun after a pull. Only someone working on the recomp itself needs those stages. A player wants one command.
- **A stale build directory blocks packaging.** The developer tree's `build/CMakeCache.txt` had `XBOXRECOMP_ENHANCE=OFF`. `package` refused it as non-stock, and the message did not say how to fix it.
- **Twenty-five silent minutes.** A cold run is about 30 s of setup, 2.5 min of analyze, 10 min of recomp, and 6 to 7 min of build per target. The output is a wall of tool lines, or nothing at all, with no sense of how far along it is.
- **No icon.** The app, the installer and the Steam shortcut use generic icons. The XBE carries the game's own title image (`$$XTIMAGE`, 128×128 DXT1).
- **The macOS app's first real run.**
  - It was silent and quit after 10 s, because a packaging test had written `SDL_AUDIODRIVER=dummy` and `RECOMP_WINDOW_QUIT_AFTER=10` into the user's real `~/Library/Application Support/BLiNX2/config/launch.env`.
  - A controller did nothing, because host pads are on by default only on `_WIN32` (`src/pad_input.c`), and the packaged macOS defaults do not turn them on.

## What Changes

- **One-liner.**
  - `./blinx2` with no arguments packages for this host's native target (macOS→`macos`, Linux→`steamos`, Windows→`windows`). `./blinx2 package <target>` does the same for any target the host can build.
  - Both run `setup` when the toolchain or toolkit is missing. They regenerate `src/recomp/gen/` (analyze, then recomp) only when it is missing or stale, judged by a recorded generation key (XBE, toolkit including its gitignored icall database, config inputs, stage arguments). Then they build and package.
  - `blinx2.cmd` behaves the same on Windows.
- **Its own stock build.**
  - `package` builds in its own directories, `build-pkg-macos/` and `build-pkg-win/`, and passes the stock options explicitly on every configure. A developer's `build/` and `build-win/` are never read or changed by `package`.
  - If a cache still fails the stock check, the refusal prints the exact command that fixes it.
- **Help for players.** `--help` lists the player commands: `package`, `doctor` and `setup`. The pipeline stages, `build` and `pins` move under a "developer commands" heading.
- **Progress view.** A hand-rolled ANSI view from the standard library shows:
  - the overall stage, n of N, with elapsed time;
  - a bar for the current step, fed by download bytes, the recomp and disasm output the tools already print, Ninja's `[n/m]` status, makensis file lines and hdiutil percentages, plus a text ETA from the previous run where ticks are coarse;
  - the latest log line.

  Full logs go to `build-logs/`, and on failure the CLI prints the log's tail and path. Output is plain with `--plain`, when stdout is not a TTY, with `CI` set, or when Windows VT mode is unavailable. No new dependency and no toolkit change.
- **Game icon.**
  - `scripts/game_icon.py` (standard library) extracts the XBE title image and decodes XPR0 DXT1/DXT5 to RGBA. It upscales with Catmull-Rom and writes PNG through zlib, `.icns` and `.ico` with no outside tools.
  - The icon goes into:
    - the macOS app (`CFBundleIconFile`);
    - `BLiNX2.exe` and `cat_recomp.exe` (a windres resource), plus the NSIS installer and uninstaller;
    - a PNG next to the steamos launcher, used for the Steam shortcut icon.
  - If extraction fails, a generated generic icon with no game data is used instead.
  - The icon is game data. It exists only in build directories and private bundles, never in git. Tests use a synthetic XPR fixture.
- **User data is never touched by tests.**
  - The macOS and Windows launchers honour `BLINX2_DATA_DIR`, which overrides the user-data root.
  - Every test or gate that starts a packaged game sets it to a scratch directory. A test proves the real folder is untouched.
- **Pads in the packaged app.**
  - `packaging/launch.env.default.macos` sets `RECOMP_HOST_PAD=1`. The user has confirmed pad and audio work in the app with that key.
  - The runtime default in `pad_input.c` does not change: goldens and the bench set their own.
  - The Windows and steamos defaults already get the pad (`_WIN32`, also under Proton). They also gain `RECOMP_KEYBOARD=1` as a fallback, on by default (user decision). The macOS keyboard needs a toolkit change and is recorded as a follow-up.
- **Follow-ups from the packaging-deploy merge.**
  - The macOS launcher's alert passes its message to `osascript` as an argument, so a quote can no longer break it.
  - `docs/packaging.md` and `pipeline.sh --help` say that `pipeline.sh build` on Linux cross-builds the Windows exe.

## Impact

- **Code:**
  - `blinx2.py`, `scripts/package_lib.py`, the new `scripts/progress.py` and `scripts/game_icon.py`;
  - `packaging/macos/{BLiNX2.in,Info.plist.in}`, `packaging/windows/{launcher.c,installer.nsi.in}` plus a new `BLiNX2.rc.in`, `packaging/steamos/{install_lib.py,launch.sh}` and the `packaging/launch.env.default.*` files;
  - `CMakeLists.txt`: the opt-in `CAT_APP_ICON` option, default empty, so the stock build is unchanged.
- **Docs:** `docs/packaging.md`, `docs/env.md` (a launcher section for `BLINX2_DATA_DIR`), `README.md`, `.gitignore`.
- **Tests:**
  - new `scripts/test_game_icon.py` and `scripts/test_progress.py`;
  - extended `scripts/test_blinx2_cli.py`, `test_package_lib.py` and `test_steamos_install.py`;
  - a macOS launcher data-dir test; the Windows launcher is checked under Proton.
- **No toolkit change.** The macOS keyboard backend and an optional finer-grained recomp progress line are recorded as toolkit follow-ups.
- **Runtime:** no change to stock behaviour. `cat_recomp` is unchanged unless `CAT_APP_ICON` is set, and only `package` sets it.
- **Linux PC:** its gates join the deferred 9.x tasks of packaging-deploy.
