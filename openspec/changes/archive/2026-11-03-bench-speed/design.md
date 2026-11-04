## P4: verdicts kept, one-scenario reruns

`bench golden` in check mode runs `golden check` once per scenario (each
with its own `--used` file) instead of once over all of them. The compare
is the same, its output is printed as before and also written, after the
scenario's `end:`/`present:` lines, to that run's `golden.txt`, which ends
in one `verdict: SCEN WORD` line. WORD is the first of `FAIL-RUN` (crash or
early end), `FAIL-PRESENT`, `REGRESSION`, then for check's exit 2 the first of
`INCOMPLETE`, `MISSING`, `NEWVIEW` its output shows, `INCONCLUSIVE`
(slow on a busy host) or `pass`. The session line in
`bench-logs/golden-sessions.tsv` (time, `golden`/`integrate`, tests
`pass`/`skip`/`FAIL`, `only=all` or the `--only` list, `scen=stamp:WORD` for each, the exit code) is what a
flake count reads. Record mode is unchanged (one call over every dir).

`--only SCEN[,SCEN]` filters `golden plan`'s rows; an unknown name is an
error before any run. The tests still run (or skip, P2a) as for a full pass.

## P2a: tests skipped when nothing they test changed

A host script, `tests_key.sh`, prints the host's parts of the key: a
sha256 over every file of `$BENCH_DIR/xboxrecomp` (without `.git`, build
trees, venvs, caches: what sync sends), the resolved Proton (`PROTONPATH`'s
`version` file, or that of the newest
`~/.local/share/Steam/compatibilitytools.d/$PROTONPATH*`), the prefix's
`version` file, the game's `CMakeLists.txt` hash (the tests build in
build-win, which it configures) and `game_src`: a digest of the directory of
game.toml's `game.env_header` (the toolkit's `recomp_env.h` includes the
game's header) and of a `cmake/` dir, `unknown` when the named dir is gone
(review fix). The controller adds the CLI's commit (and
`-dirty`), the sha256 of the test script as shipped (prologue included, so
host paths count) and `LLVM_MINGW_TAG`, and hashes the lot. One ssh call,
under a second.

When the tests pass, the key and its parts go to
`bench-logs/tests-pass/<id>.txt`, `id` a hash of host and `REMOTE_GAME`
(each host tree has its own record; the local store is shared by every
agent's tree, so one file per tree, no shared file to race on). A golden
skips the tests when the current key equals the recorded one and says:
`tests: skipped: toolkit, CLI and Proton unchanged since the pass at
<time> (--tests runs them)`. Any part it cannot read (no Proton version)
makes the key `unknown`, which never matches. `bench tests` always runs and
records; `--tests` on `golden`/`integrate` forces the run.

What the skip gives up: a timing test that flakes on an unchanged tree is
no longer re-rolled on every golden. That is not what the golden is for;
the next toolkit, CLI or Proton change runs them again.

## P5: dump slack from the measured drift

`golden.py` anchors (`find_anchor`) over every Metal run log in `runs/`
(66-76 per scenario, 2026-10-02..09), distance of the run's anchor from the
nearest reference's anchor flip: story tsedit p90 29 max 81, slot-list p90
63, hub p90 45 max 112; stage1 first-3d p90 12 max 42 (46 in the first gate run). At 40 the story
missed 19/76 menu and 13/74 hub frames; stage1 at the default 12 missed
6/66. Story 100 leaves one hub frame; stage1 60 covers all. The runs that took another
menu path (anchors 400+ flips off) are excluded: no slack fixes those.
Cost: one more dumped BMP per flip of slack per anchored frame until the
prune.

## P9

`set_property(SOURCE ${RECOMP_GEN_SOURCES} APPEND PROPERTY COMPILE_OPTIONS
-Wno-parentheses-equality)` for Clang only (GCC has no such warning). Host
code keeps the warning.

## P3: `golden run`

`<game> golden run [SCEN...] [--backend metal|cpu] [--secs S] [--out DIR]
[--keep-frames] [--lock-wait S] [VAR=val...]`, in the golden engine (stdlib;
the game's paths from game.toml). Per scenario:

1. Environment: the process environment without inherited `RECOMP_*`, then
   `golden plan`'s env for the scenario, `RECOMP_PB_BACKEND` = the backend,
   `RECOMP_HEADLESS=1`, `SDL_AUDIODRIVER=dummy`, `RECOMP_SAVE_DIR=@run` ->
   the run's `save/`, `RECOMP_DEBUG` += `fb_dump=<run>/frames/,fb_dump_at=<dumpat>`,
   then the `VAR=val` arguments (`RECOMP_TRACE`/`RECOMP_DEBUG` add up).
2. Lock: `~/.recomp-mac-run.lock` with `notes/mac-run-lock.sh`'s protocol
   (mkdir, `pid`, `cmd`, a dead holder's lock taken over, waits up to an
   hour, exit 75). A lock held by an ancestor process (the script wrapping
   this command) counts as held.
3. Load: before each run, a 1-minute load average above 0.75 x CPUs, or a
   game process already running, prints a WARNING (and goes in run-info).
   The run goes ahead: the pace check turns a slowed run into INCOMPLETE,
   and the warning says why.
4. Stop: the log is read as it grows. Each frame needs its flip
   `60*dump+1` (+ window); an anchored frame, once its anchor is in the log,
   needs `A + 60*dump+1 - R` (+ window) for each reference, at most its
   `dumpat` range end; before the anchor, the range end. The run gets
   SIGINT when the last flip seen is 3 past the largest need, or at `--secs`
   (default 2x the scenario's seconds), or ends by itself.
5. Check and prune as `bench golden`: `golden.txt` with the verdict line,
   `exit-code`, frames pruned on a pass unless `--keep-frames`.

Run dirs: `<game root>/bench-logs/<stamp>-<backend>-<scen>/` (the one
store). Exit 1 on any FAIL or a crash/early end, else 2 on any INCOMPLETE,
else 0.
