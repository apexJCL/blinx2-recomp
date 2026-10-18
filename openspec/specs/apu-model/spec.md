# apu-model Specification

## Purpose
Defines how the APU model processes, decodes and locks voices so that queued voices are not lost, decode buffers are not overrun and lock methods and traces never wait on the APU frame thread.

## Requirements

### Requirement: The voice processor holds a frame while a queued voice is locked
Before it processes the voices queued for a frame, the APU voice processor SHALL wait while any of them is locked by `NV1BA0_PIO_VOICE_LOCK` (or by `VOICE_ON`/`VOICE_RELEASE` around their own writes), releasing the model lock while it waits, so that no voice is mixed while the title is mid-update on it. The wait SHALL end within 1 ms of the last such voice being unlocked, and SHALL end after at most 2 ms plus scheduling delay regardless, starting no wait that would end past that bound, after which the voice is mixed as it stands. A voice still locked when that bound runs out SHALL NOT hold any later frame until it has been unlocked. The guest's voice lock methods SHALL still never wait for the voice processor, and SHALL wake the frame thread's condition only to end this wait, while it is in progress.

#### Scenario: Hold and release
- **WHEN** a voice on a voice list is locked and a frame starts
- **THEN** the frame waits without processing that voice, and once the guest unlocks it the frame processes it, with no bound timeout counted

#### Scenario: The unlock wakes the hold
- **WHEN** the frame is holding and asleep, and the guest unlocks the held voice, twenty times over
- **THEN** most of those holds end inside their first 1 ms wait, counted by `hold_wakes`

#### Scenario: Title never blocks
- **WHEN** the frame is holding and the guest writes `VOICE_LOCK(1)`/`VOICE_LOCK(0)` on other voices and then unlocks the held voice
- **THEN** each write returns in under 5 ms

#### Scenario: Voice left locked
- **WHEN** a queued voice is locked and never unlocked
- **THEN** one frame holds for the 2 ms bound and then processes it, the next frame does not hold, and after the guest unlocks and locks it again a frame holds again

#### Scenario: Locked voice not queued
- **WHEN** a voice is locked but on no voice list
- **THEN** the frame does not hold

#### Scenario: Pacing wait undisturbed
- **WHEN** no frame is holding and the guest issues 1000 voice locks and unlocks while another thread waits on the frame thread's condition for 300 ms
- **THEN** that wait returns early fewer than 10 times

### Requirement: ADPCM voices cannot overrun the decode buffers
The voice processor SHALL decode ADPCM voices whose samples-per-block field is up to 18 blocks exactly as the block decoder does, and SHALL refuse a voice with a wider block, with a single warning, rather than read or decode past its buffers.

#### Scenario: Wide blocks
- **WHEN** an ADPCM mono voice uses each block width from 1 to 18
- **THEN** its fetched samples equal `adpcm_decode_block`'s for that block, and width 19 returns no samples

### Requirement: Voice lock methods do not wait for the APU frame thread
The APU model SHALL complete `NV1BA0_PIO_VOICE_LOCK`, `NV1BA0_PIO_VOICE_ON` and `NV1BA0_PIO_VOICE_RELEASE` without acquiring the lock the frame thread holds while it renders, and without signalling the condition the frame thread waits on. As on hardware, where PIO methods are posted to the front-end FIFO, a guest method write SHALL NOT wait for the voice processor. The voice's lock bit SHALL be set, cleared and read with atomic operations on its 64-bit word, so that concurrent writers to voices sharing a word lose no update, and the operations SHALL compile under MSVC as well as clang and GCC.

#### Scenario: Frame thread busy
- **WHEN** another thread holds the model lock for 200 ms and the guest writes `VOICE_LOCK(1)`, `VOICE_ON`, `VOICE_RELEASE` and `VOICE_LOCK(0)` for one voice
- **THEN** each write returns in under 20 ms, and the voice's lock bit reads set after `VOICE_LOCK(1)` and clear after `VOICE_LOCK(0)`

#### Scenario: Voice on leaves a title's lock alone
- **WHEN** the guest writes `VOICE_LOCK(1)` for voice A, then `VOICE_ON` for voice B in the same 64-bit word
- **THEN** afterwards A's bit is still set and B's bit is clear

#### Scenario: Concurrent writers
- **WHEN** two threads lock and unlock two voices in the same 64-bit word a million times each
- **THEN** both bits are clear afterwards, and locking each once more leaves exactly those two bits set

#### Scenario: Pacing wait undisturbed
- **WHEN** a thread waits on the frame thread's condition in 300 ms timed waits for 300 ms while the guest issues 1000 voice locks
- **THEN** the wait returns before its deadline fewer than 10 times

#### Scenario: Proton 5-1
- **WHEN** stage 5-1 idles under Proton on D3D11 with `RECOMP_TRACE=apu,apu_lock`
- **THEN** `[APU-LOCK]` reports no voice taker, the frame-thread hold maximum stays under 1 ms, and `[APUMMIO-STATS]` reports the handler at under 1 us per access

### Requirement: APU traces do not write while holding the model lock
APU trace output produced inside the voice processor (`RECOMP_TRACE=apu`: voice positions and `[APU-VSTAT]`; the `[APU-RING]` monitor) SHALL be formatted while the model lock is held and written after the frame thread releases it, with the same line formats and rates. When the formatted text exceeds the buffer, the excess lines SHALL be dropped and a marker line SHALL say how many.

#### Scenario: Trace on under Proton
- **WHEN** 5-1 idles under Proton with `RECOMP_TRACE=apu,apu_lock`
- **THEN** the `[APU] voice N pos=` and `[APU-VSTAT]` lines appear at their usual rate, and `[APU-LOCK]` shows no frame-thread hold over 1 ms
