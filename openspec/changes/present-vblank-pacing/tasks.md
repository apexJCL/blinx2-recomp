## 0. Review
- [x] 0.1 Fable reads and improves this spec (the writing agent isn't Fable). Implementation starts from the revised version (commit `spec: present-vblank-pacing review`). Rulings: root cause confirmed in 0988b9c; release rule stays `last + interval` with `flip_pacing=edge` as the switchable D3D rule; alternative B rejected for now and recorded as a follow-up; the hold runs on `nv2a-ack` and holds nothing (design 4b); the KickOff spin is lowered in both titles (design 9); gates extended (sections 3 and 4).
- [ ] 0.2 Comment on Plane BLX-53 and BLX-49 with the spec's revision sha and the gate list (`/tracker`).

## 1. Mechanism (toolkit worktree `wt/pacing/xboxrecomp`, branch `fix/present-vblank-pacing` off BLX-31's `fix/mac-one-cpu` 32cd6fd, rebased onto BLX-31's squash on posix-host/portability once it lands)
- [x] 1.1 Read-only checks before coding, in the B3 and BLiNX 2 gen:
  - B3 sets no swap callback (no store to device + 0x1DB4 or miniport + 0x18C);
  - both titles' `sub_00350BD0`-style encoders agree on the payload bits.

  Record the results in `notes/pacing/NOTES.md`.
- [x] 1.2 `src/kernel/nv2a_flip_hold.{c,h}`: the pure rule (design 2, 5, 6, 7), including the `edge` flag, wired into the toolkit's CMake source list.
- [x] 1.3 `nv2a_pb_exec.c`:
  - a `NV097_NO_OPERATION` case decodes swap method 1;
  - FLIP_STALL samples `xbox_VblankCount()` before `on_flip`, then arms the hold, and only outside a CALL (`nv2a_pb_scan.c` keeps `in_call` local today: expose it to the executor, or have the scan pass it in);
  - `nv2a_pb_exec_flip_poll()` (the ack loop's per-pass poll);
  - a walk stop clears the hold.
- [x] 1.4 `xbox_memory_layout.c`:
  - Poll each pass;
  - while held, skip the walk and both kick acks, and the fast-kick loop naps instead of ticking;
  - `xbox_SpinWake()` on every kick clear (both paths);
  - frame-counter `last_written` / `seeded` / `owned_by_title`, first bump seeds.
- [x] 1.5 `recomp_env.h`: `flip_pacing` debug row (`0`, `1`, `edge`). `kernel_pacing.c`: the trace fields.
- [x] 1.5b KickOff spin sites (design 9):
  - cat `config/spin_waits.json`: the 0x002E7F20 loop, then `blinx2 analyze` and `blinx2 recomp` in `wt/pacing/cat`; the gen diff shows only that site;
  - b3: the same for the kick's spin (it is at 0x00351BF0 in `sub_00351BD0`, which `sub_00350C10` calls), in a b3 worktree on its own branch (the orchestrator merges it; agents don't edit `b3/`);
  - if `tools/recomp/spin_waits.py` rejects the `test [mem], imm / jne` form, extend it with a `test_spin_waits.py` case.
- [x] 1.6 `git merge-tree` against BLX-31 (`fix/mac-one-cpu` 32cd6fd) and BLX-47 (`chore/vanilla-cleanup`). Record any conflict and how it resolves. (Done: the only conflict is `recomp_env.h`'s GUEST_CPUS row, which BLX-31 and BLX-47 already conflict on between themselves; this branch also merges cleanly with BLX-31's later tip e48f150.)

## 2. Tests
- [x] 2.1 `tests/flip_hold` covers the cases in the spec's standalone scenario plus the counter-ownership rule (including the seeding case: a counter that starts non-zero is bumped first and not stood down) and the `edge` rule. It fails against a rule that releases at once.
- [x] 2.2 The POSIX ctests pass on the Mac, including `nv2a_backend_smoke`, `d3d11_backend_smoke` (where it builds), `pb_tex_cache`, `vblank_schedule` and `spin_wait`.

## 3. Gates (Mac)
- [x] 3.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`, through `notes/mac-run-lock.sh`):
  - cat in `wt/pacing/cat` against the toolkit worktree;
  - b3 built into its own build directory from a copy, or from `wt/b3mac/b3` read-only, with `XBOXRECOMP_DIR` pointing at the toolkit worktree.
- [x] 3.2 Burnout 3 on Metal (`SDL_AUDIODRIVER=dummy`, headless, `RECOMP_TRACE=flip,pacing`), boot plus the TASKS r3 race script, into `runs/pacing/`:
  - flips.py per bucket: front end and race at about 60;
  - intro movie lengths;
  - the HUD race clock against wall time from two dumped frames (B3's race HUD shows no clock; the flip interval, p50 16.6 ms, stands in);
  - the `holds` / `nonop` / `counters_owned` trace fields, `hold_timeouts` = 0, the stand-down log line exactly once;
  - an A/B run with `flip_pacing=0` on the same binary, and one short race run with `flip_pacing=edge` for the fidelity comparison (flips/s and the HUD clock);
  - with the guest-CPU lock on (as BLX-31 configures it for the Mac): no APU underruns beyond today's, and the spin-site trace shows the KickOff site yielding.
- [x] 3.3 BLiNX 2 Metal goldens story, stage1 and attract: `uv run --project xboxrecomp-cli xbr --game cat golden run SCEN --backend metal --out runs/pacing/golden-SCEN`. Stage1 flips/s against the last reference, the trace's hold count and `iv1`/`iv2`, no stand-down log line, `hold_timeouts` = 0.
- [x] 3.3b BLiNX 2 on the Mac CPU backend, one stage1 run: flips/s and raster ms within the bench thresholds (a drop of 25% in flips/s or 1.5x in raster ms fails).
- [ ] 3.4 Fable merge review. Its fixes come back to this branch.

## 4. Proton (the orchestrator runs these on the Linux/Proton host, one at a time, under the run lock)
- [ ] 4.1 `blinx2 bench tests` (with `flip_hold`) and `blinx2 bench golden` (D3D11); the bench's flips/s and raster ms against the last integrate run (the same 25% / 1.5x thresholds).
- [ ] 4.2 Burnout 3 on D3D11 under Proton, on the exact head:
  - boot to the attract loop: front-end flips/s about 60, intros at real length;
  - the scripted race to 900 s: no hang, race at 60 or below;
  - the same on the Steam Deck (90 Hz): menus at 60, audio in phase, checked by the user by ear.
- [ ] 4.3 Burnout 3 on the CPU backend under Proton, one boot: flips/s in the menus not below today's (about 14).

## 5. After the merge
- [ ] 5.1 TASKS: close BLX-49/BLX-53, and list the follow-ups:
  - letting the title run one segment ahead during a hold (needs MakeSpace's notify);
  - alternative B (real GPU interrupts) if a title needs its swap callback;
  - b3 may drop its frame-counter registration.
- [ ] 5.2 Upstream note in `analysis/upstream/pr-stack-plan.md`: flip pacing under topic 4 (BLX-49's row), with the walker's swap-NOP decode and FLIP_STALL arm noted as G2 content if that series goes first; the PR description names the `last + interval` deviation, the `edge` switch, and alternative B as the faithful successor. Tested on Burnout 3 under Proton on the exact head.
