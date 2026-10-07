## ADDED Requirements

### Requirement: Device interrupts never run alongside the one-CPU gate holder
A guest interrupt routine (vblank, APU, OHCI) SHALL NOT run on one host thread while another host thread holds the one-CPU gate (a thread at DISPATCH_LEVEL, a DPC or a KeSynchronizeExecution routine). When the gate is held, the interrupt SHALL be posted and run on the holder's thread at its next safe point: a kernel call, a spin-wait yield or the gate's release, taken before the gate is let go. It SHALL run on its own stack, at the device IRQL, with the holder's guest register state saved and restored, and SHALL NOT nest inside another posted routine. A post SHALL never be lost when the holder releases the gate while the post is made. Repeated posts of one vector before delivery SHALL coalesce. A holder that reaches no safe point within `irq_safe_ms` SHALL be logged with its thread and raise site, and the interrupt SHALL keep waiting unless `irq_safe_force` is set.

#### Scenario: Interrupt during a DPC
- **WHEN** the APU raises its interrupt while the timer thread is running the DSOUND DPC
- **THEN** the APU routine runs on the timer thread at the DPC's next kernel call or at the DPC's end, never in parallel with it

#### Scenario: Standalone test
- **WHEN** `tests/irq_safe_points` parks a gate holder half-way through a list edit while another thread posts an interrupt that edits the same list
- **THEN** the routine runs only inside the holder's next safe point call, on the holder's thread, and the same case with `irq_safe_points=0` records the routine running during the edit

#### Scenario: Results screen
- **WHEN** BLiNX 2 reaches the mission-1 results screen and the player continues
- **THEN** the game does not hang, and no wait log appears

#### Scenario: Vblank keeps its clock
- **WHEN** a guest thread holds the gate across several vblank ticks
- **THEN** the vblank counter advances for every tick, the ISR runs once at the holder's next safe point, and `last 600 in` stays at about 10000 ms
