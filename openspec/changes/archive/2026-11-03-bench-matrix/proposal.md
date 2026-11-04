# bench-matrix: a game-agnostic benchmark matrix, first used on the JSRF title

## Why

The user wants a JSRF title benchmark across render scale, the APU DSP and
the aspect, on the Mac (Metal), the Steam Deck (D3D11 under Proton) and
native Windows (D3D11), with a report. Our benches so far are one-off
scripts per question, each with its own launch line and
its own interval parser, so their numbers are hard to compare and nothing
carries over to the next game. The tracker item.

## What changes

- **CLI (xboxrecomp-cli, `<game> bench-matrix`)**: a matrix runner, a
  collector and an analyser, game-agnostic.
  - `plan`: expands a matrix TOML (axes, hosts, the scene) into arms, each
    with its environment and its `config.toml`.
  - `run`: runs arms on a host kind: `mac` (local, `lockf`), `deck` (ssh,
    the host's `flock`, Proton through `umu-run`); writes the raw log and
    run info per arm. Native Windows gets a PowerShell runner (`run-arm.ps1`)
    that reads the same plan, for the session that drives the PC.
  - `collect`: one `run.json` per run: the frame-time series, avg/max/min
    fps, p1/p50/p99 frame time, 1% low fps, stutters (frames over twice the
    median), warm-up (the window's first 20 s) apart from the steady state,
    GPU clock and busy samples where the host has them, and the symbolised
    hot paths.
  - `analyse`: aggregates the runs into `summary.json` and `summary.csv`
    (one row per host and arm), for charts.
- **Game config (JSRF repo, `config/bench/title.toml`)**: the scene (start
  trigger, duration, run length), the axes and the hosts. No game data in
  the CLI.
- **Toolkit (`RECOMP_TRACE=prof`)**: an in-process sampling profiler
  (Windows, Wine and macOS) so the hot paths come from the same tool on all
  three hosts.

## Out of scope

- A CPU-backend arm, A/B gating, charts (the summary is chart-ready data;
  the report is a separate artifact).
- Driving the Windows PC from the Mac: another session runs it.
