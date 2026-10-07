# Design: cli-extraction

## Context

Read on cat `main` at 70bf5c8 (2026-10-06), the Burnout 3 project at
`b3` 79b578d (upstream `sp00nznet/burnout3`, with the local `TESTING.md`
and `_local/bench host.sh`), and the toolkit at `posix-host/portability`
4e9a2f2. Line numbers below are from 70bf5c8.

- `blinx2.py` is one file: host helpers (97-199), build (205-363), the
  pipeline stages and the generation key (366-922), setup, doctor and pins
  (925-1700), package (1703-2366) and the argparse front (2372-2426). It
  imports `scripts/progress.py`, `scripts/package_lib.py`,
  `scripts/game_icon.py` and `scripts/benchlib` through
  `sys.path.insert(0, ROOT/scripts)` (88, 1726, 1735, 2399).
- `scripts/benchlib/` is the bench controller (toolchain-cli phase 1):
  `__init__.py` (the command table and `HELP`), `config.py` (`BENCH_*`),
  `remote.py` (ssh, `shell_quote`), `sync.py`, `checks.py`, `golden.py`,
  `pacing.py`, and `host/*.sh` shipped over ssh's stdin.
- `scripts/golden.py` (1673 lines) is the frame compare engine; its data,
  `analysis/golden/golden.json`, holds the BLiNX 2 scenarios, hashes and
  thresholds.
- Tests: `scripts/test_*.py`, plain asserts, `uv run pytest scripts`.
  `test_bench_cli.py` replays 28 recorded command lines against
  `scripts/testdata/bench_parity.json` (every ssh argv and stdin script,
  paths and host normalised) and is the proof that the bench did not
  change.
- Python: `pyproject.toml` has `requires-python = ">=3.9"` for the
  standard-library runtime of `blinx2.py`; `.python-version` is `>=3.12`,
  the floor for the dev group; uv 0.12.21 and Python 3.14.8 on the Mac,
  system Python 3.9.6; `git-filter-repo` is not installed.
- Burnout 3 runs upstream's `regen.sh` (bash, `py -3`, `../xboxrecomp`,
  `Burnout 3 Takedown/default.xbe`, `build/xr`, every code section, split
  1000, gen in `src/game/recomp/gen`), `Setup.cmd` → `tools/setup.ps1`
  (winget, pip capstone, clones the toolkit at `main`), an MSVC-only
  `src/game/CMakeLists.txt` (exe `burnout3` into `bin/`), and the local
  `_local/bench host.sh` (its own ssh/rsync/flock, copying cat's
  `cmake/llvm-mingw-x86_64.cmake` to the host).
- The toolkit's `tools/` are the library the CLI drives:
  `tools.xbe_parser`, `tools.disasm`, `tools.func_id`,
  `tools.abi_analysis`, `tools.recomp` (and `recomp.icall_feedback`),
  `tools/ghidra_naming/`, plus `tools/macos/setup.sh` (a pip venv and a
  `py` shim) and `tools/doctor.py` (expects `tools/*/output`). The upstream
  README's Quick Start (steps 3-9) is the same sequence the CLI's stages
  run.

## Goals / Non-Goals

**Goals**
- `xboxrecomp-cli` holds every game-agnostic command; a game holds a
  manifest, its content and its wrapper. A third game is a manifest.
- `./blinx2` stays the user's one command: fresh clone to bundle, with no
  new prerequisite beyond uv, git and Python 3 (as today).
- Byte-identical behaviour on cat through the migration: the help, the
  bench's ssh traffic, the gen key, the packaged payloads, the golden
  verdicts.
- The toolkit fork is untouched.
- Pins are explicit and offline-safe: game → CLI → toolkit.

**Non-Goals**
- Changing any output of the pipeline, build, bench or packaging.
- Migrating Burnout 3 (a follow-up with its own spec; D2 records its
  needs).
- Publishing the CLI, or any public push.
- The Windows controlling host (toolchain-cli phase 3, still deferred).
- Porting `export-public.sh` (private, shell, stays in cat) or
  `xemu_capture.sh`.

## Decisions

### D1. The split

Three classes. *Agnostic*: moves to the CLI as is. *Parameterisable*: moves
to the CLI and reads the value from `game.toml` (D2) or from a path the
manifest names. *Game*: stays in cat.

**Commands**

