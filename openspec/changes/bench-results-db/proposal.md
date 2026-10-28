# bench-results-db: bench results and cleanup in one small SQLite tool

## Why

Bench results are plain text spread over the file system, and the user
(2026-10-25) wants them in one SQLite database that can be queried
and updated. Files on disk are kept only as paths in it. With that, old data
can be reorganised, and stale or superseded data pruned: large data is kept
only for the current and the previous release, enough to catch a regression.

What the bench keeps today (inventory in design D1):

- `bench-logs/` holds 21 GB in about 238 stamp dirs plus topic dirs. Frame
  dumps are 17.8 GB of that, Proton logs 1.6 GB and `game-stdio.log` files
  0.9 GB. Each run has a `run-info.txt` in one of three formats: the Proton
  host script (`bench/host/run_game.sh:206-219,328-343`), the Windows host
  script (`bench/host/windows/run_game.ps1:161-233`) or the Mac
  `golden run` (`golden_run.py:380-395,431`). Each format is parsed by its
  own reader (`bench/checks.py:94,185`, `bench/gc.py:88`).
- `golden-sessions.tsv` gets one appended line per golden pass
  (`bench/golden.py:314-330,490-498`). It has no game column, and its
  `host=` is only `posix` or `windows`, so the Deck and the Linux/Proton host look the same.
  Mac goldens write no line at all. On 2026-10-24 the file was overwritten,
  and 42 lines had to be rebuilt by hand into
  `golden-sessions.reconstructed.tsv`.
- Builds are barely timed:
  - `build-logs/timings.json` keeps only the last duration of each step on
    each machine (`package/progress.py:258-264,501-517`);
  - `build` (`build.py:241-308`) and bench builds (`bench/ship.py:165-202`)
    record no time, job count or warm state;
  - builds on the Windows PC leave nothing the Mac reads;
  - patch sizes live in `patch.json` (`package/patch.py:313-325`) and are
    not collected anywhere.
- Performance is recomputed by hand each time: flips/s from `run-info.txt`
  (`bench/checks.py:181-205`), frame intervals from `pacing-stats`, and
  steady fps and p99 from `bench-matrix analyse`. Nothing compares a build
  with the previous release, so the 25% flips/s and 1.5x frame-ms rules are
  applied by hand.
- Releases (`v2026.10.1`-`.3` for BLiNX 2) exist only as public tags and
  as `<public> <private> <date>` lines in the export map
  (`public.py:713-716`). No bench result is tied to one.
- Cleanup runs through three tools with three rule sets: `bench gc`
  (`bench/gc.py:1-25`, `--host`), `benchlog-retention`
  (`benchlog_retention.py:1-35`) and the workspace's
  `notes/cleanup-derived.py`. Its refusals go to the user as `!` commands.

## What changes

- **A new command, `benchdb`**, shipped in the xboxrecomp-cli package next
  to `xbr`. Its code is a stdlib module `xboxrecomp_cli/benchdb/` using only
  `sqlite3`. It is scoped to the workspace, not one game, and reads its
  private settings (roots, hosts, reference files) from a local
  `benchdb.toml` that is in no repo (D2, D3). `<game> bench db` is an
  alias for it.
- **Data verbs**: `init`, `import`, `pull`, `releases`, `show`, `query`,
  `regress`, `export`.
- **One db file**: `bench-logs/bench.db` on the Mac, shared by every game.
  WAL mode, short `BEGIN IMMEDIATE` writes and a daily online backup.
  Hosts never open the db. Their runs reach it by the existing pulls, and
  their builds through an inbox that `benchdb pull` fetches.
- **Writers**: `bench run`, `golden`, `integrate`, `golden run`, `pacing`,
  `build`, `package` (full and patch) and `bench-matrix collect` each
  write a `record.json` beside their output and a row in the db. A run dir
  describes itself, so the db can always be rebuilt from disk.
- **Every build on every host is timed** (the Mac, the native Windows PC,
  cross builds): steps, jobs, cold or warm, gen reuse, ccache state, the
  host and its load.
- **Releases are the versions.** A build belongs to a release when its
  build inputs match the tagged commit's: the game's input paths, the
  toolkit (its public pin translated through the private toolkit map) and
  the CLI. Docs and pin-only release commits do not break the match. A
  release with no matching build gets a marked stand-in, and each release
  round runs one integrate at the tag so the match is the normal case. The current and previous
  release keep their large files. Internal builds keep theirs until the
  next release, at most the newest 3 since the last release. Rows are kept
  forever.
- **Cleanup**: `benchdb plan` and `benchdb clean` replace
  `cleanup-derived.py`, `bench gc` and `benchlog-retention`. They are the
  single sanctioned deletion path, and agents run them without asking:
  - they cover the Mac roots and the host scratch roots (Deck, the Linux/Proton host,
    the PC), including old read-only `game_files` copies and the dangling
    `bench-logs/bench-logs` link;
  - guards replace the user's `!` review and are at least as strong as
    `bench gc`'s: declared roots and narrow patterns; never-paths; links
    only ever unlinked; pins from every game's reference files in every
    worktree, failing closed; worktrees with tracked changes or uncopied
    untracked notes refused; young and just-shipped dirs; host runs deleted
    only once the Mac holds a whole copy; a fresh plan at clean time; the
    hosts' own locks (the PC's `.bench-lock` protocol); and a journal of
    every delete.
  What stays a user action: anything outside the roots, `~/Games`
  installs, saves, configs and game dumps.
- **Migration**: a one-time import of every run dir, both session TSVs,
  `tests-pass/`, the bundle records and the releases. Unparseable runs are
  imported as `partial` with the reason. Every topic dir is flattened into
  the store, so release retention applies to its runs (D12).
- **Regression check**: `benchdb regress` compares a build with the
  previous release's build per game, host, backend and scenario:
  - a flips/s drop of 25% or more;
  - a p50 or p95 frame-interval rise to 1.5x or more;
  - build time: a step 1.5x slower and 30 s longer than comparable builds
    (same host, jobs, warm state and toolchain), flagged only for cold or
    full builds, fresh recomps, packaging, and incremental builds per
    edge.
  `bench integrate --golden` and `package` print it at their end.

## Out of scope

- The implementation, which is a later item in a CLI worktree off `main`,
  with the workspace config in its own step.
- The timeline. The tool neither reads nor feeds it. What `charts.py` drew
  from bench data becomes `benchdb query` (D14). Removing the timeline is
  a separate item, and `benchdb clean` replaces `cleanup-derived.py` only
  after it lands, so the timeline's citations keep protecting runs until
  then.
- The CLAUDE.md deletion rule. The orchestrator updates it when the tool
  merges.
- Storing any file in the db. Frames, dumps, logs and bundles stay files,
  and the db holds their paths, sizes and hashes.
- Publishing. The db, its backups, `benchdb.toml` and the exports never
  leave the Mac and are never committed or pushed.

## Decisions

The user answered the first draft's nine questions on 2026-10-25. They are
recorded in design D17, with the three defaults still open there
(`internal_keep`, the `--large` threshold, the build-time flag). The
review of 2026-10-25 is answered finding by finding at the end of
design.md.
