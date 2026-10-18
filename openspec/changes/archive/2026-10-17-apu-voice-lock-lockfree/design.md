## Context

The MCPX APU model (toolkit `src/apu/`) runs on one frame thread. That thread takes `d->lock`, a `CRITICAL_SECTION` (a recursive pthread mutex through win32_compat on POSIX), and keeps it for its whole loop. It lets go only in three places:
- `throttle()`'s `qemu_cond_timedwait` (the pacing wait), and the idle `qemu_cond_wait` while `pause_requested`;
- around the interrupt post in `apu_deliver_irq`;
- the per-iteration unlock → `SwitchToThread` → lock at the bottom of the loop. That release was added after Burnout 3 froze on vehicle select, starved in `voice_lock`.

Guest-side PIO methods go through `mcpx_apu_mmio_write` → `mcpx_apu_dispatch_mmio` → `mcpx_apu_vp_write` → `fe_method` (`apu_vp.c`), with no lock on the way. Of the methods, only `voice_lock` takes `d->lock`. It runs for `NV1BA0_PIO_VOICE_LOCK`, and for VOICE_ON and VOICE_RELEASE when the voice is not already locked. Each time it:
1. takes the lock;
2. flips one bit in `vp.voice_locked[4]`;
3. calls `qemu_cond_signal(&d->cond)`;
4. unlocks.

**Who reads the bit.** `voice_locked` is read only by `is_voice_locked`, which only VOICE_ON and VOICE_RELEASE call. `mcpx_apu_vp_frame` never reads it. Note that the shim's `qatomic_read` is `(*(ptr))`, a plain load: nothing about today's read is atomic in the language sense.

**What the title's writes race with.** The VP walks the three voice lists through `NV_PAVS_VOICE_TAR_PITCH_LINK` in guest memory and, per active voice, read-modify-writes `PAR_STATE`, `PAR_OFFSET` and `CUR_ECNT` as it renders. VOICE_ON writes the list link and `PAR_STATE`; VOICE_RELEASE writes `CUR_ECNT` and `PAR_STATE`. All of these are `voice_set_mask` RMWs of 32-bit words, unlocked on both sides. The list walk tolerates a concurrent insert (a new voice's `next` is set before it is linked in, and the VP reads `top` once per frame), but two RMWs of the same word can lose one update. That race exists today; see D1 for what this change does to its window.

