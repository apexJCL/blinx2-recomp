## ADDED Requirements

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
