## ADDED Requirements

### Requirement: A DPC queued by an interrupt runs before guest code resumes below DISPATCH
A DPC queued by an interrupt routine SHALL run before a guest thread that raises to DISPATCH_LEVEL enters its critical region, and SHALL run at the release point of a guest thread that held the gate while the routine was queued, as on the console a DPC runs when the processor drops below DISPATCH before the interrupted thread resumes. It SHALL run on that guest thread, at DISPATCH_LEVEL, holding the one-CPU gate, with the thread's guest register state saved and restored, SHALL NOT run inside a posted interrupt routine, and SHALL NOT nest inside another drain. A device-model thread (APU frame thread, OHCI controller thread) SHALL NOT run a queued DPC. `KeInsertQueueDpc` SHALL wake the timer thread so a queue that no guest thread drains runs within a few milliseconds. `dpc_on_raise=0` SHALL restore the timer-thread-only drain.

#### Scenario: Stop list drained before Play
- **WHEN** the DSOUND interrupt appends an idle voice to the stopped-voice list and queues its DPC, and the title then calls Play on that voice
- **THEN** Play's raise to DISPATCH runs the DPC first, the voice is off the stopped list and the hardware list before Play re-links it, and the next idle trap for that handle inserts it once

#### Scenario: Standalone test
- **WHEN** `tests/dpc_order` delivers a gated interrupt on a model thread whose routine queues a DPC, and a guest thread then raises to DISPATCH
- **THEN** the DPC ran before the raise returned, on the guest thread, at DISPATCH, with the thread's registers unchanged; the same queue is not run by the model thread's release and is run by the lower of a guest holder that took the interrupt at a safe point; a queued DPC ends the timer thread's sleep within 2 ms; with `dpc_on_raise=0` the raise returns with the DPC still queued

#### Scenario: Bomb door, results screen, mission-3 boss
- **WHEN** the mission-1 door is opened with bombs, the mission-1 results screen is reached, or the mission-3 boss is defeated
- **THEN** the game does not hang, and no `[IRQ] wait` log appears, on Metal and on D3D11 under Proton

#### Scenario: Burnout 3 keeps its front-end pair
- **WHEN** Burnout 3 boots and reaches the vehicle select under Proton
- **THEN** no DPC runs on the APU frame thread, and the DSOUND DPC that waits on a trapped front-end method still completes