**What xemu does.** In xemu master (36334d9, `hw/xbox/mcpx/apu/vp/vp.c`, the author's reading; no local checkout), `voice_lock` takes the lock, sets the bit and signals the cond, and `voice_work_dispatch` defers to it: while any voice queued for this frame is locked, it waits on `d->cond` with a 1 ms timeout, with `d->lock` dropped. That deferral is xemu's whole reason for the signal, and it is also xemu's answer to the RMW race above: a title locks a voice, writes its parameters, unlocks, and the VP keeps off a locked voice. The port is single-threaded and has no such wait, so the signal now lands on `throttle()` or the idle wait. The implementer links the xemu lines in the code comment.

**Hardware.** A PIO method write is posted into the front end's method FIFO, and `PIO_FREE` reports the space left in it. The CPU's store does not wait for the voice processor. The VP's handling of a locked voice (skip it for the frame, or hold off) is described only through xemu's model. We have no MCPX documentation that pins it down further, so this change does not try to model it (Non-goals).

### Measurements

**Setup.** Stage 5-1 idle (`st5-idle.txt`), steady state, t=130 s and t=135 s windows of 5 s each.
- Proton: GE-Proton, D3D11, the Linux/Proton host, toolkit 9ffdb52 plus the lockstat trace.
- Mac: Metal, `SDL_AUDIODRIVER=dummy`.

**Histogram buckets.** log2 microseconds: [0,1) [1,2) [2,4) ... and a last bucket at 16.4 ms and over.

**Proton, `RECOMP_TRACE=apu,apu_lock,pacing=all`** (`bench-logs/20261012-125657`), the setup the tracker item was filed from:
- **voice taker:** 12.6k takes, 670-755 contended, waiting 351-387 ms in total, max 46-50 ms.
  - Contended waits: about 140 in [64,256) us, about 60 in [1,16) ms, and 4 at 16 ms or over.
- **frame holder:** 1.33-1.36 s held in total, max 46-47 ms.
  - About 5500 holds in [64,128) us, about 120 in [2,8) ms, and 5 at 16 ms or over.
- **VP stage:** 1.30-1.34 s in total.
  - Normal frames are [32,128) us. About 120 frames run [2,8) ms and 5 run 16 ms or over.
  - Those counts line up with `vp_trace_positions` (about 40 lines every 60 frames, about 25 bursts a second) and `vp_stat_report` (about 47 lines every 1500 frames, once a second).
- **DSP stage:** under 10 us. **Monitor stage:** under 2 ms, about 2 ms a second in total.
- **XAudio2 submit:** 16-46 us per period, max 1.7 ms. Not a factor.
- **APUMMIO handler:** 8.8 us per access at about 10.7k accesses a second.

**Proton, `RECOMP_TRACE=apu_lock,pacing=all`** (`bench-logs/20261012-130003`), with no APU trace:
- **voice taker:** 12.9-13.0k takes, 567-682 contended, waiting 48.6-59.7 ms in total, max 0.69-0.72 ms.
  - Contended waits: about 70-110 in [1,16) us, about 170 in [64,256) us, and 26-63 in [256,512) us.
- **voice holds:** 0.6 us each (7.6 ms per 13k).
- **frame holder:** 605 ms held in total (12% of wall time), max 145-181 us. About 7450 holds in [64,128) us (the se_frames) and about 4600 in [0,1) us (the pacing loop's re-takes).
- **frame taker** (the re-take after `SwitchToThread`): 7512 takes, 600-730 contended, waiting under 0.3 ms in total.
- **VP stage:** 78 us mean, max 143 us. **se_frame:** 80 us mean, 7504 per 5 s.
- **pace_waits:** about 4600 per 5 s, against about 938 EP periods and 7504 se_frames.

**Mac Metal, `RECOMP_TRACE=apu_lock,pacing=all`** (`runs/apulock/m-lockonly-51`):
- **voice taker:** 12.9k takes, 1410-1480 contended (11%), waiting 22.7-23.9 ms in total, max 180-240 us.
  - Contended waits: about 600 in [4,8) us and about 600 in [16,64) us.
- **voice holds:** 0.23 us each.
- **frame holder:** 201-203 ms held in total (4%), max 84-116 us.
- **VP stage:** 26 us mean. **se_frame:** 26.7 us mean.
- **Monitor stage:** 0.4 ms in total, against 13-14 ms under Proton, where the XAudio2 submit is 12-13 ms of that. Not a factor.
- **pace_waits:** about 4100 per 5 s.

**Mac Metal, `RECOMP_TRACE=apu,apu_lock`** (`runs/apulock/m-before-51`):
- **voice taker:** 12.9k takes, about 1150 contended (9%), waiting 23-25 ms in total, max about 300 us.
- **frame holder:** 217 ms held in total, max 270-400 us. **se_frame:** 29 us mean.
- **pace_waits:** about 5000 per 5 s.
- **APUMMIO handler:** 0.55 us per access.

On macOS the trace's stderr writes are cheap, so the trace barely moves the Mac numbers.

**Reading.**
- **Trace inflation.** The tracker item's "about 9 us per access, about 3.2 ms per frame" is mostly `RECOMP_TRACE=apu` printing from inside the VP with the lock held. Wine's stderr writes are slow.
- **Without the trace.** The wait is about 11 ms of guest time a second under Proton, about 0.37 ms per 30 fps frame, and about 4.7 ms a second on the Mac.
  - Its cause: about 5% of VOICE_LOCKs land while a se_frame is in flight, and each waits for the rest of it, 78 us of VP on the Linux/Proton host.
  - It grows with VP cost, so a slower host (Steam Deck) pays more both ways: a longer hold, and more takes landing inside one. It is still a fraction of a millisecond per frame, so it is not what the tracker items are about (proposal.md).
- **Pacing waits.** 4600 waits per 5 s is about five per EP period, or 0.6 per se_frame. `voice_lock`'s signal is one explanation (each wake re-runs `mcpx_apu_pace_step` and sleeps again); the pacer's one-frame-per-frame band mode is another, since it wakes per se_frame on purpose. The trace does not separate them. D2 removes the signal because nothing waits for it, not because of this count; the after-run says how much of the count was the signal.
- **The bigger number.** The frame thread holds the lock 12% of wall time under Proton against 4% on the Mac, and nearly all of it is the VP stage: 78 us against 26 us for the same voices. That is the frame thread's own cost, which this change does not touch (Non-goals), and it is the lead for the next ticket.
- **Spin count would not help.** `InitializeCriticalSectionAndSpinCount` (option A) spins for at most a few microseconds. That does not cover a 78 us hold, and Wine's critical sections already spin briefly.

## Goals / Non-Goals

**Goals**
- VOICE_LOCK, VOICE_ON and VOICE_RELEASE never wait for the frame thread.
- The pacing wait is no longer woken by voice locks.
- `RECOMP_TRACE=apu` no longer holds `d->lock` while it writes to stderr.
- A standalone ctest for each of the three, run on POSIX and under Proton.
- A trace (`apu_lock`) that shows lock holds and se_frame stage cost per host, for the next APU performance question.
- Code that builds with MSVC as well as clang, since it is upstream-bound.

**Non-Goals**
- **Making the VP honour `voice_locked`** (option C below). It is a behaviour change to rendering, unmeasured as a problem, and recorded as a follow-up.
- **VP cost.** The VP runs 78 us per se_frame on the Linux/Proton host against 26 us on the Mac. That is per-voice resampling and envelope work, and it is a separate question (TASKS follow-up, with a hypothesis list: `mcpx_apu_phys` per sample word, the page-map lookups in it, the resampler, and the Wine `QueryPerformanceCounter` calls the trace itself makes). This change makes the guest stop waiting for it. It does not make it cheaper.
- **The frame thread's per-iteration `SwitchToThread` release.** It stays. The trap path and `apu_mixer_play` still take `d->lock`, and removing the release is not needed for this fix.
- **The RMW race between the title's `voice_set_mask` and the VP's.** Pre-existing (Context); its fix is option C.

## Decisions

### D1. `voice_lock` flips the bit atomically, with no `d->lock`

```c
static void voice_lock(MCPXAPUState *d, uint16_t v, bool lock)
{
    uint64_t mask = 1ULL << (v % 64);
    assert(v < MCPX_HW_MAX_VOICES);
    if (lock)
        qatomic_or64(&d->vp.voice_locked[v / 64], mask);
    else
        qatomic_and64(&d->vp.voice_locked[v / 64], ~mask);
}

static bool is_voice_locked(MCPXAPUState *d, uint16_t v)
{
    uint64_t mask = 1ULL << (v % 64);
    assert(v < MCPX_HW_MAX_VOICES);
    return (qatomic_load64(&d->vp.voice_locked[v / 64]) & mask) != 0;
}
```

with, in `apu_shim.h` beside `qatomic_or`:

```c
#ifdef _MSC_VER
#define qatomic_or64(p, v)   _InterlockedOr64((__int64 volatile *)(p), (__int64)(v))
#define qatomic_and64(p, v)  _InterlockedAnd64((__int64 volatile *)(p), (__int64)(v))
#define qatomic_load64(p)    ((uint64_t)_InterlockedOr64((__int64 volatile *)(p), 0))
#else
#define qatomic_or64(p, v)   __atomic_fetch_or((p), (v), __ATOMIC_SEQ_CST)
#define qatomic_and64(p, v)  __atomic_fetch_and((p), (v), __ATOMIC_SEQ_CST)
#define qatomic_load64(p)    __atomic_load_n((p), __ATOMIC_ACQUIRE)
#endif
```

**Why lock-free is enough.**
- The bit's only readers are VOICE_ON and VOICE_RELEASE in `fe_method`. Its writers are the title thread and a DPC on the timer thread (`voice_lock`'s existing prof comment names both). An atomic RMW keeps concurrent writers to the same 64-bit word safe, and an atomic load keeps the compiler from caching or tearing the read.
- The VP's view of the voice is unchanged. It never read the bit, and the voice-memory writes in VOICE_ON and VOICE_RELEASE already ran after the unlock.
- **Memory ordering.** The bit orders nothing else: no reader infers anything about voice memory from it. Relaxed would do. The RMWs are sequentially consistent anyway because on x86 a lock-prefixed instruction is one regardless, on arm64 the cost is a fence pair per method (a few ns against the 0.3-0.6 us the lock took), and it leaves option C's Dekker handshake with nothing to re-order later. The load is acquire for the same reason.
- **What is lost:** today a VOICE_LOCK cannot complete in the middle of a se_frame. Nothing depends on that: the writes it would order run unlocked whatever happens. What widens is the RMW race window described in Context: the 5% of methods that used to wait for the end of the frame now write while the VP is running. The VP is inside `voice_process` for one voice at a time, so the method has to hit that voice, in that word, inside its RMW. That is rare, pre-existing in kind, and option C's to close. `audio-check` on the goldens and the Burnout 3 run are the watch.

**Why the shim pair, not the raw builtin.** `apu_shim.h`'s existing `qatomic_or` and `qatomic_and` are `__sync_fetch_and_*` on GCC and clang, which is fine for `uint64_t`, but under `_MSC_VER` they are `_InterlockedOr` on `long`, which would truncate a 64-bit word to its low 32 bits. Every build we ship is clang (Apple clang, llvm-mingw), but upstream's README builds with Visual Studio 2022 (MSVC) or MinGW-w64, and this fix is upstream-bound (Upstream below). So the new ops get their own names with a correct 64-bit MSVC branch, in the file whose job that is. The raw `__atomic_*` would fail to compile under MSVC, which is not acceptable for a PR.

**The prof hook.** `XBOX_PROF_WAIT_APULOCK` (`RECOMP_TRACE=dpc`) loses its only caller. Keep the enum and its report column, which will read 0, so `dpc` logs stay comparable across the change. Note the reason next to the enum.

### D2. No `qemu_cond_signal` from `voice_lock`

The signal is xemu's wake for `voice_work_dispatch`'s locked-voice wait, which the port does not have. Every waiter on `d->cond` in the port is in `apu_core.c`, and each has its own wake:
- **The idle wait** (`pause_requested`). Woken by `mcpx_apu_resume`, `mcpx_apu_wait_for_idle`, the `ISTS`/`SECTL`/`FECTL` register-write broadcasts, `apu_mixer_play` and shutdown. `voice_lock` never cleared `pause_requested`, so its wake only made the thread re-check and sleep again.
- **The trapped-FE 1 ms wait.** Woken by the `FECTL` write broadcast, with a timeout.
- **The pacing wait.** It has a timeout and wants no early wake: an early wake re-runs `mcpx_apu_pace_step` and goes back to sleep. The schedule is time-based, so a voice starting does not need to pull the next frame forward.

Nothing else waits on `d->cond` (`apu_mmio_hook.c`, `apu_dsp.c`, the mixer and the tests included). Dropping the signal removes a `WakeConditionVariable` per method, which under Wine is a futex or wineserver round trip, and whatever share of the 4600 pacing waits per 5 s it caused (Measurements, Pacing waits).

If option C is ever done, the signal comes back with the wait it serves.

### D3. Trace printers format under the lock, print after it

`vp_trace_positions`, `vp_stat_report` and the ring monitor (`vp_ring_report` once a second, and its `[APU-RING] stale` lines) run inside `mcpx_apu_vp_frame`. They format their lines with `snprintf` into a static buffer. `vp_stat_report` loops over all `MCPX_HW_MAX_VOICES` (256) and prints about 200 bytes per voice that rendered anything, so the worst case is about 50 KB, not the 16 KB a two-list estimate gives: the buffer is 64 KB. If it fills, the excess lines are dropped and a `[APU] trace lines dropped: N` marker is appended.

A new `mcpx_apu_vp_trace_flush()` writes the buffer to stderr and empties it. The frame thread calls it after `apu_lockstat_unlock` at the bottom of its loop, beside `apu_lockstat_flush()`. The buffer is written and flushed by the frame thread only, so it needs no lock of its own.

Line formats and rates stay as they are. Log parsers (`audio-check`, the `[APU-VSTAT]` readers) see the same text, at most one frame later.

Still printed under the lock, and left alone: the `[APU-IRQ]` line once every 5 s, the `[APU] started by the title` line, and the error `DPRINTF`s. One line per 5 s is below the noise; a hold they cause shows in `[APU-LOCK]` if it ever matters.

### D4. Keep `apu_lockstat` as `RECOMP_TRACE=apu_lock`

**Placement.** The trace stays in the TRACE tier of `recomp_env`, default off. It is a measurement tool only, with no behaviour of its own.

**Cost when off.**
- Each lock and unlock wrapper, and each se_frame stage timer, checks a cached int.
- With D1, the voice path no longer goes through the wrappers at all.

**What it reports after the fix.**
- Frame-thread holds and takes, takes by `apu_mixer_play` and the stage times.
- The `voice` holder and taker lines disappear, because the voice path no longer goes through the wrappers. That is not the proof that D1 worked: the proof is `[APUMMIO-STATS]`'s handler time per access (8.8 us → near the Mac's 0.5 us, with `RECOMP_TRACE=apu,apu_lock`, and the 0.55 us floor without it), and the frame-ms and flips/s before and after.

