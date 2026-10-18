## MODIFIED Requirements

### Requirement: Vblank runs at 60 Hz
The kernel timer SHALL raise the NV2A vblank interrupt, while the title enables it in PCRTC_INTR_EN_0 (toolkit 3b552c5), on an absolute 1/60 s schedule that does not depend on the timer thread's sleep granularity. The schedule SHALL be computed in nanoseconds from one epoch (vblank N due at epoch + N × 10⁹/60 ns, in integer arithmetic, so it never drifts). The timer thread SHALL sleep with a high-resolution host sleep to the earliest of the next vblank, the next due kernel timer and a 10 ms cap, and SHALL ask the host for an on-time wake where the host offers one (on macOS a time-constraint scheduling policy; if the host refuses, it logs one line and runs as a normal thread). After a stall of more than 100 ms, the schedule SHALL restart rather than fire the missed vblanks in a burst. When a DPC drain stops because the one-CPU gate is busy and DPCs remain queued, the next pass SHALL come within 1 ms. The drain SHALL still never wait for the gate. `RECOMP_DEBUG=vblank_clock=ms` SHALL restore the millisecond schedule, the millisecond sleep and the 10 ms re-poll.

#### Scenario: Vblank rate
- **WHEN** BLiNX 2 runs with vblank enabled
- **THEN** each `[NV2A] vblank N: last 600 in T ms` line reports a T of about 10000

#### Scenario: Even vblank gaps
- **WHEN** BLiNX 2 runs `@stage1` on an otherwise idle Mac (Metal) or on the Linux/Proton host under Proton (D3D11)
- **THEN** over the run's `[NV2A] vblank` 600-vblank windows, the median gap spread (max − min) is at most 3 ms and at least 80% of the windows lie within 16.67 ± 1.5 ms at both ends, windows overlapping a stage load or a logged schedule restart excluded; and the 3D flip interval's p95 − p5 is at most half of the same route with `vblank_clock=ms`, with p50 within 33.3 ± 0.5 ms on both

#### Scenario: Schedule unit test
- **WHEN** the `vblank_schedule` ctest drives the schedule with synthetic times: steady 60 Hz, a late tick of 50 ms, a stall of 150 ms and an epoch near 2⁶² ns
- **THEN** due times stay on the epoch grid without drift, the late tick fires once and catches up on the grid, and the stall restarts the schedule without a burst

#### Scenario: Old loop on request
- **WHEN** a run sets `RECOMP_DEBUG=vblank_clock=ms`
- **THEN** the timer loop behaves as before this change (millisecond schedule, millisecond sleep, 10 ms cap after a gate-busy drain)
