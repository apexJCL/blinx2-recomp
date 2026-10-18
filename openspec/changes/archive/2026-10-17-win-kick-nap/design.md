## Context

**The ack loop and its nap.** The walker thread (`nv2a_ack_thread`, toolkit `src/kernel/xbox_memory_layout.c:1642`) runs one tick per pass: the ack table, the fence mirrors, the DSP ack, `nv2a_pb_poll`, and, when `DMA_PUT` moved, the walk of the new segment followed by the `DMA_GET` advance. The comment above `NV2A_KICK_REG` (1519-1543) records why the KickOff flush is acknowledged by this thread and never earlier: the title's D3D sets PFB 0x100410 bit 16, spins on it, then writes `DMA_PUT`; an ack before the previous segment is executed lets the title run a segment ahead into a MakeSpace notify nobody answers. With `RECOMP_FAST_KICK` (default on since the 19 ms-a-frame finding on macOS) the end of each tick is a poll loop (1886-1927):

```c
for (;;) {
    put = *DMA_PUT;
    if (nv2a_pb_exec_flip_poll())        last_active = now;       /* held: no ack */
    else if (put != g_scanned_put)       { last_active = now; break; }   /* new work */
    else if (*kr & NV2A_KICK_BIT)        { *kr &= ~NV2A_KICK_BIT; kick_cleared(now); last_active = now; }
    if (now - t0 >= 1 ms)                break;                   /* the tick */
    if (now - last_active > 200 ms)      { Sleep(1); break; }     /* idle */
    kick_nap_us(50);
    now = nv2a_pb_now_ns();
}
```

`kick_nap_us` (1556-1584) is `NtDelayExecution(FALSE, -us * 10)` on Windows, found by `GetProcAddress` so the mingw build needs no ntdll import, with `Sleep(1)` if the lookup fails; `nanosleep` elsewhere. Its own comment says what this change acts on: "Wine honours (select with a timeval) and native Windows rounds to its timer resolution". The kernel timer thread calls `timeBeginPeriod(1)` at start (`kernel_bridge.c:3750-3762`) so that `Sleep(1)` is a millisecond and not 15.6, which sets that resolution to 1 ms for the process. `kick_cleared` (1587) accounts the wait and calls `xbox_SpinWake`, which ends the guest's lowered KickOff spin at once (`kernel_pacing.c:156`: `SleepConditionVariableCS` with a 1 ms timeout, `248`: `WakeAllConditionVariable`), so the walker-to-guest leg has no timer in it.

The observer thread `nv2a_kick_thread` (1606-1623, started under `RECOMP_TRACE=flip`) samples the bit with `kick_nap_us(50)` while kicks are recent and `kick_nap_us(1000)` otherwise, and stamps the first time it sees the bit set; `[PB-PERF]`'s `kickwait` is the sum of (cleared - seen) over the kicks of a flip (`nv2a_pb_exec.c:6206`). On Windows its 50 us is also a millisecond, so a kick can be seen up to 1 ms after it was set and `kickwait` reads low.

