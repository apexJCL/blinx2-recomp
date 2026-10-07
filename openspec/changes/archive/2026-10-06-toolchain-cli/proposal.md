# toolchain-cli: the rest of the toolchain under `blinx2`, with uv and ruff

Status: spec drafted by Fable (2026-10-06); the user's answers to the open
questions are in design.md "Decided" (2026-10-06).

## Why

Packaging moved to one Python CLI (`blinx2.py`, standard library, with
`blinx2` and `blinx2.cmd`) so a user builds and installs on Windows, Linux
or macOS without hoops. The developer side did not move. Four shell scripts
remain in `scripts/`:

| Script | Lines | What it is | Runs on |
|---|---|---|---|
| `bench.sh` | 1160 | the Proton bench: setup, sync, build, run, golden, tests, pacing, logs, symbolize, integrate, the run lock, `--kill-game`, the gen digest check | the controlling host, over ssh to the Linux/Proton host |
| `pipeline.sh` | 48 | a forwarder to `blinx2 <stage>` | any |
| `export-public.sh` | 140 | the public-tree export (private, excluded from the export) | the Mac |
| `xemu_capture.sh` | 34 | xemu reference capture under the run lock | the Linux/Proton host itself |

`bench.sh` is the one that matters: every merge gate runs through
`bench.sh golden` and `bench.sh integrate`, and it is the only path to the
D3D11 goldens. It needs bash, ssh, rsync, `shasum` and awk on the
controlling host, so a Windows developer cannot drive the bench at all, and
its host-side logic is bash inside heredocs, which the one test that covers
it (`scripts/test_bench_hold.py`) has to extract with a regex. Its
controller-side logic (`check_run_end`, `check_present_mismatch`, the
provenance lines, the gen digest, the golden plan loop) is pure file and
string processing that the Python side already has the pieces for
(`golden.py`, `package_lib.py`, `running_game.py`, `pacing_stats.py`), and
it duplicates `blinx2.py` (toolkit lookup, tree state, gen digest).

Separately, the user decided on 2026-10-06 that the project adopts modern
Python tooling: **uv** for the environment and dependencies, **ruff** for
lint and format. Today `blinx2 setup` hand-rolls a resolver (`pins refresh`:
the `PIP_SETUP`/`PIP_DEV` tables, markers, transitive closure) into two
hashed `requirements-*.txt`, and nothing lints the 29 Python files. The
system Python on the Mac has no pytest, so the `scripts/test_*.py` suite
runs one file at a time by hand.

### Feasibility (Fable's assessment)

**Feasible now, for the controller.** The split that makes it safe:

- Everything that runs **on the controlling host** (argument parsing,
  configuration, the ssh transport, the sync, pulling logs and frames, the
  run and present checks, the golden plan loop, the pacing series, the
  integrate guards) ports to Python. It is testable with the existing
  `scripts/test_*.py` style, and it is what a Windows host lacks today.
- Everything that runs **on the Linux bench host** stays shell, as files
  shipped with the project instead of heredocs: the run lock (`flock` on fd
  9, the lslocks holder report, `-w 3600 -E 75`), `distrobox enter`,
  `systemd-run` for the pacing hold, `umu-run`, the survivor sweep over
  `/proc`, PSI, `wineserver -k`, `llvm-symbolizer`. Python on the host would
  gain nothing there and would put the gate every merge depends on at risk.
  The host scripts can be shipped byte-for-byte equal to today's heredocs,
  so phase 1 changes no remote behaviour at all.

What is genuinely shell- or host-bound, and what replaces it:

