# game-route Specification

## Purpose
The normal route from boot to play (logos, title, START, story opening, team editor, save, hub), driven on game events as a regression check and walked by hand with a real controller, so the menus and the save path are covered and not just the debug stage select.

## Requirements

### Requirement: The story route to the hub is scripted on events
A built-in preset `@story-hub` SHALL take the title from boot through the intro (START skips the logos and the opening), the title (START when title state `0x5EB620` is 0), the story opening `R0_opening.sfd` (A skips it), the team editor (A through the defaults), back to the title and Story Mode / SAVE GAME (slot 1, 1P), the save write (`blinx2data.bin`), and the hub load (`song_HUBsw.adx`). Every step that leaves a screen SHALL end on a game event (a file open, a title-state value, or a poll count). Wall-clock holds are allowed only between those steps, to land the golden frame dumps on the same screens from run to run (today `wait until 24` after the opening, whose skip moment varies, `wait 8` on AUTO SELECT, `wait 7` on the SAVE GAME slot list, and taps every 1.5 s in the menus; the archived input-real-devices design, "Golden `story`"). The preset SHALL contain no `poke` step. The log SHALL show each matched event and `script done`.

#### Scenario: Hub reached on macOS and Proton
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@story-hub` from an empty save directory, normally and slowed down
- **THEN** the `[INPUT]` log shows the opens of R0_opening.sfd, tsedit, blinx2data.bin and song_HUBsw.adx in that order, then `script done`, and the hub renders

#### Scenario: Save created
- **WHEN** `@story-hub` finishes
- **THEN** `<save dir>/UDATA/4d530065/13C91777168C/blinx2data.bin` exists and is non-empty, and `SaveMeta.xbx` is beside it

### Requirement: Each scripted story run starts from an empty save directory
The host SHALL honour `RECOMP_SAVE_DIR` as the root for the title's UDATA and TDATA on every host, and the bench SHALL give each story run a fresh, empty directory under that run's log directory, so a second run still takes the SAVE GAME path and not LOAD GAME. The directory SHALL stay local and gitignored.

#### Scenario: Two story runs in a row
- **WHEN** `blinx2 bench golden` runs the `story` scenario twice on the same host
- **THEN** both runs show the SAVE GAME menu (not LOAD GAME) and both `[INPUT]` logs match step for step

### Requirement: The story route is a golden scenario
`golden.json` SHALL hold a `story` scenario on `@story-hub` with the host pad and keyboard pinned off, with at least these reference frames: the Story Mode / SAVE GAME menu, the team editor, and the first hub frame. The scenario SHALL pass three runs in a row on the Linux/Proton host before its references are merged, under the same record and limit rules as the existing scenarios.

#### Scenario: Story golden passes
- **WHEN** `blinx2 bench golden` runs on the integration heads
- **THEN** the `story` frames pass their limits alongside `attract` and `stage1`

### Requirement: The normal route is checked by hand with a real controller
A checklist SHALL cover the route with a real controller on Proton: which movies START or A skips, the title, the story opening, the team editor, Story Mode, the save prompt and slots, the hub drill, and stage 1-1; the prompts the menus show with no save, with a save and with no controller; what happens when the controller is unplugged in a menu and in play; the stick feel (drift, deadzone), the trigger and shoulder mapping and rumble. A completed checklist SHALL be kept locally with the bench-logs stamp of the run, and its findings SHALL be summarised in the archived input-real-devices change (`openspec/changes/archive/2026-10-13-input-real-devices/tasks.md` 6.6).

#### Scenario: Checklist run
- **WHEN** the user walks the route on the Linux/Proton host with their controller
- **THEN** each checklist item is marked pass, fail or not applicable, with the bench-logs stamp, and every fail has a follow-up task or a deviations entry

### Requirement: Menu prompts are catalogued
The catalogue, the "Menu catalogue" section of `openspec/changes/archive/2026-10-13-input-real-devices/design.md`, SHALL record, per menu state the route passes through, the title-state value, the files the title opens on entry, the buttons it accepts and the prompts it shows, including the save and memory-unit behaviour (no memory unit is ever present) and any controller-removed behaviour found.

#### Scenario: Catalogue complete
- **WHEN** the `@story-hub` preset is written
- **THEN** every tap and wait that leaves a screen cites an entry of the catalogue