**What the host gives.** Native Windows: `NtDelayExecution` and `Sleep` are timer-queue waits rounded up to the current clock interval, 1 ms at best under `timeBeginPeriod(1)` and 15.6 ms without it (Windows 11 also drops a process's resolution request while its window is occluded). The high-resolution waitable timer (`CreateWaitableTimerExW` with `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`, Windows 10 1803+) is exempt from coalescing and does not depend on `timeBeginPeriod`, but it still expires on the system clock interrupt: the kernel runs the clock at its maximum rate while one is pending, and the WDK says a relative high-resolution timer "never expires early" but can be up to a clock interval late. The finest clock on the user's PC is 0.5 ms, so a 50 us request wakes at p50 511 us (p95 542), against 1005 us for `NtDelayExecution` and 50 us for a spin on the clock (200 naps each, 2026-10-14). Bruce Dawson's 2020 table has the same 535-585 us for 10-100 us requests; DuckStation's author drops the last 0.5 ms and spins for it on Windows 11 22H2; SDL3, Dolphin, PCSX2, DXVK, RPCS3, yuzu, Ryujinx, Special K and RTSS all sleep to within one clock interval and spin the rest (sources in `notes/kicknap/windows-sub-ms-waits.md`). `NtSetTimerResolution(5000)` reaches the same 0.5 ms, MMCSS and thread priority shorten dispatch after a wake and not the wake itself, and `SwitchToThread`/`Sleep(0)` return at once on an idle core and hand a whole quantum away on a busy one. Wine: a non-alertable `NtDelayExecution` is a `select` with a timeval inside ntdll, no server round trip, honoured to the scheduler's granularity (tens of microseconds, plus the kernel's timer slack; the Deck measures p50 107-126 us); a waitable timer is a wineserver object, so `SetWaitableTimer` plus `WaitForSingleObject` are two server round trips per nap and the wake comes through the server's poll loop. POSIX: `nanosleep`, honoured to the same tens of microseconds (the Mac measures p50 78-82 us). So native Windows is the one host where a 50 us *timed* wait does not exist in user mode: the floor is one clock interval whichever API asks, and below it there is a spin, or a wake from a thread that knows the event happened.

**The profile** (`runs/asynclog/win/prof-walker-waits.txt`): over 117.76 s the walker waited 61.38 s (52.1%), in 79,637 `DelayExecution` waits (676/s, 0.77 ms each), 78,743 readied by Idle. At 30 fps that is 22 naps a frame. Each KickOff then waits for the segment before it plus up to a millisecond of poll latency (0.5 ms on average), and each new `PUT` is picked up with the same latency; with 16-20 kicks a frame in the city view that is 8-10 ms a frame on the guest's critical path, the 5-9 ms the `[PACING]` windows show over 33.3. On the timer alone the same arithmetic leaves ~5 ms a frame: not enough.

## Goals / Non-Goals

**Goals**
- On native Windows the ack loop's 50 us poll interval is about 50 us while the title is kicking, so a KickOff is acknowledged and a new `PUT` picked up within a poll of the walker going idle, as on Wine and macOS.
- The CPU spent on that is bounded: the walker spins only within a short budget of its last activity, and sleeps on the timer and then `Sleep(1)` beyond it, so menus, light scenes and a backgrounded window do not hold a core.
- Wine/Proton and POSIX run the same wait calls as today; the goldens there do not move.
- The Windows log states the nap each primitive gives, and the ctest bounds what can be bounded on every host.
- A knob for the recorded A/B and for the floor measurement, DEBUG tier.

**Non-Goals**
- The 1 ms tick, the idle `Sleep(1)` paths and `RECOMP_FAST_KICK=0` (a plain `Sleep(1)` loop) stay as they are.
- `xbox_HostSleepNs` and the vblank schedule: unchanged (the schedule compares against an absolute deadline on the same timer and is measured already).
- The event-driven kick leg. The guest's KickOff spin at 0x002E7F20 is a lowered spin-wait site whose `RECOMP_SPIN_WAIT` macro (`templates/runtime/recomp_types.h:545`) runs host code on every pass under `present.pacing=sleep`, microseconds after D3D set bit 16: a doorbell rung there (an auto-reset event the walker waits on with the 1 ms tick as timeout, rung once per walker nap), with a bounded post-ack poll for the `PUT` write that follows every ack, would make the kick leg a scheduler wake on every host and remove the 50 us poll entirely, spin included. It needs its own spec (the `PUT`-follows-kick assumption checked against `[PB-PERF]`, the macro's fast path under `present.pacing=spin`); the hybrid here is what native Windows needs today, and the doorbell is the follow-up in TASKS.md.
- `nv2a_pb_now_ns` on Windows reads `timespec_get(TIME_UTC)`, a clock that is not monotonic, and the loop's `t0`/`last_active` arithmetic runs on it. Pre-existing and out of scope; noted in TASKS.md for a move to `xbox_HostNowNs`.
- Burnout 3 on native Windows (CLAUDE.md asks Proton for runtime changes; the upstream PR that carries this tests it there).

## Decisions

