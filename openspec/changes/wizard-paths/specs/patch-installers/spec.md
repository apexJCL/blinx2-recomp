## MODIFIED Requirements

### Requirement: A patch is chosen from a usable base manifest
`xbr package` SHALL make a patch when a base `manifest.json` is usable (same app and target, equal `data_layout`, a sha256 for every path the patch keeps, and on Windows a versioned install with a `current.txt` and an equal `stub_abi`) and the patch is under half the full bundle's size, and the full installer otherwise. The base SHALL be the target's current version, taken from `--patch-from` (a manifest, a version folder, an app, a bundle tar, or a bundle record's sha256 prefix), else the current version installed on this host. `package --plan --json` SHALL list the bundle records the CLI keeps and the installed version as bases, each with its version, update ID, tweaks, patch size, and whether it is usable and why not, for the wizard to offer. A base named by `--patch-from` SHALL be strict: when it is not usable, the patch would not be under half the full bundle, or the build equals it, `package` SHALL refuse with the reason and write no bundle, and the plan SHALL report `output.kind = "none"` with that reason. Only the host-install base without `--patch-from` SHALL fall back to the full installer. `--full` SHALL always make the full installer. A schema 1 manifest SHALL be a usable base. The manifest SHALL record the game tree it was built from (`game_tree`: the XBE's sha256, the file count and a listing digest). A base whose game tree differs from the new build's SHALL be refused ("built from other game files") unless the run imported the game files with `--dump`, and a patch that removes game files SHALL be refused unless `--allow-game-file-deletes` is given, and always when the base records no `game_tree`. The plan SHALL give each reason a code (`why_codes`) and each base its counts of game files changed, new and deleted, and a refusal SHALL end with a `refused: CODE` line.

#### Scenario: No install found
- **WHEN** no base is found for the target and `--patch-from` is not given
- **THEN** the full installer is made, and the output reads "no install found"

#### Scenario: A bundle tar made outside the wizard is a base
- **WHEN** `--patch-from` names a steamos bundle tar made by an earlier CLI
- **THEN** its `manifest.json` is read from the tar without extracting it and used as the base

#### Scenario: A base built from other game files is refused
- **WHEN** `--patch-from` names a base whose `game_tree` differs from the new build's, and the run did not import with `--dump`
- **THEN** `package` refuses with "built from other game files" and the code `game_files`, and no bundle is written

#### Scenario: A patch that removes game files needs the flag
- **WHEN** the patch from a base would delete `game_files/` entries and `--allow-game-file-deletes` is not given
- **THEN** `package` refuses with the count and the code `game_deletes`, and the plan's base row reports the deleted count

#### Scenario: A patch that changes game files warns first
- **WHEN** a steamos or Windows patch made after a `--dump` import changes, adds or deletes a game file under an equal `data_layout`
- **THEN** the wizard and the applier warn that rolling back will not undo the game data change before applying

#### Scenario: macOS rollback restores game files
- **WHEN** a macOS patch that changed a game file is rolled back
- **THEN** the app's game files equal the base version's, and no game-data warning was shown before the apply

#### Scenario: An in-place Windows install gets the full installer
- **WHEN** the Windows install found has a root `manifest.json` and no `current.txt`, or a different `stub_abi`
- **THEN** no patch is made, and the full installer (which migrates) is offered

#### Scenario: A game data layout change refuses an explicit base
- **WHEN** `--patch-from` names a base whose `data_layout` differs from the new bundle's
- **THEN** `package` exits non-zero with the reason and "make the full bundle with --full", and no bundle is written

#### Scenario: An explicit base and a large patch
- **WHEN** `--patch-from` names a usable base and the patch would be 62% of the full bundle
- **THEN** `package` refuses with the share and no bundle is written

## ADDED Requirements

### Requirement: The appliers point out a config.toml that overrides the HUD pack
`install.sh` (full install and patch), the Windows `apply.exe` and the macOS `apply.command` SHALL look in the player's `config/config.toml` for a `pack` key under a `[textures]` header with a line scan, and when it is found and differs from the new `config.default.toml`'s, SHALL print one line naming the value and saying to remove it to use the build's HUD pack. The scan SHALL never change the file or the apply's result. `install.sh status` SHALL print `update id:` (the first 8 hex of the current version's manifest sha256) and `tweaks:` (the HUD pack's scale and entries, or none).

#### Scenario: Pack turned off by hand
- **WHEN** a steamos patch with a HUD pack is applied and `config.toml` holds `[textures]` then `pack = "none"`
- **THEN** after the apply, `install.sh` prints a note naming `textures.pack = "none"` and the patch is applied as usual

#### Scenario: Status shows the update ID
- **WHEN** the player runs `./install.sh status`
- **THEN** it prints the current version, `update id: ` with 8 hex, and `tweaks: ` with the HUD pack's scale and entries or `none`
