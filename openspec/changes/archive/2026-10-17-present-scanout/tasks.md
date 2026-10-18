Worktrees:
- `wt/present-scanout/xboxrecomp`: toolkit, branch `fix/present-scanout` off `posix-host/portability`.
- `wt/present-scanout/cat`: this spec and the two `docs/env.md` rows, branch `spec/present-scanout` off `main`.
- No b3 branch: the race gate runs from a b3 build against the toolkit worktree (`--stale-gen-ok`, provenance note).

Raw runs go in `xbox-recomp/runs/present-scanout/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`), builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Proton runs are on the Deck with a Mac-built exe copied over, under `flock -w 3600 ~/.recomp-run.lock` (memory note *deck-proton-bench*; `blinx2 bench` takes the lock itself). BLiNX 2 first on the Deck; one agent there at a time. No tools under `tools/` change.

## 0. Spec review

- [x] 0.1 The reviewer wrote this spec, so no second read is needed before implementation; the review (5.1) covers the code. The user decides on design D1's phase 2 (the display-mode height) separately; it is not a prerequisite.

## 1. Executor: the scanout set and the eviction rule

- [x] 1.1 `s_scanout[SCANOUT_MAX = 8]` of `{ phys, last_flip }` in `nv2a_pb_exec.c` (design D2): fed from the pick at the end of `present_pick()`, LRU by `last_flip`, entries older than `present_stale_flips()` dropped, cleared where the display-mode generation changes.
- [x] 1.2 Pass 0 of the size scan accepts an entry at the display address or at a live ring entry; pass 1, the candidate loop, the staleness and field rules unchanged (design D2).
- [x] 1.3 `present_note()` eviction: LRU among unprotected entries first, protected = display address or ring entry at the display (or field) pitch; plain LRU when all are protected; `dma_resolve` only on this path (design D3).
- [x] 1.4 `PRESENT_MAX` 32.
- [x] 1.5 `RECOMP_PRESENT_TRACE`: print the ring on each traced flip; one line for the first 20 protected evictions and a count in the end-of-run present summary (design D3). Update the present block's comment (the rule as it now stands, with the B3 card as the reason).
- [x] 1.6 From a B3 Metal race run with `RECOMP_PRESENT_TRACE=1`, record in the notes the pitch and draw order of the 640x480 target at 0x0096C000 relative to the back buffer's composite (design D2); if it is ever the pick, say so in TASKS as a follow-up (preferring scanout entries among same-size candidates), not as a change here. Result: pitch 2560, drawn before the back buffer's 640x480 composite in every frame that touches it (1622/1622 in `runs/b3jitter/mac/20261015-120115-base-diag`), never the pick.

## 2. Tests

- [x] 2.1 The four CPU-path cases in `tests/nv2a_backend_smoke/smoke.c` (design D5), after the existing cases, restoring the display state at the end. One `[backend-smoke] scanout:` line each.
- [x] 2.2 Show cases 1 and 3 fail on `posix-host/portability` and all four pass on the branch; keep both outputs in the notes.

## 3. Gates

- [x] 3.1 Mac build and `tests/posix_ctest.sh <dir>`: 0 FAIL, `nv2a_backend_smoke` in the list. Summary in `runs/present-scanout/`.
- [x] 3.2 BLiNX 2 Metal goldens on the Mac (attract, stage1, story) from a cat build against the branch (`--stale-gen-ok`, provenance note): verdicts unchanged; flips/s and mean frame ms against main's last runs (45.8 / 33.4 / 54.0 flips/s), flagged at a 25% drop or 1.5x rise.
- [x] 3.3 The D4 proof on the same three scenarios, headless with `RECOMP_FLIP_LOG=1` and `RECOMP_PRESENT_TRACE=1`, main and branch: every flip on both builds is 0x00104000 or 0x00230000 at 640x480 and the eviction count is 0 (per-flip sequences diverge with run-to-run timing, a build against itself too; design D4). The diff and counts in `runs/present-scanout/`.
- [ ] 3.4 BLiNX 2 D3D11 goldens on the Deck: `blinx2 build windows` on the Mac with a provenance file, copy to `~/blx-bench/cat/build-win/`, `blinx2 bench golden`. Verdicts unchanged; flips and frame ms against bench-logs 20261015-074306 / -074426 / -074617; the `[d3d11] first present` line reads `copy`.
- [x] 3.5 Burnout 3 Metal race gate (`b3/scripts/race_gate.py`) on the Mac from a b3 build against the branch: pass, plus the dense dump across the card (design D6): every BMP in the range 640x480, count equal to the flips in the range; a contact sheet in `runs/present-scanout/b3-mac/`.
- [x] 3.6 Burnout 3 D3D11 under Proton on the Deck: the gate's `--pad-script` variant with `RECOMP_PRESENT_FULLSCREEN=1` and `RECOMP_FLIP_LOG=1`, under the run lock, from a Mac-built exe: no size change after the race load (4 changes before it, the same as base). Log and the change count in `runs/present-scanout/deck/`.
- [x] 3.7 CPU rasteriser builds (3.1 covers it); no CPU golden.

## 4. Docs

- [x] 4.1 cat `docs/env.md`: the `present_stale` row says the window also bounds the scanout set; the `RECOMP_PRESENT_TRACE` row says it prints the set and the protected-eviction count. `uv run ruff check . && uv run ruff format --check .` and `uv run pytest scripts` unaffected but run.

## 5. Review, merge, follow-ups

- [ ] 5.1 Review of the toolkit branch (and this cat branch) before the merge; fixes go back to the branch's agent.
- [ ] 5.2 Merge: toolkit and cat with `git merge --squash` (one commit each naming the branch and tip sha). Then the post-merge steps: notes to `notes/present-scanout/`, referenced runs to `runs/` with `cp -c`, worktrees removed and branches kept, the Deck `bench golden` on the merged tree.
- [ ] 5.3 TASKS.md: close the tracker item; record the gate numbers; write phase 2 (presenting the display mode's height; design D1's open items: the mode-word table, field rendering, the 320x240 crop semantics) under follow-up (f) as waiting on the user's decision; add 1.6's finding; note the upstream candidacy with the walker present series.
