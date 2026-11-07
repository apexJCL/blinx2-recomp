# crystal-sets Specification

## Purpose
TBD - created by archiving change crystal-sets. Update Purpose after archive.

## Requirements

### Requirement: Crystal row
With the `crystals` mod on, in a Sweepers stage, each crystal the game
counts SHALL go into a four-slot row in pickup order. The third crystal of
one colour in the row SHALL grant that colour's control once and the fourth
SHALL grant it again; the row SHALL empty when it holds four crystals.
Every crystal in the row SHALL be drawn with an icon of its colour; a heart
crystal SHALL be drawn with the heart the game shows above the heart gauge.

#### Scenario: Three of a colour
- **WHEN** the row holds two REW crystals and a REW crystal is picked up
- **THEN** one REW control goes into the stock and the row holds three

#### Scenario: Mixed row
- **WHEN** four crystals of which no three match are picked up
- **THEN** no control is granted and the row is empty

#### Scenario: Heart crystal
- **WHEN** a heart crystal is picked up into the row
- **THEN** its slot shows the gauge's heart, not an empty slot

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
retries and the stage start treat it like the stock counts. A death and
retry SHALL keep the row as it was at the death, as the stock counts are
kept. The row's heart crystals, at most two, SHALL also be kept in the
RETRY count byte, so the stock lit hearts above the heart gauge show them.

#### Scenario: Retry
- **WHEN** the player dies and retries
- **THEN** the row is the one held at the death, crystals picked after the
  last checkpoint included

#### Scenario: Checkpoint load
- **WHEN** the game loads a checkpoint's saved copy of the record
  (`sub_001A90F0`)
- **THEN** the row is the one saved at that checkpoint (not tested live)

#### Scenario: Lit hearts
- **WHEN** the row holds one or two heart crystals
- **THEN** that many hearts light above the heart gauge

### Requirement: Player-facing name
The mod SHALL be shown to players as "BLiNX 1 crystals" on the Mods page
and in its enable row, while its id `crystals`, its key
`mods."crystals.enable"` and its env keys stay unchanged.

#### Scenario: Old settings
- **WHEN** a settings file sets `mods."crystals.enable" = "on"`
- **THEN** the mod named "BLiNX 1 crystals" is on
