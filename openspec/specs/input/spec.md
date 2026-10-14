# input Specification

## Purpose
Defines how the title's controller input is supplied: the XInput entry points the port overrides, the scripted pad used by tests and goldens, host controllers mapped onto the Duke layout, and the keyboard and mouse as a configurable source on port 0.

## Requirements

### Requirement: The title's XInput entry points are overridden
`src/recomp_manual.c` SHALL define the seven XDK XInput entry points the title calls (`XGetDevices` `0x00367EEC`, `XGetDeviceChanges` `0x00367F0E`, `XInputOpen` `0x0036821D`, `XInputClose` `0x00368273`, `XInputGetCapabilities` `0x0036827F`, `XInputGetState` `0x00368457`, `XInputSetState` `0x003684CA`), with the guest's stdcall stack contract. For `XDEVICE_TYPE_GAMEPAD` (`0x00366B90`) each of the four ports SHALL be reported as inserted exactly while it has a source (a script on port 0, a host controller the backend has open, or the keyboard and mouse on port 0), and removed when the source goes away; the insert and remove masks of `XGetDeviceChanges` SHALL follow those transitions. The XInput backend (Windows and Proton) probes its slots, so a controller connected later becomes a source; the SDL backend opens the controllers present at start only (hot-plug on SDL hosts is BLX-15, then sdl3-migration BLX-78). No port SHALL be reported as inserted without a source. `XInputGetCapabilities` SHALL describe a Duke-class gamepad (subtype gamepad, all eight digital buttons, eight analog buttons, four stick axes, two rumble motors). `XInputGetState` on a port without a source SHALL return `ERROR_DEVICE_NOT_CONNECTED`. `XInputSetState` SHALL complete synchronously (`dwStatus = 0`), because the title busy-waits on `ERROR_IO_PENDING`. Other device types (memory units, `0x00366B10`) SHALL keep the library's semantics on the guest device-type struct and report nothing inserted.

#### Scenario: Overrides excluded from generated code
- **WHEN** `blinx2 recomp` runs
- **THEN** it reports 8 functions excluded (these seven and `sub_002E0DB0`), and no file in `gen/` defines any of them

#### Scenario: No source, no pad
- **WHEN** the title runs with neither `RECOMP_INPUT_SCRIPT`, nor a connected host controller with the host pad enabled, nor the keyboard or mouse (`input.keyboard`, `input.mouse`, or `RECOMP_KEYBOARD`, `RECOMP_MOUSE`)
- **THEN** no gamepad is reported on any port, `XInputOpen` returns 0 for every port, and the boot follows the no-controller path (title_movie_1a.sfd after the three intro movies, then the attract demo)

#### Scenario: Two host controllers
- **WHEN** two host controllers are connected with the host pad enabled and no script
- **THEN** ports 0 and 1 are reported inserted, ports 2 and 3 are not, and the title's pad structs for ports 0 and 1 hold non-zero handles while ports 2 and 3 hold 0

#### Scenario: Memory units never appear
- **WHEN** the title calls `XGetDevices` for `0x00366B10` before a save
- **THEN** no memory unit is reported, and the save menus offer only the hard disk slots

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
Host controllers SHALL be a source for the pad when the host pad is enabled. Enablement: with no `RECOMP_INPUT_SCRIPT`, the host pad is on by default on Windows and Proton (XInput); elsewhere (SDL2 GameController) it is on with `RECOMP_HOST_PAD=1`, which the macOS app's launcher sets; with a script set, it is off unless `RECOMP_HOST_PAD=1` is given explicitly; `RECOMP_HOST_PAD=0` SHALL always disable host controllers, and nothing else: the keyboard and the mouse SHALL NOT depend on the host pad being enabled (they are governed by `input.keyboard` and `input.mouse`, below). Host controller N (XInput user index or SDL slot N) SHALL drive port N. When a port has both a script and a host source, buttons SHALL be OR-ed, analog values SHALL take the larger, and a stick axis the script leaves at zero SHALL take the host's value. On port 0 a host controller and the keyboard-and-mouse source SHALL be merged the same way, a non-zero keyboard or mouse axis replacing the controller's for that poll.

