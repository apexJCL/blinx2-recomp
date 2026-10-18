## Context

Written 2026-10-11 against cat `main` 1d51340, toolkit
`posix-host/portability` e629c35, CLI `main` 2ad3699 (v0.6.0). Read-only;
nothing here is implemented.

**How input reaches the title today.** The seven XDK XInput entry points
are overridden in `cat:src/recomp_manual.c`; `cat:src/pad_input.c`
merges a script on port 0 with the toolkit's `xbox_InputGetState(port)`
(buttons OR, analog max, a stick axis the script leaves at zero takes the
host's) and reports a port inserted exactly while it has a source
(`connected_mask_now()`: script bit 0 | `keyboard_on()` bit 0 | host mask).
`toolkit:src/input/input_core.c` reads the host backend (XInput on Windows
and Proton, SDL2 GameController on POSIX) and merges the keyboard on port
0 through the backend's `keyboard` hook (`xbox_InputKeyboardPoll`, gated
by `RECOMP_KEYBOARD`): buttons OR, analog max, a non-zero keyboard axis
replaces the pad's, and the packet number is the keyboard's so the title's
edge detector sees a change.

**The key path.** `toolkit:src/input/keyboard.c` owns `s_key_down[256]`
indexed by Windows virtual-key codes, written by three window procedures
(`fb_present.c` GDI, `nv2a_pb_d3d11.c` D3D11, `keyboard_sdl.c` for the SDL
loop in `fb_present_sdl.c`, which turns SDL keycodes into the same VKs)
and read on the guest's poll thread, byte by byte, no lock. Focus loss,
hide and minimise clear the table; auto-repeat is dropped; on macOS Cmd
clears and Cmd+key is ignored. The one map `xbox_key_map[]` (24 rows) is
checked against `src/input/README.md` by `tests/input_keyboard`;
`tests/input_keyboard_sdl` drives the SDL rules with synthetic events under
`SDL_VIDEODRIVER=dummy`. A stick key is `±32767`; opposite keys cancel; a
button key is 255 or a `wButtons` bit.

**What the title does with the values** (`analysis/bringup/input/
analog-audit.md`, local; `input-real-devices` design): face buttons are
read as zero or non-zero (threshold 30); the triggers are read as analog;
each stick is normalised and anything under **0.4** of full deflection is
zeroed; the menus turn a stick into d-pad directions at `|s| >= 0x6000`;
the poll runs once per game frame (30 Hz in play) at frame start. START
pauses ("GAME PAUSED"); the hub drill says "Press the A Button" and "Move
the Right thumbstick to look", so A confirms and jumps and the right stick
is the camera. The language pack ships four button-prompt textures per
class (`com_button01..04_swe_us.dds`, `_tom_`), so four face buttons are
prompted in play.

**Mouse today.** None. The three windows load `IDC_ARROW` and handle no
mouse message; the SDL loop forwards every event to `xbox_InputSdlEvent`,
which ignores mouse events.

**Config.** `config-layering` (merged 2026-10-11): `enhance_cfg_init`
reads `<exe dir>/config.default.toml` (slot 2), `<root>/config/config.toml`
(slot 1) and an optional title file (slot 0), the environment on top;
typed lookups, `enhance_cfg_bind_env(key, RENV_X)`, `enhance_cfg_file(i)`
for prefix scans, `enhance_cfg_report_unused`, one `[ENHANCE] config:`
line, a file that does not parse skipped whole with its line. The reader
(`recomp_cfg.h`) accepts tables, dotted keys, strings, ints, floats, bools
and arrays of scalars. cat calls `xbox_enhance_init(".", NULL)` then binds
its own keys (`fps.mode`, `fx.glow`). `golden.json` pins
`RECOMP_CONFIG=none RECOMP_HOST_PAD=0 RECOMP_KEYBOARD=0
RECOMP_INPUT_STRICT=1`. The bundles' `launch.env.default.{windows,macos}`
set `RECOMP_KEYBOARD=1` (macOS also `RECOMP_HOST_PAD=1`);
`scripts/test_launchers.py` asserts both.

**Neighbours.** `enhance-menu-preview` D4 adds a hook at the end of
`xbox_InputGetState`, a pad chord and the keyboard hotkey `menu.hotkey`
(default `F10`) read through `xbox_FramebufferKeyDown(vk)`; while the menu
is open the hook returns a neutral pad. `sdl3-migration` D8/D9 renames the
SDL gamepad and key APIs and brings hot-plug; it has not merged.
`TASKS.md` keeps "Fullscreen hotkey: decide it together with
spike/input-selection" open.

## Goals / Non-Goals

