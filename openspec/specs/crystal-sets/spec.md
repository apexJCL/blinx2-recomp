# crystal-sets Specification

## Purpose
TBD - created by archiving change crystal-sets. Update Purpose after archive.

## Requirements

### Requirement: Crystal row
With the `crystals` mod on, in a Sweepers stage, each crystal the game
counts SHALL go into a four-slot row in pickup order. The third crystal of
one colour in the row SHALL grant that colour's control once and the fourth
SHALL grant it again; the row SHALL empty when it holds four crystals.

#### Scenario: Three of a colour
- **WHEN** the row holds two REW crystals and a REW crystal is picked up
- **THEN** one REW control goes into the stock and the row holds three

#### Scenario: Mixed row
- **WHEN** four crystals of which no three match are picked up
- **THEN** no control is granted and the row is empty

### Requirement: Stock rules kept
Grants SHALL go through the game's own pickup: a control at its cap SHALL
pay gold as in BLiNX 2, the d-pad pick and the controls' use SHALL be
unchanged, and an item SHALL be counted as often as the game counts it
(natural play counts it once).

#### Scenario: Cap full
- **WHEN** a set completes for a control whose held count is at its cap
- **THEN** gold is paid and the held count stays at the cap

### Requirement: Stock when off and outside Sweepers
With the mod off (the default) the game SHALL run as stock. In Tom Tom and
VS the pickup and the HUD SHALL be stock even with the mod on. Switching
the mod live SHALL empty the rows of a Sweepers stage.

#### Scenario: VS
- **WHEN** the mod is on and a VS stage is played
- **THEN** crystals count per colour as in stock

### Requirement: Row carried by the record
The row SHALL live in the team record's count bytes so that checkpoints,
retries and the stage start treat it like the stock counts.

#### Scenario: Retry
- **WHEN** the player retries from a checkpoint
- **THEN** the row is the one saved at that checkpoint
