## MODIFIED Requirements

### Requirement: Help shows player commands first
`blinx2 --help` SHALL list the player commands first: the path form (`blinx2 /path/to/dump`, the disc image or folder), no arguments, `package`, `doctor`, `import`, `assets hud-pack` and `setup`. It SHALL list the pipeline stages, `build`, `pins`, `new` and `bench` under a separate "Developer commands" heading, with `bench` as one line that points at `blinx2 bench --help`. Every developer command SHALL keep its current behaviour. The help SHALL print the same bytes with or without uv on the host.

#### Scenario: Help
- **WHEN** a user runs `./blinx2 --help`
- **THEN** the first command line shows the path form with the disc image, `import` is among the player commands, and `analyze`, `recomp`, `build` and `bench` appear only under "Developer commands"

#### Scenario: Bench help
- **WHEN** a developer runs `./blinx2 bench --help`
- **THEN** it lists the bench commands, their options, the `BENCH_*` configuration table, the host layout and the rule that the command takes the run lock itself and is never wrapped in an outer `flock`

### Requirement: The owner's HUD pack in the private bundle
`blinx2 package <target> --hud-pack [DIR]` SHALL copy `DIR/hud.pack` (default `dist/enhance/hud/hud.pack`, what `blinx2 assets hud-pack` writes) into the payload as `enhance/hud.pack`, append `[textures]` `pack = "enhance/hud.pack"` (on macOS `"../Resources/enhance/hud.pack"`, the path from `Contents/MacOS` to the payload) to the staged `config.default.toml`, and record `enhance.hud_pack` (`sha256`, `scale`, `entries`) in `manifest.json`. Because the game reads `config.default.toml`, the key SHALL take effect on a first install and on an upgrade alike; a player turns the pack off with `pack = "none"` in `config.toml`. It SHALL refuse with the path when the pack is missing or not a valid pack. Without the flag the payload SHALL be what it is today and `config.default.toml` SHALL hold no `[textures]` key. The pack is part of the owner's private bundle and falls under the same notice as the game files.

#### Scenario: Bundle with the pack
- **WHEN** `blinx2 package windows --hud-pack` runs with a pack of 41 entries in `dist/enhance/hud/`
- **THEN** the payload holds `enhance/hud.pack`, `config.default.toml` ends with the `[textures]` key, `manifest.json` records its sha256, 4 and 41, and the installed game's log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: ...)` whether or not a `config.toml` already existed

#### Scenario: Bundle without the flag
- **WHEN** `blinx2 package windows` runs with a pack present in `dist/enhance/hud/`
- **THEN** the payload has no `enhance/` directory and `config.default.toml` names no pack

#### Scenario: Missing pack
- **WHEN** `--hud-pack` is given and `dist/enhance/hud/hud.pack` does not exist
- **THEN** packaging refuses before building, names the path and the command that makes it

#### Scenario: Player turns the pack off
- **WHEN** the bundle's `config.default.toml` names the pack and the player's `config.toml` holds `[textures] pack = "none"`
- **THEN** the log reads `[ENHANCE] textures.pack=none` and the stock HUD is drawn