### D1. The nap is a host helper with three primitives; native Windows runs a bounded hybrid, the other hosts the old call

`src/platform/host_time.h` gains:

```c
/* The Windows build under Wine (ntdll exports wine_get_version); 0 on a
 * native Windows host and on POSIX. Looked up once. */
int xbox_HostUnderWine(void);

typedef enum {
    XBOX_NAP_AUTO,    /* the rule below, resolved once */
    XBOX_NAP_TIMER,   /* the thread's high-resolution waitable timer (Windows) */
    XBOX_NAP_DELAY,   /* NtDelayExecution on Windows, nanosleep on POSIX */
    XBOX_NAP_SPIN,    /* busy-wait on the clock with a pause instruction */
    XBOX_NAP_HYBRID   /* SPIN for a hot nap, TIMER for a cold one */
} XboxNapMode;
/* Set once before the napping threads start (an A/B switch). */
void xbox_HostNapModeSet(XboxNapMode mode);
XboxNapMode xbox_HostNapMode(void);          /* the mode in effect, never AUTO */

/* A poll loop's short sleep. `hot` says the caller expects the event it is
 * polling for within a couple of milliseconds (it saw activity just now):
 * under HYBRID a hot nap spins and a cold one takes the timer; the other
 * modes ignore the flag. Honoured to the microsecond where the host can:
 * nanosleep on POSIX, NtDelayExecution under Wine (a select with a timeval),
 * and on native Windows either a spin or the high-resolution waitable timer,
 * since every timed wait there expires on the system clock interrupt (0.5 ms
 * at best; NtDelayExecution and Sleep round to 1 ms under timeBeginPeriod(1)).
 * 0 returns at once. The caller re-reads its clock, as with xbox_HostSleepNs. */
void xbox_HostNapNs(uint64_t ns, int hot);
```

`xbox_HostNapNs` on `_WIN32`:
- `AUTO` resolves once to `DELAY` when `xbox_HostUnderWine()`, else `HYBRID`.
- `HYBRID`: `hot` ? the `SPIN` path : the `TIMER` path.
- `TIMER`: the per-thread `CreateWaitableTimerExW(NULL, NULL, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS)` handle that `xbox_HostSleepNs` keeps (lifted into one `thread_timer()` the two share), `SetWaitableTimer` with the relative due time in 100 ns units, `WaitForSingleObject`. When the handle cannot be created (a Windows before 1803: `ERROR_INVALID_PARAMETER`) the cold path degrades to `DELAY` for the process (`HYBRID` keeps spinning hot naps) and `xbox_HostNapMode()` reports the degraded mode so the startup line can print it.
- `DELAY`: today's code, `NtDelayExecution(FALSE, -(ns + 99) / 100)`, `Sleep(1)` if ntdll has no such export.
- `SPIN`: `t_end = xbox_HostNowNs() + ns; while (xbox_HostNowNs() < t_end) YieldProcessor();` (`_mm_pause` on x86; the arm64 POSIX build has no SPIN caller, but the loop is portable). Bounded by the clock, never by a count.

On POSIX `AUTO` resolves to `DELAY`; `TIMER` and `DELAY` are both `nanosleep`; `SPIN` as above; `HYBRID` is `SPIN` hot and `nanosleep` cold (not a default anywhere, available for a measurement). `xbox_HostUnderWine` is `GetModuleHandleA("ntdll.dll")` + `GetProcAddress(..., "wine_get_version") != NULL` under `_WIN32`, cached; 0 elsewhere. Wine, Proton and GE-Proton all export it; a false negative would only send Wine down the hybrid path, correct but a core warmer.