**Clock.** Windows uses QPC. POSIX uses win32_compat's QPC shim (the clock is `mach_absolute_time` or `CLOCK_MONOTONIC` underneath), so the same code serves both.

### Options weighed

- **A. Spin count on the critical section.** Rejected. The wait is for the rest of a 78 us se_frame (up to 0.7 ms seen), far beyond a useful spin. It changes nothing on POSIX, where the lock is a pthread mutex.
- **B. Lock-free bit (D1) plus no signal (D2).** Chosen. Behaviour is identical as far as the VP is concerned. It matches posted PIO writes on hardware and removes the wait completely.
- **C. B, plus the VP honouring `voice_locked`.** Deferred. The frame thread would publish the voice it is processing, with a sequentially consistent store, Dekker-style against the setter. VOICE_LOCK(1) would wait only while that one voice is mid-process, and the VP would skip or defer a locked voice as xemu does at frame granularity. It is the faithful model of what the lock is for: a title's multi-parameter voice update lands in one frame, and the RMW race in Context closes.
  - **Costs.** It changes what is rendered, through skipped or deferred voices. It brings a handshake with its own ordering risks. It needs audio goldens across both games.
  - **Evidence for it.** None measured today: no audible tearing on a voice update has been reported in either game.
  - **Status.** A TASKS follow-up with this text. Revisit if a torn update is ever heard, or if `audio-check` moves after this change.