#### Scenario: Proton with a real controller
- **WHEN** the title runs under Proton with one controller connected and no script
- **THEN** the `[INPUT] sources` line reports `host=on ports=0x1`, and pressing START on the title advances to the story opening (R0_opening.sfd opens; title state 0x5EB620 leaves 0)

#### Scenario: Proton with a Steam Input pad
- **WHEN** the title runs under Proton with a controller that Steam Input exposes as XInput
- **THEN** pressing START on the title advances to the menu

#### Scenario: A script keeps the host out
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@stage1`, a controller connected, and `RECOMP_HOST_PAD` unset
- **THEN** the `[INPUT] sources` line reports `host=off`, and no host button appears in the `[INPUT]` log

#### Scenario: Explicit opt-in merges both
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@skip-intro RECOMP_HOST_PAD=1`
- **THEN** the script skips the intro, and a host button pressed on the title is seen by the game

#### Scenario: Host pads off, keyboard on
- **WHEN** the title runs with `RECOMP_HOST_PAD=0`, no script, and `input.keyboard = true` in effect
- **THEN** the `[INPUT] sources` line reports `host=off keyboard=on ports=0x1` and keys drive port 0

#### Scenario: Pad and mouse together
- **WHEN** a controller drives port 0 with its right stick at rest and the mouse is moved during one game frame
- **THEN** that poll's `sThumbRX`/`sThumbRY` are the mouse's values, and the next poll with the mouse at rest reads the controller's stick again

### Requirement: Host controls map to the Duke layout
A host controller's controls SHALL map to the Xbox gamepad as follows: A, B, X, Y to A, B, X, Y; the left shoulder button to WHITE; the right shoulder button to BLACK; START/Menu to START; BACK/View to BACK; thumbstick clicks to LTHUMB and RTHUMB; the d-pad to the d-pad; the left and right triggers to L and R; the sticks to the left and right sticks with up and right positive. The mapping SHALL be the same on every host backend and SHALL be documented in one table that the code is generated from or checked against.

#### Scenario: Shoulder buttons
- **WHEN** the right shoulder button of a host controller is held
- **THEN** the guest reads `bAnalogButtons[BLACK] = 255` and `bAnalogButtons[WHITE] = 0`

#### Scenario: Mapping unit test
- **WHEN** the toolkit's input mapping test runs (on macOS and under Proton through `blinx2 bench tests`)
- **THEN** every host control in the table produces exactly the listed guest field and value, and the test fails if the README table and the code disagree

### Requirement: Analog values keep the hardware scale
Sticks SHALL be passed to the guest as signed 16-bit values at the host's full range with no deadzone applied by default, because the title applies its own (a float deadzone on the normalised stick and a 0x6000 threshold for stick-as-d-pad). `RECOMP_PAD_DEADZONE=N` (0..32767) SHALL apply a radial deadzone of N with rescaling, for drifting pads. Triggers SHALL be 0..255 at the host's resolution. Digital face buttons SHALL be reported as 255 when held and 0 otherwise, which is above the title's 30 threshold. The right stick's Y SHALL reach the title's normalisation sign-extended, like the other three axes.

#### Scenario: Right stick down
- **WHEN** the right stick is held fully down
- **THEN** the title's pad struct holds `sThumbRY = -32768` at `+0x10` and a negative normalised float at `+0x20`, not a value near +1

#### Scenario: Deadzone off by default
- **WHEN** `RECOMP_PAD_DEADZONE` is unset and the left stick rests at (300, -200)
- **THEN** the guest reads exactly (300, -200)

#### Scenario: Deadzone on
- **WHEN** `RECOMP_PAD_DEADZONE=4000` and the left stick rests at (300, -200)
- **THEN** the guest reads (0, 0), and a stick at (32767, 0) still reads (32767, 0)

### Requirement: Rumble reaches the host controller
`XInputSetState` motor speeds (0..65535 per motor) SHALL be forwarded to the host controller on the same port when the host pad is enabled and that port has a host device. `RECOMP_RUMBLE=0` SHALL disable forwarding. All motors SHALL be set to zero when the process exits or the host pad is shut down.

#### Scenario: Rumble on a hit
- **WHEN** Stick takes a hit in stage 1-1 with a real controller
- **THEN** the controller vibrates, and the `[INPUT]` trace (when enabled) shows the two motor values the title set

