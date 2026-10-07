# Design: toolchain-cli

## Context

Read on cat `main` at 89bbe77 (2026-10-06):

- `blinx2.py` (1956 lines) registers commands with `@command(name, help,
  configure)` into `COMMANDS`, in `--help` order; the docstring is the help
  text and splits player commands from "Developer commands". `setup` makes
  `.venv` with `python -m venv` and `pip install --require-hashes
  --only-binary :all: -r config/requirements-setup.txt [-r
  config/requirements-dev.txt]`. `pins refresh` resolves `PIP_SETUP` and
  `PIP_DEV` against PyPI by hand (markers, transitive closure) and writes
  both files plus `config/setup-pins.json` (`llvm_mingw`, `nsis`,
  `toolkit`, each with a sha256 `setup` verifies). `doctor` looks for
  `.venv/bin/{cmake,ninja}` and the tools Python at `.venv/bin/python`.
  `tool_python()` runs the toolkit's `tools.*` modules with that
  interpreter. Scripts under `scripts/` are imported with
  `sys.path.insert(0, ROOT/scripts)` (`progress_lib()`).
- `scripts/bench.sh` (1160 lines): the controller is bash; every host
  action is a heredoc piped to `ssh -o BatchMode=yes $BENCH_HOST bash -s`
  (`remote`), or to `distrobox enter $BENCH_BOX -- bash -s` (`in_box`), or
  to the same after `flock` on fd 9 (`in_box_locked [-x]`). `remote_vars`
  is the unquoted prologue (`BENCH_DIR`, `REMOTE_GAME`, `LLVM_MINGW_ROOT`,
  `BENCH_PREFIX`, `BENCH_BOX`); host paths keep a literal `~` for the
  host's shell. `run_game` sends `STAMP PROTONPATH GAME_ARGS GAME_ENV
  TIMEOUT FRAMES KILL_GAME LOCK_HELD` with `printf %q`, then the run script
  (lock, running-game check, env merge for `RECOMP_TRACE`/`RECOMP_DEBUG`,
  `RECOMP_SAVE_DIR=@run`, `BENCH_FRAMES`, run-info, the `RECOMP_BENCH_RUN`
  tag, survivors, PSI/load, exit-code), then `cmd_logs` pulls
  `bench-logs/` with rsync (excluding `/*/frames/`). `check_run_end` and
  `check_present_mismatch` read the pulled files. `cmd_golden` loops over
  `golden.py plan` (tab-separated `scen secs minf env`), runs each with
  `RECOMP_DEBUG=fb_dump_at=<dumpat> BENCH_TIMEOUT BENCH_FRAMES=1`, pulls
  the frames `golden.py frames` and `golden.py pulls` name, then runs
  `golden.py check|record SCEN=DIR...`; exit 3 is INCONCLUSIVE.
  `cmd_integrate` refuses a non-`main` tree or a dirty one, syncs, compares
  the gen digest (`sha256` over `sha256` of each `gen/*`, sorted by name),
  builds, prints the exe sha and provenance, and with `--golden` runs
  golden with `RECOMP_HOST_PAD=0 RECOMP_KEYBOARD=0 RECOMP_INPUT_STRICT=1`
  added. `cmd_pacing` holds the lock across a series through a
  `systemd-run --user` unit (`hold_run_lock`) and runs with
  `BENCH_LOCK_HELD=1`.
- Tests: `scripts/test_*.py` are "plain asserts; runs alone or under
  pytest", with an `if __name__ == "__main__"` runner. `test_bench_hold.py`
  extracts the `hold_run_lock` heredoc with a regex and runs it under
  `bash -s` with stub `systemctl`/`systemd-run` on `PATH`.
  `test_export_public.py` builds a throwaway repository and runs the
  script. `test_blinx2_cli.py` mocks `urllib.request.urlopen` and checks
  `test_requirements_hashed`.
- Tooling present on the Mac: uv 0.12.21, ruff 0.16.9, Python 3.14.8, no
  pytest for the system Python. `ruff format --check` would rewrite all 29
  Python files at the default width (88) and still all 29 at 100; `ruff
  check --select E,F,W --line-length 100` reports 112 findings (75 E501,
  23 E741, 8 E702, 3 E731, 2 F401, 1 F541). The default rule set reports 465.
- The toolkit's `tests/proton_run.sh` takes `PROTON_RUN_LOCK` itself when
  set; `bench.sh tests` unsets it because the bench already holds the lock.
- `docs/env.md` lists `RECOMP_BENCH_RUN, RECOMP_RUN_LOCK` under "Not in
  the table" as script-side variables of `scripts/bench.sh` and
  `scripts/vpad.py`. `BENCH_*` are not game variables and are not in the
  recomp_env table; they stay out of it (the game never reads them).

## Goals / Non-Goals

**Goals**
- `blinx2 bench <command>` does what `bench.sh <command>` does, with the
  same remote commands, the same files on the host and in `bench-logs/`,
  and the same verdicts and exit codes (0, 1, 3, 75), from a macOS, Linux
  controlling host (Windows: deferred, Q4).
- The run lock is taken exactly as today, on the host, by the host script.
- The environment and the tests are managed by uv; lint and format by ruff;
  both are per-merge gates.
- The end user's `./blinx2` and `blinx2.cmd` stay one command with no new
  prerequisite on `PATH`.
- `bench.sh` and `pipeline.sh` go away without a day on which the golden
  or integrate gate is unavailable.

**Non-Goals**
- Changing any host-side behaviour (lock, umu-run, survivors, PSI,
  symbolize). The host scripts move into files; they do not change in
  phase 1, and later changes to them are ordinary bench changes.
- Porting `export-public.sh` or `xemu_capture.sh`.
- ruff or uv for the toolkit's `tools/`.
- A Windows bench host, or ssh-based deployment for players.

## Decisions

### D1. The split: Python controller, shell host scripts as files

`scripts/benchlib/` is a package:

```
scripts/benchlib/
  __init__.py      the `bench` command table, its argument parsing and command functions
  config.py        BENCH_* defaults, scripts/bench.env, config/toolchain.env
  remote.py        ssh transport: remote(), in_box(), in_box_locked(), ship()
  sync.py          rsync (the manifest transfer of D6 is deferred)
  checks.py        check_run_end, check_present_mismatch, provenance, tree_state, gen_digest
  golden.py        the golden loop (calls scripts/golden.py as a subprocess, as bench.sh does)
  pacing.py        hold_run_lock / release, the A/B series
  host/
    prologue.sh.in the remote_vars prologue, filled by remote.py
    setup_box.sh   setup_pkgs.sh  setup_mingw.sh
    game_files.sh  build.sh  gen_digest.sh  integrate_show.sh
    run_game.sh    tests.sh  hold_lock.sh  symbolize.sh
```

`remote.py` builds each remote script as `prologue + assignments + file`
and pipes it to `ssh -o BatchMode=yes HOST bash -s` (or the distrobox and
locked variants) exactly as `bench.sh` does, with the script on stdin so
quoting stays local. Assignments use a `shell_quote()` that reproduces
`printf %q` for the values the scripts receive (plain words, `=`, `/`,
`:`, spaces; anything else is quoted with single quotes and `'\''`); the
parity test (D8) proves the equivalence on the real argument sets.

Why not Python on the host: the Linux/Proton host has `python3`, and `running_game.py`
already runs there, but the run script's value is in `flock` on an
inherited fd, `exec 9>>`, `9>&-`, `systemd-run`, `/proc/*/environ`, and
`wineserver -k`. A Python rewrite would reproduce that with `fcntl`,
`os.set_inheritable` and `subprocess` for no gain and with every golden at
stake. The host scripts become files so they can be read, shell-checked
and tested directly (`test_bench_hold.py` stops extracting a heredoc).

### D2. Lock semantics, verbatim

- The lock is `~/.recomp-run.lock` on the host, taken by the host script
  on fd 9 with `flock -n 9`, else the lslocks holder report and `flock -w
  3600 -E 75 9` (shared for builds, exclusive for runs and tests). The
  script writes its line into the file after taking it. Children get
  `9>&-`.
- Exit 75 means "waited an hour"; the controller maps it to the same
  messages (`build: the run lock was held for an hour; nothing built`,
  `tests: FAIL the run lock was held for an hour; nothing run`,
  `pacing: could not get the run lock`).
- `BENCH_LOCK_HELD=1` is passed to runs inside a pacing hold; the hold is
  the `systemd-run --user --unit=recomp-pacing-hold` unit with
  `BENCH_HOLD_MAX` (14400 s), released by removing `~/.recomp-run.hold`.
- The controller never takes, waits on or inspects the lock. `blinx2
  bench` is therefore never wrapped in an outer `flock` (CLAUDE.md's rule
  for `bench.sh` applies unchanged); `bench --help` says so.
- `tests.sh` keeps `unset PROTON_RUN_LOCK`.

### D3. uv for the environment and the lockfile

`pyproject.toml` at the root:

```toml
[project]
name = "blinx2"
version = "0"
description = "BLiNX 2 static recompilation: build, package and bench tooling"
requires-python = ">=3.9"
dependencies = [
  "cmake", "ninja",
  "capstone==5.0.9",      # the lifter decodes with it: a different capstone could change gen/
  "pefile==2024.8.26",
]

