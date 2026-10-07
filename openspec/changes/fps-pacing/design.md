# Design: fps-pacing (v1: lock30 plus smoother pacing)

## Context

The spike's sketch (`spike/fps:openspec/changes/fps-modes-spike/v1-pacing-proposal.md`) was written against toolkit 48a6483. Since then the toolkit has moved to 81be009 (the CAMetalLayer present, guest write-back on demand, plain window title). Every file and line below was re-read on `posix-host/portability` at 81be009 and cat `main` at 4228612.

How a BLiNX 2 frame is paced today:
1. `sub_0005F960` (loop head `0x602D0`) zeroes the vblank counter `[0xAE7388]` and stores the wait `[0x3FD344]`: 2 in 3D, 1 in menus.
2. It runs the frame.
3. It spins at `0x00060475` until the counter reaches the wait, then calls Swap (`sub_002E6FE0`).
4. The counter is bumped by the title's vblank callback `sub_000604A0`. That callback runs from D3D's vblank DPC, which the kernel timer thread drains right after it raises vector 3 (`kernel_bridge.c`: `kernel_vblank_tick` ~2804, `kernel_drain_dpcs` ~2922, `kernel_timer_thread` ~3193).

So a 3D flip lands on the second vblank after the frame starts. Its interval is two vblank gaps, plus however late the DPC runs.

The lifted spin (`gen/recomp_0010.c`, `loc_00060475`) is:

```c
loc_00060475: ;
    _fa = (uint32_t)(MEM32(0xAE7388)) ...; _fb = (uint32_t)(eax) ...;   /* cmp MEM32(0xAE7388), eax */
    _cf = (int)(_fa < _fb);
    if (CMP_L(_fas, _fbs)) goto loc_00060475; /* jl */
```

`MEM32` is a volatile load (`templates/runtime/recomp_types.h:455`), so the loop is correct but hot. The compare register is loaded before the label (`eax = MEM32(0x3FD344)`), so the loop block itself is `cmp [0xAE7388], eax; jl`. The same VA appears in 261 emitted function bodies (124 in `recomp_0010.c`, 137 in `recomp_0011.c`, one label and one back edge each). They are the interior entries of `sub_0005F960` (`sub_0005F972`, `sub_0005F99F`, ...) that the lifter emits as functions of their own. Lowering therefore works per VA, never per function.

The one-CPU gate (`kernel_hal.c`): a thread's IRQL is thread-local, `t_irql_counted` says whether this thread is in `g_irql_raised_count`, and `t_dispatch_gate_held` says whether this thread took the gate on its raise. Both exist today; neither is exported. `KfLowerIrql` releases the gate but does not drain DPCs, so a DPC queued behind a busy gate runs only when the timer thread next polls. That is what the 1 ms retry (D2) is for.

The timer thread today:
- sleeps `Sleep(ms)` (`timeBeginPeriod(1)` on Windows);
- returns the next vblank in whole ms from a schedule `t0 + count*1000/60` ms on `kernel_clock_ms()`;
- caps each sleep at 10 ms;
- drains DPCs only when `xbox_DispatchGateTryEnter()` succeeds, and otherwise leaves them for the next pass.

