## Context

**How output reaches the file today.** `cat/src/main.c` `host_stdio_setup` (line 1018) runs first thing in `main` and `WinMain`, after `recomp_env_init`. With `RECOMP_STDIO_LOG` set it truncates the file and `freopen`s stdout and stderr onto it in append mode on Windows (a GUI-subsystem exe starts with `_fileno(stderr) == -2`, so there is no descriptor to `dup2` onto), or `freopen`s stdout and `dup2`s it onto stderr elsewhere. Then `setvbuf(..., _IONBF, 0)` on both. Every packaged launcher sets the variable (CLI `package/templates/windows/launcher.c:188`, `steamos/launch.sh`, cat `packaging/macos/BLiNX2.in:58`), and the Proton bench does too (`bench/host/run_game.sh:24`). The Mac golden (`golden_run.py:331`) does not: it hands the child a file as stdout with stderr merged, which `_IONBF` turns into the same pattern of one write per call. The toolkit's template (`templates/new-game/src/main.c:306`) sets `_IONBF` the same way. Windows logs are CRLF (the CRT's text mode on the reopened streams).

So each `fprintf` is one `WriteFile` (or `write`) to the file, on the calling thread, under the FILE lock. The toolkit has 811 `fprintf(stderr)` sites, 182 `fflush(stderr)` calls and a dozen `fputs`/`vfprintf`; cat has 90 more. The only writer that bypasses stdio is the POSIX crash handler's `crash_printf` (main.c:163), which `write(2)`s to `STDERR_FILENO` because it may run while the faulting thread holds stdio's lock. Nothing calls `SDL_Log`.

**What a write costs.** Native Windows 11 with Defender: the profile's 33% of the walker's samples for about 1,800 writes a second is about 180 us per write, whatever its length, through FLTMGR and `WdFilter`. The Mac: APFS writes of a line are microseconds; the Mac held 30 fps with the trace on (the user, 2026-10-13). Proton: a file write is a `write(2)` on Wine's cached unix fd; the apu-voice-lock measurements saw 2-8 ms for a 40-line burst under Proton with the APU trace on, so tens of microseconds a line, and the Deck passed all three goldens today with the trace on.

**The hot line.** The walker thread (`nv2a-ack`, `xbox_memory_layout.c:1640`) polls the NV2A registers. When `DMA_PUT` moves it walks the segment, sets `DMA_GET`, ticks the fence, and, under `s_nv2a_trace` (line 1817), prints the `[NV2A] <ms> DMA_PUT/DMA_GET/fence` line in four `fprintf` calls followed by an `fflush` that runs on every kick whether traced or not (line 1831). Under the same flag it prints `PCRTC_START` changes (1834), runs the once-a-second display framebuffer checksum (`framebuffer_probe_tick`, 1486, 1.2 MB of reads), and calls `nv2a_pb_scan_report()` every `pb_report_ms` (1787; default 10 s). The flag is set at 3612:

```c
s_nv2a_trace = recomp_env(RENV_NV2A_TRACE) != NULL
            || recomp_env(RENV_PB_SCAN) != NULL
            || recomp_env(RENV_PB_EXEC) != NULL;
```

and `recomp_env.c:272` makes `RENV_PB_EXEC` default on (5b1d8e9), so the trace is on in every run. The executor itself never reads `s_nv2a_trace`: `nv2a_pb_scan` arms from `RENV_PB_EXEC`/`RENV_PB_SCAN` on its own (`nv2a_pb_scan.c:308`), and the poll's comment at 1711 records that the scan call was deliberately taken out from under the trace flag. The title's D3D spins on the KickOff bit (0x002E7F20) until this thread clears it after the walk, so every microsecond the walker spends in `fprintf` is a microsecond the guest's frame waits.

