## Context

- `mcpx_apu_vp_frame` runs on the APU frame thread with `d->lock` held. It walked each voice list and called `voice_process` inline for each active voice.
- `voice_lock` (title thread, or a DPC on the timer thread) is a lock-free 64-bit atomic or/and on `vp.voice_locked`. History in its comment and in `apu_core.c`'s per-frame unlock comment: while it took `d->lock`, Burnout 3 froze on its vehicle select; while it signalled `d->cond`, Proton saw about 1000 needless pacing-wait wakes a second.
- `VOICE_ON` and `VOICE_RELEASE` set and clear the bit around their own writes when the title has not locked the voice.
- In the game the only other waits on `d->cond` are the frame thread's own (pacing in `throttle`, the idle wait, the trapped-FE wait), so during the hold no other waiter can steal a wake. `tests/apu_voice_lock` runs the mix on a test thread while the idle frame thread also waits on `d->cond`, and there the idle thread took every plain signal on macOS (D3).

## Goals / Non-goals

- Goal: the VP never processes a voice in a frame while the title has it locked, within a bound.
- Goal: no title-side wait of any kind, and no cond signal outside the hold.
- Non-goal: a multithreaded VP (xemu's worker pool). The queue reuses `VoiceWorkDispatch`'s queue fields, single-threaded.
- Non-goal: #217's volume ramps and HRTF default; they are separate.

## Decisions

### D1. Walk then process, as xemu

The list walk queues active voices into `vp.voice_work_dispatch.queue` and issues the idle-voice trap for inactive ones; processing follows the hold. The hold then sees every voice the frame will touch before it touches any. Processing one voice never changes another's active state or list link, so the split renders what the inline loop rendered when nothing is locked.

### D2. The hold

`vp_hold_locked_voices` builds a 256-bit mask of queued voices, then loops: read the four lock words, drop exemptions for voices now unlocked, `held = locked & queued & ~exempt`. Nothing held: done. Otherwise it sets `hold_waiting` (an atomic RMW, before the next check of the bits) and waits `qemu_cond_timedwait(&d->cond, &d->lock, 1)` with the lockstat hold ended around the wait, as the other waits do. Once a further 1 ms wait would end past the bound (D4) it yields instead, dropping `d->lock` around `SwitchToThread()`. Both drop `d->lock`, so `apu_mixer_play` and anything else that takes it is not kept waiting.

### D3. The wake

`voice_lock(…, false)` clears the bit, then reads `hold_waiting` and broadcasts on `d->cond` when set. Each side does a seq-cst RMW and then a seq-cst load of the other's word: `qatomic_load64` is `__atomic_load_n(…, __ATOMIC_SEQ_CST)` off MSVC (it was acquire, which does not order a load after an earlier store to another word) and `_InterlockedOr64(p, 0)`, a full barrier, on MSVC. So either the hold's check sees the cleared bit or the unlock sees `hold_waiting`. A wake can still arrive between the hold's check and its sleep (the waker holds no mutex); it is then lost, and the 1 ms timed wait catches the cleared bit. Correctness never depends on the wake; it only shortens the wait. Locks (`VOICE_LOCK(1)`) never wake anything.

A broadcast, not a signal: in the game the frame thread is the only waiter, so the two are the same; in the ctest the idle frame thread also waits, and with a signal it took the wake in 20 of 20 tries on macOS, so the test could not show the wake ends the hold.

Rejected: signalling on every unlock (the Proton pacing-wake cost again); a spin or `SwitchToThread` poll for the whole hold (burns a core under Proton while a title thread is preempted, and keeps `d->lock` unless dropped by hand; the hold yields only for the last part of the bound, D4); taking `d->lock` in `voice_lock` as xemu does (the vehicle-select freeze).

### D4. The bound: at most 2 ms plus scheduling delay, then exempt until unlocked

A title's update is a handful of PIO stores between `VOICE_LOCK(1)` and `VOICE_LOCK(0)`: microseconds when its thread runs. The bound only matters when that thread is preempted mid-update or never unlocks.

- 2 ms is three 32-sample VP frames: one 1 ms poll, as xemu's, then yields to the bound, so an update that straddles the poll finishes.
- The deadline is checked before each wait: a 1 ms wait that would end past the bound is not started, and the hold yields with `d->lock` dropped until the bound instead. Checking only after each wait let holds reach 2.8-3.9 ms on a loaded Mac with no timeout counted, because a 1 ms timed wait there oversleeps. A hold still runs past 2 ms by however late the scheduler resumes the frame thread.
- The device queue's low pacing mark is half the device buffers (1024 samples, ~21 ms, with SDL2's 1024..2048 marks on the Mac), so a held frame is absorbed by pacing slack and cannot underrun the device by itself.
- Past the bound the voice is mixed as it stands: the pre-change behaviour, never worse.
- A voice still locked at the bound joins `hold_exempt` until its bit is seen clear. Without that, a title that leaves a voice locked would cost 2 ms per 0.67 ms VP frame and run the mix at a third of real time. With it, it costs one bounded wait per lock.

