# Design: bench-results-db

Paths under `src/` are in xboxrecomp-cli (read at `main` f76a9a4). The
`game.toml` path is cat's (main 750653c). `notes/` is the workspace's.
Store figures are from `bench-logs/` on 2026-10-25. The user's answers to
the first draft's questions (2026-10-25) are recorded in D17.

## D1. Inventory: what is recorded now

| Record | Where it lives | Written by | Fields |
|---|---|---|---|
| Proton run info | `bench-logs/<stamp>/run-info.txt` | `bench/host/run_game.sh:206-219` (head), `:286` (procs at +10 s), `:328-343` (tail) | `host:` uname and ISO time (the uname is **empty** on 84 Deck runs), `proton:` and prefix path, `env:`, `args:`, `limit:`, `lock:` with the wait, `<sha256>  <exe>`, `built:` lines copied from `provenance.txt` (synced or shipped, `<tree>: sha branch clean/dirty (n paths)`, `toolkit:`, `cli:`, `exe:`), `flips:` (exact from the flip trace, else a floor marked "at least", `:252-266`), `load:`, `cpu-stall:` (PSI), `busy:`, `hog:`, `top:` |
| Windows run info | the same file | `bench/host/windows/run_game.ps1:161-172,230-235` | as above, plus `os: windows (native, no Proton)` and `elapsed: Ns, game exit N`; `load:` in %; no PSI |
| Mac run info | `<out>/<stamp>-<backend>-<scen>/run-info.txt` | `golden_run.py:380-395,431-436` (`golden run`), `:804,881` (`golden play`) | `host:` node, `backend:`, `exe: <sha256> <abs path>`, `tree: <root> <sha> (n paths dirty)`, `env:` (RECOMP_* only), `limit:`, `lock:`, `load: x on N CPUs`, `stop: why at flip N after S s (max load L)`; no `built:` lines and no toolkit or CLI sha |
| Exit code | `<run>/exit-code` | `run_game.sh:294`, `golden_run.py:437` | the game's rc |
| Golden checks | `<run>/golden.txt` | `bench/golden.py:502-538` (`check_each`), `golden_run.py:594` | `end:`, `present: a/b flips mismatched`, one line per frame: `EXACT`/`CLOSE`/`FAIL`/`KNOWN`/... with name, dump, present, ref (`d3d11-windows`), MAE r/g/b, max, bad %, worst tile; `golden: pass`; last line `verdict: SCEN WORD` (`verdict_word`, `:288-308`) |
| Golden sessions | `bench-logs/golden-sessions.tsv` (34 lines) | `bench/golden.py:314-330`, appended at `:490-498` | time, kind (golden or integrate), `tests=`, `only=`, `scen=stamp:WORD`..., `rc=`, `host=posix\|windows`. There is **no game**, the host is only its OS, and Mac goldens never append |
| Rebuilt sessions | `golden-sessions.reconstructed.tsv` (42 lines) | by hand, after the 2026-10-24 overwrite | `kind=reconstructed`, `tests=unknown`, `rc=unknown`, `src=` paths. Its header says flake counts must not read it |
| Test skip key | `bench-logs/tests-pass/<key16>.txt` | `bench tests` (`bench/tests_skip.py`) | key, passed, host, dir, cli, cmake, game_src, llvm_mingw, prefix, proton |
| Game and kernel logs | `<run>/game-stdio.log`, `xbox_kernel.log`, `console.log`, `steam-default.log` (capped at 8 MiB per end, `bench/__init__.py:252-254`) | the game, the host script | the flip trace (`[GPU] flip N T ms`, `[D3D11]`/`[METAL] flip N ...`, `[PACING] flip N t_us T`) that every frame statistic is computed from |
| Frame dumps | `<run>/frames/` (17.8 GB across the store) | `RECOMP_DEBUG=fb_dump_at`/`d3d11_dump` | BMP and PNG files. A passing run is pruned to the frames the check read (`bench/host/prune_frames.sh`, golden `--keep-frames`) |
| Launch | `<run>/launch.json`, `launch.pid`, `launch.done` | Windows host | exe, cwd, env pairs |
| Topic dirs | `bench-logs/jsrf-golden/` (16 GB, 38 Mac runs), `jsrf-fps/`, `sdl3-gate8/`, `linux-native-gate8/`, `ssx3-20261018-185435/` | `golden run --out`, agents | the same run dirs, one level down |
| Build timings | `<game>/build-logs/timings.json` | `package/progress.py:258-264` (each step's duration, last value only), `:511` (`save_timing`) | `{"recomp": 614.8, "build windows (build-pkg-win)": 2.1, ...}` |
| Bench build | `<build>/bench-provenance.txt` | `bench/ship.py:198-201`, `bench/checks.py:228-240` | when, where and from which tree it was built or synced, the three tree states, the exe sha. **No duration**, no job count |
| Plain `build` | nothing | `build.py:241-308` | the jobs (`sizing.jobs`, `:308`) and the configure-or-not choice are known in the code and never written |
| Package and patch | `dist/<Name>-<date>-c<game>-t<tk>-g<gen>-o<..>[-<target>]-patch-from-<base>.{tar,dmg}`, `patch.json`, the bundle records in `.git/xbr/bundles/<target>/` | `package/__init__.py:1108,1155`, `package/patch.py:313-325` | version, base version and its manifest sha, changed, new, deleted and kept files with sizes. The sizes (`payload_size`, `full_size`, `:301-307`) are printed, never stored |
| Releases | `refs/public-tags/<tag>` and `notes/public/<slug>.map` | `public export --tag` (`public.py:623-716`) | the tag (`v2026.10.3`) points at a public commit. The map holds `<public sha> <private sha> <date>` per export round (`:713-716`), which is the only link from a release to the private game sha (and through its `game.toml`, the toolkit and CLI pins) |
| Matrix runs | `runs/bench-matrix/<scene>/<host>/<arm>/run-info.json`, `summary.json`, `summary.csv` | `bench_matrix.py:2073`, `run-arm.ps1` (`:2472`), `analyse` (`:1139-1160`) | per run: steady_fps, steady_low1_fps, steady_worst_s_fps, steady_p99_ms, hitches, stutters, slow_share, prof, disturbed |
| Pacing A/B | `bench-logs/<stamp>-pacing/` | `bench pacing`, `pacing_stats.py:1-40` | interval p5/p50/p95/max, flips/s, CPU raster p50, spin-wait CPU, vblank spread |
| Lock log | `notes/benches.md` (2148 lines) | each agent, by hand | `- <time> <host>: <who> <what> start/end, lock free` |
| Golden refs | `<game>/analysis/golden/golden.json`, `frames/` (gitignored) | `golden --record` | scenarios, seconds, min_flips, frames with limits, sha256, anchor, `known_divergence` per host. These are cited stamps, so they are pins (D11) |
| Host stores | Deck `~/xbr-bench/<game>/runs/<id>/` (and old `~/<task>-bench`, `~/blx-bench`), the Linux/Proton host `<data-drive>/xbr/<task>-bench`, PC `D:\bench\bench\<game>\runs\<task>\` and `D:\bench\<task>` | `bench ship`, agents | the shipped exe and changed runtime files, a link to (or an old copy of) the read-only `game_files` (`bench/sync.py:263`, `chmod -R a-w`) |
| Cleanup | `bench gc` (`bench/gc.py:1-25,256`, `--host` at `:421,512-534`), `benchlog-retention` (`benchlog_retention.py:1-35,130`), `notes/cleanup-derived.py` (roots `:45`, refs `:47-52`, host patterns `:53-63`) | | three rule sets over the same files. Refusals by `cleanup-derived.py` go to the user as one-line `!` commands (its header, `:28-31`) |

Who runs what. The controller is always the Mac: `bench` drives the Deck,
The Linux/Proton host and the PC over ssh, and pulls `bench-logs/` into
`<game>/bench-logs/` (`bench/__init__.py:635-682`). Stamps are made on
the controller (`:350`). `golden run` writes in place on the Mac. So
every **run** record already lands on the Mac. **Builds** do not: a build
made on the PC by a Windows session leaves nothing the Mac reads (D7.6).

Facts that shape the schema:
- `host:` is not a stable key. Counting runs at the store's top level
  only (the topic dirs hold more):
  - the Mac is `mac-a` (106) and the older `mac-b` (10);
  - the Deck is an empty uname (72), told apart only by the handheld's home
    path on the `proton:` line;
  - the PC is `PC` (24) under Windows (`os: windows`);
  - the same PC under the Linux/Proton host is `bench host` (19), and `pc` (16,
    lowercase) after the 2026-10-21 reinstall. Both carry a
    `<data-drive>/` `proton:` path.
  So the host is keyed on the OS markers first and the uname last (D12.2).
- Exes in the store: cat_recomp.exe 166 runs, skates 58 + 23 Mac,
  burnout3.exe 13, ssx3 10, cat Mac 6. The store holds several games
  (cat's and jsrf's `bench-logs` both link to it), and `bench gc` already
  sorts runs by game through the exe line (`gc.py:9-11`).
- Of the 247 run dirs with a `run-info.txt` (10 have none), 29 lack
  `built:` lines (the Mac format) and 30 lack `flips:`.
- `bench-logs/bench-logs` (dated 2026-10-15) is a dangling symlink, not a
  loop. It points to `../../../bench-logs`, which resolves to a
  `bench-logs` two levels above the workspace, a path that does not exist. It is
  left over (D12.7).

## D2. The tool: `benchdb`, a second entry point of the xboxrecomp-cli package

The user asked for "a new small CLI app" that also takes over cleanup.
It is a **standalone command, `benchdb`**, shipped in the xboxrecomp-cli
package as a second `[project.scripts]` entry next to `xbr`
(`pyproject.toml:17-18`). Its code is the module `xboxrecomp_cli/benchdb/`.

Why a separate command:
- Its scope is the **workspace**, not one game. The store, the worktrees,
  the scratchpads and the host scratch trees span every game. `xbr` is
  always run as `<game> ...` from a game dir and reads that game's
  game.toml. `benchdb` runs from anywhere under the workspace (or with
  `--config`), with no game dir and no `BENCH_HOST`.
- Its private inputs (roots, hosts, reference files) live in one local
  config file outside every repo (D3). A subcommand of `xbr` would read
  game.toml, which is public.
- It is the one deletion path, so it should be small and easy to audit:
  one module, one config, one command.

Why not its own repo or package:
- The writers (`bench`, `golden run`, `build`, `package`, `bench-matrix`)
  call the layer in-process, through `benchdb.open()`. In the same package
  there is one version and one pin: cat's `game.toml` pins the CLI sha,
  and `benchdb` comes with it. A second repo would need its own pin and
  release round and a subprocess or import shim.
- The cat bootstrap (`cat/blinx2`) already installs the package, so
  `benchdb` is on the PATH wherever `xbr` is. `uv run benchdb` works in the
  CLI checkout.

`<game> bench db VERB` stays as a thin alias. It runs `benchdb VERB --game
<slug>`, so a game session can use either form.

## D3. Configuration: public defaults, private config

- **game.toml** (public, per game) holds only game facts:
  - `[bench.db]`: `keep_releases` (default 2), `internal_keep` (default 3,
    D10), `heavy_log` (1 MiB), `hash_max`, and the regression ratios (D13);
  - `[release]`: `tag_glob` (default `v*`) and `inputs`, the paths whose
    changes make a different build (default: the `[pipeline]` and `[build]`
    paths plus `src/`, `config/`, `game.toml`'s `[toolkit]` and `[cli]`
    tables; D10).
  Defaults are in `config_defaults.py`.
- **The workspace config** (private) is `benchdb.toml`. `benchdb` takes
  `$BENCHDB_CONFIG` when it is set, else finds it by walking up from the cwd
  (the way git finds `.git`). In this workspace it is `<ws>/benchdb.toml`, a plain
  file in a directory that is not a git repo. It holds:
  - `db`: the db path (here `bench-logs/bench.db`).
  - `[roots.<name>]`: each root with `path`, `host` (`local` or an ssh
    alias), `kind`, and `deletable`.
    - Deletable kinds: `store`, `runs`, `worktrees`, `scratch`,
      `host-scratch`. Each has a `pattern` for the child names it
      may delete (D11 guard 2).
    - Reference-only kinds (`deletable = false`): `checkout` (each game
      dir, so `<build>/build-record.json`, `dist/` and the bundle records
      under `.git/xbr/bundles/` can be recorded, D7) and `notes`.
      `clean.py` only ever plans paths under deletable roots, and a test
      holds it to that.
    - `inbox` roots are written by host-side writers and emptied only by
      `pull`, by name and hash (D7.6). `clean` never plans them.
    - For a host root: `lock` (`flock` for POSIX, `bench-lock` for the PC's
      protocol, D11.4) and `df`.
  - `[never]`: paths no rule may delete even inside a root. These are the
    hosts' shared `~/xbr-bench/<game>/game_files` bases, `~/xbr-bench/prefix`,
    `<data-drive>/xbr/xbox-recomp`, Proton, llvm-mingw, and on the PC
    `D:\bench\bench\<game>` itself, its `base\`, the PC's `BENCH_GAME_FILES`
    and `D:\bench\.bench-lock`.
  - `[refs]`: extra reference paths beyond what each game gives (D11 guard
    3), for example `notes/`. `exclude` lists paths that are never refs:
    `notes/bench-db/` (the JSONL exports), `bench-logs/clean-plans/`,
    `bench-logs/clean.log` and every other output of `benchdb` itself.
    Without that, the first export would cite every stamp and pin the whole
    store.
  - `[release]`: `export_maps` (`$XBR_PUBLIC_DIR`, here `notes/public/`)
    and `toolkit_map` (`notes/public-toolkit-map/map.txt`, `<private>
    <public>` per line). Both are private, so they are not in game.toml.
  - `[hosts.<key>]`: `os`, the markers that identify it in an old run-info
    (D12.2), and `inbox` (D7.6).
  - `[games]`: the game dirs whose `game.toml`, worktrees and `bench-logs`
    it reads (cat, jsrf/skates, b3, ssx3/recomp, spartan).
- **The host-side config** on a machine that builds but holds no db (the
  PC under Windows) is two environment variables, set in the session's
  profile: `BENCHDB_HOST` (its key, `bench host-win`) and `BENCHDB_INBOX`
  (`D:\bench\benchdb-inbox`). With neither set, a writer writes only its own
  `build-record.json` in the build dir and creates nothing else. That is
  the player's case: the wizard's builds leave no inbox and no db.
- The public repo carries no copy of `benchdb.toml`. The tests use a
  fixture config with made-up roots and hosts, and the README documents the
  keys. `benchdb` without a config refuses every deletion verb and keeps
  only the query verbs.

## D4. One db, on the Mac

- The db path comes from the workspace config, so every game shares one
  db. Each row has a `game` column holding the game.toml slug. Queries
  default to the game of the cwd (if any), else all games.
- Paths in the db are `(root, relpath)`. `roots` mirrors the config's
  roots, so moving the store or reorganising it (D12) means updating one
  root or a few relpaths, never rewriting absolute paths. A path outside
  every root is refused when it is written. Roots are deletable (the
  store, `runs/`, scratch, host scratch) or reference-only (`kind =
  checkout` for each game dir, `notes`; D3). That way build and package
  records in a checkout (`<build>/build-record.json`, `dist/`,
  `.git/xbr/bundles/`) can be recorded while never being planned for
  deletion.
- Bench hosts **never open the db**. SQLite over ssh, sshfs or SMB breaks
  WAL's locking. A host's results are files (its run dir, or its inbox,
  D7.6), which the Mac pulls and then inserts.

## D5. Schema (version 1)

```sql
PRAGMA journal_mode = WAL;        -- set once at create, sticky
PRAGMA foreign_keys = ON;         -- per connection
-- PRAGMA user_version = 1        -- the schema version (D6)

CREATE TABLE roots (
  name TEXT PRIMARY KEY,           -- from benchdb.toml: 'store', 'runs', 'deck-bench'
  host TEXT NOT NULL,              -- 'local' or the ssh alias
  path TEXT NOT NULL,
  kind TEXT NOT NULL,              -- store | runs | worktrees | scratch | host-scratch |
                                   -- inbox | checkout | notes
  deletable INTEGER NOT NULL       -- 0 for checkout and notes: never planned (D11)
);

CREATE TABLE hosts (
  key TEXT PRIMARY KEY,            -- 'local' (this Mac), 'deck', 'bench host', 'bench host-win'
  os TEXT NOT NULL,                -- 'macos' | 'windows' | 'linux-proton' | 'linux-native'
  label TEXT
);
CREATE TABLE host_names (          -- what a run-info's host: line says -> key
  seen TEXT PRIMARY KEY,           -- 'mac-a', 'PC', 'mac-b'
  host TEXT NOT NULL REFERENCES hosts(key)
);

CREATE TABLE releases (            -- published versions: the work that is wrapped up
  game TEXT NOT NULL,
  tag TEXT NOT NULL,               -- 'v2026.10.3'
  published TEXT,                  -- tag date
  public_sha TEXT,                 -- the commit the public tag points at
  game_sha TEXT NOT NULL,          -- the private commit, from <slug>.map
  toolkit_pin TEXT,                -- [toolkit] commit in that game.toml (a public-fork sha)
  toolkit_sha TEXT,                -- the private sha, through [release] toolkit_map
  cli_sha TEXT,                    -- [cli] commit
  state TEXT NOT NULL,             -- published | unmapped | withdrawn (D10)
  PRIMARY KEY (game, tag)
);

CREATE TABLE builds (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL UNIQUE,       -- from its record.json (D7); import upserts on it
  game TEXT NOT NULL,
  target TEXT NOT NULL,            -- windows | macos | steamos | linux
  host TEXT REFERENCES hosts(key), -- where it was built
  cross INTEGER,                   -- 1: target OS differs from the host's (llvm-mingw on the Mac)
  exe_sha256 TEXT,                 -- NULL for a failed build or a package that only restaged
  kind TEXT NOT NULL,              -- full | incremental | package | patch | unknown
  command TEXT,                    -- 'build', 'bench build', 'bench integrate', 'package'
  started TEXT, ended TEXT, secs REAL, ok INTEGER,
  jobs INTEGER,                    -- the -j given to cmake --build
  warm TEXT,                       -- 'cold' (new build dir) | 'warm' | 'reconfigured' | NULL
  gen_fresh INTEGER,               -- 1: recomp ran (gen key changed), 0: reused
  ccache TEXT,                     -- 'off' | 'on h/m' (hits/misses) | NULL when unknown
  edges INTEGER,                   -- ninja edges run, from .ninja_log
  cpu TEXT, ncpu INTEGER, mem_gb REAL,   -- the host's figures at build time
  load_start REAL,
  game_sha TEXT, game_branch TEXT, game_dirty INTEGER,
  toolkit_sha TEXT, toolkit_branch TEXT, toolkit_dirty INTEGER,
  cli_sha TEXT, gen_digest TEXT,
  toolchain TEXT,                  -- 'llvm-mingw 20250114, cmake 3.31.2, ninja 1.12.1' (D13)
  version TEXT,                    -- the bundle version string, when packaged
  base_version TEXT,               -- patch: what it applies to
  payload_bytes INTEGER, full_bytes INTEGER,
  release TEXT,                    -- the tag it belongs to, NULL: internal (D10)
  release_match TEXT,              -- 'match' | 'stand-in' | NULL
  after_release TEXT,              -- internal: the newest tag before it
  lineage TEXT NOT NULL,           -- 'integration' | 'branch:<name>' | 'unknown'
  record TEXT                      -- relpath of its record.json
);
CREATE TABLE build_steps (
  build_id INTEGER NOT NULL REFERENCES builds(id) ON DELETE CASCADE,
  seq INTEGER NOT NULL,
  step TEXT NOT NULL,              -- 'recomp', 'configure', 'cmake --build', 'stage', 'wrap'
  secs REAL NOT NULL,
  detail TEXT,                     -- 'edges 94/2210', 'cached'
  PRIMARY KEY (build_id, seq)
);

CREATE TABLE runs (
  id INTEGER PRIMARY KEY,
  game TEXT NOT NULL,
  root TEXT NOT NULL REFERENCES roots(name),
  relpath TEXT NOT NULL,
  stamp TEXT NOT NULL,             -- YYYYMMDD-HHMMSS, the citation key
  host TEXT REFERENCES hosts(key),
  backend TEXT,                    -- d3d11 | metal | cpu | vulkan
  build_id INTEGER REFERENCES builds(id),
  kind TEXT NOT NULL,              -- golden | integrate | golden-run | run | pacing | matrix | tests
  scenario TEXT,
  started TEXT, secs REAL, limit_secs REAL,
  exit_code INTEGER, stop TEXT,
  busy INTEGER, busy_why TEXT, cpu_stall_pct REAL,
  load_start REAL, load_end REAL, ncpu INTEGER, lock_wait_secs REAL,
  stock INTEGER,
  env TEXT,                        -- normalised, local paths replaced by <root>/... (D15)
  status TEXT NOT NULL,            -- ok | partial | unparsed
  problems TEXT,
  info_sha256 TEXT,
  UNIQUE (root, relpath)
);
CREATE TABLE perf (
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  window TEXT NOT NULL,            -- 'run' | 'steady' | 'after:<anchor>'
  source TEXT NOT NULL,            -- run-info | flip-trace | pacing-stats | bench-matrix
  flips INTEGER, flips_exact INTEGER, secs REAL, flips_per_s REAL,
  ms_p50 REAL, ms_p95 REAL, ms_p99 REAL, ms_max REAL,
  hitches INTEGER, low1_fps REAL,
  PRIMARY KEY (run_id, window, source)
);
CREATE TABLE metrics (
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  name TEXT NOT NULL, value REAL, unit TEXT,
  PRIMARY KEY (run_id, name)
);

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL UNIQUE,       -- live: written by golden; TSV: game + sha256(line)
  game TEXT NOT NULL,
  kind TEXT NOT NULL,              -- golden | integrate | golden-run | reconstructed
  host TEXT REFERENCES hosts(key), backend TEXT,
  build_id INTEGER REFERENCES builds(id),
  started TEXT NOT NULL, ended TEXT,
  tests TEXT, only TEXT, rc INTEGER,
  source TEXT                      -- live | tsv | reconstructed-tsv | golden.txt
);
CREATE TABLE verdicts (
  session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  scenario TEXT NOT NULL,
  run_id INTEGER REFERENCES runs(id),
  word TEXT NOT NULL,
  PRIMARY KEY (session_id, scenario)
);
CREATE TABLE frame_checks (
  run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  frame TEXT NOT NULL, result TEXT NOT NULL, ref TEXT,
  dump INTEGER, present INTEGER,
  mae_r REAL, mae_g REAL, mae_b REAL, bad_pct REAL, tile_pct REAL,
  PRIMARY KEY (run_id, frame)
);
CREATE TABLE test_passes (
  key TEXT PRIMARY KEY, host TEXT, passed TEXT,
  cli TEXT, cmake TEXT, game_src TEXT, llvm_mingw TEXT, proton TEXT, prefix TEXT
);

