# cli-extraction: the game-agnostic toolchain CLI moves to its own repo

Status: spec drafted by Fable (2026-10-06), read on cat `main` at 70bf5c8
(the branch is off a8ade89; only `TASKS.md` moved in between). No
implementation here. The user answered the draft's three questions the
same day; they are recorded in design.md "Decided" and are binding.

## Why

`blinx2.py` (2426 lines at 70bf5c8) plus `scripts/benchlib/`,
`scripts/package_lib.py`, `scripts/golden.py`, `scripts/game_icon.py`,
`scripts/progress.py` and their tests are about 9,500 lines of Python and
shell that set up a toolchain, drive the toolkit's `tools/`, build, package,
and run the Proton bench. Almost none of it knows anything about BLiNX 2.
What it does know is a short list of constants and paths: the product name,
the title ID, the executable name, the disasm sections, the seed and
spin-wait files, the Homebrew libraries, the data folders, the golden file.
Those live in `blinx2.py` lines 293-387, 1418, 1707-1721 and in
`package_lib.py` lines 33-45, 263, 280 (design.md D1 has the full table).

The user decided (TASKS.md, 2026-10-06) that this code becomes its own
repository, `xboxrecomp-cli`, so that:

- **A third game needs only a manifest.** Burnout 3 today runs the
  upstream-shaped `regen.sh` (`py -3`, hard-coded paths, no doctor, no
  packaging, no bench driver) and a local `_local/bench host.sh` that copies
  cat's toolchain file by hand. With a `game.toml` it gets `setup`,
  `doctor`, the pipeline, `build` and `bench` for free; packaging follows
  when its launchers exist.
