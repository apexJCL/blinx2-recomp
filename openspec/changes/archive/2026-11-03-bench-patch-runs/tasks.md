## 1. CLI: local build and patch runs

- [x] 1.1 `BENCH_BUILD` (`local` default, `host`), `BENCH_RUN`; `remote_game` is the run directory in `local` mode.
- [x] 1.2 `bench/ship.py`: the files to ship, the local provenance (gen digest, exe sha256), `ship_prep.sh` (seed, game_files link, CLI's running_game.py), rsync itemized.
- [x] 1.3 `build`, `all`, `integrate` build locally then ship; `sync` ships; `run`, `golden`, `pacing` ship first when needed; integrate checks the gen digest before and after the build and the host's exe sha256.
- [x] 1.4 `build.sh`/`tests.sh` refuse on `~/.recomp-no-build` (exit 78); `tests` refuses in `local` mode; golden's tests are `nobuild` there; `doctor` shows the mode and the marker.
- [x] 1.5 Help text and `docs/commands.md`.
- [x] 1.6 Tests: parity cases pinned to `BENCH_BUILD=host`; local mode's calls (no host build, run dir, itemized rsync), the gen check, the sha check, the refusals.

- [x] 1.7 Review fixes (review-ITEM): every run checks the shipped exe's sha256 under the run lock (`EXPECT_SHA`, exit 76), from a hashed snapshot; the exe's directory holds exactly the shipped set (stage plus `rsync --delete`, seed without dot-files); `BENCH_GAME_FILES` defaults under the base in `local` mode; `sync --game-files` leaves it read-only and a ship refuses UDATA/TDATA in it; `setup` makes no box in `local` mode and a no-build host refuses it in `host` mode; the local build refuses while gen/ regenerates.

## 2. Hosts

- [x] 2.1 Deck: `~/xbr-bench` base (prefix and llvm-mingw, for symbolize only, seeded from `~/blx-bench`), the `~/.recomp-no-build` marker.
- [x] 2.2 Deck proof: `bench integrate --golden` from a clean main, with no compile on the Deck and only the exe and changed files sent; attract, stage1 and story pass on D3D11.
- [x] 2.3 Deck delta proof after the review fixes: a Mac-built exe with a new sha (3ae6eaaf, from 2dc4371b) into a new run directory seeded from the old one; 10.7 of 39.6 MB sent, a stale DLL `*deleting`, the seed's rsync temp file not copied; `game_files` linked to the base's read-only copy; golden attract passes (logs in `runs/bench-integrate/delta-*.log`).

## 3. Docs

- [x] 3.1 Proposed CLAUDE.md post-merge wording and `notes/benches.md` wording (`notes/bench-integrate/proposed-docs.md`).
- [x] 3.2 The Deck trees the new flow makes obsolete (`notes/bench-integrate/deck-trees.md`).

## 4. Follow-ups

- [ ] 4.1 Proton toolkit ctests from Mac-built test exes (no compile on the host). Until then they run nowhere under Proton (d3d8_hlsl_split, d3d11_backend_smoke, the input tests); the stand-in is the native Windows run. Goes in TASKS.md.
- [ ] 4.2 `bench gc --host` over whole run directories: it misses them today.
- [ ] 4.4 `logs` and `symbolize` find only the current run directory's stamps: look up a stamp across `runs/*`.
- [ ] 4.5 Ships to a shared `BENCH_RUN` take no lock: a ship during a run can replace the exe, PDB or DLLs under it (a later `symbolize` then reads a mismatched PDB). Refuse in `ship_prep.sh` while the run lock is held and the exe differs, or check the PDB too. Until then a `BENCH_RUN` belongs to one worktree.
- [ ] 4.6 A configurable ship list (`[bench]`, subdirectories included) so a texture pack (`enhance/hud.pack`) can be benched: today `--delete` removes anything placed beside the exe on the host.
- [ ] 4.3 A PC helper for the drop-in run directory, if the manual steps grow.
