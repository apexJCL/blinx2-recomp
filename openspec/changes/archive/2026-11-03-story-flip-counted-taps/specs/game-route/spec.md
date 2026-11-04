## MODIFIED Requirements

### Requirement: The story route to the hub is scripted on events
A built-in preset `@story-hub` SHALL take the title from boot through the intro (START skips the logos and the opening), the title (START when title state `0x5EB620` is 0), the story opening `R0_opening.sfd` (A skips it), the team editor (A through the defaults), back to the title and Story Mode / SAVE GAME (slot 1, 1P), the save write (`blinx2data.bin`), and the hub load (`song_HUBsw.adx`). Every step that leaves a screen SHALL end on a game event (a file open, a title-state value, or a poll count). Holds between those steps exist to land the golden frame dumps on the same screens from run to run. Holds and tap periods in the menus after the opening SHALL be counted in pad polls, which are one per flip there, so that a stalled present cannot move them in flips. Today these are `wait polls 476` on AUTO SELECT, `wait polls 416` on the SAVE GAME slot list, and taps every 90 polls. The one wall-clock hold is `wait until 24` after the opening, whose skip moment varies. The preset SHALL contain no `poke` step. The log SHALL show each matched event and `script done`.

#### Scenario: Hub reached on macOS and Proton
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@story-hub` from an empty save directory, normally and slowed down
- **THEN** the `[INPUT]` log shows the opens of R0_opening.sfd, tsedit, blinx2data.bin and song_HUBsw.adx in that order, then `script done`, and the hub renders

#### Scenario: Save created
- **WHEN** `@story-hub` finishes
- **THEN** `<save dir>/UDATA/4d530065/13C91777168C/blinx2data.bin` exists and is non-empty, and `SaveMeta.xbx` is beside it

#### Scenario: Present stalls do not move the menu anchors
- **WHEN** a D3D11 story run stalls present for seconds inside a dump window
- **THEN** the slot-list and hub anchors stay within the dump slack of their references, and story-menu and story-hub are checked (not INCOMPLETE)
