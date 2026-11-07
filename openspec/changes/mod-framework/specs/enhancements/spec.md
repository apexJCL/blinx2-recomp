## ADDED Requirements

### Requirement: Mods have a documented contract and layout
The toolkit SHALL document the mod API's contract, its calls and how a mod reaches the game in `docs/runtime/mods.md`, and how to write a mod in `docs/runtime/mod-howto.md`. A new mod in a game repo SHALL live in `src/mods/`, with logic that needs no guest access in a separately tested file. A mod SHALL declare its title, settings and controls in its descriptor, and SHALL guard its build to the newest API member it uses, returning a NULL accessor below that.

#### Scenario: Below the guard
- **WHEN** a mod guarded at API N is built against a toolkit below N
- **THEN** its accessor returns NULL, the game builds, and the game runs without that mod

#### Scenario: Stock
- **WHEN** a game with mods runs with no mod setting in its config
- **THEN** the log prints `[ENHANCE] mods=none`, unless a default-on mod is doing something the stock configuration asks for

### Requirement: A mod reaches the game through the documented order
A new mod SHALL reach game code through, in order of preference: a frame callback with guest memory, a hook slot declared in `game.toml [mods] hook_functions`, the HUD table, a guest call. A C wrapper in the game's manual file SHALL be used only where none of these fits, SHALL keep to a call into the mod's file, and SHALL say in a comment why a hook doesn't fit.

#### Scenario: A function a mod hooks
- **WHEN** a mod with a hook is off or dormant
- **THEN** its callbacks are not called and the function runs as the game's own code

#### Scenario: A hook entry that no longer holds
- **WHEN** a game regenerates and a `hook_functions` entry is no longer a function start
- **THEN** `analyze` fails and names the entry

### Requirement: A template mod builds with the toolkit
The toolkit SHALL carry a game-agnostic template mod in `templates/mod/`, off by default, and a standalone ctest SHALL build that exact file and run it through `xbox_enhance_init`.

#### Scenario: Off
- **WHEN** the template is registered with no key set
- **THEN** the log prints `mods=none`, its init logs nothing, and it shows no panel

#### Scenario: On
- **WHEN** the user file sets `"demo.enable" = true`
- **THEN** the mod is listed on the `mods=` line and shows its panel by the first frame

#### Scenario: Menu toggle
- **WHEN** the mod is dormant with the menu on and the Mods page turns it on, then off
- **THEN** the panel appears from the next frame, and is gone once it is off

#### Scenario: Setting out of range
- **WHEN** a user file sets `"demo.interval"` above its `hi`
- **THEN** the value is clamped, with one `[MOD]` line naming the change
