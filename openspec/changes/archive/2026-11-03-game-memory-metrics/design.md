## D1. The line

    [MEM] exit ram_mib=812.4 ram_peak_mib=905.1 commit_mib=n/a commit_peak_mib=n/a gpu_mib=301.0 gpu_peak_mib=350.2 gpu_nl_mib=n/a gpu_nl_peak_mib=n/a ram_src=phys_footprint gpu_src=metal why=atexit

- One line, `key=value` pairs separated by single spaces, MiB with one
  decimal, `n/a` for a value the host cannot give. The parser takes the
  pairs it knows and ignores the rest, so fields can be added.
- `ram_*`: phys_footprint on macOS (what Activity Monitor calls Memory),
  the working set on Windows and Wine, RSS on Linux. On macOS the GPU
  shares the memory and phys_footprint counts the Metal allocations, so
  `ram_*` already includes `gpu_*` there; never add the two on the Mac.
  `commit_*`: Windows' private commit (PagefileUsage), the figure that runs
  out first on a 32-bit-era budget; `n/a` elsewhere.
- Under Wine (Proton) the commit's peak (PeakPagefileUsage) is the current
  value, since Wine keeps no peak, so `commit_peak_mib` is not a peak there.
- `gpu_*`: the largest value the backend reported (sampled every 60
  presents and at the first), so a peak between samples can be missed.
  `gpu_nl_*`: D3D11's non-local (system memory the GPU maps); `n/a` on
  Metal, which has no separate segment (its allocations show in `gpu_*`
  and again inside `ram_*`).
- `sample` lines (`RECOMP_TRACE=mem=S`) have the same fields plus `t=`.

## D2. When it prints

Benches and goldens stop the game with SIGINT, which skips atexit; the
Windows window ends with ExitProcess, which skips it too. The line prints
from whichever comes first, once:
- atexit;
- the window exit hook (`recomp_exit_hook_add`);
- SIGINT and SIGTERM on POSIX: the handler formats into a stack buffer
  with integer arithmetic only and `write(2)`s it, then restores the
  previous handler and raises again, so the stop means what it did;
- `SetConsoleCtrlHandler` on Windows (Wine turns the bench's SIGINT into
  CTRL_C_EVENT), returning FALSE so the next handler still runs.

The GPU figures come from the backend's last note, never queried in a
signal handler.

## D3. Started where

`mem_stats_start_from_env()` at process-main, beside `host_prof`, in
`kernel_bridge.c`. It lives in the `recomp_env` library with
`host_prof.c`, so every runtime library and the standalone D3D11 test
link it.

## D4. CLI

- `benchdb.parse.mem_line(text)` -> dict of floats (an `n/a` size is
  left out); `mem_stats(log)` takes the last `[MEM] exit` line, else the
  last `sample` line.
- ingest writes every size the line gives (`ram_mib`, `ram_peak_mib`,
  `commit_mib`, `commit_peak_mib`, `gpu_mib`, `gpu_peak_mib`,
  `gpu_nl_mib`, `gpu_nl_peak_mib`) to `metrics` (unit MiB). No schema
  change.
- `regress`: per (host, backend, scenario) the median RAM peak and GPU
  peak of each build's clean runs; a `mem` line per group, flag `ram` or
  `gpu-mem` when B's median is at least `mem_rise` (1.25) times A's. Checked on every backend: the
  25% rule is about growth, which a CPU-raster run shows as well.