xemu has no bound; there a voice left locked stops the mix.

### D5. Counters

`hold_count`, `hold_timeouts`, `hold_max_us` and `hold_wakes` are frame-thread fields in `MCPXAPUVPState`. `hold_wakes` counts holds that ended after their first 1 ms wait returned in under 0.9 ms. It is meant to count the unlock's broadcast, but any early return counts: a spurious wake, the ISTS/FECTL broadcasts in `apu_core.c`, the `apu_mixer_play` signal, or `SleepConditionVariableCS` returning early on native Windows. The ctest asserts it, so the test fails if the unlock's wake is removed (checked on macOS only: 0 of 20 without it, 20 of 20 with it). The ctest reads them; `RECOMP_APU_TRACE` prints them as `[APU-HOLD]` once a second, through the VP trace buffer (printed after the frame thread's unlock, as the other VP trace lines are).

### D6. ADPCM bounds (upstream #217 b380f021)

Taken as written, with its test. The fork's `apu_vp.c` includes `recomp_env.h` and calls `apu_lockstat_hold_*`, so `tests/apu_vp` links the `platform` target (recomp_env and the POSIX Win32 shims; an INTERFACE target on Windows) and stubs the two lockstat calls.

## Risks

- A title that relies on the VP mixing a voice while locked (no known case; xemu, which most titles are tested on, holds without a bound).
- A title that locks voices so often that holds add up: `[APU-HOLD]` shows it; each hold is capped at 2 ms plus scheduling delay.
- Test timing on a loaded host: the release case asserts that no timeout fired, and the unlock follows the hold's start by microseconds.

## Validation

- `tests/apu_voice_lock`: existing no-wait, lost-update and no-wake cases unchanged; new cases:
  - hold: a frame with a locked queued voice waits (`hold_waiting` set, voice not processed);
  - title never blocks: VOICE_LOCK on another voice and the unlock each return in under 5 ms while the hold waits;
  - release: the frame ends only after the unlock and processes the voice, with one hold and no timeout;
  - wake: over 20 repetitions the unlock, sent once the hold sleeps, ends most holds inside the first poll (`hold_wakes`);
  - bound: a voice left locked holds the frame for 2 ms, then is processed; the next frame does not hold; after an unlock and a fresh lock it holds again; a locked voice on no list never holds.
- `tests/apu_vp`: every width 1-18 decodes as `adpcm_decode_block` does, 19 is refused; the old code fails under AddressSanitizer.
- `tests/posix_ctest.sh`: 0 FAIL. BLiNX 2 Metal goldens. BLiNX 2 and Burnout 3 audio on the Mac (`SDL_AUDIODRIVER=dummy`, `RECOMP_AUDIO_WAV`) against the base build, and on the Steam Deck under Proton.