- **Per-voice locks instead of `d->lock`.** Rejected. Equivalent to C's handshake but heavier, and pointless while the VP ignores the bit.

## Upstream

This is toolkit code that upstream also has, so the upstream rules apply (CLAUDE.md; `analysis/upstream/pr-stack-plan.md`; the README at `origin/main`).

- **Upstream-first.** `voice_lock`, `is_voice_locked` and the frame thread's `SwitchToThread` release are byte-identical at `origin/main` (v0.13.1, 193e299). Upstream has not touched this, so there is no upstream version to prefer.
- **README adherence.** Upstream builds with MSVC (Visual Studio 2022) or MinGW-w64, C11. Hence D1's shim pair with `_Interlocked*64` instead of raw `__atomic_*`: *conform*. Upstream has no `recomp_env`; the plan's binding decision is plain `getenv` in PRs. The `apu_lock` trace therefore stays fork-only unless PR 8 (diagnostics) wants it, in which case it goes over as `getenv("RECOMP_APU_LOCK_TRACE")`: *fork-only for now*. The fix itself has no env switch, so it carries nothing of the table.
- **Placement.** PR 6 (APU), beside the other `apu_vp.c`/`apu_core.c` changes. The commit for it is D1 + D2 + the ctest, title-neutral, with D3 as a second commit (it is a trace fix, but it changes `apu_vp.c` lines the same PR touches). The PR text states Proton and macOS/Metal testing on the exact head, native Windows untested, and that the ctest ran under Proton. No tracker references in it.
- **Burnout 3 gate.** Required before merge here, on the exact toolkit head (Validation).

