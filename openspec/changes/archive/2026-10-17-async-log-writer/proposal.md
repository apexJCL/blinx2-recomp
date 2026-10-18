## Why

The tracker item's native Windows 11 profile (WPR, mission 1-2, about a minute; the orchestrator's comment of 2026-10-14) found the slowdown's cause in the log, not in the game:

- The GPU walker thread (`nv2a-ack`, toolkit `src/kernel/xbox_memory_layout.c`) spends about 33% of its samples inside `fprintf`, with ntoskrnl, FLTMGR and the Defender filter (`WdFilter`) under it. The hot format string is the per-kick line `  [NV2A] %8lu ms  DMA_PUT = 0x%08X  DMA_GET = ...  fence ...` (line 1822).
- The guest main thread spends 80% of its samples on one instruction, the D3D KickOff spin at guest 0x2E7F7A (`config/spin_waits.json` site 0x002E7F20), which waits for that walker to clear the kick bit. So the game is not working; it is waiting for the log.
- The user hears garbled sound effects during the slowdown: the guest's DirectSound updates run late when its frames run long (2026-10-14: XAudio2 reports no starvation, so the garbling is guest-side).

Two things make every line expensive:

1. `cat/src/main.c` `host_stdio_setup` (line 1044) sets both streams to `_IONBF`, and with `RECOMP_STDIO_LOG` set, which every packaged launcher does (Windows `launcher.c`, steamos `launch.sh`, macOS `BLiNX2.in`), both are `freopen`'d onto the log file. Every `fprintf` call is then a synchronous `WriteFile` to an NTFS file, which Defender's filter scans: about 180 us each on this PC (a third of a core for 1,800 writes a second). The walker's line is four `fprintf` calls plus an `fflush`.
2. The line is armed by default. `s_nv2a_trace` (line 3612) is set by `RECOMP_TRACE=nv2a` or `pb_scan`, **or `RECOMP_PB_EXEC`**. Upstream wired `PB_EXEC` to the trace when the executor was opt-in (v0.7.0); our 5b1d8e9 made `PB_EXEC` default on, which made the trace default on. That is the tracker item.

Measured on `runs/win11/20261014/game-20261014-125152.log` (647 s, 308,303 lines): 288k are `[NV2A] ... DMA_PUT` lines (93%, about 445 a second, about 1,800 synchronous writes a second), then `[INPUT] t=... host port=0 buttons=...` 6.4k, `[KERNEL] summary` plus its six `ordinal` lines 2.6k, `[READ]` about 2k and `[WRITE]` about 1.6k (loading and the checkpoint save), `[INPUT] rumble` 1.3k, `[PATH]` 953, `[FILE]` 720. Frame times: 1-1 p95 34-37 ms, 1-2 p50 33.6-37.2 ms, p95 41-50 ms (`RECOMP_TRACE=pacing`).

**The gating alone fixes it.** The user's throwaway build with the DMA_PUT line silenced (2026-10-14, `game-20261014-131844.log` before, `-140530.log` after, same route, `RECOMP_TRACE=pacing,apu`) took 1-2 p95 from 37-50 ms to 34.2-34.9 ms in 15 of 18 windows (three windows at 40-42 ms), process CPU from 112-184% to 91-152%, and the log from 19.3 MB to 4.4 MB. The after-run still printed about 140 synchronous lines a second (82k `[APU] voice` and 2.3k `[APU-VSTAT]` lines from the `apu` trace, on the APU frame thread) and held 34-35 ms, which puts the harmless rate on this host in the low hundreds of lines a second. The default output after this change is under five lines a second.

The user first asked for an async log writer (lines to an in-memory queue, one writer thread, flush on exit and crash). This spec was written around one, then weighed against the evidence above (design.md, Recommendation). The recommendation is the gating and the quieting now, with the writer kept as a designed follow-up that two kinds of evidence would reopen. The user accepted the trim of the native Windows A/B and asked for that weighing; this revision is the result.

## What Changes

