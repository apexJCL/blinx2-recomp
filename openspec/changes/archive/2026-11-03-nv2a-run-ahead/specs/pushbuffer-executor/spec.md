## ADDED Requirements

### Requirement: Opt-in run-ahead walker
With `RECOMP_DEBUG=run_ahead` unset or `0`, the walker SHALL ack the KickOff flush only once it has executed everything submitted, as before. With it set, it SHALL do the following at top-level method headers about every 4 KB of a walk that executes:
- store DMA_GET, after settling the walk's reports;
- ack the flush while the title waits to submit and fewer than N segments are submitted past the walk;
- never ack while a flip is held.

#### Scenario: Key off
- **WHEN** the game runs without `run_ahead`
- **THEN** no checkpoint, notify or `run ahead` report line occurs, and the goldens match stock

#### Scenario: Key on
- **WHEN** `RECOMP_DEBUG=run_ahead=64` runs `@stage1-2-barricade`
- **THEN** the title waits less at KickOff, and the goldens pass on Metal and D3D11

### Requirement: The PGRAPH notify ends without a walker watching
With `run_ahead` on, a notify SHALL NOT be dropped while another is pending. It SHALL be queued and raised once that one is serviced. The ack thread SHALL watch a pending notify on every pass until its handler has run, so a DPC delivered after the walk's bounded stall ends its loop.

#### Scenario: Late DPC
- **WHEN** the walk gives up on a notify after 50 ms and the handler's DPC runs later on the timer thread
- **THEN** the ack thread takes the bits down, the DPC's loop ends, and the run does not hang
