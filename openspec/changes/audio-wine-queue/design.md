## Context

Every number below is from toolkit `posix-host/portability` (c391da41).

- **Device queue** (`src/apu/apu_xaudio2.c:33,40,83`): `XA2_BUF_SAMPLES_DEFAULT` 512 and `XA2_NUM_BUFS_DEFAULT` 4, both inside the `_WIN32` block. They are overridable with `RECOMP_AUDIO_BUF_SAMPLES` (128..4096) and `RECOMP_AUDIO_BUF_COUNT` (2..8). The ring has count + 1 slots. The SDL2 backend keeps its own `SDLA_*` copies (`apu_sdl2.c:39`).
- **Pacing marks** (`apu_xaudio2.h:49`, `xa2_pacing_marks`, applied at `apu_core.c:561`): high is buffers x count, capped at `buf * (count + 1) - period`; low is half of high. With 512 x 4 that gives 1024..2048 samples; with 512 x 6, 1536..3072; with 512 x 8, 2048..4096.
- **Feed:** `mcpx.apu_thread` (`apu_core.c:1416`) loops in `mcpx_apu_frame_thread` (`:1147`). Each pass throttles, takes a pace step, runs `se_frame` under `d->lock` (`APU_LOCK_FRAME`), then submits one 256-sample period (`:954`). Guest MMIO traps take the same lock (`:315-320`).
- **Gate dependency:** when the front end is trapped (`:1211`), no period is produced until DirectSound's ISR or DPC clears FECTL. The ISR runs on the frame thread when the dispatch gate is free (`apu_deliver_irq`, `:327`). Otherwise it is posted to the gate holder's next safe point (`src/kernel/kernel_hal.c:670`).
- **Thread creation:** `qemu_thread_create` (`src/apu/apu_shim.h:126`) is a bare `CreateThread`. It drops the name (`(void)name`, `:129`) and gives normal priority. Nothing in `src/apu` sets a priority or uses MMCSS.
- **Thread identity under Wine:** Wine's TIDs are not Linux TIDs. Without a name, the thread cannot be found with `ps -L`.

Deck evidence (GE-Proton11-7, SSX 3, 620 s with the host audio trace):
- trap spells 0;
- one `[XA2] underrun`, at t ≈ 278 s, next to a 49 ms frame with no shader compile or upload; submit gap max 24.6 ms; minimum queued 256 samples;
- no starve lines;
- a 477 ms render-thread hitch at the race load, with no underrun;
- PSI cpu-some 9.8 %.

This is consistent with (b) or (c), not (a). The run had no lock statistics, so it cannot tell (b) from (c).

## Goals / Non-Goals

**Goals:**
- No `[XA2] underrun` over the long SSX 3 bench under Proton, and a clear margin in the queue-depth distribution under a synthetic CPU load.
- The least latency that achieves that, within the 125 ms lag budget (D4).
- Native Windows, macOS and Linux SDL2 unchanged by default.

**Non-Goals:**
- Cause (a). A guest thread holding the gate with no safe point is a kernel-side change. If the A/B shows trap spells at an underrun, that is a separate change.
- Shortening the APU lock holds in (c). Depth absorbs them here; if the lock statistics show long holds, that is a follow-up.
- The ~20 ms low-latency target (the `audio` change, task 4.6). This change goes the other way under Wine, on purpose. 4.6 stays open for native hosts.
- MMCSS "Pro Audio" on native Windows. Wine's `avrt` is a stub, so it does nothing under Proton. On native Windows it is a reasonable follow-up, recorded in TASKS.

## Decisions

### D1. Defaults live in the header, resolved by pure functions

- **Header constants:** `XA2_BUF_SAMPLES_DEFAULT`, `XA2_NUM_BUFS_DEFAULT` and the new `XA2_NUM_BUFS_WINE` move out of the `_WIN32` block in `apu_xaudio2.c` into `apu_xaudio2.h`. `apu_sdl2.c` uses them in place of its own `SDLA_*` copies of the default (it keeps its own min and max).
- **Resolver:** `xa2_default_buf_count(int under_wine)` returns `XA2_NUM_BUFS_WINE` or `XA2_NUM_BUFS_DEFAULT`. `xa2_init` passes its result as the default to `xa2_env_int`, so the env override and the 2..8 clamp work as they do today.
- **Log:** when the Wine default applies, the init line `[XA2] XAudio2 initialized (512 x N ...)` gains ` (wine default)`.

*Alternative: a bigger buffer (1024 x 4).* This gives the same 85 ms ring but a coarser queue: the pacer's marks move in 1024-sample steps, and each XAudio2 callback carries more samples. More buffers of the same size keep the granularity and are the smaller change.

