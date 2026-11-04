## MODIFIED Requirements

### Requirement: A host pad can drive the pad
Host controllers SHALL be a source for the pad when the host pad is enabled. Enablement: with no `RECOMP_INPUT_SCRIPT`, the host pad is on by default on Windows and Proton (XInput); elsewhere (SDL2 GameController) it is on with `RECOMP_HOST_PAD=1`, which the macOS app's launcher sets; with a script set, it is off unless `RECOMP_HOST_PAD=1` is given explicitly; `RECOMP_HOST_PAD=0` SHALL always disable host controllers, and nothing else: the keyboard and the mouse SHALL NOT depend on the host pad being enabled (they are governed by `input.keyboard` and `input.mouse`, below).

Host controllers SHALL reach the ports in the order they come up, not by their host slot (XInput user index or SDL slot), through one slot-to-port map; the host slot SHALL serve only as the controller's identity (the SDL backend gives a replugged model its old slot). A controller that comes up SHALL drive the port its slot last drove when that port is free and another host controller drives a port, and otherwise the lowest port no other host controller drives; controllers that come up together SHALL be assigned in slot order, and a controller SHALL keep its port until it goes away, so plugging one in or out never moves another player and ports never shift. Controllers filling the slots from 0 in order therefore drive port N from slot N, a controller pulled and replugged comes back on its port, and a lone controller on any slot drives port 0, where the title reads player 1.

A controller that has never shown input SHALL give up its port to the first controller on a higher port that does. Input is a digital button, or an analog button above 30; the sticks SHALL NOT count. When a controller first shows input, it SHALL swap ports with the controller on the lowest port held by one that never has, if that port is lower than its own; controllers whose first input falls in the same poll SHALL be handled in slot order. The swap SHALL NOT change the connected mask: the title sees no remove or insert. A controller that has shown input SHALL never be moved while it stays connected, and a controller that goes away SHALL count as never active when it comes back. While any controller holding a port has never shown input, the host SHALL read every such controller on each poll of port 0, and on each poll of any port while port 0 has no source, whether or not the title polls its port, so a controller played alone is marked before a second one can take its port; once every controller has shown input, nothing extra is read.

The keyboard and mouse, when either is on, SHALL be read once per poll of port 0 and at no other time, whichever host slot drives port 0, since the read consumes the mouse motion. When a port has both a script and a host source, buttons SHALL be OR-ed, analog values SHALL take the larger, and a stick axis the script leaves at zero SHALL take the host's value. On port 0 a host controller and the keyboard-and-mouse source SHALL be merged the same way, a non-zero keyboard or mouse axis replacing the controller's for that poll.

#### Scenario: Proton with a real controller
- **WHEN** the title runs under Proton with one controller connected, Steam Input off for the game (`PROTON_NO_STEAMINPUT=1`) and no script
- **THEN** the `[INPUT] sources` line reports `host=on ports=0x1 pads=0:0`, and pressing START on the title advances to the story opening (R0_opening.sfd opens; title state 0x5EB620 leaves 0)

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
- **THEN** the `[INPUT] sources` line reports `host=off keyboard=on ports=0x1 pads=none` and keys drive port 0

#### Scenario: Pad and mouse together
- **WHEN** a controller drives port 0 with its right stick at rest and the mouse is moved during one game frame
- **THEN** that poll's `sThumbRX`/`sThumbRY` are the mouse's values, and the next poll with the mouse at rest reads the controller's stick again

#### Scenario: Lone controller on a non-zero slot
- **WHEN** the title runs with one controller that the host reports on slot 1 and nothing on slot 0
- **THEN** the `[INPUT] sources` line reports `ports=0x1 pads=1:0`, and its buttons appear as `host port=0` and drive player 1

#### Scenario: Steam's inert pad on slot 0
- **WHEN** the title runs under Proton with Steam Input on, Steam's virtual pad on slot 0 and the real controller on slot 1 (`sources ... ports=0x3 pads=0:0,1:1`), and a button is pressed on the real controller
- **THEN** the log shows `[INPUT] t=<s> pads=0:1,1:0 active=0x2`, no `ports=` line follows, and the controller's buttons appear as `host port=0` from that poll on and drive player 1

#### Scenario: A pressed controller keeps its port
- **WHEN** two controllers drive ports 0 and 1 and the one on port 0 was pressed first
- **THEN** pressing the controller on port 1 moves nothing, and no `active=` line is logged

#### Scenario: A controller pressed while alone keeps port 0
- **WHEN** one controller drives port 0 alone and is pressed, then a second controller comes up on another port and is pressed
- **THEN** no `active=` line is logged, and the first controller keeps port 0