Implementation notes from the review of 2f22039: the ntdll lookups (`wine_get_version`, `NtDelayExecution`) go through `INIT_ONCE` / `InitOnceExecuteOnce`, not a hand-rolled `looked` flag; `s_nap_mode` is read and written with `__atomic_load_n` / `__atomic_store_n` on POSIX (`Interlocked*` on Windows) so the once-only resolution of `AUTO` is a data race nowhere; the mode is set before any napping thread exists (D2's `kick_nap_init`).

**The hybrid in the loop.** `kick_nap_us(us)` in `xbox_memory_layout.c` becomes `xbox_HostNapNs((uint64_t)us * 1000u, hot)` with `hot = (now - last_active) < KICK_NAP_SPIN_BUDGET_NS`, `KICK_NAP_SPIN_BUDGET_NS` = 2 ms. The loop's structure is unchanged: the 1 ms tick bound, the 200 ms idle `Sleep(1)`, the `g_kick_fast` gate. What changes is which primitive the nap takes:

| time since the last kick, `PUT` or flip hold | native Windows (`hybrid`) | Wine / POSIX (`delay`) |
|---|---|---|
| under 2 ms | `pause` spin on the clock, ~50 us | `select` / `nanosleep`, ~80-120 us |
| 2 ms to 200 ms | high-resolution timer, ~0.5 ms | the same |
| over 200 ms | `Sleep(1)` (unchanged) | `Sleep(1)` (unchanged) |

Why 2 ms: the intra-frame gaps the walker waits through are the title's time to build the next segment, hundreds of microseconds to about a millisecond in the city view (16-20 kicks across the active part of a 33 ms frame), so 2 ms covers them with margin; the frame-end wait (several ms when the title is ahead) and menus fall to the timer. A kick that arrives after a gap longer than the budget pays up to one clock interval (0.5 ms) once, the same price every kick paid under `timer`. The budget is a constant printed on the startup line; it becomes a knob only if the Windows run (tasks.md 4.4) asks for it.

The observer thread (`nv2a_kick_thread`, `RECOMP_TRACE=flip`) naps cold (`hot = 0`): on Windows it takes the timer, so a kick is stamped up to 0.5 ms after it was set and `kickwait` under-reads by that much. It is diagnostics; a second spinning core is not worth the stamp. The `[PB-PERF]` doc says so.

**Why not an event.** The KickOff bit and `DMA_PUT` are plain stores into the mapped register window (`layout_commit_at`, 3626): no host code runs on the write, so a trap per write is the only way to wake on the store itself, a fault per write (the APU lesson: about 51 us each under Wine, and D3D writes these registers many times a frame). The leg in the other direction is already event-driven (`kick_cleared` → `xbox_SpinWake`), and the guest's lowered KickOff spin runs host code right after the store, which is the signaller the doorbell follow-up uses (Non-Goals). Until then the guest-to-walker leg is a poll, and the poll's nap is the fix.

**Why not a plain spin.** `spin` alone holds the walker's core for 200 ms after the last kick, which during play is always: menus and light scenes included, and on a Windows handheld that is a few watts and thermal headroom for nothing. The hybrid spins exactly where the 50 us matters and sleeps where it does not. `spin` stays as the knob's floor measurement.

**Why not the timer alone.** It is the measured 0.5 ms floor: 22 naps a frame at ~0.5 ms is ~5 ms a frame on the guest's critical path, and the city view runs 5-9 ms over 33.3. The first version of this change (2f22039) was that and is kept as `kick_nap=timer` for the A/B.

### D2. The nap mode is set, measured and printed before the ack thread starts

`kick_nap_init()` (split out of `xbox_Nv2aKickStart`, called from `xbox_Nv2aAckStart` before `CreateThread` of the walker, so no thread naps on an unresolved mode) reads the knob, calls `xbox_HostNapModeSet`, then times 32 naps of 50 us per primitive on the calling thread and prints the mode in effect with each p50, once:

```
  NV2A KickOff flush: ack loop polls at ~50 us while kicking (RECOMP_DEBUG=fast_kick=0: Sleep(1)); nap hybrid (spin within 2 ms of activity, then timer): spin p50 50 us, timer p50 511 us
```

(`nap delay (wine): 50 us -> p50 108 us` under Wine; `nap nanosleep: 50 us -> p50 80 us` on POSIX; `nap timer: 50 us -> p50 511 us` and `nap delay: 50 us -> p50 1005 us` for the Windows A/B values; `nap spin: 50 us -> p50 50 us`; `nap hybrid (no high-resolution timer: spin, then delay)` after the fallback.) A few milliseconds at boot, and the number every Windows log then carries is the floor this bug is about.

### D3. The knob

`src/platform/recomp_env.h`, DEBUG tier, after `FAST_KICK`, with a short help string (the long form lives in `docs/env.md`):

```c
X(KICK_NAP, DEBUG, "kick_nap", NULL, "=hybrid|timer|delay|spin: how the ack loop naps between its ~50 us polls (docs/env.md)") \
```

Unset is `AUTO`: `hybrid` on native Windows, `delay` under Wine and on POSIX. `docs/env.md` gets the row in the Debug table with the read site and the long description: `hybrid` (native Windows default: a `pause` spin while within 2 ms of the last kick, `PUT` or flip hold, the high-resolution waitable timer beyond, `Sleep(1)` after 200 ms idle), `timer` (the high-resolution timer alone: on this hardware a 0.5 ms floor), `delay` (Wine and POSIX default: `NtDelayExecution` / `nanosleep`; on native Windows the old 1 ms-rounded nap), `spin` (busy-wait on the clock, the floor measurement), plus the startup line's format. The default is the fix, so no opt-in on Windows; the other hosts' default is what they run today.

### D4. The ctest

`tests/host_nap/` is a standalone project like `tests/flip_hold`: it builds `../../src/platform/host_time.c` alone (the file includes only `windows.h` or `time.h`/`pthread.h`), on every host, under `tests/posix_ctest.sh` automatically and under the Proton runner by the same toolchain. Each check prints its figures on a `PASS`/`FAIL` line; bounds are on p50 only (a loaded Deck or Mac makes p95 and max useless as a gate, and the 2f22039 run showed it), 200 naps of 50 us per primitive:

1. `xbox_HostUnderWine()` is 0 on POSIX; under `_WIN32` it agrees with a direct `GetProcAddress(ntdll, "wine_get_version")` (the Proton run exercises the 1 case).
2. `xbox_HostNapMode()` after `xbox_HostNapModeSet(XBOX_NAP_AUTO)` is `HYBRID` on native Windows and `DELAY` under Wine and on POSIX.
3. `SPIN` (and therefore the hybrid's hot nap): p50 under 100 us. The clock bound, on every host.
4. `DELAY`: on Wine and POSIX p50 under 400 us (the Deck measures 107-126 us, the Mac 78-82; the margin is scheduler noise on a loaded host); on native Windows printed, not bounded (it is the 1 ms the bug is about, recorded for the comparison).
5. `TIMER`: printed, not bounded, on every host (the 0.5 ms clock floor on native Windows; a wineserver round trip under Wine; `nanosleep` on POSIX).
6. `HYBRID` with `hot = 0`: printed (it is `TIMER` on Windows, `nanosleep` on POSIX), so the Windows log shows both halves of the default.
7. `xbox_HostNapNs(0, hot)` for both `hot` values: p50 of 200 calls under 50 us (a no-op; p50, not max, so a preempted call does not fail the test).

On native Windows the exe (`host_nap_test.exe` from the Mac cross-build) is the regression check for this bug: the lines record spin ~50 us, timer ~0.5 ms, delay ~1 ms, and check 3 fails if the spin ever stops honouring its length.

The Proton runner: `host_nap` on the CLI's optional standalone list (`bench/host/tests.sh`, the `optional=` line beside `enhance_cfg`; the step text in `bench/__init__.py:367`), since a game pinned to an older toolkit has no such dir. Until cat's `[cli]` pin moves to a tag with that commit, the Deck gate configures and runs the test by hand with the same toolchain, as `tests.sh` does for each standalone dir.

### D5. Windows 11 keeps the 1 ms clock when the window is occluded

Beside `timeBeginPeriod(1)` in the kernel timer thread (`kernel_bridge.c:3750-3762`), the same `GetProcAddress` style: `SetProcessInformation(GetCurrentProcess(), ProcessPowerThrottling, &state, sizeof state)` with `state.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION`, `state.ControlMask = PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION` (`0x4`, defined locally if the mingw headers lack it), `state.StateMask = 0`. Microsoft: "By default in Windows 11 if a window owning process becomes fully occluded, minimized, or otherwise non-visible to the end user, and non-audible, Windows may automatically ignore the timer resolution request"; with the mechanism turned off "the system remembers and honors any previous timer resolution request by the process" (`SetProcessInformation` docs). Dolphin and yuzu do the same. It keeps the idle `Sleep(1)` paths and the ms vblank schedule at 1 ms when the game window loses focus; it does not reach the hybrid's hot path, which has no timer in it. A failing call (Windows 10, an older build) is ignored: the game then runs as before this change. Under Wine the call is a stub or absent and is ignored the same way.

### What the Windows run reads

- `RECOMP_TRACE=pacing`: the `[PACING] flips 600: interval p5 p50 p95 max ms; vblank gap; cpu process N%; mode sleep` summary (`kernel_pacing.c:453`), the frame-time comparison against `game-20261014-164545.log`; the `[PACING]   site 0x002E7F20: waits N immediate N wakes N timeouts N ...` line that follows it (`site_line`, 395) is the guest's KickOff spin: `wakes` are spins ended by `kick_cleared`, `timeouts` the 1 ms timeouts, and `cpu in-wait` its share of the window. `cpu process` is expected to rise by roughly 50 percentage points (the walker's 52% asleep becomes a spin); a rise with the frame time back at 33.3 is the trade accepted.
- `RECOMP_TRACE=flip`: one `[PB-PERF] flip N wall W ms walk X ms (draw, decode) methods M batches B present P kicks K kickwait Y ms stops S` line per flip (`nv2a_pb_exec.c:6206`): `kicks` is the KickOff flushes acknowledged since the last flip, `kickwait` the sum of the guest's waits on them (under-read by up to 0.5 ms a kick on Windows, D1), so `kickwait / kicks` is the wait per kick, and `wall - walk - present` is what the walker spent outside the walk (its naps and the ticks). The comparison is the pair of runs on the fixed build, `kick_nap=delay` against the default, if the default alone does not reach 33.3.
- The startup line (D2): spin p50 and timer p50 and the budget.
- Draws a frame: the `[d3d11] present #N: ... draws` lines every 300 presents, as the tracker item's 2026-10-14 reading used them, to confirm the compared windows are the same view (more than 6000 draws a frame).
- WPR, the walker thread's waits summarised as `prof-walker-waits.txt` was: the timer-wait count collapsing (from ~680/s to the cold naps only), the walker's busy share near 100% in the city view and back on the timer in a menu window, the guest thread's share on the spin instruction (74.7% + 7.8% before).

## Upstream

Toolkit code (CLAUDE.md; `analysis/upstream/pr-stack-plan.md`).

- **Upstream-first.** Upstream has neither `RECOMP_FAST_KICK` nor `host_time.c`; its ack loop is the `Sleep(1)` tick. Nothing to prefer.
- **Placement.** `xbox_HostUnderWine`, `xbox_HostNapNs`, the power-throttling opt-out and `tests/host_nap` go where `host_time.c` lands, PR 4 (pacing); the ack loop's poll, the hybrid policy and its use of the helper with G2 (the walker from GET to PUT), which already carries `RECOMP_FAST_KICK` and the trace gating from async-log-writer. The knob is `getenv("RECOMP_KICK_NAP")` in the PR. The PR text states the Windows figures (1.0 ms `NtDelayExecution`, 0.5 ms high-resolution timer, 50 us spin per 50 us nap) and the Wine reason for keeping `NtDelayExecution` there.
- **Burnout 3 gate.** Required before merge (Validation): the walker is shared.

## Risks / Trade-offs

- **The walker's CPU.** While the title kicks, the walker's core is busy for the active part of the frame: on the 3700X about +50 percentage points of `cpu process`, a core out of sixteen. On a Windows handheld (8 cores, 15-30 W) a `pause` spin on one core costs a few watts; the 2 ms budget bounds it to the active part of the frame, and `spin` is never the default. The Steam Deck runs Proton and is untouched. `[PACING]`'s `cpu process` and the WPR capture measure it; a 25% flips/s drop or a 1.5x frame-ms rise anywhere is a blocker, a CPU rise with the frame time at 33.3 is not.
- **The budget is wrong for some view.** Gaps longer than 2 ms pay one 0.5 ms wake per kick, which is `timer`'s behaviour, not worse than it; gaps shorter than the budget in a light scene spin for nothing, bounded by the budget. If the Windows run shows either mattering, the budget becomes a knob value (`hybrid:N`), filed in TASKS.md, not built here.
- **The spin's power on a laptop.** `pause` is what SDL3, Dolphin and DuckStation spin with; AMD `MWAITX` / Intel `TPAUSE` (what Special K uses on Zen) would sleep the core inside the spin and `MONITORX` on the KickOff register would wake on the store itself. A refinement for later, not a prerequisite; the doorbell follow-up removes the spin altogether.
- **More cold waits per second on the walker.** Past the budget the timer waits are what `timer` did on every nap: a `SetWaitableTimer` plus a `WaitForSingleObject`, about 5-10 us of CPU each, at most ~2 a millisecond. Negligible against the hot spin.
- **Wine detection.** `wine_get_version` has been in ntdll since Wine 1.x and Proton exports it; a Wine without it takes the hybrid path (a warm core, correct behaviour). No native ntdll exports it, so Windows cannot be mistaken for Wine.
- **`timeBeginPeriod` stays**, with D5 keeping it honoured when the window is occluded. The hot path does not depend on it.
- **The goldens.** Wine and POSIX run the same calls as before; the goldens there are a check that the helper's dispatch is right, not a measurement.
- **`nv2a_pb_now_ns` is not monotonic on Windows** (`timespec_get(TIME_UTC)`): a clock step during play would make one `hot` decision or one tick bound wrong, once. Pre-existing; the move to `xbox_HostNowNs` is the follow-up in TASKS.md, not part of this change.

## Validation

- **Mac build** (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`), then `tests/posix_ctest.sh <build-dir>` with 0 FAIL, `host_nap` among them (`pytest tools/recomp tools/disasm` not needed: no tool change).
- **Mac Metal**: `blinx2 golden run` (attract, stage1, story) unchanged; the startup line reads `nap nanosleep: 50 us -> p50 ...`.
- **Proton on the Steam Deck** (exe from the Mac cross-build): `blinx2 bench integrate --golden` (the Proton ctests and the three D3D11 goldens), `tests/host_nap` by hand with the bench toolchain until the CLI list carries it; the startup line reads `nap delay (wine)`. Burnout 3 on the exact toolkit head: boot, front end, one race, flips/s against the last gate (57.5 on the Deck, async-log-writer 3.4).
- **Native Windows, the user's PC**: the merged build, the 1-2 route to the city view, render.scale=3 as in `game-20261014-164545.log`, `RECOMP_TRACE=pacing,flip`, on the default. Read: the startup line's spin and timer figures; `[PACING]` p50/p95 and `cpu process` on the city windows against 164545's p50 38.4-41.8 / p95 40.2-45.3 ms, cpu 187-199% (target: p50 33.3, p95 within 1-1's 34-37 ms, at the same draws a frame); `[PB-PERF]` kicks a frame and `kickwait / kicks`. If the default does not reach 33.3, a second run with `RECOMP_DEBUG=kick_nap=delay` as the control, same route, is the recorded A/B. `host_nap_test.exe` from the cross-build once, for its spin, timer and delay lines. A ~1 min WPR capture of the city view on the default summarised as `prof-walker-waits.txt` was (timer-wait count, the walker's busy share, the guest's spin share) if the frame time does not tell the story on its own. Flag a 25% flips/s drop or 1.5x frame-ms rise anywhere as a blocker; record the `cpu process` change.
- **Gates**: the above, `uv run pytest scripts` and ruff in cat, the CLI's `uv run pytest tests` and ruff for the list change, the review.
