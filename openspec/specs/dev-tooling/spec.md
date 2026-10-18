# dev-tooling Specification

## Purpose
Defines the project's Python tooling: the uv-managed environment from a committed lockfile, uv from `PATH`, ruff as the lint and format gate, pytest through uv, and the standard-library rule for code that runs on players' and bench hosts.

## Requirements

### Requirement: The Python environment is managed by uv from a committed lockfile
The project SHALL declare its Python dependencies in `pyproject.toml` at the repository root (`requires-python >= 3.9`; cmake, ninja, `capstone==5.0.9`, `pefile==2024.8.26`; a `dev` dependency group with pytest and ruff) and SHALL commit `uv.lock`, in which every package entry carries a sha256 hash. `blinx2 setup` SHALL create or update `.venv/` with `uv sync --locked`, adding the `dev` group only with `--dev`, and SHALL fail when the lockfile does not match `pyproject.toml`. `config/requirements-setup.txt`, `config/requirements-dev.txt` and the hand-written PyPI resolver in `blinx2 pins refresh` SHALL be removed; `pins refresh` SHALL run `uv lock --upgrade` for the Python half. The venv path SHALL remain `.venv/`, so the tool paths `blinx2` and `doctor` use are unchanged.

#### Scenario: Locked install
- **WHEN** `blinx2 setup` runs with a `uv.lock` in step with `pyproject.toml`
- **THEN** `.venv/` holds exactly the locked versions, with `capstone` at 5.0.9, and nothing is resolved against PyPI

#### Scenario: Stale lockfile
- **WHEN** `pyproject.toml` has changed and `uv.lock` has not
- **THEN** `setup` exits non-zero saying the lockfile is out of date and naming `blinx2 pins refresh`, and `.venv/` is not changed

#### Scenario: The lockfile is tested
- **WHEN** `scripts/test_blinx2_cli.py` runs
- **THEN** it asserts that every package in `uv.lock` has a sha256 hash and that capstone is pinned at 5.0.9

### Requirement: uv comes from PATH and is never installed by the project
`blinx2 setup` SHALL use the `uv` on `PATH` and SHALL NOT download or install uv. When no `uv` is on `PATH`, or it is older than the minimum `blinx2.py` names, `setup` SHALL exit non-zero and `doctor` SHALL report it, each with the install command for the host's OS (macOS, Linux including immutable hosts, Windows). `blinx2.py`, `blinx2` and `blinx2.cmd` SHALL run with the standard library alone, so they start, print help and run `doctor` without uv. `config/setup-pins.json` SHALL carry no uv pin. `doctor` SHALL report the uv path and version in use.

#### Scenario: Fresh clone with uv on PATH
- **WHEN** `./blinx2 setup` runs in a fresh clone on a host with Python 3.9 or newer and `uv` on `PATH`
- **THEN** setup creates `.venv/` from `uv.lock` with that uv, downloads no uv, and `doctor` prints the uv path and version

#### Scenario: No uv
- **WHEN** `./blinx2 setup` runs on a host with no `uv` on `PATH`
- **THEN** it exits non-zero naming uv and the install command for that OS, and `./blinx2 doctor` still runs and lists uv as missing with the same command

### Requirement: ruff lints and formats every Python file in this repository
`pyproject.toml` SHALL configure ruff for `blinx2.py`, `scripts/`, `packaging/` and any other Python file in the repository, excluding generated code, `external/`, `third_party/`, virtual environments, `analysis/` and build directories. `uv run ruff check .` and `uv run ruff format --check .` SHALL be per-merge gates. The first formatting pass SHALL be a commit of its own with no behaviour change, listed in `.git-blame-ignore-revs`. The toolkit's `tools/` SHALL NOT be touched by this configuration; it follows later through the fork as a separate change.

#### Scenario: Gate
- **WHEN** a branch is proposed for merge
- **THEN** `uv run ruff check .` and `uv run ruff format --check .` both exit 0 on it

#### Scenario: Format commit stands alone
- **WHEN** the format commit is checked out and `uv run pytest scripts` runs before and after it
- **THEN** the same tests pass, and the commit's diff contains no change outside formatting and the agreed renames

### Requirement: Tests run through uv
`uv run pytest scripts` SHALL run every `scripts/test_*.py`, with pytest coming from the `dev` group, and SHALL be a per-merge gate when any Python under the repository changes. Each test file SHALL still run alone under the system Python with plain asserts, as today.

#### Scenario: System Python without pytest
- **WHEN** the host's Python has no pytest and the developer runs `uv run pytest scripts`
- **THEN** the suite runs from the locked environment and reports every test file