#### Scenario: Keyboard with a controller on port 1 from slot 0
- **WHEN** the keyboard is on, a controller on slot 1 drives port 0, and a controller on slot 0 drives port 1
- **THEN** keys drive port 0 only, and each poll of port 0 reads the keyboard and mouse exactly once

#### Scenario: Controller added below a held one
- **WHEN** a controller on slot 1 drives port 0 and a second controller comes up on slot 0
- **THEN** the log shows `[INPUT] t=<s> pads=0:1,1:0`, the first controller keeps port 0, and the new one drives port 1

#### Scenario: A replugged controller keeps its port
- **WHEN** three controllers drive ports 0, 1 and 2, the ones on ports 0 and 1 are unplugged, and the one from port 1 is plugged in again first
- **THEN** it drives port 1 again, not port 0, and the one from port 0, plugged in after it, drives port 0

#### Scenario: A controller alone after a replug is player 1
- **WHEN** every controller is unplugged and one that drove port 1 is plugged in again
- **THEN** it drives port 0

#### Scenario: A controller pressed while port 0 is empty
- **WHEN** controllers drive ports 0 and 1 and neither has been pressed, the keyboard and the script are off, the one on port 0 is unplugged, the one on port 1 is pressed, and then the first is plugged in again
- **THEN** the first drives port 0 again, and pressing the second moves nothing

#### Scenario: Slot mapping unit test
- **WHEN** `scripts/test_pad_slots.py` runs
- **THEN** it passes: slot 0 alone maps to port 0, slots filled from 0 map to themselves, a lone slot 1 or 3 maps to port 0, an unplug frees only its own port and forgets that slot's activity, freed ports are refilled lowest first, a first press takes the lowest port held by a never-active controller without changing the port mask, a controller once active is never moved, a controller pressed while alone keeps port 0 when a second comes up and is pressed, a replugged slot takes its old port back when it is free and another controller is up (also after a first-press swap), a slot that comes up alone takes port 0, and first presses in one poll are handled in slot order

#### Scenario: Toolkit pad-only read
- **WHEN** the toolkit's `input_map` ctest runs
- **THEN** it passes: `xbox_InputGetPadState` never reads the keyboard and answers `ERROR_DEVICE_NOT_CONNECTED` for an empty slot under the same backoff as `xbox_InputGetState`, `xbox_InputGetState(0)` reads the keyboard exactly once and `xbox_InputGetState(1)` never, and `xbox_InputMergeKbm` gives the state `xbox_InputGetState(0)` gives

### Requirement: Rumble reaches the host controller
`XInputSetState` motor speeds (0..65535 per motor) SHALL be forwarded to the host controller driving that port when the host pad is enabled and that port has a host device. When a first press swaps two controllers' ports, both controllers' motors SHALL be set to zero, so a rumble does not stay on the controller that left the port; the title's per-frame resend restarts it on the controller now driving the port. `RECOMP_RUMBLE=0` SHALL disable forwarding. All motors SHALL be set to zero when the process exits or the host pad is shut down.

#### Scenario: Rumble on a hit
- **WHEN** Stick takes a hit in stage 1-1 with a real controller
- **THEN** the controller vibrates, and the `[INPUT]` trace (when enabled) shows the two motor values the title set

#### Scenario: Rumble on a scripted run
- **WHEN** a scripted run with the host pad off reaches the same hit
- **THEN** no host rumble call is made and the title's feedback status still reads complete

### Requirement: Input sources are logged
At start the host SHALL log one line `[INPUT] sources: script=<name|off> host=<on|off> keyboard=<on|off> mouse=<on|off> rumble=<on|off> ports=<mask> pads=<map>`, where `<map>` lists each host controller as `slot:port` in slot order or reads `none`. It SHALL log `[INPUT] t=<s> ports=<mask>` whenever the connected mask changes, `[INPUT] t=<s> pads=<map>` whenever a host controller takes or gives up a port, and `[INPUT] t=<s> pads=<map> active=<slot mask>` whenever a first press moves a controller, where `<slot mask>` lists every controller that has shown input; a first press that moves nothing SHALL NOT be logged. Host-driven state changes SHALL be logged per port as `[INPUT] t=<s> host port=<n> buttons=<state>` in the same format as script changes, at most once per poll per port, where `<n>` is the title's port, not the host slot. The bench SHALL record these lines with the run.

#### Scenario: Sources line in a bench run
- **WHEN** a bench run finishes
- **THEN** `game-stdio.log` holds the `sources` line, and `run-info.txt` records `RECOMP_HOST_PAD` and `RECOMP_KEYBOARD` as they were set