#### Scenario: Rumble on a scripted run
- **WHEN** a scripted run with the host pad off reaches the same hit
- **THEN** no host rumble call is made and the title's feedback status still reads complete

### Requirement: Input sources are logged
At start the host SHALL log one line `[INPUT] sources: script=<name|off> host=<on|off> keyboard=<on|off> mouse=<on|off> rumble=<on|off> ports=<mask>` and SHALL log `[INPUT] t=<s> ports=<mask>` whenever the connected mask changes. Host-driven state changes SHALL be logged per port as `[INPUT] t=<s> host port=<n> buttons=<state>` in the same format as script changes, at most once per poll per port. The bench SHALL record these lines with the run.

#### Scenario: Sources line in a bench run
- **WHEN** a bench run finishes
- **THEN** `game-stdio.log` holds the `sources` line, and `run-info.txt` records `RECOMP_HOST_PAD` and `RECOMP_KEYBOARD` as they were set

### Requirement: Scripted and golden runs are isolated from host devices
Golden and integration runs (`blinx2 bench golden`, `blinx2 bench integrate`) SHALL set `RECOMP_HOST_PAD=0`, `RECOMP_KEYBOARD=0` and `RECOMP_MOUSE=0` and record them. With `RECOMP_INPUT_STRICT=1` a script that fails to parse, or names an unknown preset, SHALL end the run with a non-zero exit before the game starts; the bench SHALL set it. A tap step SHALL accept a period in polls (`every Np`) and an action a hold in polls (`BUTTON/Np`), so presets can avoid wall-clock time.

#### Scenario: Pad plugged into the bench
- **WHEN** `blinx2 bench golden` runs while a controller is connected to the Linux/Proton host
- **THEN** every scenario's `sources` line reports `host=off keyboard=off mouse=off`, and the frames match the references as without the controller

#### Scenario: Bad preset in strict mode
- **WHEN** `RECOMP_INPUT_SCRIPT=@no-such RECOMP_INPUT_STRICT=1`
- **THEN** the host logs `[INPUT] unknown preset` and exits with status 2 before the guest entry point

#### Scenario: Poll-counted tap
- **WHEN** a script runs `tap A every 6p until mem 0xae73fc == 1`
- **THEN** successive A presses start exactly 6 port-0 polls apart in the `[INPUT]` log, independent of frame rate

### Requirement: Keyboard and mouse are a source on port 0
The host keyboard and mouse together SHALL be one source for port 0, merged on top of a controller there, on every host that has a window: the SDL window (macOS, Linux), the D3D11 window and the GDI window (Windows and Proton). They SHALL be read only while the title's window has focus; losing focus, hiding or minimising the window SHALL release every key and mouse button and the cursor capture. The source SHALL be enabled by `input.keyboard` (bound to `RECOMP_KEYBOARD`) and `input.mouse` (bound to `RECOMP_MOUSE`), each read through the configuration layer (environment over `config.toml` over `config.default.toml` over the code default); the code default of both SHALL be off, and this title's shipped `config.default.toml` SHALL set both on. When `RECOMP_INPUT_SCRIPT` is set, both SHALL be off unless the environment sets them on explicitly, so a file value never reaches a scripted run. Port 0 SHALL be reported inserted while the source is enabled, with or without a controller, so a controller plugged in or out during play never removes port 0. The `[INPUT] sources` line SHALL report `keyboard=<on|off> mouse=<on|off>`.

#### Scenario: Keyboard and mouse from the shipped defaults
- **WHEN** a bundle, or a developer build beside its `config.default.toml`, starts with no script, no controller and no `RECOMP_KEYBOARD`/`RECOMP_MOUSE` in the environment
- **THEN** the log shows `[INPUT] config: keyboard=on mouse=on ...` and `sources: ... keyboard=on mouse=on ports=0x1`, and Return on the title advances exactly as START on a controller

#### Scenario: A script keeps the keyboard out
- **WHEN** the title runs with `RECOMP_INPUT_SCRIPT=@attract` and the defaults file says `keyboard = true`
- **THEN** `sources` reports `keyboard=off mouse=off`; with `RECOMP_KEYBOARD=1` added it reports `keyboard=on`

