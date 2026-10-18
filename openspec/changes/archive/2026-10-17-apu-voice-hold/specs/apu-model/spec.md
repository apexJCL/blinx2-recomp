## ADDED Requirements

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