**Goals**
- A player with a keyboard and a mouse and no controller plays BLiNX 2
  from the title screen to a stage on macOS, on a Linux PC, on the Deck's
  desktop and on the Linux/Proton host, with the camera on the mouse.
- The whole mapping is one table in the shipped `config.default.toml`
  that the operator tunes before implementation and the player overrides
  key by key in `config/config.toml`, with mistakes reported by file and
  line and never fatal.
- A controller keeps working beside the keyboard and mouse, plugged in or
  out at any time.
- Scripted, golden and bench runs never see a key or the mouse.
- Everything is testable without hands: a ctest for every pure part and a
  scripted injection for the end-to-end path.

**Non-Goals**
- Per-port source selection, pinning a pad by GUID, remapping a pad's own
  buttons (the parked `input-selection` spike; Steam Input covers pads on
  the Deck and the Linux/Proton host).
- Hot-plug on SDL hosts (`sdl3-migration` D8).
- A rebinding UI. The menu (`enhance-menu-preview`) may grow an input page
  later on top of the same keys; the trace that names keys and mouse
  inputs (D10) is the discovery tool until then.
- A pointer for the title. It has none; the mouse only emulates a stick
  and buttons.
- Pressure-sensitive face buttons from keys or mouse buttons: the title
  reads them as pressed or not.
- The fullscreen hotkey. `F11` is reserved for it (D11) and nothing is
  implemented.

## Decisions

### D1. One port-0 source, "KBM", above the backend seam; enablement decoupled from the host pad

The keyboard and the mouse together are one source on port 0, composed in
the toolkit (`keyboard.c` for keys, new `mouse.c` for the mouse, one
`xbox_InputKbmPoll()` replacing `xbox_InputKeyboardPoll` as the backend
hook) and merged on top of a pad there exactly as the keyboard is today.
`xbox_input` gains overrides the config layer or a game sets before the
first poll:

```c
void xbox_InputKeyboardEnable(int on);    /* -1: back to RECOMP_KEYBOARD */
void xbox_InputMouseEnable(int on);       /* -1: back to RECOMP_MOUSE */
int  xbox_InputKeyboardOn(void);
int  xbox_InputMouseOn(void);
```

Without the enhancements layer the hook falls back to the environment
(`RECOMP_KEYBOARD`, `RECOMP_MOUSE`) and the compiled-in table, which is
what upstream ships. cat's `keyboard_on()` becomes
`xbox_InputKeyboardOn() || xbox_InputMouseOn()` with no `g_host_on` term:
`RECOMP_HOST_PAD` governs host *pads*; the keyboard and mouse are the
host itself. A Mac developer build with no pad and no script therefore
gets the keyboard from `build/config.default.toml` without
`RECOMP_HOST_PAD=1`.

Alternative: a separate port for the keyboard (player 2). Rejected: the
title is single-player in story mode and the merged port-0 source is what
every bundle has shipped since 2026-10-06.

### D2. Defaults: off in code, on in the game's shipped config; why that is not an opt-in enhancement

Code defaults (toolkit): `input.keyboard = false`, `input.mouse = false`.
That is upstream's `RECOMP_KEYBOARD` default and keeps a toolkit without
the config layer, and every scripted or golden run (`RECOMP_CONFIG=none`),
exactly where it is.

Game defaults (`packaging/config.default.toml`): `keyboard = true`,
`mouse = true`. CLAUDE.md says opt-in features default off and never
change stock behaviour. Stock behaviour is the title's: its frames, its
pacing, its sound. Input devices are the host's. The console had a Duke
in port 1 and the title is unplayable without one; a PC has a keyboard
and a mouse and, often, no pad. A bundle whose player cannot press START
is not stock, it is broken, and the user already decided (2026-10-06,
`packaging-ux`, `input-real-devices` 4.4) that the packaged game turns the
keyboard on. This change continues that decision, moves the switch from
`launch.env` into the file the player edits, and adds the mouse beside
it. The goldens cannot see any of it: `RECOMP_CONFIG=none` skips the
defaults file, `RECOMP_KEYBOARD=0` is pinned and `RECOMP_MOUSE=0` joins
it; `golden.py` reads no `[INPUT]` line.

Scripted runs outside the bench (`RECOMP_INPUT_SCRIPT` set, a developer
probing): the isolation rule of `input-real-devices` D6 holds. With a
script set, cat turns the keyboard and the mouse off unless the
environment names them (`enhance_cfg_source_of("input.keyboard") ==
ENHANCE_SRC_ENV`, same for the mouse): a file value never reaches a
scripted run, an explicit `RECOMP_KEYBOARD=1` does.

