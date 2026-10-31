## ADDED Requirements

### Requirement: The debug menu opens from the in-game menu at PRESS START
With `mods."debug_menu.enable" = "on"` (env `RECOMP_DEBUG_MENU`), the
`debug_menu` mod SHALL add an "Open the debug menu" row and a "Status" row
to its page of the in-game menu. Pressing the row, or the `debug_menu.open`
host action, while the title shows PRESS START (scene `[0xAE73F0]` 0x81 or
0x9C, `[0x5EB5F4] == 0x5EB620` and `[0x5EB620] == 0`) SHALL write, from the
guest thread, `[0xB22E3C] = 1`, `[0xAE7A10] = 0`, `[0x5EB630] = 0`,
`[0x5EB638] = 0` and then `[0x5EB620] = 1`. The binding SHALL work with the
overlay menu off (`RECOMP_MENU=0`).

#### Scenario: Stage picked by hand
- **WHEN** the mod is on, the title shows PRESS START, and the player
  presses the row, closes the menu, picks 1P_MISSION(NORMAL) and a stage
- **THEN** the game's debug menu and SELECT A STAGE show, and the stage loads

#### Scenario: Elsewhere
- **WHEN** the row is pressed outside PRESS START, including during the
  logos and intro movies before the title first runs
- **THEN** nothing is written, a toast says to go to PRESS START, and the
  Status row says the same

### Requirement: Unsafe debug rows are skipped
Debug-menu rows found to hang the port SHALL be listed in
`dbgm_unsafe`; while the debug menu shows and the mod is on, a cursor on
such a row SHALL be moved to the next safe row in the direction it moved.

#### Scenario: Cursor past an unsafe row
- **WHEN** the cursor moves down onto an unsafe row
- **THEN** it lands on the next safe row below it

#### Scenario: Step and A in one poll
- **WHEN** a step onto an unsafe row and A arrive in the same pad poll
- **THEN** the row picked is the next safe row in that direction

### Requirement: Off is stock
With the mod off (the default), the mod SHALL write no guest memory, and
`game.toml` `[golden] enhance_stock` SHALL list
`"mods.debug_menu.enable" = "off"`. The mod and its settings SHALL appear in
the mods describe dump (`RECOMP_MODS_DESCRIBE`).

#### Scenario: Goldens
- **WHEN** the goldens run with `RECOMP_MENU=0` and the mod off
- **THEN** their verdicts are unchanged
