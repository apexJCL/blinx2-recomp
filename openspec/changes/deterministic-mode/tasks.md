## 1. Phase 1: virtual clock (toolkit, `feat/deterministic-clock`)

- [x] 1.1 `guest_time.{c,h}`: every guest clock read routed through it, no-op commit.
- [x] 1.2 PC D3D11 golden with the mode off on the refactor commit.
- [x] 1.3 Virtual mode behind `RECOMP_DEBUG=deterministic`: clocks, exports at the step, waits, delays, kernel timers, the step with vblanks off, the frozen-clock warning.
- [x] 1.4 ctest `tests/guest_time`: real follows the host; virtual frozen between steps, one period per step, monotonic over 10^6 steps; waits and delays end after the crossing step; the object still ends a wait.
- [x] 1.5 `state_hash`, `state_hash_skip`, `state_dump` at the port-0 poll hook.

## 2. Phase 1: cat

- [x] 2.1 `sub_002E0DB0` waits for the next virtual vblank in the mode.
- [x] 2.2 `docs/env.md` rows for the four keys.

## 3. Phase 1: gates

- [x] 3.1 POSIX ctests 0 FAIL.
- [x] 3.2 PC D3D11 golden with the mode off on the tip.
- [x] 3.3 `TOOLKIT=<worktree> WIN_BUILD_HOST=bench host-win sh notes/build-all.sh`.

## 4. Phase 1: measurement (PC, mode on)

- [x] 4.1 clip3 replayed twice with `state_hash`; stage1 golden scenario twice.
- [x] 4.2 First differing poll before the tunnel; pages; dump and diff; owner.
- [x] 4.3 Report on the tracker item with what phase 2 must pin.

## 5. Phase 2: lockstep vblanks (`feat/deterministic-phase2`)

- [x] 5.1 Det scheduler `kernel_guest_det.c`: ring in ring-slot order, passes at waits and back edges, step only when every guest thread is idle (D7).
- [x] 5.2 Devices granted: NV2A catch-up, timer pass, 25 APU frames per step; APU warm-start skipped in the mode.
- [x] 5.3 Undecided-mode nap for device threads (D8).
- [x] 5.4 `det_trace`, `det_dump` keys; `docs/env.md` rows.
- [x] 5.5 ctest `tests/guest_det`.
- [x] 5.6 Creator-carved worker TIB (D9).
- [x] 5.7 A quantum spinning on a frozen clock counts as idle (D10); ctest case.
- [x] 5.7a Fixed FileFsSizeInformation in the mode (D12); ctest case.
- [x] 5.7b Fixed file times in the mode (D13); ctest case.
- [x] 5.7c Input scripts on the virtual clock (D14); `det_snap` key (D11).
- [x] 5.7d A thread's end published before it parts (D15); pass hash and `K` lines (D11); ctest case.
- [x] 5.7e Review fixes: device threads idle until the mode is decided, stock decides off at once (D8); thread waits test the end event (D15); failed spawns drop their slot and TIB (D9); dead slots reused, steps under suspended threads, sub-ms timeouts in the ring (D18); ctest cases.
- [x] 5.7f Delta review fixes: undecided asked before the mode in the device loops (D8); the turn's slot never reused, the parting steps bounded (D18); ring-slot order in the docs (D7); the main thread's object checked (D15); ctest cases; toolkit rebased on `posix-host/portability` 120ac485. On toolkit 701a2faa: POSIX ctests 0 FAIL; build-all (BLiNX 2, BLiNX 1, KUF; macOS and Windows on the PC) pass; Metal goldens attract, stage1, story pass; D3D11 golden on native Windows attract and story pass-with-known, stage1 pass; Mac clip2 5/5 identical in the mode (4073 polls each; `runs/deterministic-mode/p2-fix2/`).
- [x] 5.8 stage1 and clip2 identical per-frame checksums, 5 runs Mac, 5 runs PC (D17).
  - [x] stage1: Mac 6/6, PC 5/5 identical over the common prefix.
  - [x] clip2 PC: 5/5 identical, full clip (4073 polls, quit on the script's end).
  - [x] clip2 Mac: 4/5 identical before the review fixes (one run parted at poll 3982 of 4073); 5/5 identical after them (D17).
  - [x] After the review fixes, PC: clip2 5/5 and stage1 5/5 identical.
- [x] 5.9 Mode off: Metal goldens (attract, stage1, story pass), build-all (BLiNX 2, BLiNX 1, KUF; macOS and Windows) on toolkit bd3b48e6; after the review fixes (toolkit 643691a4) the same, plus the D3D11 golden on native Windows (attract and story pass-with-known, stage1 pass).

## 6. Later phases

- [ ] 6.1 Ordered loader and audio completions at guest points (the async I/O and APC candidate of D17; follow-up).
- [ ] 6.2 The tracker item replay check in the bench.

## 7. Phase 3: pad record and replay for every game (`feat/deterministic-phase3`)

- [x] 7.1 Engine already in the toolkit (`pad_script`, `usb_gamepad`); BLiNX 2 through the game tap, USB titles through `usb_gamepad_report` (D19).
- [x] 7.2 OHCI controller as a granted device, one pass per vblank step, frame counter on virtual ms (D20); ctest case in `tests/guest_det`.
- [x] 7.3 Millisecond scripts and `PAD_PRESS` on the virtual clock in the mode (D21).
- [x] 7.4 ctest: the recorded formats (flip, poll, anchors, comments, out-of-order steps, `@end`) in `tests/pad_script`; the test also checks pad files given as arguments.
- [x] 7.5 `docs/env.md`: `deterministic` and `pad_script` rows.
- [x] 7.6 Gates on toolkit 42d7676f. POSIX ctests: 0 FAIL. build-all: BLiNX 2, BLiNX 1 and KUF pass on macOS and Windows, built natively on the PC. Metal goldens: attract, stage1 and story pass. D3D11 golden on native Windows: stage1 passes; attract and story pass with known issues. Mac clip2 in the mode: 5/5 identical, and equal to phase 2. BLiNX 1: a record and two replays in the mode agree (D22).
