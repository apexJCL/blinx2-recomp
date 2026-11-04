## Purpose

Defines the in-game menu's System tab, with Restart game and Quit game: how the player asks for them, how saves are kept safe, when a restart is refused, and how a restart rebuilds the game as a fresh boot inside the same window on every host.

## ADDED Requirements

### Requirement: A System tab offers Restart game and Quit game behind confirms
The in-game menu SHALL have a System tab, after the toolkit's other tabs, for every game built with the enhancements layer. It SHALL hold a "Restart game" row and a "Quit game" row. Activating either row SHALL open a modal dialog that says progress since the last in-game save is lost, with the action's button and Go Back, and the focus on Go Back. When menu settings are unsaved, the dialog SHALL instead offer the action without saving, Save settings and the action, and Go Back, and SHALL list the unsaved settings as the leave dialog does. No input other than the dialog's action buttons SHALL restart or quit the game.

#### Scenario: Confirm and restart
- **WHEN** the player opens the System tab, selects Restart game, moves to Restart and presses A
- **THEN** the game restarts as a fresh boot in the same window

#### Scenario: A double press does nothing
- **WHEN** the player presses A on the Restart game row or the Quit game row and then A again at once
- **THEN** the second press activates Go Back, the dialog closes and the game keeps running

#### Scenario: Quit with unsaved settings
- **WHEN** two menu settings are unsaved and the player selects Quit game
- **THEN** the dialog names both settings and offers Quit without saving, Save settings and quit, and Go Back; Save settings and quit writes them to the config file before the game closes

### Requirement: A bindable action opens the Restart confirm, never the restart
The toolkit SHALL register a host action `game.reset` labelled "Restart game", with no default binding. Firing it SHALL open the menu on the Restart game dialog and SHALL NOT restart the game by itself. Going back from that dialog SHALL return to the game.

#### Scenario: Bound to a key
- **WHEN** the player binds `game.reset` to F8 and presses F8 during play
- **THEN** the menu opens on the Restart game dialog with the focus on Go Back

#### Scenario: Scripted pad
- **WHEN** a pad script presses the buttons bound to `game.reset`
- **THEN** the action does not fire

### Requirement: Restart and Quit never tear or lose a save
Before a restart or a menu quit, the runtime SHALL wait until the title has no file open under its `UDATA` or `TDATA` trees and has not touched one for 2 s, waiting at most 10 s. It SHALL then stop every further open of a save file from completing until the new boot starts or the process ends, so no save can start between the check and the action. When the 10 s pass while the title is still saving, the action SHALL be called off with the message that the game is saving, and the game SHALL keep running unchanged. Everything the title wrote before the action SHALL be on disk for the next boot.

#### Scenario: Restart right after an in-game save
- **WHEN** the player saves in game, picks Restart within a second, and loads that save after the new boot
- **THEN** the restart waits until the save's files are closed and quiet, and the loaded save holds the progress just saved

#### Scenario: Title keeps saving
- **WHEN** the title holds a save file open for more than 10 s after the player picks Restart
- **THEN** the dialog says the game is saving, nothing restarts, and the save completes

#### Scenario: Save attempted during the restart
- **WHEN** a title thread opens a save file after the freeze has been taken
- **THEN** that open does not complete, no partial save file is left behind, and the new boot opens save files normally

### Requirement: Restart is refused during automation
The Restart game row SHALL be shown greyed out, with the reason as its help line, and both the row and `game.reset` SHALL do nothing except log `[RESET] refused (<reason>)`, while any of these is in force: a DEBUG-tier runtime key (including the deterministic mode, pad scripts, pad records and frame or audio dumps), `RECOMP_WINDOW_QUIT_AFTER`, a headless run, the game's own automation reason, the game having turned the action off or not booting through the toolkit's boot loop, an enabled mod that declares or uses guest state, pokes or hooks without a reset callback, or a `HalReturnToFirmware` already under way. A request while a restart is already running SHALL be ignored with `[RESET] already running`. A golden run SHALL never show the System tab.

#### Scenario: Deterministic run
- **WHEN** the menu is opened in a run with `RECOMP_DEBUG=deterministic`
- **THEN** Restart game is greyed out with "deterministic mode" as its reason, and selecting it does nothing

#### Scenario: Recording a pad session
- **WHEN** `RECOMP_PAD_RECORD` is set and the player selects Restart game
- **THEN** nothing restarts and the record file is not cut short

