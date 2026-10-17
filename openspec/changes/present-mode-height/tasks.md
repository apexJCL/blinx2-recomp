Worktrees:
- `wt/present-mode-height/xboxrecomp`: toolkit, branch `fix/present-mode-height` cut from `fix/present-scanout`'s tip (phase 1; 2a142d7 when this was written, re-cut if phase 1 moves before this starts).
- `wt/present-mode-height/cat`: this spec and the `docs/env.md` rows, branch `spec/present-mode-height` off `spec/present-scanout`.
- No b3 branch: the race gate runs from a b3 build against the toolkit worktree (`--stale-gen-ok`, provenance note).

Raw runs go in `xbox-recomp/runs/present-mode-height/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`), builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Proton runs are on the Deck with a Mac-built exe copied over, under `flock -w 3600 ~/.recomp-run.lock` (memory note *deck-proton-bench*; `blinx2 bench` takes the lock itself). BLiNX 2 first on the Deck; one agent there at a time. No tools under `tools/` change. The xbe-derived table extraction (design D1) and its output stay in the worktree's notes, then `notes/present-mode-height/`; never in a public repo.

## 0. Spec review

- [x] 0.1 Fable wrote this spec, so no second read is needed before implementation; the Opus review (5.1) covers the code. Phase 1 (`present-scanout`) must be merged, or at least frozen at the tip this branch is cut from, before 4.x runs.

## 1. Kernel: the display mode's size

- [x] 1.1 `xbox_AvModeSize(mode, &w, &h)` in `kernel_hal.c` beside the AV constants: the timing-byte table of design D1 (0x01/03/07/0D/0E/0F 640x480; 0x02/04/08 720x480; 0x05 640x576; 0x06 720x576; 0x0A 1280x720; 0x0C 1920x1080; 0x10 640x576), 0 for any other byte. The comment says where the words come from (the kernel's AV mode vocabulary, as nxdk's `hal/video.c` lists it) without naming a title or a dump.
- [x] 1.2 Verify 1.1 against both titles' XDK tables with a stdlib Python script in the notes: walk the 180 rows, double the field rows' heights, assert every word's size matches `xbox_AvModeSize` (89 words). Keep the script and its output in the notes, not the repo.
  Done: 180 rows in each title, byte-identical, 0 mismatches, 89 distinct words (the spec said 90 until the review).
- [x] 1.3 `xbox_SetDisplayMode(fb_va, pitch, mode, format)` and `xbox_GetDisplayMode(&pitch, &w, &h)` in `xbox_memory_layout.{c,h}`; the bridge calls it where it called `xbox_SetDisplayFramebuffer`, before `xbox_DisplayModeBump()`; the width cross-check against `pitch / bpp(format)` for the linear formats, one `[AV]` line on a disagreement or an unknown word (design D1). The probe's `s_fb_height` and `fb_present.c`'s 640x480 read the record.
- [x] 1.4 `tests/kernel_display_mode` (design D6), registered and standalone-buildable.

## 2. Executor and backends

- [x] 2.1 `present_pick()`: after the entry is chosen, publish the extent by rules 1-3 of design D3; the `[PRESENT]` trace prints the display size and the rule. Update the present block's comment (the CRTC scans the mode's size; the clip extent is the fallback).
- [x] 2.2 `present_extent()` in `nv2a_pb_d3d11.c` and `nv2a_pb_metal.m`: grow the target to the pick with `rt_grow` when the pick exceeds it, then show the pick (design D5). `internal_resize` and the shown-size accessors unchanged in shape.
  Done, plus one change D5 did not foresee: `present_target` refused a target smaller than the pick (`rt->w >= p->w`), so the grow never ran; with one target per surface the size check goes (toolkit 1ff65d2).
