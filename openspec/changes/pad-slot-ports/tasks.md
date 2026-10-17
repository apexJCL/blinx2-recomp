## 0. Review
- [x] 0.1 Opus review, round 1 (`runs/padslot/REVIEW.md`, cat 97bf37f): S1 double keyboard read, S2 the Deck cause overstated, S3 stale comments, N1 to N7. All fixed in acd399c and toolkit 10528b3.
- [x] 0.2 Opus review, round 2 (`runs/padslot/REVIEW-r2.md`, cat acd399c, toolkit 10528b3): B1 a lone pad never marked active, N1 `active=` semantics, N2 motors on a swap, N3 the one-poll press, N4 README, N5 kbm_script. All fixed in d156bb1 and toolkit 631c5f4.
- [x] 0.3 Fable reads and improves the spec (the writing agent was Opus; CLAUDE.md). Commit `openspec: pad-slot-ports Fable read`. The merge is reviewed against this version.

## 1. Map
- [x] 1.1 `src/pad_slots.c`/`.h`: init, update (free gone slots, then the lowest free port to each new slot in slot order), activity, idle, mapped, slot_of, ports, format. No host or guest state.
- [x] 1.2 `scripts/test_pad_slots.py`: stock slot 0, identity from 0, a lone slot 1 or 3, later pads, unplug, a swap within one interval, high bits ignored, four pads with the middle two replugged, slot 0 back on port 0.

## 2. pad_input.c
- [x] 2.1 The connected mask is built from the map wherever `cat_pad_connected_mask` is computed and at init. `[INPUT] t= pads=` is logged (and flushed) when a pad takes or gives up a port. The sources line gains `pads=`.
- [x] 2.2 `cat_pad_get_state` reads the mapped slot through `xbox_InputGetPadState`. On port 0 only, when the keyboard or mouse is on, they are read once and merged with `xbox_InputMergeKbm` (review S1).
- [x] 2.3 `cat_pad_rumble` forwards to the mapped slot.
- [x] 2.4 The one-second probe reads every slot through the pad-only accessor; the slot-0 exception is gone.
- [x] 2.5 `src/recomp_manual.c` comments name pad_slots instead of "controller N on port N"; `docs/env.md` `RECOMP_HOST_PAD` row and line references.

## 3. Toolkit
- [x] 3.1 `xbox_InputGetPadState` and `xbox_InputMergeKbm` on `fix/pad-only-state`; `xbox_InputGetState` is built from them; both listed in `src/input/README.md`.
- [x] 3.2 `tests/input_map`: the fake backend counts keyboard reads: none for `GetPadState`, one for `GetState(0)`, none for `GetState(1)`; the exported merge equals `GetState`'s.

## 4. First-press promotion
- [x] 4.1 `pad_slots_activity`, `pad_slots_idle`, `pad_slots_mapped`; `active` cleared on unplug.
- [x] 4.2 Tests: `0:0,1:1` with slot 1 active gives `0:1,1:0` with the port mask unchanged; later slot-0 activity moves nothing; three pads, two inert, the active one on port 0 and the next pressed on port 1; activity forgotten on unplug; activity on a slot without a port is ignored.
- [x] 4.3 `pad_input.c` reads every idle slot at the start of each port-0 poll while any is idle, a lone pad included (round-2 review B1); on a swap logs `pads=... active=<every active slot>`, clears `g_host_last`, and stops both swapped pads' motors.
- [x] 4.4 Test: a pad pressed while alone keeps port 0 when a second comes up and is pressed; the idle and mapped masks the glue reads.
- [x] 4.5 Test: two never-pressed pads whose first press falls in the same poll are handled in slot order (`0x3, a0x3` stays `0:0,1:1`; `0x2, 0x3, a0x3` goes from `0:1,1:0` to `0:0,1:1`).

## 4b. Rebase onto BLX-15 (round 4, `fix/pad-slot0-r2`, toolkit `fix/pad-only-state-r2`)
- [x] 4b.1 Toolkit: 10528b3 and 631c5f4 cherry-picked onto posix-host/portability c8a8214f, clean.
- [x] 4b.2 cat: af947c8's change replayed onto main 04eaf77 in one commit; the conflicts were main's trace gating of the `host port=` and rumble lines (BLX-123), kept, and the env.md rows.
- [x] 4b.3 One port map with SDL hot-plug (design.md decision 7): `PadSlots.last`, a returning slot takes its old port when free and another pad is up, else the lowest free; D2's player-1 and no-shift rules hold at the title's ports.
- [x] 4b.4 The watch also runs on the other ports' polls while port 0 has no source (decision 7, the B1 review with hot-plug in place).
- [x] 4b.5 Tests: a replug keeps its port, the lowest free when it is taken, a lone returning slot takes port 0, the port remembered after a swap, same-poll presses (4.5); `test_four_pads_middle_replugged` now expects each slot back on its own port.

## 5. Gates
- [x] 5.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`); `uv run pytest scripts` (58 pass, 15 of them `test_pad_slots.py`; `test_gitignore` fails only in a worktree, where `game_files` is a symlink, not the real dir); ruff check and format clean; toolkit `tests/posix_ctest.sh` 0 FAIL with `input_map` passing (`runs/padslot/posix-ctest-r3.log`, toolkit 631c5f4).
- [x] 5.2 `blinx2 golden` Metal on the round-3 tree (cat d156bb1, toolkit 631c5f4): attract, stage1, story pass (`runs/padslot/golden-r3.log`; runs 20261013-204450, -204517, -204636; `pads=none`; attract carried a host-load warning and still passed). Round 2 (acd399c) also passed: 20261013-202353, -202420, -202540.
- [x] 5.3 Round 1 (cat 97bf37f, before promotion): `blinx2 bench golden` D3D11/Proton passed (bench-logs 20261013-193245, -193404, -193555). Proton, one bench vpad: with `PROTON_NO_STEAMINPUT=1`, `pads=0:0` and START on port 0 (20261013-195017); with Steam Input on, `pads=0:0,1:1` and START on port 1 (20261013-194641), which is the inert-pad case this change then fixed.
- [ ] 5.4 Pending (the Linux/Proton host down): `blinx2 bench golden` D3D11/Proton on the exact tips of `fix/pad-slot0-r2` and `fix/pad-only-state-r2` (round 4; the round-3 tips d156bb1 and 631c5f4 were never run there), and the Steam Input on vpad probe, which should log `sources ... ports=0x3 pads=0:0,1:1`, then `[INPUT] t=<s> pads=0:1,1:0 active=0x2` on the first press, no `ports=` change, and `host port=0 buttons=START`.
- [ ] 5.5 Pending (the user): a Steam Deck Desktop Mode log with the `pads=` field. `pads=1:0` in the sources line means a lone pad on index 1; `pads=0:0,1:1` then `pads=0:1,1:0 active=0x2` means Steam's inert pad on index 0. Record the answer in TASKS.md under BLX-117.

## 6. After the merge
- [ ] 6.1 Toolkit first (`fix/pad-only-state-r2` squashed onto `posix-host/portability`), then cat (`fix/pad-slot0-r2` squashed onto `main`), then the usual post-merge steps from CLAUDE.md: notes to `notes/padslot/`, the runs cited above kept under `runs/padslot/`, worktrees removed, the Linux/Proton host synced and `blinx2 bench integrate --golden`, TASKS.md updated with the gate results and BLX-117's state.
