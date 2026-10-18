## Why

The tracker item came out of apu-mmio-direct. Once DirectSound's voice-register writes stopped faulting, `[APUMMIO-STATS]` still showed the APU handler at about 9 us per access under Proton, against 0.55 us on the Mac. At about 10.7k accesses a second that is roughly 96 ms of guest time a second, or 3.2 ms per 30 fps frame. The suspect was `voice_lock`, which takes the model's `d->lock` on every `NV1BA0_PIO_VOICE_LOCK` and on every `VOICE_ON` and `VOICE_RELEASE`. The frame thread holds that lock for its whole loop. This change measures that cost, then removes it.

**Measured** with a new trace, `RECOMP_TRACE=apu_lock` (toolkit `src/apu/apu_lockstat.{c,h}`). Every 5 s it prints, for each holder, a histogram of how long the lock was held. For each taker it prints how many takes found the lock already held and how long they waited. It also gives the time per se_frame stage and the count of pacing waits. All runs are stage 5-1 idle, steady state (t=130-135 s), one 5 s window. Logs are under `bench-logs/` and `xbox-recomp/runs/apulock/`.

| | Proton, `RECOMP_TRACE=apu` on (the setup) | Proton, lock trace only | Mac Metal, lock trace only |
|---|---|---|---|
| run | `20261012-125657` | `20261012-130003` | `runs/apulock/m-lockonly-51` |
| guest wait in voice_lock | 351-387 ms / 5 s (~75 ms/s) | 49-60 ms / 5 s (~11 ms/s) | 23-24 ms / 5 s (~4.7 ms/s) |
| contended takes | 670-755 of 12.6k (5-6%) | 570-680 of 13k (5%) | 1410-1480 of 12.9k (11%) |
| longest wait | 46-50 ms | 0.7 ms | 0.18-0.24 ms |
| frame-thread hold, total | 1.33-1.36 s / 5 s (27%) | 0.61 s / 5 s (12%) | 0.20 s / 5 s (4%) |
| frame-thread hold, longest | 46-47 ms | 0.15-0.18 ms | 0.08-0.12 ms |
| VP stage per se_frame | ~180 us mean, 2-8 ms bursts 25/s, ~45 ms 1/s | 78 us mean, max 143 us | 26 us mean, max 113 us |
| pacing waits / 5 s (7500 se_frames, 940 periods) | ~5100 | ~4600 | ~4100 |

The wait is real but small: about 11 ms of guest time a second, or 0.37 ms per 30 fps frame. Most of the "3.2 ms per frame" in the tracker item was the trace measuring itself. `RECOMP_TRACE=apu` turns on `vp_trace_positions` and `vp_stat_report`. Together they print about 1000 lines a second from inside the VP while the VP holds `d->lock`, in bursts of about 40 lines every 60 frames and one of about 47 lines every second. Under Wine every `fprintf(stderr)` is a slow host write, so each burst holds the lock for 2-8 ms, or about 45 ms for the per-second one. Any VOICE_LOCK that arrives during a burst waits for it.

What remains without the trace still costs something, and it scales with the host. About 95% of VOICE_LOCKs find the lock free (the frame thread is in its pacing wait). The other 5% land inside a se_frame and wait for the rest of it: about 78 us of VP under Proton on the Linux/Proton host, more on slower cores. The lock they wait on protects nothing in this port:

- **The VP never reads `voice_locked`.** Only VOICE_ON and VOICE_RELEASE read it, and only to decide whether to set and clear the bit around their own writes.
- **The voice writes run unlocked anyway.** VOICE_ON and VOICE_RELEASE do their voice-memory writes after `voice_lock` has dropped `d->lock`, as does every other PIO method (`TAR_VOL`, `TAR_PITCH` and the rest): `mcpx_apu_vp_write` → `fe_method` takes no lock. So the lock does not keep the VP away from a voice under update. All it does is wait for the end of a se_frame, then flip a bit nothing on the frame thread reads.
- **The `qemu_cond_signal(&d->cond)` belongs to a wait the port dropped.** It comes from xemu, whose `voice_work_dispatch` waits on `d->cond` while a queued voice is locked. That wait does not exist here. The signal now lands on `throttle()`'s pacing wait (or the idle wait), which has nothing to do with it.
- **The real MCPX does not make the CPU wait for the VP.** A PIO method write is posted into the front end's method FIFO, and `PIO_FREE` reports the space left in it. The CPU's store retires whatever the voice processor is doing.

**What this is not.** The tracker item was opened as a suspect for the Steam Deck slowdowns. At 0.37 ms per frame on the Linux/Proton host, this wait is not their main cause: a 30 fps frame is 33 ms, and the Deck runs are several frames behind, not one hundredth of one. The bigger lead in the same data is the frame thread itself: the VP costs 78 us per se_frame under Proton against 26 us on the Mac (3x), 1500 times a second, so the APU thread burns about 12% of a core under Proton before XAudio2's submits (another 12-13 ms a second). On the Deck's four cores that thread competes with the guest thread and the renderer. That is the next ticket (Impact), not this one. This change is still worth doing: it is a correct, small, upstream-shaped fix that removes a wait that grows with VP cost, and it removes the trace's own distortion so the next measurement is honest.

