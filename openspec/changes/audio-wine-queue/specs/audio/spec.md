## MODIFIED Requirements

### Requirement: Buffer sizes are tunable and the defaults are measured
Device buffer length SHALL default to 512 samples on every host. Device buffer count SHALL default to 4, except in the Windows build running under Wine (`xbox_HostUnderWine()`), where it SHALL default to 6, the count chosen by the measurement. Both SHALL be overridable with `RECOMP_AUDIO_BUF_SAMPLES` and `RECOMP_AUDIO_BUF_COUNT` on every host. The pacing marks SHALL follow the resolved size and count. The chosen defaults SHALL be the smallest combination measured under Proton on the Deck that gives no underruns over the long bench and the golden scenarios; the measurement SHALL be recorded in `analysis/golden/audio.json` (`about`). When the Wine default applies, the `[XA2] XAudio2 initialized` line SHALL say so.

#### Scenario: Override
- **WHEN** `RECOMP_AUDIO_BUF_SAMPLES=1024 RECOMP_AUDIO_BUF_COUNT=3` is set
- **THEN** the boot log's `[XA2] XAudio2 initialized` line reports 1024 x 3 on any host

#### Scenario: Wine default
- **WHEN** the Windows build starts under Proton with neither key set
- **THEN** the `[XA2] XAudio2 initialized` line reports 512 x the Wine count and `(wine default)`, and the `[APU] Using XAudio2 audio backend` line reports the pacing marks for that count

#### Scenario: Native hosts unchanged
- **WHEN** the Windows build starts on native Windows, or the POSIX build starts on macOS, with neither key set
- **THEN** the backend reports 512 x 4, as before this change

## ADDED Requirements

### Requirement: APU thread priority
`RECOMP_AUDIO_THREAD_PRIORITY` SHALL accept `normal` and `highest` and SHALL default to `normal` on every host. It is opt-in for hosts that honour it. `time_critical` SHALL be honoured only with the DEBUG-tier key `audio_thread_tc` on; otherwise it SHALL be reported once and treated as `highest`. When the key is set, Windows builds SHALL set the APU frame thread to the resolved priority at creation and log the value read back, or the error when the call fails; when it is unset, nothing SHALL be logged. Another value SHALL be reported once and treated as `normal`. POSIX builds SHALL report once that the key is ignored.

### Requirement: APU thread is named
On Windows builds the APU frame thread SHALL be named `mcpx.apu_thread` with `SetThreadDescription` when the host provides it (looked up at run time), so it can be identified on the Linux side under Wine.

#### Scenario: Raised on Proton
- **WHEN** SSX 3 runs under Proton with `RECOMP_AUDIO_THREAD_PRIORITY=highest`
- **THEN** the log has `[APU] thread priority highest` with the value read back, and the `mcpx.apu_thread` task's nice on the Linux side drops below 0 only when the user's `RLIMIT_NICE` allows it (on a stock Deck it stays 0)
