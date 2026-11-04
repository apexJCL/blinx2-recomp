## MODIFIED Requirements

### Requirement: steamos versioned install with an atomic switch
`install.sh` (default command `install`) SHALL verify the bundle's `SHA256SUMS`, transfer the program files to `<root>/versions/<version>.partial/`, flush them and the directory, rename it to `<root>/versions/<version>/`, sync `game_files/` into `<root>/game_files/`, refresh the `.default` config files, and then point `<root>/current` at the new version with a single atomic rename of a relative symlink, flushing the root before and after it, and appending to `<root>/state/history`. A failed verify or transfer SHALL remove the `.partial` directory and leave `current` unchanged. A `versions/<version>/` that is already complete SHALL be reused, so a rerun after a crash between the rename and the switch completes the install. Reinstalling the current version SHALL exchange the new tree and the old one in one `renameat2(RENAME_EXCHANGE)` where the filesystem has it, so `current` never resolves to a missing directory. Both `install` and `patch` SHALL refuse while the game holds `launch.lock`. When the folder it runs from holds a `patch.json`, or when run as `install.sh patch`, it SHALL apply the patch instead: the same checks and post-install steps as `install`, with the program step built from hard links to the current version's kept files plus the patch's files, and the game-file step done by the patch-aware sync; it SHALL refuse unless `current` is the patch's base version with the base manifest's sha256. It SHALL keep the newest `--keep` versions (default 3) plus the current and previous ones, removing only directories under `versions/` whose `manifest.json` names this product. `rollback [version]` SHALL switch `current` back by the same rename. `status`, `list` and `uninstall` SHALL behave as the design describes; `uninstall` SHALL have no option that removes saves.

#### Scenario: First install
- **WHEN** `./install.sh` runs from a bundle on a host without `<root>`
- **THEN** `<root>/current` resolves to `versions/<version>`, `<root>/game_files/default.xbe` matches the bundle's, `<root>/BLiNX2` is an executable regular file, `hdd/` does not exist yet, and the output ends with the save path and the notice

#### Scenario: Corrupt bundle
- **WHEN** a payload file's checksum does not match
- **THEN** nothing is transferred, `current` is unchanged if present, and the command exits non-zero naming the file

#### Scenario: Same version again
- **WHEN** the bundle's version is already installed with identical checksums
- **THEN** no program files are transferred, and `current` is switched to it only if it is not current

#### Scenario: Patch over the current version
- **WHEN** `./install.sh` runs from a patch whose base is the current version
- **THEN** `versions/<new>` is complete and `current` resolves to it, unchanged files are hard links into the base version, and the result equals a full install of the new version

#### Scenario: Patch over the wrong version
- **WHEN** `./install.sh` runs from a patch whose base is not the current version
- **THEN** it exits non-zero naming both versions, and nothing under `<root>` changes

#### Scenario: Power loss during an install
- **WHEN** the host loses power during `install` or `patch`, including a reinstall of the current version and the moment between the rename of `versions/<version>` and the switch
- **THEN** after the restart `current` resolves to a complete version that launches, and rerunning the same command reuses any complete `versions/<version>` and completes the install

#### Scenario: Install while the game runs
- **WHEN** `install.sh` or `install.sh patch` runs while the game holds `launch.lock`
- **THEN** it refuses before writing anything

#### Scenario: Prune keeps the rollback target
- **WHEN** a fourth version is installed with `--keep 3`
- **THEN** the oldest version is removed, and the current and previous versions remain

#### Scenario: Foreign directory
- **WHEN** `versions/` holds a directory without this product's manifest
- **THEN** prune leaves it and reports it

#### Scenario: Wrong host
- **WHEN** `install.sh` runs on a host that is not Linux x86-64
- **THEN** it refuses before writing anything

#### Scenario: No umu-run (a stock Steam Deck)
- **WHEN** `install.sh` finds no `umu-run` on PATH, in `~/.local/bin` or in the copy it fetched before
- **THEN** it offers to download the umu-launcher release the CLI pins (asked y/N, or `--fetch-umu`), installs it only if its sha256 matches the pin, and otherwise refuses before writing anything, naming `--fetch-umu`

### Requirement: Windows installer
The Windows bundle's `setup.exe` SHALL install per user without elevation, defaulting to `%LOCALAPPDATA%\Programs\BLiNX2\`, in a versioned layout: the program files in `versions\<version>\`, a `current.txt` naming the current version and replaced atomically, the unversioned `game_files\` at the root, a stable root launcher that starts the current version's launcher, and at the root the applier `apply.exe` and `state\history.txt`; the root launcher and `apply.exe` SHALL be recorded in the manifest outside `files[]`. The installer SHALL do every hard link, flush and `current.txt` change through its embedded `apply.exe` (`migrate`, `switch`), since NSIS has none of those calls. It SHALL copy `game_files\` from the folder it runs in and refuse when that folder has no `game_files\default.xbe`, create a Start Menu shortcut to the root `BLiNX2.exe`, register an uninstaller under `HKCU`, and support `/S` for silent install and uninstall. Over an older in-place install it SHALL migrate once, moving the old program files into `versions\<old version>\` with a directory junction `versions\<old version>\game_files` to the root `game_files\` (the old launcher needs `game_files` beside its exe), in an order that leaves a working install at every step. A patch SHALL be applied by the bundle's `apply.exe` into a new version folder with the same base check, flush and switch, and `apply.exe rollback` SHALL switch back. Neither SHALL run while the game runs. The uninstaller SHALL delete only the files and folders the installer and `apply.exe` wrote (`versions\`, `current.txt`, the root launcher, `apply.exe`, `state\`, `game_files\`), SHALL remove a junction without following it, and SHALL leave the data folder.

#### Scenario: Silent install under Proton
- **WHEN** `setup.exe /S` runs under Proton in a scratch prefix with `game_files/` beside it
- **THEN** the prefix's `%LOCALAPPDATA%\Programs\BLiNX2\` holds `current.txt`, `versions/<version>/cat_recomp.exe`, `BLiNX2.exe`, `apply.exe`, `state/history.txt`, `game_files/default.xbe` and `uninstall.exe`, and launching `BLiNX2.exe` reaches the title screen with D3D11 and writes `AppData/Local/BLiNX2/logs/game-*.log` and `AppData/Local/BLiNX2/hdd/Partition0.img`

#### Scenario: Missing game files beside the installer
- **WHEN** `setup.exe` runs from a folder without `game_files\default.xbe`
- **THEN** it refuses with a message and installs nothing

#### Scenario: Migration from an in-place install
- **WHEN** `setup.exe` runs over an install made by an older in-place installer
- **THEN** the old version is under `versions\` with its `game_files` junction, the new one is current, the game starts, and the root `apply.exe rollback` returns to the old version, which also starts

#### Scenario: Power loss during a Windows apply
- **WHEN** the PC loses power during `apply.exe`
- **THEN** after the restart `current.txt` names a complete version that starts, and rerunning `apply.exe` completes the apply