CREATE TABLE artifacts (
  id INTEGER PRIMARY KEY,
  run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
  build_id INTEGER REFERENCES builds(id) ON DELETE SET NULL,
  root TEXT NOT NULL REFERENCES roots(name),
  relpath TEXT NOT NULL,
  kind TEXT NOT NULL,              -- frames | hdd | stdio-log | kernel-log | proton-log |
                                   -- console-log | run-info | golden-txt | crash-symbols |
                                   -- dump | bundle | patch | record | host-run | worktree |
                                   -- scratch | link | other
  heavy INTEGER NOT NULL,
  bytes INTEGER, files INTEGER, sha256 TEXT,
  state TEXT NOT NULL,             -- present | deleted | missing
  seen TEXT NOT NULL,
  UNIQUE (root, relpath)
);
CREATE TABLE pins (
  stamp TEXT NOT NULL,             -- a stamp, HHMMSS token, or a path under a root
  source TEXT NOT NULL,            -- 'cat/TASKS.md:812'
  refreshed TEXT NOT NULL,
  PRIMARY KEY (stamp, source)
);
CREATE TABLE deletions (           -- the journal of every delete the tool made
  id INTEGER PRIMARY KEY,
  plan TEXT NOT NULL,              -- the plan id (D11)
  at TEXT NOT NULL,
  agent TEXT,                      -- $BENCHDB_AGENT, else $USER
  root TEXT NOT NULL, relpath TEXT NOT NULL,
  bytes INTEGER, reason TEXT NOT NULL,
  result TEXT NOT NULL             -- deleted | refused:<why> | failed:<err>
);
CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);