| Command | Class | Evidence | Manifest keys it reads |
|---|---|---|---|
| `setup` (uv venv, llvm-mingw, NSIS, toolkit clone) | parameterisable | `run_setup` 1317-1331; `find_uv` 1174, `sync_venv` 1226 are agnostic; `fetch_mingw` 1085 reads the tag from `config/toolchain.env` (217-222); `clone_toolkit` 1278 reads `pins["toolkit"]`; `TOOLKIT_PIN_MARK = ".blinx2-pin"` 929 is a game-named file | `toolchain.llvm_mingw`, `toolchain.nsis`, `toolkit.*`, `cli.*` |
| `doctor` | parameterisable | `doctor_report` 1468-1596 is agnostic except `brew_missing(pkgs=("sdl2","sdl3","openssl","libepoxy"))` 1418 (the macos target's link libraries), the XBE path 1556-1561, and `MAKENSIS_HINT["immutable"]` 946-952 naming `blinx2-build` and the `blinx2` commands | `package.brew`, `xbe.path`, `game.slug` |
| `pins refresh` | parameterisable | 1629-1691: llvm-mingw from the GitHub release API (agnostic), NSIS from SourceForge (agnostic), `TOOLKIT_FORK` 1614 hard-codes the fork URL and branch and writes the branch head as the pin | `toolkit.url`, `toolkit.branch`; it no longer writes the toolkit pin (D4) |
| `parse disasm funcid abi ghidra names recomp`, `analyze`, `all` | parameterisable | the commands are data (`tool_cmd` 394, `parse_cmds` 425, `disasm_cmds` 428-466, `funcid_cmds` 469, `abi_cmds` 489, `names_cmds` 513, `recomp_cmds` 533-561) with these game constants: `XBE` 374, `SEEDS` 377, `GAME_NAME = "cat"` 382, `DISASM_EXTRA_SECTIONS` 387, `--text-only` 460, `split_size()` 390, `HOST_RESERVED` 507, `RECOMP_MANUAL` 508, `SPIN_WAITS` 510, `GEN` 38, `OUT` 376, `.venv-ghidra` 619 | `pipeline.*`, `xbe.path` |
| the generation key | agnostic | 712-867 hashes whatever the stage commands and inputs are, with `$ROOT`/`$TK` placeholders 768-771; `GEN_KEY` 722 and `STAGE_EXTRAS` 723 are paths under `pipeline.gen` and `pipeline.out` | none beyond the stages' |
| `build` | parameterisable | `build()` 296-340: the toolchain file `cmake/llvm-mingw-x86_64.cmake` 330 (game-owned in phase A, CLI-owned in phase B), the exe name `cat_recomp(.exe)` 337, `STOCK_CMAKE_ARGS` 293 (`-UCAT_GEN_OPT`), `build_dir` 281 and `pkg_build_dir` 285 names; `build_env` 160-171 and `build_tools` 247-265 are agnostic | `build.*`, `package.stock_cmake` |
| `bench` controller | parameterisable | `benchlib/__init__.py`: `HELP` 39 and 97-122 name `cat_recomp.exe` and `<game>`; `cmd_integrate` 308 refuses a branch other than `main` and 314 warns off `posix-host/portability`; `cmd_tests` 243-246 lists toolkit tests (toolkit policy, not game); `config.py` 82 derives the remote name from the checkout's basename, 86-95 reads `config/toolchain.env`, 105 defaults `LLVM_MINGW_TAG`, 109 derives `BENCH_GAME_FILES`; `sync.py` `GAME_EXCLUDES` 19-54 names `/analysis`, `/.venv-ghidra`, `src/recomp/.gen-regenerating`; `checks.py` 169 names `src/recomp/gen`; `golden.py` 19 runs `scripts/golden.py` from the game dir; `pacing.py` 26 defaults to scenario `stage1` and 96 runs `scripts/pacing_stats.py` from the game dir; `remote.py` is agnostic | `bench.*`, `build.exe`, `pipeline.gen`, `pipeline.out`, `golden.*` |
| `bench` host scripts | parameterisable | `run_game.sh` 7-8 (`build-win/cat_recomp.exe`, `game_files/default.xbe`), 57-60 (`scripts/running_game.py`), 109 and 150 (the exe), 183 (the hog regex names `cat_recomp`); `build.sh` 6 and 9 (the toolchain file); `symbolize.sh` 12-13 and 25 (`cat_recomp.exe`, `.pdb`); `doctor.sh` 32-35; `integrate_show.sh` 3; `gen_digest.sh` 3 (`src/recomp/gen`); `game_files.sh` 6 (`default.xbe`); `tests.sh` is toolkit policy (the test names); `setup_*.sh`, `prologue.sh.in`, `lock_box.sh.in`, `hold_lock.sh`, `check_umu.sh` are agnostic | the same, as `EXE=`, `GEN_DIR=`, `XBE=` assignments in the prologue (D5 says when) |
| `golden.py` (the engine) | parameterisable | `GOLDEN_DIR`, `GOLDEN_JSON`, `FRAMES_DIR` 132-134 are the only game paths; the compare, anchors, masks, pace, split frames and the `running_game` warning (1634) are agnostic. `golden.json` itself is game data (hashes, thresholds, scenario env) | `golden.json`, `golden.frames`, `build.exe` (for the warning) |
| `package` | parameterisable | 1703-2366: `NOTICE_TEXT` 1707 and `readme()` 1769 take the name from `lib.PRODUCT_NAME`; `TARGET_NAMES` 1712 is agnostic; `DATA_PATHS` 1717-1721 names `BLiNX2` folders; `stage_payload` 1859 checks `lib.TITLE_ID`, 1868 passes `-DCAT_APP_ICON`, 1898 names the payload `BLiNX2-…`; `build_launcher_exe` 1796-1819 renders `BLiNX2.rc.in` and defines `BLINX2_NAME`; `wrap_steamos` 1957 and `execs` 1961; `wrap_windows` 2010-2022; `wrap_macos` 2062-2076 (`BLiNX2.app`, `BLiNX2.in`, `BLiNX2.icns`), 2084 (`brew_prefix_lib("sdl3", "libSDL3.dylib")` as a dlopen companion); `package()` 2308-2339 copies `packaging/steamos/*` and `scripts/running_game.py` into the payload. `package_lib.py`: `PRODUCT` 33, `PRODUCT_NAME` 36, `TITLE_ID` 37, `GAME_FILES_EXCLUDE` 43, `LF_ONLY` 263 (`^BLiNX2$`), `ICON_FILES` 280, `cache_problems` 153-156 (`CAT_GEN_OPT`), `build_manifest` 355-358 (`sources: cat, toolkit`); the rest (version, tree state, gen digest, XBE title, staged checks, dylib plan, NSIS lists, private-leak check) is agnostic. `game_icon.py`: `NAME = "BLiNX2"` 26; the XPR0/DXT decode and the ICNS/ICO writers are agnostic | `package.*`, `data.*`, `xbe.title_id`, `game.name` |
| `packaging/` templates | parameterisable (phase B) | `windows/installer.nsi.in` (`!define APP "BLiNX2"`, `$LOCALAPPDATA\Programs\BLiNX2`), `windows/launcher.c` (`BLINX2_NAME`), `windows/BLiNX2.rc.in`, `macos/BLiNX2.in`, `macos/Info.plist.in`, `steamos/install.sh`, `steamos/install_lib.py` (`PRODUCT`, `DEFAULT_ROOT = "~/Games/BLiNX2"`), `steamos/launch.sh`, `README.txt.in` are the mechanism with the name baked in. `*/README.part`, `launch.env.default.*`, `enhance.toml.default` are the game's content | `package.app`, `package.product`, `data.*` |
| `export-public.sh` | game | private, shell, its `REWRITE` rules name the bench host; stays in cat with `test_export_public.py` (toolchain-cli decided this already) | none |
| `running_game.py` | parameterisable (phase B) | matches `cat_recomp.exe` in command lines (its docstring and 11 mentions); runs on the bench host (`run_game.sh` 57) and ships in the steamos payload (2329) | `build.exe` (as `--exe`) |
| `progress.py`, `pacing_stats.py`, `benchlog-retention.py`, `audio_check.py` | agnostic | no game names (`grep` count 0-1, the one being `blinx2 package` in a docstring); `audio_check.py` reads `analysis/golden/audio.json` only through its arguments | none |
| `host_reserved_names.py` | game | a names-stage hook that reserves ISO C names in `functions.json`; its list is this game's CRT collisions. It stays in cat and the manifest names it as a hook (`pipeline.names_hooks`) | run as a `py_cmd`, as today (529) |
| `vpad.py`, `xemu_*.{sh,py}`, `shots/` | game | reference capture and screenshots for this title on the Linux/Proton host | none |

**Tests**

| Moves to the CLI | Stays in cat |
|---|---|
| `test_blinx2_cli.py` (as `test_cli.py`, with `fake_tree` 402 writing a `game.toml`), `test_bench_cli.py` + `testdata/bench_parity.json`, `test_bench_checks.py`, `test_bench_hold.py`, `test_package_lib.py`, `test_golden.py`, `test_game_icon.py`, `test_progress.py`, `test_pacing_stats.py`, `test_benchlog_retention.py`, `test_audio_check.py`; phase B adds `test_running_game.py`, `test_launchers.py`, `test_steamos_install.py` | `test_export_public.py`, `test_env_doc.py`, `test_unimpl_budget.py`; phase A keeps `test_running_game.py`, `test_launchers.py`, `test_steamos_install.py` |

New tests in the CLI: `test_manifest.py` (schema, defaults, errors,
the BLiNX 2 example parses to the constants the code used to carry) and
`test_wrapper.py` (the bootstrap: resolution order, the pin check, the
`[cli]` parse agrees with `tomllib`).

### D2. The manifest: `game.toml`

TOML, read with `tomllib` (Python 3.11+; the CLI floor is 3.12, D3).
Unknown keys are errors: a typo must not silently fall back to a default.
Paths are relative to the game root, with `/`. Required keys have no
default; the others default as shown. The CLI validates the manifest on
every command and prints the key and the reason on an error.

```toml
# game.toml: what xboxrecomp-cli needs to know about this game. The CLI reads
# it on every command; see <cli>/docs/manifest.md for every key.
schema = 1                            # required: the manifest format

[game]
name = "BLiNX 2"                      # required: the name players see
slug = "blinx2"                       # required: the wrapper and prog name, [a-z0-9-]
env_header = "src/env/recomp_env_game.h"   # optional: this game's recomp_env keys
env_doc = "docs/env.md"                    # optional: their documentation

[xbe]
path = "game_files/default.xbe"       # default: <data.game_files>/default.xbe
title_id = 0x4D530065                 # required: package refuses another title
# sha256 of the known dumps: the ones the goldens were recorded on. Another
# dump builds, packages and plays with a warning (doctor, package, which
# records "xbe": "unknown" in manifest.json); bench golden refuses it, since
# the references mean nothing on other code. The user's new dump (2026-10-06)
# has a different default.xbe from the old one; both are listed until the
# investigation in tasks 1.13 says whether the code moved.
sha256 = ["0c57fd72<full sha, task 1.13>", "aa186954<full sha, task 1.13>"]

[cli]
commit = "<sha>"                      # required: the xboxrecomp-cli commit this game is tested with
url = "https://github.com/apexJCL/xboxrecomp-cli.git"   # where the wrapper clones it from when it is not found beside the checkout or in external/

[toolkit]
url = "https://github.com/apexJCL/xboxrecomp.git"   # required
branch = "blinx2/portability"                       # required
commit = "6d51fa2d2b9eae4a31b22022925c6e72ad14dd04" # required

[toolchain]
llvm_mingw = "20260922"               # required for the windows target and the bench
nsis = "3.13"                         # default 3.13 (Windows build hosts only)

[pipeline]
game_name = "cat"                     # required: recomp --game-name; fixed, it is written into gen/
gen = "src/recomp/gen"                # required: the generated code
out = "analysis"                      # default: every intermediate
seeds = ["config/seed_functions.json"]            # default []
icall_seeds = true                    # default true: the toolkit's icall_feedback db, when present
spin_waits = "config/spin_waits.json" # default "": no --spin-waits
exclude_manual = "src/recomp_manual.c"            # default "": no --exclude-manual
split = 250                           # default 250 (SPLIT in the environment still wins, as today)
names_hooks = ["scripts/host_reserved_names.py"]  # default []: scripts run after names, with functions.json
ghidra = true                         # default true: the optional stage is offered

[pipeline.disasm]
text_only = true                      # default true, as upstream's README
extra_sections = ["D3D", "D3DX", "XGRPH", "DSOUND", "PSFD_I", "PSFD_B", "PSFD_P", "PSFD00", "SRCADV", "SRCED", "SRCAC", "XPP"]   # default []

[build]
exe = "cat_recomp"                    # required: the CMake target and file name (.exe on Windows)
targets = ["windows", "macos"]        # default ["windows"]
windows_dir = "build-win"             # default
macos_dir = "build"                   # default
toolchain_file = "cmake/llvm-mingw-x86_64.cmake"  # default: the CLI's own copy (phase B); phase A names the game's
# Passed on every packaging configure so a cache cannot keep a non-stock
# value; nonstock_vars are what package refuses without --allow-nonstock.
stock_cmake = ["-DXBOXRECOMP_ENHANCE=ON", "-UCAT_GEN_OPT"]   # default ["-DXBOXRECOMP_ENHANCE=ON"]
nonstock_vars = ["CAT_GEN_OPT"]       # default []
icon_var = "CAT_APP_ICON"             # default "": no icon compiled into the exe

[data]
game_files = "game_files"             # default
game_files_exclude = ["default_analysis.json", "UDATA", "TDATA"]   # default: the same
dir_env = "BLINX2_DATA_DIR"           # default <APP>_DATA_DIR, APP from package.app upper-cased
windows = "%LOCALAPPDATA%\\BLiNX2"    # default %LOCALAPPDATA%\<app>
steamos = "~/Games/BLiNX2"            # default ~/Games/<app>
macos = "~/Library/Application Support/BLiNX2"   # default ~/Library/Application Support/<app>

[input]
script_env = "RECOMP_INPUT_SCRIPT"    # default: the toolkit key a scenario's script goes in
presets = ["@attract", "@stage1", "@stage1-enemies", "@story-hub", "@story-load"]   # default []: names golden.json may use; checked when set

[golden]
json = "analysis/golden/golden.json"  # default "": no golden command
frames = "analysis/golden/frames"     # default <json dir>/frames
audio = "analysis/golden/audio.json"  # default ""

[package]
app = "BLiNX2"                        # required for package: file, app and folder names
product = "blinx2-recomp"             # default <slug>-recomp: manifest.json "product"
targets = ["windows", "steamos", "macos"]   # default ["windows", "steamos"]; macos needs build.targets to hold macos
brew = ["sdl2", "sdl3", "openssl", "libepoxy"]   # default []: Homebrew formulae the macos target links
dylib_companions = ["libSDL3.dylib=brew:sdl3"]   # default []: libraries loaded with dlopen, bundled too
content = "packaging"                 # default: README.part per target, launch.env.default.*, enhance.toml.default
templates = ""                        # default "": the CLI's templates (phase B); phase A names "packaging"
icon = "xbe"                          # default: the XBE's title image, else the generic icon

[bench]
remote_name = ""                      # default: the checkout's basename, as today
main_branch = "main"                  # default: integrate refuses another branch
toolkit_branch = "posix-host/portability"   # default "": integrate warns off this branch
toolkit_tests = true                  # default: golden runs the toolkit's Proton tests first
pacing_scenario = "stage1"            # default: the first scenario in golden.json
```

Why these and not more:
- **`cli.commit` and `toolkit.commit` are here, not in `setup-pins.json`.**
  They are deliberate choices a maintainer reviews; `setup-pins.json` is
  generated and holds download hashes. The CLI never writes `game.toml`
  (no TOML writer in the standard library, and a writer would drop the
  comments), so `pins refresh` prints the newer heads and the maintainer
  edits the two lines (D4).
- **`pipeline.game_name` is separate from `game.slug`**: recomp writes it
  into every gen/ file (382), so it is fixed for the life of the game;
  the slug is what the user types.
- **`xbe.sha256` is a list** (user decision, 2026-10-06). A PAL dump
  builds fine, so build and play only warn and record; the goldens are
  only meaningful on the dump they were recorded on, so `bench golden`
  (check and record alike) refuses an unknown dump before any run. An
  empty list turns the check off. The title ID keeps refusing a wrong game
  (1859). Two BLiNX 2 dumps exist today (`0c57fd72…` current,
  `aa186954…` old); whether their code differs is task 1.13, and the list
  holds whatever that finds.
- **`input.presets` only validates `golden.json`.** The presets are
  compiled into `src/pad_input.c`; the CLI cannot derive them. The list
  catches a scenario naming a preset that does not exist.
- **`bench.*` is policy, not host config.** `BENCH_HOST`, `BENCH_DIR`,
  `PROTONPATH` and the rest stay in the environment and
  `scripts/bench.env` (per user, gitignored), as the `BENCH_*` table of
  `bench --help` says. The manifest holds what the project decides for
  every developer: which branch integrates, which toolkit branch is
  expected, whether the toolkit tests gate golden.
- **The toolchain file** moves to the CLI in phase B because Burnout 3
  has none and `_local/bench host.sh` copies cat's. Until then the manifest
  names the game's.
- **`env_header` and `env_doc`** are reserved: `doctor` reports whether
  they exist, and the `test_env_doc.py` check becomes a CLI command in a
  follow-up. Nothing else reads them in this change.

**What Burnout 3 needs** (from `regen.sh`, `CMakeLists.txt`,
`src/game/CMakeLists.txt`, `TESTING.md`, `_local/bench host.sh`; not done
here):

```toml
schema = 1
[game]      name = "Burnout 3: Takedown"; slug = "burnout3"
[xbe]       path = "Burnout 3 Takedown/default.xbe"; title_id = <from the dump>
[toolkit]   url, branch, commit = the fork branch the port is tested with (today a374605-based worktrees, not main)
[toolchain] llvm_mingw = "20260922"
[pipeline]  game_name = "burnout3"; gen = "src/game/recomp/gen"; out = "build/xr"
            seeds = ["config/seed_functions.json"]; exclude_manual = "src/game/recomp/recomp_manual.c"
            split = 1000; spin_waits = ""; names_hooks = []
[pipeline.disasm] text_only = false        # regen.sh: every code section, never --text-only
[build]     exe = "burnout3"; targets = ["windows"]
[data]      game_files = "Burnout 3 Takedown"
[input]     script_env = "RECOMP_PAD_SCRIPT"
[bench]     toolkit_branch = ""; toolkit_tests = false
```

Three things the follow-up must check rather than assume: (1) `regen.sh`
calls `abi_analysis` with `--functions`/`--identified` (60-63) where cat
uses `--disasm-dir`/`--func-id-dir` (489-503); the CLI follows the toolkit
it is pinned to, so b3 on the fork toolkit takes the dir flags and that
has to be verified on the fork's `tools/abi_analysis`. (2) The exe lands in
`bin/` (`RUNTIME_OUTPUT_DIRECTORY`, `src/game/CMakeLists.txt` 45-48), not
in the build dir as `build()` 337 expects: `build.exe_dir` (default: the
build dir) is the one key this list adds to the schema above. (3) The
game dir has a space in its name; every path the CLI builds is an argument
list, never a shell string (174-177), and the host scripts quote `$XBE`
and `$GAME_FILES`; the parity test gains a case with a space. Packaging,
golden and the data folders are optional sections and b3 starts without
them. `Setup.cmd`/`setup.ps1` and `regen.sh` would become one-line
wrappers like `blinx2`, or stay as upstream's for the upstream clone; that
is the follow-up's call.

### D3. The repository and the package

```
xboxrecomp-cli/
  pyproject.toml          [project] name = "xboxrecomp-cli", version from a VERSION constant,
                          requires-python = ">=3.12", dependencies = [] ;
                          [project.scripts] xbr = "xboxrecomp_cli.main:main" ;
                          [dependency-groups] dev = ["pytest", "ruff"] ;
                          [tool.ruff] as cat's (line-length 100, E F W I UP B, E501 and UP031 ignored,
                          target-version = "py312")
  uv.lock                 the interpreter and the dev group; nothing at runtime
  .python-version         >=3.12
  README.md               what it is, the wrapper, game.toml, the override, the gates
  docs/manifest.md        every key, its default and who reads it
  src/xboxrecomp_cli/
    __init__.py           VERSION, SCHEMA (the manifest format this CLI reads)
    main.py               argparse, COMMANDS, the help text with @slug@ rendered, native_target, bench dispatch
    manifest.py           load, validate, defaults, Paths (every absolute path the code used to build from ROOT)
    host.py               host_os, host_arch, exe_suffix, say/step/mark, run(), CliError
    toolkit.py            toolkit_dir, tool_python, toolkit_state, clone_at_pin, pin mark
    cli_dir.py            the CLI's own dir and pin check (doctor's "cli:" row)
    env.py                find_uv, UV_MIN, uv_env, lock_in_step, sync_venv
    fetch.py              download, extract, check_archive_members, fetch_mingw, fetch_nsis, MINGW_ASSETS
    setup.py              run_setup, setup_needs, host_blockers
    doctor.py             doctor_report, makensis, brew, quarantine, Windows path warnings
    pins.py               pins refresh (hashes), the "newer heads" report
    pipeline.py           the stage commands, STAGES, the generation key
    build.py              build(), build_tools, mingw_root, STOCK args from the manifest
    package/__init__.py   plan, stage_payload, write_common, write_manifest, package()
    package/lib.py        package_lib.py
    package/icon.py       game_icon.py
    package/progress.py   progress.py
    package/windows.py, steamos.py, macos.py   wrap_* and build_launcher_exe
    package/templates/    phase B: installer.nsi.in, launcher.c, app.rc.in, app.in (macOS), Info.plist.in,
                          install.sh, install_lib.py, launch.sh, README.txt.in, with @APP@ @NAME@ @PRODUCT@ @DATA_ROOT@
    bench/__init__.py, config.py, remote.py, sync.py, checks.py, golden.py, pacing.py
    bench/host/*.sh       the host scripts, as today
    golden.py             the compare engine (scripts/golden.py), also `xbr golden <subcommand>`
    pacing_stats.py, benchlog_retention.py, audio_check.py
    running_game.py       phase B, with --exe
    wrapper/game.py       the bootstrap template every game vendors as `<slug>.py` (D4); `xbr wrapper --check` diffs a game's copy
    cmake/llvm-mingw-x86_64.cmake   phase B
  tests/                  the moved tests (D1), test_manifest.py, test_wrapper.py, testdata/
```

- **One package, flat modules.** The code is one `blinx2.py` today; the
  split follows its section headers (host, build, pipeline, key, setup,
  doctor, pins, package, CLI) so a reader of 70bf5c8 finds each function
  where its comment banner was. No class hierarchy, no plugin system: a
  game is data, not code.
- **`Paths`**: every `os.path.join(ROOT, …)` constant in `blinx2.py`
  (37-41, 373-377, 506-510, 722-723, 927-928, 1705-1706) becomes an
  attribute computed once from the game root and the manifest. The gen
  key's `_placeholders()` keeps `$ROOT` and `$TK` so existing
  `gen.key.json` files stay valid (the key must not change: D5 gate).
- **Python 3.12** for the CLI: `tomllib` (3.11), `tarfile`'s `data` filter
  without the fallback (1077-1082), and the dev group's numpy floor the
  toolkit's tests need. uv provides the interpreter (as `.python-version`
  already asks for in cat); the wrapper stays 3.9 so a host with only the
  system Python can print `--help`, the uv hint and `doctor`'s first lines.