**What the periodic report does.** `nv2a_pb_scan_report()` (`nv2a_pb_scan.c:187`) calls `nv2a_pb_exec_report()` (the `[GPU] surface/draws/index batches/semaphore/...` block plus `vsh_report`, `[TEXUSE]`, and, when `fb_dump` is set, one numbered `<prefix>NNN.bmp` through `dump_present_bmp`/`dump_surface_bmp`, `nv2a_pb_exec.c:6464-6508`), then the `[PB]` survey, which is already self-gated on `pb_scan`. Nothing parses that block: the goldens read `[GPU] flip N ... batches B` (`RECOMP_TRACE=flip`, `nv2a_pb_exec.c:6172`, and the backends' `[METAL]`/`[D3D11] flip` lines) and take their frames from `fb_dump_at` (`dump_at_flip`, flip-named, independent of the report); `pacing-stats` reads `[PACING]` and `[NV2A] vblank`; `audio-check` reads `[APU]`; `soak.py` reads `[GPU] flip` and `[INPUT] ... script done`; `shots/run.sh` and `soak.py` use `fb_dump_flips`. The numbered report pictures have no consumer.

**The `[KERNEL] summary` block** (`kernel_bridge.c:10826-10855`): every 2 s, on whichever guest thread's kernel call lands on the tick, one line with the cumulative call count, the ordinal that call happened to be ("latest names whatever the sample happened to land on", the comment says) and esp, then the six most-called ordinals since boot. In the Windows log the six are the same every time after boot: 277 and 294 (`RtlEnter`/`LeaveCriticalSection`, 480k each), then 184 and the rest, so 368 blocks said one thing. The hang and crash paths do not print it: the watchdog prints esp, the registers, the ICALL ring, the peek sample, the NV2A pointers and the guest stack (`xbox_memory_layout.c:2770`); the crash report prints registers, the guest chain and the ICALL ring; the thread dumps print native stacks. No note, spec, TASKS or RESUME entry has used the block (the only hits under `notes/` are raw logs). Its value is the one question the comment names, what an idle title asks the kernel for, which the cumulative counts answer once.

**The Windows log, by shape** (`runs/win11/20261014/game-20261014-125152.log`, 647 s, 308,303 lines; leading digits folded):

| lines | shape | source | rate |
|---|---|---|---|
| 288k | `[NV2A] N ms DMA_PUT = ... DMA_GET = ... fence ...` | `xbox_memory_layout.c:1822`, walker thread | 445/s, one per kick |
| 6.4k | `[INPUT] t=N.N host port=0 buttons=...` | cat `pad_input.c:1066`, guest thread, one per poll in which a host pad's state changed (a stick that moves at all changes every poll) | about 10/s with a pad in hand |
| 2.6k | `[KERNEL] summary: ...` + 6 `[KERNEL]   ordinal N xM` | `kernel_bridge.c:10830`, guest thread, every 2 s | 3.5/s |
| ~2k | `[READ] from=... buf=... ev=... apc=...` | `kernel_bridge.c:4700`, every NtReadFile with an event or APC | bursts at loads |
| ~1.6k | `[WRITE] from=... buf=... @N len=...` | `kernel_bridge.c:4767`, every NtWriteFile of 4 KB or more | bursts at saves (the 1-2 checkpoint) |
| 1.3k | `[INPUT] rumble port=0 left=N right=N sent` | cat `pad_input.c:1357`, one per change of the motor words | 30/s while a rumble plays |
| 953 | `[PATH] \Device\Harddisk0\...` | `kernel_path.c:559`, one per path translation | bursts at loads |
| 720 | `[FILE] z:\... (disp N opts ...) -> 0x...` | `kernel_bridge.c:4235`, one per NtCreateFile | bursts at loads |
| 64 x ~20 | the `[GPU]`/`[VSH]`/`[d3d11] present #N` report blocks | the periodic report, every 10 s | 2/s |
| 64 | `[NV2A] vblank N: last 600 in ...` | `kernel_bridge.c:3067`, every 600 vblanks; `pacing-stats` reads it | 0.1/s |

**The throwaway build** (the user, 2026-10-14; `game-20261014-131844.log` before, `-140530.log` after, same route, scale 1, `RECOMP_TRACE=pacing,apu`): with the DMA_PUT line silenced, 1-2 p95 went from 37-50 ms to 34.2-34.9 ms in 15 of 18 windows, with three windows at 40-42 ms; process CPU from 112-184% to 91-152%; the log from 19.3 MB to 4.4 MB. The after-log's shapes: 82.5k `[APU] voice N pos=` and 2.3k `[APU-VSTAT]` (the `apu` trace, about 140 lines a second, synchronous, on the APU frame thread), 5k `[INPUT] host port`, 1.6k `[KERNEL] ordinal`, 1.4k `[APUMMIO-HIST]`, 1.1k rumble, 740 `[PATH]`, 720 `[FILE]`. So about 150 synchronous lines a second on this host cost nothing visible in the frame times.

## Goals / Non-Goals

**Goals**
- The NV2A per-kick trace, the PCRTC line, the framebuffer probe and the periodic report run only when a trace key asks (BLX-111), and the stall timeline stays one key away.
- A default run prints under five lines a second in steady state and tens in a load, each line a whole line.
- The crash report, the `unimpl_trap` line, the watchdog's report and the tools that tail a running log keep working as they do.
- The async writer's design stays on file with the evidence that would start it.

**Non-Goals**
- Changing the content or format of any line that stays.
- `xbox_kernel.log` (a second file written by `xbox_log` with a flush per line under its own critical section; quiet at the default level).
- A console control handler on Windows (the packaged exe is GUI-subsystem and gets none).

## Recommendation: gating now, the writer deferred

The user asked whether a pipe plus a writer thread, with a sync-token flush on every exit path, is worth its complexity and risk once the trace is gated and the rest quieted. Weighed against the evidence in Context:

- **(a) Gating alone.** What the throwaway build measured: 1-2 p95 from 41-50 ms to 34-35 ms, with about 150 synchronous lines a second still printing. After D1 and D2 a default run prints under five lines a second. At 180 us a write on the slowest host that is about a millisecond a second, spread over threads. The bursts that remain are boot (a few hundred lines, once), loads (hundreds of `[PATH]`/`[FILE]` lines inside a load that takes seconds: tens of milliseconds nobody sees), the checkpoint save (a handful of opens; the `[WRITE]` records that landed on that moment are gated), and the exit. A hitch mid-play would need a burst of about 100 lines on a game thread to cost one frame; nothing in the default output does that any more. The three 40-42 ms windows in the after-run have no log burst to blame: that log still carried 140 trace lines a second without trouble, and the default output is thirty times quieter than that.
- **(b) Gating plus a full stdio buffer, flushed from the crash, exit and watchdog paths.** The 182 `fflush(stderr)` calls that follow lines make most of them synchronous anyway, so it buys little; what it does buffer arrives late for the tools that tail a run (`FlipLog`, `soak.py`), stdout's boot banner would land at the end of the file unless kept unbuffered on its own, the FILE lock is held across the write so other threads' `fprintf` wait on it, and `fflush` from a signal handler is the deadlock the crash handler's `write(2)` path exists to avoid. No.
- **(c) Gating plus a writer thread for hot lines only, no pipe.** A queue behind a `recomp_log_line()` call with the hot sites converted: fewer moving parts than the pipe (no fd games, no token straddling, the crash path drains the queue itself), but it splits the log into two paths whose order can invert by the writer's latency, and the lines it would carry are exactly the traces whose point is order (`[NV2A]` gaps against `[APU]` and `[PACING]` lines). Only worth it for a trace where the writes themselves distort the measurement, which is the second trigger below.
- **The pipe design (D4, deferred).** The complete answer: every site unchanged, order kept, crash and exit covered. Its risks are the ones the user lists: a flush protocol on seven exit paths, Wine's pipe behaviour, lost lines on a kill, Windows' `-2` descriptor, and about 300 lines of platform code plus a ctest to review. Against a benefit a default run no longer has.

**Recommendation: (a), with D2's quieting and D3's one-call lines, and the writer as a designed follow-up.** Traces turned on for bug reports: `flip` and `pacing` print 30 lines a second (5 ms a second on Windows, nothing); `apu` printed 140 a second in the after-run without moving the frame times; `nv2a` brings the 445-a-second line back on the walker, on purpose, and a bug report that needs it is an investigation, where the person knows the trace costs frame time on Windows (`docs/env.md` says so in the row). The Deck is the other slow host; it passed the goldens with the trace on, and D1 removes that cost there too.

**Evidence that would change it, either one:**
1. A default-run profile (WPR on Windows, `perf` on the Deck) with 5% or more of any game thread's samples under the log's write path, or a frame-time spike that lines up with a burst in the same log (`[PACING]` window against line timestamps).
2. An investigation on Windows or Proton that needs a high-rate trace (`nv2a`, `apu`, the kernel call trace) and finds the writes perturbing what it measures, the way BLX-108's `apu` trace inflated the lock figures under Wine. Then D4 as written (or (c) for that one trace, if ordering against other lines does not matter to it).

## Decisions

### D1. BLX-111: the NV2A trace follows `nv2a` alone

`xbox_memory_layout.c:3612` becomes `s_nv2a_trace = recomp_env(RENV_NV2A_TRACE) != NULL;` with the comment saying why `PB_EXEC` left (5b1d8e9 made it default on; the executor reads its own key). What follows the flag, and what each needs:

- **The DMA_PUT line** (1817): trace-only, and one call: `snprintf` of the whole line (ms, PUT, GET, fence or `-`, the `(GPU behind)` suffix) into a 128-byte stack buffer, then `fputs`. The `fflush(stderr)` at 1831 moves inside the `if`. This is the stall timeline BLX-110 used (a gap between two lines is the GPU side standing still, time-stamped by `xbox_log_ms` like the `[GPU] flip` line): `RECOMP_TRACE=nv2a` brings it back unchanged, and `blinx2 bench ... BENCH_ENV="RECOMP_TRACE=nv2a"` is how a pacing run asks for it.
- **`PCRTC_START`** (1834) and **`framebuffer_probe_tick`** (1486): trace-only; unchanged otherwise. The probe's 1.2 MB checksum a second on the walker goes with it.
- **The periodic report** (1787): today `if (s_nv2a_trace && interval elapsed) nv2a_pb_scan_report();`. Becomes

  ```c
  if (now_ms - last_report > (uint64_t)report_ms) {
      last_report = now_ms;
      if (s_nv2a_trace || recomp_env(RENV_PB_SCAN))
          nv2a_pb_scan_report();            /* [GPU] block, [PB] survey, picture */
      else if (recomp_env(RENV_FB_DUMP))
          nv2a_pb_exec_report_dump();       /* the picture without the text */
  }
  ```

  `nv2a_pb_exec_report_dump()` is the `dump_present_bmp()`/`dump_surface_bmp()` choice lifted out of `nv2a_pb_exec_report` (6505-6508) into its own function, which the report calls too. So `pb_scan` keeps arming the `[GPU]` block as it does today (it armed `s_nv2a_trace`), `fb_dump` alone keeps its periodic numbered picture (the `fb_dump` row promises "frame dumps"), `pb_report_ms` keeps both meanings, and a default run prints none of it. `RENV_PB_SCAN`/`RENV_FB_DUMP` are cached array loads (`recomp_env.h`), so reading them in the poll costs nothing.
- **What does not change:** `s_pb_exec` and the scan's own arming (`nv2a_pb_scan.c:308`), the fence mirrors, the flip hold, `nv2a_pb_poll`, the `[GPU] flip` line (`RECOMP_TRACE=flip`), `dump_at_flip` and `fb_dump_flips`, the `[NV2A] vblank` line, `pb_wrap`. The goldens (`RECOMP_TRACE=flip` plus `fb_dump_at`) and the bench's pacing scenarios (`flip,pacing=all`) touch none of the gated output.

**env.md** rows reworded: `nv2a` ("NV2A register poll: one `[NV2A] <ms> DMA_PUT/DMA_GET/fence` line per pushbuffer kick (the stall timeline; on native Windows each line is a filtered file write of about 0.2 ms on the walker, so expect the frame times it is used to measure to move), `PCRTC_START` changes, the once-a-second framebuffer checksum, and the periodic `[GPU]`/`[PB]` report with its `fb_dump` picture. Until async-log-writer `RECOMP_PB_EXEC` armed it too, so every run logged every kick (BLX-111)"), `pb_scan` ("... also arms the periodic `[GPU]` report"), `pb_report_ms` ("the periodic report under `nv2a` or `pb_scan`; with neither and `fb_dump` set, the picture alone"), and `RECOMP_PB_EXEC` loses its two `xbox_memory_layout.c` read sites.

### D2. Default output: what goes behind a key

From the table in Context, by rate and by what reads it:

- **`[INPUT] ... host port=` and `[INPUT] rumble`** (cat `pad_input.c:1062`, `1357`): per poll while a stick moves, per frame while a rumble plays. Gated under the game's existing `RECOMP_TRACE=input` ("pad handles and states"; the `handles=` line already is). The `ports=` change line, the script's `[INPUT] ... script done` (`soak.py` reads it) and the scripted-pad `buttons=` line stay as they are. `vpad.py`'s docstring says its latency subtraction needs `RECOMP_TRACE=input` on the game side.
- **`[READ]` and `[WRITE]`** (`kernel_bridge.c:4700`, `4767`): per-call records from bring-up, two thousand lines in a load and hundreds in the 1-2 checkpoint save, on the guest thread. Gated under a new toolkit trace key `file` (`RENV_FILE_TRACE`, TRACE tier: "`[READ]`/`[WRITE]` records per NtReadFile/NtWriteFile call: caller, buffer, offset, length, status and the first bytes"). `[PATH]` and `[FILE]` (one per open) stay: they say what the title opened, at a rate that only matters for log size.
- **`[KERNEL] summary`** (`kernel_bridge.c:10826`): the periodic block goes behind a new trace key `kernel_summary` (`RENV_KERNEL_SUMMARY`, TRACE tier: "the 2 s `[KERNEL] summary` block: cumulative calls, the ordinal the tick landed on, esp, the six most-called ordinals"). Its information is kept where it is worth having: **once at exit**, the same block printed by a `kernel_summary_report(const char *why)` registered with `atexit` and `recomp_exit_hook_add` (one of the three free slots; a print-once guard, as the missing-file summary has), and called from the bridge's `HalReturnToFirmware` path beside `xbox_missing_summary("firmware")` so the firmware exit on Windows gets it before `ExitProcess`; and **in the watchdog's hang report** (`xbox_memory_layout.c` after the ICALL ring), where "the ordinal the last call was" and the counts are exactly the hang question, through the same function. The ordinal counts are the title's whole-run profile of kernel use, which is what a bug report wants and what 368 copies never said better.
- **Left alone, with the reason:** `[NV2A] vblank` (`pacing-stats` reads it); the `[d3d11] present #N` line every 300 presents; the boot-time `[KERNEL] #N` lines (budgeted to 200); `[PATH]` and `[FILE]`. After D1 and D2 a default run prints under five lines a second in steady state and tens in a load, from 450.

### D3. stdio stays unbuffered and synchronous; hot lines are one call

Both streams keep `_IONBF`: a line is one write, nothing sits in a stdio buffer when the process dies, the crash report and the `unimpl_trap` line reach the file as they do today, and the tools that tail a run see a line when it is printed. The cost is the per-write price in Context, which at the rates D1 and D2 leave is about a millisecond a second on the slowest host. The one hot multi-call line, the walker's DMA_PUT line, becomes one `fprintf` (D1), so when it is on it costs one write and cannot tear against another thread's line.

### D4. Deferred: the async writer

Kept here so the follow-up starts from a design, not a ticket. The complete version is in this change's first revision (`spec/async-log-writer` 7fd609a, design.md D1-D3 and Validation). The shape:

- **Capture at the descriptor.** `src/platform/recomp_log.{c,h}` in the `recomp_env` library. After the host has pointed both streams at the log file, `recomp_log_start()` dups that file as the sink (binary mode on Windows: the CRT's CRLF translation happens on the way into the pipe), creates a pipe (1 MB where the OS takes it; 64 KB on macOS), puts its write end under fds 1 and 2 (`dup2`; on Windows `_open_osfhandle` + `_dup2` + `SetStdHandle`, returning 0 and leaving stdio alone when `_fileno(stderr) == -2`), and starts one detached `log-writer` thread that copies the pipe to the sink in 256 KB batches (read, drain what else is there, one write; no timer, no allocation, no stdio inside). Every call site, `write(2)` and library line is carried unchanged and in order; a game thread pays one pipe write per call, and waits only if the pipe fills during one sink write. Both streams stay `_IONBF`. The host starts it unless `RECOMP_DEBUG=log_sync`; the writer reads no environment.
- **Flush by sync token.** `recomp_log_flush(ms)` writes 16 NUL-prefixed bytes with a sequence number into the pipe and waits (atomic loads, 1 ms naps, async-signal-safe) until the writer, which scans batches for the token (it may straddle two reads), has written everything before it and publishes the sequence. On timeout the caller writes one `[LOG] flush timed out` line straight to the sink (`recomp_log_sink_write`). It runs from `atexit` (registered first in the host so later handlers' output is carried), at the end of `recomp_exit_hook_run` (the Win32 windows' `WM_CLOSE` before `ExitProcess`), before the four `ExitProcess` calls in `kernel_hal.c`, before the watchdog's `_exit`, from a SIGABRT handler the writer installs (so `unimpl_trap`'s `abort()` keeps its last line), and from both crash handlers after their report (500 ms). A kill from outside loses the pipe and the batch in flight.
- **Drops counted.** A failed sink write drops the batch, counts lines and bytes, keeps draining so nothing blocks, and reports `[LOG] dropped N lines` before the next batch and a total at the next flush; `recomp_log_stats` exposes the counters.
- **Tests.** A standalone ctest `tests/log_writer`: ordering across four threads and both streams, flush at exit, from a crash handler, from `abort()`, a 32 KB burst with the writer stalled 200 ms returning in under 50 ms, drop counting through a fault-injection hook, and the negative control; on `posix_ctest.sh` and the CLI's Proton standalone list. Exe-level: a normal quit's exit lines last, `unimpl_trap`'s line last, `log_sync` restoring the old path. An A/B with `log_sync` as the control.
- **Upstream.** Self-contained C11 with MSVC branches, its own small PR, `getenv` for the key.

### Options weighed

See Recommendation: (a) chosen; (b) rejected (late lines, held FILE lock, `fflush` from a signal handler, stdout ordering); (c) deferred as the cheaper form for a single distorting trace; the pipe deferred as the complete form.

## Upstream

Toolkit code (CLAUDE.md; `analysis/upstream/pr-stack-plan.md`).

- **Upstream-first.** Upstream has the `PB_EXEC`-armed trace (the v0.7.0 wiring), harmless there because its `PB_EXEC` is opt-in, and the four-call line. Nothing to prefer.
- **Placement.** The arming change and the one-call line go with G2 (the walker from GET to PUT), where the poll lives; the PR text says the fork made `PB_EXEC` default on and why the trace must not follow it. The `file` and `kernel_summary` keys are fork-only (`getenv` in the PR); the `[READ]`/`[WRITE]` gate and the exit-time kernel summary are offered with PR 3 (kernel objects and files) if upstream wants quieter defaults, else fork-only. The deferred writer, if built, is its own PR.
- **Burnout 3 gate.** Required before merge (Validation): the walker's poll is shared.

## Risks / Trade-offs

- **The trace comes back by accident.** `nv2a` is a trace key; `pb_scan` and `fb_dump` arm only the periodic report and its picture, which is what they did through `s_nv2a_trace` before, minus the kick line. The golden env pins neither.
- **A burst that still costs a frame.** The remaining default bursts are at boot, in loads and at exit; D2's rates are the argument. The first trigger in Recommendation is the check.
- **`[READ]`/`[WRITE]` and the periodic `[KERNEL]` block go quiet.** No script reads them; the keys bring them back, and the exit and watchdog reports keep the kernel counts.
- **A user's trace run on Windows is slower.** By design and documented in the `nv2a` row; `flip` and `pacing` stay cheap.

## Validation

- **Mac build**, then `tests/posix_ctest.sh <build-dir>` with 0 FAIL (no new test: the change is gates and a report; `pytest tools/recomp tools/disasm` not needed).
- **Mac Metal**: `blinx2 golden run` (attract, stage1, story) unchanged; `audio-check` against the previous golden. Note the golden logs' size before and after. A default run's log: no `[NV2A] ... DMA_PUT`, `PCRTC_START`, `[GPU] surface`, `[READ]`, `[WRITE]` or periodic `[KERNEL] summary` line; the `[KERNEL] summary` block once at the end; `RECOMP_TRACE=nv2a` brings the kick line back one per kick; `RECOMP_TRACE=kernel_summary` the 2 s block; `RECOMP_DEBUG=fb_dump=<p>` alone writes `<p>NNN.bmp` every 10 s with no `[GPU]` text; `RECOMP_DEBUG=unimpl_trap` ends the log with the `[UNIMPL]` line.
- **Proton (Deck or the Linux/Proton host)**: `blinx2 bench integrate --golden` (tests, the three D3D11 goldens); the watchdog's report shows the kernel summary (`RECOMP_DEBUG=watchdog` on a run that is left to time out).
- **Native Windows**: one run of the merged build on the 1-2 route with `RECOMP_TRACE=pacing` (`blinx2 pacing-stats`): 1-2 p95 within 1-1's band (34-37 ms) as the throwaway build showed, and the log under 5 MB for ten minutes; the user's by-ear check of the sound. The throwaway pair (`-131844` before, `-140530` after) is the recorded A/B. Flag a 25% flips/s drop or 1.5x frame-ms rise as a blocker.
- **Burnout 3 under Proton** on the exact toolkit head: boot, front end, one race; the log ends with the exit lines and the kernel summary.
- **Gates**: the above, `uv run pytest scripts` and ruff in cat, the Opus review.
