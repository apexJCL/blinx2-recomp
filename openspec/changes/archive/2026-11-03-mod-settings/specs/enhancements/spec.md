## ADDED Requirements

### Requirement: Mods declare a static descriptor
The enhancements layer SHALL offer `XBOX_MOD_API_VERSION 3`. It SHALL add
an optional `desc` pointer at the end of `struct xbox_mod`, pointing to a
`const struct xbox_mod_desc`. The descriptor SHALL carry:
- `version` and `size`;
- title, summary, author and version text;
- typed settings;
- controls.

The layer SHALL read a descriptor before any `init` and only within its
`size`. A mod table without descriptors SHALL behave as under v2. A
descriptor that fails validation SHALL mark only that mod failed, with one
`[MOD]` line. Validation fails on any of:
- duplicate names or ids;
- `lo` greater than `hi`;
- an enum without choices;
- an unknown kind.

#### Scenario: Off mod still described
- **WHEN** cat runs with the menu on and `camera.free = "off"`
- **THEN** the free camera's detail page shows its title, summary, controls
  and settings

#### Scenario: v2 table
- **WHEN** a title registers a mod with no descriptor
- **THEN** its Mods row and sub-page are the ones 3D shows, and it runs
  unchanged

#### Scenario: Bad descriptor
- **WHEN** a descriptor declares two settings named `speed`
- **THEN** that mod's state is Failed with one `[MOD]` line, and the other
  mods and the game run

### Requirement: The layer owns mod settings
Each descriptor setting SHALL be bool, int, float or enum, with a default,
a range and step or its choices, help text and a live class. The live class
SHALL be one of:
- live;
- next activation;
- restart.

The layer SHALL resolve the value by this precedence, highest first:
1. the setting's env row;
2. the user file's key, then an alias in the user file;
3. the defaults file's key, then an alias in the defaults file;
4. the descriptor default.

A setting's key SHALL be its declared legacy key, or else the flat
`mods."<id>.<name>"`. The layer SHALL then clamp the value and snap it to
`step`, or fall back to the default for an unknown enum. Each adjustment
SHALL log one `[MOD]` line. Mods SHALL read the value through
`api->setting` without a lock. Changes from the menu SHALL reach
`on_setting` on the guest thread at the next mod frame. A restart-class
change SHALL only be recorded. No mod setting SHALL use the host-options
flush path.

At start, the layer SHALL print `[ENHANCE] <key>=<value>` for every
descriptor mod's enable setting, whether or not the mod is inited.

#### Scenario: Out of range
- **WHEN** `camera.free_speed = 50`
- **THEN** the camera uses 20 and the log has one
  `[MOD] camera.free.speed: 50 -> 20` line

#### Scenario: Live change
- **WHEN** the player changes Speed on the detail page while flying
- **THEN** the next frames fly at the new speed with no restart

#### Scenario: Stock enable line
- **WHEN** cat runs with no feature keys and the menu off
- **THEN** the free camera's `init` does not run, and the log still has
  `[ENHANCE] camera.free=off`

#### Scenario: Env-forced
- **WHEN** `RECOMP_CAMERA_FREE_SPEED=2` is set
- **THEN** the Speed row is greyed with "set by RECOMP_CAMERA_FREE_SPEED",
  and Save does not write it

### Requirement: Mod config keys survive edits
A mod's switch SHALL stay the flat `mods."<id>"` bool, default true, and
`false` SHALL keep the mod from being inited. A mod with an enable setting
SHALL show that setting as its Enabled row. Turning that row on SHALL also
remove a `mods."<id>" = false`.

A descriptor mod with its enable setting off SHALL be inited dormant only
when the menu is on and the enable setting is live-class; otherwise it
SHALL NOT be inited.

Aliases read from the user file SHALL be rewritten to the current key at
the next Save, even when nothing was edited. Aliases in the defaults file
SHALL NOT be rewritten.

Save, "Reset this mod" and "Reset all" SHALL NOT remove keys the layer does
not own:
- undeclared `mods."<id>..."` keys;
- undeclared `[input.controls]` keys;
- keys of mods missing from the build.

The unused-key report SHALL list those keys, including keys under a
descriptor mod that is off.

#### Scenario: Flat keys side by side
- **WHEN** a config has `[mods]` `"x" = true` and `"x.speed" = 2.0`, and
  mod `x` declares a setting `speed`
- **THEN** `x` is on with speed 2.0, and a Save of another change leaves
  both lines as they are

#### Scenario: Stale 3D switch
- **WHEN** a config has `[mods] "camera.free" = false` and
  `camera.free = "on"`
- **THEN** the free camera is not inited, its State reads
  "Off (mods."camera.free" = false)", and turning Enabled on and saving
  removes the `mods."camera.free"` line

