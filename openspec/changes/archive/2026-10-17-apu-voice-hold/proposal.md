## Why

The fork's `voice_lock` went lock-free in apu-voice-lock-lockfree (toolkit 66587631): `NV1BA0_PIO_VOICE_LOCK` flips a bit in `vp.voice_locked` with a 64-bit atomic, takes no `d->lock` and signals nothing. That fixed the Burnout 3 vehicle-select freeze (the title blocked in `voice_lock` at raised IRQL behind the frame thread, which held off every USB interrupt) and the Proton cost of waking the pacing wait on every lock. It left one gap, written down in its comment and in TASKS: the VP never reads the bit. A title's writes after `VOICE_LOCK(1)` (pitch, buffer, envelope, volume) can land while the VP processes that same voice, so one frame can mix a half-updated voice.

xemu closes that gap on the mix side. `voice_work_dispatch` (hw/xbox/mcpx/apu/vp/vp.c at 36334d9, lines 1721-1738) loops `if (!any_queued_voice_locked(d)) break; qemu_cond_timedwait(&d->cond, &d->lock, 1);` before it processes the frame's queued voices, and its `voice_lock` signals `d->cond` to end that wait early.

Upstream PR #217 (MattSG) reworks VOICE_LOCK into a per-voice spinlock held around `voice_process`; that keeps the title waiting on the VP and still leaves the same window, since the spinlock is released inside `voice_lock`. The same PR carries an independent ADPCM fix (b380f021): `voice_get_samples` decodes into stack buffers sized for two 36-byte blocks while the descriptor allows up to 32, an overrun the fork shares.

## What Changes

- **The mix holds while a queued voice is locked** (toolkit `src/apu/apu_vp.c`). `mcpx_apu_vp_frame` walks the three voice lists first, queueing the active voices, then holds, then processes the queue. The hold drops `d->lock` in 1 ms timed waits on `d->cond` until no queued voice is locked.
- **The title side stays non-blocking.** `voice_lock` remains an atomic or/and. On an unlock it signals `d->cond`, but only while the hold is waiting (`vp.hold_waiting`), so the pacing wait is not woken by voice locks the rest of the time.
- **The hold is bounded** at 2 ms (`VP_HOLD_MAX_US`). Past the bound the voice is mixed as it stands (the pre-change behaviour), and a voice still locked then is exempt from further holds until the title unlocks it, so a voice left locked costs one bounded wait rather than every frame.
- **ADPCM bounds** from upstream #217 b380f021: buffers for 18 blocks (`ADPCM_MAX_BLOCKS`), a wider voice refused with one warning, and its `tests/apu_vp` ctest adapted to the fork.
- **Diagnostics:** `[APU-HOLD]` totals (holds, timeouts, longest) once a second under `RECOMP_APU_TRACE`, beside `[APU-VSTAT]`.
- **Tests:** `tests/apu_voice_lock` gains the hold, the release on unlock, the bound and its exemption, and title methods returning at once while the mix holds.
- **Upstream:** a revised comment for #217 offering the hold, credited to xemu (`notes/newprs/c217-hold.md`, not posted by the agent).

## Impact

- Toolkit: `src/apu/apu_vp.c`, `src/apu/apu_state.h`, `src/apu/apu_regs.h`, `tests/apu_voice_lock/`, new `tests/apu_vp/`.
- Behaviour: what the VP renders changes only in frames where the title holds a voice lock across the frame boundary; then that frame waits for the update (at most 2 ms) instead of mixing a mix of old and new parameters.
- Hosts: BLiNX 2 Metal goldens on the Mac; audio checks on BLiNX 2 and Burnout 3 (Mac headless with a WAV dump, Steam Deck under Proton). The Linux/Proton host is not available for this change (PC booted into Windows).
- This narrows apu-voice-lock-lockfree's requirement that voice lock methods never signal the frame thread's condition: an unlock signals it while, and only while, the hold waits.
