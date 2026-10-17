# Keyboard and mouse

BLiNX 2 was made for the Xbox controller. The keyboard and the mouse stand
in for one: together they are player 1, merged with a controller on player 1
if one is plugged in (both work at once). **Escape pauses the game (it is
START); `F9` frees the mouse cursor.**

Both are on in the shipped settings (`input.keyboard` and `input.mouse` in
`config.default.toml`) and read only while the game window has the focus.

## The default keys

| Keys and mouse | Xbox control | What it does in BLiNX 2 |
|---|---|---|
| `W` `S` `A` `D`, or numpad `8` `2` `4` `6` | left stick | move |
| mouse motion, or `I` `K` `J` `L` | right stick | look (the camera) |
| arrows | d-pad | menus and selection |
| `Space` | A | jump; confirm |
| left click or `R` | right trigger | sweep and shoot |
| right click or `F` | B | action; back in menus |
| `E` | X | time control |
| `Q` | Y | in play |
| `C` | White | in play |
| `Z` | Black | in play |
| left `Shift` | left trigger | in play |
| `Tab` | left stick click | |
| middle click | right stick click | camera |
| `Enter` or `Escape` | START | pause; "press start" |
| `Backspace` | BACK | menus |
| left `Alt` (hold) | | walk: the movement keys push the stick half way |
| `F9` | | free the cursor; again to grab it |

Untouched by default, so there is room to add your own: `X` `V` `G` `T`
`Y` `U` `O` `P` `H` `N` `M` `B`, the digits, `Ctrl`, `F1` to `F8`, `F12`,
the punctuation keys, the fourth and fifth mouse buttons and the wheel.

## Changing a key

Put the control under `[input.bindings]` in `config/config.toml` in the
data folder (the file that holds only your changes; `config.default.toml`
beside the game lists every control with its default and is replaced on an
update). A control takes one name or a list of names:

```toml
[input.bindings]
# Jump on J as well as Space.
a = ["Space", "J"]

# Y on the wheel: a notch up presses it for a moment.
y = "WheelUp"

# Bind Space to B. Space is then B and nothing else: it leaves A by itself,
# and A keeps its other keys (none by default, so give it a free one).
b = "Space"
a = "G"
```

The rules:

- Your line replaces the default for that control whole: `start = "Return"`
  drops `Escape` from START. `a = []` unbinds A.
- An input you bind in `config.toml` is taken away from every control that
  had it by default, so you never press two controls with one key by
  accident.
- In one file, an input named under two controls is reported and the second
  is ignored.
- A mistake never stops the game. The log has one line for each, for example
  `[INPUT] config error: config/config.toml:4: unknown input 'Spacebar' in
  input.bindings.a (see docs/input.md); skipped`, and the rest of the file
  applies.
- The startup line `[INPUT] config: keyboard=on mouse=on ... bindings=24
  (config.default.toml) +3 (config/config.toml)` says how many controls each
  file decided.

The controls are `a b x y white black ltrigger rtrigger start back lthumb
rthumb dpad_up dpad_down dpad_left dpad_right lstick_up lstick_down
lstick_left lstick_right rstick_up rstick_down rstick_left rstick_right`.

## Names

Names are case-insensitive and follow the label on the key (on an AZERTY
keyboard, `Z` is the key labelled Z):

- letters `A` to `Z`, digits `0` to `9`, `F1` to `F12`;
- `Space`, `Return` (or `Enter`), `Escape` (or `Esc`), `Backspace`, `Tab`;
- `LShift` `RShift` (`Shift`: either), `LCtrl` `RCtrl` (`Ctrl`), `LAlt`
  `RAlt` (`Alt`);
- `Up` `Down` `Left` `Right`, `Insert` `Delete` `Home` `End` `PageUp`
  `PageDown`;
- the numpad: `KP0` to `KP9`, `KPEnter` `KPPlus` `KPMinus` `KPMultiply`
  `KPDivide` `KPPeriod`;
- punctuation: `Comma` `Period` `Slash` `Semicolon` `Quote` `LBracket`
  `RBracket` `Backslash` `Minus` `Equals` `Grave`;
- the mouse: `MouseLeft` `MouseRight` `MouseMiddle` `Mouse4` `Mouse5`
  `WheelUp` `WheelDown`.