#### Scenario: Live enable from the menu
- **WHEN** the menu is on, `camera.free = "off"`, and the player turns
  Enabled on
- **THEN** the camera was inited dormant at start, and F6 starts flight
  without a restart

#### Scenario: Unknown key kept
- **WHEN** a config has `[mods] "camera.free.colour" = "red"` and the
  player resets the free camera and saves
- **THEN** the line is still in the file, and the log lists it as unused

#### Scenario: Alias
- **WHEN** the user file has `camera.free_freeze_key = "F8"` and the player
  saves without editing anything
- **THEN** `camera.free.freeze` is bound to F8, and the file has
  `"camera.free.freeze" = ["F8"]` in `[input.actions]` and no
  `camera.free_freeze_key`

### Requirement: Mod controls are shown and rebindable
Descriptor controls SHALL be actions, captured buttons, captured sticks or
info rows. Actions SHALL be registered from the descriptor as
`<id>.<verb>`, owned by the mod, and a mod SHALL get their ids through
`api->control_action`. An action's env row, when set, SHALL replace its
bindings.

While the mod is off, its actions SHALL be dormant:
- they are listed and rebindable;
- they are conflict-checked and count in the "one input fires one action"
  resolution;
- they never fire, never consume input and never arm the actions hook.

Captured controls SHALL be bound in `[input.controls]` to guest buttons,
triggers or sticks, or to host keys. They SHALL be read through
`api->control_value` from port 0's guest state, which the layer records
after the consumed-chord mask and before the neutral pad. The layer SHALL
record it only while a mod holds input capture, and SHALL record whether
the port is connected. `xbox_InputGetState` SHALL record it whether or not
the pad filter is installed, and while a mod holds capture SHALL give the
guest a connected, released port 0 with a new packet number when the
neutral pad starts and ends.

Capture SHALL refuse:
- a binding another action owns, dormant ones included;
- a captured binding another captured control of the same mod uses;
- a captured key that is an action's single key, and an action binding on
  a key a captured control names;
- a host source with no guest slot for a captured control.

A captured single button SHALL coexist with an action chord that contains
it.

#### Scenario: Dormant action blocks a duplicate
- **WHEN** the free camera is off and the player binds F6 to `shot.window`
- **THEN** the capture is refused, and the footer reads "F6 is Free camera:
  Toggle flight"

#### Scenario: Stock run
- **WHEN** cat runs with no feature keys
- **THEN** the log has `[ENHANCE] actions hook=off`, no dormant action
  reads input, and no port-0 state is recorded

#### Scenario: Chord over a captured button
- **WHEN** the player is flying and presses Y
- **THEN** the camera sinks, and when the player holds Guide and presses Y,
  flight toggles off and the camera does not sink

#### Scenario: input_core title with the hook disarmed
- **WHEN** a title on input_core has a mod holding capture, no feature key
  arms the actions hook, and the player pushes the left stick
- **THEN** the mod reads the stick through `control_value`, and the guest
  reads port 0 connected and released

#### Scenario: Dormant default over a live default
- **WHEN** a dormant mod's action default and another action's default
  name the same input
- **THEN** the first registered keeps the input and one `[MOD]` line names
  both actions and the input

#### Scenario: Paddle refused for a fly control
- **WHEN** the player captures `paddle1` for `camera.free.rise`
- **THEN** the capture is refused with "fly controls take buttons the game
  sees"

#### Scenario: Remapped pad
- **WHEN** the player's pad mapping sends the host A button to the guest X
  button, and the player presses host A to capture `camera.free.rise`
- **THEN** the binding stored is `x`, and pressing host A raises the camera

### Requirement: Mods page detail view
Every row on the Mods page SHALL open a detail page with these rows:
- the title and version;
- Author;
- About, word-wrapped to the panel width;
- State;
- Enabled;
- a Controls section;
- a Settings section;
- "Reset this mod".

Each setting row SHALL show whether it applies live, at next activation or
at restart. Control rows SHALL list their bindings, the keys that reach the
same pad source through `[input.bindings]`, and their "when" note. The
footer SHALL show the selected row's help. A failed mod's page SHALL
still list its controls and settings, marked unavailable. The Controls page SHALL group
actions by owner under the owner's title. Metal and D3D11 SHALL draw the
page the same way.

#### Scenario: Help text
- **WHEN** the player selects the Speed row
- **THEN** the footer shows the setting's help text

#### Scenario: Restart-only setting
- **WHEN** a mod declares a restart-class setting and the player changes it
- **THEN** the row reads "applies at restart", and the mod's value is
  unchanged until the next start

### Requirement: The free camera declares its info, controls and settings
The cat free camera SHALL declare a descriptor with these parts.

**Actions:**

