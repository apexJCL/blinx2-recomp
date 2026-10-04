## Purpose

The normal route from boot to play (logos, title, START, story opening, team editor, save, hub, stage 1-1), driven on game events as a regression check and walked by hand with a real controller, so the menus and the save path are covered and not just the debug stage select.

## ADDED Requirements

### Requirement: The story route to the hub is scripted on events
A built-in preset `@story-hub` SHALL take the title from boot through the intro (START skips the logos and the opening), the title (START when title state `0x5EB620` is 0), the story opening `R0_opening.sfd` (A skips it), the team editor (A through the defaults), back to the title and Story Mode / SAVE GAME (slot 1, 1P), the save write (`blinx2data.bin`), and the hub load (`song_HUBsw.adx`). Every step SHALL wait on a game event (a file open, a title-state value, or a poll count), never on wall-clock time alone, and the preset SHALL contain no `poke` step. The log SHALL show each matched event and `script done`.

#### Scenario: Hub reached on macOS and Proton
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@story-hub` from an empty save directory, normally and slowed down
- **THEN** the `[INPUT]` log shows the opens of R0_opening.sfd, tsedit, blinx2data.bin and song_HUBsw.adx in that order, then `script done`, and the hub renders

#### Scenario: Save created
- **WHEN** `@story-hub` finishes
- **THEN** `<save dir>/UDATA/4d530065/13C91777168C/blinx2data.bin` exists and is non-empty, and `SaveMeta.xbx` is beside it

### Requirement: Each scripted story run starts from an empty save directory
The host SHALL honour `RECOMP_SAVE_DIR` as the root for the title's UDATA and TDATA on every host, and the bench SHALL give each story run a fresh, empty directory under that run's log directory, so a second run still takes the SAVE GAME path and not LOAD GAME. The directory SHALL stay local and gitignored.

#### Scenario: Two story runs in a row
- **WHEN** `bench.sh golden` runs the `story` scenario twice on the same host
- **THEN** both runs show the SAVE GAME menu (not LOAD GAME) and both `[INPUT]` logs match step for step

### Requirement: The story route is a golden scenario
`golden.json` SHALL hold a `story` scenario on `@story-hub` with the host pad and keyboard pinned off, with at least these reference frames: the Story Mode / SAVE GAME menu, the team editor, and the first hub frame. The scenario SHALL pass three runs in a row on the Linux/Proton host before its references are merged, under the same record and limit rules as the existing scenarios.

#### Scenario: Story golden passes
- **WHEN** `bench.sh golden` runs on the integration heads
- **THEN** the `story` frames pass their limits alongside `attract` and `stage1`

### Requirement: The route to stage 1-1 without the debug menu
Once the path from the hub to stage 1-1 is mapped, a preset `@story-stage1` SHALL continue from `@story-hub` to stage 1-1 and end, like `@stage1`, when `0xAE73FC` becomes 1, with no `poke` step. If the training drill cannot be passed deterministically from a script, the preset SHALL instead start from a seeded save (`RECOMP_SAVE_SEED=<dir>`, a locally kept, never committed, tutorial-complete save) and the design SHALL record why. The seeded leg from the title to the hub SHALL be its own preset, `@story-load` (LOAD GAME, slot 1, on title-state and file events), which `@story-stage1` then extends; a seed that cannot be read or copied SHALL stop the run before boot.

#### Scenario: Stage 1-1 by the front door
- **WHEN** the title runs with `@story-stage1`
- **THEN** the log shows stg0101 opening and `mem 0x00AE73FC = 0x1`, the HUD timer runs, and no `poke` line appears

### Requirement: The normal route is checked by hand with a real controller
A checklist SHALL cover the route with a real controller on Proton: which movies START or A skips, the title, the story opening, the team editor, Story Mode, the save prompt and slots, the hub drill, and stage 1-1; the prompts the menus show with no save, with a save and with no controller; what happens when the controller is unplugged in a menu and in play; the stick feel (drift, deadzone), the trigger and shoulder mapping and rumble. A completed checklist SHALL be kept locally with the bench-logs stamp of the run, and its findings SHALL be summarised in the change.

#### Scenario: Checklist run
- **WHEN** the user walks the route on the Linux/Proton host with their controller
- **THEN** each checklist item is marked pass, fail or not applicable, with the bench-logs stamp, and every fail has a follow-up task or a deviations entry

### Requirement: Menu prompts are catalogued
The change SHALL record, per menu state the route passes through, the title-state value, the files the title opens on entry, the buttons it accepts and the prompts it shows, including the save and memory-unit behaviour (no memory unit is ever present) and any controller-removed behaviour found.

#### Scenario: Catalogue complete
- **WHEN** the `@story-hub` preset is written
- **THEN** every tap and wait in it cites an entry of the catalogue

### Requirement: Reference frames from xemu under the safety rules
The xemu capture scripts SHALL gain a `story` scenario that follows the same route with the virtual pad, so the story golden frames can be compared with hardware-accurate references. The existing rules stand: the user's xemu instance, config, HDD and EEPROM are never touched; the run refuses to start while any xemu instance is running; frames stay local.

#### Scenario: Story frames compared
- **WHEN** `xemu_capture.sh story` and `xemu_compare.py` run on the Linux/Proton host
- **THEN** each story golden frame has a best-match xemu frame and a mean-absolute-error figure in `analysis/reference/xemu/`, and no file under it is tracked
