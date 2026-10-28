## Why

Bench and golden runs measure frame speed (flips/s, frame ms, pacing) but
not what the running game costs in memory. The tracker item adds a RAM cache of up
to 750 MB to BLiNX 1, and nothing would show a run that grew by that much
or a GPU path that leaks textures. `resources.py` measures build jobs and
`bench_hw.py` records the GPU's total VRAM; neither covers the game.
The tracker item (the user, 2026-10-28).

## What changes

- **Toolkit** (`src/platform/mem_stats.{c,h}`): one always-on line at exit,
  `[MEM] exit ...`, with the process's current and peak RAM and the GPU
  memory the backend last reported (current and peak, local and
  non-local). Sources: Windows `K32GetProcessMemoryInfo` (working set,
  its peak, commit and its peak), macOS `task_info(TASK_VM_INFO)`
  (`phys_footprint` and `ledger_phys_footprint_peak`), Linux
  `/proc/self/status` (`VmRSS`, `VmHWM`). GPU: Metal
  `MTLDevice.currentAllocatedSize`, D3D11
  `IDXGIAdapter3::QueryVideoMemoryInfo` (local and non-local), sampled by
  the backend every 60 presents. A value a host cannot give prints `n/a`.
  `RECOMP_TRACE=mem=S` adds a `[MEM] sample ...` line every S seconds
  (off by default).
- **cat**: the `mem` row in `docs/env.md`.
- **CLI**: benchdb parses the exit line from `game-stdio.log` into the
  run's `metrics` rows; `benchdb regress` prints a memory line per
  host, backend and scenario and flags peak RAM or peak GPU memory up
  25% or more on the baseline (`bench.db.regress.mem_rise`, 1.25);
  `bench run` and `golden run` print the line's figures after each run.

## Out of scope

The CPU rasteriser, a per-allocation profiler, the bench-matrix HTML
report (a follow-up once the matrix runs again).
