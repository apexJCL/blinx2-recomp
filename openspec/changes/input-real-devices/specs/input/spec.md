## MODIFIED Requirements

### Requirement: The title's XInput entry points are overridden
`src/recomp_manual.c` SHALL define the seven XDK XInput entry points the title calls (`XGetDevices` `0x00367EEC`, `XGetDeviceChanges` `0x00367F0E`, `XInputOpen` `0x0036821D`, `XInputClose` `0x00368273`, `XInputGetCapabilities` `0x0036827F`, `XInputGetState` `0x00368457`, `XInputSetState` `0x003684CA`), with the guest's stdcall stack contract. For `XDEVICE_TYPE_GAMEPAD` (`0x00366B90`) each of the four ports SHALL be reported as inserted exactly while it has a source (a script on port 0, a connected host controller, or the keyboard on port 0), and removed when the source goes away; the insert and remove masks of `XGetDeviceChanges` SHALL follow those transitions. No port SHALL be reported as inserted without a source. `XInputGetCapabilities` SHALL describe a Duke-class gamepad (subtype gamepad, all eight digital buttons, eight analog buttons, four stick axes, two rumble motors). `XInputGetState` on a port without a source SHALL return `ERROR_DEVICE_NOT_CONNECTED`. `XInputSetState` SHALL complete synchronously (`dwStatus = 0`), because the title busy-waits on `ERROR_IO_PENDING`. Other device types (memory units, `0x00366B10`) SHALL keep the library's semantics on the guest device-type struct and report nothing inserted.

#### Scenario: Overrides excluded from generated code
- **WHEN** `blinx2 recomp` runs
- **THEN** it reports 8 functions excluded (these seven and `sub_002E0DB0`), and no file in `gen/` defines any of them

#### Scenario: No source, no pad
- **WHEN** the title runs with neither `RECOMP_INPUT_SCRIPT`, nor a connected host controller with the host pad enabled, nor `RECOMP_KEYBOARD`
- **THEN** no gamepad is reported on any port, `XInputOpen` returns 0 for every port, and the boot follows the no-controller path (title_movie_1a.sfd after the three intro movies, then the attract demo)

#### Scenario: Two host controllers
- **WHEN** two host controllers are connected with the host pad enabled and no script
- **THEN** ports 0 and 1 are reported inserted, ports 2 and 3 are not, and the title's pad structs for ports 0 and 1 hold non-zero handles while ports 2 and 3 hold 0

#### Scenario: Memory units never appear
- **WHEN** the title calls `XGetDevices` for `0x00366B10` before a save
- **THEN** no memory unit is reported, and the save menus offer only the hard disk slots

### Requirement: A host pad can drive the pad
Host controllers SHALL be a source for the pad when the host pad is enabled. Enablement: with no `RECOMP_INPUT_SCRIPT`, the host pad is on by default on every host that has a backend (XInput on Windows and Proton, SDL2 GameController elsewhere); with a script set, it is off unless `RECOMP_HOST_PAD=1` is given explicitly; `RECOMP_HOST_PAD=0` SHALL always disable it. Host controller N (XInput user index or SDL slot N) SHALL drive port N. When a port has both a script and a host source, buttons SHALL be OR-ed, analog values SHALL take the larger, and a stick axis the script leaves at zero SHALL take the host's value.

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

## ADDED Requirements

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

### Requirement: Hot-plugging follows the host
A host controller connected or disconnected while the title runs SHALL appear or disappear on its port within one second, and the title SHALL be told through the insert/remove masks so it reopens or closes the port itself. Disconnected ports SHALL be probed at most once per second (the XInput guidance), connected ports at every poll. On hosts whose backend delivers device events (SDL2), those events SHALL be handled and slots SHALL be stable for the life of a device.

#### Scenario: Unplug and replug in play
- **WHEN** the only controller is unplugged during stage 1-1 and plugged back in five seconds later
- **THEN** the `[INPUT]` log shows `ports=0x0` then `ports=0x1`, the title's port-0 handle goes to 0 and back to non-zero, and play continues with the pad

### Requirement: Rumble reaches the host controller
`XInputSetState` motor speeds (0..65535 per motor) SHALL be forwarded to the host controller on the same port when the host pad is enabled and that port has a host device. `RECOMP_RUMBLE=0` SHALL disable forwarding. All motors SHALL be set to zero when the process exits or the host pad is shut down.

#### Scenario: Rumble on a hit
- **WHEN** Stick takes a hit in stage 1-1 with a real controller
- **THEN** the controller vibrates, and the `[INPUT]` trace (when enabled) shows the two motor values the title set

#### Scenario: Rumble on a scripted run
- **WHEN** a scripted run with the host pad off reaches the same hit
- **THEN** no host rumble call is made and the title's feedback status still reads complete

### Requirement: The keyboard can stand in for a pad on port 0
With `RECOMP_KEYBOARD=1` the host keyboard SHALL act as a port-0 source whenever the title's window has focus, on Windows and Proton (the GDI and D3D11 windows alike, whichever is up) and on POSIX hosts (the SDL window: macOS, Linux), with one key map shared by every host, kept in one table (toolkit `src/input/README.md`) that a test checks against the code. The map SHALL be: arrows the d-pad; Enter START; Backspace BACK; Z, X, C, V the A, B, X, Y buttons; Q and E WHITE and BLACK; 1 and 3 the left and right triggers; Shift and Ctrl the left and right stick clicks; W, S, A, D and numpad 8, 2, 4, 6 the left stick; I, K, J, L the right stick, each key at full deflection. Keys SHALL be matched by the label the host layout gives them (Windows virtual-key codes; SDL keycodes, not scancodes). It SHALL be off by default in the game and in bench runs, SHALL require the host pad to be on, and SHALL count as a source for connection reporting only when enabled. Losing the window's focus, hiding or minimising it SHALL release every key, key auto-repeat SHALL NOT produce presses, and on macOS a key pressed with Cmd held SHALL be ignored. The packaged game's launcher defaults (Windows, SteamOS, macOS) MAY turn it on.

