## MODIFIED Requirements

### Requirement: Saves and settings survive every install, update, rollback and uninstall
On every target, the saves and the emulated hard disk SHALL live in a user-data directory outside the program files and outside any Wine prefix: `%LOCALAPPDATA%\BLiNX2\hdd\` on Windows, `<root>/hdd/` on steamos, `~/Library/Application Support/BLiNX2/hdd/` on macOS. No installer, update, rollback or uninstaller SHALL create, write, rename or delete anything under `hdd/`, `config/` or `logs/`, with two exceptions on steamos: `install` creates `config/` when it is absent (empty), and the `--import-saves` option writes `hdd/` only when it is absent or empty. Installing a bundle onto a target whose user data already exists SHALL leave that data byte-identical. The shipped defaults file `config.default.toml` SHALL live with the program files (installed, updated and uninstalled with them) and never under `config/`; what changes under `config/` at a **launch** is only the game's one-time rename of `enhance.toml` to `config.toml`, its creation of an absent `config.toml` as a comment header, the launcher's removal of the `config/enhance.toml.default` copy an earlier version made, and whatever the player or the in-game menu writes.

#### Scenario: Update keeps a save (steamos)
- **WHEN** `<root>/hdd/` holds a save and `config/config.toml` holds `render.scale = 2`, and a newer bundle's `install.sh` runs
- **THEN** every file under `hdd/`, `config/` and `logs/` is byte-identical afterwards, `current` points at the new version with its own `config.default.toml`, and the game loads the save at `render.scale = 2`

#### Scenario: Update keeps a save (Windows installer under Proton)
- **WHEN** a save exists under `%LOCALAPPDATA%\BLiNX2\hdd\` and a newer `setup.exe /S` runs in the same prefix
- **THEN** the save files are byte-identical, and the installed `cat_recomp.exe` and `config.default.toml` are the new ones

#### Scenario: Uninstall keeps saves
- **WHEN** `install.sh uninstall` runs, or `uninstall.exe /S` runs on Windows
- **THEN** the program files (`config.default.toml` among them) are gone, `hdd/`, `config/` and `logs/` are byte-identical, and the output names their path

#### Scenario: Replace the app (macOS)
- **WHEN** a newer `BLiNX2.app` replaces the installed one and is launched
- **THEN** `~/Library/Application Support/BLiNX2/` is byte-identical before the launch, and the game loads the existing save with the new app's `Contents/Resources/config.default.toml` under the player's `config/config.toml`

#### Scenario: Prefix recreated
- **WHEN** `<root>/prefix/` is deleted on steamos and the game is launched again
- **THEN** the prefix is recreated by Proton and the game loads the save from `<root>/hdd/`

#### Scenario: Rollback keeps saves
- **WHEN** `install.sh rollback` runs after an update
- **THEN** `hdd/`, `config/` and `logs/` are byte-identical, and the game reads the rolled-back version's `config.default.toml`
