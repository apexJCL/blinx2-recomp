# input Specification

## Purpose
TBD - created by archiving change input. Update Purpose after archive.

## Requirements

### Requirement: The title's XInput entry points are overridden
`src/recomp_manual.c` SHALL define the seven XDK XInput entry points the title calls (`XGetDevices` `0x00367EEC`, `XGetDeviceChanges` `0x00367F0E`, `XInputOpen` `0x0036821D`, `XInputClose` `0x00368273`, `XInputGetCapabilities` `0x0036827F`, `XInputGetState` `0x00368457`, `XInputSetState` `0x003684CA`), with the guest's stdcall stack contract. For `XDEVICE_TYPE_GAMEPAD` (`0x00366B90`), they SHALL report a gamepad as inserted on each port that has a source, and `XInputGetState` SHALL return that source's state. Other device types SHALL keep the library's semantics on the guest device-type struct. `XInputSetState` SHALL complete synchronously (`dwStatus = 0`).

#### Scenario: Overrides excluded from generated code
- **WHEN** `scripts/pipeline.sh recomp` runs
- **THEN** it reports 8 functions excluded (these seven and `sub_002E0DB0`), and no file in `gen/` defines any of them

#### Scenario: No source, no pad
- **WHEN** the title runs with neither `RECOMP_INPUT_SCRIPT` nor a host pad enabled
- **THEN** no gamepad is reported, and the boot follows the same path as before the overrides (title_movie_1a.sfd after the three intro movies)

### Requirement: A script drives the pad on port 0
When `RECOMP_INPUT_SCRIPT` is set, port 0 SHALL report a gamepad whose state follows the script. The value is an inline list of steps separated by `;`, a path to a file of steps (one per line, `#` comments), or `@name` for a built-in preset. Steps SHALL run in order:
- `wait open TEXT`: until the title opens a file (successfully) whose guest path contains TEXT, case-insensitively;
- `wait SECS`: SECS seconds;
- `wait polls N`: N more polls of port 0;
- `tap BUTTON [every P] until open TEXT`: press BUTTON for P/2 every P seconds (default 0.5) until TEXT opens, then release it at once;
- `ACTION[,ACTION...]`: applied at once. An action is `BUTTON` (press), `-BUTTON` (release), `BUTTON/D` (press, release D seconds later) or `BUTTON=V` (an analog or stick value).

Buttons are the digital `UP DOWN LEFT RIGHT START BACK LTHUMB RTHUMB`, the analog `A B X Y BLACK WHITE L R` (a press is 255), and the sticks `LX LY RX RY`. File opens SHALL be observed from before the game starts and kept, so an open that happens before the first pad poll, or while an earlier step is waiting, still satisfies the step that waits for it; each match consumes the opens up to it. The absolute form `T:ACTION[,ACTION...]` and `T1-T2@P:BUTTON` (seconds since the first pad poll) SHALL still work alongside the steps. Each pad change SHALL be logged as `[INPUT] t=<seconds> buttons=<state>`, each step start and matched open as an `[INPUT] t=...` line, and the packet number SHALL advance only when the state changes.

#### Scenario: Presets reach their targets at any speed
- **WHEN** the title runs on macOS with `@skip-intro`, `@attract` or `@new-game`, both normally and slowed down (busy loops on every core)
- **THEN** `@skip-intro` and `@attract` end idle on title_movie_1a.sfd and the attract demo loads stg0101; `@new-game` reaches R0_opening.sfd and then the Time Sweeper editor (tsedit); no step depends on wall time

#### Scenario: Scripted START skips the intro
- **WHEN** the title runs with `@skip-intro`
- **THEN** stderr shows each step and matched open, logo_artoon.sfd is never opened, and title_movie_1a.sfd opens a few seconds after start instead of about 84 s

#### Scenario: Unknown button or bad step
- **WHEN** a script names a button that does not exist, or a step that does not parse
- **THEN** an `[INPUT] script:` line is logged and the remaining steps still run

### Requirement: A host pad can drive the pad
The host's controller SHALL be merged into the pad state when enabled: by default on Windows (XInput, plus the keyboard with `RECOMP_KEYBOARD=1`), and with `RECOMP_HOST_PAD=1` elsewhere (SDL2 GameController). `RECOMP_HOST_PAD=0` SHALL disable it. Buttons SHALL be OR-ed with the script's, analog values SHALL take the larger, and a stick axis the script leaves at zero SHALL take the host's value.

#### Scenario: Proton with a Steam Input pad
- **WHEN** the title runs under Proton with a controller that Steam Input exposes as XInput
- **THEN** pressing START on the title advances to the menu
