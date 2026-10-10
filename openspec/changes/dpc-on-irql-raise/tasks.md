## 1. Mechanism (toolkit, branch `fix/dpc-on-irql-raise` off posix-host/portability d27aa68)
- [x] 1.1 `kernel_bridge.c`: the queue behind `xbox_DpcQueue`, `xbox_DpcPending`, `xbox_DpcDrainHere` (pop under `g_dpc_lock`, clear `Inserted`, `kernel_run_dpc`; the caller holds the gate); `bridge_KeInsertQueueDpc` uses them and wakes the timer thread; `xbox_log_thread_role` marks guest-main and guest-worker threads.
- [x] 1.2 `kernel_hal.c`: the guest-thread mark, `in_dpc`, the drain with register save/restore at the raise (`xbox_KfRaiseIrql`, `xbox_KeRaiseIrqlToDpcLevel`, when the transition took the gate) and at `irq_release_point`; never inside a posted ISR or another drain; `dpc_on_raise` read with the irq config.
- [x] 1.3 `host_time.c`: `xbox_HostTimerSleepNs` (condition variable with a nanosecond deadline; waitable timer plus event on Windows; latched wake) and `xbox_HostTimerWake`; `kernel_timer_loop_ns` sleeps on it.
- [x] 1.4 `recomp_env.h` row `dpc_on_raise`; cat `docs/env.md` row.
- [x] 1.5 After the rebase onto posix-host/portability 99b9798 (BLX-1, BLX-3, BLX-4): the BLX-1 review's N7, toolkit 0beee9a. `xbox_log_thread_role` marks and pins the guest roles in one place; the pin still waits for a routine, so the host main's early guest-main log stays unpinned, as in BLX-1. `kernel_guest_cpu` now drives the pin through the roles. env.md Debug count 84. CLI branch `bench/dpc-order-tests` 5b51945 adds `dpc_order` to `bench tests`.

## 2. Test
- [x] 2.1 `tests/dpc_order` (cases a-e of the design), deterministic through events; shows the old ordering with `dpc_on_raise=0`.
- [x] 2.2 `tests/irq_safe_points`, `tests/spin_wait`, `tests/apu_irq` pass on the Mac (POSIX ctests); `tests/kernel_irql_abi` is Windows-only (VirtualAlloc) and runs with 3.3.

## 3. Gates
- [x] 3.1 Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`, `./blinx2 build macos` in the cat worktree against the toolkit worktree) under `notes/mac-run-lock.sh`; Metal goldens unchanged, stage1 flips/s and raster ms within the CLAUDE.md thresholds (the sleep primitive changed). 2026-10-07, toolkit 39303f2 (runs/m1hang/golden/): stage1 CLOSE x3 (pace 29.0 vs ref 28.4-29.6), attract CLOSE x2, story tsedit CLOSE, menu exact vs menu-a (one run; the other runs' menus are the known Mac menu marginal, 11-13% bad with dpc_on_raise=0 too), hub a new camera view with the overlay exact. A/B on the same binary (`RECOMP_DEBUG=dpc_on_raise=0`): 32.6-32.8 flips/s vs 32.4-33.0 with the fix on stage1, 51.1 vs 51.0-52.3 on story. No `[IRQ] wait` log in any run; longest posted wait 3.9 ms. Raster ms is not logged on Metal (CPU field is 0). Runs whose anchor drifted outside the dump window (the Mac's known +-30 flips, worse while Docker's VM loaded the host) are INCOMPLETE, not failures. Re-run after the rebase, 2026-10-08, toolkit 0beee9a with gen/ regenerated: Metal goldens 8/8 CLOSE (story-menu vs menu-a, no BLX-9 flake); stage1 33.65 flips/s with the fix vs 33.67 with `dpc_on_raise=0`.
- [ ] 3.2 Repro on the Mac (Metal), by the user if it cannot be scripted: three play-throughs each of (1) the mission-1 door opened with bombs, (2) the mission-1 results screen, (3) the mission-3 boss defeat (a second user repro, 2026-10-07: the game hangs right after the boss dies, a burst of sounds; expected to be the same double insert). No hang, no `[IRQ] wait` log. If (3) hangs with the fix, take a sample and a read-only lldb peek of the DSOUND lists as in `runs/m1hang/findings.md`: a different signature is a different bug and is reported, not folded in.
- [ ] 3.3 the Linux/Proton host, on the coordinator's go: `blinx2 bench tests`, `blinx2 bench golden` (D3D11 under Proton), the three repros on the Deck (D3D11), Burnout 3 boot and vehicle select under Proton on the exact head. 2026-10-08, toolkit 0beee9a, cat 5096778, gen/ regenerated (runs/m1hang/gates/): bench tests pass, dpc_order and kernel_guest_cpu included; bench golden pass (attract-cliff EXACT, 7 CLOSE); native Linux kernel_guest_cpu and dpc_order pass; pacing A/B on stage1 (3+3) 29.98 vs 29.98 flips/s, no flags. **Burnout 3 fails:** with the fix it stalls 3 of 3 runs (about 380-608 s into the race). Guest-main, inside a DirectSound raise (`sub_002F3F70`), drains a queued DPC whose call chain ends in XPP's OHCI done-list walk `sub_003681BA`, which never returns and reaches no safe point. With `dpc_on_raise=0` on the same exe: 1 of 1 clean to 900 s. The Mac and Deck repros are still to do.
- [ ] 3.5 Re-gate after design decision 7 (toolkit e0c4508), 2026-10-08. Done:
  - POSIX ctests pass, vblank_ack's new masked case included.
  - Mac build, and Metal goldens 8/8 CLOSE (stage1 33.73 flips/s).
  - Burnout 3 under Proton: vbl1 ran clean to 895 s with no `[IRQ] wait`.

  Paused for quota before:
  - vbl2 and vbl3;
  - `blinx2 bench tests` and `bench golden`;
  - the stage-1 pacing A/B.
- [ ] 3.6 Fable merge review of e0c4508: MERGE-WITH-FIXES. Fix: the masked arm leaves PCRTC_INTR_0 (design decision 7), with a write-once-ack case in `tests/vblank_ack` that fails without it; the raise comment; decision 7 records the merged-into-next-tick timing and the enable-read race. Re-gate on the final combined build (the upstream v0.13.1 sync plus this branch): Mac ctests, `bench tests`, `bench golden`, Burnout 3 twice to 900 s.
- [ ] 3.4 Fable wrote this spec and the change; the merge review is the usual one.

## 4. After the merge
- [ ] 4.1 TASKS: close the mission-1 and mission-3 hangs, re-label #26 (import-slot read, not APU MMIO), note the verification runs; `runs/m1hang/` stays as the evidence.
- [ ] 4.2 Upstream note in `analysis/upstream/pr-stack-plan.md`: DPC ordering joins the gate cluster.
