## ADDED Requirements

### Requirement: Configurable pad map on upstream's model
The toolkit SHALL map host pad sources to guest Duke controls with upstream #203's `InputRaw`, `InputPadMap` and `xbox_InputMap_PadMap`, configured by `[input.pad]`. `[input.pad]` SHALL use the layering and per-control resolution of `[input.bindings]`. With no `[input.pad]` in any file, the result SHALL equal the fork's previous fixed table: White = LB, Black = RB, no deadzone, no trigger threshold, and raw sticks. A stick whose deadzone is 0 SHALL be passed raw, not through #203's radial rescale.

#### Scenario: No file means the identity
- **WHEN** the runtime starts with `RECOMP_CONFIG=none`
- **THEN** every host pad state maps to the same Duke state as the fork's `xbox_InputMapXInput` and `xbox_InputMapSdl` give, for all 256 trigger values and the stick extremes

#### Scenario: A full diagonal stays a full diagonal
- **WHEN** a host stick reads `(32767, 32767)` or `-32768` on an axis, with no deadzone set
- **THEN** the guest stick reads the same values, not a value clamped to the unit circle

#### Scenario: Stock polling is unchanged
- **WHEN** no pad filter is installed and the map is the identity on the XInput backend
- **THEN** the backend calls `XInputGetState`, not `XInputGetStateEx`

#### Scenario: A player rebinds one control
- **WHEN** the player's file has `x = "lb"` and the defaults have `white = "lb"`
- **THEN** LB drives X, and White is driven by nothing from LB

#### Scenario: Two bindings on one control
- **WHEN** `x = ["west", "paddle3"]` is set
- **THEN** either source presses X, merged by `xbox_InputMap_PadMerge`

#### Scenario: Unbind
- **WHEN** a control is bound to `[]`
- **THEN** no host pad source drives that control

### Requirement: Host actions use physical sources
Pad bindings in `[input.actions]` SHALL name host sources, which are read from `InputRaw` before the map. A single source SHALL be active as an action binding only while no map gives it to a guest control. A chord's kind SHALL be derived from the current map at every rebuild, independent of the order its members are written in. A chord member written as a guest control name SHALL mean the source the identity gives it; the old spellings SHALL NOT be read.

#### Scenario: A freed button opens the menu
- **WHEN** `[input.pad]` has `back = []` and `[input.actions]` has `menu.open = "back"`
- **THEN** pressing Back opens the menu, and the game never sees Back

#### Scenario: A mapped button is refused
- **WHEN** `menu.open = "a"` is set and `a` drives the guest's A
- **THEN** the binding is inactive with a warning, and the other bindings stay

#### Scenario: A fallback chord survives a remap
- **WHEN** `menu.open` includes `back+left_thumb@400` and the player unmaps `left_thumb` but keeps Back mapped
- **THEN** the chord stays valid as a modifier chord with L3 pressed first, and one log line names the new kind and the press order

#### Scenario: A chord whose members all become mapped
- **WHEN** `menu.open` includes `guide+a` and the player maps `guide` to a guest control
- **THEN** `guide+a` goes inactive with a warning, because it has no hold of 200 ms or more

### Requirement: Default overlay bindings
`menu.open` SHALL default to `F10`, `guide+a` and `paddle1`. A game MAY add a chord in its `config.default.toml`.

#### Scenario: Deck R4 without Steam Input
- **WHEN** the native SDL3 build runs on the Deck with Steam Input off, and R4 is pressed
- **THEN** the menu opens

### Requirement: Controller family
The toolkit SHALL report a family per slot (`xbox`, `playstation`, `nintendo`, `steam`, `generic`), and `input.glyphs` SHALL override it. Under XInput the family SHALL be `xbox`.

#### Scenario: A DualSense on macOS
- **WHEN** a DualSense is connected on the SDL3 backend
- **THEN** its slot reports `playstation`, and the Controls page shows PlayStation glyphs

### Requirement: Steam Input detection is not a vendor check
On SDL hosts, Steam Input SHALL be reported `on` only for a pad with a Steam handle or the VID:PID 28de:11ff. Under Proton it SHALL be reported only as `maybe`, from Steam's variables read through `recomp_env`.

#### Scenario: Deck built-in pad with Steam Input off
- **WHEN** the native build sees the Deck's own pad (28de:1205) with no Steam handle
- **THEN** Steam Input is not reported, and the Pad group shows no Steam line

#### Scenario: Deck under Proton
- **WHEN** the game runs under Proton with `SteamDeck=1`
- **THEN** the Pad group shows "Steam may apply its layout first"

### Requirement: The Controls page remaps without lockout
The overlay's Controls page SHALL capture pad, keyboard and action bindings by press, apply them live and save only differences. Menu navigation SHALL use fixed raw inputs that no remap changes. A change SHALL be refused, live and at Save, when it would leave `menu.open` with no binding that the host can deliver.

#### Scenario: The confirm press is not captured
- **WHEN** the player confirms a cell with A to capture
- **THEN** capture arms only after A is released, and takes the next single input on its release

#### Scenario: Back stays bindable
- **WHEN** the player presses and releases Back during capture
- **THEN** Back is captured. Holding Start and Back together for 1 s cancels instead

#### Scenario: Cross-group conflict
- **WHEN** the player maps `paddle1` to a guest control while `menu.open` uses `paddle1`
- **THEN** the page prompts and names the `menu.open` bindings that remain

#### Scenario: Start+Back is the cancel, not a chord
- **WHEN** the player holds exactly Start and Back during capture in Host actions
- **THEN** no chord is captured at 400 ms, and capture cancels at 1 s

#### Scenario: Proton without a keyboard
- **WHEN** Steam Input is `maybe`, no keyboard has been seen, and the game's fallback chord is the last active pad binding of `menu.open`
- **THEN** a remap that would deactivate that chord is refused, even though F10 is bound

#### Scenario: Deck without a keyboard
- **WHEN** no keyboard has been seen, Steam Input is off, and `paddle1` is `menu.open`'s only deliverable binding
- **THEN** mapping `paddle1` to a guest control is refused, with the reason shown in the row

#### Scenario: Remapping does not trap the player
- **WHEN** every face button has been remapped
- **THEN** the south and east host buttons still confirm and go back in the menu

### Requirement: Optional SDL3 backend on Windows
The Windows build SHALL read pads through XInput by default. `input.backend = "sdl"` SHALL load `SDL3.dll` at run time, and SHALL fall back to XInput with a log line when the DLL is missing.

#### Scenario: Missing DLL
- **WHEN** `input.backend = "sdl"` is set and no `SDL3.dll` is beside the exe
- **THEN** pads read through XInput, and one log line says so
