## ADDED Requirements

### Requirement: The ack loop's poll interval is honoured on every host
While the title is kicking, the walker's ack loop polls the KickOff flush bit and `DMA_PUT` at about 50 us (`RECOMP_FAST_KICK`, default on). The nap between polls SHALL be about 50 us on native Windows as well as under Wine and on POSIX while the loop is within 2 ms of its last activity (a kick acknowledged, a new `PUT`, a flip hold): native Windows SHALL spin on the clock with a pause instruction for those naps and SHALL wait on a high-resolution waitable timer beyond the 2 ms budget, since every timed wait there expires on the system clock interrupt (0.5 ms at best); Wine SHALL keep `NtDelayExecution`; POSIX SHALL keep `nanosleep`. The 200 ms idle `Sleep(1)` SHALL be unchanged. The observer thread that times kicks for `[PB-PERF]` SHALL nap through the same helper on the cold primitive (the timer on Windows). The nap mode SHALL be set before the ack thread is created. The startup line SHALL name the nap mode in effect, the budget, and the measured p50 of a 50 us nap on each primitive the mode uses. `RECOMP_DEBUG=kick_nap=hybrid|timer|delay|spin` SHALL select the mode for comparison; unset SHALL be the rule above. Beside `timeBeginPeriod(1)` the process SHALL opt out of Windows 11's occluded-window timer-resolution policy (`PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION` turned off), so the millisecond paths stay at 1 ms when the window loses focus.

#### Scenario: Native Windows
- **WHEN** the game runs on Windows 10 1803 or later, outside Wine, with no `kick_nap` key
- **THEN** the startup line reads `nap hybrid (spin within 2 ms of activity, then timer): spin p50 N us, timer p50 N us` with the spin p50 under 100 us, and on the mission 1-2 city view the `[PACING]` window p50 returns to the 33.3 ms lock with p95 within 1-1's band, where the 1 ms-rounded nap gave p50 38-42 ms; `cpu process` rises by the walker's former sleeping share and no more

#### Scenario: The walker sleeps when the title is not kicking
- **WHEN** the title has not kicked, written `PUT` or held a flip for more than 2 ms (a menu, a light scene, a backgrounded window)
- **THEN** the ack loop's naps are timer waits, not spins, and after 200 ms idle the loop is a plain `Sleep(1)` as before this change

#### Scenario: Wine and POSIX unchanged
- **WHEN** the game runs under Proton or on macOS with no `kick_nap` key
- **THEN** the nap is the same `NtDelayExecution` or `nanosleep` call as before (the startup line reads `nap delay (wine)` or `nap nanosleep`), and the D3D11 and Metal goldens pass unchanged

#### Scenario: No high-resolution timer
- **WHEN** the host cannot create a high-resolution waitable timer
- **THEN** the hybrid's cold naps fall back to `NtDelayExecution`, its hot naps still spin, the startup line says so, and the game runs correctly

#### Scenario: The A/B values
- **WHEN** `RECOMP_DEBUG=kick_nap=timer` or `=delay` is set on native Windows
- **THEN** every nap is the high-resolution timer or `NtDelayExecution` respectively, and the startup line records its p50 (about 0.5 ms and 1 ms on the 2026-10-14 hardware) beside the mode name, for the recorded comparison

#### Scenario: The helper is bounded standalone
- **WHEN** `tests/host_nap` runs under the POSIX ctest script, under the Proton runner, or by hand on native Windows
- **THEN** 200 naps of 50 us have a p50 under 100 us in the spin mode on every host, a p50 under 400 us in the delay mode on Wine and POSIX, the timer and the Windows delay figures are printed for the record without a bound, `AUTO` resolves to `hybrid` on native Windows and `delay` elsewhere, and a zero-length nap has a p50 under 50 us