#### Scenario: Golden runs see neither
- **WHEN** a golden run starts with `RECOMP_CONFIG=none RECOMP_KEYBOARD=0 RECOMP_MOUSE=0`
- **THEN** the log reads `[INPUT] config: keyboard=off mouse=off (RECOMP_CONFIG=none)`, no key or mouse reaches the pad, and the frames match the references as before this change

#### Scenario: Unfocused window
- **WHEN** keys are pressed and the mouse is moved while another application has focus
- **THEN** nothing is logged and the pad state does not change

#### Scenario: Controller unplugged with the keyboard on
- **WHEN** the only controller is unplugged during play with `input.keyboard = true`
- **THEN** the `[INPUT]` log shows no `ports=0x0` line, the title's port-0 handle stays non-zero, and a stick key moves Stick

### Requirement: The mapping lives in the configuration files
The binding of host inputs to the Duke's controls SHALL be read from the `[input]` and `[input.bindings]` tables of the configuration files through the layering of `config-layering` (`config.default.toml` shipped and read, `config/config.toml` the player's differences). `[input.bindings]` SHALL map each control name (`a b x y white black ltrigger rtrigger start back lthumb rthumb dpad_up dpad_down dpad_left dpad_right lstick_up lstick_down lstick_left lstick_right rstick_up rstick_down rstick_left rstick_right`) to a string or an array of strings naming keys (`A`..`Z`, `0`..`9`, `F1`..`F12`, `Space`, `Return`/`Enter`, `Escape`/`Esc`, `Backspace`, `Tab`, `LShift` `RShift` `Shift`, `LCtrl` `RCtrl` `Ctrl`, `LAlt` `RAlt` `Alt`, `Up` `Down` `Left` `Right`, `Insert` `Delete` `Home` `End` `PageUp` `PageDown`, `KP0`..`KP9`, `KPEnter` `KPPlus` `KPMinus` `KPMultiply` `KPDivide` `KPPeriod`, `Comma` `Period` `Slash` `Semicolon` `Quote` `LBracket` `RBracket` `Backslash` `Minus` `Equals` `Grave`) or mouse inputs (`MouseLeft` `MouseRight` `MouseMiddle` `Mouse4` `Mouse5` `WheelUp` `WheelDown`), case-insensitively, by the label the host layout gives the key. Resolution SHALL be: per control, the highest layer that names it wins whole (`[]` unbinds); an input the player's file names under one control is removed from every control it inherited from a lower layer; an input named under two controls in one file is reported and the second occurrence ignored; a control no file names keeps the compiled-in default. The `[input]` knobs SHALL be `keyboard`, `mouse` (bool), `mouse_look` (`right_stick` default, `left_stick`, `none`), `mouse_sensitivity` (0.1..10.0, default 1.0), `mouse_invert_y`, `mouse_invert_x` (bool, default false), `mouse_min_deflection` (0.0..0.9, default 0.45), `mouse_capture` (`focus` default, `click`, `never`), `mouse_release_key` (default `F9`; `""` or `"none"`: no key), `wheel_pulse_ms` (default 100), `stick_ramp_ms` (0..2000, compiled-in default 0, instant), `walk_key` (compiled-in default none; `""` or `"none"`: no key), `walk_scale` (0.41..1.0, compiled-in default 1.0); the compiled-in stick defaults SHALL keep the toolkit's legacy keyboard, and the game's shipped `config.default.toml` SHALL set `stick_ramp_ms = 60`, `walk_key = "LAlt"` and `walk_scale = 0.5`. Every error SHALL be one line `[INPUT] config error: <file>:<line>: <message>` naming the control or key and what was done instead, SHALL never be fatal, and SHALL leave the rest of the file applied; an unknown control, an unknown input, a wrong type, an out-of-range knob and an unknown choice SHALL each have their message; a binding of `F9`, `F10` or `F11` SHALL be applied with a warning naming the reserved use. One line `[INPUT] config: keyboard=<on|off> mouse=<on|off> look=<target> sens=<v> bindings=<n> (<file>) [+<m> (<file>)]` SHALL be logged at init; the toolkit's compiled-in key table SHALL be the fallback when no file binds a control and SHALL NOT change. The `[ENHANCE]` lines SHALL gain nothing and the golden harness SHALL NOT learn `[input]` keys.