CREATE INDEX runs_group   ON runs (game, host, backend, scenario, started);
CREATE INDEX runs_build   ON runs (build_id);
CREATE INDEX runs_stamp   ON runs (stamp);
CREATE INDEX builds_exe   ON builds (exe_sha256);
CREATE INDEX builds_rel   ON builds (game, target, release, after_release, ended);
CREATE INDEX builds_time  ON builds (game, host, target, kind, ended);
CREATE INDEX sess_game    ON sessions (game, started);
CREATE INDEX verd_run     ON verdicts (run_id);
CREATE INDEX art_run      ON artifacts (run_id);
CREATE INDEX art_state    ON artifacts (heavy, state);
CREATE INDEX pins_stamp   ON pins (stamp);
CREATE INDEX del_at       ON deletions (at);
```

Notes:
- **Keys.** Every table that import fills has a natural key, so importing
  a record twice, or pulling an inbox from two agents, adds nothing:
  `builds.uuid` and `sessions.uuid` (UNIQUE), runs by `(root, relpath)`,
  artifacts by `(root, relpath)`, verdicts by `(session, scenario)`.
  Writes upsert on those keys.
- **A run's build** is the build uuid that `bench ship` writes into the
  host run dir's provenance (`build: <uuid>`, copied into the run-info's
  `built:` lines), and that `golden run` writes for a Mac build. One exe
  sha can belong to several builds (a package and a bench build of the
  same tree, or a rebuild), so the exe sha256 is only the fallback when
  old runs are imported: there the newest build with that sha is taken.
  A run of a build no record describes gets a `builds` row with `kind = unknown`, filled from its
  `built:` lines (Proton and Windows) or its `tree:` line (Mac: game sha
  only).
- `lineage = integration` when `bench integrate` built it (main, clean
  trees, `bench/__init__.py:738-750`) or the game branch is `[bench]
  main_branch`; otherwise `branch:<game_branch>`.
- `stock` uses golden's rule (golden.json's env and `[golden]
  enhance_stock`, through `golden plan`). The regression check reads only
  stock runs.
- `frame_checks` and `verdicts` are parsed from `golden.txt`, which stays
  the source on disk, so a re-import gives the same rows.
- Dates are ISO 8601 UTC. The Windows `host:` time is local without an
  offset (`run_game.ps1:161`), so import converts it with the offset
  `bench_matrix.py:793` uses, else keeps the controller's stamp time.

## D6. Schema version and migrations

- `PRAGMA user_version` holds the version. `benchdb/schema.py` has an
  append-only `MIGRATIONS = [(1, ...), (2, ...)]`.
- `open()` reads `user_version`. If it is behind, it first makes an
  online backup (`Connection.backup`) to `db-backup/bench-pre-v<N>.db`,
  then applies each step in one `BEGIN IMMEDIATE` transaction that ends by
  setting `user_version`. A failure rolls back.
- A db newer than this CLI is opened read-only, with a message naming the
  version. An older CLI pinned by another game never downgrades it.
- A migration only adds tables, columns or indices, or rewrites derived
  rows. A destructive change is `import --rebuild` (D9): the db is rebuilt
  into a temp file, then copied into the live db with
  `Connection.backup()` under the exclusive lock. It is never swapped in
  by rename. The `deletions` journal and `releases` are copied into the
  temp db first, since disk cannot recreate them.
- Tests: every migration runs on a v1 fixture db and on an empty one, and
  the result's `sqlite_master` must equal the fresh latest schema.

## D7. The layer and its writers

The layer is stdlib only (`sqlite3`, `json`, `os`, `re`, `statistics`,
`subprocess` for ssh and git).

```
benchdb/__init__.py    open(readonly=False) -> Db; config()
benchdb/config.py      benchdb.toml (tomllib) and game.toml [bench.db]
benchdb/schema.py      DDL, MIGRATIONS, migrate(conn)
benchdb/store.py       class Db: the write and read API
benchdb/parse.py       run-info (3 formats), golden.txt, sessions TSV,
                       tests-pass, timings.json, patch.json, record.json
benchdb/record.py      record.json read and write
benchdb/releases.py    tags and the export map -> releases rows (D10)
benchdb/retain.py      the planner (pure: rows and config in, plan out)
benchdb/clean.py       guards, plan files, local and ssh deletion (D11)
benchdb/regress.py     run and build regression queries (D13)
benchdb/cli.py         the verbs (argparse)
```

API (each write is one short transaction):

```python
db = benchdb.open()                       # migrates; WAL; busy_timeout 30 s
with db.write() as w:                     # BEGIN IMMEDIATE ... COMMIT
    b = w.build(game, target, host, kind, ..., steps=[("recomp", 614.8, None), ...])
    r = w.run(game, root, relpath, stamp, host, backend, build=b, kind, scenario, ...)
    w.perf(r, window="run", source="flip-trace", flips=..., ms_p50=...)
    w.artifact(r, relpath, kind, heavy, bytes, files, sha256)
    s = w.session(game, kind, host, backend, build=b, tests, only, rc, started)
    w.verdict(s, scenario, r, word)
