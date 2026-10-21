## ADDED Requirements

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
