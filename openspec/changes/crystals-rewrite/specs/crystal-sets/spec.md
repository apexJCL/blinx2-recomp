## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Player-facing name
The mod SHALL be shown to players as "BLiNX 1 crystals" on the Mods page
and in its enable row, while its id `crystals`, its key
`mods."crystals.enable"` and its env keys stay unchanged.

#### Scenario: Old settings
- **WHEN** a settings file sets `mods."crystals.enable" = "on"`
- **THEN** the mod named "BLiNX 1 crystals" is on