#### Scenario: Golden run
- **WHEN** a golden scenario runs with `RECOMP_MENU=0`
- **THEN** no System tab, dialog or `[RESET]` line exists, and the frames match the reference

### Requirement: A restart rebuilds the game in the same process and window
A restart SHALL stop every guest thread, pause the device threads, return every guest-derived piece of runtime state (guest memory, the XBE's sections, kernel objects and handles, timers, clocks, GPU state and guest-derived GPU caches, APU and DSP state, input state, FMV playback, the RAM cache) to its state at a cold start, and then run the title's entry point again. The window and its mode, the GPU device, the host audio device, the configuration and the menu SHALL stay open and unchanged. Settings the guest reads at boot SHALL take effect. No guest frame SHALL be presented between the stop and the new boot. The behaviour SHALL be the same on the D3D11 and Metal backends.

#### Scenario: Window kept
- **WHEN** the game runs fullscreen on the Deck and the player restarts it
- **THEN** the window stays fullscreen and focused, the boot sequence plays in it, and the process is the same one

#### Scenario: Boot-time setting
- **WHEN** the player sets `system.language` to French, saves, and restarts
- **THEN** the new boot runs in French without the player quitting the game

#### Scenario: Restart during a stock movie
- **WHEN** the player restarts while one of the title's movies plays (decoded by the title's own code on guest threads)
- **THEN** the movie stops as its guest threads unwind, its files are closed with the other handles, and the new boot plays the title's boot movies as at a cold start

#### Scenario: Restart during a host-decoded movie
- **WHEN** `RECOMP_FMV_HOST` is on (Windows) and the player restarts while the host player shows a movie
- **THEN** the host player stops and closes its own window and device before the rebuild, and the game's window is unchanged

#### Scenario: A lock held by a stopped thread
- **WHEN** a guest thread that exits at the restart still owns a guest mutant or critical section
- **THEN** that host lock is never destroyed or unlocked; it is left out of the kernel's tables, the log has `[RESET] abandoned <n> locks`, and the new boot creates its own objects

#### Scenario: Stuck reset
- **WHEN** a guest or device thread does not stop within its time
- **THEN** stderr has `[RESET] stuck at <step>:` with the thread named, and the game ends as a quit does, with the saves intact

### Requirement: A boot after a restart matches a cold boot
In the deterministic mode, a run that restarts once at a given flip through the DEBUG-tier test trigger SHALL produce, from the new boot's first flip, the same frames and the same audio as a cold run from its first flip, for the same pad input, on Metal and on D3D11. This gate SHALL only be relied on once two cold runs in the deterministic mode have been shown to give identical frames and audio. Fifty restarts in a row SHALL leave host handles, guest heap use, texture counts, GPU memory and process memory, less the memory of abandoned locks, within 2 % of their values after the first restart, and the number of locks abandoned per restart SHALL not grow.

#### Scenario: Equivalence
- **WHEN** the stage-1 scenario runs deterministically after a restart at flip 600, and again from a cold start
- **THEN** both runs give identical frames and audio hashes from their first boot flip to the scenario's end

#### Scenario: Soak
- **WHEN** the game is restarted 50 times at random flips
- **THEN** no restart gets stuck, the resource counts stay flat within 2 %, and the abandoned-lock count per restart does not grow

#### Scenario: A title run with the guest CPU lock off
- **WHEN** a game without the deterministic mode (Burnout 3, lock off) is restarted at a fixed flip
- **THEN** its golden after the restart passes within the golden's normal tolerance; frame equivalence is not required

### Requirement: Games declare their boot and their statics
A game's one-shot host setup that writes outside guest memory, such as BLiNX 2's save seed, SHALL stay in the host half and SHALL NOT run at a restart. A mod SHALL declare in its `needs` every guest hook, poke and state read it makes, and SHALL provide a reset callback if it wants the restart to stay available while it is enabled. A game SHALL get the restart by booting through the toolkit's boot loop, with its guest-side setup in the loop's game callback, and by registering one reset hook for its own state. A game MAY pass an automation reason and MAY turn the action off with a reason; when it is off, or the game does not boot through the loop, the Restart game row SHALL be greyed out with the reason. Quit game SHALL work for every game.

#### Scenario: A game not yet adopted
- **WHEN** a game that still calls its entry point itself opens the System tab
- **THEN** Restart game is greyed out with "this game does not support restart yet", and Quit game works