The Windows key and Cmd belong to the system and cannot be bound. `F10`
opens the enhancements menu and `F11` is kept for fullscreen; binding them
works but logs a warning, as does binding `F9`, which frees the cursor.

To find a key's name, run with `RECOMP_TRACE=key` (in `config/launch.env`,
or in front of the command) and press it: the log prints `[KEY] down
Semicolon`, and that name goes in the file.

## The mouse

Moving the mouse turns the camera the way the right stick does. Focusing the
game window grabs the cursor (hidden, kept inside the window) and the log
says `[INPUT] mouse captured`. The cursor is freed when the window loses the
focus (Alt-Tab, Cmd-Tab, minimise) and when you press `F9`; a second `F9`, or
focusing the window again, grabs it back. While the cursor is free the mouse
drives nothing, and the click that brings the window forward does nothing
in the game either: the first click after the grab is the first that counts.

The settings, under `[input]` in `config/config.toml`:

| Key | Default | What it does |
|---|---|---|
| `mouse_sensitivity` | `1.0` | `0.1` to `10.0`; at 1.0, 40 counts in one frame is the stick pushed all the way |
| `mouse_invert_y` | `false` | `true`: mouse forward looks down |
| `mouse_invert_x` | `false` | |
| `mouse_min_deflection` | `0.45` | `0.0` to `0.9`: how far any motion pushes the stick at least |
| `mouse_look` | `"right_stick"` | `"left_stick"` moves the player instead; `"none"` keeps only the buttons |
| `mouse_capture` | `"focus"` | `"click"`: the first click in the window grabs (that click does nothing else); `"never"`: never grab |
| `mouse_release_key` | `"F9"` | any key name; `""` or `"none"`: no release key |
| `wheel_pulse_ms` | `100` | how long a wheel notch holds its control |

**Why a stick, and why the floor.** The game has no pointer; it reads the
right stick as a turning speed, so the mouse is turned into a stick for one
frame per movement. A flick turns the camera for as long as you move, not
by a fixed angle, and `mouse_sensitivity` is the lever. The game ignores a
stick pushed less than about 0.4 of the way, so a slow movement would do
nothing; `mouse_min_deflection` makes any movement count as at least that
much, and faster movement pushes further. To tune it, run with
`RECOMP_TRACE=mouse`: each frame with motion logs `[MOUSE] dx=20 dy=-5 ->
RS(23756,...)`, the counts in and the stick out.

## The movement keys

A movement key pushes the stick to just past the game's dead band at once
and all the way within `stick_ramp_ms` (60 ms, about two frames), so a tap
moves a little and a hold runs. Two keys at a right angle (W and D) push the
stick as far as one, as a real stick in a corner does. Holding `walk_key`
(left `Alt`) caps the push at `walk_scale` (0.5) of the way. In `[input]`:

| Key | Default | What it does |
|---|---|---|
| `stick_ramp_ms` | `60` | `0` to `2000`; `0`: full at once (menus react a frame sooner) |
| `walk_key` | `"LAlt"` | any key name; `""` or `"none"`: no walk key |
| `walk_scale` | `0.5` | `0.41` to `1.0` |

Buttons and triggers from a key or a mouse button are fully pressed or not
at all: the game reads the buttons that way, and a key has no pressure to
give a trigger.

## Turning them off

`keyboard = false` or `mouse = false` under `[input]` in
`config/config.toml`, or `RECOMP_KEYBOARD=0` / `RECOMP_MOUSE=0` in
`config/launch.env` (the variables win over the files). A run with an input
script (`RECOMP_INPUT_SCRIPT`) turns both off unless the variable turns them
on, and `RECOMP_CONFIG=none` reads no settings file, so both stay off there.

## Known limits

- No menu to rebind keys yet: the file is the way.
- No pointer: the mouse is a stick and buttons, nothing more.
- One player: the keyboard and the mouse are always player 1.
- With several controllers connected, the first one pressed becomes player 1,
  whatever its slot or ring LED.
- On the Steam Deck use the Gamepad controller template; a template that
  emulates a mouse also works, the trackpad then looks around.
- Under Wine and Proton the mouse uses raw input, with a fallback that
  recentres the cursor every frame if raw input stays silent.