#### Scenario: Enter on the title on macOS
- **WHEN** the title runs on macOS with the Metal backend, `RECOMP_HOST_PAD=1 RECOMP_KEYBOARD=1`, no controller and no script, and Return is pressed in the game window on the title
- **THEN** the log shows `host port=0 buttons=START` and the title advances exactly as for START on a controller

#### Scenario: Laptop left stick
- **WHEN** W is held in the focused game window with the keyboard on
- **THEN** the guest reads `sThumbLY = 32767` and no d-pad bit, and holding C reads `bAnalogButtons[X] = 255`

#### Scenario: Focus lost with a key held
- **WHEN** a mapped key is held in the game window and the window loses focus before the key is released
- **THEN** the key reads as released from the next poll on, and stays released until it is pressed again in the focused window

#### Scenario: Held key repeats
- **WHEN** a mapped key is held for a second in the focused game window
- **THEN** the key reads as held throughout and the key trace shows one down edge, not the host's auto-repeat

#### Scenario: Enter on the title under Proton
- **WHEN** the title runs under Proton with the D3D11 backend and no `RECOMP_FB_WINDOW`, `RECOMP_KEYBOARD=1`, no controller, and Enter is pressed on the title
- **THEN** the title advances exactly as for START on a controller

#### Scenario: Keyboard off
- **WHEN** `RECOMP_KEYBOARD` is unset, or set with the host pad off
- **THEN** keys do nothing and the keyboard is not counted as a source

#### Scenario: Map test
- **WHEN** the toolkit's keyboard tests run (on macOS, and `input_keyboard` under Proton through `blinx2 bench tests`)
- **THEN** every key in the table produces exactly the listed guest field and value, no key is on two rows, the SDL keycode of every key maps to its Windows virtual-key code, and the test fails if the README table and the code disagree

### Requirement: Input sources are logged
At start the host SHALL log one line `[INPUT] sources: script=<name|off> host=<on|off> keyboard=<on|off> rumble=<on|off> ports=<mask>` and SHALL log `[INPUT] t=<s> ports=<mask>` whenever the connected mask changes. Host-driven state changes SHALL be logged per port as `[INPUT] t=<s> host port=<n> buttons=<state>` in the same format as script changes, at most once per poll per port. The bench SHALL record these lines with the run.

#### Scenario: Sources line in a bench run
- **WHEN** a bench run finishes
- **THEN** `game-stdio.log` holds the `sources` line, and `run-info.txt` records `RECOMP_HOST_PAD` and `RECOMP_KEYBOARD` as they were set

### Requirement: Scripted and golden runs are isolated from host devices
Golden and integration runs (`blinx2 bench golden`, `blinx2 bench integrate`) SHALL set `RECOMP_HOST_PAD=0` and `RECOMP_KEYBOARD=0` and record them. With `RECOMP_INPUT_STRICT=1` a script that fails to parse, or names an unknown preset, SHALL end the run with a non-zero exit before the game starts; the bench SHALL set it. A tap step SHALL accept a period in polls (`every Np`) and an action a hold in polls (`BUTTON/Np`), so presets can avoid wall-clock time.

#### Scenario: Pad plugged into the bench
- **WHEN** `blinx2 bench golden` runs while a controller is connected to the Linux/Proton host
- **THEN** every scenario's `sources` line reports `host=off keyboard=off`, and the frames match the references as without the controller

#### Scenario: Bad preset in strict mode
- **WHEN** `RECOMP_INPUT_SCRIPT=@no-such RECOMP_INPUT_STRICT=1`
- **THEN** the host logs `[INPUT] unknown preset` and exits with status 2 before the guest entry point

#### Scenario: Poll-counted tap
- **WHEN** a script runs `tap A every 6p until mem 0xae73fc == 1`
- **THEN** successive A presses start exactly 6 port-0 polls apart in the `[INPUT]` log, independent of frame rate

### Requirement: Pad sampling is fresh
Host controllers SHALL be sampled synchronously inside the title's own poll (once per game frame, at frame start), with no host-side buffering or extra polling thread, so the state the title reads is never older than one host backend update. `RECOMP_INPUT_TRACE=1` SHALL log, per poll, the vblank count, the time since the last vblank tick, the host backend call time and the port mask, and SHALL print p50/p95 of the host call time at exit. The measured press-to-poll latency on Proton SHALL be at most one game frame plus one host backend update, and the host call SHALL take under 1 ms at p95 with four ports probed.

#### Scenario: Trace summary
- **WHEN** a run with `RECOMP_INPUT_TRACE=1` ends
- **THEN** stderr holds one trace line per poll and a summary with p50/p95 host call time and poll-to-vblank phase

#### Scenario: Latency measured with the virtual pad
- **WHEN** 50 START taps are sent from the virtual pad on the Linux/Proton host at recorded wall-clock times during a title screen
- **THEN** the `[INPUT] host` lines show a press-to-poll latency whose p95 is at most one game frame (33.4 ms at 30 Hz, 16.7 ms at 60 Hz) plus the host update interval, and every tap is seen
