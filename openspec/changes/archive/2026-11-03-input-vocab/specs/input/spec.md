## MODIFIED Requirements

### Requirement: The mapping lives in the configuration files
The binding of host inputs to the Duke's controls SHALL be read from the `[input]` and `[input.bindings]` tables of the configuration files through the layering of `config-layering` (`config.default.toml` shipped and read, `config/config.toml` the player's differences). `[input.bindings]` SHALL map each control name (upstream xboxrecomp's names from the toolkit's `src/input/input_map.c`: `dpad_up dpad_down dpad_left dpad_right start back left_thumb right_thumb a b x y black white left_trigger right_trigger left_stick_up left_stick_down left_stick_left left_stick_right right_stick_up right_stick_down right_stick_left right_stick_right`) to a string or an array of strings naming keys by upstream's key names (`xbox_InputMap_KeyFromName`: `A`..`Z`, `0`..`9`, `F1`..`F12`, `Space`, `Enter`/`Return`, `Escape`/`Esc`, `Backspace`, `Tab`, `Pause`, `CapsLock`, `LShift` `RShift` `Shift`, `LCtrl` `RCtrl` `Ctrl`/`Control`, `LAlt` `RAlt` `Alt`, `Up` `Down` `Left` `Right`, `Insert` `Delete` `Home` `End` `PageUp` `PageDown`, `Numpad0`..`Numpad9`, `NumpadAdd` `NumpadSubtract` `NumpadMultiply` `NumpadDivide` `NumpadDecimal`, `Comma` `Period` `Slash` `Semicolon` `Quote` `LeftBracket` `RightBracket` `Backslash` `Minus` `Equals` `Grave`) plus the fork's `NumpadEnter`, or mouse inputs (upstream's `Mouse1`..`Mouse5`, the fork's `WheelUp` `WheelDown`), case-insensitively, by the label the host layout gives the key. The names used before the tracker item (`ltrigger`, `lthumb`, `lstick_up`, `KP8`, `KPEnter`, `LBracket`, `MouseLeft` ...) SHALL be unknown names, with no alias. Resolution SHALL be: per control, the highest layer that names it wins whole (`[]` unbinds); an input the player's file names under one control is removed from every control it inherited from a lower layer; an input named under two controls in one file is reported and the second occurrence ignored; a control no file names keeps the compiled-in default. The `[input]` knobs SHALL be `keyboard`, `mouse` (bool), `mouse_look` (`right_stick` default, `left_stick`, `none`), `mouse_sensitivity` (0.1..10.0, default 1.0), `mouse_invert_y`, `mouse_invert_x` (bool, default false), `mouse_min_deflection` (0.0..0.9, default 0.45), `mouse_capture` (`focus` default, `click`, `never`), `mouse_release_key` (default `F9`; `""` or `"none"`: no key), `wheel_pulse_ms` (default 100), `stick_ramp_ms` (0..2000, compiled-in default 0, instant), `walk_key` (compiled-in default none; `""` or `"none"`: no key), `walk_scale` (0.41..1.0, compiled-in default 1.0); the compiled-in stick defaults SHALL keep the toolkit's legacy keyboard, and the game's shipped `config.default.toml` SHALL set `stick_ramp_ms = 60`, `walk_key = "LAlt"` and `walk_scale = 0.5`. Every error SHALL be one line `[INPUT] config error: <file>:<line>: <message>` naming the control or key and what was done instead, SHALL never be fatal, and SHALL leave the rest of the file applied; an unknown control, an unknown input, a wrong type, an out-of-range knob and an unknown choice SHALL each have their message; a binding of `F9`, `F10` or `F11` SHALL be applied with a warning naming the reserved use. One line `[INPUT] config: keyboard=<on|off> mouse=<on|off> look=<target> sens=<v> bindings=<n> (<file>) [+<m> (<file>)]` SHALL be logged at init; the toolkit's compiled-in key table SHALL be the fallback when no file binds a control and SHALL NOT change. The `[ENHANCE]` lines SHALL gain nothing and the golden harness SHALL NOT learn `[input]` keys.

