## 0. Decisions

- [x] 0.1 The user answered the first draft's Q1-Q9 (2026-10-25). Recorded in D17.
- [ ] 0.2 Confirm or change the three remaining defaults in D17 (`internal_keep` 3, the `--large` threshold, the build-time flag).

## 1. The command, config and schema (CLI, worktree off `main`)

- [x] 1.1 `benchdb` as a second `[project.scripts]` entry. `<game> bench db` is an alias that passes `--game`.
- [x] 1.2 `benchdb/config.py`: `benchdb.toml` discovery (cwd walk, `$BENCHDB_CONFIG`), its keys (D3), game.toml `[bench.db]` and `[release]` with defaults in `config_defaults.py`. With no config, the clean verbs are refused.
- [x] 1.3 `benchdb/schema.py`: the D5 DDL as v1, `MIGRATIONS`, `migrate()` with the pre-migration backup. A newer db opens read-only. A non-local path is refused.
- [x] 1.4 `benchdb/store.py`: `open()`, `write()` with a connection per write, upserts on the D5 keys (`builds.uuid`, `sessions.uuid`), the read-only `sql()`, the shared and exclusive `bench.db.lock`, the local-file-system check (`df -l` on macOS, `/proc/self/mounts` on Linux), and `import --rebuild` into a temp db copied in with `Connection.backup()` (D9).
- [x] 1.5 Tests: `test_benchdb_schema.py`, `test_benchdb_config.py`.

## 2. Parsers, import and releases (CLI)

- [x] 2.1 `benchdb/parse.py`: run-info in the three formats, golden.txt, both TSVs, tests-pass, patch.json, bundle records, build records, and flip-trace stats through `pacing_stats`'s parser.
- [x] 2.2 `ingest_run` and `ingest_build`, shared by the writers and `import`. Partial and unparsed runs are kept with their reasons.
- [x] 2.3 `benchdb/releases.py` (D10): tags as the union of `refs/public-tags/` and `ls-remote`, `unmapped` and `withdrawn` states, the export map, the pins at the private sha, the toolkit pin through `[release] toolkit_map`, matching on `[release] inputs` (game), tree diff (toolkit) and `src/` (CLI), and the stand-in fallback. `public export --tag` calls `releases --refresh`.
- [x] 2.3a Host keys from the OS markers first, then the case-sensitive uname (D12.2).
- [x] 2.4 Verbs: `init`, `import`, `releases`, `show`, `query` (with `series`, `boot`, `builds`, `flakes`, `deletions`, `--sql`), `export`.
- [x] 2.5 Tests: `test_benchdb_parse.py`, `test_benchdb_ingest.py`, `test_benchdb_releases.py`, `test_benchdb_cli.py` (D16: findings 1, 8, 10, 12, 13). Synthetic fixtures only.

## 3. Writers (CLI)

- [x] 3.1 `bench run`, `golden`, `integrate`: run records after the pull and the check, session and verdict rows next to the TSV line, the `BENCH_HOST` key, `lineage = integration` for `integrate`.
- [x] 3.2 `golden run`, `golden play`: run records and a `golden-run` session per call. The run-info gains `toolkit:` and `cli:` lines with their tree state, and the build uuid, so Metal runs can match a release (D10).
- [x] 3.2a Every `record.json` gets a `uuid`. `bench ship` writes `build: <uuid>` into the host run dir's provenance and touches the host run dir it ships to (D5, D11 guard 5).
- [x] 3.3 `bench pacing`, `bench tests`, `bench-matrix collect` rows. The standalone `analyze` and `recomp` verbs are timed as builds (D13).
- [x] 3.4 `build`: timed steps, jobs, cold/warm/reconfigured, gen reuse, edges, ccache, the toolchain identity (llvm-mingw, CLT or Xcode, CMake, Ninja), host CPU, memory and load, failed builds included. `build-record.json`, with ship's provenance added.
- [x] 3.5 `package`: every progress step timed, patch base and sizes, bundle and patch artifacts. `prune_bundles` journals its deletes.
- [x] 3.6 The inbox (D7.6): host-side `BENCHDB_HOST`/`BENCHDB_INBOX`, nothing written without them; atomic temp-then-rename writes. `benchdb pull [--host]` imports, commits, then deletes only the imported files by name and hash, directly and without the run lock. Run by `integrate` and `golden` at the start.
- [x] 3.7 A failed db write warns and never changes a command's rc. Tests for each writer, including a Windows-path inbox.

## 4. Retention and cleanup (CLI)

