# deployment Specification

## Purpose
Defines what each installer does on its target (Windows, steamos, macOS): where the program and the user's data live, how a version is installed, updated, rolled back and removed without touching saves or settings, and how tests stay away from the player's real data.

## Requirements

### Requirement: Saves and settings survive every install, update, rollback and uninstall
On every target, the saves and the emulated hard disk SHALL live in a user-data directory outside the program files and outside any Wine prefix: `%LOCALAPPDATA%\BLiNX2\hdd\` on Windows, `<root>/hdd/` on steamos, `~/Library/Application Support/BLiNX2/hdd/` on macOS. No installer, update, rollback or uninstaller SHALL create, write, rename or delete anything under `hdd/`, `config/` or `logs/`, with one exception: the steamos `--import-saves` option, which writes `hdd/` only when it is absent or empty. Installing a bundle onto a target whose user data already exists SHALL leave that data byte-identical.

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

### Requirement: steamos versioned install with an atomic switch
`install.sh` (default command `install`) SHALL verify the bundle's `SHA256SUMS`, transfer the program files to `<root>/versions/<version>.partial/`, rename it to `<root>/versions/<version>/`, sync `game_files/` into `<root>/game_files/`, refresh the `.default` config files, and then point `<root>/current` at the new version with a single atomic rename of a relative symlink, appending to `<root>/state/history`. A failed verify or transfer SHALL remove the `.partial` directory and leave `current` unchanged. It SHALL keep the newest `--keep` versions (default 3) plus the current and previous ones, removing only directories under `versions/` whose `manifest.json` names this product. `rollback [version]` SHALL switch `current` back by the same rename. `status`, `list` and `uninstall` SHALL behave as the design describes; `uninstall` SHALL have no option that removes saves.

#### Scenario: First install
- **WHEN** `./install.sh` runs from a bundle on a host without `<root>`
- **THEN** `<root>/current` resolves to `versions/<version>`, `<root>/game_files/default.xbe` matches the bundle's, `<root>/BLiNX2` is an executable regular file, `hdd/` does not exist yet, and the output ends with the save path and the notice

#### Scenario: Corrupt bundle
- **WHEN** a payload file's checksum does not match
- **THEN** nothing is transferred, `current` is unchanged if present, and the command exits non-zero naming the file

#### Scenario: Same version again
- **WHEN** the bundle's version is already installed with identical checksums
- **THEN** no program files are transferred, and `current` is switched to it only if it is not current

#### Scenario: Prune keeps the rollback target
- **WHEN** a fourth version is installed with `--keep 3`
- **THEN** the oldest version is removed, and the current and previous versions remain

#### Scenario: Foreign directory
- **WHEN** `versions/` holds a directory without this product's manifest
- **THEN** prune leaves it and reports it

#### Scenario: Wrong host
- **WHEN** `install.sh` runs on a host that is not Linux x86-64 or has no `umu-run`
- **THEN** it refuses before writing anything

### Requirement: Steam entry from Desktop Mode
With `--steam`, `install.sh` SHALL add `<root>/BLiNX2` to Steam through `steamos-add-to-steam`, which hands the path to the running client; the scripts SHALL NOT edit `shortcuts.vdf`. When no desktop session or no running Steam is detected, or the helper is missing, the install SHALL complete without the entry and print how to add it: from Desktop Mode with Steam open, or by hand. The registered path SHALL be the stable launcher at the install root, never a path under `versions/`.

#### Scenario: Shortcut added
- **WHEN** `./install.sh --steam` runs in Desktop Mode with Steam open
- **THEN** a non-Steam shortcut to `<root>/BLiNX2` appears in the library, and it still launches after later installs and prunes

#### Scenario: Run from Game Mode or a tty
- **WHEN** `./install.sh --steam` runs without `DISPLAY` and `WAYLAND_DISPLAY`
- **THEN** the install completes and the output says to run it again from Desktop Mode, or lists the manual steps

### Requirement: Windows installer
The Windows bundle's `setup.exe` SHALL install per user without elevation, defaulting to `%LOCALAPPDATA%\Programs\BLiNX2\`, copy `game_files\` from the folder it runs in and refuse when that folder has no `game_files\default.xbe`, create a Start Menu shortcut to `BLiNX2.exe`, register an uninstaller under `HKCU`, support `/S` for silent install and uninstall, and overwrite an older install in place. The uninstaller SHALL delete only the files the installer wrote.

#### Scenario: Silent install under Proton
- **WHEN** `setup.exe /S` runs under Proton in a scratch prefix with `game_files/` beside it
- **THEN** `drive_c/users/steamuser/AppData/Local/Programs/BLiNX2/` holds `cat_recomp.exe`, `BLiNX2.exe`, `game_files/default.xbe` and `uninstall.exe`, and launching `BLiNX2.exe` reaches the title screen with D3D11 and writes `AppData/Local/BLiNX2/logs/game-*.log` and `AppData/Local/BLiNX2/hdd/Partition0.img`

#### Scenario: Missing game files beside the installer
- **WHEN** `setup.exe` runs from a folder without `game_files\default.xbe`
- **THEN** it refuses with a message and installs nothing

### Requirement: Isolation from development trees
`install.sh` SHALL refuse an install root that equals or lies inside the bench tree (`BENCH_DIR`, default `~/xbox-recomp`) or that contains a git checkout, comparing realpaths. It SHALL NOT take or wait for the bench run lock, and SHALL NOT read or write the bench's prefix, toolchain or game files.

#### Scenario: Install during a bench run
- **WHEN** a bench run holds `~/.recomp-run.lock` and `install.sh` runs into `~/Games/BLiNX2`
- **THEN** the install completes without waiting, and the bench run's files and lock are untouched

#### Scenario: Install root inside the bench tree
- **WHEN** `--root` resolves to a path under `BENCH_DIR`
- **THEN** `install.sh` refuses and names both paths

### Requirement: The user-data root can be redirected
The macOS and Windows launchers SHALL take their user-data root from `BLINX2_DATA_DIR` when it is set and non-empty, instead of `~/Library/Application Support/BLiNX2` or `%LOCALAPPDATA%\BLiNX2`. Every path they derive from that root (`hdd/`, `config/`, `logs/`) SHALL follow it. The variable SHALL be documented as a launcher variable.

#### Scenario: Override set
- **WHEN** the macOS launcher runs with `BLINX2_DATA_DIR=/scratch/d`
- **THEN** `RECOMP_HDD_DIR`, `RECOMP_ENHANCE_CONFIG` and `RECOMP_STDIO_LOG` are all under `/scratch/d`, and nothing under the real Application Support folder is created or changed

### Requirement: Tests never touch the player's real data
Every automated test and gate that starts a packaged launcher SHALL point it at a scratch data root: `BLINX2_DATA_DIR` on macOS and Windows (plus a scratch `HOME` on macOS), or a scratch install root on steamos. It SHALL put any test-only settings (such as `SDL_AUDIODRIVER=dummy` or `RECOMP_WINDOW_QUIT_AFTER`) only in that scratch root's `config/launch.env`.

#### Scenario: Smoke test of the DMG
- **WHEN** the Mac gate launches the packaged app to check its icon
- **THEN** the user's real `config/launch.env` is byte-identical before and after

### Requirement: Packaged games accept a controller by default
The packaged macOS app's default settings SHALL set `RECOMP_HOST_PAD=1`. The Windows and steamos bundles SHALL keep host pads on through the runtime's Windows default. The windows and steamos bundles SHALL also enable the keyboard as a port-0 fallback (`RECOMP_KEYBOARD=1`) that merges with a real pad and never masks it. The runtime's own default for an unset `RECOMP_HOST_PAD` SHALL NOT change.

#### Scenario: Controller on the Mac
- **WHEN** the packaged macOS app starts with a controller connected and no user override
- **THEN** the game log shows `host=on` and the controller drives the game

#### Scenario: Golden runs unaffected
- **WHEN** a golden or bench run starts `cat_recomp` directly, with an input script and no `RECOMP_HOST_PAD`
- **THEN** host devices stay off: the packaged defaults apply only to the launchers
