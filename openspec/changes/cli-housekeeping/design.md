## Context

- The CLI is `xboxrecomp-cli` (`xbr`; cat runs it as `blinx2` at the sha pinned in `game.toml [cli] commit`). The work is on CLI branch `feat/cli-housekeeping`, off main 023c77e (worktree `wt/clihk/xboxrecomp-cli`), and on cat branch `feat/cli-housekeeping`, off main 5dd464d (worktree `wt/clihk/cat`).
- The store is shared. `xbox-recomp/bench-logs/` is the only Mac store, and `cat/bench-logs` is a symlink to it (worktrees have no copy of their own; the P1 cleanup removed them). Burnout 3 runs land there too: 9 of the 340 stamp runs name `build-win/burnout3.exe`. On the host each project tree has its own `bench-logs/` (`$BENCH_DIR/<game>/bench-logs`), and `bench logs` pulls that tree into the local store, excluding `frames/` and uncapped Proton logs, and leaves the host copy.
- A run is a directory named `YYYYMMDD-HHMMSS`. Some have a suffix (`-pacing`, `-realpad-steam-ry`). Its `run-info.txt` holds:
  - the `env:` line, which includes `<input.script_env>=@scenario` and, for a golden run, `fb_dump_at=`;
  - the `<sha256>  <windows_dir>/<exe>.exe` line (every run-info since the first bench.sh);
  - the `built:  <tree>: <sha> <branch> clean|dirty` lines (from `build-win/provenance.txt`; newer runs only, and `<tree>` is the Mac worktree's folder name: `cat`, but also `irq` and `rt` for agent trees).
  In the store today: 28 referenced runs have the exe line and no tree line; 13 tier-2 runs say `irq`/`rt` with `cat_recomp.exe`; 5 runs have no run-info.txt (old ones, Mac runs, pacing reports).
- `benchlog_retention.py` already has the reference scan: stamps, plus bare HHMMSS tokens such as "golden 101239", which golden.json uses. gc reuses `STAMP_RE`, `SIX_RE`, `protection()` and `_walk_files` from it. It does not reuse `ref_paths()`, whose file set is fixed and BLiNX-shaped. benchlog-retention itself does not change.
- The disk audit's reference set (`notes/disk-audit-2026-10-06/reference-docs-scanned.txt`, 3,858 files) found 153 referenced stamps; 116 of them are still in the store. gc must protect at least those. The audit's tier-1 Mac runs are gone (0 of 647 left); its 208 tier-2 runs are all still there, and 16 runs are newer than the audit. Task 1.9 cross-checks against this state, not the audit's.
- The reference walk has a trap: `notes/cleanup-scripts/merge-actions.tsv` and `store-per-entry.json` each name 705 stamps (every run the P1 merge touched), and the audit's own `notes/disk-audit-2026-10-06/*.txt` lists name every tier-1 and tier-2 run. A gc that read them would protect everything. The audit excluded such inventories by hand; gc needs the same, in config and visible in its report (D1.3).

## D1. `bench gc`

### Command

```
<game> bench gc [--apply] [--host] [--keep N] [--days D] [--include-unowned] [--refs PATH]... [--quiet]
```

- `bench gc` lives in `bench/gc.py`. It is a bench command because it needs `Config` for `--host` (ssh, `remote_game`, the run lock). Without `--host` it never needs `BENCH_HOST`. A missing host config is an error only with `--host`.
- **Local:** the store is `<game_dir>/bench-logs`, resolved with `realpath`, so the symlink is followed once and the shared store is what gets listed. The header prints that realpath. No store there is a refusal (exit 1), not an empty listing: a worktree without the symlink must not look clean.
- **`--host`:** the controller lists `remote_game/bench-logs` through one shipped script, `host/gc_list.sh`: per stamp dir its `du -sk`, the sha256 of its run-info.txt (or `-`), whether `exit-code` exists, and the names of its files outside `frames/` (one line per file, so the pulled check in rule 6 needs no second round trip). It applies through `host/gc_apply.sh`, which runs under `flock -x -w 3600 ~/.recomp-run.lock`, like tests. A run is never in flight while gc removes runs. Exit 75 means the lock was held for an hour, and nothing was removed.
- Defaults: `--keep 3` (per scenario and kind), `--days 7`. game.toml `[bench.gc]` can change both (D1.4); cat sets `days = 3`, the audit's own tier split. Flags win over game.toml. *Why 7 in the CLI:* the default is for any game and any workflow, where a run's RESUME may be written days later; cat's docs are read from every worktree, so 3 is enough there.
- **Output:** one row per stamp run: name, owner, kind and scenario, allocated size, verdict, reason. Then totals: protected count and size by reason, removable count and size, and the loose and named entries' total (listed, never touched). Then the source report (D1.3). `--quiet` prints the totals and the source report only. The dry run says `DRY RUN: nothing removed`. Exit 0, or 2 when any removal failed.
- **Sizes:** allocated bytes (`st_blocks*512`), never `st_size`. The store holds sparse `Partition*.img` copies (audit finding: 792 GB apparent, 0 allocated). On APFS a `cp -c` clone is counted in full on both sides. The header says so: "clones are counted in full; freed space may be less". On the host the size is `du -sk` (btrfs, no reflinks: audit).

### D1.1 Which entries gc may touch

Only directories whose name *starts* with a stamp (`^\d{8}-\d{6}(-[\w.-]+)?$`) and that are not symlinks. Loose files, `_*` scratch entries and named directories (`cpu-fix`, `mac-attract`) are listed under "not managed", with their total size, and never touched. The audit removed those by hand after a fixed-string grep. Judging them needs a person, not a stamp rule.

### D1.2 Protection rules

Rules apply in order, and the first match is the reason shown. A run is removable only when no rule matches.

1. **Not ours.** Owner is read from run-info.txt's exe line, `<sha256>  <path>`:
   - it names `<build.windows_dir>/<build.exe>.exe`: ours;
   - it names another `.exe`: `other game (burnout3.exe)`, never removable, whatever the flags;
   - no run-info.txt, or no exe line: `unowned`. `--include-unowned` lets unowned runs go on to the next rules.
   The `built:  <tree>:` line is shown in the owner column when present but decides nothing: it is missing from the older run-info format and names the Mac folder (`irq`, `rt`), not the game. *Why:* the store is shared with Burnout 3. Without this rule, a gc from cat deletes every B3 run, because cat's docs never name them.
2. **Referenced.** The run's stamp, or its HHMMSS part as a bare 6-digit token, appears in the reference text (D1.3). This uses `benchlog_retention.protection()`, the same matching, including suffixed names.
3. **In flight or broken pull.** No `exit-code` file. It is reported as `incomplete (no exit-code)` and kept whatever its age: an old run without one is a pull that broke off, and the host copy (rule 6) is then its only whole copy. *Why:* a run being written, or a pull that broke off, is not settled yet.
4. **Young.** The run's stamp time is younger than D days. *Why:* a live agent may name the run in a RESUME it has not written yet (audit tier 2: "a run was still being written at 21:20").
5. **Newest N per scenario and kind.** The group key is (kind, scenario). Scenario is the last `<input.script_env>=...` value on the `env:` line, `(none)` without one. Kind is `golden` when the env has `fb_dump_at=`, `pacing` when the name has the `-pacing` suffix, else `plain`; so a scenario's plain runs never use up its golden runs' slots and a pacing report is kept beside them. The N newest of each group, by stamp time, are kept.
6. **Host only: not pulled.** A host run is removable only when the local store has the same stamp with: the same run-info.txt (sha256), an `exit-code` file, and every file name the host lists outside `frames/` and `steam-*.log` (a local `<name>.zst` or `.gz` counts for `<name>`: benchlog-retention and the P1 cleanup compress in place). Otherwise it is `not in the local store (N files missing)` and kept. `frames/` never counts: `bench logs` never pulls it and `golden` pulls only the flips it checks; Proton logs are pulled only under the cap. The host's `frames/` size is shown in the row, so the dry run says what goes with the run. *Why:* the host copy is the only one until `bench logs` has pulled it (audit: all 261 were pulled, but gc must not assume so), and a run-info.txt alone does not prove a whole pull.

On the host, rules 1-5 use the host's own run-info.txt, and the reference text is the local one. The host has no docs.

### D1.3 The reference text

The text is read from these sources, in every worktree of the game repo (`git -C <game root> worktree list --porcelain`; its first entry is the main checkout):
- `golden.json` and `audio.json` (game.toml paths);
- `TASKS.md`, `OPEN_QUESTIONS.md`, `RESUME*.md` at the root;
- every `*.md`, `*.json`, `*.txt` under `openspec/` (that covers its `RESUME-*.md` and `tasks.md`);
- each `[bench.gc] refs` path, relative to the worktree root, walked if it is a directory: files with the suffixes `.md`, `.json`, `.txt` (benchlog-retention reads `.md` only under `../notes`; `.json` and `.txt` are the shapes RESUME lists and timeline entries take). cat sets `["timeline", "../notes", "analysis", "docs", "README.md"]`;
- `[bench.gc] refs_exclude`: glob patterns relative to the worktree root; a path matching one is not read. cat sets `["../notes/cleanup-scripts/*", "../notes/disk-audit-*/*"]` (the inventories above);
- `--refs PATH`, repeatable, as in benchlog-retention, with no suffix filter.

Untracked files count. timeline/ and RESUME files are untracked in cat, and the main checkout holds them.

*Why every worktree:* an agent's unmerged RESUME or spec names its evidence runs before they reach main. The audit scanned "the live worktrees' RESUME/TASKS" for this reason.

Rules for the sources:
- The walk skips `.git`, `bench-logs`, `build*`, the pipeline's `gen` path, `third_party`, `.venv` and `node_modules`. It also skips files over 8 MiB: gen and logs are not docs, and they would make the scan slow and the HHMMSS rule protect at random. Each skipped-by-size file is named in the report.
- Missing sources. In the main checkout, every source must exist: golden.json, audio.json when game.toml sets one, TASKS.md, `openspec/` and every `[bench.gc] refs` path. One missing makes gc refuse to run (exit 1, naming it). `RESUME*.md` and `OPEN_QUESTIONS.md` may be absent (a game need not keep them; a warning). In the other worktrees a missing path is silently skipped: `../notes` resolves to `wt/<name>/notes`, which never exists. An unreadable worktree list is a refusal too. *Why refuse, not warn:* a gc with a partial reference text deletes evidence. A short protect list is worse than no gc. benchlog-retention warns; gc deletes whole runs and must not.
- **Source report**, printed after the totals: worktrees read, files read, distinct stamps, distinct HHMMSS tokens; then the files that alone protect runs (a run whose stamp or token appears in exactly one source), the ten with the most, as `<count> <path>`. An inventory that slipped past `refs_exclude` shows up here as a file protecting hundreds of runs, and the orchestrator adds it before the `!` line is built. A change in the counts between dry runs is visible.

### D1.4 game.toml

```toml
[bench.gc]
refs = ["timeline", "../notes", "analysis", "docs", "README.md"]   # default []
refs_exclude = ["../notes/cleanup-scripts/*", "../notes/disk-audit-*/*"]  # default []
keep = 3          # default 3
days = 3          # default 7
```

These go in the manifest schema as a nested table under `bench` (a new `gc` section, keys `refs` STRS, `refs_exclude` STRS, `keep` INT, `days` INT), with rows in `docs/manifest.md`. The defaults are game-agnostic. Only the paths are the game's. There is no game constant in the CLI. A `refs` path may start with `../` (it leaves the game root on purpose; the manifest's inside-the-root rule gets an exception for this key, said in the doc row).