The 600-vblank line already measures gaps on the performance counter (`gap a-b ms`, the window's minimum and maximum). In `runs/fpsspike/hold-lock30` (12 windows, Mac Metal) the typical window is 12.1-20.9 ms and the stage load's is 1.7-46.4 ms; no schedule restart was logged. `kernel_clock_ms` is already the performance counter truncated to milliseconds, so the ms and ns schedules share one time source; the loss is in the truncation and in `Sleep(ms)`.

## Goals / Non-Goals

**Goals**
- The guest main thread's CPU while it waits for a vblank drops from about one core to near zero, under `present.pacing = "sleep"`.
- Flip intervals in stock 3D tighten around 33.3 ms on Metal and on D3D11 under Proton, with no change in game speed or in the frames.
- `fps.mode` exists and tells the truth.
- The spin-wait lowering is title-agnostic and opt-in, so it can go upstream.
- Every stock path (pacing `spin`, no generator flag) behaves as before. Goldens pass unchanged.

**Non-Goals**
- `lock60` and `free` gameplay, frame interpolation, turbo. The user decided against all three on 2026-10-05. The 60 fps mod stays a separate cat-only investigation (`mod60.md`).
- D3D11 present vsync. The SDL and Metal presenters already follow `RECOMP_PRESENT_VSYNC`. D3D11 still calls `Present(0, 0)` (`nv2a_pb_d3d11.c:3104`). That is an existing presentation difference: it only causes tearing and does not set the cadence. It is recorded as a TASKS follow-up, not done here.
- Retiring the `BlockUntilVerticalBlank` 60 Hz pacer (`recomp_manual.c` `sub_002E0DB0`) by putting it on the kernel's vblank edges. See Decided, 3.
- The stage-loader yield loop (`sub_0005E3C0` → `NtYieldExecution`, hot-threads §1b). It calls the kernel, so it is not a memory self-loop and is not matched. It is a separate follow-up.
- Vblank from a real present (E3), the exit of the "Vertical blank from the host timer" deviation.

## Decisions

### D1. Two independent parts, with the clock unconditional

The jitter comes from the clock and the DPC timing (D2). The CPU cost comes from the spin (D3-D5). They ship as separate commits and are measured separately:
- The **nanosecond clock** is a fix to existing toolkit behaviour, for every title. It does not change what the guest observes beyond timing precision. It has no enhance key, so it applies with or without the layer. `RECOMP_DEBUG=vblank_clock=ms` keeps the old loop for A/B runs and for bisecting.
- The **sleeping wait** is an opt-in enhancement (D5, D6).

*Alternative:* gate the clock behind `present.pacing` too. Rejected: a more precise version of an existing schedule is a fix, not a feature. Gating it would leave stock jitter in place for every user and for Burnout 3. The debug key covers rollback.

*The price of being unconditional* (Decided, 2): there is no key to hide behind, so the clock's own merge gate is stricter than an enhancement's. The toolkit branch merges only when, at `spin`, the Metal and D3D11 goldens give every frame the same verdict as main (8.3, 8.4), `audio_check.py` shows no new starves (8.8), and the fork's Burnout 3 smoke under Proton runs boot → menu → race at the same pace (8.9, required). A changed verdict blocks the merge until it is explained; it is not recorded and carried.

### D2. Nanosecond vblank schedule and timer loop

- **Clock.** `xbox_HostNowNs()` and `xbox_HostSleepNs(ns)` move into the toolkit's platform layer.
  - `xbox_HostNowNs` is QPC on Windows and `CLOCK_MONOTONIC` on POSIX.
  - `xbox_HostSleepNs` uses a per-thread high-resolution waitable timer on Windows (with a `Sleep` fallback) and `nanosleep` on POSIX.

  This is the code cat already has in `recomp_manual.c` (`host_now_ns`, `host_sleep_ns`), which then calls the toolkit's copy instead of its own. On Windows `xbox_HostNowNs` reads the same performance counter as `kernel_clock_ms`, so kernel timers (still in ms) and the vblank schedule (ns) are compared on one clock. A sleep may return early or late; the loop never trusts it and re-reads the clock against the absolute schedule.
- **Schedule.** Vblank N is due at `t0 + N * 1e9 / 60` ns, computed as `t0 + (N * 1000000000) / 60` in 64-bit integers so it never drifts (N × 10⁹ overflows a signed 64-bit value only after 4.9 years of vblanks; the restart rule resets N long before).
  - The 100 ms restart rule stays, measured in ns.
  - `kernel_vblank_tick` returns nanoseconds to the next edge.
  - The schedule arithmetic is a pure function (`xbox_VblankSchedule(state, now_ns) -> {fire, restart, next_due_ns}`), exported through `kernel.h` the way `vblank_ack` exports its ack step, so a ctest can drive it with fake times.
- **Timer loop.** The sleep target is the earliest of three times:
  - the next vblank edge;
  - the earliest due kernel timer (kernel timers keep their ms `due_ms`, converted when compared);
  - `now + 10 ms`, the existing cap.

  The loop sleeps with `xbox_HostSleepNs`. The profiler's `SLEEP_OVER` counter keeps working, in µs.
- **Gate-busy retry.** When `kernel_drain_dpcs` stops because the gate is busy and DPCs remain queued, the next sleep is capped at 1 ms. The drain still never waits for the gate, which is the dpc-stall rule; it only polls sooner. The `drains gate-busy` profiler counter shows how often this happens.
- **Unchanged.**
  - The vblank is raised only while `PCRTC_INTR_EN_0` enables it.
  - `g_vbl_tick_busy` is set around the raise.
  - The ack is armed for claimed and declined vblanks alike, and the vblank-ack thread owns the PMC and PCRTC bits.
  - The nv2a-ack backstop (`VBL_ACK_LATE_MS`) stays.
  - The 600-vblank line format stays, and `bench` and golden parsers depend on it.
- **`vblank_clock=ms`** (debug tier) restores the whole previous loop: the ms schedule, `Sleep(ms)` and the 10 ms re-poll after a gate-busy drain.
- **An on-time wake on macOS** (Decided, 7). At the start of the ns loop, `xbox_HostTimerThreadInit()` gives the timer thread a Mach time-constraint policy where the host offers one, because a plain `nanosleep` there overshot by 3.7 ms on average (8 ms at worst) at every QoS class. Other hosts are unchanged.

*Expected effect:* gaps within ±0.5 ms of 16.67 ms when the host is not stalled. (The first draft expected macOS `nanosleep` to overshoot by tens of µs on an idle core; it measured 3.7 ms on average, hence the time-constraint policy above.) DPCs stop slipping by up to 10 ms behind a busy gate. The gate in D8 is wider than this expectation, because a 600-vblank window reports only its minimum and maximum, and one late wake marks a whole window.

### D3. Spin-wait detection in the generator (`tools/recomp`, opt-in)

- **Flag.** `--spin-waits FILE`. Without it the matcher does not run, and the output is byte-identical to today's. A pytest case compares the two outputs.
- **Where it runs.** On decoded instructions, in `translator.py`'s block pass, before emission. A candidate is a basic block B, starting at L, that ends in a conditional jump to L (a self-loop). Every other instruction in B must be one of:
  - `cmp` or `test` with at least one memory operand, or with a register that B loads from memory;
  - `mov reg, [mem]` or `mov reg, imm` into a register that no address expression in B uses;
  - `pause` (`rep nop`).
- **Rejected** if anything in B:
  - stores to memory, calls, pushes or pops;
  - uses a string op, a `lock` prefix, `in`/`out`, `cpuid`, `rdtsc` or an FPU op;
  - writes a register that an address expression in B uses;
  - reads no memory at all (a register-only loop is not a wait).

  Multi-block wait loops are out of scope for v1. A memory operand may be MMIO (a polled PGRAPH register reaches the host through the trap); it is still a read, and the 1 ms bound covers a register the kernel never signals.
- **Per body.** The matcher runs on each emitted body that contains the VA, because an interior entry is lifted as a body of its own and could in principle split the block differently. A listed site must match in every body that contains it; the first body where it does not stops the run, naming the body and the rule. The report counts bodies per candidate, and the lowering in every body is the same text.
- **Emission.** Only the back edge changes:

  ```c
  if (CMP_L(_fas, _fbs)) { RECOMP_SPIN_WAIT(0x00060475u); goto loc_00060475; } /* jl */
  ```

  The first test of the condition never waits. A wait runs only after the condition has been seen still true, so a loop whose condition is already false costs nothing extra.
- **`FILE`** is JSON (cat `config/spin_waits.json`, in the style of `seed_functions.json`):

  ```json
  { "auto": false,
    "sites": [ { "va": "0x00060475", "note": "main loop: wait for [0xAE7388] >= [0x3FD344]" } ],
    "exclude": [] }
  ```

  - `auto: true` lowers every candidate except those in `exclude`.
  - `auto: false` lowers only `sites`.
  - A listed site that is not a candidate stops the recomp run with an error naming the VA and the reason it failed the matcher. A site cannot be forced through a shape the matcher rejects.
- **Report.** The recomp run writes `spin_waits.json` into its `-o` directory. It lists every candidate VA with the number of bodies containing it, whether it was lowered, and why not.
- **Tests (pytest, `tools/recomp/test_spin_waits.py`).**
  - Positive shapes: `cmp [m], reg`, `cmp [m], imm`, `mov eax, [m]; test eax, eax`, with `pause`.
  - Negative shapes: a store in the body, a call, a modified address register, `lock cmpxchg`, register only, a two-block loop.
  - Config: `auto` with `exclude`, a list, and a listed non-candidate erroring.
  - The no-flag output byte-identical.
  - The emitted back edge compiles.

*Why the explicit list for BLiNX 2 in v1:* the loose scan of today's `gen/` finds about 150 self-loop VAs. Many of them are not vblank waits: the DSOUND GP-doorbell spin at `0x00334325` waits on the APU frame thread, and the sites in the D3D range (`0x002E7F20`, `0x002E7F70`, `0x002E8020`) are probably GPU-state or fence waits (not checked). `auto` is the title-agnostic mode and the one tested on Burnout 3. BLiNX 2 starts with `0x00060475` alone, and the report gives the list for later. A site is added only after the `pacing` trace shows it waking on signals rather than on timeouts.

### D4. Runtime macro and `xbox_SpinWait`

- **The macro**, in `templates/runtime/recomp_types.h`:

  ```c
  extern volatile int g_xbox_spin_sleep;
  void xbox_SpinWait(uint32_t va);
  #define RECOMP_SPIN_WAIT(va) do { if (g_xbox_spin_sleep) xbox_SpinWait(va); } while (0)
  ```

  Under `spin`, a lowered loop costs one extra load and a never-taken branch per pass. The guest sees no difference.
- **`xbox_SpinWait(va)`** (new `src/kernel/kernel_pacing.c`) waits on a generation counter: a counter plus a condition variable, through the existing `CONDITION_VARIABLE` / `SleepConditionVariableCS` (native on Windows, `pthread_cond` on POSIX via `win32_compat.c`).
  - Each thread remembers the last generation it saw.
  - If the generation moved since then, `xbox_SpinWait` returns at once, so the loop re-reads memory. Otherwise it waits until the generation moves or 1 ms passes.

  The protocol that makes this lossless: the waiter takes the lock, compares the generation with its last-seen value, and only while they are equal waits on the condition variable (which releases the lock atomically); on return it records the generation and releases the lock. The waker takes the lock, increments the generation, releases it and broadcasts. The generation is never read outside the lock. A write to guest memory that precedes a wake in program order (the DPC's store, then `xbox_IrqlLeaveInterrupt`) is therefore visible to the loop's next `MEM32` read after the wait returns, on x86-64 and on arm64, because the lock pairs the release with the acquire. A wake that arrives between the loop's memory read and the wait has already moved the generation, so it is never missed. The only waits that time out are those whose writer the kernel does not signal (D5).
- **Never sleeps** while the calling thread is at DISPATCH level or above, or holds the one-CPU gate. Both facts are thread-local in `kernel_hal.c` today (`t_irql_counted`, `t_dispatch_gate_held`) and are exported through one query, `xbox_IrqlThisThreadBlocksDpcs()`, placed beside `xbox_DispatchGateTryEnter`. Sleeping there would hold back the very DPC the loop waits for. Those calls return at once, which is stock behaviour, and are counted as dispatch skips. The BLiNX 2 site is at PASSIVE level: were it not, the DPC that moves its counter could never run and the stock loop would already hang.
- **The 1 ms timeout** bounds every wait. A site whose state the kernel never signals still advances, at most 1 ms late per pass. It is also the timeout in `vblank-held` (`PCRTC_INTR_EN_0` off), where no vblank ever comes.
- **Per-site counters** go in a small fixed open-addressing table keyed by VA, with atomic increments: waits, immediate returns, signalled wakes, timeouts, dispatch-level skips. When the table is full, further sites go to an "other" bucket.
- **Loop exits.** A timeout in the middle of a loop is normal: a vblank wait spans up to 16 of the 1 ms timeouts before the signal that ends it. What shows a missing wake point is how loops *leave*. Each thread keeps its last site, the last pass's outcome and the time it returned. On entry, if more than 500 µs has passed since that return, the previous pass was its loop's last: it counts on that site as `exit_wake` (woken, or returned at once) or `exit_timeout`. This costs two `xbox_HostNowNs` reads per pass (on entry, and at return), at `sleep` only. A loop's exit is counted at the thread's next wait, so the last loop before the process ends is not counted.

### D5. Wake sources (`xbox_SpinWake()`)

`xbox_SpinWake()` bumps the generation and broadcasts. It is called only when `g_xbox_spin_sleep` is set, so at `spin` it costs one load. It is called:
1. by the timer thread, after a pass that raised a vblank, ran a DPC or fired a timer;
2. in `xbox_IrqlLeaveInterrupt`, which every host-run ISR and DPC passes through on any thread (APU, OHCI, the vblank ISR);
3. by the executor, after it writes the fence word at a semaphore release, and by the ack tick, after it updates `0x400B10`, so that fence-polling sites can be lowered later.

The vblank site in BLiNX 2 needs only 1 and 2: the counter moves in the DPC. Source 2 already covers every ISR and DPC; source 1 adds the pass itself, so that a declined or not-callable vblank still wakes a waiter that polls the PCRTC bits. Writes by one guest thread to another are not signalled. On the console's one CPU such a wait only progresses through preemption, and the 1 ms timeout covers it. A site whose loops leave on the timeout more than 5% of the time shows up in the trace, and it either goes on `exclude` or gets a wake point at its writer, for example the APU frame thread's doorbell clear for `0x00334325`.

### D6. Keys

| Key | Where | Values | Default | Env | Tier |
|---|---|---|---|---|---|
| `present.pacing` | toolkit enhance layer | `"spin"` (stock), `"sleep"` | `"spin"` (D9 may flip it) | `RECOMP_PRESENT_PACING` | config, `RECOMP_ENV_ENHANCE_KEYS` |
| `fps.mode` | cat game key | `"lock30"`; `"lock60"`, `"free"` reported unavailable | `"lock30"` | `RECOMP_FPS_MODE` | config, `RECOMP_ENV_GAME_KEYS` |
| `pacing` | toolkit | `1`: summary every 600 flips; `all`: also one line per flip | off | `RECOMP_TRACE=pacing` | trace |
| `vblank_clock` | toolkit | `ms`: the previous timer loop | ns | `RECOMP_DEBUG=vblank_clock=ms` | debug |

- **`present.pacing`.** `xbox_enhance_init` reads it as a choice, logs it on the existing `[ENHANCE]` line (`... present.fullscreen=0 present.pacing=spin (display.aspect=4:3)`), and hands it to the kernel through `xbox_PacingSetMode()` before the guest starts. The kernel never links the layer. Without the layer, the mode stays `spin`.
- **`fps.mode`.**
  - Name: no code reads it today. The toolkit doc names its variable `RECOMP_FPS`, but the doc's own naming rule gives `RECOMP_FPS_MODE`, so the doc row is corrected, as was done for `RECOMP_DISPLAY_ASPECT`.
  - Reading: cat binds it with `enhance_cfg_bind_env("fps.mode", RENV_FPS_MODE)` and reads it with `enhance_cfg_choice` in `host_enhance_init` (`main.c`). For `lock30` it logs `[ENHANCE] fps.mode=lock30`. Otherwise it logs:

    ```
    [ENHANCE] fps.mode=lock60 not available for this title (stage logic advances a fixed 1/30 s per frame; see docs/env.md); using lock30
    ```

  - Effect: nothing. `lock30` is the game's own pacing.
- **Unused-key report.** `xbox_enhance_init` calls `enhance_cfg_report_unused()` itself today (`enhance.c:53`), before the title reads its own keys, so an `fps.mode` set in `enhance.toml` would be reported as unused. The call therefore moves to the title, after its own keys: cat `main.c` calls it right after `fps.mode`. This is what the layer's own doc already shows (`enhance-config.md`, the title example ends with `enhance_cfg_report_unused(); /* after the modules' init */`), so the change aligns the code with the doc. `enhance.h` and `enhance-config.md` say so.
- **Docs.**
  - `docs/env.md` gets rows for `RECOMP_PRESENT_PACING` and `RECOMP_FPS_MODE` (game) in Config, `pacing` in Trace and `vblank_clock` in Debug, and its tier counts are updated.
  - The toolkit's `enhance-config.md` key table, environment table and `[ENHANCE]` example are updated.
  - `enhance.toml` example:

    ```toml
    [present]
    pacing = "sleep"   # "spin" (stock busy-wait) or "sleep"
    [fps]
    mode = "lock30"    # lock60 and free are not available for this title
    ```

### D7. The `pacing` trace and measurement point

- **Measurement point.** The flip timestamp is taken in the executor at the flip, at the point that prints `[GPU] flip N T ms` (`nv2a_pb_exec.c` ~5866), with `xbox_HostNowNs`. CPU, D3D11 and Metal all pass through that point, so the trace is identical in meaning on every backend. No backend file changes.
- **Summary line.** Every 600 flips, from the walker thread:

  ```
  [PACING] flips 600: interval p5 32.9 p50 33.3 p95 33.8 max 35.1 ms; vblank gap 16.4-16.9 ms; cpu process 41%; mode sleep
  [PACING]   site 0x00060475: waits 13900 immediate 1000 wakes 3150 timeouts 9750 dispatch 0; exits wake 1198 timeout 2; cpu in-wait 1.2% thread 38%
  ```

  - **Process CPU** over the window comes from `GetProcessTimes` (Windows/Wine) or `getrusage`, as a share of one core.
  - **In-wait CPU** is the figure the sleep gate reads: the CPU time the calling thread accrues between entering and leaving `xbox_SpinWait`, as a share of the window's wall time. It is sampled on one call in 64 from the thread's own clock (`clock_gettime(CLOCK_THREAD_CPUTIME_ID)`; on Windows `GetThreadTimes`, since cycles have no fixed rate to turn into time) and scaled by 64. At `spin` it would be the whole wait; at `sleep` it is the wake and sleep overhead. The thread's total CPU share (`thread`) prints beside it so that the game work on the same thread is visible and is not mistaken for spinning. Wine's `GetThreadTimes` moves in 15.6 ms steps, so the Proton in-wait figure is coarse (unbiased over a window, noisy within one); the Proton gate therefore also reads the process-CPU drop between modes.
  - *Exits* are the loop exits of D4: `exits wake` loops that left on a signal or at once, `exits timeout` loops that left on the 1 ms timeout. Mid-loop timeouts are expected and reported in `timeouts`.
  - At `spin`, the site counters stay 0 (nothing calls `xbox_SpinWait`), and the line says `mode spin`. The interval and process-CPU figures still print, which is what makes the A/B possible.
- **`pacing=all`** adds `[PACING] flip N t_us batches B` per flip, so that `scripts/pacing_stats.py` can work on 3D flips only (D8). The `[GPU] flip` line has only ms resolution.

### D8. Measurement method and thresholds

- **Script.** `scripts/pacing_stats.py` (cat, stdlib, with a `scripts/test_pacing_stats.py`) reads a run log and reports, for 3D flips only, the following. It uses the bench-methodology movie-window rule: a flip with more than 2 batches that is not inside a movie window; until `fmv-playback` tags movie windows, batches > 2 alone.
  - flip interval p5/p50/p95/max;
  - flips/s;
  - CPU raster ms p50 (from the `[GPU] flip ... raster` field, CPU path);
  - the process, thread and in-wait CPU from the `[PACING]` summaries;
  - every 600-vblank gap window from the `[NV2A] vblank` lines, with the median spread and the share of windows within 16.67 ± 1.5 ms.
- **`bench.sh pacing A B`.** Under the run lock, it runs one scenario with two environments (default: `RECOMP_PRESENT_PACING=spin` against `sleep`), three runs each. It writes both logs and a `pacing-report.txt` into one `bench-logs/<stamp>/`.
- **Route and conditions.** `@stage1`, at stock resolution, with `RECOMP_TRACE=flip,pacing=all`, `RECOMP_ENHANCE_CONFIG=none`, on:
  - Mac Metal and Mac CPU (headless, `SDL_AUDIODRIVER=dummy`; no sound on the Mac);
  - Proton D3D11 and Proton CPU (windowed, sound on).

  The Mac uses `pacing_stats.py` directly, with runs under `runs/pacing/`. The statistics window is the 3D flips after the stage-1 checkpoint (the script finds it the way `golden.py` does, from the batch counts), and each run holds at least 1,000 of them (about 35 s of 3D; the spike's sheet used 1,399). A statistic for an arm is the median of its three runs; an arm's *spread* for a statistic is the range of its three runs, widened by 2% of the value for flips/s and by 0.5 ms for an interval percentile, because three runs under-estimate the true run-to-run range.
- **Flags.** Recorded, not automatic fails:
  - flips/s at `sleep` 25% or more below `spin`;
  - CPU raster ms p50 at 1.5x or more of `spin`.

  Either one blocks the default flip (D9) until it is explained. The CPU path is tracked but is low priority, as the perf rules say.
- **Gates** (Decided, 6). Each is read on Metal and on Proton D3D11; the CPU paths are recorded, not gated.
  - *Clock gate*, both arms at `spin`, the `vblank_clock=ms` arm against the ns arm. On the Mac this measures the ns schedule plus the timer thread's time-constraint policy (D2) against the old loop, not the schedule alone:
    - the 3D flip interval's p95 − p5 on the ns arm is at most half the ms arm's (Metal baseline from the spike: 14.6 ms, so at most 7.3 ms there);
    - p50 on both arms is within 33.3 ± 0.5 ms, so the clock changed no speed;
    - of the run's 600-vblank windows (`gap a-b ms`), the median of (b − a) is at most 3 ms (the spike's windows were about 8.8 ms), and at least 80% have a ≥ 15.2 and b ≤ 18.2 ms (16.67 ± 1.5). A window that overlaps a stage load or a logged schedule restart is listed with what the run was doing and does not count. The ±1.5 ms, rather than the ±0.5 ms expected of the schedule, is because one late wake in 600 marks the whole window.
  - *Sleep gate*, `spin` against `sleep`, both on the ns clock:
    - in-wait CPU at site `0x00060475` at most 10% of the window (the Mac figure is the precise one);
    - process CPU at `sleep` lower than at `spin` by at least 25 points of one core on each host (the spin takes 40% or more of the main thread in 3D);
    - loops that left on the timeout are at most 5% of the site's loop exits (`exits timeout` / (`exits wake` + `exits timeout`)) in every summary. Mid-loop timeouts are reported, not gated: the first draft's "wakes outnumber timeouts" could not hold with a 1 ms timeout and a 16.7 ms vblank period (3.5 to 4 timeouts per wake measured on both hosts with the vblank site working as designed);
    - flips/s and each interval percentile at `sleep` inside the `spin` arm's spread, and neither regression flag raised.

  Measured numbers go in `RESUME`, `TASKS` and the tasks file. A gate that fails on host noise rather than on the schedule (a window the host was visibly busy for) is reported with the evidence; the orchestrator, not the implementing agent, decides whether to re-run or to stop.

### D9. Default flip to `sleep`: gated, separate and reversible

The default changes only if `sleep` is frame-identical on every check below.

1. **Metal goldens (Mac)** and **D3D11 goldens (`bench.sh golden`, Proton)**: all scenarios, three runs at `sleep` and three at `spin`.
   - Every frame gets the same verdict under `sleep` as under `spin`.
   - A frame that matches its exact hash in all three `spin` runs matches it in all three `sleep` runs. A frame that is exact in only some `spin` runs is wall-time dependent and is judged by verdict alone.

   Goldens are not bit-exact from run to run (the cloud movie and timer phase follow wall time; see `golden.json`), so the comparison is with spin's own run-to-run behaviour, not with zero. These are evaluation runs: `golden.py --allow-enhance present.pacing=sleep` turns the non-stock check into a note. It is never used to record references.
2. **A flip-indexed A/B** on `@stage1` and `@story-hub`. `fb_dump_at` takes the same flip indices under both modes, three runs each. For each dumped flip, the pixel difference between a `sleep` dump and each `spin` dump (`golden.py`'s compare: mae, bad share, worst tile) must be no larger than the largest difference between two `spin` dumps of that flip. A flip that is identical across the `spin` runs must be identical under `sleep`.
3. **Burnout 3 under Proton** on the exact upstream PR head (PR-E2). The b3 project is regenerated with `--spin-waits` in `auto` mode, then runs boot → "Press START" → menu → race start plus the three `b3/_local/bench host.sh` scenes. Run under `spin` and under `sleep`:
   - the same screens at the same flips;
   - race pace (flips/s) within spin's spread;
   - no new `[AUDIO-HOST]` starve lines;
   - no site in the `pacing` trace whose loops leave on the timeout more than 5% of the time; such a site goes on that project's `exclude` list with its reason.
4. **`audio_check.py`** on a Proton BLiNX 2 `@attract` run at `sleep`: no new starves.

When all four pass, the flip is its own branch, `feat/fps-pacing-default`, with:
- one toolkit commit: the `present.pacing` default to `"sleep"` in `enhance.c`, plus `enhance-config.md`;
- one cat commit: the `setup-pins.json` bump, `docs/env.md`, and an openspec change of its own that amends the `enhancements` requirement "Enhancements default to stock" with a named exception for `present.pacing` (citing the four checks) and updates the exit of the `deviations` entry.

`golden.json` keeps `RECOMP_PRESENT_PACING=spin`, and so does `golden.py`'s check. Reverting the two commits restores `spin`. If any check fails, the default stays `spin`, and the failing evidence is recorded in TASKS.

Under `sleep` as the default, `present.pacing` stays an enhancement key (Decided, 4): frame-identical is not hardware-identical, since the console's CPU spins, so the behaviour belongs in the register (`deviations`, "Spin waits may sleep") and in the layer, where a player can switch it back.

### D10. Generated code and the gen key

- `gen/` must be regenerated. In `wt/pacing/cat`, with `XBOXRECOMP_DIR` pointing at `wt/pacing/xboxrecomp`: `blinx2 analyze`, then `blinx2 recomp`. `recomp` alone misses seeds, so `analyze` runs first.
- `blinx2.py`:
  - `recomp_cmds()` gains `--spin-waits config/spin_waits.json`;
  - `gen_inputs()` gains `config/spin_waits.json`.
- The gen key changes in three fields, which `blinx2 package` names as stale reasons:
  - `toolkit` (the new tools commit);
  - `argv` (the recomp command);
  - `inputs` (the new file).

  `GEN_KEY_VERSION` stays 1, because the key's format is unchanged. `scripts/test_blinx2_cli.py` `test_gen_key_inputs` covers the new input.
- The expected diff of `gen/` against main's is the lowered back edge in every body containing `0x00060475`, and nothing else. The check is a scripted diff whose only changed lines contain `RECOMP_SPIN_WAIT`.
- After the merges, the orchestrator regenerates `gen/` in the main `cat/` checkout before `blinx2 bench integrate`, because integrate syncs that `gen/` and checks its hash.
- `config/setup-pins.json` moves to the merged toolkit commit.

### D11. Backends agree

Pacing lives in the kernel (clock, wake) and in generated code (the wait). None of it is in a render backend. CPU, D3D11 and Metal therefore pace identically. The flip measurement is the executor's, shared by all three, and the measurement plan (D8) covers each backend on its host. The only backend difference in this area is the existing D3D11 `Present(0, 0)`, which is listed under Non-Goals and in TASKS. The Metal presenter's rule that "the walker never blocks on drawable acquisition" is unaffected.

### D12. Upstream shape

- **Cut by hunk.** The fork's kernel commit e4740b4 holds the clock, the wait and the trace together. The PRs are cut from it by hunk, and each PR commit says "fork e4740b4 (part)":
  - PR-08b (the clock): `host_time.*`, `xbox_VblankSchedule`, `kernel_vblank_tick_ns`, `kernel_timer_loop_ns`, `kernel_fire_timers`, the `kernel_drain_dpcs` return value, `vblank_clock` and the `vblank_schedule` ctest;
  - PR-E2 (spin waits): `xbox_SpinWait`/`xbox_SpinWake`, `xbox_IrqlThisThreadBlocksDpcs`, the four wake points, `RECOMP_SPIN_WAIT`, the `pacing` trace and the `spin_wait` ctest.
- **The nanosecond clock** extends PR-08 `up/08-vblank-pacer` if that PR is not yet filed. Otherwise it becomes `up/08b-vblank-ns`, cut from `origin/main` (plus PR-08 if that is still open). It is cherry-picked with `-x`, and `recomp_env(RENV_*)` is changed to `getenv` per §3.2. `vblank_clock=ms` is spelled `RECOMP_VBLANK_CLOCK=ms` in upstream style.
- **Spin waits** become PR-E2 `up/e2-spin-waits`, after PR-E1, as an opt-in extension:
  - the generator flag (off by default);
  - `RECOMP_SPIN_WAIT` and `xbox_SpinWait`/`xbox_SpinWake`, with the mode read by `getenv("RECOMP_PRESENT_PACING")` in the title glue when the enhance layer is absent;
  - the pytest cases and the `spin_wait` ctest.

  The code is title-agnostic: no BLiNX VA in toolkit code or tests, and the tests use synthetic instruction streams.
- **Gates** (pr-stack-plan §2, gate G): Mac ctests and `pytest tools/`, the mingw build with Proton ctests, and Burnout 3 under Proton on the exact head (D9.3). Any later force-push re-runs Burnout 3. For PR-E2 the Burnout 3 run in `auto` mode is expected to find sites whose writer is a guest thread; those go on that project's `exclude` list, and the list is part of the PR's test evidence, not a failure of the mechanism. For the clock PR, the B3 evidence is race pace and the `[NV2A] vblank` gap range before and after.
- **The PR body** says "tested under Proton only; native Windows untested" and states that the work is AI-assisted.
- **Reviews.** Fable reviews against upstream's own README and CONTRIBUTING from `origin/main`, with a verdict per deviation (conform, argue or fork-only). Expected verdicts: conform for the naming (`xbox_Module_Function`) and the test layout; argue for the generator flag.
- **Tracking.** Every gate result is written to the PR tracker by the agent that ran it.

## Risks / Trade-offs

- **A lowered site polls something the kernel never signals.** It still advances at up to 1 ms per pass, which is a slowdown, not a hang. Detection: the per-site timeout counts in the `pacing` trace. Mitigation: `exclude`, or a wake at the writer. BLiNX 2 v1 lowers only the vblank site, whose writer is a DPC.
- **The clock change alters timing for every title.** More precise vblanks and earlier DPCs are closer to hardware, but a title tuned to the old jitter could react. Detection: Metal and D3D11 goldens, Burnout 3, `audio_check.py`. Mitigation: `vblank_clock=ms`.
- **The gate-busy retry wakes the timer thread more often** while the gate is contended. Detection: the profiler's `N_LOOPS` and `drains gate-busy` counters, and process CPU in the trace. It is bounded at 1 kHz, and only while DPCs are queued behind a busy gate.
- **Wine timer resolution.** The high-resolution waitable timer and `timeBeginPeriod(1)` are already in use. Proton runs measure the gap range. Fallback: `vblank_clock=ms`.
- **macOS timer coalescing.** A sleeping thread on a loaded Mac can wake a millisecond or more late, and a backgrounded process is subject to App Nap. Detection: the gap windows in the clock gate. Mitigation: the absolute schedule (a late wake is followed by an on-time one, not a drift), and the gate's ±1.5 ms window.
- **Wine's thread-time granularity.** The in-wait CPU figure under Proton is coarse. The Proton sleep gate therefore also reads the process-CPU drop.
- **Generator false positives.** The matcher is strict, and every candidate appears in the report. The BLiNX 2 list is explicit. Burnout 3 `auto` runs on the PR head are the test of the auto mode.
- **261 copies of one VA.** The lowering is per VA, so all copies change together. The diff check in D10 shows it.
- **Frame identity is statistical**, because goldens vary with wall time. D9 compares with spin's own spread and uses flip-indexed dumps of deterministic routes, so a timing-only change cannot hide a logic change.

## Migration Plan

1. The toolkit branch lands (clock, kernel pacing, generator flag, key at `spin`). Then the cat branch lands (gen regenerated, list, `fps.mode`, scripts, pin). Both land as squash merges by the orchestrator (one commit per feature, the branches kept), after Fable's review.
2. Goldens stay at `spin`. Nothing changes for players unless they set `present.pacing = "sleep"`.
3. `feat/fps-pacing-default` lands only after D9 passes. Rollback is a revert of its two commits.

## Decided

The six open questions of the first draft (1-6), decided by Fable on 2026-10-06 under the user's delegation of unattended decisions. None is a dispute for the user.

1. **`fps.mode`'s variable is `RECOMP_FPS_MODE`.** The layer's naming rule (`RECOMP_` + the dotted key in upper case) is the binding one and has already corrected a doc name once (`RECOMP_RENDER_ASPECT` → `RECOMP_DISPLAY_ASPECT`). The toolkit doc's `RECOMP_FPS` predates the rule and nothing reads it; the spike's `RECOMP_FPS` hook is spike-only code that is not for merge. The doc row is corrected in 4.2.
2. **The nanosecond clock is unconditional.** The opt-in rule exists for features that change stock behaviour. This changes the precision of a schedule that the `kernel-threads` spec already requires to be absolute and independent of the sleep granularity, and it moves toward hardware, where a vblank has no millisecond jitter and a DPC runs the instant IRQL drops. The evidence that must hold before the toolkit branch merges is in D1 ("The price of being unconditional"): same golden verdicts at `spin` on Metal and D3D11, no new audio starves, and the fork's Burnout 3 smoke at the same race pace. `vblank_clock=ms` is the rollback.
3. **`sub_002E0DB0` stays a follow-up.** It is the ADX threads' pacer and `AvSetDisplayMode`'s, so moving it onto the kernel's edges changes audio timing and needs `audio_check.py` on both hosts and its own A/B. v1 already removes the practical beat: after 1.6 both clocks run at exactly 60 Hz from one time source with a fixed phase offset. Recorded in TASKS (7.3), where 1.6 makes it a small change.
4. **`present.pacing` stays an enhancement key even as a default.** Frame-identical is not hardware-identical: the console's CPU spins and the host thread's scheduling changes, so the behaviour belongs in the `deviations` register and in the layer, where a player can turn it back. The default-flip change amends the `enhancements` "default to stock" requirement with a named exception citing D9's evidence (D9), keeps the golden pins, and does not turn the key into a plain config key.
5. **BLiNX 2 never uses `auto`.** Its other candidates (about 150) are fence, doorbell and GPU-state polls whose writers are guest threads or the APU, so each needs a wake point and its own A/B. Sites are added one at a time from the report, after the `pacing` trace shows their loops leaving on a wake (timeout exits at most 5%). `auto` is the title-agnostic mode that Burnout 3 exercises on the PR head, and its `exclude` list is an expected output of that run (D12).
6. **Thresholds** are set in D8: p95 − p5 halved and p50 within 33.3 ± 0.5 ms; gap windows with a median spread of at most 3 ms and 80% within 16.67 ± 1.5 ms; in-wait CPU at most 10%, a process-CPU drop of at least 25 points, timeout exits at most 5% of loop exits, and `sleep` inside `spin`'s widened spread. (Revised after the first measurements: "wakes over timeouts" counted mid-loop timeouts, which the 1 ms bound makes normal; see D8.) The first draft's "gap range within ±1 ms" on a window's minimum and maximum was not measurable without false failures, and its "waiter CPU" mixed the game's own work on the main thread with the spin.

7. **The macOS timer thread asks for on-time wakes** (added at implementation, fork e9a701f). Measured: plain `nanosleep` on the timer thread overshot by 3.7 ms on average and 8 ms at worst, at every QoS class, which gave 13-20 ms vblank gaps on the Mac. `xbox_HostTimerThreadInit()` sets `THREAD_TIME_CONSTRAINT_POLICY` with a 1/60 s period, 2 ms computation, an 8 ms constraint, preemptible. If the host refuses it, one `[KERNEL]` line says so and the thread stays a normal one: the grid keeps its rate and only the wake jitter is the old one. Mac audio with this thread at real-time priority is not yet checked by ear; that is a TASKS item before section 9.

The first draft's own calls, reviewed:
- **The `deviations` entry ships in v1**, written as a mode ("With `present.pacing = "sleep"` ..."). The register is where the 1 ms-late risk and its detection live and where the player doc points. The default-flip change updates its exit.
- **D3D11 present vsync stays out of v1.** Vsync blocks the walker thread on `Present` under Proton and would confound every pacing number, and the cadence is the guest's, not the presenter's. The follow-up is D3D11 honouring the existing toolkit key `RECOMP_PRESENT_VSYNC` (the SDL and Metal presenters already do), not a new key.
- **The fork's Burnout 3 smoke is required**, not optional (8.9): it is the price of decision 2. If Burnout 3 cannot run on the Linux/Proton host for an infrastructure reason (the dump, the build), the orchestrator asks the user; the gate is never routed around.
- **`present.vsync` is dropped**, rightly: `RECOMP_PRESENT_VSYNC` already exists as a toolkit config key, so a layer key would duplicate it.
