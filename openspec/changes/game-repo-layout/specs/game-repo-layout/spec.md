## ADDED Requirements

### Requirement: Standard game repo layout
Every game repo SHALL contain the required entries of design.md D1: `game.toml`; the `<slug>`, `<slug>.cmd` and `<slug>.py` bootstrap files; `pyproject.toml` with ruff and pytest configuration and `uv.lock`; `.gitignore` and `.gitattributes`; `README.md`, `CHANGELOG.md` and `LICENSE`; `CMakeLists.txt`; the main C source (`[layout] main`, default `src/main.c`) and the manual C source; `config/seed_functions.json` and `config/setup-pins.json`; and `scripts/` with at least `scripts/test_gitignore.py`. Paths that `game.toml` names SHALL be resolved through the manifest, with the standard name as the default.

#### Scenario: A required file is missing
- **WHEN** `<slug> doctor` runs in a game repo that has no `CHANGELOG.md`
- **THEN** the layout block reports a problem naming `CHANGELOG.md`, and `<slug> public audit` fails

#### Scenario: A manifest path differs from the default
- **WHEN** b3's `game.toml` sets `[pipeline] gen = "src/game/recomp/gen"`, `exclude_manual` to `src/game/recomp/recomp_manual.c` and `[layout] main = "src/game/main.c"`
- **THEN** doctor checks the manual and main sources at those paths and reports no missing `src/recomp_manual.c` or `src/main.c`

### Requirement: Doctor's layout block is separate
Doctor SHALL print the layout checks as their own block, in text and under a `layout` key in `--json`. Layout problems SHALL NOT be added to `PROBLEMS` or to the `--json` `problems` and `blockers`, and SHALL NOT change `next:` or doctor's exit status. `public audit` and `public export` SHALL fail on them. Top-level names in the private set SHALL count as known names.

#### Scenario: Layout problems leave doctor's verdict alone
- **WHEN** a game that is otherwise ready lacks `CHANGELOG.md` and `<slug> doctor --json` runs
- **THEN** the `layout` key lists the problem, `problems` and `blockers` do not, and the exit status and `next:` are those of the same repo with the file present

#### Scenario: The private set is known
- **WHEN** a game tracks `TASKS.md` at the top level
- **THEN** doctor prints no unknown-entry note for it

#### Scenario: A hooks path is set
- **WHEN** `core.hooksPath` is set in a game repo with a remote whose URL is `[public] url`
- **THEN** the layout block reports a problem, since the push guard would be bypassed

### Requirement: Conditional entries follow their tables
A game with `[package]` SHALL have, per target, the packaging files that `package` looks up for it in the game's `packaging/`, or the CLI templates as the fallback. A game with `[wizard]` SHALL have `.github/workflows/release-wizard.yml` equal to the CLI's template for its slug, and `[wizard] repo` (the https form) SHALL name the same repo as `[public] url` (the ssh form), compared as `<owner>/<repo>` ignoring case and `.git`.

#### Scenario: The release workflow drifted
- **WHEN** a game's `release-wizard.yml` differs from the template
- **THEN** `<slug> workflow --check` exits non-zero and doctor's layout block reports the drift as a problem

#### Scenario: The wizard names another repo
- **WHEN** `[wizard] repo` names another `<owner>/<repo>` than `[public] url`
- **THEN** doctor reports a problem naming both values

### Requirement: Declared extras
Top-level tracked entries outside the D1 table SHALL be listed in `[layout] extra`. An undeclared entry SHALL be reported as a note, not a problem.

#### Scenario: Upstream-inherited files
- **WHEN** b3 tracks `regen.sh`, `Setup.cmd` and `tools/` and lists them in `[layout] extra`
- **THEN** doctor reports no note for them

#### Scenario: An undeclared entry
- **WHEN** a game tracks a top-level `notes.txt` that `[layout] extra` does not list
- **THEN** doctor prints a note naming `notes.txt`

### Requirement: Gitignore baseline
Every game's `.gitignore` SHALL ignore the baseline of design.md D3: the data folder and its `.partial` and `.old` siblings, gen, build trees, `dist/`, `/wt/`, `_local/`, `runs/`, backup files, and the game-data extensions. The game's own lines SHALL follow the `# --- this game ---` marker.

#### Scenario: A backup file is ignored
- **WHEN** a user saves `game.toml.bak-20261016` in a conformed repo
- **THEN** `git status` does not list it

#### Scenario: The baseline test
- **WHEN** `uv run pytest scripts` runs
- **THEN** `scripts/test_gitignore.py` fails if any baseline sample path is not ignored, or if `game.toml` or `scripts/` is ignored

### Requirement: No worktree or embedded repo inside a game repo
No git worktree, nested repository or gitlink SHALL exist under a game repo's root. Worktrees SHALL live in the workspace's `wt/<name>/`.

#### Scenario: A nested worktree
- **WHEN** a worktree exists at `<repo>/wt/apulife/b3`
- **THEN** doctor reports a problem naming it, even though `/wt/` is ignored

#### Scenario: A gitlink in the tree
- **WHEN** a commit tracks an entry with mode 160000
- **THEN** `<slug> public audit` fails and names the path

### Requirement: No game data in a game repo
A game repo SHALL track no game data, ISO, executable, frame dump, golden reference, audio capture or save. Doctor SHALL report any tracked file with a data extension, other than `docs/images/*.png` and the entries in `[public] allow` or `[public] upstream_files`, as a problem.

#### Scenario: A tracked capture
- **WHEN** a commit tracks `runs/frame_0100.ppm`
- **THEN** doctor reports a problem, and `public audit` and `public export` refuse

### Requirement: Public games carry checks and openspec
A game with `[public]` SHALL have `.github/workflows/checks.yml` equal to the CLI's template, running its pytest and ruff gates, and SHALL have `openspec/` with `config.yaml`, `specs/` and `changes/` (the user, 2026-10-17). `openspec/` SHALL be exported through the same rewrite and audit as every other file.

#### Scenario: A public game without checks
- **WHEN** a game has `[public]` and no `checks.yml`
- **THEN** doctor reports a problem and `public audit` fails

#### Scenario: A local-only game without openspec
- **WHEN** a game has no `[public]` and no `openspec/`
- **THEN** doctor prints a note, not a problem

### Requirement: The scaffold writes the layout
`xbr new` SHALL write every required D1 entry except `LICENSE` (written only with `--license`) and the entries `finish` writes (`CMakeLists.txt`, the C sources, `config/setup-pins.json`, `uv.lock`). It SHALL write the D3 `.gitignore`, a commented `[public]` stub, `checks.yml`, and a `[wizard]` stub that names `[public]`'s URL. It SHALL write `openspec/` unless `--no-openspec` is given.

#### Scenario: A new game passes doctor
- **WHEN** `xbr new` creates a game online (not `--offline`) with `--license mit` and `doctor` runs before any pipeline step
- **THEN** the layout block reports no problem
