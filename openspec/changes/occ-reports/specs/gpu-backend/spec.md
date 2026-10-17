## ADDED Requirements

### Requirement: A visibility-test report is settled before the title can read it
The GPU backends SHALL complete every pending visibility-test report (NV097 `GET_REPORT`) before the title can read it: at the end of each walk, before GET is stored; before a `BACK_END_WRITE_SEMAPHORE_RELEASE` that follows the report; and at the flip. They SHALL do it through one shared routine in the tracker (`nv2a_occ_settle`, `nv2a_backend_common.c`; `nv2a_occ_flip` at the flip). The executor calls it through the backend's `on_poll` at the first two points. At the flip, the D3D11 backend calls it after its `Present` and the Metal backend after its flip wait.

The routine SHALL work in three steps:
1. Take every result that is in, with a flush.
2. Wait for the rest while the frame's budget lasts. The budget is `occ_settle_us` (debug tier), counted per frame across all of that frame's settles. The default is 8000 µs on both backends; 0 means no wait.
3. Write each report still pending as complete (status 0) with the last completed count for that report address. The count must be younger than 250 ms. When the address has no such count, write the visible fallback (`NV2A_OCC_VISIBLE`).

A settled report's late result SHALL update only the address's last count and SHALL never be written to the report. A late result SHALL never replace the count of a newer report at the same address.

Reports already settled SHALL be polled without a flush. An `on_poll` with nothing pending SHALL only poll those.

The settle SHALL change nothing for:
- a report whose result is in by then;
- the `sync` and `fixed` modes;
- the CPU and null paths;
- the supersede, overflow and 250 ms rules;
- the render-scale division of counts.

`occ_delay_us` (debug tier) SHALL hold every result back by that many microseconds on both backends, for tests. Both backends' flip lines under `RECOMP_TRACE=flip` SHALL report the settles (`settled N (stale M, first K)`).

#### Scenario: Pending at a settle, with history
- **WHEN** a report at address A is pending at a settle, and A has a completed count younger than 250 ms from an earlier report (`tests/occ_reports`, fake ops)
- **THEN** the settle writes that count with status 0
- **AND** when the GPU result arrives later, the report words are unchanged, and a status the title has since reset stays reset
- **AND** the next report at A pending at a settle reads the late result (one frame stale)

#### Scenario: Pending at a settle, no history
- **WHEN** the first report at an address is pending at a settle, or the address's last count is older than 250 ms
- **THEN** the settle writes `NV2A_OCC_VISIBLE` with status 0 and counts it as `first`

#### Scenario: Result in within the budget
- **WHEN** a report's result comes in within the frame's remaining `occ_settle_us`
- **THEN** the real count is written and nothing is settled

#### Scenario: A budget a frame
- **WHEN** one settle in a frame has spent the budget
- **THEN** the frame's later settles take what is in without waiting, and the flip starts a new budget

#### Scenario: Injected latency reproduces the fault and the fix
- **WHEN** BLiNX 2 idles on the Story Mode / LOAD GAME screen (`@story-idle`) with `RECOMP_DEBUG=occ_delay_us=16000` and `RECOMP_TRACE=flip`, on Metal (Mac) and on D3D11 (Deck)
- **THEN** on the executor before this change thousands of flips draw 157 batches (the characters skipped)
- **AND** with the change every flip after the first with the screen up draws at least 1400 batches (`scripts/occ_flips.py` exit 0), and the settled reports are all `stale` but the first few

#### Scenario: Stock goldens unchanged
- **WHEN** attract, stage1 and story run on Metal (Mac) and on D3D11 under Proton with `RECOMP_TRACE=flip`
- **THEN** the goldens pass with the same verdicts without a re-record, at flips/s within the 25% rule
- **AND** the per-scenario `settled` totals are recorded; with the default budget most reports get their exact count

#### Scenario: Burnout 3 race
- **WHEN** a Burnout 3 race runs on Metal and on D3D11 under Proton (15-20 visibility tests a flip)
- **THEN** the race gate passes on both and no report is left pending across a walk or a flip