- [x] 2.3 The six smoke cases of design D6 in `tests/nv2a_backend_smoke/smoke.c`, after phase 1's cases, each restoring the display state; one `[backend-smoke] mode-height:` line each. Show cases 1, 2 and 6 fail on `fix/present-scanout` and all pass on the branch; both outputs in the notes.
  Done: the branch passes all six; the base variant fails 1, 2 and 6 and passes 3, 4 and 5 (`smoke-branch2.log`, `smoke-base.log`). After the review: case 3 at a 640x232 clip with the warning counted, case 7 (a pass-1 pick), and the D3D11 crop and grow cases in `d3d11_backend_smoke`, run under Proton on the Deck (a no-grow build fails the grow case).

## 3. Docs

- [x] 3.1 cat `docs/env.md`: the `RECOMP_PRESENT_TRACE` row says it prints the display size and the extent rule; the `present_stale` row's clause from phase 1 stands. No new key. `uv run ruff check . && uv run ruff format --check .` and `uv run pytest scripts` unaffected but run.

## 4. Gates

- [x] 4.1 Mac build and `tests/posix_ctest.sh <dir>`: 0 FAIL, `kernel_display_mode` and `nv2a_backend_smoke` in the list. Summary in `runs/present-mode-height/`.
- [x] 4.2 BLiNX 2 Metal goldens on the Mac (attract, stage1, story) from a cat build against the branch: verdicts unchanged; flips/s and mean frame ms against main's last runs, flagged at a 25% drop or 1.5x rise.
- [x] 4.3 The stock proof (design D7): the three scenarios headless with `RECOMP_FLIP_LOG=1` and `RECOMP_PRESENT_TRACE=1` on main and on the branch; the per-flip `(offset, w, h)` columns identical; the trace shows rule 1 on every flip with display 640x480.
  As in phase 1, the flip sequences diverge run to run, so the proof compares sets: every flip on main, phase 1 and the branch presents 0x00104000 or 0x00230000 at 640x480, and every rule line reads rule 1 with mode 640x480 (one held flip at boot, before the first pick). Diff and counts in `runs/present-mode-height/`.
- [ ] 4.4 BLiNX 2 D3D11 goldens on the Deck (`blinx2 build windows` on the Mac with a provenance file, copy to `~/blx-bench/cat/build-win/`, `blinx2 bench golden`): verdicts unchanged; the `[d3d11] first present` line reads `copy`.
- [x] 4.5 Burnout 3 Metal race gate on the Mac from a b3 build against the branch: pass; dense dumps across the menu-to-race transition (`RECOMP_DEBUG=fb_dump_at=<range>` around the race load) all 640x480.
- [x] 4.6 Burnout 3 D3D11 under Proton on the Deck: the gate's `--pad-script` variant with `RECOMP_PRESENT_FULLSCREEN=1` and `RECOMP_FLIP_LOG=1`, under the run lock, from a Mac-built exe: zero `WxH` changes in the flip log from the `[AV] SetDisplayMode` line to the end of the drive (title, menus, load, race). Log and count in `runs/present-mode-height/deck/`. The user's look at the menu-to-race transition on the Deck is the acceptance for the eye.
- [x] 4.7 CPU rasteriser builds (4.1); no CPU golden.

## 5. Review, merge, follow-ups

- [ ] 5.1 Opus review of the toolkit branch (and this cat branch) before the merge; fixes go back to the branch's agent.
- [ ] 5.2 After phase 1's squash merge: `git rebase --onto posix-host/portability fix/present-scanout` on this branch, re-run 4.1 and 4.3 on the rebased tip, then merge toolkit and cat with `git merge --squash`. Post-merge steps: notes to `notes/present-mode-height/`, referenced runs to `runs/` with `cp -c`, worktrees removed and branches kept, the Deck `bench golden` on the merged tree.
- [ ] 5.3 TASKS.md: close follow-up (f) and BLX-144 phase 2; record the gate numbers; add the follow-ups: field interleaving from guest memory (design D3), the widescreen bit as an input to `display.aspect = auto` (design D2), the grow-margin difference between the backends if not already listed; note the upstream candidacy with the walker-present series.
