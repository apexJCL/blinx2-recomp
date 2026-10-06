## 0. Before implementation

- [x] 0.1 Fable revised this spec after the user's answers (bundle the game files; no lock in the installed game; windows and steamos as separate bundles; saves kept everywhere).
- [x] 0.2 Worktree `wt/packaging/cat` on `feat/packaging`, cut from `spec/packaging`. No toolkit worktree: the toolkit is used read-only through `XBOXRECOMP_DIR`. If a toolkit change turns out to be needed, it gets its own worktree off `posix-host/portability` and a task here.
- [x] 0.3 Fable read the cross-platform amendment (build on any host, one CLI, no ssh deploy) and recorded decisions 3 and 4 in design "Decided". Phase 2 starts from this version.

## 1. Data location keys (`src/main.c`, `src/env/recomp_env_game.h`, `docs/env.md`)

- [x] 1.1 The `GAME_FILES` and `HDD_DIR` CONFIG rows, and their `docs/env.md` rows; the `RECOMP_SAVE_DIR` row says it sits inside the save root (WIP 872cc0c).
- [x] 1.2 `host_main` resolves the game dir and the XBE path, passes both keys to `xbox_path_init`, prints `[BOOT] game files: …` only when a key is set, and names the source in the missing-XBE message (WIP 872cc0c).
- [x] 1.3 Verify on macOS, headless, with `SDL_AUDIODRIVER=dummy`:
  - with the keys unset, the boot log up to `Starting game...` is line-identical to `main` (diff two `RECOMP_WINDOW_QUIT_AFTER=10` runs);
  - `RECOMP_GAME_FILES=<abs path>` boots from an unrelated working directory;
  - `RECOMP_HDD_DIR=<tmp>` puts `Partition0.img`, `TitleData/` and `UserData/` there;
  - a missing XBE exits non-zero with the new message.

## 2. The host CLI (`blinx2.py`, wrappers, pins)

Order for the implementer: 2.2 then 2.6 first (the CLI builds what the Mac already builds, which is the quickest proof of the skeleton), then 2.5, then 2.3 and 2.4 together, then 2.1 (its files are written by `pins refresh`, which needs the CLI), then 2.7 and 2.8. Commit each numbered item on its own.

