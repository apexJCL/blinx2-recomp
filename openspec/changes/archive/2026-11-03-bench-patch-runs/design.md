## Context

`bench` (CLI `bench/`) drives a Linux host over ssh. Every host script
starts with `cd "$REMOTE_GAME"`, runs `$EXE_REL` (`build-win/<exe>.exe`)
under umu-run, finds `game_files/` relative to its working directory, and
writes `bench-logs/<stamp>/`. Up to now `REMOTE_GAME` was
`$BENCH_DIR/<game>`: a full rsync of the game's sources, compiled in place.

## Decisions

1. **The run directory is the new `REMOTE_GAME`.** In `local` mode,
   `REMOTE_GAME` is `$BENCH_DIR/<game>/runs/<id>`, where `<game>` is
   `[bench] remote_name` or else the game's slug (not the checkout's
   basename), so every worktree of a game shares one base. The host scripts
   (run_game, symbolize, prune_frames, integrate_show) and the
   controller's log and frame pulls keep working without change. Each
   exe gets its own directory, logs and provenance, so two agents never
   overwrite each other's exe between a ship and a run. The run lock
   still keeps their runs from overlapping.
2. **The id is content-addressed by default.** It is the first 12 hex
   digits of the local exe's sha256, so `bench golden` in any worktree
   resolves to that worktree's own build without any shared "current"
   pointer. `BENCH_RUN` (`[A-Za-z0-9._-]+`) names it instead for a
   long-lived job.
3. **Only changed bytes move.** `ship_prep.sh` seeds a new run
   directory's `build-win/` from the newest other run directory with a
   host-local copy. rsync then runs with `--checksum -i --info=stats1`,
   so the log lists each file that differed and the literal against the
   matched bytes. The shipped set is staged in one directory and sent
   with `--delete`, so the run's `build-win/` holds exactly that set (the
   seed's stale PDB, DLL or rsync temp file goes). game_files is a symlink
   to `BENCH_GAME_FILES` (default `$BENCH_DIR/<base>/game_files`), never a
   copy. `sync --game-files` leaves it read-only, and a ship refuses it
   with `UDATA`/`TDATA` inside: the runtime keeps saves in the game
   directory when those exist, so one run would change what the next reads.
   Saves otherwise go to local app data in the shared prefix, as before.
4. **The build is the controller's own `build windows`.** The local build
   goes through `build.build("windows", ...)`, with the bench's game and
   toolkit made current, as `gen_stale_reasons` does. It is the same
   build tree (`build-win/`), cache and toolchain the developer uses on
   the Mac, or a native build when the CLI runs on the Windows PC. Nothing
   in the CLI names a host or a game. The local build adds no lock: the
   workspace's Mac lockf wraps the command, as for any heavy job.
5. **The gen/ check moves to the controller.** The gen/ digest is taken
   before and after the build (a regeneration mid-build fails the
   integrate) and written into the shipped `provenance.txt` with the
   exe's sha256. integrate reads back the host's sha256 of the exe and
   fails on any difference. Every run checks it too: `run`, `golden` and
   `pacing` build nothing, ship a hashed snapshot of the local exe, and
   `run_game.sh` compares the run directory's exe with that sha256 under
   the run lock (`EXPECT_SHA`, exit 76), so a run never starts another
   ship's exe. The local build refuses while a recomp regenerates gen/.
6. **No-build is a host property, kept on the host.** A marker file,
   `~/.recomp-no-build`, sits on the host. `build.sh` and `tests.sh`
   check it first and exit 78, and `setup_box.sh.in` refuses the build
   box the same way (`local` mode's `setup` makes none). So any controller, any CLI version
   carrying this change and any agent's `bench.env` is refused there,
   with no setting to forget. `doctor` prints it.
7. **`BENCH_BUILD=local` is the default.** Every Proton host in this
   workspace (the Deck) is a no-build host. The host path stays for a
   box that may build (`BENCH_BUILD=host`). The bench.sh parity
   record pins it.
8. **ctests.** These are the toolkit's Proton ctests, compiled with
   `CMAKE_CROSSCOMPILING_EMULATOR` in the host's `build-win/`. In
   `local` mode golden reports them as `tests=nobuild`, the status it
   already uses for a tree with no configured `build-win/`.
   `bench tests` refuses with a reason. Shipping cross-built ctest
   binaries is a follow-up.

## The PC (no CLI change)

PC runs are started by the user, so this part is a convention in
`notes/benches.md`. Base: `D:\bench\bench\<game>\base\`, one unpacked
Windows package (`game_files\`, launcher, `config.default.toml`), made
once per game and refreshed only when the game files change. Run:
`D:\bench\bench\<game>\runs\<task>\` holds the test exe (and changed
runtime files), a directory junction `game_files` to the base's
(`mklink /J`, which needs no admin rights), and `<dir_env>` (for example
`BLINX2_DATA_DIR`) pointing at `runs\<task>\data`. The player's
`%LOCALAPPDATA%` config and saves are never touched.

## Risks

- The run directories accumulate. They are small (exe, PDB, logs), and
  `cleanup-derived --host deck` removes them like any other scratch.
  Host-side `gc` of whole run directories is a follow-up.
- A worktree that rebuilds without shipping makes `run` ship first. A
  stale exe can't be run by accident under a new sha.
