Worktrees: `wt/clihk/xboxrecomp-cli` on CLI `feat/cli-housekeeping` (off main 023c77e), whose commits are authored and committed as `carlos <4037632+apexJCL@users.noreply.github.com>`; and `wt/clihk/cat` on cat `feat/cli-housekeeping` (off main 5dd464d), whose commits use the private local identity (the workspace rules). There is no toolkit worktree. Small commits, with subjects `area: what changed`. No agent runs `bench gc --apply`, `golden prune` on a store run, or any other deletion of existing data: those reach the user as `!` lines (7.5). The Linux/Proton host only for 7.2 and 7.3, after "ready for the Linux/Proton host" and the orchestrator's "go".

Public-repo rules for every CLI commit: fixtures are synthetic (a run-info.txt fixture is written by the test with placeholder host, paths and shas; never copied from the store, whose files carry the Mac host name and home directories); no `.bmp`/`.png` is committed (the tests write theirs into temp dirs); host scripts, help and tests name no host. `scripts/audit-public.sh main..HEAD` must pass before every push to the branch is called done (7.1).

## 1. bench gc (CLI)

- [x] 1.1 Manifest: a `bench.gc` table (`refs` STRS `[]`, `refs_exclude` STRS `[]`, `keep` INT 3, `days` INT 7), with rows in `docs/manifest.md` (the `refs` row says `../` is allowed here); tests in `tests/test_manifest.py`, including a `refs` path with `../` accepted and `keep = "3"` rejected.
- [x] 1.2 `bench/gc.py`: entry selection (D1.1), owner from the exe line (D1.2 rule 1), the (kind, scenario) group key (rule 5), allocated sizes, and the plan with ordered reasons. These are pure functions over a store path, a parsed host listing and a reference text.
- [x] 1.3 Reference text (D1.3): worktree list, the main checkout as its first entry, per-worktree sources, `bench.gc.refs` with the suffix filter, `refs_exclude`, `--refs`, the skip list, the 8 MiB cap, the refusals, the counts line and the sole-protector report. Reuse `benchlog_retention.protection`/`STAMP_RE`/`SIX_RE`/`_walk_files`.
- [x] 1.4 The local `--apply` with the D1.5 path checks; exit 2 on a failure. The missing-store refusal and the realpath header.
- [x] 1.5 `--host`: `host/gc_list.sh` (one ssh round trip: names, du, run-info sha, exit-code presence, file names outside frames/, frames/ size), and `host/gc_apply.sh` under `flock -x -w 3600`, with exit 75 handled. Plus the pulled rule (rule 6) with the `.zst`/`.gz` equivalence and the frames/ and `steam-*.log` exclusions.
- [x] 1.6 Wiring: `gc` in `COMMANDS`/`dispatch`, the HELP text, README; `BENCH_HOST` is needed only with `--host`. `test_bench_cli.py`'s parity record learns the two new host scripts.
- [x] 1.7 Tests (`tests/test_bench_gc.py`), on temp stores built from synthetic run-info text:
  - each protection rule, alone and in order;
  - owner: exe line ours, another exe (never removed, even with `--include-unowned`), no exe line (unowned; removable only with the flag), a tree line that names an agent folder with our exe (ours);
  - a suffixed stamp, and an HHMMSS-only reference;
  - a reference only in a second worktree's untracked RESUME (a temp git repo with `git worktree add`);
  - `refs_exclude` drops an inventory file, and the sole-protector report names it when it is not excluded;
  - a missing `refs` path in the main checkout refuses; the same path missing in the other worktree does not;
  - a file over 8 MiB is skipped and named;
  - newest N per (kind, scenario), with golden, pacing and plain runs kept apart;
  - no `exit-code` keeps a run at any age;
  - a symlink inside a run is not followed; a loose file or named dir is never touched;
  - a dry run changes nothing (tree hash before = after);
  - the refusal without golden.json and without a store;
  - the host plan from a canned `gc_list.sh` output (no ssh): pulled, not pulled (a file missing locally), pulled with a local `.zst`, host frames/ ignored.
- [x] 1.8 Dry run on the real Mac store (read-only): `blinx2 bench gc` from `wt/clihk/cat`, using the CLI branch (`XBR_CLI_DIR` or the worktree's venv), with cat's `[bench.gc]` entries in place. Save the output to `xbox-recomp/runs/clihk/gc-dry-mac.txt`.
- [x] 1.9 Cross-check against the audit (`notes/disk-audit-2026-10-06/`) and the store's state today (340 stamp runs; tier 1 gone; tier 2's 208 present; 116 referenced; 16 newer):
  - every stamp in `referenced-stamps.txt` that is still in the store is protected, and by `referenced` (not only by age or newest);
  - every run gc marks removable is in `mac-tier2-benchlogs-stamps.txt`; explain any that is not before going on;
  - list the tier-2 runs gc keeps, with the reason (expected: `other game` for the one B3 run, `unowned` for the one without run-info, newest per group, and `younger than 3d` for most of them today);
  - the source report names no inventory (no file alone protects more than a handful of runs).
  Record the counts in this file.

