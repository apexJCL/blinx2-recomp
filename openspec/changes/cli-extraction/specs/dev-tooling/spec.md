## MODIFIED Requirements

### Requirement: Runtime code stays standard-library
The `xboxrecomp-cli` package, the game's `blinx2.py` bootstrap and the scripts the game, the launchers and the bench host run SHALL import only the standard library; the CLI's `pyproject.toml` SHALL declare no runtime dependency. The CLI SHALL require Python 3.12 or newer, provided through uv (`uv run --project <cli>`); the bootstrap SHALL run on Python 3.9 so a host with only the system Python prints help and the uv hint. uv and ruff are development tools; cmake, ninja, capstone and pefile are the game's tools environment, pinned in the game's `uv.lock` because capstone's version is a gen/ input. A new third-party runtime dependency SHALL be justified in a spec before it is added.

#### Scenario: Import audit
- **WHEN** every module under `src/xboxrecomp_cli/` and the wrapper template are imported with only the standard library available, on Python 3.12
- **THEN** every import succeeds

#### Scenario: Bootstrap on the system Python
- **WHEN** `python3.9 blinx2.py --help` runs
- **THEN** it prints the command list without importing anything outside the standard library and without uv

### Requirement: Tests run through uv
`uv run pytest tests` in `xboxrecomp-cli` SHALL run the CLI's tests (the former `scripts/test_blinx2_cli.py`, `test_bench_cli.py` with its parity record, `test_bench_checks.py`, `test_bench_hold.py`, `test_package_lib.py`, `test_golden.py`, `test_game_icon.py`, `test_progress.py`, `test_pacing_stats.py`, `test_benchlog_retention.py`, `test_audio_check.py`, and the new `test_manifest.py` and `test_wrapper.py`; from phase B also `test_running_game.py`, `test_launchers.py`, `test_steamos_install.py`), and `uv run pytest scripts` in the game SHALL run what stays there (`test_export_public.py`, `test_env_doc.py`, `test_unimpl_budget.py`, and until phase B the three that move). Each SHALL be a per-merge gate when any Python in its repository changes. The CLI's tests SHALL use synthetic XBEs, synthetic frames and `fakehost`, never game data or a real host name.

#### Scenario: Both suites green
- **WHEN** a branch pair is proposed for merge
- **THEN** `uv run pytest tests` in the CLI worktree and `uv run pytest scripts` in the game worktree both pass

#### Scenario: Parity record moves intact
- **WHEN** `tests/test_bench_cli.py` replays `tests/testdata/bench_parity.json` in the CLI repository after phase A
- **THEN** every case passes, and the record's diff against cat 70bf5c8's `scripts/testdata/bench_parity.json` is the `provenance` case's added `cli:` line and nothing else

#### Scenario: System Python without pytest
- **WHEN** the host's Python has no pytest and the developer runs `uv run pytest tests` in the CLI or `uv run pytest scripts` in the game
- **THEN** the suite runs from the locked environment and reports every test file

### Requirement: ruff lints and formats every Python file in this repository
`pyproject.toml` in the game SHALL configure ruff for its remaining Python (`blinx2.py`, `scripts/`, `packaging/`), and `pyproject.toml` in `xboxrecomp-cli` SHALL configure ruff for `src/` and `tests/` with the same rules (`E F W I UP B`, line length 100, `E501` and `UP031` ignored) and `target-version = "py312"`, excluding generated code, `external/`, `third_party/`, virtual environments, `analysis/` and build directories. `uv run ruff check .` and `uv run ruff format --check .` SHALL be per-merge gates in each repository. The toolkit's `tools/` SHALL NOT be touched by either configuration.

#### Scenario: Gate
- **WHEN** a branch pair is proposed for merge
- **THEN** `uv run ruff check .` and `uv run ruff format --check .` exit 0 in both worktrees

#### Scenario: Format commit stands alone
- **WHEN** the format commit is checked out and `uv run pytest scripts` runs before and after it
- **THEN** the same tests pass, and the commit's diff contains no change outside formatting and the agreed renames
