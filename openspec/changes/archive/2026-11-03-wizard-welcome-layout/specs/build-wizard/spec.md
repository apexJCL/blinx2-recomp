## ADDED Requirements

### Requirement: The credits open from the footer on every page
The build wizard SHALL show, centred in the footer between Back and Next on every page, an outline button reading "♥️ Open-source" (no fill, a red or pink outline that reads on light and dark themes) that opens the open-source credits as a modal dialog. The Welcome page SHALL NOT list the credits.

#### Scenario: Credits from any page
- **WHEN** the player taps the footer's credits button on any page
- **THEN** the "Open-source credits" dialog opens over the page, and closing it returns to that page

### Requirement: Welcome's statements show their lead, the rest as a tip
The Welcome page SHALL show its three statements (no game inside, downloads only what it needs, sends nothing) as one row of three columns, each with its own icon, its lead and an info glyph. Each statement's sentence SHALL open in a tip when the pointer is over it or when it is tapped, and a second tap SHALL close a tip a tap opened.

#### Scenario: A touch screen
- **WHEN** the player taps "Downloads only what it needs." on a Steam Deck
- **THEN** its sentence opens under it, and a second tap closes it

### Requirement: The path is chosen with two tiles
The Welcome page SHALL show Fresh build and Update build as two large tiles in one row, each an icon over its label, with exactly one chosen at a time and the chosen one highlighted. Under both, the wizard SHALL show the chosen path's sentence, or a hint to pick one before a choice. The choice SHALL drive the path, its saved setting and the Next button as before.

#### Scenario: Choosing Update
- **WHEN** the player taps the Update build tile
- **THEN** it is highlighted, Fresh is not, the line under them describes Update, and Next is enabled

### Requirement: Failures point at the log, not the error's own words
When the wizard has no plain words for an error, it SHALL say that something went wrong, SHALL name the log file that holds the error, and SHALL offer Copy error, Copy log path and Open the log folder. This SHALL apply to the Getting ready row on Checks, to any error box, and to the build failure page. The error's own words SHALL be written to the wizard's log and SHALL NOT be shown on the page. An error the wizard wrote for the player (a player error) SHALL be shown in its own words in the error box, with the same log path and buttons under it. The build failure page SHALL keep its "What the build said" excerpt.

#### Scenario: A developer build's error
- **WHEN** Prepare fails with "this developer build names no release tag to clone: run it with --game DIR"
- **THEN** the Getting ready row's details say "Something went wrong while getting ready.", show the path of `wizard.log` and the three buttons, Copy error puts that sentence on the clipboard, and `wizard.log` holds it

#### Scenario: A player error in the error box
- **WHEN** Install now finds no install.sh in the Steam Deck bundle
- **THEN** the error box says "The build has no install.sh, so the wizard cannot install it. Build it again, or install it by hand.", not "Something went wrong", and still shows the log path, Copy error, Copy log path and Open the log folder
