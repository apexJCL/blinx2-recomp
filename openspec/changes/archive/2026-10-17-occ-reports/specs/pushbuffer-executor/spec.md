## ADDED Requirements

### Requirement: A GET_REPORT handed to a backend is written before the title can read it
The executor's `on_report` hook contract SHALL be: a backend that returns 1 writes the 16-byte report (`{timestamp, count, status 0}`) now or later, and no later than the next `on_poll` returns. Until then the status keeps the 0xFFFFFFFF that D3D wrote (TESTINCOMPLETE).

The executor SHALL call the backend's `on_poll` at two points after such a report:
- before the next `BACK_END_WRITE_SEMAPHORE_RELEASE` writes its semaphore;
- at the end of the walk, before GET is stored or a stop's salvage releases a semaphore.

The ack thread SHALL still call `on_poll` once per pass.

The walker's own paths SHALL be unchanged: the CPU rasteriser writes its fragment count at `GET_REPORT`, and `zpass_fixed` or a backend without the hooks writes the fixed value there.

#### Scenario: Deferred report complete when the walk hands back
- **WHEN** a GPU backend takes a `GET_REPORT` and the walk then releases a semaphore or ends
- **THEN** before the semaphore word or GET changes, the report's status is 0 and its count is one of: the query's result, the address's last completed count, or the visible fallback

#### Scenario: CPU path unchanged
- **WHEN** the CPU rasteriser (or `RECOMP_DEBUG=zpass_fixed=n`) handles a `GET_REPORT`
- **THEN** the report is written at the method, as before, and no `on_poll` is owed