## Risks / Trade-offs

- **Burnout 3 vehicle select.** Its freeze was `voice_lock` starving on `d->lock`. B removes that dependency entirely. The frame thread's `SwitchToThread` release stays for the other takers. A Proton run through vehicle select and one race is required.
- **The RMW race window.** Described in Context and D1. Pre-existing in kind, wider in window, closed by option C. Watched by `audio-check` on the goldens and by the Burnout 3 run; an audible or measured change reopens C.
- **Hidden reliance on frame-boundary ordering.** Something might implicitly rely on VOICE_LOCK ordering with se_frame boundaries: a title that writes VOICE_LOCK and then reads VP-updated voice state, expecting a frame to have finished. The lock never guaranteed that; it only waited for the current frame to end, not for a new one. Audio goldens (`audio-check`) and the B3 run would show a change.
- **Lost `d->cond` wake.** A waiter that relied on voice_lock's signal would now sleep to its timeout. D2 lists every waiter. Each has its own wake or a timeout of 1 ms or one pacing step.
- **MSVC path untested.** We cannot build with MSVC. The shim branch is written from the documented `_InterlockedOr64`/`_InterlockedAnd64` signatures and reviewed, not compiled; the PR says so.

## Validation

- **`tests/apu_voice_lock`** (new standalone ctest, POSIX and Win32, picked up by `posix_ctest.sh` as a project). It brings the model up as `tests/apu_lifecycle` does (`mcpx_apu_init_standalone` on a small zeroed RAM, every `xa2_*` faked), sets `NV_PAPU_VPVADDR` so the voice array lives in that RAM, and drives methods through `mcpx_apu_mmio_write` at the VP offset. The frame thread idles on `d->cond` after init, which matters for case 3.
  1. **No wait.** A helper thread takes `d->lock` and holds it 200 ms. Meanwhile the test thread writes `SET_CURRENT_VOICE`, `VOICE_LOCK(1)`, `VOICE_ON`, `VOICE_RELEASE` and `VOICE_LOCK(0)`. Each must return in under 20 ms, and the bit must read set after `VOICE_LOCK(1)` and clear after `VOICE_LOCK(0)` (a `VOICE_LOCK(1)` on a second voice, then `VOICE_ON` on the first, checks that VOICE_ON leaves a locked bit alone and clears its own).
  2. **No lost updates.** Two threads lock and unlock voices 3 and 5, which share a word, 1M times each, through `mcpx_apu_mmio_write`. Afterwards both bits are clear, and a final lock of each leaves exactly those two bits set.
  3. **No wake.** A helper thread loops `qemu_cond_timedwait(&d->cond, &d->lock, 300)` until 300 ms have passed on its own clock, counting returns before the deadline, while the test thread issues 1000 VOICE_LOCKs. The early-return count must be under 10 (spurious wakeups are legal, a signal per method is not). Counting, rather than timing one wait, is what makes the check robust while the idle frame thread is a second waiter on the same cond: `qemu_cond_signal` wakes one waiter, so the old code would still wake the helper hundreds of times.
  4. **Negative control.** Cases 1 and 3 fail on the pre-change `voice_lock` (case 2 passes on both: the old lock protected the word, the new atomics do). Record that output in the branch notes.
