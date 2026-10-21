## ADDED Requirements

### Requirement: The boot log names the XBE the build was made from
When `RECOMP_BUILD_XBE` is set and not empty, the game SHALL print `[BOOT] build xbe: <value>` once, right after the stdio setup, so it is in the first lines of the game log (`RECOMP_STDIO_LOG`). The key SHALL be read through `recomp_env`. When the key is unset or empty, nothing SHALL be printed. The packaged launchers set it from `launch.env.default`; dev and golden runs do not.

#### Scenario: Packaged game
- **WHEN** a packaged build starts through its launcher
- **THEN** the game log's first lines include `[BOOT] build xbe: <sha256> <verdict>`

#### Scenario: Dev run
- **WHEN** the game runs without `RECOMP_BUILD_XBE`
- **THEN** the log has no `build xbe` line and is otherwise unchanged