#### Scenario: Player rebinds one key
- **WHEN** `config.default.toml` binds `start = ["Return", "Escape"]` and the player's `config/config.toml` holds `[input.bindings]` `back = "Escape"`
- **THEN** Escape drives BACK and not START, Return still drives START, and the `[INPUT] config:` line reports one binding from the player's file

#### Scenario: Unknown control
- **WHEN** the player's file holds `jmp = "Space"` under `[input.bindings]` and `a = "J"` on the next line
- **THEN** the log shows `[INPUT] config error: config/config.toml:<line>: unknown control 'jmp' under [input.bindings] (controls: a b x ... rstick_right); ignored`, and J drives A

#### Scenario: Unknown key
- **WHEN** the player's file holds `a = ["Spacebar", "J"]`
- **THEN** the log names `'Spacebar'` as an unknown input for `input.bindings.a` and points at `docs/input.md`, and J drives A

#### Scenario: Knob out of range
- **WHEN** the player's file holds `mouse_sensitivity = 50`
- **THEN** the log reports the value, the range `0.1 .. 10.0` and `using 1.0`, and the mouse model runs at 1.0

#### Scenario: Reserved key bound
- **WHEN** the player's file holds `start = "F10"`
- **THEN** F10 drives START, and one warning line says F10 is the menu hotkey

#### Scenario: Environment over the file
- **WHEN** `config.default.toml` says `keyboard = true` and the process runs with `RECOMP_KEYBOARD=0`
- **THEN** the keyboard is off, `sources` reports `keyboard=off`, and the bindings are still read (the mouse may use them)

### Requirement: The mouse drives a stick
With `input.mouse` on, the mouse's relative motion accumulated between two polls of port 0 SHALL become that poll's deflection of the stick `input.mouse_look` names: per axis `c = counts * mouse_sensitivity / 40`, deflection `0` when `c` is zero, otherwise `sign(c) * (mouse_min_deflection + (1 - mouse_min_deflection) * min(1, |c|)) * 32767`, mouse right as stick right and mouse forward as stick up unless `mouse_invert_x`/`mouse_invert_y`. A mouse at rest SHALL read zero at the next poll. Mouse buttons SHALL drive their bound controls like keys (255 or a `wButtons` bit while held); a wheel notch SHALL hold its control for `wheel_pulse_ms` and notches SHALL queue. The floor `mouse_min_deflection` SHALL default above the title's own 0.4 stick deadzone so any motion moves the camera.

#### Scenario: Full deflection
- **WHEN** the mouse moves 40 counts right in one game frame at `mouse_sensitivity = 1.0`
- **THEN** that poll reads `sThumbRX = 32767`, and the next poll with the mouse still reads 0

#### Scenario: Slow motion clears the deadzone
- **WHEN** the mouse moves 1 count forward in one frame with `mouse_min_deflection = 0.45` and `mouse_sensitivity = 1.0`
- **THEN** that poll reads `sThumbRY = 15196 ± 1` (`0.45 + 0.55 · 1/40` of full), above the title's 0.4 threshold

#### Scenario: Inverted Y
- **WHEN** `mouse_invert_y = true` and the mouse moves forward
- **THEN** `sThumbRY` is negative

#### Scenario: Wheel notch
- **WHEN** the player's file binds `white = ["C", "WheelUp"]` (the wheel is unbound by default) and the wheel is rolled up one notch at 30 polls per second
- **THEN** `bAnalogButtons[WHITE]` reads 255 for three consecutive polls and 0 after

### Requirement: The cursor is captured while the window has focus
With `input.mouse` on and `mouse_capture = "focus"` (the default), the cursor SHALL be captured (hidden, relative motion, confined to the window) whenever the game window has focus, from the first focus on; the capture SHALL be released on focus loss, hide or minimise, while the enhancements menu is open (`xbox_InputMouseSuspend(1)`), and when the window closes, and SHALL be taken again when focus returns or the menu closes. `mouse_release_key` (default `F9`; `""` or `"none"`: no key) SHALL toggle the capture: pressed while captured it frees the cursor and the window keeps focus with the cursor free; pressed again it captures. While released, motion and buttons SHALL drive nothing. `"click"` SHALL capture on the first mouse button press inside the focused window (that press consumed) and otherwise behave as `focus`; `"never"` SHALL never capture, buttons working only over the window. Each transition SHALL log `[INPUT] mouse captured` or `[INPUT] mouse released (<reason>)`. On Windows the motion SHALL come from raw input (`WM_INPUT`) with a re-centring `WM_MOUSEMOVE` fallback when raw input is silent, and the first capture SHALL log which path is in use; on SDL hosts from relative mouse mode. The same window procedures SHALL feed the SDL, D3D11 and GDI windows; headless runs SHALL have no mouse.

