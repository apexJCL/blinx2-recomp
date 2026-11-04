# build-wizard Specification

## Purpose
TBD - created by archiving change wizard-multi-platform. Update Purpose after archive.

## Requirements

### Requirement: A fresh build can make several platforms in one run
On the Fresh path the Platform page SHALL offer each buildable platform as a checkbox, with this computer's platform ticked first, and SHALL keep at least one ticked. The wizard SHALL run the prerequisite commands once, then `package` once per ticked platform, and SHALL pass `--clean` to one run a session: the first, or the next one when the first stopped before the CLI cleaned. A Retry after the clean SHALL NOT clean again. With several platforms ticked, the Summary SHALL sum the plans' disk needs per volume and warn when the sum is more than is free. Blocked platforms SHALL stay unavailable with their reason. The ticked platforms SHALL be saved in the settings, and a settings file holding a single platform string SHALL be read as that one platform.

#### Scenario: Windows and the Steam Deck
- **WHEN** the player ticks Windows and Steam Deck or Linux and builds
- **THEN** the wizard runs `package windows` then `package steamos`, the Building page heads each one's parts with its name, and Done shows both bundles

### Requirement: An update is for one platform
On the Update path the Platform page SHALL offer a single choice and SHALL say that an update is for one computer at a time.

#### Scenario: Update after a two-platform fresh build
- **WHEN** the saved settings tick two platforms and the player picks Update
- **THEN** the Platform page shows one choice and the build runs one `package` with its `--patch-from`

### Requirement: One platform's own failure does not stop the others
When a platform's `package` run fails in its package stage, the wizard SHALL go on to the next platform. When it fails in its build stage, the wizard SHALL list the later platforms on the same compile tree as not built and SHALL go on to the others. When a prerequisite fails, or a `package` run fails before any stage, in shared work (import, setup or generate) or for disk space, the wizard SHALL stop and list the remaining platforms as not built. Done SHALL list each platform's end and, for each one made, its bundle and install step.

#### Scenario: The Steam Deck build fails to compile
- **WHEN** Windows, Steam Deck or Linux and macOS are ticked and the Steam Deck's run fails in build
- **THEN** macOS is still built, and Done says Windows and macOS are ready and the Steam Deck stopped at build, with the failure's log and buttons

#### Scenario: Generate fails on the first platform
- **WHEN** the first platform's run fails in generate
- **THEN** no other platform runs, and Done lists them as not built

#### Scenario: Windows fails to compile
- **WHEN** Windows, Steam Deck or Linux and macOS are ticked and the Windows run fails in build
- **THEN** the Steam Deck is listed as not built, macOS is still built, and Done's log folder is the Windows run's

#### Scenario: Short of disk space
- **WHEN** the first platform's run refuses for disk space
- **THEN** no other platform runs, and Done lists them as not built

#### Scenario: Retry after a clean rebuild
- **WHEN** the player ticked Rebuild everything, the first platform's run cleaned and a later one failed, and the player presses Retry
- **THEN** no run of the Retry passes `--clean`

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

### Requirement: The wizard has a Fresh path and an Update path
The build wizard SHALL ask on its Welcome page for **Fresh build** or **Update build**, and SHALL show only that path's pages after Checks. Fresh SHALL always be allowed, SHALL pass `--full` to `package`, and SHALL keep the disc, platform, options (with the seed) and summary pages. Update SHALL pass `--patch-from` with a base the player chose, and SHALL make a patch or say why it cannot. The Summary SHALL have no separate output choice, since the path is that choice. "Rebuild everything" (`--clean`) SHALL stay on both paths. The wizard SHALL remember the last path used.

#### Scenario: Fresh with an existing build
- **WHEN** this folder already made a build for the target and the player picks Fresh
- **THEN** the wizard runs `package <target> --full`, reusing the build folder's current stages, and makes the full installer

#### Scenario: Update pages
- **WHEN** the player picks Update and the game files in the build folder are current
- **THEN** the pages are Checks, Target, Base, Changes, Summary, Build and Done, with no disc page and no config values form