### Requirement: Runtime code stays standard-library
`blinx2.py`, `scripts/benchlib/` and the scripts the game, the launchers and the bench host run SHALL import only the standard library. uv and ruff are development tools; cmake, ninja, capstone and pefile are what `setup` installs for the toolkit's tools, as before. A new third-party runtime dependency SHALL be justified in a spec before it is added.

#### Scenario: Import audit
- **WHEN** `blinx2.py` and every module under `scripts/benchlib/` are imported with only the standard library available
- **THEN** every import succeeds

### Requirement: A new game starts from one command
`xbr new DIR` SHALL write a complete starter game into an empty or absent
`DIR`: a `game.toml` that `manifest.load` accepts with every pin filled in
(the CLI commit it runs from, the toolkit branch head or a checkout's HEAD),
the bootstrap `<slug>.py` byte-identical to the CLI's `wrapper/game.py`,
the `<slug>` and `<slug>.cmd` wrappers, the tools `pyproject.toml`,
`.gitignore`, `README.md`, and the toolkit's `templates/new-game/` with the
game's name, executable name, entry point, title ID and game-files path
patched in. When the network, git and uv allow, it SHALL also clone the
toolkit at the pin and write `config/setup-pins.json` and `uv.lock`; when
one of those fails or `--offline` is given, it SHALL still write the files
and name the command that finishes each missing piece. It SHALL never
overwrite a file, never copy, move or link a dump, and SHALL end by naming
the next three steps (the dump into `game_files/`, `setup`, `all`).

#### Scenario: A scaffold loads and checks
- **WHEN** `xbr new d/mygame` runs with a fake toolkit template, a fake git and no network
- **THEN** `manifest.load("d/mygame")` succeeds, `./mygame wrapper --check` reports the template unchanged, and the output names `setup` and `pins refresh` as the steps left

#### Scenario: The XBE fills the constants
- **WHEN** `d/mygame/game_files/default.xbe` exists (or `--xbe` names one) with a synthetic header whose title is `T`, title ID `0x4B4C0001` and entry point `0x00123456`
- **THEN** `game.toml` has `name = "T"` and `title_id = 0x4B4C0001`, and `src/main.c` defines the entry point `0x00123456`, and the dump is not copied

#### Scenario: A changed template is reported
- **WHEN** a patch of the template matches nowhere
- **THEN** the copy still lands and the output says which edit to make by hand; a patch that matches more than once is treated the same

#### Scenario: Refusals
- **WHEN** `DIR` holds a file, or `--slug` is not `[a-z0-9-]`
- **THEN** `new` writes nothing and exits 1 with the reason

### Requirement: The entry point needs no checkout
`xbr new` SHALL run through `uvx --from git+<cli url> xbr new …` and pin
`cli.commit` to the commit uv installed (the distribution's `direct_url.json`),
or from a clone with `uv run xbr new …`, pinning the clone's HEAD. The
README SHALL give both, the uvx form with the `@<sha>` way to pin it, and
SHALL offer no `curl | sh` of its own (uv's installer, in the prerequisites,
is Astral's).

#### Scenario: The pin is the running commit
- **WHEN** `xbr new` runs from a checkout at commit C
- **THEN** the scaffold's `cli.commit` is C, and from an installed distribution whose `direct_url.json` names commit D it is D

### Requirement: A first run ends in messages, not tracebacks
A game without `config/setup-pins.json` SHALL get a `CliError` from `setup`
that names `pins refresh`; `doctor` SHALL close with one `next:` line
naming the first fix in setup order; the copied `main.c` SHALL declare
`recomp_dispatch_init` so it compiles under Clang.

#### Scenario: No pins
- **WHEN** `setup` runs in a game with no `config/setup-pins.json` and a `toolchain.llvm_mingw`
- **THEN** it exits 1 with a message that names `<slug> pins refresh`, and no traceback

### Requirement: The README is written for a porter
The CLI's README SHALL open with what the CLI is and the legal stance (your
own dump, nothing fetched or published is game data, enhancement assets are
made locally and never distributed), then prerequisites, the quickstart,
porting a first game, the command reference pointers with `docs/manifest.md`
as the reference, the bench host as optional, troubleshooting, and the
maintainer material last. It SHALL mention the housekeeping work on
`feat/cli-housekeeping` only as coming.

#### Scenario: Five steps
- **WHEN** a developer with uv, git and a dump follows the quickstart on a Mac or Linux host
- **THEN** the steps are: install uv and git, `xbr new`, the dump into `game_files/`, `<slug> setup`, `<slug> all`, and the result is `build-win/<exe>.exe`

### Requirement: Windows is a development host on the same path
The quickstart SHALL work on Windows with the same five steps, through the
`py` launcher (`<slug>.cmd`, or `py -3 <slug>.py`), llvm-mingw fetched by
`setup` (never Visual Studio through the CLI), and the same `uvx` one-liner
in PowerShell; the README SHALL give the Windows prerequisites, the path
rules (a short checkout path, `core.longpaths`, a Defender exclusion) and
say that a Windows host is untested until a run verifies it. The scaffold
SHALL write `<slug>.cmd` with CRLF and a `.gitattributes` that keeps `*.cmd`
CRLF and the scripts, `.py`, `.toml` and `.in` files LF.

#### Scenario: The Windows wrapper
- **WHEN** `xbr new` writes `<slug>.cmd`
- **THEN** it runs `py -3 "%~dp0<slug>.py" %*` when `py` exists, else `python`, exits with the bootstrap's status, and every line ends in CRLF

#### Scenario: doctor on a Windows host
- **WHEN** `doctor` runs on a Windows host (mocked) in a fresh scaffold
- **THEN** its `next:` line names the `winget` uv install, and the report keeps its long-path warnings

### Requirement: A scaffolded game builds and boots on Windows and macOS
The toolkit's `templates/new-game/` SHALL be a two-host game: one `src/main.c`
whose boot sequence is shared and whose host-specific parts (the crash
handler and its symbol lookup, the fatal-step dialog, the window, the entry
points) sit under `#if defined(_WIN32)` / `#else`, and a `CMakeLists.txt`
that configures and builds with llvm-mingw for Windows and with Apple clang
for macOS. On every host it SHALL honour `RECOMP_STDIO_LOG` before its
first line of output and SHALL print its crash report under the `[CRASH]`
tag. On POSIX it SHALL hand a trapped MMIO fault to `xbox_PosixMmioFault`
before reporting, SHALL run the guest under `xbox_HostWindowMain` unless
`RECOMP_HEADLESS` is set, and on Apple SHALL default `RECOMP_PB_BACKEND` to
`metal` when it is unset. The template SHALL carry no title constant other
than the `YOUR_GAME_*` macros `xbr new` patches. With `RECOMP_STDIO_LOG`
unset, the Windows build's boot sequence, VEH and crash report SHALL be
what they were before; the only allowed differences are the `[THREAD]`
and `[FATAL]` lines on stderr, the deprecation notes printed at boot
rather than at exit, no fatal dialog under `RECOMP_HEADLESS`, and the
guest-main thread marked for DPC delivery, which the toolkit requires.
`xbr new` SHALL write `build.targets = ["windows", "macos"]`, and SHALL
say so, rather than fail, when the toolkit it copies the template from
still has the Win32-only one.

#### Scenario: Both targets from one scaffold
- **WHEN** `xbr new d/g --xbe <dump>` runs with a toolkit at or after this change, then `./g analyze`, `./g recomp`, `./g build windows` and `./g build macos` on a Mac
- **THEN** both builds succeed with `src/main.c` and `CMakeLists.txt` as `new` wrote them

#### Scenario: Boot or a reported fault on macOS
- **WHEN** the macOS build runs with `SDL_AUDIODRIVER=dummy`, `RECOMP_HEADLESS=1` and a dump in `game_files/`
- **THEN** it presents frames on Metal, or it dies by SIGBUS or SIGSEGV after a `[CRASH]` report naming the signal, the host PC and the generated function, the guest registers, the guest return addresses and the native stack

#### Scenario: The log reaches the file under Proton
- **WHEN** the Windows build runs under Proton with `RECOMP_STDIO_LOG=<file>`
- **THEN** the boot lines, and the `[CRASH]` report if it crashes, are in `<file>`, and the bench's crash check reads them

#### Scenario: An old toolkit beside the game
- **WHEN** `xbr new` copies a template that has no `_WIN32` host section
- **THEN** the scaffold is written with both targets and the summary notes that `build macos` needs a newer toolkit pin or `macos` dropped from `build.targets`

#### Scenario: The template cannot rot unnoticed
- **WHEN** `tests/posix_ctest.sh` runs on the Mac, or the CLI's Proton standalone tests run on the Deck
- **THEN** `tests/template_main` compiles and links the template's `main.c` against the toolkit, exits 1 with `[FATAL] load XBE` when there is no XBE, and writes that line to `RECOMP_STDIO_LOG` when it is set
