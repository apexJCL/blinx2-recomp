## MODIFIED Requirements

### Requirement: Game file location
The host SHALL load `<game_dir>/default.xbe` and use `<game_dir>` as the game data root. `<game_dir>` SHALL be the value of `RECOMP_GAME_FILES` when that is set, and otherwise `game_files/`, resolved relative to the current working directory. When `RECOMP_HDD_DIR` is set, the host SHALL pass it to the kernel as the save root (partition images, title and user data, caches). When it is unset, the host SHALL pass none, and the toolkit's default save root applies. `RECOMP_SAVE_DIR` SHALL keep overriding the UDATA/TDATA root within whichever save root is in force. With both keys unset, the boot output and every path used SHALL be identical to the behaviour before these keys existed. The host SHALL accept forward-slash paths on every host.

#### Scenario: Run from the project root
- **WHEN** the executable is launched with the project root as the working directory, `game_files/default.xbe` exists, and neither key is set
- **THEN** the XBE loads, the printed size equals the file's size in bytes, and no `[BOOT] game files:` line is printed

#### Scenario: Game files elsewhere
- **WHEN** `RECOMP_GAME_FILES=/data/BLiNX2/game_files` is set and the working directory is unrelated
- **THEN** the XBE loads from `/data/BLiNX2/game_files/default.xbe`, disc paths (`D:\`) resolve under that directory, and one `[BOOT] game files:` line names it

#### Scenario: Save root elsewhere
- **WHEN** `RECOMP_HDD_DIR=<dir>` is set
- **THEN** `Partition0.img`, `TitleData/`, `UserData/` and `Cache/` are created under `<dir>`, and the title's save games are written there, not under the toolkit's default save root

#### Scenario: Missing XBE with the key set
- **WHEN** `RECOMP_GAME_FILES` names a directory with no `default.xbe`
- **THEN** stderr names the full path tried and says it came from `RECOMP_GAME_FILES`, and the process exits non-zero before memory mapping