## What Changes

- **`voice_lock` becomes lock-free.** It sets or clears the voice's bit in `vp.voice_locked` with a 64-bit atomic or/and. It no longer takes `d->lock` and no longer signals `d->cond` (design.md D1, D2). `is_voice_locked` reads the word with an atomic load (today's `qatomic_read` in the shim is a plain dereference). The atomics go through `apu_shim.h` so that an MSVC build, which is upstream's primary toolchain, compiles them too. VOICE_ON and VOICE_RELEASE behave as before: they set the bit around their writes when the title has not already locked the voice.
- **APU trace output leaves the lock.** `vp_trace_positions`, `vp_stat_report` and the ring monitor's lines format into a buffer while the frame thread holds `d->lock`. The frame thread prints that buffer after its per-frame unlock, as `apu_lockstat` already does, so `RECOMP_TRACE=apu` stops inflating the wait it is used to measure (design.md D3).
- **`RECOMP_TRACE=apu_lock` stays as a trace.** It is default off and costs one well-predicted branch per lock operation and per se_frame. It gets a row in `docs/env.md`. After the fix it shows the frame thread's own holds and stage times, which is what the next APU performance question (the VP cost) needs.
- **Tests.** A new standalone ctest, `tests/apu_voice_lock`. With `d->lock` held by another thread, a VOICE_LOCK, VOICE_ON and VOICE_RELEASE must complete without waiting and leave the bits right. Concurrent lock and unlock of different voices in the same 64-bit word must lose no update. A wait on `d->cond` must not be woken by voice locks (design.md Validation). It joins the CLI's Proton test list, since the Wine critical section is where the cost was.

Not in this change: making the VP honour `voice_locked`, which is option C in design.md. It would be more faithful, but it changes what the VP renders. Nothing measured points to a torn multi-parameter update, so it is recorded as a follow-up in TASKS.md rather than done here.

## Impact

- Toolkit:
  - `src/apu/apu_vp.c`: `voice_lock`, `is_voice_locked`, the trace printers, and a flush hook.
  - `src/apu/apu_shim.h`: 64-bit atomic or/and and an atomic load, with `_Interlocked*64` under `_MSC_VER`.
  - `src/apu/apu_core.c`: the frame thread calls the trace flush after its unlock.
  - `src/apu/apu_lockstat.{c,h}`, `src/platform/recomp_env.h` (the `APU_LOCK_TRACE` row) and `src/apu/CMakeLists.txt`.
  - `tests/apu_voice_lock/` (new); `tests/posix_ctest.sh` picks it up as a standalone project.
- CLI: `apu_voice_lock` in `bench/host/tests.sh` and the step text in `bench/__init__.py`; cat's `game.toml` pin follows.
- Cat:
  - `docs/env.md`: the `apu_lock` row.
  - TASKS.md: the corrected figures, the option-C follow-up, the VP-cost follow-up, and a note on the tracker items that this was not their cause.
  - `analysis/upstream/pr-stack-plan.md`: the fix joins PR 6 (APU).
- Behaviour: no change to what is rendered. VOICE_LOCK no longer serialises against a se_frame. It never protected the VP's view of the voice anyway, because the voice writes ran unlocked. The frame thread's pacing wait now ends on its timeout or on a real register or resume signal.
  - **Residual race, unchanged in kind.** The title's `voice_set_mask` and the VP's envelope updates are both read-modify-writes of the same 32-bit voice words (`PAR_STATE`, `CUR_ECNT`), with no lock on either side today. A VOICE_RELEASE that lands while the VP is inside `voice_process` for that same voice can lose one side's update. Today that needs the frame thread to wake and start the next frame within the title's few-microsecond write; after this change the 5% of methods that land mid-frame write while the VP is running, so the window is wider. The fix for it is option C (the VP skips or defers a locked voice, as xemu does), which is why C stays listed. Audio goldens and the Burnout 3 run are the watch for it.
- Performance: under Proton, about 11 ms a second of guest wait (0.37 ms per frame) in 5-1 goes away, and more on slower hosts. With `RECOMP_TRACE=apu` on, the trace stops costing the guest about 75 ms a second. Whether the frame thread's pacing-wait count falls (about 4600 per 5 s today against 940 periods and 7500 se_frames) is a measurement, not a promise: the after-run reports it.
- Backends: shared APU code, so Metal and D3D11 agree by construction. Burnout 3 is affected: its vehicle-select freeze came from `voice_lock` starving on this lock (the comment above the frame thread's `SwitchToThread`). It runs under Proton on the exact toolkit head before merge.
- Upstream: `voice_lock`, `is_voice_locked` and the frame thread's per-frame release are identical at `origin/main` (v0.13.1), so upstream has the same wait and no fix of its own (upstream-first does not apply). The fix is a candidate for PR 6 (APU) in `analysis/upstream/pr-stack-plan.md`; the `apu_lock` trace is PR 8 material at most, and its `recomp_env` row stays fork-only (design.md, Upstream).
