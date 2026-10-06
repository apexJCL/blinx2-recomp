## ADDED Requirements

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
- **THEN** host devices stay off, as before this change
