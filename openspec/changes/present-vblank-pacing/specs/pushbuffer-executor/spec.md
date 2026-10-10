## ADDED Requirements

### Requirement: A flip waits for the guest vblank its presentation interval asks for
The pushbuffer executor SHALL NOT let the title see a flip complete sooner than the swap's presentation interval allows, counted on the guest's 60 Hz vblank clock (`xbox_VblankCount`).

The interval is decoded from D3D's swap software method (`NO_OPERATION` with `(param & 0x1F) == 1`: `interval = (param >> 5) & 7`, IMMEDIATE = `(param >> 5) & 8`). A FLIP_STALL with no swap NOP since the previous one SHALL count as interval 1, and interval 0 with IMMEDIATE SHALL never hold. After a FLIP_STALL whose target vblank (`last_flip_vblank + interval`) hasn't arrived, the walker SHALL:
- finish its current segment;
- leave `DMA_GET` equal to the `PUT` it walked to;
- not walk the next segment;
- not acknowledge the KickOff flush, on either kick path,

until the vblank count reaches the target. The frame SHALL still be presented at the FLIP_STALL, on every backend (CPU, D3D11, Metal). `last_flip_vblank` SHALL be `max(target, count at FLIP_STALL)`, the count sampled when the walk that reaches the FLIP_STALL began (the title's kick of its Swap segment), not after the segment's draws; the hold's 100 ms clock starts at the FLIP_STALL, before the backend's present.

The hold SHALL run on the walker's own thread (`nv2a-ack`) and SHALL hold no lock while it waits: not the guest CPU, not the DISPATCH gate, not the DPC lock, not a backend lock. Its release SHALL depend only on `xbox_VblankCount()` and host time, never on a guest thread. The ack loop SHALL call `xbox_SpinWake()` whenever it clears the kick bit.

The hold SHALL NOT apply:
- while the vblank clock is off, or hasn't advanced for 100 ms;
- inside a pushbuffer CALL;
- for longer than 100 ms of host time.

`RECOMP_DEBUG=flip_pacing=0` SHALL restore the immediate FLIP_STALL. `RECOMP_DEBUG=flip_pacing=edge` SHALL select D3D's rule, `target = max(last_flip_vblank + interval, count at FLIP_STALL + 1)`, interval 0 with IMMEDIATE still never holding and a late ONE_OR_IMMEDIATE flipping at once; it is an A/B switch and the goldens pin the default.

#### Scenario: Burnout 3 front end on Metal
- **WHEN** Burnout 3 boots on the Mac with the Metal backend and sits in the attract loop and menus
- **THEN** flips.py shows about 60 flips/s per 10 s bucket after the boot clears (not about 350), the vblank stays at 60 Hz, and the intro movies take their real length

#### Scenario: Burnout 3 race on Metal
- **WHEN** the scripted race runs on Metal
- **THEN** the race buckets show at most about 60 flips/s (not 70-90), and the HUD race clock advances at wall-clock rate between two dumped frames

#### Scenario: Host display faster than 60 Hz
- **WHEN** Burnout 3 runs on D3D11 under Proton on the Steam Deck's 90 Hz screen
- **THEN** the menus run at 60 fps, not 90, and the audio stays in phase with the picture

#### Scenario: A title that paces itself is held only at interval changes
- **WHEN** BLiNX 2 runs its story, stage 1 and attract goldens
- **THEN** the goldens pass unchanged, on Metal and on D3D11 under Proton; the pacing trace reports holds only rarely (under 1% of flips, each about one vblank, where the title's swap interval changes), `hold_timeouts` 0 and no stand-down log line; flips/s and raster ms stay within the bench thresholds on the CPU backend too

#### Scenario: Slow backend is not quantised
- **WHEN** a frame reaches FLIP_STALL `interval` or more vblanks after the previous flip
- **THEN** the walker doesn't hold, and the CPU backend's flips/s is unchanged within the bench thresholds

#### Scenario: Standalone rule
- **WHEN** `tests/flip_hold` drives the rule with these cases: interval 1 frames at 5 ms, interval 2, IMMEDIATE, no swap NOP, a 20 ms frame, a stopped vblank clock, a 100 ms timeout and `last_flip` after it, two stalls in one walk, a count wrap, and the 20 ms frame and a late ONE_OR_IMMEDIATE under `edge`
- **THEN** the hold arms and releases at exactly the vblank the rule gives, never holds in the slow, immediate and stopped-clock cases, holds the slow frame to the next edge only under `edge` (a late ONE_OR_IMMEDIATE still flips at once), adds no held time for a stall nothing waited on, and counts the timeout

### Requirement: A held title's KickOff spin yields
The KickOff spin on PFB 0x100410 bit 16 SHALL be a listed spin-wait site (`config/spin_waits.json`) in every title the hold ships for (BLiNX 2 at 0x002E7F20, Burnout 3 at 0x00351BF0 in `sub_00351BD0`), so that a title held in KickOff yields the guest CPU under the guest-CPU lock and sleeps under `present.pacing=sleep`. A site the matcher rejects SHALL be fixed in the matcher, with a test, not dropped from the list.

#### Scenario: Burnout 3 on the Mac with the guest-CPU lock
- **WHEN** Burnout 3 runs on Metal with the guest-CPU lock on and the hold active
- **THEN** the spin-site trace shows the KickOff site yielding, and the APU reports no more underruns than a run with `flip_pacing=0`

### Requirement: A frame counter the title moves itself is left to the title
A counter registered with `xbox_Nv2aFrameCounter` SHALL be advanced by the toolkit (per flip, and by the 60 Hz fallback) only until the toolkit sees it advanced by something else since its own last write. The first bump SHALL always happen and seed the last-written value; the comparison starts with the second. From then on the toolkit SHALL NOT write it, and SHALL say so once in the log. A counter that went backwards SHALL stay the toolkit's. `RECOMP_DEBUG=flip_pacing=0` SHALL restore the unconditional bump.

#### Scenario: A counter that starts non-zero
- **WHEN** a registered counter already holds a non-zero value at the toolkit's first bump and nothing else moves it afterwards
- **THEN** the toolkit bumps it and keeps bumping it; it is not stood down

#### Scenario: Burnout 3's vblank count
- **WHEN** Burnout 3's vblank DPC starts incrementing device + 0x1DE8 (the miniport's vblank count) after D3D initialises
- **THEN** the toolkit stops bumping it, the log says so once, and the count advances at 60 per second

#### Scenario: A counter only the toolkit moves
- **WHEN** a title's registered counter is never written by the title
- **THEN** the toolkit keeps advancing it per flip and by the 60 Hz fallback, as before
