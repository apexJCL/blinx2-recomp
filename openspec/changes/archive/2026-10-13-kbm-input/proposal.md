# Change: Keyboard and mouse input, with the mapping in the config file

Tracker BLX-96, required for v1.0 (epic BLX-99). Spec first: the operator
tunes the default mapping in this document, then implementation starts.

## Why

A player without a controller cannot play the game well today, and a
player with one cannot change a single key:

- **The keyboard is digital and fixed in C.** `toolkit:src/input/keyboard.c`
  holds one table (arrows d-pad, Enter START, Z X C V = A B X Y, Q E =
  White Black, 1 3 = triggers, W/S/A/D the left stick, I/K/J/L the right
  stick). A stick key is full deflection or nothing. Nothing can be rebound
  without recompiling; the bundle READMEs print the table as a fact of
  life.
- **There is no mouse.** `input-real-devices` D9 and the parked
  `input-selection` spike both wrote "the title has no pointer" and built
  nothing. That is true of the title and beside the point for the player:
  BLiNX 2 is a third-person platformer whose camera is the right stick
  ("Move the Right thumbstick to look at the 3 balloons around you", the
  hub drill), and on a PC the camera stick is the mouse. The operator asked
  on 2026-10-11 that keyboard support "must be keyboard and mouse" and that
  "the mapping itself could be a part of the config file".
- **The keyboard needs the host pad on.** `cat:src/pad_input.c:880`
  `keyboard_on()` is `g_host_on && RECOMP_KEYBOARD`, so on a Mac
  developer build (`RECOMP_HOST_PAD` off by default) `RECOMP_KEYBOARD=1`
  alone does nothing, and `RECOMP_HOST_PAD=0`, meant to keep host pads
  out of a run, also silences the keyboard.
- **The switch lives in `launch.env`, not in the config file.** The
  bundles turn the keyboard on with `RECOMP_KEYBOARD=1` in
  `launch.env.default` (Windows, macOS; steamos through the same
  mechanism). Since `config-layering` (BLX-74) the player's settings live
  in `config/config.toml` over the shipped `config.default.toml`, with the
  environment on top; an input switch set from `launch.env` cannot be
  turned off from `config.toml`, and a key layout cannot live in an
  environment variable at all.

## What Changes

- **Keyboard and mouse are one port-0 source on every host**: the SDL
  window on macOS and Linux, the D3D11 window under Proton (the Deck,
  the Linux/Proton host) and the GDI window, through the key table that
  `input-real-devices` 4.x already feeds from all three, plus a mouse
  state fed the same way. The source no longer depends on `RECOMP_HOST_PAD`.
- **The mouse drives a stick** (the right stick, the camera, by default):
  relative motion accumulated between the title's polls becomes a
  deflection, with `input.mouse_sensitivity`, `input.mouse_invert_y`,
  `input.mouse_invert_x` and a minimum deflection that clears the title's
  own 0.4 stick deadzone. Mouse buttons and the wheel bind like keys. The
  cursor is captured (hidden, relative) whenever the game window has
  focus, released on focus loss or when the enhancements menu opens, and
  `F9` toggles it free and back (the operator, 2026-10-11).