**Testing.** The header functions are tested in a new header-only ctest, `tests/xa2_defaults`. It includes `apu_xaudio2.h` without XAudio2, builds on every host and is picked up by `tests/posix_ctest.sh`. The existing `tests/xaudio2` harness refuses non-Windows hosts (`CMakeLists.txt:3-5`), so it cannot be the gate. Native Windows has no gate run of its own: the pure-function test covers its default (`under_wine = 0`). A run on native Windows needs the user's go and is not required for this change.

### D2. A thread-priority knob, off by default, plus a thread name

**The name.** `qemu_thread_create` names the thread with `SetThreadDescription`, looked up with `GetProcAddress` from kernel32 because older Windows and Wine lack it. Recent Wine passes the description to the Linux thread's comm. `mcpx.apu_thread` is exactly 15 characters, the comm limit. Task 2.0 checks on the Deck that `ps -L -o tid,nice,comm` shows the name, before arms C and D run. If Wine does not pass it on, the arms find the thread by elimination (the TID that appears at APU start) and say so in the table.

**The knob.** `RECOMP_AUDIO_THREAD_PRIORITY` (CONFIG) accepts `normal` and `highest`. `time_critical` is honoured only when the DEBUG-tier key `audio_thread_tc` is on; otherwise it is reported and treated as `highest`. After `qemu_thread_create`, `apu_core.c` calls `SetThreadPriority` and logs `[APU] thread priority <name>` with the value `GetThreadPriority` reads back. POSIX builds parse the key, log once that it is ignored, and do nothing.

- **Parsing** is a pure function in `apu_xaudio2.h`, tested in `tests/xa2_defaults`.
- **Why `time_critical` is fenced off:** the frame thread runs guest code. DirectSound's ISR runs on it when the gate is free (`apu_core.c:327`), and `CRITICAL_SECTION` has no priority inheritance. At `time_critical` on the Deck's 4 cores, it can starve the game's own threads.
- **Why not MMCSS:** Wine's `avrt` returns a handle without changing scheduling, so it would be a no-op that looks like it worked.
- **Whether Wine applies it:** Wine maps thread priority to a Linux nice value only when the process may raise its niceness (RLIMIT_NICE or rtkit). On the Deck this is unverified, and `GetThreadPriority` reads back the requested value either way. The A/B therefore reads the nice value directly.

### D3. The A/B decides between depth and priority

Every run uses:
- SSX 3, `bench-pad-long.txt`, 620 s, the D3D11 backend;
- `RECOMP_TRACE=audio_host,apu_lock`. `apu_lock` gives `[APU-LOCK]` hold and wait histograms every 5 s, including the frame thread's wait on `d->lock` (`taker=frame`).

| Arm | `RECOMP_AUDIO_BUF_COUNT` | `RECOMP_AUDIO_THREAD_PRIORITY` | When |
|---|---|---|---|
| A (stock) | 4 | normal | 0.1, no code |
| B | 6 | normal | 0.1, no code |
| C | 4 | highest | 2.1, after 1.x |
| D | 6 | highest | 2.1, after 1.x |

**Load.** Each arm runs twice idle and twice loaded. The Deck has 4 cores and 8 threads. "Loaded" means 7 busy-loop processes (`sh -c 'while :; do :; done'`) at nice 0, started with the game and stopped with it. One hardware thread is left to the rest of the system.

**Positive control.** Loaded arm A must underrun, or reach `q_min` 0, in both runs. If it does not, the load is too weak to test anything: raise it to 8 loops, then add a `stress-ng --vm` memory load if needed, and re-run arm A before running any other arm. The load that works is recorded and used for every arm.

**Metrics,** per arm, idle and loaded:
- the per-second `[AUDIO-HOST]` `q_min` distribution: p1, p5, and the count of seconds with `q_min` below one period (256);
- the per-second `gap_max_ms` distribution: p99 and the maximum;
- the `[XA2] underrun` total;
- the frame-thread lock wait from `[APU-LOCK]`: total, maximum, and the count of waits over 10 ms;
- flips/s;
- for C and D, the measured nice of the APU thread.

Underrun counts alone have no power: arm A had one in 620 s. The decision rests on the distributions.

**Rule:**
1. **Priority wins** when all of these hold:
   - C's loaded `q_min` p1 is at least B's;
   - C has no seconds below one period idle;
   - C's measured nice is below 0;
   - the lock waits do not explain the underruns (no frame-thread wait over 10 ms at the seconds where `q_min` falls).

   The count then stays 4, and `xa2_default_priority(int under_wine)` returns `highest` under Wine and `normal` elsewhere. It is tested in `tests/xa2_defaults` and its log line gains ` (wine default)`. No latency is added.