| action | defaults | alias | env |
|---|---|---|---|
| `camera.free.toggle` | `F6`, `guide+y` | `camera.free_toggle` | `RECOMP_CAMERA_FREE_TOGGLE` |
| `camera.free.hud` | `F7` | `camera.free_hud_key` | `RECOMP_CAMERA_FREE_HUD_KEY` |
| `camera.free.freeze` | `End` | `camera.free_freeze_key` | `RECOMP_CAMERA_FREE_FREEZE_KEY` |
| `camera.free.reset` | `Home` | `camera.free_reset_key` | `RECOMP_CAMERA_FREE_RESET_KEY` |

**Captured controls** (in `[input.controls]`):

| control | kind | defaults |
|---|---|---|
| `move` | stick | `left_stick` |
| `look` | stick | `right_stick` |
| `rise` | button | `rt`, `x` |
| `sink` | button | `lt`, `y` |
| `fast` | button | `white` |
| `slow` | button | `black` |
| mouse look | info | none |

**Settings:**

| setting | type | values | applies |
|---|---|---|---|
| `camera.free` | enable | off/on | live |
| `camera.free_speed` | float | 0.05..20, default 1 | live |
| `camera.free_look_sens` | float | 0.05..10, default 1 | live |
| `camera.free_mouse_sens` | float | 0.05..10, default 1 | live |
| `camera.free_invert_x` | bool | default false | live |
| `camera.free_invert_y` | bool | default false | live |
| `camera.free_fast` | float | 1..20, default 4 | live |
| `camera.free_slow` | float | 0.05..1, default 0.25 | live |
| `camera.free_hud` | enum | keep/hide | next activation |

With the default bindings and settings it SHALL fly exactly as before,
each stick with its own dead zone. The toolkit SHALL print the `[ENHANCE] camera.free=on|off`
line with today's text.

#### Scenario: Invert
- **WHEN** `camera.free_invert_y = true` and the player pushes the right
  stick up while flying
- **THEN** the camera pitches down, and mouse motion is inverted the same
  way

#### Scenario: Fast multiplier
- **WHEN** `camera.free_fast = 8` and the player holds White while flying
- **THEN** the camera moves at 8 times its normal speed, and with the
  default 4 it moves as it does today

#### Scenario: Mouse sensitivity alone
- **WHEN** `camera.free_mouse_sens = 2` and `camera.free_look_sens = 1`
- **THEN** mouse look turns twice as fast as today and stick look is
  unchanged

#### Scenario: Rebound rise
- **WHEN** the player binds `camera.free.rise` to Space on the detail page
  and flies
- **THEN** Space raises the camera, and the guest receives the neutral pad

#### Scenario: Off from the menu mid-flight
- **WHEN** the player turns Enabled off on the detail page while flying
- **THEN** at the next frame the game camera is restored, freeze is
  dropped and the HUD is shown

### Requirement: Mods expose every sensible setting
A mod with a descriptor SHALL expose as a setting every value it holds
that a player could sensibly want to change. Each value kept as a
constant SHALL have a recorded reason: another setting covers it, the
toolkit owns it for every input, it keeps the game or the maths correct,
or it is a game fact or a diagnostic.

#### Scenario: Free camera audit
- **WHEN** a reviewer reads the free camera's descriptor
- **THEN** a comment above its settings table lists each constant left
  out (the stick dead zones, the pitch limit, the frame-time cap, the
  trigger threshold, roll, FOV, the freeze rules) with its reason

### Requirement: Descriptor dump
With `RECOMP_MODS_DESCRIBE=json` the toolkit SHALL write every registered
mod's descriptor and resolved values as JSON (schema 1), then exit 0
before the game starts. It SHALL run no mod `init` and arm nothing. With
`RECOMP_MODS_DESCRIBE_OUT=<path>` it SHALL write the JSON to that file,
otherwise to stdout. Each setting and binding SHALL carry its value and
the precedence source that won. Each mod SHALL carry what the init rule
would do. Later versions SHALL only add fields unless they bump `schema`.

#### Scenario: Stock dump
- **WHEN** cat runs with `RECOMP_MODS_DESCRIBE=json` and no config
- **THEN** stdout holds one JSON document listing `camera.free` with
  `"init": "no"`, every setting at its default with `"source": "default"`,
  and its 11 controls, and the process exits 0 without a window

#### Scenario: Env-forced value in the dump
- **WHEN** `RECOMP_CAMERA_FREE_SPEED=3` and the dump is requested
- **THEN** the `speed` setting reads `"value": 3` and `"source": "env"`

#### Scenario: Dump to a file
- **WHEN** `RECOMP_MODS_DESCRIBE_OUT` names a writable path
- **THEN** the JSON is written there, replacing the file, and nothing is
  written to stdout; an unwritable path logs one `[MOD]` line and exits 1