- **The tracker item: the NV2A per-kick trace becomes trace-only** (design.md D1). `s_nv2a_trace` is armed by `RECOMP_TRACE=nv2a` alone. `RECOMP_PB_EXEC` keeps driving the executor, the scan, the fences and the flip hold, none of which read the flag. The `PCRTC_START` line and the once-a-second framebuffer checksum follow the trace. The periodic `[GPU]`/`[PB]` report runs under `nv2a` or `pb_scan`, and `fb_dump` alone keeps its periodic picture. The DMA_PUT line becomes one `fprintf`, so it cannot tear and costs one write when it is on. The stall timeline the tracker item used (gaps between DMA_PUT lines) stays available as `RECOMP_TRACE=nv2a`.
- **Default output quieted** (D2): the game's per-poll `[INPUT] ... host port=` and `[INPUT] rumble` lines go under the game's existing `RECOMP_TRACE=input`; the toolkit's per-call `[READ]` and `[WRITE]` records go under a new `RECOMP_TRACE=file`; the 2 s `[KERNEL] summary` block moves to once at exit and into the watchdog's hang report, with the periodic form under a new `RECOMP_TRACE=kernel_summary`. `[PATH]`, `[FILE]`, the 600-vblank line and the boot-time `[KERNEL] #N` lines stay.
- **stdio stays unbuffered and synchronous** (D3): with the rates above, a write of about 0.2 ms per line on the slowest host costs a default run about a millisecond a second, and the crash report, the `unimpl_trap` line, the watchdog's report and the log readers that tail a run keep working as they do today, with no new machinery.
- **The async writer is deferred** (D4): its design (a pipe under fds 1 and 2, one writer thread, a sync-token flush on every exit and crash path, counted drops, a `log_sync` key, a standalone ctest) is kept in design.md as the follow-up to build when a default-run profile shows the log back on a game thread's critical path, or an investigation on Windows or Proton needs a high-rate trace whose writes perturb what it measures.
- **Rows in `docs/env.md`** for `file` and `kernel_summary` and the reworded `nv2a`, `pb_scan`, `pb_report_ms` and `input`.

Not in this change: `xbox_kernel.log` (a second file, a flush per line, quiet at the default level); a console control handler on Windows. Each is a line in TASKS.md if a profile ever points at it.

## Impact

- **Toolkit** (`posix-host/portability`, from 88874d6):
  - `src/kernel/xbox_memory_layout.c`: the trace arming, the report gate, the one-call DMA_PUT line, the kernel summary in the watchdog report.
  - `src/kernel/nv2a_pb_exec.c`: `nv2a_pb_exec_report_dump()`, the report's picture without its text.
  - `src/kernel/kernel_bridge.c`: the `[READ]`/`[WRITE]` gate; the kernel summary as a once-at-exit report plus the periodic form under its key.
  - `src/platform/recomp_env.h`: the `FILE_TRACE` and `KERNEL_SUMMARY` rows.
- **Cat**: `src/pad_input.c` (the `input` gate), `scripts/vpad.py` (docstring), `docs/env.md`, TASKS.md, `analysis/upstream/pr-stack-plan.md`.
- **CLI**: nothing.
- **Behaviour**: no game-visible change. The output change is the trace itself: a default run no longer logs every kick, which is what every build before 5b1d8e9 printed, and the `[READ]`/`[WRITE]`, per-poll `[INPUT]` and periodic `[KERNEL]` lines move behind keys. The goldens (`RECOMP_TRACE=flip` plus `fb_dump_at`), `pacing-stats`, `audio-check` and `soak.py` read none of the gated lines.
- **Performance**: on native Windows the walker thread stops paying about 1,800 filtered writes a second; measured by the user's throwaway build as 1-2 p95 from 41-50 ms to 34-35 ms. Under Proton the same lines went away; the Deck passed all three goldens on today's main with the trace still on, so the Deck figure is a check, not a fix. The Mac held 30 already; its golden logs shrink by about 95%.
- **Backends**: shared host code; CPU, D3D11 and Metal agree by construction. Burnout 3 runs under Proton on the exact toolkit head before merge (the walker's poll is shared).
- **Upstream**: the trace arming fix and the one-call line go with G2 (the walker from GET to PUT), where the poll lives; upstream's own wiring is harmless there because its `PB_EXEC` is opt-in, so the PR text says so and offers the one-call line as hygiene. The `file` and `kernel_summary` keys are fork-only (`getenv` in the PR). The deferred writer, if built, is its own PR (design.md D4).