2. **Depth wins** when, otherwise, B has no seconds below one period idle and its loaded `q_min` p1 stays above 0, within the D4 budget. The count becomes 6 under Wine.
3. **If B still drains under load,** try 8, but only if the D4 chain at 8 is at most 125 ms. If 8 is ineligible or also drains, report the floor reached and the residual cause.
4. **D** is adopted only when neither B nor C alone meets the bar. If the lock waits show cause (c), depth is the only part that helps.

Flips/s must not drop 25 % or more in any idle arm (the workspace speed rule). The loaded arms share the CPU by design and are reported without that limit.

**Outcome (2026-10-19, Deck; table in `analysis/golden/audio.json`).** The rule ends at step 3 with the floor reached, and the count is 6 under Wine.
- **Priority fails.** `highest` is set and read back (2), but `mcpx.apu_thread` keeps nice 0. The `deck` user's `RLIMIT_NICE` is 0, and Wine lowers nice only when that limit allows it. Raising the limit would be a system change; decided by the user (2026-10-19): the Deck's limit stays as stock. The priority key is not needed there, since 6 buffers is clean in normal play and the loaded arms were a synthetic stress test where the whole process loses CPU; the key stays an opt-in for native Windows. C and D track A and B within run-to-run noise.
- **Depth step 2 fails under load.** B has no underruns and no second below one period idle, but loaded its `q_min` p1 is 0. It has 36 % fewer underruns than A.
- **Step 3 fails too.** Count 8 is eligible (D4) but also drains loaded, with 22 % fewer underruns than B. The floor is reached.
- **Residual cause: (b) host scheduling of the whole process.**
  - The busy loops take CPU from every game thread: flips/s falls from 60 to 45 to 48 in every loaded arm.
  - (a) is ruled out: there are no trap spells loaded or idle.
  - (c) is ruled out: the frame thread's lock wait stays under 1 ms in every run, with none over 8 ms.
  - Only scheduling priority could address (b), and the Deck does not grant it.
- **The default is therefore 6.** It is the smallest count with a clean idle long bench, which is what the `audio` requirement asks for. Count 4 has 2 underruns idle. Count 8 adds 21 ms of lag for a partial gain under synthetic load only.

### D4. The latency budget

The chain is the device queue's high mark, plus FAudio's mix buffer, plus the PipeWire graph quantum. The quantum is read with `pw-top` during an arm-A run; the FAudio figure comes from its log or source for the Proton version. Eligible counts are those where the chain stays at or under 125 ms, the threshold for sound lagging the picture (ITU-R BT.1359).

As an expectation only (D4 measures it): at count 6, 64 ms plus a 1024-sample quantum (21.3 ms) plus FAudio is about 85 to 105 ms, which fits. At count 8, 85.3 ms plus the same is about 107 to 127 ms, which may not fit.

**Measured (2026-10-19).**
- PipeWire: `pw-top` shows the game's stream at quantum 256 (5.3 ms), with ERR 0, in every 0.1 run. The graph has `clock.quantum` 512 (10.7 ms) and `clock.min-quantum` 256.
- Device queue: the trace gives its floor, `q_min` p1 idle. That is 768 samples (16 ms) at count 4, 1280 (26.7 ms) at 6 and 2048 (42.7 ms) at 8. The high marks are 42.7, 64 and 85.3 ms.
- FAudio: its mix period under Wine was **not measured**. About 10 ms (one mmdevapi default period) is assumed.
- Chain with the 512 graph quantum: about 85 ms at count 6 and 106 ms at count 8. Both fit the 125 ms budget.
- No end-to-end lag measurement exists yet. That is the A/V sync check, `audio` 6.x.

## Risks / Trade-offs

- **Movies' lip sync.** Sound lags the picture by up to 21 ms more under Proton (43 ms at count 8), inside the D4 budget. The A/V sync check (`audio` change, 6.x) does not exist yet, so nothing measures it end to end.
- **Raised priority runs guest code high.** The DirectSound ISR runs on the frame thread, so a raised frame thread also raises guest code, with no priority inheritance on the locks it shares. `highest` is the most that can become a default, under Wine only. `time_critical` stays behind the DEBUG tier.
- **The loaded arm is synthetic.** Busy loops compete for cores but not for the GPU or memory the way a shader-compile burst does. The positive control makes sure it at least reproduces the symptom. The idle long runs stay the measurement of the real case.
- **A player's own `RECOMP_AUDIO_BUF_COUNT` keeps winning.** That is intended.
