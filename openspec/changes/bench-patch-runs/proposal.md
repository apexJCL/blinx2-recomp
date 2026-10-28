## Why

`blinx2 bench integrate --golden` syncs the sources to the bench host and
compiles `build-win/` there. The post-merge run on 2026-10-23 built
94 objects in `~/blx-bench` on the Deck. The user's rule (2026-10-16, again
2026-10-23): "Both the Mac and windows can build - the deck never". Every
post-merge integrate has broken it, since CLAUDE.md names this command.

Every agent also keeps its own full copy of the sources on the Deck
(`~/<task>-bench`, 0.3 to 53 GB each, 30 trees on 2026-10-23), only to drop
a Mac-built exe into its `build-win/`. The user approved the patch model on
2026-10-23.

## What Changes

- **Build here, ship the exe (CLI).** A new `BENCH_BUILD` setting, `local`
  by default: `bench build`, `all` and `integrate` build the Windows exe on
  the controller (the Mac's llvm-mingw cross-build, or a native build on
  the Windows PC), exactly as `<game> build windows` does, and then ship it.
  `BENCH_BUILD=host` keeps the old sync-and-compile path for a host that
  may build.
- **Patch runs (CLI).** A ship sends only the exe, its PDB,
  `config.default.toml` and any DLL beside the exe, plus a provenance file,
  to a run directory of its own on the host:
  `$BENCH_DIR/<game>/runs/<id>/`. The id is the exe's sha256 (12 hex) or
  `BENCH_RUN`. A new run directory is seeded on the host from the newest
  one, and rsync sends only the files whose checksums differ, as deltas.
  The run directory links the host's single `game_files/` copy, keeps its
  own `bench-logs/`, and every run, golden, pacing, logs and symbolize step
  works in it. `run`, `golden` and `pacing` ship first when the local exe
  is not on the host yet.
- **No compile on a no-build host (CLI).** A host carries the marker file
  `~/.recomp-no-build`. `build.sh` and `tests.sh` refuse to start on such a
  host (exit 78). In `local` mode `bench tests` refuses, and golden's
  toolkit ctests are skipped as `nobuild`, since they compile on the host.
- **Kept:** the gen/ digest check, which is now made locally: the digest
  before and after the build must match, and it goes into the shipped
  provenance. integrate then reads back the host's exe sha256 and
  provenance, and the sha256 must equal the local exe's. The
  toolkit/game/CLI sha report is unchanged.
- **The PC (docs).** The PC keeps one bench base per game,
  `D:\bench\bench\<game>\base\`, a one-time copy of the unpacked Windows
  package. A test drops only its exe (and changed runtime files) into
  `D:\bench\bench\<game>\runs\<task>\`, which links the base's `game_files`
  and uses a data dir of its own. No more copies of the installed app per
  task.
- **The Deck (host setup).** One base, `~/xbr-bench`, for every game:
  `prefix/`, `llvm-mingw/` (for symbolize only), `xboxrecomp-cli/` (for
  `running_game.py`), and `<game>/runs/`. Its `~/.recomp-no-build` marker
  is in place.

## Impact

- CLI: `bench/__init__.py`, `bench/config.py`, the new `bench/ship.py`,
  `host/build.sh`, `host/tests.sh`, the new `host/ship_prep.sh`,
  `host/doctor.sh`, the help text and `docs/commands.md`, and tests.
- cat: this spec. Each worktree's `scripts/bench.env` (ignored) points
  `BENCH_DIR` at `~/xbr-bench`.
- Workspace docs: CLAUDE.md's post-merge step and `notes/benches.md` get
  new wording. It is proposed in `notes/bench-integrate/proposed-docs.md`,
  and the orchestrator applies it.
- Not covered here: the Proton toolkit ctests on a no-build host. They
  compile in the host's `build-win/`. Running them from Mac-built test
  exes is a follow-up (4.1). Until then nothing runs them under Proton;
  the stand-in is the native Windows run.
