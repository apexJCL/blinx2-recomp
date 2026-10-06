## Purpose

Defines how a recompiled title waits for its next frame without burning a host core. It covers the generator's opt-in lowering of guest busy-wait loops, the runtime's sleeping wait and what wakes it, the `pacing` trace, and how frame pacing is measured and compared across render paths.

## ADDED Requirements

### Requirement: Opt-in spin-wait lowering in the generator
The generator SHALL run spin-wait detection only when it is given a spin-wait file. Without the file, its output SHALL be byte-identical to the output of a generator without the feature. A spin-wait candidate SHALL be a basic block that ends in a conditional branch back to its own start and whose other instructions only read memory, compare or test it, load registers that no address in the block uses, or pause. A block that writes memory, calls, pushes or pops, uses a string, locked, port, `cpuid`, `rdtsc` or FPU instruction, changes a register used in one of its addresses, or reads no memory SHALL NOT be a candidate. For each lowered site, only the taken back edge SHALL call the runtime wait, identified by the loop's guest address, so a loop whose condition is false on first test runs exactly as before. The matcher SHALL judge each emitted body that contains the site, and a listed site SHALL match in every such body. The file SHALL select either every candidate except an exclude list, or only a listed set of sites. A listed site that is not a candidate in some body SHALL stop generation with an error naming the address, the body and the failed rule. Every run with the file SHALL write a report of all candidates with the number of bodies each appears in, saying for each whether it was lowered and why not.

#### Scenario: No file, no change
- **WHEN** the generator runs on the same input with and without the feature present, and without a spin-wait file
- **THEN** the generated sources are byte-identical

#### Scenario: Vblank wait lowered
- **WHEN** BLiNX 2 is regenerated with `config/spin_waits.json` listing `0x00060475`
- **THEN** every generated body that contains `loc_00060475` calls the wait for `0x00060475` on the back edge of that loop, and no other line of `gen/` differs from the build without the file

#### Scenario: Unsafe shape refused
- **WHEN** a listed site's loop body stores to memory or calls a function
- **THEN** generation fails with an error naming the site and the rule it broke

#### Scenario: Matcher unit tests
- **WHEN** the generator's test suite runs
- **THEN** it covers the accepted shapes (memory compared with a register or an immediate, load then test, with and without pause), the rejected shapes (store, call, modified address register, locked instruction, register-only loop, multi-block loop), both selection modes, the listed non-candidate error and the byte-identical no-file output, and passes

### Requirement: Sleeping wait with bounded latency
With `present.pacing = "spin"`, the runtime wait SHALL return at once, so the lowered loop executes as a busy-wait exactly as before. With `present.pacing = "sleep"`, the wait SHALL block the calling thread until the kernel signals that guest-visible state may have changed, or until 1 ms passes, whichever is first. It SHALL NOT miss a signal raised between the loop's memory read and the wait: the signal is a generation counter that the wait compares and waits on only under one lock, and a signal increments it under the same lock before broadcasting, so a guest store that precedes the signal is visible to the loop's next read. It SHALL NOT sleep while the calling thread runs at DISPATCH level or above or holds the one-CPU dispatch gate; it SHALL return at once there. The kernel SHALL signal after each timer-thread pass that raised a vblank, ran a DPC or fired a timer, after every host-run ISR or DPC on any thread, and after the executor writes the fence word or the ack tick updates the fence status register.

#### Scenario: Core released while waiting for vblank
- **WHEN** BLiNX 2 runs `@stage1` with `present.pacing = "sleep"` and `RECOMP_TRACE=pacing`
- **THEN** the in-wait CPU reported for site `0x00060475` is at most 10% of the window, the process CPU is at least 25 points of a core below the same route at `spin`, at most 5% of the site's loop exits in every summary are on the timeout (mid-loop timeouts are reported, not limited), and the frames match the `spin` run (see `enhancements`)

#### Scenario: No hang without signals
- **WHEN** the `spin_wait` ctest waits with no signal ever raised
- **THEN** each wait returns within 1 ms plus host sleep overshoot, and the timeout counter rises by one per wait

#### Scenario: No lost wake
- **WHEN** the `spin_wait` ctest raises a signal after the waiter's memory read but before it waits
- **THEN** the wait returns without timing out

#### Scenario: Loop exits classified
- **WHEN** the `spin_wait` ctest runs a burst of waits on one site, pauses for more than 0.5 ms, and waits again
- **THEN** the burst counts as one loop exit, on a wake if its last wait returned on a signal or at once and on the timeout if it timed out, and the waits inside the burst count as no exit

#### Scenario: Never sleeps at DISPATCH
- **WHEN** the `spin_wait` ctest calls the wait while the thread is at DISPATCH level, or with `present.pacing = "spin"`
- **THEN** it returns at once without blocking, and the DISPATCH case is counted as a dispatch skip

### Requirement: Pacing trace
`RECOMP_TRACE=pacing` SHALL print one summary every 600 flips. The summary SHALL report the flip interval p5, p50, p95 and maximum in milliseconds, the vblank gap range, the process CPU share, the pacing mode, and for each lowered site that was reached: waits, immediate returns, signalled wakes, timeouts, dispatch skips, loop exits on a wake and on the timeout (a thread's wait more than 0.5 ms after its previous one ends that previous loop), the in-wait CPU share (the calling thread's CPU time spent inside the wait, as a share of the window) and the calling thread's total CPU share. Flip times SHALL be taken at the executor's flip, which every render backend shares, on a nanosecond clock. `RECOMP_TRACE=pacing=all` SHALL also print one line per flip with its index, time in microseconds and batch count. The trace SHALL only print; it SHALL NOT change behaviour.

#### Scenario: Same trace on every backend
- **WHEN** `@stage1` runs with `RECOMP_TRACE=pacing` on the CPU path, on D3D11 under Proton and on Metal
- **THEN** each log has `[PACING] flips 600:` summaries with the same fields, measured at the same executor flip point

#### Scenario: Spin mode still measured
- **WHEN** the trace runs with `present.pacing = "spin"`
- **THEN** the summaries report intervals, gaps and process CPU, and say `mode spin`, with no site counters

### Requirement: Pacing is compared across modes on every render path
A pacing A/B SHALL compare two environments (`spin` against `sleep`; or `vblank_clock=ms` against the nanosecond clock, both at `spin`) on the same scenario at stock resolution, three runs each with at least 1,000 3D flips after the route's checkpoint, on Mac Metal, Mac CPU, Proton D3D11 and Proton CPU. It SHALL report, for 3D flips only (outside movie windows): flip interval p5, p50, p95 and maximum; flips/s; CPU raster ms p50; process, thread and in-wait CPU; and every 600-vblank gap window. An arm's statistic SHALL be the median of its runs, and its spread the range of its runs widened by 2% for flips/s and by 0.5 ms for a percentile. The report SHALL flag a drop of 25% or more in flips/s and a rise of 1.5x or more in raster ms between the arms.

#### Scenario: Regression flagged
- **WHEN** the `sleep` runs average 25% fewer 3D flips/s than the `spin` runs, or 1.5x the CPU raster ms
- **THEN** the report marks the comparison as flagged and names the metric, and the default stays `spin` until the cause is recorded

#### Scenario: Script unit tests
- **WHEN** `scripts/test_pacing_stats.py` runs on synthetic logs with known flip times, batch counts and `[PACING]` lines
- **THEN** the computed percentiles, 3D-only filtering and both regression flags match the expected values