- [x] 4.1 `benchdb/retain.py`: D10 (two releases, internal builds until the next release with at most 3, the integration baseline, young, pinned, incomplete, per game), with each kept item's first reason.
- [x] 4.2a `benchdb/clean.py`, local: the D11 guards 1-7 (parent realpath and leaf lstat; patterns and `[never]`; gc's `read_refs` and `protection` over every game and worktree, failing closed, HHMMSS kept, `[refs] exclude`; worktrees with untracked files not under `notes/<name>/` refused; young and recently shipped; retention; host runs pulled whole, from gc's `pulled_state`); only deletable roots planned; local deletion (worktree remove and prune, `chmod` without following links, links unlinked); plan files; `clean <id>` as the intersection with a fresh plan; `--large`; the `deletions` journal and `clean.log`, with `$BENCHDB_AGENT`. Tests with a temp tree.
- [x] 4.2b POSIX remote: the shipped `clean_apply.sh` under `flock -x -w 3600 ~/.recomp-run.lock` (the resolved path `realpath(parent)/name` checked against root, `[never]` and reference-only roots and deleted; guard 5 re-checked from each path's planned mtime; `rm` for a link, `find -P -xdev ! -type l -exec chmod u+w` then `rm -rf --one-file-system --`, no trailing `/`). Tests: the script against a temp tree, the commands through a fake ssh.
- [ ] 4.2c Windows remote: the shipped `clean_apply.ps1` with the `.bench-lock` protocol of `run_game.ps1:30-104`, the same resolved-path and mtime re-checks, a manual walk (`EnumerateFileSystemEntries`, a per-entry `ReparsePoint` test, links deleted with `Delete(path, $false)` and never entered, read-only cleared only on plain files), never `-Recurse`. Tests: the PowerShell builder, junction and symlink cases including a junction to a read-only dir outside the tree that must keep its files and attributes, the lock text and takeover; one fixture run on the PC when it is up on Windows (never switch the boot for it). *Done except the PC fixture run: the builder text, the lock and the link cases are tested on the Mac, which has no pwsh; the run is a follow-up item.*
- [x] 4.3 Verbs: `pins [--refresh]`, `plan`, `clean PLAN_ID`, `gc`.
- [x] 4.4 `bench gc` (with `--host`) prints the matching `benchdb plan` call and exits 2. Move `protection`, `STAMP_RE` and `SIX_RE` from `benchlog_retention.py` into `benchdb/` and point `bench/gc.py:39` at them; then remove `benchlog-retention`, its `main.py:638,670` entries and `tests/test_benchlog_retention.py`.
- [x] 4.5 Tests: `test_benchdb_retain.py`, `test_benchdb_clean.py` (D16: findings 2, 3, 4, 5, 6, 7, 16, 18).

## 5. Regression (CLI)

- [x] 5.1 `benchdb/regress.py` and `benchdb regress` for runs (D13), against the previous release by default.
- [x] 5.1a The run filter as a whitelist (`pass`, `pass-with-known`, `REGRESSION`), one verdict per run from a session that was not reconstructed (D13).
- [x] 5.2 Build-time regression: comparable builds including the toolchain; only cold or full builds, fresh recomp and analyze, package and patch steps flagged, incremental builds by secs per edge; 1.5x and +30 s against the median of 5; fewer than 3 baselines never flagged.
- [x] 5.3 `bench integrate --golden` and `package` print their lines at the end, and golden's rc is unchanged.
- [x] 5.4 Tests: `test_benchdb_regress.py`.

## 6. Migration (workspace, after the CLI lands and cat re-pins)

- [ ] 6.1 Write `<ws>/benchdb.toml`: the deletable roots and patterns (D11.1, with the narrowed `/tmp` and the PC `D:\bench\<task>` patterns), the reference-only checkout and notes roots, the never-paths, `[refs]` and its `exclude`, `[release] export_maps` and `toolkit_map`, the hosts with their OS markers and uname aliases, the PC inbox, the games. Set `BENCHDB_HOST`/`BENCHDB_INBOX` in the PC's Windows profile.
- [ ] 6.2 `benchdb init`, `import --all --dry-run`. Check the counts per game against `bench gc`'s listing.
- [ ] 6.3 `import --all`, `releases --refresh`, `pins --refresh`, then `plan`. Post the plan's size and its refusals on the tracker item before the first `clean`. `benchdb clean` replaces `cleanup-derived.py` only after this supervised first clean and after the timeline-removal item has landed (D11.6, D14).
- [ ] 6.4 Layout (D12.7): flatten every topic dir (`jsrf-golden/`, `jsrf-fps/`, `sdl3-gate8/`, `linux-native-gate8/`, `ssx3-20261018-185435/`) into the store root with `mv -n`, aborting a dir on a clash. Update the relpaths and pins in one transaction. Remove the empty dirs and the dangling `bench-logs/bench-logs` link with `benchdb clean`.
- [ ] 6.4a Change `notes/jsrf-golden/*.sh` from `--out bench-logs/jsrf-golden` to `--out bench-logs`.
- [ ] 6.5 Host stores: plan and clean the old Deck `~/<task>-bench` trees and `~/blx-bench`, the Linux/Proton host `*-bench` trees, and the PC task trees when it is up on Windows. Each goes only once its runs are pulled whole (guard 7).
- [ ] 6.6 Optional, per game when its owner agrees: `bench-logs` links for b3, ssx3/recomp and spartan. Until then their `bench-logs/` are extra store roots in `benchdb.toml`.
- [ ] 6.7 `notes/cleanup-derived.py` becomes the wrapper that prints the `benchdb plan` call. Remove it later with `benchdb clean` once nothing calls it.
- [ ] 6.8 Release procedure: after `public export --tag`, one `bench integrate --golden` and one Metal `golden run` on the exported private sha, so each release has a matched build per host (D10). Add the step to the release checklist.

## 7. Gates

- [x] 7.1 CLI: `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.
- [x] 7.2 `scripts/audit-public.sh` refuses `*.db`, `*.db-wal`, SQLite magic bytes and `benchdb.toml`. The CLI's delta is audited before its push round. *The rules and their tests are in; the push-round audit is the orchestrator's.*
- [ ] 7.3 One `blinx2 bench integrate --golden` on the Deck with the db live: the session, verdicts, perf, build rows and regress output are checked against `golden.txt`, run-info and the build log. One Windows-PC build is checked through `pull` when the PC is up on Windows (never switch the boot for it). No golden gate otherwise, since nothing the game runs changes.
- [ ] 7.4 Review of the merge. *The pre-merge review is answered on feat/benchdb: H1-H3, M1-M10, L1, L3, L10-L13, N2, N4 and the `live.run` TypeError are fixed, each with a test. The rest (L2, L4-L9, N1, N3) is the tracker item.*

## 8. Follow-ups (one release round after the tool lands)

- [ ] 8.1 Stop writing `golden-sessions.tsv`; it is made on demand by `export --sessions-tsv` (D17 Q4).
- [ ] 8.2 Remove the `bench gc` stub (D11.6).

## Implementation notes (feat/benchdb)

Where the code departs from design.md, and why.

- The game.toml defaults (`[bench.db]`, `[bench.db.regress]`, `[release]`) are in the manifest `SPEC` and `docs/manifest.md`, not `config_defaults.py`. That file is the runtime `config.default.toml` helper.
- The package exports `load_config()` instead of D7's `config()`, because `config()` shadowed the `config` submodule.
- The record IO is in `record.py`, the shared run and build ingest is in `ingest.py`, and the live writers are in `live.py`. The host scripts are in `benchdb/host/`.
- The default `[release] inputs` are `src`, `config`, `CMakeLists.txt` and `cmake`, plus game.toml's `toolkit`, `cli`, `pipeline` and `build` tables.
- A clean branch build can match a release. Lineage gates only the stand-ins, which is how D10 reads.
- The Windows run-dir touch (D11 guard 5) goes through `ship.ps1`.
- ccache is recorded as on or off from the compiler launcher only.
- Package records take the bundle index's uuid, so `import` does not count a bundle twice.
- The matrix stamp comes from `started`.
- The standalone `analyze` and `recomp` records are `<out>/<verb>-record.json`.
- `pull` reads the inbox as base64 over ssh rather than through scp.
- `golden play` records a run of kind `play`.
- The `golden run` session record sits in `--out`.
- The tests' conftest keeps any real `benchdb.toml` out of reach.
- Cleanup:
  - Worktrees and scratch trees are pinned by their path only, as in `cleanup-derived.py`.
  - Plan ids avoid the stamp regexes.
  - The deletions journal covers only planned items.
  - Host items are keyed by their resolved path.
- Regress (D13):
  - An incremental build is compared by seconds per edge. Its +30 s floor applies to the difference times its edges, so the floor stays in seconds.
  - For gen builds (the standalone `analyze` and `recomp`), the command is part of the comparable key, so an `analyze` is never compared with a `recomp`.
  - A failed build or step is listed and never compared.
- `regress` is printed after `bench integrate --golden` only for a local build (`BENCH_BUILD=local`), since only there is the shipped build's uuid known here.
- Review fixes (pre-merge):
  - Guard 4 keeps a file unless it is build output, regenerable pipeline output, identical to the main checkout's copy, or has its sha under `notes/<name>/`. A HEAD that no ref holds refuses.
  - A path not spelled as the disk spells it (case, Unicode normalisation) is refused.
  - `--older-than` under 1 day needs `--force-young`. Retention and links get the young check too.
  - The host apply renames a dir to `.<name>.deleting.<pid>` before it deletes it, and puts it back if a ship touched it meanwhile.
  - The db lock times out after 300 s.
