## Why

BLiNX 2 hangs at the end of mission 1, on the results screen. The user reproduced it twice (`runs/stage1-issues/user/game-20261006-123223-hang2.log`, with a thread dump, and `sample-hang2.txt`). The kernel timer thread never leaves the DSOUND DPC. In `sub_003346BE` (0x33470F-0x334730), the DPC pops the first node of the list at dsound+0x4A0 and calls its handler until the list is empty. One node in that list points to itself while the head still points at it. Taking it off the list then does nothing, so the list never empties. The only insert is `sub_00335C18` (0x335DB8), which appends voice+0x54 without checking whether it is already linked, so the same voice was inserted twice.

That insert runs in the APU interrupt handler (`sub_00334D23` → `sub_00334C06` → `sub_00334B85` → `sub_003347D1` → `sub_00335C18`). Its only guards are a check-then-act on dsound+0x84 and "voice+0x4C still linked". They are safe on the Xbox because an interrupt runs atomically on its one CPU: whatever it interrupted (a DPC, or a thread at DISPATCH editing the same lists) is frozen until it returns.

The runtime breaks that. The one-CPU gate keeps a DPC and a thread at DISPATCH apart, but a device interrupt can run in parallel with whoever holds the gate:
- APU: once delivery has been held off for 50 frames (32 samples each, about 33 ms), it is "forced" without the gate (`apu_core.c`, `apu_deliver_irq`).
- OHCI: after `OHCI_IRQ_HOLDOFF` (500) polls, the same.
- Vblank: never waits; it runs ungated whenever the gate is busy (`kernel_raise_interrupt`).

So the guest's interrupt handlers and its DPC or DISPATCH code really do run at the same time, and lists like DSOUND's get corrupted. The double insert at the results screen (the first time `song_RESULTsw.adx` plays, since the old dump lacked it) is one instance. TASKS #26 (the DSOUND DPC faulting on APU registers, stage 5-1) and the user's "audio loops its last beat" may be others. Whether a forced delivery happened in the user's session is not yet confirmed (task 1.1); the ungated paths are a concurrency hole whatever that run shows.

## What Changes

- A device interrupt that finds the gate held is not run alongside the holder. It is posted as pending, and the holder runs it on its own thread at its next safe point, the way a CPU takes an interrupt at an instruction boundary. Safe points: every kernel thunk call, the spin-wait yield (`xbox_SpinWait`, including its immediate return for a thread at DISPATCH), and the gate's release (KfLowerIrql below DISPATCH, the end of a DPC, the end of a KeSynchronizeExecution routine), taken before the gate is let go.
- A serviced MMIO trap is not a safe point in this change. The trap is serviced inside a signal handler (POSIX) or a vectored exception handler (Windows); running a guest interrupt routine there puts guest code on the signal stack, nests faults and, on Windows, meets the loader lock. A holder's register poll loop that must take an interrupt is lowered through `config/spin_waits.json`, which turns it into a yield, the existing tool for that.
- The run on the holder's thread saves and restores the holder's guest register state, uses a worker stack, as the delivering threads do today, and raises the IRQL to the device level for the routine.
- No concurrent fallback by default. A holder that reaches no safe point for `irq_safe_ms` (250 ms) is logged with its thread, its raise site and its kernel call count, and logged again every second; the interrupt waits. Concurrent delivery after that time is an opt-in A/B key (`irq_safe_force=1`), because it reinstates the race exactly when the holder is longest. `RECOMP_DEBUG=irq_safe_points=0` restores today's behaviour entirely.
- The vblank keeps its clock: the schedule and counter stay on the timer thread, a posted vblank runs at the holder's next safe point and coalesces with later ticks, as a latched line does.

## Capabilities

### Modified Capabilities
- `kernel-threads`: device interrupts are serialised with the one-CPU gate holder through safe points instead of running concurrently.

## Impact

- toolkit: `src/kernel/kernel_hal.c` (gate ownership, pending word, safe-point hook, delivery on the holder), `src/kernel/kernel_bridge.c` (vblank post and ack bookkeeping, kernel thunk dispatch, DPC and KeSynchronizeExecution epilogues), `src/apu/apu_core.c` (APU post), `src/usb/ohci.c` (OHCI post), `src/kernel/kernel_pacing.c` (yield safe point), new ctest `tests/irq_safe_points`. It touches every title's interrupt model, so it is upstream-relevant and gated on Burnout 3.
- cat: `docs/env.md` rows (`irq_safe_points`, `irq_safe_ms`, `irq_safe_force`), TASKS #26 cross-reference, `config/spin_waits.json` if a holder loop turns up.