#### Scenario: Focus captures
- **WHEN** the game window gains focus with `input.mouse` on and the defaults (`rtrigger = ["MouseLeft", "R"]`)
- **THEN** `[INPUT] mouse captured` is logged, the cursor is hidden, and the first left click after the capture (not the click that focused the window) reads `bAnalogButtons[RTRIGGER] = 255`

#### Scenario: The focusing click drives nothing
- **WHEN** a left click brings the unfocused game window forward, on any host (Win32 or Wine, SDL on macOS or Linux), with `mouse_capture = "focus"`
- **THEN** that click reads no control; the toolkit knows it from `WM_MOUSEACTIVATE` on Win32, and elsewhere as the first press within 250 ms of the focus gain

#### Scenario: Alt-Tab releases
- **WHEN** the cursor is captured and the player switches to another window
- **THEN** `[INPUT] mouse released (focus)` is logged, the cursor is visible and free, and every key and button reads released

#### Scenario: F9 frees the cursor
- **WHEN** the cursor is captured and `F9` is pressed
- **THEN** `[INPUT] mouse released (key)` is logged, the cursor is free while the window keeps focus, mouse motion drives nothing, and a second `F9` or a focus loss and return captures again

### Requirement: Key and mouse events can be injected for tests
With `RECOMP_DEBUG=kbm_script=<file>` the toolkit SHALL apply a file of timed events on the pad poll, one per line: a time in seconds since the first poll or in polls (`Np`), then `key down|up NAME`, `mouse move DX DY` (counts, one poll's motion), `mouse down|up NAME` or `wheel N`, with `#` comments; names SHALL be the binding vocabulary. It SHALL write the same tables the windows write and force capture, SHALL log `[INPUT] kbm_script: <n> events` at init and report a bad line with its number and skip it, and SHALL be refused with one line when `RECOMP_INPUT_SCRIPT` is set.

#### Scenario: Headless title screen on the Mac
- **WHEN** a headless Metal run with the build's defaults and `kbm_script` holding `15.0 key down Return` / `15.2 key up Return` reaches the title
- **THEN** the log shows `[KEY] down Return`, `host port=0 buttons=START` and `R0_opening.sfd` opens

#### Scenario: Mouse under Proton
- **WHEN** a `blinx2 bench run` under Proton (D3D11 window) plays a script with `mouse move 20 -5` once the title has appeared
- **THEN** `[MOUSE] dx=20 dy=-5 -> RS(23756,...)` is logged, the `host port=0` line of that poll carries the same right-stick values and the next poll's reads zero, and the first capture logged which motion path the window used (raw input or the re-centre fallback)

#### Scenario: Refused beside an input script
- **WHEN** both `RECOMP_INPUT_SCRIPT=@stage1` and `kbm_script` are set
- **THEN** one `[INPUT] kbm_script: refused (RECOMP_INPUT_SCRIPT is set)` line is logged and the preset runs alone

### Requirement: Host inputs are named in the trace
With `RECOMP_TRACE=key` the host SHALL log every key and mouse edge by its binding name (`[KEY] down Space`, `[KEY] up Space`, `[KEY] mouse down MouseLeft`, `[KEY] wheel +1`), the first 200 edges then one in 50, so a player can discover a name by pressing the key; `RECOMP_TRACE=mouse` SHALL log the mouse model's input and output per poll with motion (`[MOUSE] dx=<n> dy=<n> -> RS(<x>,<y>)`) for the first 200 such polls.

#### Scenario: Discover a key name
- **WHEN** the trace is on and the player presses and releases the space bar
- **THEN** stderr shows `[KEY] down Space` then `[KEY] up Space`
