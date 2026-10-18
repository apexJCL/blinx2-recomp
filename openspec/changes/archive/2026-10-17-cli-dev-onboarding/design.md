# cli-dev-onboarding: design

## Context

Read at xboxrecomp-cli `main` 023c77e and the toolkit `posix-host/portability`
cb43f7b. What the code gives a scaffold to build on:

- `manifest.SPEC` knows every key, its type and default, so a scaffold can
  write a manifest that `manifest.load` accepts and `validate` checks.
- `wrapper/game.py` is the bootstrap every game vendors; `wrapper --check`
  already compares a game's copy with it.
- `toolkit.clone_toolkit()` clones at the manifest's pin into
  `external/xboxrecomp` and marks it; `pins.pins_refresh()` writes
  `config/setup-pins.json` and runs `uv lock --upgrade`;
  `pins.remote_head()` asks a remote for a branch head.
- `package/lib.xbe_title_id` reads the certificate's title ID from the XBE
  header with `struct`; the entry point and the title are two more fields
  of the same header.
- `main.main()` loads the manifest before dispatch, except for nothing:
  `bench` and the tools dispatch after the load. A command that runs
  without a game has to dispatch before it.
- The toolkit's `templates/new-game/` is the canonical starter: its
  CMakeLists.txt links the Windows SDK libraries unconditionally and its
  `main.c` is Win32 (WinMain, VEH, dbghelp). It builds for the windows
  target with llvm-mingw once `recomp_dispatch_init` is declared; it does
  not build for the macos target, which needs the POSIX host code cat's
  `main.c` carries (`host_main`, signal handlers, the SDL window).

## D1. One command, `xbr new`, dispatched before the manifest loads

`xbr new DIR [options]` runs with no `game.toml` in sight, so `main()`
dispatches it right after `split_global`, as `bench` would be if it did not
need a game. `DIR` must not exist or must be empty: the scaffold never
overwrites a file. Options, each with a default that works for a first
port:

| Option | Default | Why |
|---|---|---|
| `--slug` | DIR's basename, lower-cased, `[a-z0-9-]` | the command name (`game.slug`) |
| `--name` | the XBE certificate's title, else the slug | `game.name` |
| `--xbe PATH` | `DIR/game_files/default.xbe` when it exists | read for the title, title ID and entry point; never copied |
| `--toolkit-url`, `--toolkit-branch`, `--toolkit-commit` | the fork, `blinx2/portability`, resolved (D3) | the toolkit pin |
| `--cli-commit` | resolved (D3) | the CLI pin |
| `--llvm-mingw` | the tag both games pin today | `toolchain.llvm_mingw` |
| `--offline` | off | write the files only, and name each follow-up |

What it writes, in order, and what it does not:

1. `game.toml` with the required keys filled and the defaults written out
   with their comments, so the file reads as documentation. `title_id`
   is the XBE's when one was read, else `0` with a comment saying so
   (`package` refuses a mismatch, so a wrong value cannot ship).
2. `<slug>.py` (the bootstrap, byte for byte: `wrapper --check` passes),
   `<slug>` (sh, executable) and `<slug>.cmd`.
3. `pyproject.toml` for the tools environment: cmake, ninja, capstone and
   pefile at the versions the toolkit's tools are checked with,
   `[tool.uv] package = false` and `no-build = true`, and a dev group with
   pytest and ruff. These are toolkit constants, not a game's.
4. `.gitignore`: the game's own output paths from the manifest (gen, out,
   build dirs, `dist/`), the toolchain and clones, and every game-data and
   capture extension cat's list has. Game-agnostic by construction: the
   paths come from the manifest the scaffold just wrote.
5. `README.md` (short: the name, bring your own dump, the four commands).
6. The toolkit clone (`toolkit.clone_toolkit()`), then
   `templates/new-game/` copied in: `CMakeLists.txt`, `src/main.c`,
   `src/recomp_manual.c`, patched (D4).
7. `config/setup-pins.json` and `uv.lock` through `pins.pins_refresh()`.

Steps 6 and 7 need the network, git and uv. Each failure is caught and
printed as the command that finishes it (`./<slug> setup` clones the
toolkit; `./<slug> pins refresh` writes the pins and the lock), and the
scaffold is still complete as files. `--offline` skips them without trying.

The last lines always say what is next: put the dump in `game_files/`,
`./<slug> setup`, `./<slug> all`.

## D2. The entry point: uvx, not curl | sh

The one-liner is

    uvx --from git+https://github.com/apexJCL/xboxrecomp-cli xbr new mygame