- **The mapping lives in the configuration files**: an `[input]` table and
  an `[input.bindings]` table in `config.default.toml` (shipped, tuned by
  the operator) and `config/config.toml` (the player's differences), read
  through the existing layering (env > title file > user file > defaults
  > code). A binding names a Duke control and lists the keys and mouse
  inputs that drive it. Unknown names, duplicates and type errors are
  reported with file and line and never fatal.
- **A default layout for WASD plus mouse**, fixed by the operator on
  2026-10-11 (design D5): W/A/S/D move, the mouse looks, `Space` = A,
  the left mouse button or `R` = the right trigger, the right button or
  `F` = B, `E` = X (revised 2026-10-12; `R` and `F` added 2026-10-13), `Q` `C` `Z` = Y, White, Black, `LShift` = the
  left trigger, the middle button = the right stick
  click, `Return`/`Escape` = START; a short ramp plus a walk modifier give
  the stick keys usable analog movement. The toolkit's compiled-in table
  (upstream's behaviour when no config layer is present) does not
  change.
- **Enablement**: code defaults keep the keyboard off and the mouse off
  (upstream parity, goldens unaffected); the game's `config.default.toml`
  turns both on (design D2, which argues why this is not an opt-in
  enhancement). `RECOMP_KEYBOARD` keeps its meaning and binds
  `input.keyboard`; new `RECOMP_MOUSE` binds `input.mouse`; a scripted run
  keeps both off unless the environment says otherwise. The launchers stop
  setting `RECOMP_KEYBOARD=1`, so `config.toml` can turn it off.
- **Tests**: a toolkit ctest for the names, the bindings resolver, the key
  composer and the mouse model (`tests/input_bindings`), the `[input]`
  layering and error lines in `tests/enhance_cfg`, SDL mouse events in
  `tests/input_keyboard_sdl`, and an unattended scripted input run through
  a new debug key `RECOMP_DEBUG=kbm_script=<file>` that injects key and
  mouse events into the same tables the windows write, so a headless Mac
  run and a Proton bench run prove the whole path to the title's pad
  struct without a person at the machine.

## Relation to other changes

- **`input-real-devices`** (open; its 4.x keyboard work is merged) ADDs the
  `input` requirement "The keyboard can stand in for a pad on port 0". This
  change supersedes that requirement (the map moves to the config file, the
  host-pad coupling goes, the mouse joins). Archive order:
  `input-real-devices` first; before this change archives, its `input`
  delta gains a `REMOVED` section for that requirement (task 7.4), which
  cannot be written today because the main spec does not hold it yet.
- **The parked `input-selection` spike** (cat `spike/input-selection`
  e09b325, deferred to the very end, BLX-26) proposed per-port source
  selection, pad pinning by GUID, pad remapping, a WASD layout with ramps,
  an `input.ini` bindings file and SDL hot-plug. This change takes the
  parts v1.0 needs and places them where the project now keeps such
  things: the layout and ramps (spike D5) and the bindings file (spike D6,
  as `[input]` tables in the TOML config layer instead of a flat
  `input.ini`, since `config-layering` landed). It does **not** fold in
  per-port source selection, GUID pins or pad remapping (spike D2, D8),
  which stay parked, and hot-plug now belongs to `sdl3-migration` D8
  (BLX-78, BLX-15). When the spike is picked up it starts from a smaller
  scope and the vocabulary this change fixes (control names, key names).
- **`enhance-menu-preview`** D4 reads the menu hotkey through
  `xbox_FramebufferKeyDown(vk)`; the VK table stays, so nothing there
  changes. Its phase 3 calls the one new API this change adds for it,
  `xbox_InputMouseSuspend(int)`, so the cursor is free while the menu is
  open (task 7.3 hands it over). `F10` stays the menu's key and bindings
  that use it are warned about.
- **`sdl3-migration`** (BLX-78) renames the SDL event fields and the
  relative-mouse call; the mouse feeder lives in one new file,
  `mouse_sdl.c`, so whichever branch merges second ports one file.
- **`config-layering`** supplies the files, the precedence, the error
  reporting and `enhance_cfg_file(i)` for prefix scans; nothing there
  changes. **`enhancements`** spec: `[input]` keys are not frame-affecting
  and `golden.py`'s stock check does not learn them; the `[ENHANCE]` lines
  gain nothing.

## Capabilities

### Modified Capabilities
- `input`: keyboard and mouse as a configurable port-0 source on every
  host, the mouse as a stick, capture rules, the binding vocabulary, the
  error rules, the scripted injection; the host-pad requirement loses its
  keyboard coupling.
- `deployment`: the packaged bundles enable the keyboard and mouse through
  `config.default.toml`, not `launch.env`.
- `deviations`: a new entry for keyboard and mouse as a Duke on port 0
  (ramped digital sticks, mouse as a stick, pressure-less buttons).

## Impact

- **Hosts and backends.** Every host that has a window: macOS (SDL, Metal
  and CPU present), Linux native (SDL), Windows under Proton (D3D11 and
  GDI windows). The render backends themselves do not change; input is
  read on the guest's poll thread as today. Headless runs have no window
  and so no keys or mouse, except through `kbm_script`.
- **Goldens.** None moves: `golden.json` pins `RECOMP_CONFIG=none`,
  `RECOMP_HOST_PAD=0`, `RECOMP_KEYBOARD=0` and gains `RECOMP_MOUSE=0`;
  Metal (Mac) and D3D11 (Proton) goldens are run to show it.
- **Toolkit** (`posix-host/portability`, upstream-bound where noted):
  `src/input/keyboard.c` (binding table, composer, ramps), new
  `src/input/mouse.c` (state, model) and `src/input/input_names.c` (the
  vocabulary), `keyboard_sdl.c` and new `mouse_sdl.c` (fork-only, the SDL
  window is fork-only), `fb_present.c` and `nv2a_pb_d3d11.c` (Win32 mouse
  feeder; upstream has both windows), `input_core.c` (enable overrides),
  `src/enhance/enhance_input.c` (new; reads `[input]`, upstream-neutral
  like the rest of the layer), `src/platform/recomp_env.h` (`RECOMP_MOUSE`,
  `kbm_script`, `mouse` trace), tests, `src/input/README.md`,
  `docs/runtime/config.md`. The `src/input` parts are "conform" for an
  upstream PR (C11, no dependency, tests), with the compiled-in default
  table unchanged; the config reader is part of the enhancements layer,
  which upstream receives as one opt-in extension.
- **Game** (`cat`): `packaging/config.default.toml` (`[input]`,
  `[input.bindings]`), `packaging/launch.env.default.{windows,macos}`
  (drop `RECOMP_KEYBOARD=1`), `packaging/*/README.part` and `README.md`
  (Controls), `src/pad_input.c` (decoupling, `mouse=` in the sources line,
  script isolation), `src/env/recomp_env_game.h` (nothing new; the keys
  are the toolkit's), `analysis/golden/golden.json` (`RECOMP_MOUSE=0`),
  `docs/env.md` (rows and counts), new `docs/input.md`,
  `scripts/test_launchers.py`.
- **CLI** (`xboxrecomp-cli`): no code change. Two optional follow-ups ride
  the next release: the steamos `README.part` Controls paragraph, and
  `RECOMP_MOUSE=0` in the `bench integrate` pin string (not a gate:
  `RECOMP_CONFIG=none` plus the code default already give off).
- **Burnout 3** (`b3/`): unaffected until BLX-75 wires the layer; then its
  `config.default.toml` may turn the keyboard on for its USB pad path,
  which reads `xbox_InputGetState(0)`. The toolkit `src/input` change is
  built and smoke-run on Burnout 3 under Proton (CLAUDE.md gate).
