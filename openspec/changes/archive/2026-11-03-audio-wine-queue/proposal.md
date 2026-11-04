## Why

Under Proton, players hear audio crackle, most often around a scene load (the SSX 3 race load). The XAudio2 device queue holds at most 4 x 512 samples (42.7 ms), and the pacer keeps it between 1024 and 2048 samples queued. A gap in submissions longer than 21 to 43 ms drains it.

The feed does not depend on the main thread. The dedicated host thread `mcpx.apu_thread` renders and submits every period (toolkit `src/apu/apu_core.c`: created at 1416, loop at 1147, submit at 954). A render-thread stall does not stop it: a 477 ms load hitch on the Deck caused no underrun. Three things can still starve it:
- **(a) A trapped front end** waiting for DirectSound's interrupt routine. A guest thread holding the dispatch gate can delay that routine.
- **(b) Host scheduling.** The APU thread runs at normal priority, and under Wine a burst of busy threads can preempt it for longer than the queue lasts.
- **(c) Lock contention.** The frame thread takes the APU model lock `d->lock`, which guest MMIO also takes (`apu_core.c:315-320`). If the host preempts a guest thread while it holds that lock, the frame thread waits behind it: priority inversion.

A 620 s Deck run with the host audio trace showed no trap spells and one underrun, with a 24.6 ms submit gap. That rules out (a), but it does not separate (b) from (c); the A/B adds the lock statistics to tell them apart.

A feed independent of the main thread already exists, so the remaining options are:
- a deeper device queue, which absorbs (b) and (c) at the cost of latency;
- a higher APU thread priority, which fixes (b) at no latency cost if Wine applies it, but not (c), because a raised frame thread still waits for a preempted guest lock holder.

## What Changes

- **Toolkit `src/apu/apu_xaudio2.c`:** under Wine (`xbox_HostUnderWine()`), the device buffer count defaults to 6 instead of 4, giving at most 64 ms queued.
  - The Deck A/B (design D3 outcome) chose 6. It is the smallest count with a clean idle long bench.
  - Under a synthetic 7-loop CPU load every count still drains. 6 has 36 % fewer underruns than 4, and 8 has 22 % fewer than 6. The cause is host scheduling of the whole process. The pacing marks follow it, because `xa2_pacing_marks` derives them from the count. `RECOMP_AUDIO_BUF_COUNT` still overrides on every host. Native Windows and the SDL2 backend (macOS, Linux) keep 512 x 4.
- **Toolkit, new CONFIG key `RECOMP_AUDIO_THREAD_PRIORITY`:**
  - Values: `normal` or `highest`, applied to `mcpx.apu_thread` with `SetThreadPriority` on Windows builds. `time_critical` is accepted only behind the DEBUG tier (design D2). The key is ignored on POSIX.
  - Default: `normal` everywhere. The key stays opt-in for hosts that honour it, such as native Windows, where it is untested until the PC is up.
  - The A/B found that Wine on a stock Deck does not apply it. The Win32 priority reads back `highest`, but the thread's nice stays 0, because the `deck` user's `RLIMIT_NICE` is 0. Raising that limit (the `gamemode` group or limits.d) would be a system change. Decided by the user (2026-10-19): the Deck's limit stays as stock. The priority key is not needed there, since 6 buffers is clean in normal play and the loaded arms were a synthetic stress test where the whole process loses CPU; the key stays an opt-in for native Windows.
- **Toolkit:** the APU thread is named with `SetThreadDescription` so it can be found on the Linux side.
- **cat:**
  - a `docs/env.md` row for the new key;
  - the `audio` requirement on buffer defaults amended for the Wine default;
  - the A/B table in `analysis/golden/audio.json` (`about`).

## Latency and stock behaviour

**One effect.** The pacer renders up to the high mark ahead of what is heard, so a deeper queue makes the sound lag the picture by more.
- The guest's audio clock (the APU's rendered position) runs that far ahead of the speakers.
- Movies that slave video to the audio clock (Sofdec) therefore show each frame as much earlier than its sound.

**The cost.** With 6 x 512 buffers the pacer holds 1536 to 3072 samples instead of 1024 to 2048: 32 to 64 ms, which is 10.7 ms more at the low mark and 21.3 ms more at the high. With 8 buffers it is 85.3 ms at the high mark.

**The budget.** The threshold for sound lagging the picture is about 125 ms (ITU-R BT.1359; the ~45 ms figure is for sound leading). The whole chain counts:
- the device queue;
- FAudio's mix buffer;
- the PipeWire quantum (the Deck's graph quantum, read with `pw-top`).

The A/B measures the last two (design D4). Any count whose chain total exceeds 125 ms is not eligible as a default.

**Stock behaviour changes under Proton only.** Native Windows and the POSIX hosts are untouched, so the Mac goldens and native Windows see no change. Under Proton nothing guest-visible changes except the audio clock's lead over the speakers: the APU still advances one period per EP frame, and the pacing rules are unchanged. The priority key changes nothing at its default.