- **`xbr`** is the console script. Nobody types it: the game's wrapper
  passes `--game <root> --prog <slug>` so the help reads `blinx2 …` byte
  for byte as today (`prog="blinx2"` 2374).
- **ruff and pytest** as cat's gates: `uv run ruff check . && uv run ruff
  format --check .` and `uv run pytest tests`. The CLI's tests run on
  macOS and Linux; the parity test is skipped on Windows as today.
- **Standard library at runtime** stays the rule: `dependencies = []`.
  cmake, ninja, capstone and pefile are the *game's* tools environment
  (`<game>/pyproject.toml`, `uv.lock`, `.venv`), made by `setup` with `uv
  sync --locked --project <game>` as today (1247-1249). They are pinned
  per game because capstone's version is a gen/ input (the comment in
  cat's `pyproject.toml`).
- **Help text**: `main.py` keeps the docstring block verbatim with
  `@slug@` for `blinx2`; the gate diffs `./blinx2 --help` against 70bf5c8.

### D4. Pinning and the wrapper

The chain: a game commit names a CLI commit (`game.toml` `[cli]`); that
pair names a toolkit commit (`[toolkit]`); `setup-pins.json` names the
download hashes; `uv.lock` names the Python wheels. Each link is a sha
checked out and verified, never a branch head resolved at install time.

**The wrapper** is three files in the game, as today: `blinx2` (sh),
`blinx2.cmd`, both exec `blinx2.py` with the host's Python 3; `blinx2.py`
becomes the bootstrap (about 60 lines, standard library, Python 3.9, a
copy of the CLI's `wrapper/game.py` template, named after the game). It:

1. reads `[cli]` from `game.toml` with a line parser for `commit = "…"`
   and `url = "…"` inside that table (the schema requires plain,
   one-per-line strings there; `test_wrapper.py` checks the parse agrees
   with `tomllib` on the real manifest);
2. finds uv on `PATH` (`UV_MIN`, the per-OS hint, as 1141-1191); without
   it, prints the hint and exits 1, except for `--help`, which it prints
   itself;
3. finds the CLI: `$XBOXRECOMP_CLI_DIR`, else `external/xboxrecomp-cli`,
   else `../xboxrecomp-cli`, the order `toolkit_dir()` 124-133 uses for
   the toolkit;
4. when none is found and `cli.url` is set: `git clone <url>
   external/xboxrecomp-cli` and `git checkout <commit>`, writing
   `.xbr-pin` as `clone_toolkit` 1278-1294 does (the mark goes into the
   clone's `info/exclude`, 1252-1275); with no URL it prints "no
   xboxrecomp-cli: clone it beside this checkout, or set
   XBOXRECOMP_CLI_DIR";
5. execs `uv run --project <cli> --locked xbr --game <root> --prog
   <slug> <argv>`.

The CLI then checks its own HEAD against `cli.commit`: equal, or the
`.xbr-pin` mark is absent (a developer's checkout), it goes on; a marked
clone at another commit means the game moved its pin and `setup` has to
re-checkout; `doctor` prints `cli: <path> @ <sha> (pinned | differs from
the pin <sha>)` beside the `toolkit:` row (1513-1535). Nothing refuses: a
developer pointing at a newer CLI is the normal way to test one.

**No network surprises.** The wrapper reaches the network only in step 4
and only for a clone at a sha; `uv run --locked` never resolves; `setup`
runs `uv sync --locked` for the game's tools environment and `clone_toolkit`
at its pin. If no Python ≥ 3.12 exists, uv fetches one and verifies it
against hashes built into uv (the same as today's `.python-version`).

**Working on the CLI and a game together.** `XBOXRECOMP_CLI_DIR` points
at the developer's CLI worktree, as `XBOXRECOMP_DIR` points at a toolkit
worktree. `uv run --project <cli>` runs the source tree directly (uv
installs the project editable into the CLI's own `.venv`), so there is no
install step. A feature pair is `wt/<name>/{cat,xboxrecomp-cli}` with the
variable set in the agent's shell; `doctor` shows which CLI is in use.
`pins refresh` prints the heads of the CLI's `main` and the toolkit
branch next to the pinned shas; moving a pin is an edit to `game.toml`
reviewed in the game's commit, which is the point.

**`setup-pins.json`** keeps `llvm_mingw` and `nsis` (hashes for the tag
and version the manifest names) and drops `toolkit` (its three fields
move to `game.toml`). `config/toolchain.env` goes: `mingw_tag()` 217-222
and `config.py` 86-95 read the manifest.

### D5. Migration, cat first

| Phase | Lands | Gates |
|---|---|---|
| A: the code moves | The `xboxrecomp-cli` repository (D3, one commit, D6); cat: `game.toml`, the bootstrap `blinx2.py`, `pyproject.toml` renamed, `setup-pins.json` without `toolkit`, `config/toolchain.env` deleted, the moved files deleted, `test_bench_cli.py`'s record moved with the paths it normalises; `package.templates = "packaging"` and `build.toolchain_file = "cmake/llvm-mingw-x86_64.cmake"` so the CLI reads the game's templates and toolchain file where they are; `running_game.py` stays and the host scripts call it as today | G1 `./blinx2 --help` and `./blinx2 bench --help` byte-equal to 70bf5c8's. G2 the CLI's `test_bench_cli.py` passes against the moved `bench_parity.json` with no fixture edit except the `provenance` case (one added `cli:` line, see below) and the `GAME_ARGS` normalisation already there. G3 `src/recomp/gen.key.json` unchanged by the move: `./blinx2` on a tree with a fresh key plans `build, package` only (no regenerate). G4 packaging on the Mac (`package macos`, `package windows`, `package steamos`) and on Linux in the Linux/Proton distrobox (`package steamos`, `package windows --no-build`): each payload's file list and every file's sha256 equal to the same commit packaged with 70bf5c8's `blinx2.py`, except `manifest.json`/`SHA256SUMS` (`built`, `version`, the new `sources.cli`) and the exe's embedded timestamps. G5 `uv run pytest` in both repositories; ruff in both. G6 the Linux/Proton host: `blinx2 bench integrate --golden` from the main checkout (the orchestrator), same verdict and `run-info.txt` fields as the previous integrate; `@attract` on Metal on the Mac. G7 a fresh clone of cat on the Mac with `XBOXRECOMP_CLI_DIR` unset and `../xboxrecomp-cli` present runs `./blinx2 doctor` and `./blinx2 setup`; the same with the CLI absent and `cli.url` set clones it at the pin |
| B: the mechanism moves | The CLI owns `package/templates/`, `cmake/llvm-mingw-x86_64.cmake`, `running_game.py --exe`; cat's `packaging/` keeps `README.part` per target, `launch.env.default.*`, `enhance.toml.default`; `package.templates` and `build.toolchain_file` default to the CLI's; the host scripts take `EXE`, `GEN_DIR`, `XBE` and `GAME_FILES` from the prologue and `run_game.sh` calls `running_game.py --exe "$EXE"` from a synced `$BENCH_DIR/xboxrecomp-cli/` (one more rsync in `sync`, with the toolkit's excludes) | G4 again, byte-equal payloads for all three targets (the rendered templates must equal today's files: `@APP@` → `BLiNX2`). G2 with the record re-recorded for the prologue and `run_game.sh` lines that changed; the diff of the record is reviewed line by line and is only those assignments. G6 again. `test_launchers.py`, `test_steamos_install.py`, `test_running_game.py` move and pass |
| Follow-up, not here | Burnout 3's `game.toml` (D2), its wrappers, the three checks | its own spec |

The `provenance` line (`checks.py` 155-163) gains `cli: <sha> <branch>
<clean|dirty>` so `bench-provenance.txt`, `build-win/provenance.txt` and
`run-info.txt` say which CLI synced and built; `package_lib.tree_state`
runs on the CLI dir too and `manifest.json` `sources` gains `cli`; the
version string keeps its `-c…-t…-g…` form (a third sha would change every
version for no reader), and a dirty CLI tree makes the version `-dirty`
like a dirty toolkit (118-121), because in phase B the CLI's templates are
in the payload.

Each phase is one branch in the agent's worktree pair
(`wt/cli/{cat,xboxrecomp-cli}`), squash-merged by the orchestrator after a
Fable review. Phase A's CLI commit is the repository's first commit; its
cat commit is `toolchain: the CLI moves to xboxrecomp-cli; game.toml and
the bootstrap wrapper` and names the CLI sha it pins.

### D6. History: start fresh, cite the shas

**Recommendation: one initial commit, no `git filter-repo`.**

- The files' history in cat is not theirs alone. `blinx2.py` was born in
  the packaging change (333358e) and grew through `toolchain-cli` phases
  0, 1, 2 and 4 (1623e8b, 61ea933, 25ec32c, 70bf5c8), each a squash of a
  branch whose subjects mix game and tooling work; a filtered history
  would carry those commits with most of their diffs stripped, which is
  the "long history" the user does not want in a lean repository.
- The private identity. Every cat commit carries the private author
  address; a carried history would need the mailmap scrub before the CLI could
  ever be public, as the toolkit push rounds do. A fresh commit is written
  with the identity the moment asks for.
- The history is not lost: cat keeps every branch (the workspace rule),
  and `git log --follow` in cat answers "why is this line here" for
  anything older than the move.
- `git-filter-repo` is not installed; the tool is not the reason, but it
  would be one more step to get right.

The first commit's subject is `cli: extract the toolchain CLI from
blinx2-recomp` and its body names cat 70bf5c8 and the five commits above,
and ships `docs/origin.md`: a table of every file in the CLI with the cat
path it came from, so blame starts with a pointer.

### D7. The public story (decided by the user, 2026-10-06)

Today the public `apexJCL/blinx2-recomp` is `export-public.sh`'s snapshot
of cat and contains `blinx2.py` and `scripts/`. After phase A the public
tree depends on the CLI at `cli.commit`.

**The user decided: `xboxrecomp-cli` is its own public repository,
`apexJCL/xboxrecomp-cli`, not vendored.** The public `blinx2-recomp`
depends on it at the pinned sha through `cli.url` and `cli.commit` in its
`game.toml`; the wrapper clones it at that sha as it clones the toolkit.
The draft's vendoring option is dropped.

The public CLI follows the lean-public-repos rules, adapted:

- **Only `main`.** There is no upstream to mirror, so `main` is both the
  integration branch and the public branch. Feature branches stay local
  (`feat/cli-a-move`, `feat/cli-b-templates`, later ones), squash-merged
  onto `main` as in cat.
- **Fresh history, public identity from the first commit.** Because the
  repository is public from its first push and every commit on `main` is
  pushed as is (fast-forward, no export script, no scrub), the local
  `main` is authored and committed as
  `carlos <4037632+apexJCL@users.noreply.github.com>` from the first
  commit. This is the one tree where the workspace's private local
  identity is not used; the squash merge's `--author` and
  `GIT_COMMITTER_*` are set by the orchestrator at merge time, and a
  pre-push check (`git log --format='%ae %ce' origin/main..main`) must
  show only the noreply address.
- **Batched push rounds at milestones**, each asked of the user, and
  ordered: the CLI round first, then `blinx2-recomp`'s, because the sha
  cat's public `game.toml` pins must already exist on the public CLI, or
  a fresh public clone cannot clone it.
- **The audit before every push** covers the whole delta
  (`git diff origin/main..main`, and the full tree on the first push):
  host names (the bench host's name must not appear; the CLI's text says
  "the bench host" or "the Linux/Proton host"), private paths
  (`/Users/`, `/home/`, `/var/home/`, the workspace path), the personal
  email, claude.ai links, binaries, game data (no XBE, frame, hash of a
  game frame, WAV or save; the tests' XBEs and frames are synthetic), and
  nothing from `tests/testdata` that came from a real run. A small
  `scripts/audit-public.sh` in the CLI runs the greps so the round is one
  command; the first push also runs it over the whole tree.
- **No `export-public.sh` for the CLI.** cat's stays as it is, minus any
  rule that only existed for the moved files.

The public `game.toml` of `blinx2-recomp` is the private one: the export
copies it unchanged, since `cli.url` and `toolkit.url` are public URLs
and the shas are public once the rounds are ordered as above. `cli.url`
is therefore set in cat's `game.toml` from phase A, and `setup`'s clone
of the CLI works for the user's own machines as well.

### D8. Upstream README adherence, and the eventual offer

The CLI's pipeline is the upstream README's Quick Start, steps 3 to 8,
with the same modules and flags: `tools.xbe_parser … --json` (425),
`tools.disasm --text-only [--extra-sections]` (453-465), `tools.func_id`
(469), `tools.abi_analysis` (489), the optional Ghidra naming (606-678,
the same scripts with the runtime tag swapped), `tools.recomp --all
--split N --gen-dir` (533-561). Where it deviates, and the verdict
(upstream-readme-adherence):

| Deviation | Why | Verdict |
|---|---|---|
| Intermediates under the game (`-o`, `--analysis-json`, `--disasm-dir`) instead of `tools/*/output` | two games cannot share one toolkit's `output/` (366-371); `tools/doctor.py` has flags for every path | argue upstream, when offered |
| The tools run with the game's `.venv` Python, not `py -3` | a pinned capstone per game, since the lifter decodes with it | argue upstream (upstream's own `tools/macos/setup.sh` makes a venv) |
| `--spin-waits`, `--exclude-manual`, `icall_feedback seeds` | fork flags the pipeline uses; the manifest turns each off with an empty value, so a game on upstream `main` runs the README's command line. `--game-name` is always passed: upstream `main` has it since d12e466 (`tools/recomp/__main__.py`), and recomp writes the name into every `gen/` file, so a default taken from the checkout folder would change `gen/` bytes with the folder | fork-only until those flags are offered; the follow-up checks which exist on upstream `main` before Burnout 3 moves |
| MSVC is the README's compiler; the CLI builds with llvm-mingw | there is no Windows build host; Burnout 3 is tested the same way under Proton | argue upstream (both are CMake toolchains; the CLI could take a `build.generator` later) |

The CLI never touches the toolkit, so the fork's upstream diff is
unchanged by this change. An offer of the CLI to upstream, as a sibling
repository or a `tools/cli` directory, waits for the give-back milestone
(both games stable) and is a user decision; its Fable review would check
the README again from `origin/main` at that time. The manifest keeps the
upstream shape reachable (`text_only = true`, no fork flags by default) so
such an offer would not need a rewrite.

### D9. Rules kept

- **recomp_env.** No game variable changes. `BLINX2_DATA_DIR` keeps its
  name through `data.dir_env`; `BENCH_*` and `XBOXRECOMP_CLI_DIR` are
  controller variables the game never reads; `docs/env.md` "Not in the
  table" names the CLI for them.
- **stdlib-first.** The CLI has no runtime dependency; the bootstrap is
  3.9 standard library; uv and ruff are development tools.
- **Never publish game data.** The CLI repository holds none: the moved
  tests use synthetic XBEs, synthetic frames and `fakehost`; `golden.json`
  (hashes of game frames) stays in cat. The CLI's own pre-push audit (D7)
  checks it before every round.
- **Opt-in, backends agree.** Not applicable: no runtime behaviour.
- **Generated code.** `gen/` is untouched; G3 proves the key is stable.
- **export-public.** Stays in cat, excluded from the export, shell.

### D10. Workspace lines for the orchestrator

CLAUDE.md (outside this repo), after phase A:

| Line | Today | After |
|---|---|---|
| Layout | `cat/` … `xboxrecomp/` … | add `xboxrecomp-cli/`: the toolchain CLI (branch `main`), a main checkout with the same read-only rule; worktrees `wt/<name>/xboxrecomp-cli` |
| Gates | `pytest tools/recomp tools/disasm` when tools changed | add `uv run pytest tests` and ruff in `xboxrecomp-cli/` when the CLI changed |
| Code style, generated code | `blinx2 analyze` then `blinx2 recomp` | unchanged wording; add "the CLI reads `game.toml`; game constants go there, never in the CLI" |
| Public repos | the two bullets for `blinx2-recomp` and the toolkit fork | add the bullet below |

The new CLAUDE.md bullet under "Public pushes", to apply verbatim:

> - `apexJCL/xboxrecomp-cli` mirrors the local `xboxrecomp-cli/` `main`
>   with fast-forward pushes and no export script: every commit on that
>   `main` is authored and committed as
>   `carlos <4037632+apexJCL@users.noreply.github.com>` from the first
>   commit (the private local identity is never used there; squash merges
>   set `--author` and `GIT_COMMITTER_*`). Only `main` exists publicly;
>   feature branches stay local. Push rounds are batched at milestones and
>   the CLI's round goes before `blinx2-recomp`'s, so the sha cat's public
>   `game.toml` pins already exists. Before each push run
>   `scripts/audit-public.sh` over `origin/main..main` (host names, private
>   paths, the personal email, claude.ai links, binaries, game data) and
>   check `git log --format='%ae %ce' origin/main..main` shows only the
>   noreply address.

And under "Keep the public repos lean", the line `The toolkit fork has
only main …` gains: `xboxrecomp-cli has only main.`

Memory notes to amend: `cat-blinx2-project` (where the CLI lives),
`subagent-required-tasks` (toolkit patches: the CLI is a third tree),
`disk-hygiene` (worktree pairs become triples when the CLI changes),
`lean-public-repos` and `public-repo-blinx2` (the third public
repository, the round order, the identity rule for its `main`).

## Risks / Trade-offs

- **A silent behaviour change hidden in the move.** Mitigation: G1-G7
  are byte comparisons, not judgement; the record and the gen key are the
  two that catch what a reviewer would not.
- **Two repositories drift.** A game pinned to an old CLI keeps working
  (that is the pin's job); the cost is `pins refresh` reminding the
  maintainer. `doctor` says which CLI is in use so a stale
  `XBOXRECOMP_CLI_DIR` in a shell cannot be mistaken for the pin.
- **The bootstrap's `[cli]` line parser.** It reads two keys in one
  table; a schema rule and a test keep it honest; a malformed manifest
  fails loudly in the CLI's validator the moment it starts.
- **Phase B rendering.** A template with `@APP@` rendered to `BLiNX2`
  must give today's bytes; G4 says so per file, and any `BLiNX`-specific
  wording left in a template (`README.txt.in` says "BLiNX 2" in its
  notice) moves to the game's content files first.
- **A public clone pins a sha that is not public yet.** The round order
  (CLI first) prevents it; the audit script also checks that cat's
  `cli.commit` is reachable on the public CLI before cat's round.
- **The identity rule differs per tree.** The CLI's `main` is noreply
  from the start while cat and the toolkit stay private locally; the
  pre-push identity check catches a slip before it is pushed, which is
  cheaper than the rewrite the first toolkit push needed.
- **Burnout 3's toolkit differences** (D2) are unknowns; they are the
  follow-up's first task, and nothing here depends on them.

## Decided

The user answered the draft's three questions on 2026-10-06. These are
binding and the sections above are written to them.

1. **The public story (D7): `xboxrecomp-cli` is its own public
   repository**, `apexJCL/xboxrecomp-cli`, not vendored. `blinx2-recomp`'s
   export depends on it at a pinned sha. Lean rules: only `main`, batched
   rounds, the noreply identity, the pre-push audit. History starts fresh
   (D6).
2. **A third main checkout** `xboxrecomp-cli/` on `main`, console script
   `xbr`, `./blinx2` kept as the wrapper: approved.
3. **Unknown dump (D2):** build and play warn; `bench golden` refuses.
   The user's new dump has a different `default.xbe` (`0c57fd72…`) from
   the old one (`aa186954…`); the known-dump list takes the current one,
   or both, pending the investigation into whether the code moved (task
   1.13).

Everything else was decided by the spec: the split (D1), the manifest
(D2), 3.12 through uv with a 3.9 bootstrap (D3), the pin chain and the
`XBOXRECOMP_CLI_DIR` override (D4), two phases with byte gates (D5), a
fresh history (D6), the adherence verdicts (D8).
