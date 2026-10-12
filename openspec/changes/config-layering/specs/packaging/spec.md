## MODIFIED Requirements

### Requirement: Self-contained private bundle per target
`blinx2 package <windows|steamos|macos>` SHALL build the target's executable, stage one payload (the program, `game_files/` from the user's dump, `config.default.toml`, `launch.env.default`, `manifest.json`, `SHA256SUMS`, `README.txt`, `LICENSE`, `NOTICE`), and wrap it as:
- **windows:** `dist/BLiNX2-<version>-windows/` holding an NSIS installer `BLiNX2-<version>-setup.exe` and `game_files/` beside it;
- **steamos:** `dist/BLiNX2-<version>-steamos.tar` holding one folder with the payload plus `install.sh`, `install_lib.py` and `launch.sh`;
- **macos:** `dist/BLiNX2-<version>.dmg` holding `BLiNX2.app` (the game files and every non-system dylib inside it) and an `Applications` symlink.

`config.default.toml` is the game's `packaging/config.default.toml`, staged beside the executable on Windows and steamos and in `Contents/Resources/` on macOS; it is read by the game at every launch and never copied into the user's data. Packaging SHALL refuse before building, naming the rename, when the game's packaging content holds `enhance.toml.default` and no `config.default.toml`. The payload SHALL exclude `default_analysis.json`, `UDATA/` and `TDATA/` from `game_files/`. The script SHALL refuse when generated code is missing or being regenerated, when `game_files/default.xbe` is missing or its title ID is not `0x4D530065`, and when the build is not a stock Release build unless an override is given, which the manifest records. The macOS `cat_recomp` SHALL remain the unchanged console build, byte-identical to `build/cat_recomp` before relinking, and the app SHALL pass `codesign --verify --deep --strict`.

#### Scenario: steamos bundle contents
- **WHEN** `blinx2 package steamos` completes and the tar is unpacked
- **THEN** the folder holds exactly the payload files (`config.default.toml` at its top level), `install.sh`, `install_lib.py`, `launch.sh` and `running_game.py`; `sha256sum -c SHA256SUMS` passes inside it; and `game_files/default.xbe` is byte-identical to the repo's

#### Scenario: Windows bundle contents
- **WHEN** `blinx2 package windows` completes
- **THEN** the folder holds `BLiNX2-<version>-setup.exe` and `game_files/`, the exe is under 2 GB, and `strings` of it names `BLiNX2.exe`, `cat_recomp.exe`, `uninstall.exe` and `config.default.toml`

#### Scenario: macOS app is self-contained
- **WHEN** `blinx2 package macos` completes on a macOS host
- **THEN** `otool -L` of `cat_recomp` and of every dylib in `Contents/Frameworks/` lists no path outside `/usr/lib`, `/System` and `@rpath`, `codesign --verify --deep --strict` passes, `Contents/Resources/config.default.toml` exists, and the app launches from the mounted DMG with `RECOMP_WINDOW_QUIT_AFTER=10` logging that file on its `[ENHANCE] config:` line

#### Scenario: Wrong or missing dump
- **WHEN** `game_files/default.xbe` is missing, or its certificate names another title
- **THEN** packaging refuses before building and names the path

#### Scenario: Non-stock build
- **WHEN** the CMake cache has `XBOXRECOMP_ENHANCE=OFF`, a non-empty `CAT_GEN_OPT` or a non-Release build type, and no override is given
- **THEN** packaging refuses and names the setting

#### Scenario: Game not yet renamed
- **WHEN** the game's `packaging/` holds `enhance.toml.default` and no `config.default.toml`
- **THEN** packaging refuses before building with a message naming both file names

### Requirement: Launchers set the data location
Each target's launcher (`BLiNX2.exe` on Windows, `launch.sh` on steamos, `Contents/MacOS/BLiNX2` on macOS) SHALL point the game at user data outside the program files through `RECOMP_GAME_FILES`, `RECOMP_HDD_DIR`, `RECOMP_CONFIG` (`<data>/config/config.toml`, the `Z:` form on steamos) and `RECOMP_STDIO_LOG`, SHALL read `launch.env.default` and then the user's `config/launch.env` with the user's values winning, SHALL create `config/` when absent and copy no template into it, SHALL remove a `config/enhance.toml.default` an earlier version wrote, SHALL keep the newest `LOG_KEEP` logs, and SHALL start the game with the target's render backend (`d3d11` on Windows and under Proton, `metal` on macOS). The steamos launcher SHALL use `<root>/prefix` as its Wine prefix, pass paths in the `Z:` form, and refuse with a visible message when the game files or `umu-run` are missing. No launcher SHALL take or wait for any lock.

#### Scenario: Launch under Proton
- **WHEN** `<root>/BLiNX2` runs on the gaming PC after an install
- **THEN** the game starts through `umu-run` with `RECOMP_PB_BACKEND=d3d11`, `RECOMP_CONFIG=Z:<root>/config/config.toml` and `WINEPREFIX=<root>/prefix`, its log is under `<root>/logs/`, and `<root>/hdd/Partition0.img` exists afterwards

#### Scenario: User override survives an update
- **WHEN** the user's `config/launch.env` sets `RECOMP_PB_BACKEND=cpu` and a newer bundle is installed
- **THEN** the game starts with the CPU backend, and `config/launch.env` is byte-identical to before the install

#### Scenario: Existing config.toml is kept, new defaults apply
- **WHEN** `config/config.toml` holds `[render] scale = 2`, and a newer bundle whose `config.default.toml` turns `textures.pack` on is installed and launched
- **THEN** `config/config.toml` is byte-identical, no `.default` copy appears in `config/`, and the game runs at `render.scale = 2` with the pack loaded

#### Scenario: Existing enhance.toml is kept
- **WHEN** the data dir holds `config/enhance.toml` with `render.scale = 2` and `config/enhance.toml.default` from an earlier version, and the new bundle is installed and launched once
- **THEN** the launcher has removed `config/enhance.toml.default`, the game has renamed `enhance.toml` to `config.toml` with the same bytes and the one log line, the game runs at `render.scale = 2`, and `hdd/` and `config/launch.env` are byte-identical

### Requirement: The owner's HUD pack in the private bundle
`blinx2 package <target> --hud-pack [DIR]` SHALL copy `DIR/hud.pack` (default `dist/enhance/hud/hud.pack`, what `blinx2 enhance hud` writes) into the payload as `enhance/hud.pack`, append `[textures]` `pack = "enhance/hud.pack"` (on macOS `"../Resources/enhance/hud.pack"`, the path from `Contents/MacOS` to the payload) to the staged `config.default.toml`, and record `enhance.hud_pack` (`sha256`, `scale`, `entries`) in `manifest.json`. Because the game reads `config.default.toml`, the key SHALL take effect on a first install and on an upgrade alike; a player turns the pack off with `pack = "none"` in `config.toml`. It SHALL refuse with the path when the pack is missing or not a valid pack. Without the flag the payload SHALL be what it is today and `config.default.toml` SHALL hold no `[textures]` key. The pack is part of the owner's private bundle and falls under the same notice as the game files.

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