#### Scenario: Player rebinds one key
- **WHEN** `config.default.toml` binds `start = ["Enter", "Escape"]` and the player's `config/config.toml` holds `[input.bindings]` `back = "Escape"`
- **THEN** Escape drives BACK and not START, Enter still drives START, and the `[INPUT] config:` line reports one binding from the player's file

#### Scenario: Unknown control
- **WHEN** the player's file holds `jmp = "Space"` under `[input.bindings]` and `a = "J"` on the next line
- **THEN** the log shows `[INPUT] config error: config/config.toml:<line>: unknown control 'jmp' under [input.bindings] (controls: dpad_up dpad_down ... right_stick_right); ignored`, and J drives A

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

### Requirement: The cursor is captured while the window has focus
With `input.mouse` on and `mouse_capture = "focus"` (the default), the cursor SHALL be captured (hidden, relative motion, confined to the window) whenever the game window has focus, from the first focus on; the capture SHALL be released on focus loss, hide or minimise, while the enhancements menu is open (`xbox_InputMouseSuspend(1)`), and when the window closes, and SHALL be taken again when focus returns or the menu closes. `mouse_release_key` (default `F9`; `""` or `"none"`: no key) SHALL toggle the capture: pressed while captured it frees the cursor and the window keeps focus with the cursor free; pressed again it captures. While released, motion and buttons SHALL drive nothing. `"click"` SHALL capture on the first mouse button press inside the focused window (that press consumed) and otherwise behave as `focus`; `"never"` SHALL never capture, buttons working only over the window. Each transition SHALL log `[INPUT] mouse captured` or `[INPUT] mouse released (<reason>)`. On Windows the motion SHALL come from raw input (`WM_INPUT`) with a re-centring `WM_MOUSEMOVE` fallback when raw input is silent, and the first capture SHALL log which path is in use; on SDL hosts from relative mouse mode. The same window procedures SHALL feed the SDL, D3D11 and GDI windows; headless runs SHALL have no mouse.

#### Scenario: Focus captures
- **WHEN** the game window gains focus with `input.mouse` on and the defaults (`right_trigger = ["mouse1", "R"]`)
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
- **WHEN** a headless Metal run with the build's defaults and `kbm_script` holding `15.0 key down Enter` / `15.2 key up Enter` reaches the title
- **THEN** the log shows `[KEY] down enter`, `host port=0 buttons=START` and `R0_opening.sfd` opens

#### Scenario: Mouse under Proton
- **WHEN** a `blinx2 bench run` under Proton (D3D11 window) plays a script with `mouse move 20 -5` once the title has appeared
- **THEN** `[MOUSE] dx=20 dy=-5 -> RS(23756,...)` is logged, the `host port=0` line of that poll carries the same right-stick values and the next poll's reads zero, and the first capture logged which motion path the window used (raw input or the re-centre fallback)

#### Scenario: Refused beside an input script
- **WHEN** both `RECOMP_INPUT_SCRIPT=@stage1` and `kbm_script` are set
- **THEN** one `[INPUT] kbm_script: refused (RECOMP_INPUT_SCRIPT is set)` line is logged and the preset runs alone

### Requirement: Host inputs are named in the trace
With `RECOMP_TRACE=key` the host SHALL log every key and mouse edge by its canonical binding name, upstream's `xbox_InputMap_KeyName` (`[KEY] down space`, `[KEY] up space`, `[KEY] mouse down mouse1`, `[KEY] wheel +1`), the first 200 edges then one in 50, so a player can discover a name by pressing the key; `RECOMP_TRACE=mouse` SHALL log the mouse model's input and output per poll with motion (`[MOUSE] dx=<n> dy=<n> -> RS(<x>,<y>)`) for the first 200 such polls.

#### Scenario: Discover a key name
- **WHEN** the trace is on and the player presses and releases the space bar
- **THEN** stderr shows `[KEY] down space` then `[KEY] up space`