The developer build (`./build/cat_recomp`, no script) reads
`build/config.default.toml` and so gets the keyboard and the mouse on;
`RECOMP_MOUSE=0` or a line in `config/config.toml` turns either off. With
`mouse_capture = "focus"` (D8, the operator's choice) a focused windowed
run grabs the cursor; `F9` frees it until the window is refocused.

### D3. The mapping lives in `[input]` and `[input.bindings]` of the config files

The two files `config-layering` defined are the place: shipped defaults
tuned by the operator, player differences in `config/config.toml`,
environment on top, one error format, one log line, `report_unused` for
typos. No new file, no new parser, no `input.ini` (the spike's D6 predates
the layer). Flat keys with an `input.` prefix for the switches and knobs,
and one sub-table for the bindings, so a TOML value and a TOML table never
share a name:

```toml
[input]
keyboard = true             # keys drive player 1 (port 0), merged onto a pad there
mouse = true                # the mouse too: motion is a stick, buttons as bound below
mouse_look = "right_stick"  # what mouse motion drives: "right_stick" (the camera),
                            # "left_stick", "none"
mouse_sensitivity = 1.0     # 0.1 .. 10.0; 1.0: 40 counts in one frame is full deflection
mouse_invert_y = false      # true: mouse forward looks down
mouse_invert_x = false
mouse_min_deflection = 0.45 # 0.0 .. 0.9; any motion deflects at least this much, because the
                            # game ignores a stick under 0.4 of full
mouse_capture = "focus"     # "focus": the cursor is grabbed whenever the window has focus;
                            # "click": the first click in the window grabs it; "never"
mouse_release_key = "F9"    # frees the cursor (press again to grab it back; refocusing
                            # the window grabs it too)
wheel_pulse_ms = 100        # how long a wheel notch holds its control
stick_ramp_ms = 60          # a stick key reaches full deflection in this time; 0: at once
walk_key = "LAlt"           # held: the stick keys give walk_scale of full deflection
walk_scale = 0.5

[input.bindings]            # Duke control = key or mouse input, or a list of them
a = "Space"
start = ["Return", "Escape"]
# ... (D5 has the full table)
```

**Vocabulary.** Control names (left column) are fixed:
`a b x y white black ltrigger rtrigger start back lthumb rthumb dpad_up
dpad_down dpad_left dpad_right lstick_up lstick_down lstick_left
lstick_right rstick_up rstick_down rstick_left rstick_right`. Input names
(right column) are case-insensitive and name the key by the label the
host layout gives it, as the VK table does today (the key labelled Z is
`Z` on AZERTY too): `A`..`Z`, `0`..`9`, `F1`..`F12`, `Space`, `Return`
(alias `Enter`), `Escape` (alias `Esc`), `Backspace`, `Tab`, `LShift`
`RShift` (alias `Shift`, both), `LCtrl` `RCtrl` (`Ctrl`), `LAlt` `RAlt`
(`Alt`), `Up` `Down` `Left` `Right`, `Insert` `Delete` `Home` `End`
`PageUp` `PageDown`, `KP0`..`KP9`, `KPEnter` `KPPlus` `KPMinus`
`KPMultiply` `KPDivide` `KPPeriod`, `Comma` `Period` `Slash` `Semicolon`
`Quote` `LBracket` `RBracket` `Backslash` `Minus` `Equals` `Grave`; the
mouse: `MouseLeft` `MouseRight` `MouseMiddle` `Mouse4` `Mouse5` `WheelUp`
`WheelDown`. `LGui`/`RGui` (Cmd, Windows key) are not bindable: Cmd is
the system's on macOS (`keyboard_sdl.c`) and the Windows key opens the
Start menu. The table of names lives in one file,
`src/input/input_names.c`, with the VK for each and the SDL keycode on
POSIX, and `tests/input_bindings` round-trips every name.

**Resolution.** Per control, the highest layer that names it wins whole
(the player's `start = "Return"` replaces the defaults'
`["Return", "Escape"]`, not appends; `a = []` unbinds). Then, across layers, a key the player's file
names under control X is removed from every other control it inherited
from a lower layer, so "I bound Space to B" means Space is B and nothing
else, without the player having to touch `a`. Inside one file an input
named under two controls is an error: the second occurrence is reported
and ignored. A control missing from every file keeps the compiled-in
default.

**Errors** (never fatal; the rest of the file applies) are one line each,
`[INPUT] config error: <file>:<line>: <message>`:
- `unknown control 'jmp' under [input.bindings] (controls: a b x ... rstick_right); ignored`
- `unknown input 'Spacebar' in input.bindings.a (see docs/input.md); skipped`
- `'Space' already bound to input.bindings.a on line 12; ignored here`
- `input.bindings.a is a string or a list of strings (got integer); ignored`
- `input.mouse_sensitivity 0 out of range 0.1 .. 10.0; using 1.0`
- `input.mouse_look 'camera' is not one of right_stick, left_stick, none; using right_stick`
- `input.walk_key 'F10' is the menu hotkey (menu.hotkey); bound anyway` (a warning, for `F10`, `F9` as a binding, and `F11`, D11)
A file that does not parse is skipped whole by the layer, as today, with
the layer's own line.

**Log** (one line at init, `[INPUT]` prefix so `golden.py`'s `[ENHANCE]`
parsers learn nothing):
```
[INPUT] config: keyboard=on mouse=on look=right_stick sens=1.0 bindings=38 (config.default.toml) +2 (config/config.toml)
[INPUT] config: keyboard=off mouse=off (RECOMP_CONFIG=none)
```
The `sources` line gains `mouse=<on|off>`.

**Where it runs.** `src/enhance/enhance_input.c` (new, part of the
enhancements layer), called from `xbox_enhance_init` after the toolkit's
own keys: binds `input.keyboard` to `RENV_KEYBOARD` and `input.mouse` to
`RENV_MOUSE`, reads the knobs with the typed getters, scans
`enhance_cfg_file(2)`, `(1)`, `(0)` for the `input.bindings.` prefix
(every key passed to `enhance_cfg_lookup` so `report_unused` is right),
resolves, and applies through the `xbox_input` API (D4). Burnout 3 gets
it the day the tracker item calls `xbox_enhance_init`. Alternative: read the keys in
cat's `main.c`. Rejected: the second game would copy it, and the
vocabulary is the toolkit's.

### D4. The `xbox_input` binding API; the compiled-in table is the fallback and does not change

`keyboard.c` keeps `xbox_key_map[]` as the compiled-in default (upstream
parity; `tests/input_keyboard` and the README table unchanged) and gains a
runtime table the config layer fills:

```c
/* input_names.c */
int  xbox_InputNameToCode(const char *name, int *code, int *is_mouse);
const char *xbox_InputCodeName(int code, int is_mouse);
int  xbox_InputControlFromName(const char *name);     /* -1 unknown */
/* keyboard.c */
void xbox_InputBindingsReset(void);                    /* back to the compiled-in table */
int  xbox_InputBind(int control, int code, int is_mouse); /* 0, or -1 when the control is full (8 inputs) */
int  xbox_InputBindingsOf(int control, int *codes, int *is_mouse, int max);
void xbox_InputKeyboardOpts(int stick_ramp_ms, int walk_code, double walk_scale);
```

`tests/input_bindings` links `keyboard.c`, `mouse.c` and `input_names.c`
with no SDL and no Win32 window, on every host, like `tests/input_keyboard`.
The composer (`xbox_InputKbmState`) builds the pad from the runtime table:
button controls 255 or a bit; a stick control's keys ramp (D6); mouse
inputs are read from `mouse.c` (D7, D8). The packet number moves on every
call, as today.

### D5. The default layout (decided by the operator, 2026-10-11)

The operator fixed the face buttons, shoulders, triggers and the right
stick click on 2026-10-11 (the list below, quoted in Open Questions 1).
The listed controls carry exactly the operator's input and nothing else;
the unlisted controls keep what the first draft proposed, minus any key
or button a listed control now takes. The "BLiNX 2 action" column stays
as far as the project knows it; it is documentation, not a decision. This
table becomes `packaging/config.default.toml` in task 3.1.

| Duke control | `input.bindings` key | BLiNX 2 action | Default inputs |
|---|---|---|---|
| Left stick | `lstick_up/down/left/right` | move (confirmed) | `W` `S` `A` `D`, and `KP8` `KP2` `KP4` `KP6` |
| Right stick | `rstick_up/down/left/right` | camera (confirmed: "Move the Right thumbstick to look") | `I` `K` `J` `L`; mouse motion through `mouse_look = "right_stick"` |
| D-pad | `dpad_up/down/left/right` | menus and selection (confirmed in the editor) | `Up` `Down` `Left` `Right` |
| A | `a` | jump; confirm ("Press the A Button") | `Space` (operator) |
| B | `b` | action; back in menus (EXIT B) | `MouseRight` (operator, 2026-10-12), `F` (the user, 2026-10-13) |
| X | `x` | time control (the user, 2026-10-12, on a Time Sweepers stage; the Tom-Tom Gang side is unchecked, task 5.3) | `E` (operator, 2026-10-12) |
| Y | `y` | in play | `Q` (operator) |
| White (LB) | `white` | in play | `C` (operator) |
| Black (RB) | `black` | in play | `Z` (operator) |
| Left trigger | `ltrigger` | in play (read as analog by the title) | `LShift` (operator) |
| Right trigger | `rtrigger` | sweep and shoot (the user, 2026-10-12; read as analog by the title) | `MouseLeft` (operator, 2026-10-12), `R` (the user, 2026-10-13) |
| Left stick click | `lthumb` | barely used | `Tab` |
| Right stick click | `rthumb` | camera | `MouseMiddle` (operator) |
| START | `start` | pause (confirmed); "press start" | `Return`, `Escape` |
| BACK | `back` | menus | `Backspace` |
| walk modifier | `input.walk_key` | half-speed walk (host-side, D6) | `LAlt` |
| free the cursor | `input.mouse_release_key` | host-side (D8) | `F9` |

Against the first draft (and the keyboard table the bundles shipped since
2026-10-06): kept as proposed are the movement, camera and d-pad rows,
`Tab` = left stick click, `Return`/`Escape` = START, `Backspace` = BACK,
`LAlt` and `F9`, none of which conflicts with the operator's list. The
operator's list reassigns `Q` (was White), `C` (was X), `Z` (was A), `E`
(was Black) and `LShift` (was the left trigger's first key). Dropped from
the defaults because a listed control took the key or the control: `X`
(was B), `V` and `F` (were Y), `G` (was the right stick click), `1` and
`3` (were the triggers), `LCtrl` (was the right trigger), `Mouse4` and
`Mouse5` (were the triggers), `WheelUp` and `WheelDown` (were the
shoulders). The wheel and the fourth and fifth mouse buttons are
therefore free by default; the "Wheel notch" scenario of the spec binds
one in the player's file. The compiled-in toolkit table does not change
(D4): these edits live in the game's `config.default.toml`.

The second keys on B (`F`) and the right trigger (`R`) came after the
round-3 review (the user, 2026-10-13): with the mouse off, freed or
unplugged, no key pressed B or the right trigger, so the game could not
be played on the keyboard alone.

Untouched by default: `X`, `V`, `G`, `T`, `Y`, `U`, `O`, `P`,
`H`, `N`, `M`, `B`, every digit, `LCtrl`/`RCtrl`, `F1`..`F8`, `F12`, the
punctuation keys, `Mouse4`, `Mouse5` and the wheel, so a player has room.

### D6. Stick keys ramp; a walk modifier; diagonals circle-normalised

A held stick key reads at least `KBM_STICK_FLOOR` (0.41 of full, just
above the title's 0.4 deadzone, so the first poll after a press already
moves Stick instead of landing in the dead band) and ramps linearly to
32767 over `stick_ramp_ms` (`config.default.toml` ships 60 ms, about two
polls at 30 Hz; the code default is 0, today's instant full deflection,
which `tests/input_keyboard` keeps checking). The ramp is a per-axis float advanced at each poll from
the backend's `now_ms`, so it needs no thread and is exact under
injection (D9). Two perpendicular stick keys are scaled by 1/√2 so the
magnitude equals one key's; opposite keys cancel. While `walk_key` is
held the stick keys give `walk_scale` of full deflection
(`config.default.toml` ships 0.5, the code default is 1.0; a
`walk_scale` under the same 0.41 floor is reported and clamped to it).
The menus turn a stick into d-pad presses at 0.75, so with the shipped
ramp a tapped stick key reaches the menus one poll after it is pressed;
a player who wants instant menus sets `stick_ramp_ms = 0`. Face buttons, shoulders, triggers and the clicks stay
0 or 255 from a key or a mouse button: the title reads the buttons as
pressed or not, and a trigger from a key has no pressure to report. The
deviation is recorded (deviations delta).

### D7. Mouse motion is a stick; the model

`mouse.c` keeps, written by the window thread and exchanged to zero by the
poll thread with atomics: `dx`, `dy` (accumulated relative counts since
the last poll), `wheel` (notches), five button bytes, a `captured` flag.
At each poll, with `c = counts * mouse_sensitivity / 40` per axis:

```
n   = min(1, |c|)
out = c == 0 ? 0 : sign(c) * (mouse_min_deflection + (1 - mouse_min_deflection) * n) * 32767
```

`40` counts per poll at sensitivity 1.0 is full deflection: at 30 polls/s
that is 1200 counts/s, about 4 cm/s on a 800-DPI mouse, a brisk but not
fast sweep; the operator tunes `mouse_sensitivity` from there. The floor
exists because the title zeroes a normalised stick under 0.4: without it
a slow mouse movement would do nothing at all and a medium one would jump
in. With the floor, any motion turns the camera at least at the title's
slowest rate, and speed scales from there, which is what mouse-as-stick
feels like in every emulator that offers it. Mouse right is stick right;
mouse forward (negative dy on Win32 and SDL alike) is stick up unless
`mouse_invert_y`. The deflection lasts exactly one poll per motion: a
mouse at rest reads zero next poll, so there is no drift and no decay
knob. `mouse_look = "left_stick"` moves Stick instead (for a player who
wants it), `"none"` keeps the buttons and drops the motion. The axis the
mouse drives replaces the pad's when non-zero, like a stick key.

Mouse buttons are inputs like keys (D3). A wheel notch presses its
control for `wheel_pulse_ms` (default 100 ms, about three polls, so the
title's edge detector sees it); notches queue, so two quick notches give
two presses.

Threads: the poll reads one atomic exchange per accumulator and byte
loads for the buttons; no lock, same argument as the key table.

### D8. Capture: focus grabs, focus loss releases, F9 toggles

`mouse_capture = "focus"` (default; the operator, 2026-10-11): the cursor
is captured (hidden, relative motion, confined to the window) whenever
the game window has focus and `input.mouse` is on, from the first focus
on. It is released on focus loss, hide or minimise (the same events that
clear the keys), when `xbox_InputMouseSuspend(1)` is called (the
enhancements menu while it is open; phase 3 of `enhance-menu-preview`
adds the call, and `Suspend(0)` grabs again if the window still has
focus) and when the window closes. `mouse_release_key` (`F9`) toggles:
pressed while captured it frees the cursor and the window stays focused
with the cursor free; pressed again it grabs; regaining focus grabs too.
While released, motion drives nothing and buttons drive nothing. The two
other modes stay available: `"click"` grabs on the first mouse button
press inside the focused window (that press is consumed) and otherwise
behaves as `focus`; `"never"` never grabs, and buttons work only while
the cursor is over the window. Each transition logs
`[INPUT] mouse captured` / `released (<reason>)`. The Deck in Game Mode
with the Gamepad template (Open Question 7) sends no mouse, so nothing
is grabbed there; in desktop mode a real mouse follows the same rules.

Host feeders:
- **Win32** (`fb_present.c`, `nv2a_pb_d3d11.c`, one shared function in
  `mouse.c`'s Win32 half, upstream-neutral): `RegisterRawInputDevices`
  for the mouse with the window as target on capture; `WM_INPUT`
  `RIM_TYPEMOUSE` relative `lLastX/lLastY` into the accumulators (the
  absolute-motion flag is handled by differencing); buttons from the raw
  flags; wheel from `WM_MOUSEWHEEL`; capture = `ShowCursor(FALSE)` +
  `ClipCursor(client rect)` + `SetCursorPos` to the centre at each poll
  as a safety net for a Wine build whose raw input stays silent (then
  `WM_MOUSEMOVE` deltas against the centre feed the accumulators
  instead); release undoes all three. Alt+Tab and `WM_KILLFOCUS` release.
  Wine implements raw mouse input (`WM_INPUT`) and `ClipCursor`; the
  Proton run (task 5.2) is the proof, and the re-centre fallback is there
  so the feature never depends on it.
- **SDL** (`mouse_sdl.c`, fork-only like `keyboard_sdl.c`):
  `SDL_SetRelativeMouseMode(SDL_TRUE/FALSE)`; `SDL_MOUSEMOTION`
  `xrel/yrel`; `SDL_MOUSEBUTTONDOWN/UP` (`button` 1..5); `SDL_MOUSEWHEEL`
  `y`, sign flipped under `SDL_MOUSEWHEEL_FLIPPED`; `FOCUS_LOST`,
  `HIDDEN`, `MINIMIZED` release. The SDL3 rename (`SDL_SetWindowRelativeMouseMode`,
  `SDL_EVENT_MOUSE_*`) touches this one file.
- **Headless** (`RECOMP_HEADLESS=1`, no window): no mouse, as no keys,
  except through injection (D9).

### D9. Scripted injection for unattended tests: `RECOMP_DEBUG=kbm_script=<file>`

A debug-tier key in the toolkit (`recomp_env.h`, `KBM_SCRIPT`): a file of
events applied on the guest's poll thread inside `xbox_InputKbmPoll`,
timed in seconds since the first poll or in polls (`p`), one per line,
`#` comments:

```
2.0   key down Return
2.2   key up Return
40p   key down W            # polls since the first poll
100p  key up W
5.0   mouse move 20 -5      # counts, applied as one poll's motion
5.1   mouse down MouseLeft
5.3   mouse up MouseLeft
6.0   wheel 1
```

It writes the same tables the windows write (`xbox_InputKeySet`, the
mouse accumulators) and forces capture, so everything from the name
table to the title's pad struct is exercised in a headless Mac run and in
a Proton bench run, where the Wayland session on the Linux/Proton host has refused
`xdotool` (`input-real-devices` 4.1). It is debug tier because it
installs machinery and changes behaviour; it is refused when a
`RECOMP_INPUT_SCRIPT` is set (two scripts on one port would race) with
one line. Names are the binding vocabulary, so the script also proves the
name table. `[INPUT] kbm_script: <n> events` at init; a bad line is
reported with its number and skipped.

### D10. Discovery: the `key` trace names every edge

`RECOMP_TRACE=key` (existing, `RENV_KEY_TRACE`) grows from "the first 40
key-downs as `vk=0x..`" to one line per edge with the binding name, so a
player finds the name of a key or mouse button by pressing it:
`[KEY] down Space`, `[KEY] up Space`, `[KEY] mouse down MouseLeft`,
`[KEY] wheel +1`, `[KEY] mouse captured`. The first 200 edges, then one in
50, so a held key cannot flood the log. A new trace key `mouse` prints,
for the first 200 polls with motion, `[MOUSE] dx=20 dy=-5 -> RS(16383,
-4096)`, the model's input and output, for tuning `mouse_sensitivity`.

### D11. Reserved keys

`F10` is the menu hotkey (`enhance-menu-preview` D6), `F9` frees the
cursor (D8), `F11` is reserved for the fullscreen hotkey the project has
not decided (TASKS: "decide it together with spike/input-selection"; this
change decides only that `F11` is kept free for it, and that `Alt+Enter`
is left to the window procedure). All three are bindable, with a warning
(D3). `Alt+F4` and Cmd+key stay the system's, as today.

### D12. Coexistence with a controller, and hot-plug

Nothing changes in the merge rules: on port 0 the pad and KBM are merged
(buttons OR, analog max, a non-zero KBM axis replaces the pad's); ports
1..3 are pads only. Port 0 is reported inserted while KBM is on, whether
or not a pad is there, so plugging a pad in or out during play never
removes port 0 (the title never sees a remove on port 0 while KBM is on),
which is the behaviour the user asked about on 2026-10-06 (hot-plug on
macOS) for the one port that matters, without the SDL device events
that `sdl3-migration` brings for the pads themselves. With KBM off the
behaviour is today's. A pad's stick at rest with drift and a mouse at
rest: the pad wins (KBM is zero). A pad's stick held and the mouse moved:
the mouse wins for that poll. The mouse being captured does not stop pad
input.

### D13. Platform verdicts and upstream placement

| Part | Lives in | Verdict | Why |
|---|---|---|---|
| Binding API, name table, composer, ramps, mouse model (`src/input/*.c`, no window code) | toolkit | **conform** (a later upstream topic PR, after PR 5 #191 lands) | C11, no dependency, ctest; the compiled-in default table is unchanged, so upstream's behaviour is unchanged until a title binds |
| Win32 mouse feeder (`fb_present.c`, `nv2a_pb_d3d11.c`) | toolkit | **conform** | upstream has both windows; raw input is plain Win32 |
| SDL key and mouse feeders (`keyboard_sdl.c`, `mouse_sdl.c`) | toolkit | **fork-only** (PR 5 territory) | the SDL window is fork-only |
| `[input]` reader (`enhance_input.c`) | toolkit enhancements layer | **fork-only** | the layer goes upstream as one opt-in extension (`enhancements-spike` decisions) |
| `RECOMP_MOUSE`, `kbm_script`, `mouse` trace rows | toolkit `recomp_env.h` | with the env table | the table is fork work in flight |
| Game defaults, the layout, the docs, the launcher change | cat | game-specific | |

Burnout 3 gate: the toolkit branch is built with `b3/` and its race gate
run once under Proton (`RECOMP_USB_PADS=2`, no keyboard) to show the
`src/input` change leaves the USB pad path alone.

## Risks / Trade-offs

- [Wine's raw input or `ClipCursor` misbehaves under some Proton build]
  → the re-centre fallback (D8) needs only `WM_MOUSEMOVE` and
  `SetCursorPos`; task 5.2 records which path the run used.
- [The mouse grabs a developer's cursor whenever the window is focused]
  → `F9` frees it (D8); `RECOMP_MOUSE=0`, `mouse_capture = "click"` or
  `mouse = false` in `config/config.toml` change it for good; focus loss
  always releases; a scripted run never grabs (D2).
- [The 0.4 deadzone floor makes slow mouse motion feel stepped] → the
  floor is a knob (`mouse_min_deflection`); the `mouse` trace shows the
  model's output for tuning; the operator tunes before release.
- [The title reads the right stick as a rate, so a flick does not turn
  the camera by a fixed angle] → inherent to mouse-as-stick; documented in
  `docs/input.md`; `mouse_sensitivity` is the lever.
- [A Deck player picks a Steam Input template that emulates a mouse]
  → both merge on port 0 and the trackpad looks around; the Deck README
  part names the Gamepad template (Open Question 7) and the focus grab
  is harmless with no mouse.
- [A player binds `F10` and loses the menu] → warned at startup (D3), the
  pad chord still opens it.
- [`Escape` = START surprises a player who expects Escape to free the
  cursor] → decided by the operator (Open Question 3): Escape pauses,
  `F9` frees; `docs/input.md` says so in its first lines.
- [Two branches touch the SDL input files (`sdl3-migration`)] → the mouse
  feeder is one new file; whichever merges second ports it; noted in both
  specs.
- [`enhance_input.c` makes the enhancements library depend on
  `xbox_input`] → cat already links both; the layer's CMake gains the
  link; a toolkit built without the layer never compiles the file.
- [Upstream's README calls keyboard/mouse "for debug builds"] → the
  compiled-in table and `RECOMP_KEYBOARD` default are untouched; the PR
  argues the feature as the config-driven opt-in it is.

## Migration Plan

One worktree pair, `wt/kbm/{cat,xboxrecomp}`, branch `feat/kbm-input` in
each, one agent, after the operator has tuned D5. Order: toolkit
(`src/input`, feeders, `enhance_input.c`, env rows, ctests, README,
`config.md`), cat (`config.default.toml`, launchers, `pad_input.c`,
goldens pin, docs, `test_launchers.py`), Mac gates, Proton on "go",
review, squash merges, the post-merge steps of CLAUDE.md.

Rollback: `RECOMP_KEYBOARD=0 RECOMP_MOUSE=0` or `RECOMP_CONFIG=none`
restores a scripted-only run; a `config.default.toml` without `[input]`
leaves the compiled-in table (today's keyboard, no mouse); the toolkit
without the layer is upstream's behaviour.

## Open Questions (answered by the operator, 2026-10-11)

The operator answered on 2026-10-11, relayed by the coordinator; the
answers are decisions and D5/D8 are written from them.

1. **The D5 table.** Decided. The operator's list, quoted
   (`<Keyboard | Mouse>: <Xbox>`): "Space: A; Left Mouse Button: B; Right
   Mouse Button: X; Q: Y; C: White; Z: Black; Left Shift: Left Trigger;
   E: Right Trigger; Mouse Middle Click: Right stick click". "Each listed
   control gets exactly the operator's input and nothing else. Unlisted
   controls keep their earlier defaults, except that any key or button
   now taken by a listed control is dropped from them." D5 records what
   was kept and dropped. The first draft's guess (`MouseLeft` = X,
   `MouseRight` = B) is reversed: B is the left button, X the right.
   **Revised 2026-10-12** after the user's hands-on test of the build
   ("works nicely"): the left button is the right trigger (sweep and
   shoot), the right button B (action), and `E` X (time control). The
   three inputs rotate among those three controls; no other control
   changes, and the D5 table above carries the new rows.
2. **Mouse look target and feel.** Decided: `right_stick`,
   `mouse_sensitivity = 1.0` "as proposed"; `mouse_min_deflection = 0.45`
   stays the starting point, tuned on a build with the `mouse` trace.
3. **Escape.** Decided: "Escape pauses only (START); F9 alone frees the
   cursor."
4. **Capture mode.** Decided: "`focus`: grab whenever the window has
   focus, not on click. Releasing on F9, focus loss and the enhance menu
   still applies, and focus regained re-grabs." D8 and the tests follow.
5. **Walk modifier and ramp.** Decided: "Keep the 60 ms ramp and the LAlt
   walk, and make the ramp tweakable." `stick_ramp_ms` and `walk_scale`
   (and `walk_key`) are `[input]` keys of the config files (D3), written
   with comments in `config.default.toml` (task 3.1) and listed in
   `docs/env.md`'s settings-files section (task 3.5); they have no
   environment variable, by design (a layout does not live in env).
6. **Developer builds.** Not answered; the proposal stands: a developer
   build reads `build/config.default.toml` and gets the keyboard and the
   mouse on without a script, `RECOMP_MOUSE=0` or `config/config.toml`
   turns the mouse off, `F9` frees the cursor. Revisit if it annoys.
7. **Steam Input on the Deck.** Decided: "name the Gamepad template; the
   Deck has a built-in gamepad." The Deck README part says so (task 3.3);
   task 5.4 only confirms the pad path.
