## MODIFIED Requirements

### Requirement: The title's XInput entry points are overridden
`src/recomp_manual.c` SHALL define the seven XDK XInput entry points the title calls (`XGetDevices` `0x00367EEC`, `XGetDeviceChanges` `0x00367F0E`, `XInputOpen` `0x0036821D`, `XInputClose` `0x00368273`, `XInputGetCapabilities` `0x0036827F`, `XInputGetState` `0x00368457`, `XInputSetState` `0x003684CA`), with the guest's stdcall stack contract. For `XDEVICE_TYPE_GAMEPAD` (`0x00366B90`) each of the four ports SHALL be reported as inserted exactly while it has a source (a script on port 0, a host controller the backend has open, or the keyboard and mouse on port 0), and removed when the source goes away; the insert and remove masks of `XGetDeviceChanges` SHALL follow those transitions. The XInput backend (Windows and Proton) probes its slots, and the SDL backend opens and closes controllers as the host connects and disconnects them ("Hot-plugging follows the host"), so on every host a controller connected later becomes a source and a removed one stops being one. No port SHALL be reported as inserted without a source. `XInputGetCapabilities` SHALL describe a Duke-class gamepad (subtype gamepad, all eight digital buttons, eight analog buttons, four stick axes, two rumble motors). `XInputGetState` on a port without a source SHALL return `ERROR_DEVICE_NOT_CONNECTED`. `XInputSetState` SHALL complete synchronously (`dwStatus = 0`), because the title busy-waits on `ERROR_IO_PENDING`. Other device types (memory units, `0x00366B10`) SHALL keep the library's semantics on the guest device-type struct and report nothing inserted.

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

## ADDED Requirements

### Requirement: Hot-plugging follows the host
A host controller connected or disconnected while the title runs SHALL change the connected-port mask, and the title's `XGetDeviceChanges` insert or remove mask, within a second, on every host. A port with no controller SHALL be asked at most once a second. On SDL hosts (macOS, native Linux) the toolkit's SDL backend SHALL:
- open a controller the host adds and close one it removes, with or without a window pumping SDL events (SDL device events, plus a rescan at most once a second);
- keep a controller on its port while it stays attached; ports SHALL never shift, so player 1 keeps port 0 while other pads come and go;
- free the port of a removed controller; `XInputGetState` on that port SHALL return `ERROR_DEVICE_NOT_CONNECTED` from the next read;
- give a new controller the port the same model (joystick GUID) last held when that port is free and another controller is still connected, else the lowest free port, so a controller that connects while no other is connected takes port 0 and a pad pulled and replugged comes back as the same player where the GUIDs tell the pads apart;
- leave a fifth controller unopened until a port frees up;
- log `[INPUT] host pad added port=<n> "<name>"` and `[INPUT] host pad removed port=<n>` once per change, beside the `[INPUT] t=<s> ports=<mask>` line of "Input sources are logged".

A controller connected before launch SHALL be open at the title's first read, so its port is connected from the first `ports` line; the first poll SHALL wait at most 250 ms for the window's loop to open it, never longer.

The game's poll threads read the controllers while the window thread pumps SDL; opening and closing SHALL be serialized with those reads so a poll never touches a closed controller, and device enumeration SHALL run only on the thread that pumps SDL.

#### Scenario: Virtual pads attached and detached (ctest)
- **WHEN** `tests/input_hotplug_sdl` attaches SDL virtual game controllers A then B, detaches A, attaches C, detaches B, and detaches C, with no window
- **THEN** the masks read 0x1, 0x3, 0x2, 0x3, 0x1, 0x0 with insert masks 0x1, 0x2, -, 0x1, -, - and remove masks -, -, 0x1, -, 0x2, 0x1; A is on port 0, B on port 1 throughout, C takes port 0; port 0 returns `ERROR_DEVICE_NOT_CONNECTED` on the first read after A is detached

#### Scenario: A replugged model keeps its port
- **WHEN** pads of three models P, Q, X sit on ports 0, 1, 2, Q and P are detached, and Q then P are attached again
- **THEN** Q returns to port 1 (not the lower free port 0) and P to port 0

#### Scenario: Boot with a pad attached (ctest)
- **WHEN** `tests/input_hotplug_sdl` attaches a virtual controller, then a guest thread makes the first XInput call while the test's thread runs the window's pad sync every 5 ms
- **THEN** port 0 reads connected at that first call, within 200 ms, and a second later no insert is reported; and with no window loop running the first call returns after 200-1000 ms with no port connected

#### Scenario: A pad connected before launch on the Mac
- **WHEN** the title is started on macOS with `RECOMP_HOST_PAD=1` and one controller already connected
- **THEN** the log shows `[INPUT] host pad added port=0` and the first `[INPUT] t=<s> ports=` line reads `ports=0x1`, with no later insert, and the pad drives the title from the first menu

#### Scenario: Unplug and replug a pad on the Mac
- **WHEN** the title runs on macOS with `RECOMP_HOST_PAD=1`, one controller connected, and the controller is unplugged in a menu and plugged in again
- **THEN** the log shows `[INPUT] host pad removed port=0` and `[INPUT] t=<s> ports=0x0` within a second of the unplug, then `[INPUT] host pad added port=0` and `ports=0x1` within a second of the replug, and the menu responds to the pad again

#### Scenario: A pad connected after launch on the Mac
- **WHEN** the title is started on macOS with `RECOMP_HOST_PAD=1` and no controller, and a controller is connected on the title screen
- **THEN** `ports=0x1` is logged within a second and START on the pad advances the title