[dependency-groups]
dev = ["pytest", "ruff"]

[tool.uv]
package = false            # a plain environment, nothing is installed as a project
```

- `uv.lock` pins every artifact with its sha256 and is committed. `blinx2
  setup` runs `uv sync --locked` (fails if the lock is stale; verifies the
  hashes) with `--no-dev` unless `--dev`. The venv is `.venv/`, uv's
  default, so `venv_bin()`, `tool_python()`, `doctor` and the
  `--system-tools` logic are unchanged.
- `pins refresh` keeps the GitHub half (llvm-mingw, NSIS, toolkit) and
  replaces the PyPI half with `uv lock --upgrade`. `PIP_SETUP`,
  `PIP_DEV`, `requires()`, `pip_block()` and both `requirements-*.txt`
  go. `test_requirements_hashed` becomes `test_lockfile_pins`: every
  package in `uv.lock` has a `sha256` hash, and `capstone` is `5.0.9`.
- `.python-version` is `>=3.12`: the floor for the dev group (numpy via the
  toolkit's tests) and what uv picks when it has to provide an interpreter.
  `requires-python` stays `>=3.9` for the standard-library runtime of
  `blinx2.py` and the scripts.
- The toolkit's tools run with `tool_python()` as before. Nothing in the
  toolkit changes; its `tools/macos/setup.sh` venv remains a fallback for
  developers who have it.

### D4. uv comes from PATH (decided by the user, 2026-10-06)

The draft weighed three options (uv on `PATH`, a pinned uv fetched into
`third_party/uv/`, a pip fallback) and recommended fetching. **The user
decided: uv must be on `PATH`.** `blinx2 setup` never downloads uv, and
`config/setup-pins.json` carries no uv pin.

- `find_uv()` is `shutil.which("uv")`, then `uv --version`. A uv older than
  `UV_MIN` in `blinx2.py` is refused with the same hint as a missing one.
  `UV_MIN` is the oldest uv this project has checked against the committed
  `uv.lock` format and `[dependency-groups]`; raising it is a one-line
  change with a comment saying why.
- A missing (or too old) uv is one error from `setup`, and a `uv:` line
  plus a blocker from `doctor`, each with the install command for the host
  (`UV_HINT`): `brew install uv` on macOS; on Linux the Astral installer
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`, which installs into
  `~/.local/bin` and so also works on an immutable host such as the Linux/Proton host or
  SteamOS) or the distribution's package; on Windows
  `winget install --id=astral-sh.uv -e`. The hint names
  https://docs.astral.sh/uv/getting-started/installation/ for the rest.