- **Trace flush.** With `RECOMP_TRACE=apu,apu_lock` under Proton, the frame-thread hold max stays under 1 ms in `[APU-LOCK]`. Before the change it was 46 ms. The `[APU] voice N pos=` and `[APU-VSTAT]` lines appear at their usual rate.
- **The ctest under Proton.** The Wine critical section is where the cost was, so the ctest also runs there.
  - Add `apu_voice_lock` to the CLI's standalone list in `bench/host/tests.sh` and to the step text in `bench/__init__.py`, as `apu_irq` already is. That is a one-line `xboxrecomp-cli` change, and the cat `game.toml` pin follows it.
  - Its threads go through win32_compat on POSIX and through the Win32 API on Windows, as `apu_irq`'s do.
- **Before/after under Proton, 5-1 idle and Mission 1-2:**
  - `[APU-LOCK]`: the voice taker line is gone; frame-thread hold max; `pace_waits`, reported as measured;
  - `[APUMMIO-STATS]` handler us per access, with `RECOMP_TRACE=apu,apu_lock`: 8.8 → close to the Mac's 0.5; and without the APU trace, at the 0.55 us floor;
  - frame ms p50 and p99, and flips/s. Flag a 25% flips/s drop or 1.5x frame-ms rise as a blocker, per CLAUDE.md.
  - Mac Metal the same, as a no-regression check.
- **Steam Deck.** The Deck is where the tracker items were seen, and a game run there needs the user's session. Ask the user for one before/after pair (5-1 idle, `RECOMP_TRACE=apu_lock`, flips/s) on the Deck when convenient. Without it the Deck figure is a projection from the Linux/Proton host, and the proposal says so.
- **Gates.**
  - Mac build.
  - `tests/posix_ctest.sh` 0 FAIL.
  - Metal goldens, plus D3D11 goldens through `blinx2 bench golden`.
  - `audio-check` on the golden runs, compared with the previous golden's: any movement reopens option C before merge.
  - Burnout 3 under Proton on the exact toolkit head (vehicle select and a race), with an `[APU-LOCK]` excerpt and the head sha in the notes.
  - Review.
