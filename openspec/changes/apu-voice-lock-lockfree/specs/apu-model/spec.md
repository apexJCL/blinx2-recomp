## ADDED Requirements

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
