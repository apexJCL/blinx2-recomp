## Why

Today's performance numbers mix things that say nothing about each other. The Sofdec movies run at 60 fps on a CPU decode plus one or two full-screen quads. That proves the 2D path and the pacing, not 3D (`analysis/research/blinx2-internals-and-fmv.md`, section 5). Two threads sit at 99.6 % while the host is 86 % idle (`bench-logs/20261001-214200/top-threads.txt`), and nothing yet maps a tid to a role. The fence rate drops from about 85 releases/s in the movies to about 48/s in the title stage, even with every 3D batch skipped, and that is unexplained. A run record also does not say which toolkit and cat commits, or which `gen/`, the exe came from.

the Linux/Proton host (GE-Proton) is the bench, driven from the Mac through `scripts/bench.sh`. The main session and its sub-agents drive it over `ssh <bench-host>` (per-agent trees `~/recomp-<agent>`, integration tree `~/xbox-recomp`, all runs under `flock ~/.recomp-run.lock`).

## What Changes

- Every run directory records enough to reproduce it: host, Proton build, the full `RECOMP_*` environment, the exe sha, the toolkit and cat commits, and the `gen/` provenance stamp.
- Movie windows are excluded from performance statistics. A frame is in a movie window if it falls between the open and close of a `movie\*.sfd` file, or if it has 2 batches or fewer and one full-screen texture.
- For 3D frames only, report flips/s, p50/p95/p99 frame ms and fence releases per frame from the per-flip log (`RECOMP_FLIP_LOG`), always alongside framebuffer dumps of the same scenes.
- Thread roles and names come from the `[THREAD] tid=.. role=..` lines of the same run.
- Crash reports are symbolized offline (`bench.sh logs` / `symbolize`, already in place).

## Capabilities

### New Capabilities
- `bench-methodology`: how a bench run is recorded, which frames count for performance, and what is reported.

### Modified Capabilities
<!-- none -->

## Impact

- cat: `scripts/bench.sh` (run-info fields, the report step), `scripts/pipeline.sh` (a `gen/PROVENANCE` stamp).
- Toolkit: `RECOMP_FLIP_LOG` and `[THREAD]` lines (merged, `a47bfb0`). The movie-window tag comes from `fmv-playback`.
- the Linux/Proton host: no change to the host setup.