- **The toolkit fork stays close to upstream.** The CLI never enters
  `apexJCL/xboxrecomp`: upstream's `tools/` are a library the CLI drives,
  and keeping the driver out of the fork keeps the give-back diff small
  (the user's clean-history rule).
- **One place to fix the toolchain.** A bench or packaging fix today lands
  in cat and would have to be copied into Burnout 3 by hand.

The user decided (2026-10-06) that it is public from its first push round,
as `apexJCL/xboxrecomp-cli`, under the lean-public-repos rules. Nothing in
this change pushes anything; the rounds are asked of the user as always.

### Feasibility (Fable's assessment)

Feasible, and mostly mechanical, because toolchain-cli already did the hard
part: the controller is Python, the host scripts are files, and the parity
test (`scripts/test_bench_cli.py` against `testdata/bench_parity.json`)
pins what the bench sends byte for byte. The CLI's own tests
(`test_blinx2_cli.py`, 898 lines) already run against a fake tree, so they
move with the code. The gates that prove nothing changed exist today:
`./blinx2 --help` byte-equal, `bench_parity.json`, the gen key (`plan:
build, package` with no regenerate), the packaged payload, `blinx2 bench
integrate --golden`.

What takes judgement is the manifest: which constants are the game's, which
are the project's policy (branch names, pins) and which are the host's
(`BENCH_*`). D1 and D2 settle that with file:line evidence.

The cost is a repository to keep in step (pinned, like the toolkit), the
export-public story for the public `blinx2-recomp` (D7: a user decision),
and one more tree in every provenance line.

## What Changes

- **New repository `xboxrecomp-cli`** (local, private): a uv-managed Python
  package, `requires-python >= 3.12`, standard library at runtime, with
  `ruff`, `pytest`, the parity and CLI tests moved from cat, and the bench
  host scripts. It has no game data, no game names and no toolkit code.
- **`game.toml`** at the game's root: name, slug, XBE path and title ID
  (plus optional known-dump hashes), the toolkit pin, the CLI pin, the
  pipeline inputs, the build names, the packaging identity, the data
  folders, the input script key and presets, the golden file, the bench
  policy. Schema and the BLiNX 2 example in design.md D2.
- **cat keeps** `./blinx2`, `blinx2.cmd` and a 60-line `blinx2.py`
  bootstrap (standard library, Python 3.9) that finds uv and the pinned CLI
  and execs it; `game.toml`; `pyproject.toml` and `uv.lock` for the tools
  environment; `config/setup-pins.json` (download hashes only);
  `config/seed_functions.json`, `config/spin_waits.json`,
  `scripts/host_reserved_names.py`; `analysis/golden/golden.json`;
  `packaging/` (phase A: all of it; phase B: only the game's content);
  `scripts/export-public.sh` and the game-only scripts and tests (D1).
- **Pins** go game → CLI → toolkit: `game.toml` names the CLI commit and
  the toolkit commit; `setup` clones each into `external/` at its pin when
  it is not found beside the checkout, as it clones the toolkit today;
  `XBOXRECOMP_CLI_DIR` overrides, as `XBOXRECOMP_DIR` does (D4).
- **Migration** in two phases on cat, each gated on byte-identical
  behaviour (D5): A, the code moves and reads the game's files where they
  are; B, the generic packaging templates and host helpers move into the
  CLI, parameterised by the manifest. Burnout 3 is a follow-up, not in
  scope (D2 "What Burnout 3 needs" records what its manifest will say).
- **History:** the CLI repository starts fresh with one commit that cites
  the cat shas the files came from (D6).
- **Public story (user decision, 2026-10-06):** `xboxrecomp-cli` becomes
  its own public repository, `apexJCL/xboxrecomp-cli`, with only `main`,
  batched push rounds, the noreply identity from its first commit and a
  pre-push audit; the public `blinx2-recomp` pins it by sha through
  `game.toml`, and the CLI's round goes before cat's (D7).
- **Unknown dump (user decision):** `xbe.sha256` lists the known dumps;
  build and play warn, `bench golden` refuses. The user's new dump has a
  different `default.xbe` from the old one; whether the code moved is a
  task, and the list holds what it finds (D2).
- **Docs:** `docs/packaging.md` (where the CLI comes from, the override),
  the README developer section and layout list, `docs/env.md` "Not in the
  table" (the `scripts/benchlib` mention becomes the CLI), and a README for
  the CLI repository.

Non-goals: any change to what the pipeline, the build, the bench or the
packaging produce (the gates forbid it); the toolkit; Burnout 3's
migration; publishing the CLI; a Windows bench controller (still deferred);
porting `export-public.sh` or `xemu_capture.sh`.

## Capabilities

### New Capabilities
- `game-manifest`: the `game.toml` schema and validation, the game → CLI →
  toolkit pin chain, the wrapper bootstrap and the developer override.

### Modified Capabilities
- `packaging`: "One CLI on every build host" (the CLI comes from
  `xboxrecomp-cli`; the game ships the manifest and the wrapper), "Setup
  fetches a pinned, verified toolchain" (the CLI clone at its pin), "Manifest
  and version" (the CLI tree in `sources`).
- `dev-tooling`: "Runtime code stays standard-library", "Tests run through
  uv" and "ruff lints and formats every Python file in this repository"
  name the CLI repository and its Python floor. These requirements are in
  toolchain-cli's deltas, not yet in `openspec/specs/`: toolchain-cli
  archives before this change does.

## Impact

- **Backends, hosts, goldens.** No render path, runtime or kernel code
  changes; the game is not touched. The gates run the goldens once per
  phase: `blinx2 bench integrate --golden` on D3D11 under Proton (from the
  main checkout, by the orchestrator) and `@attract` on Metal on the Mac,
  as regression checks only.
- **Toolkit.** Not touched, and nothing here is meant for the fork. The
  CLI drives `tools/` as before, with the same module names and arguments
  (D1 pipeline rows). An eventual offer of the CLI to upstream is a
  separate decision (D8).
- **cat.** `blinx2.py` shrinks to the bootstrap; `scripts/benchlib/`,
  `scripts/package_lib.py`, `scripts/golden.py`, `scripts/game_icon.py`,
  `scripts/progress.py`, `scripts/pacing_stats.py`,
  `scripts/benchlog-retention.py` and their tests move out (phase A);
  `scripts/running_game.py` and `packaging/`'s generic templates move out
  (phase B). `game.toml` appears. `pyproject.toml` loses nothing but its
  name. `config/toolchain.env` goes (its tag is in `game.toml`).
  `openspec/config.yaml`'s context lines that name `blinx2 analyze` and
  `blinx2 bench` stay true.
- **Workspace.** `xboxrecomp-cli/` becomes a third main checkout beside
  `cat/` and `xboxrecomp/`, with the same rules (agents never edit it;
  worktrees under `wt/<name>/xboxrecomp-cli`). The orchestrator amends
  CLAUDE.md's Layout and gates (design.md D10).
- **Private data.** Nothing new is published. The CLI repository holds no
  game data, frames, hashes or host names (its tests use `fakehost` and
  synthetic XBEs); its own pre-push audit checks it before every round
  (D7).
- **Burnout 3.** Unchanged by this change. D2 lists what its manifest
  needs and the three toolkit-shaped differences the follow-up must check
  (`abi_analysis` flags, `--text-only`, the exe in `bin/`).
- **Other open changes.** `toolchain-cli` must archive first (its deltas
  become the main specs this change modifies). `runtime-missing-files`
  edits `docs/packaging.md` and `docs/env.md`; the wording here lands after
  it or merges with it.
