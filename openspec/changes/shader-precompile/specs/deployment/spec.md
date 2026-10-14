## MODIFIED Requirements

### Requirement: Saves and settings survive every install, update, rollback and uninstall
On every target, the saves and the emulated hard disk SHALL live in a user-data directory outside the program files and outside any Wine prefix: `%LOCALAPPDATA%\BLiNX2\hdd\` on Windows, `<root>/hdd/` on steamos, `~/Library/Application Support/BLiNX2/hdd/` on macOS. No installer, update, rollback or uninstaller SHALL create, write, rename or delete anything under `hdd/`, `config/` or `logs/`, with two exceptions on steamos: `install` creates `config/` when it is absent (empty), and the `--import-saves` option writes `hdd/` only when it is absent or empty. Installing a bundle onto a target whose user data already exists SHALL leave that data byte-identical. The same root holds `cache/` (the shader index under `cache/shaders/`), which the game creates and fills itself: no installer, update, rollback or uninstaller SHALL read or write it, the player MAY delete it at any time, and it is not part of the byte-identical promise, since the game rewrites it as it runs.

#### Scenario: Update keeps a save (steamos)
- **WHEN** `<root>/hdd/` holds a save and `config/enhance.toml` holds `render.scale = 2`, and a newer bundle's `install.sh` runs
- **THEN** every file under `hdd/`, `config/` and `logs/` is byte-identical afterwards, `current` points at the new version, and the game loads the save

#### Scenario: Update keeps a save (Windows installer under Proton)
- **WHEN** a save exists under `%LOCALAPPDATA%\BLiNX2\hdd\` and a newer `setup.exe /S` runs in the same prefix
- **THEN** the save files are byte-identical, and the installed `cat_recomp.exe` is the new one

#### Scenario: Uninstall keeps saves
- **WHEN** `install.sh uninstall` runs, or `uninstall.exe /S` runs on Windows
- **THEN** the program files are gone, `hdd/`, `config/` and `logs/` are byte-identical, and the output names their path

#### Scenario: Replace the app (macOS)
- **WHEN** a newer `BLiNX2.app` replaces the installed one and is launched
- **THEN** `~/Library/Application Support/BLiNX2/` is byte-identical before the launch, and the game loads the existing save

#### Scenario: Prefix recreated
- **WHEN** `<root>/prefix/` is deleted on steamos and the game is launched again
- **THEN** the prefix is recreated by Proton and the game loads the save from `<root>/hdd/`

#### Scenario: Rollback keeps saves
- **WHEN** `install.sh rollback` runs after an update
- **THEN** `hdd/`, `config/` and `logs/` are byte-identical

#### Scenario: Installers leave the cache alone
- **WHEN** `<root>/cache/shaders/` holds an index and a newer bundle's `install.sh` runs, then `install.sh uninstall`
- **THEN** neither command reads or writes under `cache/`, and the uninstall output names it beside `hdd/`, `config/` and `logs/` as what it kept

### Requirement: The user-data root can be redirected
The macOS and Windows launchers SHALL take their user-data root from `BLINX2_DATA_DIR` when it is set and non-empty, instead of `~/Library/Application Support/BLiNX2` or `%LOCALAPPDATA%\BLiNX2`. Every path they derive from that root (`hdd/`, `config/`, `logs/`, `cache/`) SHALL follow it. The variable SHALL be documented as a launcher variable. The launchers SHALL set `RECOMP_SHADER_CACHE` to `<root>/cache/shaders` and, when the bundle carries a shader record list, `RECOMP_SHADER_PRELOAD` to its path, each **only when the variable is not defined at all** after `launch.env.default` and the player's `config/launch.env` have loaded (`[ -n "${RECOMP_SHADER_CACHE+x}" ] || export ...` in the shell launchers; `GetEnvironmentVariableW` returning 0 with `ERROR_ENVVAR_NOT_FOUND` in the Windows launcher), so a player's `launch.env` line wins, and the empty value `RECOMP_SHADER_CACHE=` turns the cache off (the runtime treats an empty value of either key as unset).

#### Scenario: Override set
- **WHEN** the macOS launcher runs with `BLINX2_DATA_DIR=/scratch/d`
- **THEN** `RECOMP_HDD_DIR`, `RECOMP_ENHANCE_CONFIG`, `RECOMP_STDIO_LOG` and `RECOMP_SHADER_CACHE` are all under `/scratch/d`, and nothing under the real Application Support folder is created or changed

#### Scenario: Player turns the cache off
- **WHEN** `config/launch.env` holds `RECOMP_SHADER_CACHE=`
- **THEN** the launcher leaves the variable empty, the game logs no `[SHADER] cache:` line, creates no `cache/` directory and compiles on demand as before the change

#### Scenario: Player points the cache elsewhere
- **WHEN** `config/launch.env` holds `RECOMP_SHADER_CACHE=/tmp/x` on steamos
- **THEN** the launcher does not replace it and the game writes its index under `/tmp/x`