- [x] 2.1 Pins:
  - `config/toolchain.env` stays as is (already done in WIP; `bench.sh` reads it).
  - Add `config/setup-pins.json`: the five llvm-mingw 20260922 UCRT assets in design Context (x86_64 and aarch64 zips, ubuntu-22.04 x86_64 and aarch64, macos-universal; the API's `digest` field is the sha256), with URL, sha256 and size; the NSIS Windows zip; the public toolkit fork URL and commit (design 1b).
  - Add `config/requirements-setup.txt` (`cmake`, `ninja`, `capstone`, `pefile`) and `config/requirements-dev.txt` for `--dev` (`pytest` with its transitive deps under markers, and `numpy`; Python 3.12 or newer, which numpy 2.5 needs), each with every wheel hash.
  - Add a maintainer-only `blinx2.py pins refresh` that rewrites the three files from the GitHub and PyPI JSON APIs, failing when a pinned package needs an unpinned dependency.
- [x] 2.2 `blinx2.py` skeleton:
  - host detection (`platform`); toolkit resolution, passed to CMake as `-DXBOXRECOMP_DIR`;
  - the project venv (`.venv/bin` or `.venv\Scripts`);
  - `DEVELOPER_DIR` on macOS;
  - subprocess calls with argument lists only.
  - Wrappers: `blinx2` (sh, LF) and `blinx2.cmd` (CRLF; `py -3`, falling back to `python`).
- [x] 2.3 `setup`:
  - create the venv, then `pip install --require-hashes --only-binary :all:`;
  - fetch and verify llvm-mingw per host, and NSIS on Windows (`urllib`, `hashlib`, `zipfile`/`tarfile`, `.partial` then rename, `.tag`). This ports the bash `pipeline.sh toolchain` from WIP 872cc0c, whose digest check already worked on the Mac;
  - clone the toolkit at its pin only when none is found;
  - finish by running `doctor`.
- [x] 2.4 `doctor`:
  - one line per piece;
  - the host × target matrix for this host;
  - the install command for anything missing (`makensis`; the CLT and Homebrew libraries for macos);
  - on Windows, the long-path and repo-path-length warnings;
  - on macOS, quarantine detection and the `DEVELOPER_DIR` in force.
- [x] 2.5 The pipeline stages (`parse`, `disasm`, `funcid`, `abi`, `ghidra` (optional), `names`, `recomp`, `analyze`, `all`) ported from `pipeline.sh` with the same arguments, outputs, icall-seed handling and `.gen-regenerating` marker. Then `pipeline.sh` becomes the thin wrapper. Its `build` stage maps to `build macos` on macOS, and `build-win` to `build windows`.
- [x] 2.6 `build windows|macos`:
  - resolves llvm-mingw (`LLVM_MINGW_ROOT`, then `third_party/`, then `PATH`);
  - generator: Ninja from the venv; Makefiles only with `--system-tools` on Linux and macOS (a Windows host has no `make`);
  - with no target: `macos` on macOS, `windows` elsewhere;
  - refuses while `.gen-regenerating` exists;
  - Release;
  - `macos` is refused off macOS.
- [x] 2.7 Verify on the Mac:
  - On a fresh clone (no `third_party/`, no `.venv/`): `setup`, `doctor`, `analyze`, `recomp`, `build windows` and `build macos` all succeed. Record the times.
  - Boot a build made without Ghidra headless (`RECOMP_WINDOW_QUIT_AFTER=10`) to show that the default path needs no Ghidra.
  - Run `scripts/pipeline.sh recomp` through the wrapper.
  - Result (2026-10-05, M4 Mac): fresh clone, no `.venv`, `third_party` or toolkit. `setup` 30 s (venv with hashes, llvm-mingw fetched and verified, toolkit cloned at the pin); `doctor` reports all three targets; `analyze` 2 min 34 s; `recomp` 10 min 13 s; `build windows` 5 min 43 s; `build macos` 7 min 3 s. The no-Ghidra macOS build boots (Metal, 537 flips in 10 s, exit 0).
  - **Finding: the pinned public toolkit (`09abd3c`) cannot build the current cat tree** (`main.c`: `enhance.h` not found); the builds above used the local integration toolkit via `XBOXRECOMP_DIR`. A fresh clone builds only after the public fork's `blinx2/portability` is brought up to the integration head and `blinx2 pins refresh` re-pins it (follow-up 10.5).
  - Equivalence: with the same toolkit (4ec9f0a), `analysis/{disasm,func_id,abi}` from the old bash `pipeline.sh` and from the CLI are identical, and both `recomp` runs give the same `gen/` (digest `014ef868`, `diff -r` clean), through the `pipeline.sh` wrapper and through `blinx2` on the fresh clone.

- [x] 2.8 `scripts/test_blinx2_cli.py`, using fake toolchains and mocked `platform`:
  - Archive note (2026-10-06): done. `scripts/test_blinx2_cli.py` covers each listed case (asset selection, digest mismatch, venv layout, wrapper line endings, the macos refusal, path checks, `DEVELOPER_DIR`, every asset pinned).
  - asset selection for each host OS and arch;
  - a digest mismatch deletes the download and unpacks nothing;
  - the venv layout per OS;
  - the `.cmd` wrapper is CRLF and `blinx2` is LF;
  - `macos` refused on Linux and Windows, with the message;
  - the long-path and reserved-name checks;
  - `DEVELOPER_DIR` set only when unset and present;
  - every llvm-mingw asset of the tag is pinned.

## 3. Payload and manifest (`scripts/package_lib.py`, `packaging/`)

- [x] 3.1 `package_lib.py`: `version`, `check-cache`, `xbe-title`, `stage-game-files`, `manifest`/`sums`, `dylibs` (with dlopen companions), `nsis-files` (WIP 872cc0c; `version` and `xbe-title` were run by hand).
  - [x] Rework it into a module the CLI imports.
  - [x] Replace `cp -c` with a clonefile attempt that falls back to `shutil`.
  - [x] Add the reserved-name, trailing-dot and CRLF checks.
- [x] 3.2 `packaging/`: `enhance.toml.default`, `launch.env.default.windows`/`.macos`, `README.txt.in`, and the per-target `README.part` (WIP).
  - [x] Add the copy step and `bash install.sh` to the steamos part.
  - [x] Add the SmartScreen and Mark-of-the-Web notes to the windows part.
  - [x] Say that the launcher refreshes `config/enhance.toml.default`.
- [x] 3.3 `blinx2 package`:
  - the build step;
  - the refusals (gen, Release, stock, the XBE title);
  - staging, minus the `game_files/` exclusions;
  - the manifest (with `host` OS/arch and `ghidra_names`, design 1d and Risks) and `SHA256SUMS`;
  - the notice;
  - the options `--no-build`, `--allow-debug`, `--allow-nonstock`, `--archive` and `--out`.
- [x] 3.4 `.gitignore`: `dist/`, `*.dmg`, `*.exe`, `*.pdb`, `*.nsi`, `*.tar`, `.venv/`, `external/` (the toolkit clone must not enter the `-dirty` hash). `.gitattributes` as in design 1e. `export-public.sh` fails when the commit tracks `dist/**` or one of those extensions. Test that with a throwaway commit in the worktree, then drop the commit. Done with an unreferenced `commit-tree` object adding `dist/BLiNX2-x-steamos.tar`: the export fails and names the path.
- [x] 3.5 `scripts/test_package_lib.py`:
  - the version format, dirty-suffix stability and difference, date ordering;
  - the manifest fields, no absolute path or host name, `SHA256SUMS` agrees with `files[]`;
  - `xbe-title` on a synthetic header;
  - `dylibs` on a fake `otool -L` with a transitive dependency and a companion;
  - the `game_files/` exclusions;
  - the reserved-name and CRLF refusals;
  - the gen digest equals bench.sh's format on a fixture.

## 4. steamos bundle (`packaging/steamos/`)

- [x] 4.1 `launch.sh` (WIP).
  - [x] Refresh `config/enhance.toml.default` on launch.
  - [x] Keep the scripts' line endings LF.
- [x] 4.2 `install_lib.py` with install, rollback, status, list, uninstall and import-saves (WIP, written, untested). Python only, no rsync or `sha256sum` (design 1d).
  - [x] Remove any write under `config/`.
- [x] 4.3 `install.sh`: the bash entry, which finds `python3` and execs `install_lib.py`. Its help mentions `bash install.sh`.
- [x] 4.4 `blinx2 package steamos` writes the tar with `tarfile`: explicit modes, a single top folder, no symlinks, LF checked.
- [x] 4.5 `scripts/test_steamos_install.py` on a temp-dir fake bundle. It covers:
  - the first install layout;
  - a same-version install is a no-op;
  - a corrupt sum leaves `current` and removes `.partial`;
  - the switch is a single rename;
  - prune keeps N plus current plus previous, and leaves a foreign dir;
  - rollback;
  - the dev-tree refusal;
  - uninstall keeps user data;
  - `--import-saves` refuses a non-empty `hdd/`;
  - the ownership snapshot of `hdd/`, `config/` and `logs/` around every command;
  - the tar unpacked by `tarfile` has executable scripts.

## 5. Windows bundle (`packaging/windows/`)

- [x] 5.1 `launcher.c`, as in design 4b plus the `.default` refresh. The CLI builds it with llvm-mingw clang (`-municode -mwindows -O2`).
- [x] 5.2 `installer.nsi.in`, as in design 4 (per user, `CopyFiles` from `$EXEDIR`, generated `File` and `Delete` lines, shortcuts, the `HKCU` uninstall entry, the final page naming the data directory). It never writes the user-data directory.
- [x] 5.3 `blinx2 package windows`:
  - build the launcher;
  - render the `.nsi` (quoted paths);
  - run `makensis` (the venv-independent path from `doctor`);
  - place `setup.exe` beside a copy of `game_files/`;
  - assert the result is under 2 GB.
- [x] 5.4 Verify on the Mac with Homebrew `makensis`: `file` says PE32, and `strings` names the three executables. Done: `file` reports a PE32 Nullsoft installer; the names sit in the zlib stream, so `7zz l` lists them instead (`BLiNX2.exe`, `cat_recomp.exe`, `uninstall.exe`, the pdb, defaults and docs; 58 MB). `game_files/` is beside it.

## 6. macOS bundle (`packaging/macos/`, macOS hosts only)

- [x] 6.1 `Info.plist.in` and `BLiNX2.in` (the launcher, including the `.default` refresh).
- [x] 6.2 `blinx2 package macos`:
  - assemble the app and copy `game_files/` into `Resources/`;
  - run the dylib plan with `--companion libSDL3.dylib`;
  - sign each dylib, then `cat_recomp`, then the app, and run `codesign --verify --deep --strict`;
  - `hdiutil` the DMG with an `Applications` symlink.
- [x] 6.3 Verify on the Mac:
  - `otool -L` shows no `/opt/homebrew` path;
  - the app launches from the mounted DMG with `RECOMP_WINDOW_QUIT_AFTER=10` and `SDL_AUDIODRIVER=dummy` in a temporary `config/launch.env` (no sound on the Mac without asking);
  - `hdd/` and the log land in Application Support;
  - a planted `hdd/` fixture survives replacing the app.
  - Result: `otool -L` over `cat_recomp` and the four bundled dylibs (libcrypto.4, libepoxy.0, libSDL2-2.0.0, libSDL3) shows only system and `@rpath` names; `codesign --verify --deep --strict` passes; the DMG is 2.4 GB. Launched with `open -W -n` from the mounted DMG: `hdd/`, the config files and the log land in Application Support, 535 flips in 10 s, and a planted `hdd/fixture` survived launching a second, rebuilt app. The first try crashed at the 248th open file: Launch Services gives apps a soft limit of 256 open files and the game keeps about 250 cache records open, so the launcher now raises the soft limit (the toolkit then dereferenced the failed handle in `w32_handle_fd`: follow-up 10.4).

## 7. The bench and the installed game (`scripts/running_game.py`, `bench.sh`, `golden.py`)

- [x] 7.1 `running_game.py`:
  - reads `/proc` on Linux and `ps` on macOS; on Windows it returns nothing with a note (no caller runs there: the bench is Linux, `golden.py` is Mac);
  - applies the match rule and excludes the caller's tree;
  - `--kill` sends TERM, waits 5 s, then sends KILL.
  - `scripts/test_running_game.py` covers it on synthetic listings.
- [x] 7.2 `bench.sh`:
  - in `run_game`, after the lock, the `WARN` line goes to stdout and into `bench-logs/<stamp>/`;
  - `--kill-game` and `BENCH_KILL_GAME`.

  `golden.py` gets the warning only. Document both in the script headers. bench.sh is otherwise unchanged and not ported (follow-up 10.4).

## 8. Docs

- [x] 8.1 `docs/packaging.md`:
  - per build host: prerequisites, `setup`, `doctor`, the matrix;
  - the copy step: USB stick, network share, `scp`; unpacking the steamos tar;
  - per target: first install, each update, rollback on steamos;
  - where saves live;
  - the Steam steps from Desktop Mode;
  - macOS quarantine; Windows SmartScreen, Mark of the Web and the Defender note;
  - "untested on a Windows host" and "untested natively on Windows";
  - troubleshooting;
  - the private-bundle statement.
- [x] 8.2 `README.md`:
  - "Getting started" uses `blinx2 setup` / `analyze` / `recomp` / `build` on any host;
  - add an "Install on your own machines" section;
  - add the non-redistribution sentence to Legal;
  - update the troubleshooting entry for `RECOMP_GAME_FILES`.
- [x] 8.3 The CLI's `--help` per subcommand; the `pipeline.sh` header points at the CLI; the `bench.sh` header lists `--kill-game`.

## 9. Gates and end-to-end verification

Every agent run on the Linux PC is wrapped in `flock -w 3600 ~/.recomp-run.lock`; expect waits. The installed game itself takes no lock. Use a test root (`--root ~/Games/BLiNX2-test`), a build checkout outside `~/xbox-recomp` (for example `~/blinx2-hostbuild/`), and a scratch Wine prefix for the Windows installer, never the bench's.

- [x] 9.1 Mac host, the full run:
  - the Mac build with the CLI (`DEVELOPER_DIR` handled by it);
  - every `scripts/test_*.py`;
  - `package steamos`, `package windows` and `package macos` all succeed;
  - `git status` shows nothing under `dist/`.
  - Result (Mac, 2026-10-05): the CLI builds `build/` and `build-win/`; 118 `scripts/test_*.py` tests pass (pytest); `package steamos` (2.8 GB tar, 4 min 46 s with the rebuild), `package windows` (58 MB setup.exe plus `game_files/`) and `package macos` (2.4 GB DMG, 7 min 4 s with the build) succeed; `git status` is clean, `dist/` ignored.
- [x] 9.2 Goldens unchanged at stock: `scripts/golden.py` on Metal (Mac), and `scripts/bench.sh golden` for D3D11 under Proton after `bench.sh integrate`. Neither sets the new keys.
  - Metal (Mac, no-Ghidra gen 014ef868, toolkit 4ec9f0a): attract 2/2 CLOSE, stage1 3/3 CLOSE, story-tsedit CLOSE, **story-menu FAIL** (mae about 6, the animated backdrop at another phase; the menu itself matches) and story-hub INCOMPLETE, twice. The main checkout's own binary (cat ef318a0) gives the same FAIL and INCOMPLETE run from the same directory, so this predates the branch. Runs in `runs/packaging/metal-*`.
  - D3D11 half (Linux PC, 2026-10-06, integration heads with packaging-ux): `scripts/bench.sh golden` passes, 7/7 CLOSE.
- [x] 9.3 Linux host, on the Linux PC under the lock:
  - plain user space: a clean clone copied over (git, or a copy of the tree, plus the dump), then `./blinx2 setup`, `doctor`, `analyze`, `recomp`, `package steamos`;
  - then `package windows` with `makensis` from a distrobox (`dnf install mingw32-nsis`), the documented route on an immutable host.

  Record the times, and the exact commands that needed the box.
  - Commands for later (on the PC, each under the lock):
    `git clone <cat bundle or remote> ~/blinx2-hostbuild/cat && cp -a --reflink=auto <dump> ~/blinx2-hostbuild/cat/game_files`;
    `cd ~/blinx2-hostbuild/cat && flock -w 3600 ~/.recomp-run.lock sh -c 'XBOXRECOMP_DIR=~/xbox-recomp/xboxrecomp ./blinx2 setup --no-toolkit && ./blinx2 doctor && XBOXRECOMP_DIR=~/xbox-recomp/xboxrecomp ./blinx2 analyze && XBOXRECOMP_DIR=~/xbox-recomp/xboxrecomp ./blinx2 recomp && XBOXRECOMP_DIR=~/xbox-recomp/xboxrecomp ./blinx2 package steamos'`
    (`XBOXRECOMP_DIR` until 10.5); then in the box: `distrobox create -n blinx2-build -i fedora:42 && distrobox enter blinx2-build -- sh -c 'sudo dnf install -y mingw32-nsis python3 git && cd ~/blinx2-hostbuild/cat && XBOXRECOMP_DIR=~/xbox-recomp/xboxrecomp ./blinx2 package windows --no-build'`.
  - Result (Linux PC, 2026-10-06, cat main b2de36b): a fresh clone plus the dump, then one plain `./blinx2` over ssh (no terminal, so plain mode) went from nothing to the steamos tar in 37:10: setup 0:16, disasm 0:59, funcid 1:40, abi 0:26, recomp 21:45, build 11:53. A rerun with nothing changed took 6 s. gen/ is byte-identical to the Mac's apart from one comment line that named the checkout folder (now fixed to "cat").
  - `package windows` in the box only works as `--no-build` (the host's `.venv` does not run in a Fedora 42 box): box create plus `dnf install mingw32-nsis` 59 s, then `distrobox enter blinx2-build -- sh -c 'cd ~/blinx2-hostbuild/cat && ./blinx2 package windows --no-build'` 11 s. The doctor hint and docs now say so.

- [x] 9.4 steamos e2e on the Linux PC, using the tar built there in 9.3 and the Mac-built one from 9.1:
  1. Unpack the tar, then `./install.sh --root ~/Games/BLiNX2-test` (no `--steam`). Check the layout, `current` and `game_files/default.xbe`, and that nothing under `~/xbox-recomp` changed (a `find -newer` listing before and after).
  2. Launch `BLiNX2` with the desktop session's environment, under the agent's lock. Check: the title screen with D3D11, the log in `logs/`, `hdd/Partition0.img`, and the prefix at the test root.
  3. Update and rollback:
     - make a save;
     - set `render.scale = 2`;
     - install a second version;
     - check that `hdd/`, `config/` and `logs/` are byte-identical, that the save loads at scale 2, and that `status` and `list` are right;
     - roll back;
     - delete `prefix/`, relaunch, and check that the save loads.
  4. `uninstall` keeps the user data.
  - Commands for later: copy `dist/*-steamos.tar` over; `tar -xf BLiNX2-*-steamos.tar && cd BLiNX2-*-steamos && ./install.sh --root ~/Games/BLiNX2-test`; launch under the lock with the desktop session's env: `flock -w 3600 ~/.recomp-run.lock ~/Games/BLiNX2-test/BLiNX2`; then the update and rollback steps above with a second bundle, `./install.sh --root ~/Games/BLiNX2-test status|list|rollback|uninstall`.
  - Result: both tars (Linux-built 0631, Mac-built 0556) install into `~/Games/BLiNX2-test`; nothing under `~/xbox-recomp` changed. The launch reaches the title screen with D3D11 (a frame dump; spectacle over ssh only gives a blank image), with the log in `logs/`, `hdd/Partition*.img` and `prefix/` under the root. The `Z:` paths with forward slashes work. Update to the Mac-built version: `hdd/`, `config/` and `logs/` byte-identical (386 files), `status` and `list` right, and the game runs at `render.scale = 2` (1280x960 frames). Rollback, `prefix/` deleted, relaunch: title screen. Uninstall keeps the user data byte for byte. No save was made by hand (it needs play), so "the save loads" is covered by the byte-identical `hdd/` only.
  - Found: installing again after an uninstall was refused ("not a BLiNX2 install root"); fixed on `fix/packaging-linux-gates`.

- [ ] 9.5 **Waiting for the user at the PC.** The Steam entry from Desktop Mode with Steam open: the user does this, or agrees to it. Start the game from Game Mode, check umu-run under Steam, then remove the test shortcut.
  - Archive note: left for the user at the PC; the steps are in TASKS.md.
- [x] 9.6 The running-game check: `bench.sh run` with the installed game running prints `WARN`, and the warning is in `bench-logs/<stamp>/`; `--kill-game` ends the game; `install.sh status` reports it.
  - Commands for later: start `~/Games/BLiNX2-test/BLiNX2` by hand, then from the Mac `scripts/bench.sh run` (expect `bench: WARN ...` and `bench-logs/<stamp>/warnings.txt`), `scripts/bench.sh run --kill-game`, and `./install.sh --root ~/Games/BLiNX2-test status` while it runs.
  - Result: with the installed game running, `scripts/bench.sh run` prints `bench: WARN ...` and writes it to `bench-logs/<stamp>/warnings.txt`; `--kill-game` ends it (all six processes of the umu chain); `install.sh status` lists it. A game started from an ssh shell with `nohup` died when the shell closed, so it was started with `systemd-run --user`. Nit: both the WARN and `status` print one long line per process in the chain.

- [x] 9.7 The Windows installer under Proton (Mac-built and Linux-built `setup.exe`):
  - `/S` into a scratch prefix;
  - plant a fixture under `AppData/Local/BLiNX2/hdd/`;
  - launch `BLiNX2.exe`: the title screen with D3D11, the log and `Partition0.img` under `AppData/Local/BLiNX2/`;
  - run setup `/S` again, then `uninstall.exe /S`: the fixture is byte-identical, the program directory is gone, the data directory remains.
  - Commands for later: `export WINEPREFIX=~/blinx2-hostbuild/prefix-nsis GAMEID=umu-default PROTONPATH=GE-Proton; cd <bundle folder>; flock -w 3600 ~/.recomp-run.lock umu-run ./BLiNX2-*-setup.exe /S`, plant `$WINEPREFIX/drive_c/users/steamuser/AppData/Local/BLiNX2/hdd/fixture`, run `BLiNX2.exe` from `AppData/Local/Programs/BLiNX2`, rerun setup `/S`, then `uninstall.exe /S`, and compare the fixture.
  - Result, Mac-built and Linux-built `setup.exe` alike, each in its own scratch prefix: `/S` installs in 9-10 s; `BLiNX2.exe` reaches the title and attract screens with D3D11 (frame dumps), with the log, `Partition0.img` and the rest under `AppData/Local/BLiNX2/`; `BLINX2_DATA_DIR=C:\b2data` puts the log and `hdd/` there and changes nothing under `AppData/Local/BLiNX2`; setup `/S` again and `uninstall.exe /S` leave the fixture byte-identical and the data directory in place. The program folder is left empty when uninstall.exe is started by Proton (Proton sets the working directory to the exe's folder); started from `cmd /c` in `C:\` it is removed completely.

- [x] 9.8 Windows build host: coverage is the unit tests (2.8, 3.5, 4.5). If it proves practical, also one smoke run of `blinx2.py doctor` and `setup --no-toolkit` under Proton with the Windows embeddable Python in a scratch prefix, recording what worked. Everything else is marked "untested on a Windows host" in `docs/packaging.md`.
  - Result: covered by the unit tests (2.8, 3.5, 4.5). The Proton smoke run needs the Linux PC (the Mac has no Wine): not done; `docs/packaging.md` says building on a Windows host is untested.
- [x] 9.9 The POSIX ctest dirs, as a sanity check (no toolkit change expected).
  - Result: every standalone toolkit test dir configured, built and run on the Mac (`runs/packaging/ctest/`): 23 pass, and the rest are the same Windows-only or non-building dirs as the batch baseline (`runs/batch/ctest/summary.txt`); no toolkit change on this branch.
- [ ] 9.10 Cleanup handed to the user as one `!` command each: `~/Games/BLiNX2-test`, the scratch prefixes, and the Linux PC's build checkout.
  - Archive note: the Linux PC cleanup command is in TASKS.md for the user.

## 10. Review, merge and cleanup

  - Mac cleanup is in the report; the Linux PC's cleanup comes with 9.3-9.7.
- [x] 10.1 Fable review of the branch, including a public-repo audit of the delta: no host names ("the gaming PC" or "a SteamOS-like Linux gaming PC"), private paths, the personal email, binaries, bundles or game data. `export-public.sh` on the branch head passes its own checks. The branch's agent applies the fixes.
  - Archive note: done. Fable review: merge-with-fixes, fixes applied (cat acc065d).
- [x] 10.2 The orchestrating session merges `--no-ff` into cat `main`, then runs `bench.sh integrate` and golden.
  - Archive note: done. Merged as cat 333358e; the Linux PC gates (cat 11d6c8a) ran the D3D11 golden after it (7/7 CLOSE).
- [x] 10.3 After the merge:
  - Archive note: done. Runs in `runs/packaging/`, worktree removed, TASKS.md updated (cat 4a9fa45); the agent's resume note is tracked in this change (RESUME.md).
  - copy untracked notes to `notes/packaging/`;
  - copy the referenced runs to `runs/packaging/` with `cp -c`;
  - move any `dist/` bundle worth keeping to `runs/packaging/dist/` (private);
  - remove the worktree and keep the branch;
  - update `TASKS.md`.
- [x] 10.4 Record these follow-ups in `TASKS.md`:
  - Archive note: done. All five follow-ups are in TASKS.md (the last three added by the openspec cleanup).
  - port `bench.sh` and golden-over-ssh to the CLI (cross-host dev harness);
  - the toolkit's title-shared default save root (an upstream candidate);
  - a compiled macOS launcher, if a future macOS rejects a script `CFBundleExecutable`;
  - native Windows verification, once a Windows machine exists;
  - toolkit: `NtQueryInformationFile` on a handle whose open failed crashes in `w32_handle_fd` instead of returning an error status (seen at the fd limit, 6.3).
- [x] 10.5 Before a fresh clone can build: bring the public fork's `blinx2/portability` up to the integration toolkit (the scrub and mailmap procedure), then `blinx2 pins refresh` and commit the new pin (2.7 finding).