- `setup_needs()` reports `no uv` only when it would need uv, that is when
  `.venv` lacks cmake, ninja or the tools Python; a host with a working
  `.venv` (or `--system-tools` plus a toolkit venv) packages without uv on
  `PATH`, as before.
- `blinx2.py`, `blinx2` and `blinx2.cmd` stay standard-library Python, so
  they start, print `--help` and run `doctor` (which says uv is missing)
  without uv.

Supply-chain delta against today: PyPI wheels are still verified by
sha256 (from `uv.lock` instead of `requirements-*.txt`); the resolver that
produced the pins is Astral's instead of our own, and its output is a
reviewed, committed lockfile; `uv sync --locked` never resolves at install
time and never reaches a package the lock does not name. The uv binary
itself is the user's, installed the way they install their other tools;
the project no longer vouches for it with a pin. If uv has to fetch a
Python (`.python-version`), it verifies the python-build-standalone archive
against hashes compiled into uv.

Windows without Python stays "install Python 3 from python.org", as today.

### D5. ruff: configuration, gate and the format commit

```toml
[tool.ruff]
line-length = 100
target-version = "py39"
extend-exclude = ["src/recomp/gen", "external", "third_party", ".venv*", "analysis", "build*", "dist"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B"]
ignore = ["E501"]          # format wraps code; strings and comments wider than 100 are left to review
```