| Piece | Where | In the port |
|---|---|---|
| `ssh` | controller | the `ssh` binary through `subprocess` (OpenSSH ships with Windows 10 1809+, macOS and Linux); no paramiko |
| `rsync` | controller | kept when present (Mac, Linux); a standard-library manifest transfer over `ssh` + `tar` when absent (Windows), with the same `--checksum --no-times --delete` semantics (phase 3) |
| `flock`, `lslocks` | host | unchanged, in the host scripts; the controller never takes the lock |
| `systemd-run` (pacing hold) | host | unchanged host script, already covered by `test_bench_hold.py` |
| `distrobox enter`, `umu-run`, `wineserver` | host | unchanged |
| `shasum`/`sha256sum`, awk, sed on the controller | controller | `hashlib`, `re` |
| `scripts/bench.env` | controller | still read; `KEY=value` lines (its documented form) |

**Run-lock semantics are kept exactly**: the lock is taken only on the host,
inside the host script, with `flock -w 3600 -E 75` on fd 9, released when
that script ends; the game never inherits the fd; `BENCH_LOCK_HELD=1` runs
inside a pacing hold do not wait again; `blinx2 bench` takes the lock
itself and so, like `bench.sh`, is never wrapped in an outer `flock`.

**Risk to golden and integrate** is contained by the phasing: `blinx2 bench`
lands beside an untouched `bench.sh`; a parity test with a fake `ssh` on
`PATH` compares the remote scripts and arguments both send; one real golden
and one real integrate through the new path must match `bench.sh`'s verdicts
and files before `bench.sh` becomes a shim; the shim stays until every
reference (CLAUDE.md, TASKS, memory notes) is updated.

**`pipeline.sh` is redundant.** It forwards every stage to `blinx2`; the two
things it adds (`--system-tools` when `.venv` is absent, `build` → `build
macos` on Darwin) are `blinx2`'s own defaults once uv manages the venv. It
becomes a one-line shim and is deleted in the last phase.

**`export-public.sh` stays shell.** It is private, excluded from the export,
runs on one host, has a test (`test_export_public.py`), and its value is in
the `REWRITE` perl rules: translating them to Python `re` is a leak risk
with no gain. `xemu_capture.sh` also stays: it runs on the bench host
itself, where everything is shell anyway.

**Gain:** the bench on a Windows controlling host (deferred, see
design.md "Decided"); a tested controller; one
toolkit lookup, provenance and gen-digest implementation instead of two;
`pytest` and `ruff` for everyone through `uv run`. **Cost:** about a week of
agent sessions and six to eight the Linux/Proton host golden runs, and one more trusted
vendor (Astral) in the supply chain, pinned.

## What Changes

- **Tooling (binding decision, 2026-10-06).** `pyproject.toml` at the root
  declares the project, its Python dependencies (cmake, ninja, capstone,
  pefile) and a `dev` group (pytest, ruff); `uv.lock` pins every artifact
  with its sha256. They replace `config/requirements-setup.txt`,
  `config/requirements-dev.txt` and the pip half of `blinx2 pins refresh`.
  `ruff check` and `ruff format --check` join the per-merge gates. One
  format-only commit precedes the port.
- **`blinx2 setup` uses uv from `PATH`** (user decision, 2026-10-06).
  It runs `uv sync --locked`; it never downloads uv. Without uv, `setup`
  and `doctor` say so with the install command for the host. The venv
  stays at `.venv`, so every path `blinx2` and `doctor` already use is
  unchanged. `blinx2.py` itself stays standard-library Python, so
  `./blinx2` and `blinx2.cmd` start with any Python ≥ 3.9 and can say what
  is missing before uv exists.
- **`blinx2 bench <command>`** replaces `scripts/bench.sh`: the same
  commands (`setup sync build run golden tests pacing logs symbolize shell
  all integrate`), options (`--record --force --kill-game --golden --dirty
  --game-files[=reflink] --scen --runs --gate`) and `BENCH_*` configuration,
  plus `bench doctor` (ssh reachability, rsync, the host's umu-run and
  distrobox). Its host-side scripts live in `scripts/benchlib/host/*.sh`.
  The controller is `scripts/benchlib/`, a package `blinx2.py` loads only
  for `bench`.
