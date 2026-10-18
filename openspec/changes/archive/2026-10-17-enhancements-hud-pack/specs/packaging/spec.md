## ADDED Requirements

### Requirement: The owner's HUD pack in the private bundle
`blinx2 package <target> --hud-pack [DIR]` SHALL copy `DIR/hud.pack` (default `dist/enhance/hud/hud.pack`, what `blinx2 enhance hud` writes) into the payload as `enhance/hud.pack`, append `[textures]` `pack = "enhance/hud.pack"` (on macOS `"../Resources/enhance/hud.pack"`, the path from `Contents/MacOS` to the payload) to the staged `enhance.toml.default`, and record `enhance.hud_pack` (`sha256`, `scale`, `entries`) in `manifest.json`. It SHALL refuse with the path when the pack is missing or not a valid pack. Without the flag the payload SHALL be what it is today and `enhance.toml.default` SHALL hold no `[textures]` key. The pack is part of the owner's private bundle and falls under the same notice as the game files.

#### Scenario: Bundle with the pack
- **WHEN** `blinx2 package windows --hud-pack` runs with a pack of 41 entries in `dist/enhance/hud/`
- **THEN** the payload holds `enhance/hud.pack`, `enhance.toml.default` ends with the `[textures]` key, `manifest.json` records its sha256, 4 and 41, and the installed game's log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries, scale 4)`

#### Scenario: Bundle without the flag
- **WHEN** `blinx2 package windows` runs with a pack present in `dist/enhance/hud/`
- **THEN** the payload has no `enhance/` directory and `enhance.toml.default` names no pack

#### Scenario: Missing pack
- **WHEN** `--hud-pack` is given and `dist/enhance/hud/hud.pack` does not exist
- **THEN** packaging refuses before building, names the path and the command that makes it

## MODIFIED Requirements

### Requirement: Bundles never enter the repository or the public export
`dist/`, `*.dmg`, `*.exe`, `*.pdb`, `*.tar`, `*.nsi`, `*.pack` and `enhance/` SHALL be gitignored. `scripts/export-public.sh` SHALL fail when the exported commit tracks any path under `dist/` or any file with those extensions. `blinx2 package` SHALL end its output with a notice that the bundle contains the user's own copy of the game and is not to be shared, and `README.txt` SHALL open with the same notice.

#### Scenario: Bundle staged for commit
- **WHEN** `git status` runs after `blinx2 package`
- **THEN** nothing under `dist/` is untracked or staged

#### Scenario: Export with a tracked installer
- **WHEN** a test commit tracks `dist/x.exe` and `export-public.sh` runs on it
- **THEN** the export fails naming the path and writes no repository

#### Scenario: Pack dropped in the tree
- **WHEN** a `hud.pack` is written anywhere under the checkout
- **THEN** `git status` shows it neither untracked nor staged