- Covered: `blinx2.py`, `scripts/*.py`, `packaging/**/*.py`
  (`install_lib.py` and friends), tests. The toolkit's `tools/` is not in
  this tree and follows later through the fork as its own change.
- Width 100: the code is written to about 100 today; 88 reformats more for
  no reason. The remaining E501 findings are long strings and comments and
  are left alone.
- E741 (23 single-letter `l` names) is fixed by renaming in the format
  commit; E702 (`;` statements) and E731 (lambda assignment) likewise.
  Nothing else changes in that commit, which is `style: ruff format and
  lint pass, no behaviour change` and whose sha goes into
  `.git-blame-ignore-revs` (`git config blame.ignoreRevsFile`).
- Gate, every merge: `uv run ruff check . && uv run ruff format --check .`.
  Not a git hook: the gates list is where this project enforces things.
- `UP` is pinned by `target-version = "py39"`, so it never introduces
  syntax the runtime floor lacks.

### D6. Sync without rsync (phase 3: deferred by the user, Q4)

Kept as the design for the follow-up; this change does not build it.

`sync.py` uses `rsync` when `shutil.which("rsync")` finds one, with
today's exact options (`-az --no-times --checksum --delete --info=stats1`
and the exclude list), so the Mac and Linux paths do not change. When it
is absent, or `BENCH_RSYNC=0` is set (for the parity test), it runs the
manifest transfer:

1. The controller walks the tree with the same excludes, hashing each file
   (`hashlib.sha256`, streamed) and recording mode bits.
2. It asks the host for its manifest with one remote script
   (`host/manifest.sh`: `find -type f -print0 | xargs -0 sha256sum`, plus
   modes) over the same excludes, so the host's `build-win/`,
   `bench-logs/`, `game_files/` and `bench-provenance.txt` are never
   touched.
3. It sends only the files whose hash or mode differs, as one `tar`
   stream written by `tarfile` to `ssh HOST tar -x -C DIR` on stdin, with
   no mtimes (`--no-times` semantics: the host's extraction time is the
   mtime, so ninja rebuilds exactly what changed and nothing that did not),
   then deletes the host files the manifest has and the tree does not
   (`--delete`), never under an excluded path.
4. Pulls (`logs`, the golden frames) are the reverse: a manifest of the
   remote directory, then `ssh HOST tar -c ... | tarfile.extractall` for
   the missing or changed files, keeping the host's mtimes as `rsync -az`
   does for pulls. `extractall` uses the `data` filter (Python 3.12+) or
   checks every member path stays inside the destination.

Game files (`sync --game-files`) use size and mtime instead of hashes, as
today's `rsync -az` quick check does, because the dump is gigabytes of
data that never change. The reflink and symlink logic is a host script
and does not change.

Parity: on the Mac, a sync with `BENCH_RSYNC=0` after a sync with rsync
must produce the same remote gen digest and a build whose last line is
`no work to do`; then one changed file must rebuild only its objects.

### D7. Command layout and help

`blinx2 bench` is one entry in `COMMANDS` (so `blinx2 --help` lists it on
one line under "Developer commands": `blinx2 bench ...  drive the Proton
bench host (blinx2 bench --help)`), with its own argparse sub-tree in
`benchlib`. The player block of the help is unchanged. `blinx2 bench
--help` carries today's bench.sh header: commands, options, the
`BENCH_*` table, the lock rule and the host layout. The `--kill-game`
flag is accepted by every command that runs the game, as today.

As built (phase 1): `blinx2.py`'s `main()` takes `bench` off `argv` before
argparse sees it and hands the rest to `benchlib.main()`, so options such as
`--golden`, `--record` or `--kill-game` reach the bench untouched instead of
being rejected by the top-level parser. `benchlib` parses its own
arguments, in the order bench.sh did, rather than with an argparse tree.

`bench doctor` (new): `ssh -o BatchMode=yes HOST true`, the host's
`umu-run`, `distrobox list` for `BENCH_BOX`, `rsync` on the controller, the lock holder if any (`lslocks`), and
`bench-provenance.txt` on the host. It changes nothing.

### D8. Parity, and what each phase proves