- **Shims, then removal.** `bench.sh` and `pipeline.sh` become one-line
  forwarders once parity is proven, and are deleted in the last phase after
  CLAUDE.md, TASKS.md, the memory notes and the docs name the new commands.
- **Help layout.** `blinx2 --help` keeps the player commands first and
  unchanged; `bench` appears under "Developer commands" as one line.
- **Windows as the controlling host** (phase 3) is **deferred** by the
  user (2026-10-06) to a follow-up: OpenSSH's `ssh`, the standard-library
  transfer when `rsync` is absent, path handling for the pulled logs.
  This change ends without it.
- **Docs:** `docs/packaging.md` (setup with uv, maintainers), the README
  developer section, `docs/env.md` ("Not in the table" row), and a list of
  CLAUDE.md lines for the orchestrator (design.md).

Non-goals: porting `export-public.sh` or `xemu_capture.sh`; ssh deploy for
end users (manual copy stays, per the deployment decision); any change to
what runs on the bench host; ruff for the toolkit's `tools/` (a later,
separate change through the fork, checked against the upstream README);
a native Windows bench host.

## Capabilities

### New Capabilities
- `dev-tooling`: uv-managed environment and lockfile, ruff lint and format
  gates, pytest through `uv run`, and what stays standard-library.

### Modified Capabilities
- `packaging`: "One CLI on every build host" (the `pipeline.sh` clause,
  `bench` as a developer command), "Setup fetches a pinned, verified
  toolchain" (uv and `uv.lock` in place of venv + pip hashed wheels), "Help
  shows player commands first" (`bench` under Developer commands).
- `bench-methodology`: "Running-game check before a bench run" names
  `blinx2 bench`; new requirements for the CLI bench driver, the kept lock
  semantics, the host scripts as files, parity with `bench.sh` and
  `bench doctor` (the rsync-free transfer is deferred with the Windows
  host).

## Impact

- **Backends, hosts, goldens.** No render path, runtime or kernel code
  changes; the game is not touched. The controlling hosts stay macOS
  and Linux (Windows is deferred); the bench host stays the Linux/Proton host under
  Proton. Every golden (`@attract`, `@stage1`, `@story`) runs through the new path during the port, on
  D3D11 via the Linux/Proton host; the Metal goldens are unaffected but run once as a
  gate for the uv venv change (`golden.py` uses the venv's tools Python
  for nothing, so this is a regression check only).
- **Toolkit.** Not touched. Nothing here is meant for upstream. The
  toolkit's `tools/` keeps its own setup (`tools/macos/setup.sh`); ruff
  for it is a follow-up through the fork.
- **cat.** `pyproject.toml`, `uv.lock`, `.python-version`,
  `.git-blame-ignore-revs`; `blinx2.py` (setup, doctor, pins, help, the
  `bench` entry); new `scripts/benchlib/` with `host/*.sh`; new tests
  `scripts/test_bench_cli.py`, `scripts/test_bench_checks.py`; `scripts/test_blinx2_cli.py` (the
  requirements test goes, a lockfile test comes); `test_bench_hold.py`
  reads the host script file instead of a heredoc; `scripts/bench.sh` and
  `scripts/pipeline.sh` shims, then deleted; `config/requirements-*.txt`
  deleted; `.gitignore`
  (`.ruff_cache/`); docs as above; `openspec/config.yaml` context lines
  that name `scripts/pipeline.sh` and `scripts/bench.sh`.
- **Private data.** Nothing new is published. `scripts/bench.env` stays
  gitignored and unsynced; the host name rewrite in `export-public.sh`
  covers the new files' comments and docs the same way (the export test
  gets a case for `scripts/benchlib/`). No game data, frames or logs move
  anywhere they do not move today.
- **Other open changes.** `fps-pacing`'s bench-methodology delta names
  `scripts/bench.sh pacing`; when it archives first, the toolchain-cli
  delta's wording wins (`blinx2 bench pacing`). `bench-methodology`'s open
  tasks 1.5 and 3.x refer to `bench.sh` and read the same under the new
  name.
