## ADDED Requirements

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
