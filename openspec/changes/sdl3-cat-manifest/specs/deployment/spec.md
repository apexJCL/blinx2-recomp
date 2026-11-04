## MODIFIED Requirements

### Requirement: Tests never touch the player's real data
Every automated test and gate that starts a packaged launcher SHALL point it at a scratch data root: `BLINX2_DATA_DIR` on macOS and Windows (plus a scratch `HOME` on macOS), or a scratch install root on steamos. It SHALL put any test-only settings (such as `SDL_AUDIO_DRIVER=dummy` or `RECOMP_WINDOW_QUIT_AFTER`) only in that scratch root's `config/launch.env`.

#### Scenario: Smoke test of the DMG
- **WHEN** the Mac gate launches the packaged app to check its icon
- **THEN** the user's real `config/launch.env` is byte-identical before and after

#### Scenario: Launcher test uses the SDL3 variable
- **WHEN** `scripts/test_launchers.py` writes its scratch `launch.env`
- **THEN** it writes `SDL_AUDIO_DRIVER=dummy`, and the launched environment carries it