The parity test (`scripts/test_bench_cli.py`) puts a fake `ssh` and
`rsync` first on `PATH`. The fake `ssh` records its argv and stdin to
files; the fake `rsync` records its argv. The test runs `bench.sh <cmd>`
and `blinx2 bench <cmd>` for `sync`, `build -DX=1`, `run --arg`, `tests`,
`symbolize`, `logs`, `integrate --golden` (with a scratch git tree on
`main` and `BENCH_GAME_DIR` set) and `pacing --runs 1 "A=1" "B=2"`, and
compares, per ssh call: the argv, and the remote script after the
variable prologue is parsed into a `name=value` map (so `printf %q` and
`shell_quote()` may differ in spelling but not in value). The host-script
bodies must be byte-equal until phase 4; from then on the test compares
`blinx2 bench` against the host files directly. `rsync` argv must be
equal. This test runs on macOS and Linux (bash present); on Windows it is
skipped with a reason.

`test_bench_checks.py` feeds `check_run_end` and `check_present_mismatch`
fixture directories (clean run, crash, SIGKILL at the limit, early exit,
flips under the floor on a busy host, on an idle host, a survivor that was
killed, one still alive, a log without flip lines) and asserts the
message and the return code `bench.sh` gives today, taken from its code.

Real gates on the Linux/Proton host, in order and each before the next phase merges:
1. `blinx2 bench golden` on the integration build, after `bench.sh
   golden` on the same build: same verdict, same `check`/`record` output,
   same files in `bench-logs/<stamp>/` (names and `run-info.txt` fields).
2. `blinx2 bench integrate --golden` from the main checkout: same
   `bench-provenance.txt`, `build-win/provenance.txt`, gen digest line
   and exe sha as `bench.sh integrate` from the same commits.
3. A golden through the `bench.sh` shim.
4. (Phase 3, deferred) the `BENCH_RSYNC=0` parity of D6.

### D9. Migration phases

| Phase | Lands | Removes | Gates |
|---|---|---|---|
| 0 tooling | `pyproject.toml`, `uv.lock`, `.python-version`, ruff config, the format commit, `setup`/`doctor`/`pins` on uv (uv from `PATH`) | `requirements-*.txt`, the hand resolver | `uv run pytest scripts`; ruff gates; fresh-clone `./blinx2 setup` on the Mac; Mac build; one Metal golden |
| 1 controller | `scripts/benchlib/`, `blinx2 bench` with `bench doctor` (D7), parity and checks tests | nothing (`bench.sh` untouched) | pytest; parity test; the Linux/Proton host gates 1 and 2 |
| 2 shims | `bench.sh` → `exec python3 blinx2.py bench "$@"`; `pipeline.sh` prints a deprecation line; references updated (README, docs, env.md, TASKS, comments in `golden.py`, `running_game.py`, `benchlog-retention.py`, `vpad.py`, `openspec/config.yaml`) | the bench.sh body | the Linux/Proton host gate 3; `grep -rn 'bench\.sh\|pipeline\.sh'` lists only the shims, the archive and history |
| 3 Windows host | **deferred (Q4)**: the manifest transfer, Windows path handling, docs for OpenSSH on Windows | nothing | not in this change; a follow-up in TASKS.md |
| 4 removal | `.git-blame-ignore-revs` tidy; packaging spec sync | `scripts/bench.sh`, `scripts/pipeline.sh` | pytest; the orchestrator has amended CLAUDE.md and the memory notes first |

Each phase is one branch on the agent's worktree, squash-merged by the
orchestrator after a Fable review (phase 0: squash merge, with the
format-only pass landed as its own commit on main, so
`.git-blame-ignore-revs` can name its main sha) (batched if the Fable quota requires,
but never skipped for phases 1 and 2).

### D10. Rules kept

- **recomp_env.** No new game variable. `BENCH_*`, `RECOMP_BENCH_RUN` and
  `BENCH_RSYNC` are controller or host-script variables the game never
  reads; `docs/env.md` "Not in the table" names `scripts/benchlib` for
  them. If the port ever needs the game to read something new, it goes
  through the table with an `env.md` row.
- **stdlib-first.** `blinx2.py` and `scripts/benchlib/` import only the
  standard library. uv and ruff are development tools, not runtime
  dependencies of anything the user runs; cmake, ninja, capstone and
  pefile are what `setup` installed before.
