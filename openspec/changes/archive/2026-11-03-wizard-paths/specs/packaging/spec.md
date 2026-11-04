## MODIFIED Requirements

### Requirement: The owner's HUD pack in the private bundle
`blinx2 package <target> --hud-pack [DIR]` SHALL copy `DIR/hud.pack` (default `dist/enhance/hud/hud.pack`, what `blinx2 enhance hud` writes) into the payload as `enhance/hud.pack`, append `[textures]` `pack = "enhance/hud.pack"` (on macOS `"../Resources/enhance/hud.pack"`, the path from `Contents/MacOS` to the payload) to the staged `config.default.toml`, and record `enhance.hud_pack` (`sha256`, `scale`, `entries`, and `made_with`: the scale, languages, `--only` list, font sha256, `[enhance.hud]` config digest and CLI version, with no paths) in `manifest.json`. Because the game reads `config.default.toml`, the key SHALL take effect on a first install and on an upgrade alike; a player turns the pack off with `pack = "none"` in `config.toml`. It SHALL refuse with the path when the pack is missing or not a valid pack.

`--keep-hud-pack` SHALL stage the base's pack, the bytes whose sha256 the base manifest records, taken from the pack store `.git/xbr/packs/<sha256>.pack`, else from `dist/enhance/hud/hud.pack` when its sha256 matches, else made again from `made_with` into a temporary folder and accepted only when its sha256 matches. It SHALL refuse, before the stage and naming `--hud-pack` and `--clear-hud-pack`, when none of these gives the same bytes, and SHALL be refused with `--full`. `--clear-hud-pack` SHALL stage no pack. `--hud-pack`, `--keep-hud-pack` and `--clear-hud-pack` SHALL be exclusive. When the run's base (from `--patch-from`, or without `--full` the host's install) records a HUD pack and none of the three is given, `package` SHALL refuse before building and name the three. Otherwise, without any of them, the payload SHALL hold no pack and `config.default.toml` no `[textures]` key.

Every staged pack SHALL be added to the pack store by sha256 (a hard link when on the same volume, else a clone or copy), and `enhance hud` SHALL write its pack to a temporary file and rename it, so a stored link never changes. The store SHALL keep the packs of the newest 3 bundle records per target and SHALL be counted by `xbr clean`. The pack is part of the owner's private bundle and falls under the same notice as the game files; the store stays in the build folder.

#### Scenario: Bundle with the pack
- **WHEN** `blinx2 package windows --hud-pack` runs with a pack of 41 entries in `dist/enhance/hud/`
- **THEN** the payload holds `enhance/hud.pack`, `config.default.toml` ends with the `[textures]` key, `manifest.json` records its sha256, 4, 41 and `made_with`, and the installed game's log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: ...)` whether or not a `config.toml` already existed

#### Scenario: Bundle without the flag
- **WHEN** `blinx2 package windows --full` runs with a pack present in `dist/enhance/hud/`
- **THEN** the payload has no `enhance/` directory and `config.default.toml` names no pack

#### Scenario: Missing pack
- **WHEN** `--hud-pack` is given and `dist/enhance/hud/hud.pack` does not exist
- **THEN** packaging refuses before building, names the path and the command that makes it

#### Scenario: Player turns the pack off
- **WHEN** the bundle's `config.default.toml` names the pack and the player's `config.toml` holds `[textures] pack = "none"`
- **THEN** the log reads `[ENHANCE] textures.pack=none` and the stock HUD is drawn

#### Scenario: A base with a pack needs a choice
- **WHEN** `package steamos --patch-from <record>` runs, the record's manifest has `enhance.hud_pack`, and no HUD flag is given
- **THEN** packaging refuses before any stage runs and names `--keep-hud-pack`, `--clear-hud-pack` and `--hud-pack`

#### Scenario: Keep after the dist pack was replaced
- **WHEN** `--keep-hud-pack` runs after a later `enhance hud` replaced `dist/enhance/hud/hud.pack` with other bytes
- **THEN** the base's pack is staged from the pack store, and the new manifest's `enhance.hud_pack.sha256` equals the base's

#### Scenario: Kept pack made again
- **WHEN** the pack store and `dist/` lack the base's pack, and the current `[enhance.hud]` digest and font match `made_with`
- **THEN** the pack is made again into a temporary folder and staged when its sha256 matches, else packaging refuses naming `--hud-pack` and `--clear-hud-pack`
