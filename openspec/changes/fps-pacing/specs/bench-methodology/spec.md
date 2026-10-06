## ADDED Requirements

### Requirement: Pacing A/B runs under the run lock
`scripts/bench.sh pacing` SHALL run one scenario under two environments given as A and B (default: `RECOMP_PRESENT_PACING=spin` against `RECOMP_PRESENT_PACING=sleep`; the clock gate passes `RECOMP_DEBUG=vblank_clock=ms` against nothing), three runs each, alternating A and B. It SHALL take the run lock once for the whole set and SHALL include the running-game check. Every run SHALL use `RECOMP_TRACE=flip,pacing=all` and `RECOMP_ENHANCE_CONFIG=none` at stock resolution. It SHALL write all six logs and a `pacing-report.txt` from `scripts/pacing_stats.py` into one `bench-logs/<stamp>/`, with `run-info.txt` naming both environments. The report SHALL hold the 3D-only interval percentiles, flips/s, CPU raster ms, CPU shares and vblank gap range per run and per mode, and the 25% flips/s and 1.5x raster-ms flags.

#### Scenario: One A/B, one directory
- **WHEN** `bench.sh pacing @stage1` finishes on the Linux/Proton host
- **THEN** `bench-logs/<stamp>/` holds three `spin` and three `sleep` logs, `run-info.txt` and `pacing-report.txt`, and the report states whether either regression flag is raised

#### Scenario: Busy host noted
- **WHEN** the installed game is running during `bench.sh pacing`
- **THEN** the running-game warning is printed and written into the run directory, as for any other bench run, and the report notes that its numbers are noisy