### D1.5 Removal

- `--apply` deletes each removable run with `shutil.rmtree(..., onerror=...)` locally, and `rm -rf -- "$BENCH_LOGS/$name"` on the host. Each name is checked again against the stamp pattern on both sides, and every path is checked to be a direct child of the store's realpath. A failure is counted and reported, and the run goes on.
- gc never follows a symlink inside a run (`os.walk(followlinks=False)`; `rm -rf` does not follow).
- **Who applies.** In this workspace an agent never runs `--apply` on the real stores: auto mode denies bulk deletions, and a denial is never routed around. The orchestrator hands the user one line, `! blinx2 bench gc --apply` or `! blinx2 bench gc --host --apply`, after the dry run and its source report have been reviewed. The tests use temp stores. The host test (task 7.2) runs a dry run only.

### Alternatives considered

- **Extend benchlog-retention with `--host`.** Rejected. Its file set is fixed (`timeline/`, `../notes`), it has a global newest-N, it has no owner rule, and it is a compression tool with prune as a side option. Mixing the two would make "dry run by default" ambiguous between compress and delete. gc shares its matcher instead.
- **Age-only gc (the audit's "older than N days").** Rejected as the only rule. A referenced old run is evidence. Age is one rule of six.
- **Owner from the `built:` tree line.** Rejected as the deciding rule: 28 referenced runs have no such line and 13 name an agent folder. The exe line is in every run-info and names the game.

## D2. Golden frames pruned on PASS

- **What a run's frames are for.** Three readers:
  - `golden check` compares, per frame and reference label, the plain dump `frame_NNNN.bmp` (an unanchored frame) or the target flip `flip_<A + 60*dump + 1 - R>.bmp` (an anchored one), and reports the best of the flips within `--window` (a diagnostic; the verdict is the target's).
  - `golden record --only NAME SCEN=DIR` and `golden reference SCEN NAME LABEL DIR` read `dump_image_path(DIR, dump)`: the plain `frame_NNNN.bmp`, else `flip_<60*dump+1>.bmp`, never the anchored target. The anchor flip and the pace come from the run's `game-stdio.log`, which no prune touches. So a re-record from an old run needs the plain dump and the log, and nothing else.
  - `bench golden` pulls one plain dump per golden frame and the flips `golden pulls` lists (each target +-2), so a local run already holds only a window, 40-50 MB; the host holds the whole `fb_dump_at` window plus every 60th present, 150-230 MB a scenario.
- **The engine reports what it compared.** `golden check` gets `--used FILE`. For each scenario it writes, as `SCEN<TAB>path`:
  - `dump_image_path(DIR, dump)` for every frame of the scenario, compared or not (the re-record set);
  - every image a verdict came from: the plain dump or the anchored target flip per reference label, and the split frame's image;
  - the window's best flip, when `window_report` picked one other than the target.
  It writes one line per scenario verdict, as `SCEN<TAB>#verdict<TAB>0|1|2`, the scenario's worst rc. Nothing else in check changes.
- **`bench golden` prunes.** After the check, for each scenario with:
  - verdict 0 (EXACT or CLOSE; no INCOMPLETE, so no NEWVIEW, MISSING or pace mismatch),
  - a clean end (`check_run_end` 0, not 3),
  - no present mismatch,
  - toolkit tests passed (`trc == 0`),
  - mode `check` (never `record`, never `--force`),
  - and neither `BENCH_KEEP_FRAMES=1` nor `--keep-frames`,
  it deletes every `frames/flip_*.bmp` in that run's local dir that is not in the scenario's used set. `frame_*.bmp`, `pulls.txt` and every non-image file stay. On the host it removes `bench-logs/<stamp>/frames/` (one `rm -rf` through a shipped script, `host/prune_frames.sh`, which checks the stamp pattern and that the path is `$REMOTE_GAME/bench-logs/<stamp>/frames`). It prints `golden: SCEN: pruned N flip dumps (X MB), kept M; host frames/ removed (Y MB)`. The host removal is safe because verdict 0 proves every image the check needed was read locally, and the plain dumps are pulled before the check.
- **Why CLOSE counts as a pass.** The audit wrote "keep the full dump on FAIL/CLOSE". But frames are not bit-exact across runs by design (golden.json's `about`: title movie, idle animation and timer phase follow wall time), so nearly every scenario passes as CLOSE (the glow-toggle Proton runs: attract-title CLOSE, attract-cliff EXACT, every stage1 and story frame CLOSE). Keeping on CLOSE would prune almost nothing, and the audit's intent was the saving. What a CLOSE is inspected with is kept: the target image the verdict was judged on, the plain dump, and the window's best flip. What goes is the rest of the +-2 window, whose only use was finding that best; a wider window was never pulled, so a pruned run can do everything an unpruned local run can, except re-run `window_report` over flips that lost. Decision: prune on CLOSE.
- **Re-check invariant.** `golden check` on a pruned run gives the same verdict, the same numbers and the same window line. The kept set holds every image the verdict read, and the window search still finds the same best flip, since the others it beat are gone. `golden record --only NAME` and `golden reference` on a pruned run find their plain dump and the log. Unit tests check both (task 2.4).
- **Default ON** (audit root cause 3). `BENCH_KEEP_FRAMES` goes in the bench HELP's configuration list. `--keep-frames` is parsed like `--kill-game` in `bench.main`. On FAIL, INCOMPLETE or INCONCLUSIVE everything is kept, locally and on the host, as today: a NEWVIEW's frames are what `golden reference` records the new view from.
- **The prune is not a bulk deletion.** It removes only dumps of the run `bench golden` just made, before anything cites it; it never touches an older run. The engine's `golden prune` (next) on an existing store run is a deletion of existing data and goes to the user as a `!` line, like gc.
- **`golden prune SCEN=DIR [--dry-run]`**, an engine subcommand. It reruns the check's frame selection without printing a verdict and prunes the dir by the same rule, only when the scenario's verdict would be 0. With `--dry-run` it prints the files only. This gives Mac (Metal) runs, which are made by hand, the same cleanup. Nothing calls it automatically.

## D3. `recomp --seeds`

- `recomp_cmds` adds `--seeds <file>` for each `G.seeds` entry (game.toml `pipeline.seeds`), after `--spin-waits`. The filtered `icall_seeds.json` is not passed: it is an analyze input, and its entries carry no `observed` field.
- **Older toolkits.** A toolkit before b0eb653 rejects `--seeds` (argparse exits 2). The b3 pin may predate it. The CLI probes the toolkit checkout the pipeline already resolves: `tools/recomp/*.py` is searched once per process for `add_argument\(\s*["']--seeds["']` (the parser definition, not any mention), and the flag is passed only on a hit. Otherwise it prints, once, `recomp: the toolkit has no --seeds (before b0eb653); the observed-seed report stays empty`. The probe is cached per process.
  - *Why not `--help`:* `recomp_cmds` is not only run; `gen_key()` hashes its argv (`stage_argv`) on every `package` and, with D6, every `build` and `integrate`. A subprocess inside a key computation is the wrong shape, and a `--help` run imports the lifter. The source probe is a file read.
  - *Why not the toolkit sha:* the public fork's shas differ from the private ones (the public-toolkit map), so a sha test would be wrong for every public user.
  - *Fragility, accepted:* if upstream moves the parser out of `tools/recomp/`, the probe misses, the flag is dropped and the warning says so on every recomp. That fails safe and loud; a test with a fake toolkit dir covers both branches (task 3.2).
- **Gen key.** The flag changes `stage_argv()`, so the gen key reports "stage commands changed" once after the pin bump; the regenerate gives byte-identical gen/ (the flag only feeds the report). The proposal's Impact says what the orchestrator does with that.
- `stage_recomp`'s staleness inputs already list `G.seeds` (pipeline.py line 433), so a seed edit reruns recomp. No change there.

## D4. `[golden] enhance_stock`

- New game.toml key `golden.enhance_stock`, a table of key → stock value, both strings. Default `{}`. In the manifest schema this needs a new value type, `STRMAP` (a str→str table, validated). It gets a row in `docs/manifest.md`.
- `ENHANCE_STOCK` keeps the toolkit's keys only: `render.scale` 1, `display.aspect` 4:3, `present.pacing` spin. `fps.mode` leaves it (a BLiNX 2 key: cat `docs/env.md` lists it as a game key). The engine's table is the toolkit's keys plus the game's. A game key that repeats a toolkit key is a manifest error.
- **One pattern rule for game keys:** `\[ENHANCE\](?:.*\s)?<re.escape(key)>=(\S+)`. The `\s` before the key and the `=` after it keep `fx.glow=` from matching `fx.glow_intensity=`. The game's line is `[ENHANCE] fx.glow=on fx.glow_intensity=1` (glow-toggle 5.2). The toolkit keys keep their current regexes, so their behaviour does not change.
- **Comparison:** when both the logged and the stock value parse as floats, they are compared as floats (`"1"` equals `"1.0"`; the design of glow-toggle said `fx.glow_intensity` "compared as a float"). Otherwise they are compared as strings.
- **How the engine gets the table:** `golden_args()` adds `--enhance-stock KEY=VALUE` for each entry. `take_config` takes the flag (repeatable) and adds it to `CONFIG_FLAGS`. When the engine runs as `<game> golden` it reads the manifest directly, as `take_config` already does for the paths. `--allow-enhance` accepts any key in the combined table.
- cat game.toml: `[golden] enhance_stock = { "fps.mode" = "lock30", "fx.glow" = "on", "fx.glow_intensity" = "1" }`.
- **Commit ordering.** The manifest rejects unknown keys, so cat cannot add `enhance_stock` or `[bench.gc]` before it pins a CLI that knows them; and the new CLI without the entry would stop checking `fps.mode` for cat. So the pin bump and both entries are one cat commit. During the work, cat's branch pins the CLI branch tip (the bootstrap fetches any reachable sha). At merge the orchestrator squashes the CLI branch onto CLI main first, then re-pins cat's branch to that squash sha (one more commit on the cat branch, `pins: cli <sha>`), then squashes cat. The public push keeps the same order (CLI round before cat's), so the public `game.toml` pins a sha that exists. `scripts/test_game_pins.py` passes at each step.
- b3 has no layer and prints no `[ENHANCE]` line. It needs no entry; its pin at 023c77e keeps the old table, where `fps.mode` is harmless to it.

## D5. export-public REWRITE

The source lines stay as they are: most are in archived specs and RESUME files, and many are excluded or historical. The rules get two changes, placed after the lower-case host-name rules (lines 43-49) and before the `a Linux/Proton` catch-all (line 55), so the specific forms win.

- **Determiner rule**, before the catch-alls:
  `s/\b(the|The|a|A|every|Every|each|any|its|our|their|this|that|next allowed|allowed|same|second|one) the Linux/Proton host\b(?= [a-z])/$1 Linux\/Proton/g`
  It covers "the Linux/Proton copy" → "the Linux/Proton copy", "every Linux/Proton run" → "every Linux/Proton run", "a second Linux/Proton directory" → "a second Linux/Proton directory", and "the next allowed Linux/Proton session" → "the next allowed Linux/Proton session". "ask before taking the Linux/Proton queue" (irq-safe-points 4.4) becomes "the Linux/Proton queue". When no lower-case word follows ("the Linux/Proton host.", "the Linux/Proton host)", "the Linux/Proton host Proton prefix"), a second rule, `s/\b(the|The) the Linux/Proton host\b/$1 Linux\/Proton host/g`, gives "the Linux/Proton host". ("the Linux/Proton host Proton prefix" is tolerated; the test records it.)
  - "a"/"A" → "a Linux/Proton" stays correct ("a Linux…").
  - The existing `the Linux/Proton host (host|desktop|distrobox|bench)` rule is subsumed. It is kept above the new rule for readability, as it is the same output.
- **Sentence-start rule:** `s/(^|[.!?]\s+|\|\s*|^- )the Linux/Proton host (?=[a-z])/$1The Linux\/Proton /g` for "the Linux/Proton host tree ~/…" at the start of a line or list item, which today gives a lower-case "the Linux/Proton host tree".
- **Possessive and adjective without a determiner** ("its Linux/Proton run" is covered by `its`; a bare "the Linux/Proton host runs show") fall to the bare-word catch-all, which gives `the Linux/Proton host`. This is acceptable. The test lists the known outputs.
- **Check:** after the rewrite, the export also fails on `\bthe the\b` and `\b(every|each|any|its|allowed|second) the Linux/Proton\b` anywhere in the rewritten files. A new awkward pattern then stops the export, as a "bench host" left does. Only files the rewrite touched are checked, so pre-existing "the the" typos elsewhere do not block.
- **Test** (`scripts/test_export_public.py`): `test_rewrite_reads_well` exports a file with these phrases and asserts the exact output lines:
  - "the Linux/Proton copy",
  - "every Linux/Proton run",
  - "the next allowed Linux/Proton session",
  - "a second Linux/Proton directory",
  - "the Linux/Proton host tree ~/x",
  - "ssh <bench-host>",
  - "on the Linux/Proton host.",
  - "the Linux/Proton host",
  - "(the Linux/Proton host)",
  - "the Linux/Proton host Proton prefix".
  It also asserts that no "bench host" is left. A second case asserts that a source line producing "the the" fails the export.
- A dry run of the real tree (`scripts/export-public.sh HEAD <tmp>`) before and after is diffed. The diff is reviewed for the lines TASKS.md line 47 names. The diff output stays in `runs/clihk/` (private), never in the repo.

## D6. Stale gen/ refused

- **Consumers.** `pipeline.gen_stale_reasons()` is called by:
  - `build.build()` (`build.py:126`), right after the `recomp_funcs.h` requirement and before `refuse_while_regenerating()`. A non-empty list raises `CliError("gen/ is stale: <reasons>; run '<game> analyze && <game> recomp' (--stale-gen-ok to build anyway)")`. `build()` grows a `stale_ok` parameter; `<game> build --stale-gen-ok` sets it. `package` passes `stale_ok=True` to its own build call, because it has already regenerated or planned to (its plan's `generate` step) and a second check there would repeat the work.
  - `bench integrate` (`bench/__init__.py:400-414`), after the dirty checks and before the sync, on the local gen/ (the one the sync ships). A non-empty list is a `BenchError` with the same text, and `--stale-gen-ok` overrides, beside `--dirty`. *Why before the sync:* the 2026-10-07 integrate shipped main's pre-wrap-fix gen/ to the host and failed at link, with a duplicate `sub_0005B7D0`; the key would have named `recomp_manual.c changed` and `toolkit changed` before a byte moved.
  - `package` keeps its calls (`package/__init__.py:323, 349`).
  `bench sync` and `bench build` are not changed: a dev loop may ship a stale gen/ on purpose; `integrate` is the gate the integration branch passes through.
- **The committed half of the key.** `toolkit_state()` (`toolkit.py:65`) uses `HEAD`, so every runtime-only toolkit merge reports "toolkit changed" against the docstring's own intent ("runtime-only toolkit edits do not stale gen/"). It becomes the tree ids `git rev-parse HEAD:tools HEAD:templates/runtime`, joined (`<tools-id>+<runtime-id>`), since gen/ is made by `tools/` and written against `templates/runtime/recomp_types.h` (its macros, `RECOMP_SPIN_WAIT` among them; a template change changes what gen/ must match). The uncommitted hash widens from `tools` to `tools` and `templates/runtime` (`git diff HEAD -- tools templates/runtime` plus untracked files under both). A toolkit with no `templates/runtime` (an older checkout) gets `-` for that id. `GEN_KEY_VERSION` goes to 2, so an existing key reads as "key format changed" rather than a misleading "toolkit changed".
- **Tests** (`tests/test_cli.py`, beside `test_gen_key_staleness`), on a temp toolkit git repo:
  - a commit touching only `src/` leaves the key fresh; one touching `tools/` or `templates/runtime/` stales it ("toolkit changed");
  - `build.build()` on a stale key raises with the reasons and the hint, and runs with `stale_ok=True` (a fake cmake via the existing `d/bin` fakes of `test_bench_cli.py`'s pattern, or monkeypatching `build_tools`);
  - `bench integrate` on a stale key fails before any host call (a `Remote` whose `remote()` asserts it is never reached), and goes on with `--stale-gen-ok`;
  - the version-1 key reads as stale with "key format changed".

## Risks

- **gc deletes evidence.** Mitigations: dry run by default; the owner rule on the exe line; every worktree's docs; refusal on a missing main source or an unreadable worktree list; `refs_exclude` plus the sole-protector report against inventories; the store cross-check (task 1.9); a user-run `--apply`.
- **The HHMMSS rule over-protects.** That is the intended direction (the same as benchlog-retention).
- **Pruning removes an image someone wanted.** It only happens on a pass, on the run just made. The plain dumps and the verdict images stay; `--keep-frames` exists. The re-check and re-record invariants are tested.
- **The pin bump changes cat's stock check.** The game.toml entry lands in the same commit, and task 4.5 checks a stock run and a `RECOMP_GLOW=off` run.
- **The stale check blocks a build that was fine.** Once per toolkit bump that touches `tools/` or the templates, the user regenerates, which `package` did already; `--stale-gen-ok` covers the rest. The first build on the new pin is stale by construction (D3's argv, the key version) and the orchestrator regenerates main's gen/ at the merge.
- **A leak into the public CLI repo.** Fixtures are synthetic; host scripts and tests name no host; no image file is committed. `scripts/audit-public.sh main..HEAD` runs in the gate.