### Requirement: Update shows its base and the player chooses it
The Update path SHALL list as candidate bases the install on this computer (when the target is this computer's platform), the bundle records this folder made for the target, newest first, and a `manifest.json` file the player copied from the device, with the file's location named per target. Each row SHALL show the version, when it was made, its update ID (the first 8 hex of its manifest's sha256), its tweaks and the update's size, from `package --plan --json`. A row that cannot take a patch SHALL be shown with its reason and SHALL NOT be selectable. For another device the wizard SHALL NOT preselect a row when there is more than one record. `install.sh status` SHALL print the current version's update ID, so the player can match a row.

#### Scenario: Building on the Mac for the Deck
- **WHEN** the player picks Update and steamos, and this folder has two steamos records
- **THEN** both are listed with their version, update ID and tweaks, neither is preselected, and the Build button stays off until one row or a file is chosen

#### Scenario: A file from the device
- **WHEN** the player picks a `manifest.json` copied from the device's `current/`
- **THEN** the wizard passes `--patch-from <that file>` and the summary names that version as the base

### Requirement: Update keeps the base's tweaks unless the player changes them
On Update, the Changes page SHALL show the base's tweaks. An unticked tweak SHALL keep the base's (`--keep-hud-pack` when the base has a HUD pack), a ticked tweak SHALL make a new one (`--hud-pack` after `enhance hud`), and **Clear previous tweaks** SHALL remove them (`--clear-hud-pack`, and every other `--clear-*` flag) and disable the tweak boxes. The wizard SHALL never remove a tweak because a box was left unticked. When the base's pack cannot be found or made again the same, the Changes page SHALL say so and offer ticking the tweak or clearing it.

#### Scenario: Unrelated update keeps the sharper HUD
- **WHEN** the base has a 4x HUD pack and the player updates with the HUD box unticked
- **THEN** the wizard passes `--keep-hud-pack`, runs no `enhance hud`, and the new version on the device still loads the same pack

#### Scenario: Clear previous tweaks
- **WHEN** the player ticks Clear previous tweaks
- **THEN** the HUD box is unticked and disabled, the wizard passes `--clear-hud-pack`, and the summary reads "Removes: Sharper HUD"

### Requirement: Update asks for the disc only when needed
On Update, the wizard SHALL ask `package --plan --json` whether the import is needed, and SHALL show the disc page, pass `--dump` and run `import DUMP` only when the plan says so, naming why. It SHALL run `enhance hud` only when a new HUD pack is made.

#### Scenario: Game files current
- **WHEN** the build folder's game files match their import record and the HUD box is unticked
- **THEN** no disc is asked for and neither `import` nor `enhance hud` runs

#### Scenario: Game files removed
- **WHEN** `game_files/` is missing from the build folder
- **THEN** the disc page is shown with "The game files in the build folder are missing", and the run imports before packaging

### Requirement: Update never falls back to a full build silently
When the chosen base cannot take a patch, the patch would not be under half the full bundle, or nothing changed, the Update path SHALL show the reason and a **Make a Fresh build instead** button in place of Build, which switches to Fresh keeping the target, folders and disc. The same SHALL apply when the run itself refuses. Update SHALL make a full bundle only after that button.

#### Scenario: Data layout changed
- **WHEN** the plan reports `output.kind = "none"` because the base's `data_layout` differs
- **THEN** the Summary reads "The game data layout changed since that build, so it can't be updated." and offers Make a Fresh build instead

### Requirement: The wizard warns about a config.toml that overrides the pack
When a HUD pack is made or kept, the wizard SHALL say that a `[textures] pack` line in the player's `config.toml` overrides it. On this computer's own target it SHALL name the line found by the plan's `config_overrides`. The Update path SHALL say that render scale, fullscreen and other settings stay in the device's `config.toml` and an update never changes them.

#### Scenario: Override on this computer
- **WHEN** the target is this computer's platform and its `config.toml` holds `[textures] pack = "none"`
- **THEN** the Changes and Done pages name that line and say to remove it to use the sharper HUD