because uv is already the prerequisite everything else needs (the
bootstrap refuses to run without it), it is pinnable
(`…xboxrecomp-cli@<sha>`), it is the standard tool rather than a script of
ours, and the CLI is standard-library-only so the install is a wheel build
with no dependencies. A `curl | sh` would be a second thing to trust and
maintain for no step saved: it would have to install uv anyway.

The no-pipe alternative, for someone who wants to read first or work on
the CLI, is the clone: `git clone …xboxrecomp-cli && cd xboxrecomp-cli &&
uv run xbr new ../mygame`. A game made beside a clone uses that clone
(the bootstrap's search order), so the two paths meet.

The commit uv installed is the one the scaffold pins (D3), so the game's
bootstrap later clones exactly that commit into `external/xboxrecomp-cli`.

## D3. Resolving the two pins

`cli.commit`, in order: the HEAD of the checkout the CLI runs from
(`cli_dir.tree_state()`), else the `commit_id` in the installed
distribution's `direct_url.json` (PEP 610; what `uvx --from git+…` writes),
else `git ls-remote` of the CLI's `main`, else forty zeros and a line that
says to fill it in. `--cli-commit` overrides.

`toolkit.commit`, in order: `--toolkit-commit`; the HEAD of a toolkit
checkout the game would use (`XBOXRECOMP_DIR` or `../xboxrecomp`, since
`setup` leaves such a checkout alone and that is the toolkit that will
build the game); else `git ls-remote` of the branch; else forty zeros and
the line. A `main.c`'s `#include`s may need a newer toolkit than the pin
one day, as cat's did; the manifest's comment says how to move it.

A dirty checkout is not an error: the scaffold writes the commit and says
the tree had uncommitted changes.

## D4. The toolkit template, patched, not copied into the CLI

The CLI does not carry its own `main.c`: the toolkit's template is the one
upstream maintains, and a copy in the CLI would drift from it, as
Burnout 3's copy of `recomp_types.h` once did. `xbr new` copies
`templates/new-game/` from the toolkit clone and patches the places the
template itself marks for editing:

- CMakeLists.txt: `project(your_game_recomp C)` becomes
  `project(<build.exe> C)` (the target is the exe name the manifest
  builds); `YOUR_GAME_NAME` in the banner becomes the name.
- `src/main.c`: `YOUR_GAME_ENTRY_POINT 0x00000000` becomes the XBE's entry
  point (decoded from the header: the stored value XOR the retail key, or
  the debug key when the retail one lands outside the image);
  `YOUR_GAME_XBE_PATH` and `YOUR_GAME_DIR` become
  `game_files/default.xbe` and `game_files` (the manifest's `data.game_files`
  and `xbe.path`, with `/`, which fopen takes on every host); `Title ID:
  0x00000000` in the comment becomes the real one; `YOUR_GAME_NAME` the
  name. `extern int recomp_dispatch_init(void);` is added after the
  `xbe_entry_point` declaration when the file has no declaration, because
  Clang rejects the implicit one (F1 fixes the template; the patch is a
  no-op once it lands).

Each patch is a plain string replacement that must match exactly once;
one that matches nowhere is reported ("the template changed; edit X by
hand") and the copy still lands. The scaffold's tests run the patches
against a fixture copy of the template so a template change shows up as a
failing test.

Why the entry point from the header and not from `xbe_parser`: the tools
environment does not exist yet when `new` runs (it is `setup`'s), and the
field is twelve lines of `struct`. The XBE header reader (`xbe.py`:
`read_header(data)` → title, title ID, base, entry point, and whether the
retail or debug key decoded it) is shared with `package`, which keeps
reading the title ID through it.

## D5. Targets: windows first, macos documented as a follow-up

The scaffold's `build.targets` is `["windows"]`: the template builds for
it on every host (llvm-mingw cross-compiles on a Mac and on Linux), and
running the exe is what the bench host (Proton) and a Windows machine are
for. A game that wants the macos target needs a `main.c` with the POSIX
host code, and the only one in existence is cat's (1425 lines, half of
them BLiNX 2's). Making it a template is toolkit work (F2) and is not
blocked on this change; the README says so under "macOS as a target".

## D6. `doctor` ends with the next step

`doctor` already names every missing piece with its fix, in the order the
report is built. A fresh scaffold produces eight lines of "missing"
before anything works, so `doctor` gains one closing line, `next: …`,
the first of its problems' fixes in setup order (uv, then `setup`, then
the dump, then `analyze`/`recomp`). It is one line, computed from the list
the report already keeps; the exit status does not change.

## D7. The README

The order a developer needs it in:

1. What this is, in five lines, with the legal stance in one of them.
2. Prerequisites per host (uv, git, the Command Line Tools on a Mac;
   `makensis` only for the windows installer).
3. Quickstart: the five commands, and what each one does in a clause.
4. Port your first game: what happens after the first build (the crash,
   `recomp_manual.c`, seeds in `config/seed_functions.json`, `analyze`
   then `recomp`, the stale-gen key), with pointers into the toolkit's
   docs for the debugging loop.
5. Commands: the table from `--help`, with `docs/manifest.md` as the
   reference for every key.
6. The bench host (optional, advanced): one paragraph and a pointer to
   `bench --help` and `scripts/bench.env`.
7. Troubleshooting: the messages a first run can end in, each with the
   fix (no uv, the pin not pushed, quarantined llvm-mingw, missing
   makensis, the template changed, a dump that is not the game).
8. Working on the CLI, releases and pins, the public audit: unchanged in
   substance, moved under "Maintainers".

`docs/manifest.md` keeps its role and gains one line under the heading:
`xbr new` writes a starter one.

## D8. Windows as a development host

The pieces exist; the design makes them one path and tests what a Mac can.

- **Prerequisites:** Python 3.9+ from python.org (the `py` launcher), Git
  for Windows, uv (`winget install --id=astral-sh.uv -e`, or Astral's
  `irm https://astral.sh/uv/install.ps1 | iex`: the only pipe a developer
  meets, and it is uv's own). No Visual Studio: the CLI cross-compiles
  with llvm-mingw on every host, Windows included, and `setup` fetches it
  (the `ucrt-x86_64` or `ucrt-aarch64` zip) with NSIS into `third_party/`.
  MSVC remains the toolkit's own flow (the toolkit README's Quick Start,
  Burnout 3's `Setup.cmd`); the CLI's `build windows` always passes its
  toolchain file, so a developer who wants MSVC configures by hand.
- **One-liner:** the same `uvx --from git+… xbr new mygame` in PowerShell
  or cmd. The no-pipe alternative is the same clone. The README gives
  the Windows prerequisites and the `<slug>.cmd` form of every command.
- **The scaffold on Windows:** `<slug>.cmd` is written with CRLF (cmd.exe
  misreads a label or an `if` block with bare LF in some cases), and the
  scaffold's `.gitattributes` fixes `*.cmd` to CRLF and `*.py`, `*.sh`,
  `*.toml`, `*.in` and `<slug>` to LF, as cat's does, so a Windows
  checkout with `core.autocrlf=true` cannot break the shell wrapper or the
  files a bundle carries to Linux and macOS. The scaffold's README names
  the path rules: a short checkout path (`C:\g\mygame`),
  `git config --global core.longpaths true`, and a Defender exclusion for
  the checkout (the CLI never adds one).
- **`doctor` on Windows:** already prints `warning:` lines for a path over
  60 characters and for `LongPathsEnabled` off, and `makensis:` from
  `third_party/nsis-<version>/`. The `next:` line (D6) uses the Windows uv
  hint and `<slug>` without `./` (`host.cli_name()`).
- **Tests on the Mac:** the `.cmd` wrapper's text (the `py -3` route, the
  `python` fallback, `%~dp0`, `%*`, `exit /b`, CRLF), the attributes file,
  the scaffold with `host_os` mocked to `windows` (the `next:` line names
  `winget`, the XBE path in `main.c` uses `/`), and the path warnings
  already covered by `test_windows_path_warnings`.
- **What only a Windows machine can verify** (the report's checklist):
  `winget` uv, `uvx … xbr new`, `mygame doctor`, `mygame setup` (the zip
  downloads and their sha256, NSIS), `mygame all` through to
  `build-win\<exe>.exe`, the exe starting natively with D3D11, `mygame
  package windows` making the installer, and the two path warnings on a
  deep checkout.

## Follow-ups (not in this change)

- F1 (toolkit, upstreamable): `templates/new-game/src/main.c` declares
  `recomp_dispatch_init` (cat's `main.c` has the line and the reason).
- F2 (toolkit): a portable `main.c` in `templates/new-game/`, from cat's
  `host_main` split, so a scaffold can list the macos target.
- F3 (CLI, after `feat/cli-housekeeping` lands): `all` runs `setup` when
  something is missing, as `package` does, so the quickstart loses a
  line. Not done here to keep the two branches apart in `main.py`.
