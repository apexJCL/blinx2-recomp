## MODIFIED Requirements

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

## ADDED Requirements

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

## REMOVED Requirements

### Requirement: The keyboard can stand in for a pad on port 0
**Reason**: Superseded by "Keyboard and mouse are a source on port 0": the keyboard no longer needs the host pad, its keys come from `[input.bindings]` rather than one fixed table, and the mouse joins it.
**Migration**: `RECOMP_KEYBOARD` still switches the keyboard (over `input.keyboard`); the compiled-in table stays the default when no `[input.bindings]` is given; layouts move to `config/config.toml` (docs/input.md).