- **Never publish game data.** The bench moves game data only between the
  user's machines, as today; `sync` keeps every exclude, and the manifest
  transfer applies the same list. `scripts/bench.env` stays gitignored and
  excluded from sync.
- **export-public.** `scripts/export-public.sh` stays and is still
  excluded. Its `REWRITE` rules cover the new files' text; the export test
  adds a `scripts/benchlib/host/run_game.sh` fixture with a "bench host"
  comment to prove the rewrite reaches it.
- **Opt-in, backends agree.** Not applicable: no runtime behaviour.

### D11. CLAUDE.md lines for the orchestrator

The workspace `CLAUDE.md` (outside this repo), at 2026-10-06:

| Line | Today | After |
|---|---|---|
| 39 | `The POSIX ctest dirs plus `pytest tools/recomp tools/disasm` when tools changed.` | add: `uv run pytest scripts` for cat, and `uv run ruff check . && uv run ruff format --check .` |
| 42 | `` `scripts/bench.sh golden` for D3D11 under Proton `` | `` `blinx2 bench golden` `` |
| 52 | `sync and rebuild the Linux/Proton host (`scripts/bench.sh integrate`) and run golden` | `` `blinx2 bench integrate --golden` `` |
| 61 | `C11 for C. Python 3 stdlib-first for tools.` | `C11 for C. Python 3 stdlib-first for tools and runtime scripts; uv manages the dev environment (`pyproject.toml`, `uv.lock`), ruff lints and formats.` |
| 63 | `` `cat/src/recomp/gen/` comes from `scripts/pipeline.sh` `` | `` comes from `blinx2 analyze` then `blinx2 recomp` `` |
| 65 | `` `pipeline.sh analyze` before `recomp` `` | `` `blinx2 analyze` before `blinx2 recomp` `` |
| 85 | `` `bench.sh` takes the lock itself, so don't nest it `` | `` `blinx2 bench` takes the lock itself, so don't nest it `` |

The memory notes that name `bench.sh` (`bench-stays-current`,
`subagent-required-tasks`) are the orchestrator's too. Until phase 4 the
shim keeps the old spellings working.

## Risks / Trade-offs

- **A parity gap in the remote scripts** breaks a gate. Mitigation: byte-
  equal host scripts in phase 1, the fake-ssh test, and two real the Linux/Proton host
  gates before `bench.sh` loses its body.
- **`printf %q` versus `shell_quote()`** on unusual `BENCH_ENV` values
  (quotes, `$`). Mitigation: the parity test parses the prologue into
  values; `shell_quote()` single-quotes anything outside `[A-Za-z0-9_./:=+-]`.
- **uv's lockfile drifts** from what a developer has. `--locked` fails
  loudly and `doctor` says "run blinx2 setup". `pins refresh` is the only
  thing that rewrites it.
- **Astral as a vendor.** uv is the user's own install (Q1), not a pin
  of ours; what it installs is still verified against `uv.lock`.
- **uv becomes a prerequisite for players.** A player's first `./blinx2`
  needs uv on `PATH` (Q1). Mitigation: the error and `doctor` print the
  one install command for the host; the README and `docs/packaging.md`
  list uv next to Python and git.
- **ruff churn hides the port's diff.** The format commit comes first and
  is blame-ignored.
- **The Windows controlling host** is deferred (Q4); `bench.sh` today is
  no worse.
- **`fps-pacing` and `bench-methodology`** both name `bench.sh` in open
  deltas and tasks; the shim keeps them true, and the archive step renames.

## Decided

The user answered the open questions on 2026-10-06. These are binding.

1. **uv bootstrap (D4): uv must be on `PATH`.** `blinx2 setup` does not
   download uv. If uv is missing, `setup` and `doctor` say so with the
   install hint for each OS, and `blinx2.py` stays standard-library so it
   starts without uv. D4 is rewritten accordingly; `setup-pins.json` gets
   no uv pin.
2. **ruff (D5):** the recommended rules, `E F W I UP B`, line length 100
   with `E501` ignored, `target-version = "py39"`.
3. **Shims (D9):** `bench.sh` and `pipeline.sh` are deleted in phase 4.
4. **Windows controlling host (phase 3): deferred.** It moves to a
   follow-up in tasks.md and TASKS.md; this change ends without it. The
   D6 manifest transfer goes with it. `bench doctor` (D7) is not
   Windows-specific and moves into phase 1.
5. **`export-public.sh`** stays shell and private.