## 2. Golden frames pruned on PASS (CLI)

- [x] 2.1 Engine: `check --used FILE` (D2): the re-record set (every frame's `dump_image_path`), the verdict images, the window best, and the per-scenario verdict lines.
- [x] 2.2 `bench golden`: the prune after the check (D2 conditions), `host/prune_frames.sh` with its path check, the `--keep-frames` flag and `BENCH_KEEP_FRAMES=1`, the summary line, and the HELP config row.
- [x] 2.3 Engine `prune SCEN=DIR [--dry-run]` for runs made by hand; it prunes only when the scenario's verdict would be 0.
- [x] 2.4 Tests (`tests/test_golden.py`, `tests/test_bench_checks.py` or a new `tests/test_golden_prune.py`), with images written by `write_png`/tiny BMPs into temp dirs:
  - a synthetic run dir with plain dumps, anchored flips and a window best is pruned to the used set; the plain dump of an anchored frame stays;
  - `check` on the pruned dir gives the same output as before (the re-check invariant, window line included);
  - `record --only NAME` and `reference` on the pruned dir succeed and record the same sha as on the unpruned one (the re-record invariant);
  - FAIL, INCOMPLETE (a NEWVIEW among them), record and keep-frames prune nothing;
  - the host prune command is built only for passing scenarios (a fake `Remote`), and its path check rejects a non-stamp name.
- [x] 2.5 Docs: the bench HELP, README, and this design's D2 wording.

## 3. recomp --seeds (CLI)

- [x] 3.1 `recomp_cmds` passes `--seeds` per `pipeline.seeds`, behind the cached source probe over `tools/recomp/*.py` (D3), with its once-per-process warning.
- [x] 3.2 Tests: the command line with and without the probe hit (a fake toolkit dir whose `tools/recomp/__main__.py` does or does not define the flag; a mention in a comment is not a hit); the order of flags; the gen key's `argv` changes when the probe flips.
- [x] 3.3 On the Mac (`wt/clihk/cat`, toolkit `posix-host/portability`), run `blinx2 analyze && blinx2 recomp`. gen/ must be byte-identical to main's (the `--seeds` flag only feeds the report). The flag-fallback report's "in observed seeds" line must be non-empty if any observed seed has a fallback site; else note that it is empty with the flag passed. Record the output in `runs/clihk/`.

## 4. enhance_stock (CLI + cat)

- [x] 4.1 Manifest: the `STRMAP` type and `golden.enhance_stock` (default `{}`); duplicates of toolkit keys are an error; a `docs/manifest.md` row.
- [x] 4.2 Engine: `ENHANCE_STOCK` without `fps.mode`; the game-key pattern and float comparison (D4); `--enhance-stock` in `take_config`; `golden_args` passing it; `--allow-enhance` over the combined table.
- [x] 4.3 Tests:
  - `fx.glow=off` is non-stock;
  - `fx.glow_intensity=1.0` is stock against `"1"`;
  - `fx.glow=` does not match `fx.glow_intensity=`;
  - `--allow-enhance fx.glow=off` is accepted;
  - with no game table, `fps.mode=lock60` is no longer flagged;
  - with cat's table it is flagged;
  - a game key repeating `render.scale` is a manifest error.
- [x] 4.4 cat `game.toml`: the `enhance_stock` and `[bench.gc]` entries (D1.4) plus the `[cli] commit` bump to the CLI branch tip, in one commit; `scripts/test_game_pins.py` passes. Update cat `docs/env.md`'s `RECOMP_FPS_MODE`, `RECOMP_GLOW` and `RECOMP_GLOW_INTENSITY` rows, which say `golden.py` fails a run with another value, so they say the check reads `game.toml [golden] enhance_stock`.
- [x] 4.5 Mac check: run `blinx2 golden check` against an existing stock Metal run (one of `final-metal-*`, glow-toggle) and against `final-off` (the glow-off run, `runs/bloom/glow-toggle/`). The stock run passes as before. `final-off` FAILs as non-stock, and passes the stock check with `--allow-enhance fx.glow=off`.

## 5. export-public REWRITE (cat)

- [x] 5.1 `scripts/export-public.sh`: the determiner and sentence-start rules (D5), in the stated place in `REWRITE`, and the "the the" check over the rewritten files.
- [x] 5.2 `scripts/test_export_public.py`: `test_rewrite_reads_well` and the "the the" failure case.
- [x] 5.3 Export the real tree to a temp dir before and after. Save the diff to `runs/clihk/export-diff.txt`. Read it for every changed line and confirm the TASKS.md line 47 phrases read well. Then tick the TASKS.md follow-up.

## 6. Stale gen/ refused (CLI)

- [x] 6.1 `toolkit_state()`: the committed half from `HEAD:tools` and `HEAD:templates/runtime` tree ids (`-` when the path is absent), the uncommitted hash over both paths; `GEN_KEY_VERSION = 2`.
- [x] 6.2 `build.build(..., stale_ok=False)`: the `gen_stale_reasons()` refusal with the reasons and the `<game> analyze && <game> recomp` hint; `<game> build --stale-gen-ok`; `package` passes `stale_ok=True` to its build. Help and README rows.
- [x] 6.3 `bench integrate --stale-gen-ok`: the check after the dirty checks and before the sync; the HELP row beside `--dirty`.
- [x] 6.4 Tests (D6): runtime-only commit fresh, `tools/` and `templates/runtime/` commits stale, the build refusal and override, the integrate refusal before any host call and its override, the version-1 key as "key format changed".
- [x] 6.5 Note for the merge (in this file and TASKS.md): the first build on the new pin is stale by construction (D3's argv, the key version); the orchestrator runs `blinx2 analyze && blinx2 recomp` on main after the merge and before the Linux/Proton integrate, and checks gen/ is unchanged.

## 7. Gates

- [x] 7.1 CLI: `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`, and `scripts/audit-public.sh main..HEAD`. Check that `git log --format='%ae %ce' main..HEAD` shows only the noreply address. cat: `uv run pytest scripts`, `uv run ruff check . && uv run ruff format --check .`. Mac build with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools` after 3.3 (the build must pass the new stale check on the regenerated gen/).
- [x] 7.2 the Linux/Proton host, after the orchestrator's "go": `blinx2 bench gc --host` (dry run only), with its output in `runs/clihk/gc-dry-host.txt`. Cross-check it against the audit's the Linux/Proton host tier lists (the user may have run them already; say what is left). Every host stamp the plan marks removable passes rule 6 (a whole local copy).
- [x] 7.3 the Linux/Proton host: one `blinx2 bench golden` from `wt/clihk/cat` at the pinned CLI. It must pass, and print the prune lines. Check that the host run dirs have no `frames/` and that the local frames dirs hold the plain dumps, the verdict images and the window bests only. Run `blinx2 golden check` again on the pruned local dirs; it must give the same verdict and window lines. Run `blinx2 golden record --only attract-cliff attract=<pruned dir>` into a scratch copy of golden.json (not the real one; `--golden-json` on a temp copy) and check it records. Then one `--keep-frames` scenario run and check that it keeps all frames. These runs delete only their own fresh dumps.
- [x] 7.4 A Fable review of the merge; its fixes go back to this branch's agent.
- [ ] 7.5 For the orchestrator: the user's `!` lines for `bench gc --apply` (Mac) and `bench gc --host --apply`, built from the reviewed dry runs and their source reports; and, if wanted, `golden prune` lines for the hand-made Metal runs.

## Follow-ups (TASKS.md)

- gc for agents' extra host trees (audit root cause 4: an `.xbr-tree` marker plus `gc --host --trees`).
- `bench logs` removing the host copy after a verified pull (audit root cause 2), or `gc --host` run after it.
- The benchlog-retention and gc overlap: retire `benchlog-retention --prune` once gc has been used for a round.
- A stale check in `bench sync`, if a stale gen/ ever reaches the host by that road again.

## Results (2026-10-07, Mac)

CLI `feat/cli-housekeeping` 30af1f4 (on main 251fde5); cat `feat/cli-housekeeping` pins it. Outputs in `xbox-recomp/runs/clihk/`.

- 1.8 `gc-dry-mac-2.txt` (after the review fixes: seed and spin-wait files read, `../notes/*/gc-dry*.txt` excluded; cat's `[bench.gc]`, days 3, keep 3): 348 runs, 0 removable: 199 younger than 3d (9.9 GB), 134 referenced (4.2 GB), 9 other game (`burnout3.exe`), 5 unowned (no run-info: pacing reports, a Mac pad run), 1 incomplete; 22 unmanaged entries (1.1 GB). Sources: 13 worktrees, 2,365 files, 139 stamps, 693 HHMMSS tokens; the biggest sole protector is `notes/batch/RESUME.md` (13 runs), no inventory. `gc-dry-mac.txt` is the same run before the fixes (343 runs, 131 referenced, 197 young; 13 worktrees, 2,324 files, 138 stamps, 688 tokens). The first dry run (`gc-dry-mac-1.txt`) read `wt/upmerge/cat/analysis/runs/` (raw logs, 14,112 HHMMSS tokens) and `analysis/bench host-inventory.md`: cat's `refs_exclude` gained `analysis/runs/*`, `analysis/*inventory*.md` and `../notes/MANIFEST.md`. gc also skips the pipeline's stage dirs under `pipeline.out` (disasm, func_id, abi, recomp, ghidra), whose hex would protect runs by HHMMSS at random.
- 1.9 Of the audit's 153 referenced stamps, 116 are in the store. 101 are protected as `referenced`, 11 by the owner rule (7 other game, 4 unowned); 4 (`20261006-073155`, `-073559`, `-074050`, `-075831`) are kept only as young. The audit counted them referenced because `runs/smallfix/bz/<stamp>/run-info.txt` (their own copies in `runs/`) was in its reference set; no doc names them, and the copies stay in `runs/`. With `--days 0` (`gc-dry-mac-days0.txt`) 184 runs are removable: 177 in the tier-2 list, the 3 above, and 4 newer than the audit (`20261006-220853`, `-221039`, `-221230`, `-231143`, unnamed glow-toggle and review runs). Tier 2's 208 runs today: 187 younger than 3d, 18 referenced, 1 incomplete, 1 unowned, 1 other game.
- 3.3 `blinx2 analyze && blinx2 recomp` (toolkit posix-host/portability, `regen.log`): recomp got `--seeds config/seed_functions.json`; gen/ is byte-identical to cat main's (`diff -rq`: none). The report's `observed_functions` is empty with the flag passed: none of the 30 observed seeds has a fallback site. The key is fresh after the rebase onto CLI 251fde5.
- 4.5 `enhance-check.txt`: `final-metal-attract` passes as before (both CLOSE); `final-off` FAILs "not a stock run (fx.glow=off ...)"; with `--allow-enhance fx.glow=off` it is compared (NOTE, then the frames differ, as glow-off frames do).
- 5.3 `export-diff.txt` (before: the old rules on this branch; after: the new ones): 40 changed lines, all reading "the Linux/Proton copy/queue/box/runs", "the next allowed Linux/Proton session", "The Linux/Proton host only for 7.2". Two spec lines (D5's catch-all regex, this file's identity line) stopped the export before the rules changed and were reworded; proposal item 5 was reworded so it holds no doubled article.
- 7.1 CLI: 350 passed, 1 skipped (after the review fixes); ruff clean; `audit-public.sh main..HEAD` clean; every commit authored and committed by the noreply address. cat: 27 passed; ruff clean. Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`, `blinx2 build macos`): clean, through the new stale check on the regenerated gen/.
- 7.2 `gc-dry-host.txt` (default BENCH_DIR, dry run): 67 runs, 0 removable: 66 younger than 3d (17.7 GB), 1 referenced (`20261006-015420`, by `timeline/assets/chartdata.json`); 8 unmanaged entries (122 MB). The host's oldest run is `20261006-000059`: the audit's `tier1-bench host.sh` has been run and nothing it listed is left.
- 7.3 From `wt/clihk/cat` in a scratch tree (`BENCH_DIR=~/xbox-recomp-clihk`, sharing llvm-mingw, the prefix and game_files; toolkit a0b9a55, CLI f476bfa), `bz-golden.log`: tests pass, all 8 frames EXACT or CLOSE; pruned 10/24/31 flip dumps locally (kept 3/4/7), and the host `frames/` of `20261007-071210`, `-071330` and `-071521` removed (807 MB). The local dirs hold the plain dumps, the verdict flips and the window bests, plus `pulls.txt`. `golden check` on them again (`recheck-pruned.txt`) gives the same verdict lines and passes. `golden record --only attract-cliff` from the pruned attract run into `runs/clihk/record-scratch/` records (dump 19, anchor flip 900); the real golden.json and frames are untouched. `golden --keep-frames` (`bz-golden-keep.log`) passes, says the frames are kept, and leaves 15/32/46 local pulls and the host `frames/` (211/142/334 files).
- 7.4 Fable merge review (round 3): no blocker. The fixes are on the branch: gc reads the seed and spin-wait files, `golden prune` parses as check does, the stale check compares the recorded stage extras, the export stoplist covers "itself" and the like, ASCII run names, the linked-run check in `prune_frames.sh`, `../notes/*/gc-dry*.txt` excluded, and the 1.8 counts. The export's own test is left out of the public tree, since its doubled-article case stopped the real export.
- 6.5 Note for the merge: the first `build`, `package` or `bench integrate` on the new pin is stale by construction (the `--seeds` argv, key version 2). After the merge and before the Linux/Proton integrate, run `blinx2 analyze && blinx2 recomp` on main and check gen/ is unchanged (as in 3.3).