db.query(name, **filters) -> list[dict]
db.sql(text, params) -> list[dict]        # separate mode=ro connection
```

- Writes upsert on the UNIQUE keys (D5), so a re-import is a no-op.
- **The uuid.** Every `record.json` carries a `uuid` (`uuid.uuid4()`,
  made once by the writer, before the work starts). It is the row's key in
  the db, so the same record imported from the build dir, the inbox and a
  rebuild is one row.
- **Where records live.** Records sit beside what they describe:
  - run records in the run dir (store root);
  - build records in `<build>/build-record.json`;
  - package records next to the bundle in `dist/` and
    `.git/xbr/bundles/<target>/`.
  The last two are under the game's `checkout` root, which is
  reference-only (D3). `import --all` walks every game's build dirs and
  `dist/`, so the db can be rebuilt from them.
- `ingest_run(db, run_dir)` and `ingest_build(db, record)` are shared by
  the live writers and `import`, so there is one parser.
- A failed write (locked past the timeout, a full disk) warns once and
  never fails the bench or build command. The record file is already on
  disk, so `benchdb import` catches up later (the rule
  `golden.py:497-498` uses for the TSV).

Each writer first writes a `record.json` beside its output (the same
fields as its rows, plus the computed stats that pruning would lose, such
as the frame-interval percentiles), then calls the layer when the db is
on this machine. Elsewhere it writes to the host's inbox (6 below).

1. **`bench run`, `golden`, `integrate`** (Mac controller): after
   `cmd_logs` pulls the run (`bench/__init__.py:506,515`) and after
   `check_each` (`golden.py:528-531`). The host key is `BENCH_HOST`, not
   uname. The session row is written next to the TSV line
   (`golden.py:490-498`) for one release round (D17 Q4). `integrate`
   marks its build `lineage = integration`.
2. **`golden run` and `golden play`** (Mac): at the end of `run_one` and
   after `check_and_prune` (`golden_run.py:594`). Host `local`. One
   `golden-run` session per call.
3. **`bench pacing`, `bench tests`, `bench-matrix collect`**: run rows
   with their perf and metrics, `test_passes` rows.
4. **`build`** (`build.py:241-308`), on every host that builds (the Mac,
   the native Windows PC, cross builds of the Windows exe on the Mac):
   - each step timed: configure (when it runs), `cmake --build`, and the
     recomp when `pipeline` runs it first;
   - `jobs` (`sizing.jobs`, `:308`);
   - `warm`: `cold` when the build dir had no `CMakeCache.txt`,
     `reconfigured` on `reconfigure` or `stock`, else `warm`;
   - `gen_fresh` from the gen key (`buildstate`);
   - `edges` from the lines `.ninja_log` gained;
   - `ccache` from `CMAKE_<LANG>_COMPILER_LAUNCHER` in the cache, with
     `ccache -s` hits and misses before and after when it is set; `off`
     when it is not (true today); `NULL` when it cannot be read;
   - the host's CPU model, core count, memory and load at the start;
   - `ok = 0` and the failed step for a failed build, which still gets a
     row (a build that got slower and then broke is still a data point).
   The record goes to `<build>/build-record.json`. `bench build` and
   `integrate` (`bench/ship.py:165-202`) go through `build()`, so they are
   covered, and `ship.py:198-201` adds its provenance to the same record.
5. **`package`** (`package/__init__.py:1256-1272`): `kind = package`, or
   `patch` with `--patch-from` (base version, base manifest sha,
   `payload_size`/`full_size`, `patch.py:297-325`). Every progress step's
   `took` (`progress.py:258-264`) becomes a step, so recomp, build, stage,
   wrap and sign are each timed. `timings.json` stays as the ETA source.
   Bundles and patches become artifacts. `prune_bundles` (`:1227`, keep
   2) journals what it deletes as `deletions` rows with plan
   `package-prune`.
6. **Builds and runs away from the Mac.** A Windows session on the PC
   builds with `xbr` there, and the db is on the Mac. The writer then puts
   its `*-record.json` in the host's inbox, `[hosts.<key>] inbox` (on the
   PC `D:\bench\benchdb-inbox\`, on the Mac itself none).
   - **The host side** knows its inbox and key only from `BENCHDB_INBOX`
     and `BENCHDB_HOST` (D3). With neither set, nothing is written outside
     the build dir.
   - **Writes are atomic.** A record is written to
     `<inbox>/.<name>.tmp`, flushed, then renamed to `<uuid>.json`, so a
     pull never reads half a record.
   - **Pull.** `benchdb pull [--host KEY]` lists the inbox (names and
     sha256), copies the files over ssh or sftp (the transport
     `bench/hosts.py` and `sync.py` use) into `bench-logs/inbox/<host>/`,
     and imports them in one transaction. After the commit it deletes, on
     the host, only the files whose name and sha256 were imported. It does
     this directly with one remote command. It does not go through `clean`
     or the run lock: the young rule would refuse them, and `integrate`
     would wait up to an hour behind another agent's run. Two agents
     pulling at once is safe: the uuid makes the second import a no-op,
     and a file already deleted is skipped.
   - `bench integrate` and `bench golden` run `pull` for their host at the
     start, so records arrive whenever the PC is up on Windows; nothing
     waits for it when it is not.

## D8. Verbs: `benchdb ...` (and `<game> bench db ...`)

Data:
- `init`: create or migrate the db and load roots and hosts from the
  config.
- `import [PATH...] [--all] [--rebuild] [--dry-run]`: run dirs, both
  session TSVs, `tests-pass/`, `timings.json`, bundle records, inboxes.
  Prints rows added, updated, partial and unparsed, then each partial run
  with its reason.
- `pull [--host KEY]`: D7.6.
- `releases [--refresh]`: lists the releases per game and, with
  `--refresh`, reads the tags and the export map again (D10).
- `show RUN|BUILD|SESSION|RELEASE`.
- `query NAME [--game] [--host] [--backend] [--scenario] [--since]
  [--json|--tsv]`. Named queries:
  - `runs`, `sessions`, `flakes` (reconstructed sessions excluded);
  - `builds` (steps, jobs, warm, ccache);
  - `perf`, `series` (flips/s and p50/p95 per build over time, per group);
  - `boot` (time to the first flip per build, what `charts.py` drew from
    game logs);
  - `artifacts` (size by root, kind and state), `pins`, `orphans`,
    `deletions`.
  - `--sql "SELECT ..."` runs a read-only query.
- `regress [--build B] [--against A|--release TAG] [--host] [--backend]
  [--builds] [--strict]`: D13.
- `export (--sessions-tsv | --jsonl DIR)`. The default `DIR` is
  `notes/bench-db/`. Export refuses a target that is a pin source unless it
  is listed in `[refs] exclude`, because an export cites every stamp and
  would pin the whole store (D3, D11 guard 3).

Cleanup (D11):
- `pins [--refresh]`.
- `plan [ROOT...] [--older-than D] [PATH...]`: a dry run. It writes a
  plan file and prints it.
- `clean PLAN_ID`: deletes what that plan listed **and** a fresh plan,
  made under the locks, still allows (D11.5). It never deletes more than
  the plan listed.
- `gc`: reconciles `artifacts` with disk, runs `PRAGMA optimize`, rotates
  backups, and runs `VACUUM` when free pages are over 25%.

## D9. Concurrency and backup

- Several agents on the Mac can write at once. WAL mode means readers
  never block. Each write is one short `BEGIN IMMEDIATE` (`isolation_level
  = None`, `busy_timeout` 30 s). No transaction spans a game run, a build,
  a pull or an ssh delete.
- **A connection per write.** `db.write()` opens a connection and closes
  it after the commit. A long command (a 40 min golden) never holds one
  across the game run, so no connection outlives a rebuild. Reads open
  their own `mode=ro` connection per query.
- Whole-db operations (`import --rebuild`, migration, `VACUUM`) take
  `<store>/bench.db.lock` exclusive with `fcntl.flock`. Each `db.write()`
  takes it shared for the length of its transaction.
- **Rebuild.** `import --rebuild` builds a temp db
  (`bench-logs/bench.db.rebuild`) from the records on disk, with no lock
  held, and copies `deletions` and `releases` into it. It then takes the
  exclusive lock and copies the temp db into the live one with
  `tmp.backup(live)`. The backup API writes through SQLite's own pager and
  WAL, so the live file, its `-wal` and `-shm` stay consistent, and a
  reader sees the old or the new db, never a mix. A rename over a WAL db
  would pair the new file with the old WAL, and lose any write still
  going to the old inode. It is never the Mac's build or run lock
  (`~/.recomp-mac.lock`, `~/.recomp-mac-run.lock`).
- `clean` takes `<store>/benchdb-clean.lock` exclusive, so two agents
  never run plans at once, and on a host it also takes that host's run
  lock (D11).
- `open()` refuses a db path that is not on a local file system. Python's
  stdlib has no `statfs` on macOS, so it runs `df -l <dir>` there, which
  fails for a network mount. On Linux it reads the mount's type from
  `/proc/self/mounts` (nfs, cifs, smb3, fuse.sshfs are refused).
- Rows are never rewritten from a snapshot, so writers cannot overwrite
  each other the way the TSV was lost on 2026-10-24. A store merge (`mv
  -n`, `cp -c -n`) brings run dirs, and `import` adds their rows. The db
  is never copied over.
- Backup: the first write of each day calls `Connection.backup()` to
  `<store>/db-backup/bench-YYYYMMDD.db`, keeping 7 daily and 4 weekly
  copies (a few MB each). `export --jsonl` to `notes/bench-db/` at each
  release gives a text copy. Run dirs carry their `record.json`, so
  `import --rebuild` is the last resort for everything except the
  `deletions` journal and `releases`, which the backups and JSONL hold.
- The db, its WAL files, the locks, `db-backup/` and `inbox/` live under
  `bench-logs/`, which every game ignores (cat `.gitignore:46-47`) and no
  export or sync reads.

## D10. Versions: releases and internal builds

The user: "A version is a release on GitHub, internal iterations can be
kept temporarily but published versions are what we keep track of as
'wrapped up work'."

### Recording releases

For each game in the config, `releases --refresh` reads:
- **the tags**: the union of `refs/public-tags/<tag>` in the game repo
  (`public.py:703`) and `git ls-remote --tags <[public] remote>` matching
  `[release] tag_glob`. Only v2026.10.2 and .3 exist locally today, while
  the remote also has v2026.10.1. A tag that has disappeared from both
  (dropped by `public export --fresh-root --drop-tags`, `public.py:660,709`)
  keeps its row with `state = withdrawn` and stops counting toward
  `keep_releases`. A tag with no map line is `state = unmapped`;
- the public commit each tag points at;
- **the private game sha** for that commit, from the export map
  (`[release] export_maps`, `<public> <private> <date>`,
  `public.py:713-716`). For BLiNX 2: v2026.10.2 is `af98ca6` and v2026.10.3
  is `23cb81b`;
- **the pins** in `game.toml` at the private sha (`git show
  <sha>:game.toml`): `[toolkit] commit` and `[cli] commit`;
- **the private toolkit sha**. The toolkit pin is a public-fork sha
  (`1c434a0` at both BLiNX 2 release shas). The `[release] toolkit_map`
  turns it into the private sha (`53cc557`, `map.txt:473`). A pin with no
  map line is recorded as is, and the toolkit test below falls back to the
  tree comparison.

`public export --tag` calls `releases --refresh` for its game at its end.

### Which builds belong to a release

The release commit is usually not the commit that was benched. On
BLiNX 2, `23cb81b` is "release: pin CLI v0.10.1, changelog 2026.10.3",
made after the round's benches, and no run in the store has a `built:`
line at either release sha. Builds also record the private
`posix-host/portability` sha (`built: toolkit: d5f17ed…`), not the public
pin. So matching on commit shas never succeeds. Instead, a build B is
**matched** to release R when all of these hold:
1. **Game inputs equal.** B's game sha is R's private sha or an ancestor of
   it, B's game tree was clean, and `git diff --quiet <B> <R> --
   <[release] inputs>` is true. Commits that only touch CHANGELOG, TASKS,
   README, docs or openspec do not break the match. A pin bump does,
   because `[toolkit]` and `[cli]` are inputs.
2. **Toolkit equal.** B's toolkit tree was clean, and its sha is R's
   private toolkit sha, or `git -C <toolkit> diff --quiet <B's> <R's
   private> -- . ':!docs' ':!*.md'` is true.
3. **CLI equal.** B's CLI sha is R's `[cli] commit`, or the two differ only
   outside `src/` (the CLI's public `main` is the private one, so the shas
   compare directly).

When several builds match per (target, host), the newest `lineage =
integration` build is R's build there, and the others are marked as
matches too (`release_match = 'match'`).

**Fallback: a stand-in.** When no build of a target matches R (an old
release, a release cut without a bench, or a Mac run that lacks toolkit
and CLI shas before task 3.2), R's build there is the **newest
`lineage = integration` build of that game and target started before R's
publish date**. It is marked `release_match = 'stand-in'`. `releases` and
`regress` print the mark, so a stand-in is never mistaken for a measured
release build. A game with no release at all has no rule 1 below: only
rule 2 applies, with "since the last release" read as "ever", so its
newest `internal_keep` builds keep their large files.

**A build's time.** Builds are ordered by their parsed `started` or
`ended`, never by the text. A build with no times of its own takes the
start of its first run. That covers a run-info written before the shipped
line, which is the case for all the early runs. A run's start is its stamp
read as local time, which all the hosts share. The run-info time is used
only when the stamp does not parse. On Windows that time is naive local
time, and read as UTC it would shift the run by the zone's offset.

**Making the match the normal case:**
- `golden run` (Mac) gains `toolkit:` and `cli:` lines with tree state in
  its run-info (task 3.2), so Metal runs can match.
- The release round gains a step: after `public export --tag`, one
  `bench integrate --golden` on the exported private sha (and a Metal
  `golden run` at it). Its builds match by rule 1 with no diff, so each
  release has a measured build per host the round ran on (task 6.8).

Builds are matched again on every `releases --refresh` and every import,
so a build made before the tag is cut becomes R's build once R exists.
`builds.release`, `builds.release_match` and `builds.after_release` (the
newest release published before B started) are derived fields.
`import --rebuild` recomputes them.

### Retention, per group (game, host, backend, scenario)

1. **Release builds**: the large files of the runs of R's builds (matches
   and stand-ins) are kept for the newest `keep_releases` (default 2)
   releases that are not withdrawn: the current and the previous release.
   When a third release is cut, the oldest of the three loses its large
   files. Its rows stay forever.
2. **Internal builds**: kept until the next release, and at most the
   newest `internal_keep` (default 3) internal builds since the last
   release.
   - "Until the next release": once R+1 is published, every internal
     build after R is superseded by work that is wrapped up, so its large
     files go (after the young rule, 3 below).
   - "At most 3": between two releases there can be dozens of builds (one
     per merge and per worktree iteration). A regression check during that
     time needs the last release (rule 1) and the builds just before the
     one under test. Three covers the current build, its predecessor, and
     the last main-line integration build when the two newest are branch
     builds.
   - The newest internal build of `lineage = integration` counts as one of
     the three, but branch builds never push it out, so main always has a
     baseline.
3. **Young**: runs younger than `[bench.gc] days` (cat: 3) keep
   everything, as gc rule 4 does (`gc.py:19-20`).
4. **Pinned**: any run the reference text cites (D11 guard 3) keeps
   everything.
5. **Incomplete**: a run with no `exit-code` is never touched (gc rule 3).

A group whose scenario has not run on the newest release keeps the large
files of the two newest releases it did run on, so every scenario keeps a
baseline.

## D11. Cleanup: one deletion path that agents run themselves

The user: "Move the cleanup behavior into this new small CLI app", and
"Any way we can avoid `!` cleanup commands?" `benchdb plan` and `benchdb
clean` replace `notes/cleanup-derived.py`, `bench gc` (local and
`--host`) and `benchlog-retention`. They are the only sanctioned way to
delete derived data, and an agent runs them without asking. Guards that
are at least as strong as today's `bench gc` replace the user's `!`
review. Where the two old tools differ, the stricter rule wins.

### D11.1 The deletable roots (from `benchdb.toml`)

| Host | Root | Pattern for a deletable child |
|---|---|---|
| Mac | `bench-logs/` | a run name (`STAMP_RE` plus suffix, as gc's `RUN_RE`), a topic dir, `clean-plans/<old>`, and links |
| Mac | `runs/` | any child (age rules, guard 5) |
| Mac | `wt/` | `<name>`, removed by `git worktree remove --force`, then `rm`, then `worktree prune` in each main checkout (`cleanup-derived.py:112-126`) |
| Mac | `/private/tmp/claude-501/` | `<project>/<session>/` scratchpads only |
| Deck | `~/xbr-bench/<game>/runs/` | `<id>` |
| Deck | `~` | `<task>-bench`, `<task>-runs`, `blx-bench` |
| The Linux/Proton host | `<data-drive>/xbr/` | `<task>-bench`, `<task>-runs` |
| The Linux/Proton host | `~` | `xbox-recomp-<x>`, `xbr-<x>` (never `xbr-bench`), `xbox-recomp/rv` |
| Deck, the Linux/Proton host | `/tmp/` | `xbr-<x>`, `<task>-bench`, `<task>-runs`: no leading dot, owned by the user. The old `/tmp/<anything>` (`cleanup-derived.py:53-63`) matched `.X11-unix`, `systemd-private-*` and Steam's sockets |
| PC (Windows up) | `D:\bench\bench\<game>\runs\` | `<task>` |
| PC | `D:\bench\` | `<task>-bench`, `<task>-runs`. Never `bench`, `spartan` (the Spartan session' tree), `benchdb-inbox` or `.bench-lock` |

Inside a deletable tree:
- **Old read-only `game_files` copies** (trees made before the shared
  base, such as `~/blx-bench`) are made writable and deleted with the tree.
  This is done without ever following a link (D11.4).
- **Proton prefixes and their saves** in a bench tree (`prefix:
  <home>/blinx-sea-bench/prefix`), and a reflink `game_files` copy
  that holds `UDATA`/`TDATA` (the `bench/sync.py` comment), are derived
  test state. They go with their tree, as they do today.
- **Symlinks** are unlinked, never followed (guard 1). That covers
  `bench-logs/bench-logs`, which is not a loop: it points to
  `../../../bench-logs`, a path that does not exist.

### D11.2 What stays a user action

The tool refuses these with no override:
- anything outside the deletable roots, a root itself, and anything under
  a reference-only root (the game checkouts, `notes/`);
- the user's `~/Games` installs on the Deck and `/Applications` on the
  Mac;
- the user's play saves and configs: the play prefix and app data the
  installed games use, never a bench tree's own prefix (D11.1);
- game dumps and imports: `burnout_3/`, ISOs, each game's `game_files/`,
  and each host's shared `~/xbr-bench/<game>/game_files` base;
- the main checkouts, Proton, llvm-mingw, `~/.local/share/Steam`.

A refusal names the rule. The agent reports it to the user and never
renames, moves or relinks the path to get around it (the
`scratch-naming-no-rename` rule).

### D11.3 Guards

Each guard is checked when the plan is made and again at clean time (D11.5).

1. **Paths resolve safely.**
   - The **parent** is resolved (`realpath(dirname(path))`) and must be a
     deletable root or under one. The leaf is examined with `lstat`.
   - A leaf that is a link is only ever unlinked, wherever it points.
   - A leaf that is not a link must satisfy `realpath(leaf) ==
     realpath(parent)/name`.
   - `realpath` serves only the root check. The path that is deleted is
     always `realpath(parent)/name`, never a resolved target.
   - Remote paths: `..` is refused in the text. The host-side script
     resolves them again under the lock (D11.4).
2. **Pattern and never-paths.** The leaf name matches its root's
   pattern, and the path is not under `[never]`.
3. **Pins, failing closed.** This is gc's reference scan (`read_refs`,
   `gc.py:198-240`, and `protection`, `benchlog_retention.py:130`), moved
   into `benchdb/` and applied to every `[games]` entry:
   - **Worktrees**: the main checkout and every worktree of each game repo
     (`git worktree list`).
   - **Reference files**: in each tree, the game's `[golden] json` and
     `audio` (so jsrf's `config/golden/golden.json`, which cites the
     `jsrf-golden/` runs, protects them), `TASKS.md`, `openspec/`,
     `OPEN_QUESTIONS.md`, `RESUME*.md`, `[bench.gc] refs` less
     `refs_exclude`, the `[pipeline] seeds` files (a seed's `source` names
     its run) and `spin_waits`. Then `benchdb.toml [refs]` less its
     `exclude`.
     - `TASKS.md` and `openspec/` are read wherever they exist. They are
       required (a missing one refuses the plan) only where the repo
       tracks them, since not every game keeps them.
   - **Matching**:
     - A name with a stamp matches by the stamp, or by its bare HHMMSS
       token (gc rule 2, `SIX_RE`, `benchlog_retention.py:48`).
     - A name with no stamp matches only as a path: it must hold a `/` or
       a `\`. Examples are `runs/<topic>`, `wt/<name>`, `runs\<task>` and
       a full or `~/` path. A bare word never pins, because names like
       `ssx3`, `cli` and `bench-logs` are words of ordinary prose. As bare
       words they pinned trees that no note meant to keep.
     - The one exception is a hex name of 7 or more characters, such as a
       Deck run dir named by its build sha. It pins as a bare word, and a
       longer sha that starts with it pins it too.
     - Host paths match by their full path, from `~/` on a POSIX host, and
       by every ending of two or more parts: `runs/<x>`, `<game>/runs/<x>`,
       `xbr-bench/<game>/runs/<x>`. On Windows they also match in both
       slash forms, ignoring case. Host paths also match by each
       `bench-logs/<stamp>` inside them.
   - **Failing closed**: if any listing fails (`git worktree list`, a game
     dir) or a required file is missing in a main checkout, the whole plan
     is refused and names the file. gc does the same ("a partial reference
     text deletes evidence"), while `cleanup-derived.py` swallowed
     `OSError`.
   - **Exclusions**:
     - `benchdb`'s own outputs (the JSONL exports, the plans, `clean.log`)
       are never refs (D3).
     - Neither is a saved plan table. `benchdb plan > notes/x.txt` names
       every path it weighed, so it is skipped with a warning. A note that
       quotes one row among other text still pins.
     - `notes/benches.md` is a coordination log, not a reference, so it
       pins nothing. It is listed in `[refs] exclude` (the user,
       2026-10-25). A run worth keeping is cited in TASKS, RESUME, a
       golden or a topic note.
   - **Topic dirs kept for nested pins** (the user, 2026-10-25):
     - A topic dir whose own name nobody cites may still hold runs that a
       note cites by stamp. Such a dir keeps only those runs.
     - Each other child is planned on its own and faces every guard by
       itself: young, never-paths, its own pins, a run with no
       `exit-code`, and guard 6 for store copies. A child that holds
       pinned runs is split in the same way.
     - The topic dir is refused as "kept until empty" until its last
       child goes.
     - A topic dir cited as a whole, by a path such as `runs/<topic>` in a
       note, keeps everything in it.
     - So does a run: a dir with a stamp in its name, or with a
       `run-info.txt`, is never split. Neither is one bench's output
       dir, which holds `bench-logs/`: its `bench.log` and env files tell
       how the pinned run was made.
     - So does a topic dir that is over a never-path.
     - The first case was the fork-PR frames topic dir (11.8 G), kept for
       one nested run that a perf note cites by its HHMMSS. This text
       names neither: a design that quotes a path or stamp pins it, since
       every worktree of a game repo is read.
     - Host trees are not split yet: a host dir with a pinned stamp inside
       is still kept whole.
4. **Worktrees keep their agent's work.**
   - A worktree with uncommitted tracked changes is refused
     (`cleanup-derived.py:100-109`).
   - A worktree whose untracked, non-ignored files are not all
     byte-identical under `notes/<name>/` is also refused. The plan lists
     those files. CLAUDE.md step 5 copies agent notes there after a merge,
     so a merged worktree passes, and one whose notes were never copied
     does not.
   - `--force-dirty` remains, for the orchestrator after it has looked. It
     is a convention, not a guard: every agent shares one account, so the
     tool cannot tell agents apart.
5. **Young and in use.**
   - These are kept:
     - a run with no `exit-code`;
     - a dir whose newest mtime anywhere under it
       (`cleanup-derived.py:129-138`) is within `--older-than` (2 days
       for `runs/`, `[bench.gc] days` for the store and hosts);
     - a host run dir whose exe was shipped within `days`.
   - `bench ship` touches the host run dir it ships to. It runs before the
     run lock is taken, so this stops a clean from removing a dir that a
     queued bench just checked.
6. **Retention.** For runs in the store, D10 decides which large files go.
   Light files stay (D17 Q8). A run dir is deleted whole only when it has
   no rows that matter: an unparsed run past its age, or a topic copy
   already moved.
7. **Host runs are on the Mac first.** A host path that holds
   `bench-logs/<stamp>` dirs is deletable only when each stamp has a whole
   local copy: the same `run-info.txt` sha256, an `exit-code`, and every
   file except frames. This is gc's rule 6 (`pulled_state`, `gc.py:383`),
   moved into `clean.py`. A failed or partial pull therefore never ends
   with a lost run.

### D11.4 How a delete happens

- **Mac.** The paths are deleted in-process after the guards. A link is
  removed with `os.unlink`. A tree is made writable first: `os.walk` with
  `followlinks=False`, then `os.chmod` with `follow_symlinks=False`, and
  only on entries that are not links. Then it is removed with
  `shutil.rmtree`, which does not follow links in a tree. A worktree goes
  through git first.
- **POSIX hosts (Deck, the Linux/Proton host).** One shipped script, `clean_apply.sh`,
  is modelled on `bench/host/gc_apply.sh`:
  - it takes `flock -x -w 3600 ~/.recomp-run.lock`, as gc_apply does at
    `:6-9`;
  - per path, it resolves the parent with `realpath` and builds the
    **resolved path** `realpath(parent)/name`. That resolved path, never
    the text it was given, is what it checks against the root, `[never]`
    and the reference-only roots, and what it deletes. It also checks the
    leaf's pattern;
  - **guard 5 again, under the lock.** Each path arrives with its planned
    newest mtime. The script measures the newest mtime again (`find -P
    path -xdev -printf '%T@\n' | sort -n | tail -1`) and skips the path,
    reporting it, when that mtime has changed or is within `days`. So a
    run that `ship` touched between the plan and the lock survives;
  - a link (`[ -L ]`) is removed with `rm -f -- path`;
  - anything else gets `find -P path -xdev ! -type l -exec chmod u+w {}
    +`, then `rm -rf --one-file-system -- path`. `--one-file-system`
    keeps rm out of a bind mount inside a bench tree; `-xdev` on the chmod
    alone would not stop rm. Paths carry no trailing `/`: GNU `rm -rf
    link/` descends into the target;
  - it prints one line per path, which goes in the journal.
  - The same `chmod -R u+w` in `game_files.sh:16` and `sync.py:263`
    follows a link given as its argument. The clean script never uses it.
- **The PC (Windows).**
  - **The script.** One shipped `clean_apply.ps1`, run over ssh to
    `bench host-win`.
  - **The lock.** It takes `D:\bench\.bench-lock` with the runs' protocol
    (`run_game.ps1:30-104`):
    - `CreateNew` with the `bench` prefix text, ending in its pid and
      start time;
    - a takeover only of a stale bench lock, done in place under an
      exclusive handle;
    - deletion of the lock only while it holds the lock's text.
    So a run never takes over a lock that clean holds, and clean never
    takes over a hand-taken lock.
  - **Checks under the lock.** The same as the POSIX script: the path is
    resolved (`[IO.Path]::GetFullPath` on the parent, with the parent
    itself refused if it is a reparse point), and the resolved path is
    checked against the root, `[never]` and the reference-only roots, and
    is the one deleted. Each path carries its planned newest mtime, which
    the script measures again with the same walk as below and skips the
    path on a change or when within `days`.
  - **Deleting.** It never lets PowerShell recurse: no `Remove-Item
    -Recurse`, and no `Get-ChildItem -Recurse`, which under Windows
    PowerShell 5.1 can descend into a junction while only filtering what it
    outputs. It walks the tree by hand:
    - it lists one directory at a time with
      `[IO.Directory]::EnumerateFileSystemEntries(dir)`;
    - for each entry it reads `[IO.File]::GetAttributes` and tests
      `-band [IO.FileAttributes]::ReparsePoint`;
    - a reparse point (junction, directory symlink, file symlink) is
      deleted as a link and never entered:
      `[IO.Directory]::Delete(path, $false)` for a directory link,
      `[IO.File]::Delete` for a file link. Its read-only flag is never
      touched, so the target's attributes cannot change;
    - a plain file has its read-only flag cleared and is deleted;
    - a real directory is recursed into, then removed empty with
      `[IO.Directory]::Delete(path, $false)`.
    The tree is then gone, with no `cmd /c rmdir` needed.
  - **Tests.** The PowerShell builder is unit-tested. A fixture covers a
    junction and a directory symlink to a read-only dir **outside** the
    tree: after the clean, the target keeps its files and its read-only
    attributes.
- A plan for a host is refused when that host is down, or when the PC is
  booted into the other OS.
- **Inbox files are not cleaned here** (D7.6): `pull` deletes them
  directly, by name and hash, without the run lock.

### D11.5 Plan, then clean

- `benchdb plan` writes `bench-logs/clean-plans/<id>.json` (the time plus
  a hash) with each path's root, size, newest mtime, the rule that lets it
  go, and the refused paths with their reason. It prints this in gc's table
  style, with the total size.
- `benchdb clean <id>` takes `<store>/benchdb-clean.lock` and, for host
  roots, the host's run lock. It then makes a **fresh plan** and deletes
  only the intersection of the two:
  - pins are re-read;
  - the D10 retention decisions are recomputed (the plan file lives in a
    writable dir, so its decisions are never trusted);
  - a path whose size or newest mtime changed since the plan is skipped
    and reported;
  - the plan must be less than 1 hour old.
- **Size cap.** A plan over 100 GB, or over 20% of the root's disk, needs
  `--large`, so a wrong rule cannot empty a disk in one step.
- **Journal.** Each deleted, refused or failed path gets a `deletions` row
  and a line in `bench-logs/clean.log`. `agent` comes from
  `$BENCHDB_AGENT`, else `$USER`. That keeps the private tracker's
  variable out of the public code.
- **`--json`.** Both verbs take it, so an orchestrator can post a plan
  before it is cleaned.

### D11.6 The old tools

- **Order of work.** `cleanup-derived.py` stays the workspace's deletion
  tool until two things are true: `benchdb clean` has passed its tests and
  a first supervised run (task 6.3), and the timeline-removal item has
  landed. The timeline is still a pin source in CLAUDE.md step 6 and in
  `cleanup-derived.py`'s refs (`:72-74`) until then, and `benchdb` has no
  timeline code (D14).
- **`cleanup-derived.py`** then becomes a short wrapper that prints the
  `benchdb plan` command for its arguments and exits 2. It is removed with
  the tool once nothing calls it.
- **`bench gc` and `bench gc --host`** print the matching `benchdb plan`
  call and exit 2 for one release round, then they go (task 8.2).
- **`benchlog-retention`** goes. The names `bench/gc.py:39` imports
  (`protection`, `STAMP_RE`, `SIX_RE`) move into `benchdb/`, and
  `main.py:638,670` and `tests/test_benchlog_retention.py` go with it.
  Compressing old frames in place is replaced by deleting them under D10.
- **CLAUDE.md.** The workspace deletion rule (workflow step 6) changes
  when the tool lands. The orchestrator updates it at merge time, so it is
  not a task here.

## D12. Migrating what exists

1. **First import.** `benchdb init`, then `import --all --dry-run`. The run
   count per game is checked against `bench gc`'s listing before the old
   tools are retired.
2. **Parsers, by format.** A host is keyed on its OS markers first and its
   uname last (`[hosts.<key>] markers`, D3). The match is case-sensitive.
   - Windows: `os: windows` is `bench host-win`, the PC under Windows. Its
     uname is `PC` (24 top-level runs). `elapsed:` gives `secs`, and
     load is in %.
   - Proton: the `proton:` path picks the host.
     - `<data-drive>/` is `bench host`, the same PC under the Linux/Proton host. That
       covers the 19 `bench host` runs, and the 16 `pc` runs from after
       the 2026-10-21 reinstall.
     - the handheld's home path is `deck`, which covers the 72 runs with an empty
       uname.
     - If no marker matches, the run is `partial`, with `host unknown`.
   - Mac (`mac-a`, 106; `mac-b`, 10): `backend:`, plus `exe:` and
     `tree:` for a build that has only the game sha (`partial`). `stop:`
     gives flips and secs.
   - The counts are runs at the store's top level. Topic dirs are counted
     on their own (item 7).
   - Flip-trace stats are computed while `game-stdio.log` still exists.
   - A test covers the `pc`/`PC` pair and the empty uname.
3. **Sessions.**
   - `golden-sessions.tsv` is imported as `source = tsv`. Each line's uuid
     is the game plus the sha256 of the line (D5), so a second import adds
     nothing. Each `scen=stamp:WORD` is linked by stamp. The game comes from
     the runs' exe, and the host from the runs, because `posix` is
     ambiguous.
   - The reconstructed TSV is imported as `kind = reconstructed`.
   - Mac goldens get sessions from their `golden.txt` (`source =
     golden.txt`).
   - Both of those are left out of flakes and out of regression joins
     (D13).
4. **Builds.**
   - One build is made per distinct exe sha in the run infos, plus the
     bundle records and `patch.json`s in `dist/` and `.git/xbr/bundles/`.
     Their uuid is derived from the exe sha and the source path, so
     re-import is a no-op.
   - `timings.json` keeps only the last value per step, so it is not
     imported. Build timing starts with the first build after the tool
     lands.
5. **Releases.**
   - `releases --refresh` unions the local `refs/public-tags/` (today
     `v2026.10.2`, `.3`) with `git ls-remote --tags` (`v2026.10.1`-`.3`),
     and reads the other games' maps.
   - A tag with no map line is `unmapped`. A tag gone from both sides is
     `withdrawn` (D10).
   - Old builds are matched by D10's input rule. Where none matches, the
     release gets its stand-in.
6. **Pins.** `pins --refresh`.
7. **Layout.** The flat `bench-logs/<stamp>[-suffix]/` layout stays. Host
   scripts, `prune_frames.sh`, gc's `RUN_RE` and every citation assume it.
   - Every topic dir moves into the store root: `jsrf-golden/`,
     `jsrf-fps/`, `sdl3-gate8/`, `linux-native-gate8/` and
     `ssx3-20261018-185435/`.
     - Each run inside moves up with `mv -n`, with no clobber: a clash
       aborts that dir (the `shared-store-merge-no-clobber` rule).
     - The run's relpath and every pin that names the old path are updated
       in one transaction.
     - The pin match works by run name and stamp (D11 guard 3), so a
       citation of `jsrf-golden/<stamp>` still protects the moved run.
   - So D10 and D17 Q8 apply to them as to any run, and none of them falls
     under the `runs/` age sweep.
   - The empty topic dirs are then removed by `benchdb clean`.
   - `notes/jsrf-golden/*.sh` pass `--out bench-logs/jsrf-golden`. They
     change to `--out bench-logs` in the same step (task 6.5), or the dir
     comes back.
   - `bench-logs/bench-logs` is a dangling link: it points to
     `../../../bench-logs`, which does not exist. `benchdb clean` unlinks
     it (a `link` artifact, guard 1).
8. **Unparseable dirs.** The 10 dirs with no `run-info.txt` are imported as
   `unparsed`, with their artifacts, so their size shows. Their large files
   go after `days` unless pinned (D17 Q7).
9. **Host stores.** `benchdb plan --root deck-bench` (and the Linux/Proton host and
   PC roots) lists the old `~/<task>-bench` trees named in
   `notes/bench-integrate/deck-trees.md`. Those that are not pinned, and
   whose runs are all pulled (guard 7), go in the first clean.
10. **Other games (optional).** b3, ssx3/recomp and spartan can get a
    `bench-logs` link to the shared store, so their runs land in the same
    db. This changes those repos' layout, so it is done per game when its
    owner agrees (task 6.6). Until then, those games' `bench-logs/` dirs
    are imported as extra store roots read from `benchdb.toml`.

## D13. Regression queries

**Runs.** `benchdb regress` compares a build B (default: the newest
build of the game's integration lineage) against A. By default A is the
previous release's build in the same group: its matched build, or its
stand-in (D10). `--against` takes a build and `--release` a tag.

```sql
WITH judged AS (            -- one verdict per run, from real sessions only
  SELECT v.run_id, v.word,
         ROW_NUMBER() OVER (PARTITION BY v.run_id
                            ORDER BY s.started DESC) AS k
  FROM verdicts v JOIN sessions s ON s.id = v.session_id
  WHERE s.kind <> 'reconstructed' AND s.source <> 'golden.txt'
),
clean AS (
  SELECT r.game, r.host, r.backend, r.scenario, r.build_id,
         p.flips_per_s, p.ms_p50, p.ms_p95
  FROM runs r
  JOIN perf p ON p.run_id = r.id AND p.window = 'run'
  LEFT JOIN judged j ON j.run_id = r.id AND j.k = 1
  WHERE r.stock = 1 AND COALESCE(r.busy, 0) = 0 AND p.flips_exact = 1
    AND (j.word IS NULL
         OR j.word IN ('pass', 'pass-with-known', 'REGRESSION'))
)
SELECT ...  -- medians per (group, build) in Python (statistics.median)
```

- **The filter is a whitelist.**
  - A judged run counts only as `pass`, `pass-with-known` or `REGRESSION`.
    `REGRESSION` is an image verdict: the run itself ran to the end.
  - `FAIL-RUN`, `FAIL-PRESENT`, `MISSING`, `NEWVIEW`, `INCONCLUSIVE` and
    `INCOMPLETE` never count.
  - A run no session judged (a plain bench) counts when its exit code is 0.
  - Each run is joined to at most one verdict, from its newest session that
    was not reconstructed, so a run named by two sessions is not counted
    twice.
- **The rules.**
  - `flips` is flagged when median(B) <= 0.75 x median(A).
  - `frame-ms` is flagged when the median p50 or p95 of B is >= 1.5 x that
    of A.
  - Both are the CLAUDE.md rules. The ratios are in `[bench.db] regress`
    (`flips_drop = 0.25`, `ms_rise = 1.5`).
- **Thin data.** Each line shows n, and n = 1 is marked `(1 run)`. A group
  with no clean run of A or B shows "no baseline" or "not run". A baseline
  that is a stand-in says so.
- **Backends.** Only D3D11 and Metal are checked by default. CPU runs are
  listed, never flagged.
- **What the numbers catch.**
  - A stock run is paced at the game's rate, so flips/s catches stalls and
    slowdowns, not speedups.
  - The p95 is the sensitive figure, and the output says so once.
  - Matrix rows (`window = steady`) are checked the same way when both
    builds have them.

**Builds** (`--builds`, also printed by default after the run lines). The
user: "All builds need to start being tracked so we can see if there's
regression on how long it takes."
- **Comparable builds** share the game, host, target, kind, `warm`,
  `gen_fresh`, `jobs`, ccache on or off, and `toolchain`. `toolchain` is a
  short identity: llvm-mingw's version for Windows targets, the CLT or
  Xcode version for the Mac, the CMake and Ninja versions, and the Python
  version for `analyze`/`recomp`. A toolchain bump therefore starts a new
  baseline instead of reading as a regression.
- **What is flagged.** A warm incremental build's time depends on what
  changed, so the rule flags only work it can normalise:
  - cold and full builds (`warm = 0`, or `kind = full`), by total and per
    step;
  - `recomp`, and the standalone `analyze`, when `gen_fresh = 1`;
  - the `package` and `patch` steps;
  - incremental builds, by seconds per edge only (`secs / edges`), when the
    build ran at least `build_min_edges` (default 20) edges. Their total
    time is printed, never flagged.
- **The threshold.** A value is flagged `build-time` when it is >=
  `[bench.db] regress.build_rise` (default 1.5) x the median of the newest
  5 comparable builds before it, **and** at least `build_min_secs` (default
  30 s) longer. The floor keeps a 2 s step going to 4 s from flagging.
  Against a release (`--release TAG`), the baseline is the median of that
  release's comparable builds.
- **Thin and busy data.**
  - A comparison with fewer than 3 baseline builds is printed as `(n
    builds)` and never flagged.
  - A build whose host load at start is above its core count is marked
    `busy` and kept out of baselines, as runs are.
- **What is timed.** `blinx2 build` and `bench build` (through
  `build.build()`), `package`, `patch`, and the standalone `analyze` and
  `recomp` verbs, which are the costliest steps (task 3.3).
- **Out of scope:** `BENCH_BUILD=host` (`bench/host/build.sh`). CLAUDE.md
  forbids builds on run hosts, so it is not timed.

**Output and exit code.**
- One line per group (or step), with A, B, the ratio and the flag.
- The exit code is 0 with flags, as in `pacing_stats.py:31-33`.
  `--strict` exits 1 on a flag.
- `bench integrate --golden` runs `regress --build <the uuid it shipped>`
  after the golden and prints it, without changing golden's rc.
- `package` prints the build-time lines for its own build at the end.

## D14. The timeline is out

The user dropped the timeline from this change. The tool has no timeline
code: it reads nothing from `cat/timeline/` and exports nothing for it.

**Order of work.** The timeline still exists, and CLAUDE.md step 6 still
names it as a pin source. Until the timeline-removal item lands, its
citations must keep protecting runs. Two things do that:
- cat's `[bench.gc] refs` keeps its `"timeline"` entry, and `benchdb`
  reads it like any other ref path (guard 3). The removal item drops the
  entry together with the dir.
- `benchdb clean` replaces `cleanup-derived.py` only after that item has
  landed (D11.6, task 6.3).

The tool itself never special-cases the timeline.
What `charts.py` computed from bench data is now a query:
- `boot_runs()`, the boot chart globbing `bench-logs/2*`
  (`charts.py:207,225-228`), is `query boot`;
- `flip_rates()` and the hard-coded stamps (`:385-392`) are `query
  series`.
Removing the timeline itself is a separate item, filed by the
orchestrator.

## D15. Constraints

- **Game-agnostic code.** `benchdb/` has no game names, scenarios, hosts or
  paths. Game facts come from game.toml, workspace facts (roots, hosts,
  host name aliases, refs, never-paths) from `benchdb.toml`. Defaults are
  in `config_defaults.py`.
- **Nothing private in the public CLI repo.** The test fixtures use made-up
  hosts (`hostA`), paths (`/srv/u/...`, `X:\w\...`), shas and synthetic
  run infos in the three formats. `benchdb.toml` is never in a repo.
  `scripts/audit-public.sh` gains checks that refuse `*.db`, `*.db-wal`,
  SQLite magic bytes and a file named `benchdb.toml` in the delta.
- **The db is never published.** It stays under the ignored `bench-logs/`,
  outside every export script and every sync to a host. The `env` column
  has absolute paths replaced by `<root>/...`. `export --jsonl` goes only
  to `notes/`.
- **Stdlib only** (`dependencies = []`). Python 3.11+ gives `tomllib`. The
  bundled `sqlite3` has WAL, `backup`, the `mode=ro` URI and
  `RETURNING`.
- **Gates.** The CLI's `uv run pytest tests` and `uv run ruff check . &&
  uv run ruff format --check .`. No golden gate, since nothing the game
  runs changes (CLAUDE.md, step 3).

## D16. Tests (CLI)

- `test_benchdb_schema.py`: create, migrate from each version, refuse a
  newer db, refuse a network file system (mocked), WAL kept.
- `test_benchdb_config.py`: config discovery (cwd walk, env), missing
  config refusing the clean verbs, game.toml defaults.
- `test_benchdb_parse.py`: each run-info format (empty uname, the floor
  `flips:` line, Mac without `built:`, Windows local time), every
  golden.txt word, both TSVs with and without `host=`, tests-pass,
  patch.json, build records.
- `test_benchdb_ingest.py`:
  - re-ingest gives the same rows;
  - the same build record imported from the build dir and from the inbox,
    and the TSV imported twice, give one row each (finding 8);
  - a run linked by its shipped build uuid when two builds share an exe
    sha;
  - a locked db warns and leaves rc unchanged; two writers at once both
    land;
  - `import --rebuild` while another connection writes: no row lost, the
    WAL consistent (finding 10);
  - inbox pull with a fake ssh: a half-written `.tmp` is skipped; only
    imported, committed files are deleted, by name and hash; two pulls at
    once; no run lock taken (finding 13);
  - with no `BENCHDB_HOST`/`BENCHDB_INBOX` and no config, a build writes
    only its own record.
- `test_benchdb_parse.py` also covers the host keys: `os: windows` with
  `PC`, the `<data-drive>/` path with `pc` and `bench host`, an
  empty uname with the handheld's home path (finding 12).
- `test_benchdb_releases.py` (finding 1), against fixture repos:
  - tag and map parsing; local and remote tags unioned; an unmapped tag; a
    withdrawn tag kept and left out of `keep_releases`;
  - a release commit that only touches CHANGELOG and docs still matches the
    build benched before it;
  - a pin bump between the build and the release breaks the match;
  - a public toolkit pin translated through the toolkit map to the build's
    private sha; a toolkit that differs only in docs still matches;
  - the stand-in when no build matches, marked `stand-in`;
  - a game with no release: its newest `internal_keep` builds kept;
  - a build matched after the tag is cut; a dirty tree never matching.
- `test_benchdb_retain.py`: two releases plus internal builds, a third
  release cut, 5 internal builds since the last release (3 kept), an
  integration build older than two branch builds, pinned, young, no
  exit-code, another game.
- `test_benchdb_clean.py`, against a temp tree:
  - every refusal: outside roots, a root, `[never]`, pinned, dirty
    worktree, young, a reference-only root;
  - pins (finding 3): a run cited only in a worktree's TASKS.md; one cited
    only in jsrf's `config/golden/golden.json`; one cited only by its
    HHMMSS token; one cited by a seed's `source`; a missing required ref
    file, or a failing `git worktree list`, refusing the whole plan; a
    JSONL export under `[refs] exclude` pinning nothing (finding 4);
  - a worktree with untracked notes refused, then allowed once the same
    bytes are under `notes/<name>/` (finding 7);
  - a host run dir refused while a stamp in it lacks a whole local copy,
    allowed after the pull (finding 2);
  - symlinks (finding 5): the dangling `bench-logs/bench-logs` unlinked; a
    link to a dir inside a root unlinked with its target intact; a link out
    of the root never followed; a non-link leaf whose realpath differs
    refused;
  - patterns (finding 16): `/tmp/.X11-unix`, `/tmp/systemd-private-x` and
    a file another user owns refused; `D:\bench\bench`, `D:\bench\spartan`
    and `.bench-lock` refused;
  - a read-only `game_files` copy inside a tree removed, a read-only
    directory outside the tree refused;
  - a stale plan, a changed path skipped;
  - the `--large` threshold;
  - the journal rows;
  - `clean <id>` deleting only the intersection with a fresh plan; a
    retention decision edited in the plan file ignored (finding 18);
  - `clean_apply.sh` against a temp tree (finding 6): a link leaf `rm`'d
    and its target intact; a read-only tree with a link to a read-only dir
    inside it removed, the target dir still read-only; no trailing `/`;
    the flock taken;
  - the PowerShell builder (finding 6): the script text for a tree with a
    junction and a directory symlink deletes the links with
    `Directory.Delete(path, $false)`, walks by hand with
    `EnumerateFileSystemEntries`, never `-Recurse`; a junction to a
    read-only dir outside the tree leaves the target's files and attributes
    unchanged; a path whose mtime changed after the plan is skipped by both
    scripts; a `[never]` path reached through a link in the parent's text
    refused on its resolved path; `rm` is given `--one-file-system`; the
    `.bench-lock` text and takeover match `run_game.ps1`'s; a fixture run
    on the PC when it is up on Windows;
  - remote commands built for a fake ssh, with the lock wrapped around
    them.
- `test_benchdb_regress.py`: a 25% vs 24% drop, 1.5x vs 1.49x p95, n = 1,
  busy, non-stock left out, CPU never flagged; only `pass`,
  `pass-with-known` and `REGRESSION` counted (`FAIL-PRESENT`, `MISSING`,
  `NEWVIEW` left out); a run named by a TSV and a reconstructed session
  counted once; build steps 1.5x and +30 s vs 1.5x and +10 s, cold vs warm
  not compared, a toolchain change starting a new baseline, an incremental
  build compared by secs per edge only, fewer than 3 baselines; `--strict`.
- `test_benchdb_cli.py`: help and exit codes for every verb, `--json`,
  `query --sql` refusing a write.
- Updates to `test_golden.py`, `test_build*.py` and `test_package*.py`:
  their records and rows are written.

## D17. Decisions (the user, 2026-10-25)

1. **Version**: a published GitHub release. The current and previous
   release keep their large files. Internal builds are temporary (D10).
2. **Cleanup**: moved into the new tool. It is a standalone `benchdb`
   command in the CLI package, with private settings in a local
   `benchdb.toml` (D2, D3, D11).
3. **`bench gc` and `benchlog-retention`**: folded into `benchdb` (D11).
4. **`golden-sessions.tsv`**: written next to the db for one release
   round, then made on demand by `export --sessions-tsv`.
5. **No `!` commands**: `benchdb plan`/`clean` is the single deletion path
   that agents run themselves, over the Mac and the host scratch roots,
   with the guards in D11. What stays a user action is listed there.
6. **Builds**: every build on every host is recorded with step times, the
   job count, the warm and ccache state and the host. Build-time
   regression is checked with the perf rules (D7.4-6, D13).
7. **Unparseable runs**: imported as partial with the reason, never given
   a guessed build. Their large files go after `days` unless pinned.
8. **Small text**: parsed fields in the db. `run-info.txt` and
   `golden.txt` stay as light files that are never pruned.
9. **Timeline**: dropped from this change (D14).

The review of 2026-10-25 changed D3, D5, D6, D7, D9, D10, D11, D12,
D13, D14 and D16. None of the changes reopens a decision above; the
mapping is in the Review response below.

Questions still open, each with a default the implementation takes unless
the user says otherwise:
- `internal_keep = 3` and `keep_releases = 2` (D10). They can be changed
  in game.toml.
- The clean size threshold that needs `--large`: 100 GB or 20% of the
  disk (D11).
- The build-time flag: 1.5x the median of 5 comparable builds and at least
  30 s longer (D13).

## Review response (review, 2026-10-25)

The review read d3b5108. Each finding below maps to a fix in this revision, or a reason
it was declined.

| # | Finding | Response |
|---|---|---|
| 1 | CRITICAL: release matching never succeeds | **Fixed** in D10. Builds match on the `[release] inputs` diff, not the commit, so docs and pin-only release commits still match. The public toolkit pin goes through `[release] toolkit_map` (`1c434a0` to `53cc557`), with a fallback to the tree diff. The CLI matches outside `src/`. `release_match = 'stand-in'` covers a release with no matching build, and a game with no release keeps its newest `internal_keep` builds. `golden run` gains `toolkit:`/`cli:` lines (task 3.2), and the release round runs one integrate at the tag (task 6.8). D12.5 and D13 use the same rule. Tests in D16. |
| 2 | Host run logs deleted before the Mac has them | **Fixed**: D11 guard 7 ports gc's `pulled_state`; the test is in D16. |
| 3 | Pins weaker than gc, and fail open | **Fixed**: D11 guard 3 is gc's `read_refs`/`protection`, over every `[games]` entry and every worktree. It fails closed on a listing error or a missing required file, and keeps the HHMMSS rule. jsrf's `config/golden/golden.json` is covered through `[golden] json`. Tests in D16. |
| 4 | The JSONL export pins every run | **Fixed**: `[refs] exclude` (D3) and the export refusing a pin-source target (D8). Tested. |
| 5 | Symlink rule contradicts guard 1, and the link is not a loop | **Fixed**: guard 1 resolves the parent and `lstat`s the leaf. A link is only unlinked, and a non-link must have `realpath(leaf) == realpath(parent)/name`. D1, D11.1 and D12.7 now call `bench-logs/bench-logs` dangling. |
| 6 | Remote deletion must be one host-side script | **Fixed** in D11.4. `clean_apply.sh` runs under the flock: it re-checks the resolved path, `rm`s a link, runs `find -xdev ! -type l` before `chmod`, and never passes a trailing `/`. `clean_apply.ps1` deletes reparse points as links, never uses `Remove-Item -Recurse`, and follows the `.bench-lock` protocol with the same text. Tasks 4.2b and 4.2c. |
| 7 | Untracked agent notes lost with a worktree | **Fixed**: guard 4 refuses untracked, non-ignored files unless they are byte-identical under `notes/<name>/`. `--force-dirty` is stated to be a convention, not a guard. |
| 8 | Re-import not idempotent | **Fixed** in D5 and D7: `builds.uuid` and `sessions.uuid` are UNIQUE, with a uuid in every record.json. A TSV line's key is the game plus sha256(line). Runs link through the build uuid that `ship` writes, and the exe sha is only the import fallback. |
| 9 | Records in checkouts would be refused | **Fixed** in D3, D4 and D5: reference-only roots (`checkout`, `notes`, `deletable = 0`), never planned. Tested. |
| 10 | The rebuild swap by rename is unsafe | **Fixed** in D6 and D9: rebuild into a temp db, then `Connection.backup()` under the exclusive lock, with a connection per write. Tested. |
| 11 | Topic dirs in `runs/` fall under the 2-day sweep | **Fixed** in D12.7: every topic dir is flattened into the store, so D10 and D17 Q8 apply. The jsrf scripts' `--out` changes (task 6.4a). |
| 12 | Host identity and tag counts | **Fixed** in D1 and D12.2: hosts are keyed on `os:` or the `proton:` path first, then the case-sensitive uname. `pc` (16) is the PC under the Linux/Proton host, and the counts are top-level. Tags are the union of local and `ls-remote`, with `withdrawn` and `unmapped` states (D10). Tested. |
| 13 | The PC inbox is unspecified | **Fixed** in D3 and D7.6. The host side reads `BENCHDB_HOST`/`BENCHDB_INBOX`, and with neither set nothing is written (the player case). Writes are temp-then-rename. Pull deletes imported, committed files by name and hash, directly, without `clean` or the run lock. Tested. |
| 14 | Incremental build times are noise | **Fixed** in D13. Flagged only: cold or full builds, fresh recomp and analyze, package and patch steps, and incremental builds per edge (at least 20 edges). The toolchain is in the comparable key. Standalone `analyze`/`recomp` are timed (task 3.3), and `BENCH_BUILD=host` is out of scope, since CLAUDE.md forbids it. |
| 15 | The run filter, and duplicate verdict rows | **Fixed** in D13: a whitelist of `pass`, `pass-with-known` and `REGRESSION`, and one verdict per run from a session that was not reconstructed. Tested. |
| 16 | Host patterns too broad | **Fixed** in D11.1. `/tmp` needs a user-owned, non-dot name with the `xbr-`/`-bench`/`-runs` naming. A PC `D:\bench\<task>-bench` pattern is added. `D:\bench\bench\<game>`, its base, `BENCH_GAME_FILES` and `.bench-lock` are in `[never]`. |
| 17 | "Saves" vs bench-tree prefixes | **Fixed** in D11.1 and D11.2: bench-tree prefixes and reflink copies are derived test state. "Saves" means `~/Games` and the user's play prefix. |
| 18 | Plan-to-clean TOCTOU; ship outside the run lock | **Fixed** in D11.5. `clean <id>` deletes the intersection with a fresh plan made under the locks, and recomputes retention instead of trusting the plan file. `ship` touches the host run dir, and guard 5 refuses dirs shipped within `days`. |
| 19 | Timeline pins dropped too early | **Fixed by ordering** (D14, D11.6, task 6.3). cat's `[bench.gc] refs` keeps `"timeline"` until the removal item drops it, and `benchdb clean` replaces `cleanup-derived.py` only after that item lands. The tool itself has no timeline code. |
| 20 | Task sizing and order | **Fixed** in tasks.md. 4.2 is split into 4.2a-c. 4.4 moves `protection`/`STAMP_RE`/`SIX_RE` and removes `main.py:638,670` and `tests/test_benchlog_retention.py`. Follow-ups 8.1 (TSV) and 8.2 (gc stub) are added, along with 6.8 (release-round integrate). The missing tests are in D16, and the macOS file-system check uses `df -l` (D9). |
| 21 | Scope extras; `$PLANE_AGENT` | **Partly kept, one fix.** `query boot`/`series` stay: they replace what `charts.py` gave, and the user's decision on the timeline gives that role to `bench db` queries (D17 Q9). The regression lines in `integrate` and `package` stay: they are a few lines, and they are how the user's build-time request shows up without anyone asking. The other games' `bench-logs` links (D12.10, task 6.6) become optional, per game, with their dirs read as extra roots until then. The journal uses `$BENCHDB_AGENT` (D5, D11.5). |

### Round 2 (f05dee5)

Verdict: merge after fixes, with no third round. All four are fixed in
D11.4, task 4.2b-c and D16.

| # | Finding | Response |
|---|---|---|
| R2-1 | The PC walk contradicts itself; PS 5.1 `-Recurse` can enter a junction | **Fixed**: a manual walk with `[IO.Directory]::EnumerateFileSystemEntries`, a per-entry `ReparsePoint` test, links deleted with `Delete(path, $false)` and never entered, read-only cleared only on plain files, recursion only into real dirs. No `-Recurse` anywhere, and no `cmd /c rmdir`. A fixture with a junction to a read-only dir outside the tree checks that the target keeps its files and attributes. |
| R2-2 | The host scripts do not re-check guard 5 | **Fixed**: each path carries its planned newest mtime. Both scripts measure it again under the lock and skip the path on a change or when it is within `days`. Tested. |
| R2-3 | Delete and match on the resolved path | **Fixed**: both scripts build `realpath(parent)/name`, delete that, and match `[never]` and the reference-only roots against it, never against the text. Tested. |
| R2-4 | `rm` can cross a bind mount | **Fixed**: `rm -rf --one-file-system --`. |
