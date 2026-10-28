## Context

This is a spike: design only, read from the code and the web, with no host runs. It was written on 2026-10-23 against:
- toolkit `posix-host/portability` `43327b8e`;
- upstream `main` `f0f8a461`, which includes #203 (`4f887107`);
- cat `a93c649`;
- the tracker item WIP (`feat/overlay-paddle` `74fd70e9`).

It builds on the parked `input-selection` spike (cat `e09b325`); the proposal's table says what is kept, changed and dropped.

Revision 2 (the same day) applies the 18 findings of the review (`notes/input-ux-spike/review-ITEM.md`) and records the user's answers to Q1-Q10. Q11 and Q12 were answered the same day (adopt #203; `[states]` through actions). The confirmation of Q4's details is open.

### What exists (toolkit `43327b8e`)

| Layer | Where | State |
|---|---|---|
| Host pad read | `src/input/xinput_device.c` | `_WIN32`: XInput. `XInputGetStateEx` (ordinal 100) is used for Guide, but only while a pad filter is installed, so a stock run polls as before (`host_pad.h`). Elsewhere: SDL3 gamepads with hot-plug, pumped by the SDL window thread (`xbox_InputSdlPadSync`). `sdl_extra` maps the paddles, Guide, MISC1 and the touchpad to `XBOX_HOST_*` |
| Pad to Duke | `src/input/input_map.{c,h}` (fork, `7618629b`) | one fixed table, `xbox_InputMapXInput` and `xbox_InputMapSdl`. White = LB and Black = RB (Microsoft's 360 convention and xemu's; the fork fixed the old swapped code). Face buttons give 0/255. No deadzone unless `RECOMP_PAD_DEADZONE=N` (an integer 0..32767), because the title applies its own. SDL3 is positional |
| Slot to port | cat `src/pad_slots.c` (pad-slot-ports) | sticky ports, and the first press takes an inert pad's port |
| Keys and mouse | `keyboard.c`, `keyboard_sdl.c`, `mouse*.c`, `[input]`, `[input.bindings]` | done on every window. The parked spike's "keyboard dead in D3D11/SDL" finding is stale |
| Host actions | `src/enhance/enhance_actions.c`, `host_pad.h`, `[input.actions]` | keys, host-only buttons, chords and modifier chords (the host-only member first); consumed chords masked through the pad filter; armed only by a feature key |
| Overlay | 3B landed (layers, text, toasts, stats); 3C/3D/3E/3F/3G/overlay 6/overlay 9 in Backlog | the Controls page (3D.3) captures action bindings only |
| Config | `recomp_cfg.c` (a TOML subset), `enhance_cfg.c` layering | env > `<root>/<title>/config.toml` > `<root>/config/config.toml` > `config.default.toml` > code default; `RECOMP_CONFIG=none` in goldens |

### Upstream #203: pad remapping already exists upstream

Upstream #203 (vyanhursky; `650dfe14`, merged as `4f887107` on 2026-10-19) is not in the fork yet. It adds a pure `src/input/input_map.{c,h}` under the same file name as the fork's module, with a different API:
- `InputRaw`: the raw host pad. It has a source array `src[]` (0..32767) over SDL positional names (`south east west north back guide start left_stick_click right_stick_click left_shoulder right_shoulder dpad_* misc1 touchpad paddle1..4 left_trigger right_trigger` and the eight stick directions), plus the signed sticks.
- `InputPadMap`: one source per guest pad control (16), `left_stick`/`right_stick` as left, right or none (a swap), per-stick deadzones in percent, and trigger and button thresholds in percent.
- `xbox_InputMap_PadMap`, `PadMapDefaults`, `ApplyStick` (radial, rescaled), `ApplyTrigger` and `PadMerge` (buttons OR, larger analog, the further-deflected stick wins).
- The named controls (`dpad_up ... a b x y black white left_trigger right_trigger left_stick_up ...`) and sources.
- Keyboard bindings (`InputBindings`, `KeysResolve`, VK names). This duplicates the fork's `[input.bindings]` resolution.

Upstream's defaults differ from the fork in three ways:
- shoulders: LB = Black and RB = White, following upstream's own `xinput_device.c`, which the fork corrected;
- stick deadzones of 15%, against the fork's 0;
- a 5% trigger threshold, against none.

`PadMapDefaults` is "an initializer, applied only by a port that calls it". Nothing upstream calls `PadMap` from a device backend yet.

### Platform facts (web research, 2026-10-23)

- **Steam Input on a non-Steam shortcut.** Our games are non-Steam shortcuts: `install.sh` adds them through `steamos-add-to-steam`, and Windows has no shortcut at all. A shortcut has no Steamworks app id, so the Steam Input API (action sets, in-game actions, official configurations) is not open to us. What Steam offers a shortcut:
  - a per-shortcut layout the player edits in Steam's UI;
  - templates. Steam reads templates from `~/.steam/steam/controller_base/templates/`. RetroDECK installs its own there, and Steam copies the chosen one into `steamapps/common/Steam Controller Configs/<id>/config/<name>/` when the player picks it.

  A template is the only "recommended layout" a shortcut can ship. The Deck's controller type is `controller_neptune`.
- **Steam's virtual pad.** With Steam Input on, a game sees a virtual Xbox 360 pad (28de:11ff). Steam hides the physical device, and the virtual pad has no paddles, touchpad or gyro. Guide belongs to Steam. Steam Input can still bind a grip to a keyboard key, and that key reaches the game, native or Proton.
  - VID 28de alone is not a Steam Input sign: it is Valve's id on the Deck's own pad (28de:1205), the Steam Controller and the virtual pad.
  - SDL3 (3.2.0+) exposes `SDL_GetGamepadSteamHandle`, which is 0 when the pad has no Steam handle.
  - SDL reads `SteamVirtualGamepadInfo`, so `SDL_GetGamepadType` may report the physical family behind the virtual pad (possibly `SDL_GAMEPAD_TYPE_STEAM` on the Deck). This is unverified (task I1.3, blocked until a native Linux build exists).
  - Under Proton, `SteamGameId` means "launched by Steam" and `SteamDeck=1` means "on a Deck". Neither means Steam Input is on: the player can turn it off per game, and Steam still sets both.
- **SDL3 gamepad features we do not use yet:**
  - `SDL_GetGamepadType`. SDL 3.4.18, the Mac pin, includes `GAMECUBE` and `STEAM`.
  - `SDL_GetGamepadButtonLabel` / `...ForType`.
  - The gyro sensor, the LED and trigger rumble.
  - The paddles are already read. `RIGHT_PADDLE1` is the Elite's P1, the Deck's R4, the DualSense Edge's right back button and a right Joy-Con's SR. The Edge's right Fn button is `RIGHT_PADDLE2` (`paddle3` here).
- **Other ports and recomps:**
  - Zelda64Recomp (N64ModernRuntime) keeps two bindings per game input per device. It captures by scanning, and its menu inputs (`TOGGLE_MENU`, `ACCEPT_MENU`, `APPLY_MENU`) sit beside the game's. cvlod_recomp adopted the same assignment menu (v0.2.17).
  - Ship of Harkinian, RPCS3 and Xenia keep per-port mappings on top of SDL.

  The common shape: a fixed list of game inputs, a few host bindings each, capture by press, glyphs from the pad type, and menu navigation on fixed inputs.

### What the user asked

On PC and macOS the overlay remaps. On the Deck, Steam Input's UI remaps. Answer per host, define the remap model and file, the UI flow, a default overlay chord (Steam+A is screen recording), and the toolkit/game split, upstream fit and phases.

## Goals / Non-Goals

**Goals**
- Every host has one obvious way to remap, and one way to open the overlay that cannot clash with the system or the game.
- One remap model, upstream's where it exists, and one file for keys, mouse and pad: the TOML config.
- A remap never sends the game a press the player did not make, and never makes the overlay unreachable, live or after a restart.
- Glyphs match the pad in the player's hands where the host tells us.
- Toolkit code serves BLiNX 2, Burnout 3 and JSRF unchanged; games add only labels and defaults.
- Stock is untouched: with `RECOMP_CONFIG=none` the map is the identity, polling is as today, and there are no actions.

**Non-Goals**
- Steamworks integration (action sets, in-game actions, an app id): not possible for a shortcut.
- Turbo, macros or per-game scripting of inputs.
- Per-port source selection and GUID pins (input-selection D2): deferred.
- Save states (the tracker item..386). Their hotkeys appear here only as actions that save-states registers (Q12).
- Merging the keyboard half of #203 (`InputBindings`) with `[input.bindings]`. It is flagged for the upstream merge, not designed here.
- Implementation.

## Decisions

### D1. Recommendation per host

| Host | Device layer | Who remaps | Opens the overlay | Glyphs |
|---|---|---|---|---|
| **Windows native** | XInput by default. SDL3 (`SDL3.dll` loaded at run time) is opt-in for one release with `input.backend = "sdl"`, and XInput is the fallback (D2, Q1) | the overlay (`[input.pad]`) | `F10`; `guide+a` (with the Game Bar's "open with the controller" setting off); `paddle1` with SDL3 | XInput: Xbox. SDL3: the pad's family |
| **Proton on the Deck** (the opt-in `steamos` route once linux-native is the default) | XInput through Steam's virtual pad | Steam Input; the overlay works too, after Steam's layout | Steam Input R4 = `F10` (the shipped template, D6); the game's fallback chord | Xbox, or the `input.glyphs` override |
| **Proton on desktop Linux** | XInput (Wine) | Steam Input when on; else the overlay | `F10`; `guide+a` with Steam Input off; the fallback chord | Xbox |
| **Steam Deck native** (linux-native-vulkan, the future default) | SDL3. Steam Input is on by default for a shortcut, so the game sees Steam's virtual pad | Steam Input; the overlay after it | Steam Input on: R4 = `F10` through the template. Steam Input off: `paddle1` (R4) directly | the family SDL reports (I1.3), else the override |
| **Linux desktop native** | SDL3 | the overlay; Steam Input if the player uses it | `F10`; `guide+a`; `paddle1` | the pad's family |
| **macOS** | SDL3 (over GameController and IOKit HID) | the overlay | `F10`; `guide+a`, once Home is handed to apps (System Settings > Game Controllers); `paddle1` | the pad's family |

Why the overlay remaps everywhere, Steam Input included: one model, testable in ctests, and the only option on native Windows and macOS. Where Steam Input runs, it remaps first and the overlay sees its output. The two compose, and the Pad group says so (D6). Hiding the overlay's pad remap under Steam Input was rejected (Q8).

### D2. Windows: an optional SDL3 backend, opt-in for one release

XInput sees XInput devices only. On native Windows, without Steam or DS4Windows, a DualSense, a DualShock 4, a Switch Pro or a GameCube adapter does nothing. XInput also has no paddles, no controller type and no gyro.

**Plan.** `xinput_device.c` gains an SDL3 path for `_WIN32`. It loads `SDL3.dll` with `LoadLibraryW` from the executable's directory and calls SDL through a function-pointer table (about 25 entry points) filled with `GetProcAddress`. The POSIX half cannot simply be reused, because it is `#else /* !_WIN32 */` code built against `<SDL3/SDL.h>`. It also relies on:
- pthread mutexes and condition variables;
- `clock_gettime`;
- `SDL_AddEventWatch` with `SDL_Event`;
- a window thread that pumps SDL (`xbox_InputSdlPadSync` from `fb_present_sdl.c`). The GDI and D3D11 windows never pump SDL.

The Windows path therefore needs:
1. **The vendored SDL3 headers** (zlib), for the types. No import library is needed, because every call goes through the table.
2. **A small thread shim**: `SRWLOCK` and `CONDITION_VARIABLE` for the mutex and condvar, and `QueryPerformanceCounter` for the clock. Shared code stays shared: the slot model, the rescan, `sdl_extra` and `sdl_read_pad` move into a file both halves include, so the POSIX path changes only by that move.
3. **A headless pump**: `SDL_Init(SDL_INIT_GAMEPAD)` with `SDL_HINT_JOYSTICK_THREAD=1`, `SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS=1`, and `SDL_UpdateGamepads` from the input poll, because no SDL window exists. Focus behaviour must be checked: pads must keep reading while the D3D11 window has focus, and must not read state while another app has it, matching XInput.

`input.backend = "xinput" | "sdl" | "auto"` (`RECOMP_INPUT_BACKEND`, a config-tier row in `recomp_env`):
- the default is `"xinput"` for one release, so a stock run is byte for byte today's;
- `"sdl"` tries the DLL and falls back to XInput with one log line;
- `"auto"` (SDL when the DLL loads) becomes the default in a later release, after a release of player reports and the user's OK.

Changing the default changes:
- player numbering and the LEDs (pad-slot-ports owns port 1 either way);
- Guide and Game Bar behaviour;
- trigger scaling (`>> 7`);
- which devices count.

That is why it is opt-in (the "opt-in features default OFF" rule).

**Under Proton** the DLL would run inside Wine and see winebus's devices: Steam's virtual pad, or with Steam Input off the HID devices Wine exposes. Paddles are unlikely to survive winebus's gamepad mapping. The `steamos` bundle's `config.default.toml` therefore pins `input.backend = "xinput"` even after the flip, until a probe (task I6.6) shows a gain.

**Not verified here:** that Guide arrives through SDL's RawInput and XInput correlation on Windows, as SDL's code suggests. The native Windows gate (I6.7) checks it.

**Cost:**
- one zlib DLL in the Windows bundle and a NOTICE line;
- the llvm-mingw cross build of SDL3 at a pinned release, built with the CLI as the Mac's is pinned;
- the shim and the pump;
- a native Windows gate run, which needs the user to boot Windows.

The total is L, about 3.5 to 4 days (task I6).

**Decision (Q1, the user, 2026-10-23):** yes, opt-in for one release, with XInput as the fallback.

### D3. The remap model: upstream #203's `InputPadMap` behind `[input.pad]`

**Decision (Q11): adopt #203's `input_map.{c,h}` unchanged.** This is the rule "upstream first on duplicates", applied:
- The fork's table module is renamed `input_host.{c,h}`. It keeps `xbox_input_map[]`, the README row generator and the deadzone env, and becomes the adapter that fills an `InputRaw` from XInput or SDL.
- Upstream's `xbox_InputMap_PadMap` then produces the Duke state.
- The rename also clears the file clash that the next upstream merge would otherwise hit.
- The adoption is a cherry-pick of `650dfe14` (the pad and deadzone half), or the next upstream merge if one is scheduled first. Phase I2 does not wait on an upstream merge.

The fork's identity is kept without editing upstream's code. The runtime calls `PadMapDefaults` and then sets:
- `source[INPUT_WHITE] = left_shoulder` and `source[INPUT_BLACK] = right_shoulder`;
- `deadzone_left = deadzone_right = 0`;
- `trigger_threshold = 0`.

**Sticks bypass #203's rescale at deadzone 0** (review R2-1). `xbox_InputMap_ApplyStick` always rescales radially: at `dz = 0` it clamps the stick to the unit circle. A full diagonal `(32767, 32767)` comes out as about `(23170, 23170)`, and `-32768` as `-32767`. The fork copies sticks raw: real pads report corners outside the circle, and the title applies its own deadzone.

So after `PadMap`, `input_core.c` overwrites each guest stick whose selected physical stick has deadzone 0 with that raw physical stick:
- the swap is honoured (`left_stick = right` copies the raw right stick);
- `none` stays centred;
- inversion (applied in the adapter) is kept.

This also keeps raw sticks for a player who remaps only buttons. A stick with a non-zero deadzone uses #203's radial rescale as is. This change lives in fork code only, and it is raised upstream together with the White = LB point (I8.3): at 0, `ApplyStick` could pass the stick through.

A ctest pins this identity: every XInput and SDL state maps to exactly what `xbox_InputMapXInput` and `xbox_InputMapSdl` give today. That covers:
- all 256 trigger values;
- the stick extremes, including the corners `(±32767, ±32767)`, `-32768` on every axis, and a swapped stick.

The adapter scales triggers into 0..32767 so that `>> 7` and `ApplyTrigger(v, 0)` give back the same 0..255; the ctest proves that round trip too.

```toml
[input.pad]
# guest control = host source, or a list of up to two; [] unbinds.
# Sources are SDL positional names (upstream's source names).
a = "south"
x = ["west", "paddle3"]
white = "left_shoulder"
left_trigger = "left_trigger"
left_stick = "left"          # which physical stick: left, right or none
right_stick = "right"
dpad_up = ["dpad_up", "paddle1"]
```

**Names.**
- Keys are the `[input.bindings]` control names, which are upstream's (`a b x y white black left_trigger right_trigger start back left_thumb right_thumb dpad_*`, read through `xbox_InputMap_ControlFromName`; input-vocab), so the TOML is consistent, plus the stick keys `left_stick` and `right_stick`.
- Values are upstream's source names only; there are no aliases (input-vocab drops the old spellings). The UI shows the pad's own glyphs (D5).
- `guide` is accepted as a value, with a warning that most hosts keep it.

**Two bindings per control (deviation, by composition only).** Upstream has one source per control. A paddle or a stick direction as a second input for a control is the most common remap request (Zelda64Recomp keeps two). The runtime therefore holds two `InputPadMap`s:
- the primary map;
- an alternate map whose sources and sticks default to none.

It merges their outputs with `xbox_InputMap_PadMerge`. This needs no change to `input_map.c`, and it is not proposed upstream unless asked for.

**Conversions** are upstream's rules, with the open cases settled:

| Case | Rule |
|---|---|
| analog source to trigger | the travel is kept (`ApplyTrigger` with threshold 0 in the identity) |
| button source to trigger or face button | 0 or 255 |
| trigger or stick direction to a digital control | on at `button_threshold`, 50% by default (`input.pad_threshold`). Upstream has no hysteresis, and none is added |
| stick | a whole stick only: `left`, `right` or `none`. A digital source to one stick direction is not in upstream's model and is dropped from v1. It would be a fork extension later, if asked for |
| two bindings on one control | `PadMerge`: buttons OR, the larger analog value, and the stick deflected further by magnitude (destination wins ties) |
| deadzone | with a non-zero deadzone, `ApplyStick` (radial, rescaled) applies to the physical stick inside `PadMap`, before any merge. At 0, the raw stick is written back after `PadMap` (see above). Nothing synthesises a stick |
| invert | `input.pad_invert_ly` and `input.pad_invert_ry` negate the **host** axis in the adapter, before `PadMap`, so a swapped stick keeps its own inversion |

Each row gets a ctest (I2.7).

**Pad options**, file-only like the mouse knobs:
- `input.pad_deadzone_left` and `input.pad_deadzone_right`, in percent 0..95, default 0. These are upstream's units.
- `input.pad_threshold` (percent, default 50).
- The two invert keys.

`RECOMP_PAD_DEADZONE` keeps its integer meaning (0..32767) as a stock-path env. When both are set, the file key wins, and one log line says so. The keys bind no env, so the units never mix.

**Resolution:** the rules of `[input.bindings]`.
- Per control, the highest file that names it wins whole.
- A source that a higher file binds is removed from the controls a lower file gave it, so binding `lb` to `x` takes it off `white`.
- Inside one file, a source named under two controls is reported, and the second is ignored.

**Scope.** One map for all ports in v1 (Q5). Per controller model is rejected: positional names make one map fit every family. Per game, through the bundle's config, and no cross-game file (Q6).

**Where it applies:** in `input_core.c`, on the `InputRaw` the backend fills, for every title. cat's `pad_input.c`, pad-slot-ports and the script merge are unchanged.

**Stock polling stays as it is** (review finding 9). The adapter fills the extras, and the XInput backend calls `XInputGetStateEx`, only while a pad filter is installed or the active map names a source that needs it (`guide`). With no filter and the identity map, XInput uses plain `XInputGetState`, and SDL does not read the extras. The identity ctest asserts which entry point is called.

Why not `Pad*` names inside `[input.bindings]`: the "highest file wins whole" rule would make a player's single pad change drop the game's default keys for that control, and the reverse. Upstream keeps keys and pad apart in the same way.

### D4. Host actions read the physical pad

Today a pad chord names Duke buttons read from the mapped pad, and "host-only" means that the Duke lacks the button. With a remap the two diverge. **Rule:** action bindings name **host sources** (the D3 vocabulary), read from `InputRaw` before the map.

- **Rule 1** ("a single guest button is refused") becomes "a single source that a map gives to a guest control is refused". Rule 2's key check already works this way for keys. A source that is not mapped is free for a single-source action. The paddles are unmapped by default; Back becomes free once a player unbinds it in a game that never uses it.
- **Masking** a consumed chord clears the guest controls that its members feed through both maps, not the members' own Duke bits.
- **Guest names in chords:** a chord member written as a guest control (`white`, `black`, `left_trigger`, `a`, `left_thumb` ...) means the source the identity gives that control. Old spellings (`ltrigger`, `lthumb` ...) are not read (input-vocab); they log `unknown name`.

**Re-classifying after a map change** (review findings 5 and R2-2). Each chord's kind is derived from the current map at every `enhance_actions_rebuild`, which runs on load and on every live map change. It no longer depends on the order the player wrote the members in.

- **All members unmapped:** a host-only chord, as today. Nothing reaches the game.
- **All members mapped, with a hold of 200 ms or more:** a guest chord (rule 1, consumed after its hold, rule 3).
- **All members mapped, with no hold or a hold under 200 ms:** **inactive**, with a warning naming the control or controls that took its members. For example, `guide+a` once a player maps `guide`, or `paddle1+a` once `paddle1` is mapped. This is rule 1 applied after the fact.
- **Some members mapped, some unmapped:** a modifier chord. The unmapped members are its modifiers. `B_MOD`'s single `modbit` becomes a **mask**, so two or more unmapped members are all modifiers and all must be held. The parser's modifier path accepts any number of host members, and the old "host-only member must be first" refusal goes away.
  - **Press order** is rule 7's and stays: every modifier must be down before the first guest member goes down. A guest member pressed earlier reaches the game, and that press does not complete the chord, because a press already delivered cannot be taken back.
  - **The hold** keeps its meaning: the chord fires once all members have been down together for `@N` ms. Without `@N` it fires on the guest member's press, as today.
  - The Controls page row shows the order, for example "hold (L3), then (Back)".
  - `back+left_thumb@400` therefore stays valid whether Back, `left_thumb`, both or neither are mapped. Only its kind changes, and with it which button is pressed first.
- **A single member that becomes mapped:** the binding goes inactive, with a warning naming the control that took it.

In the Controls page none of these happens silently. D8's cross-group prompt names every chord that would go inactive or change kind, and the new press order.

Each change of kind logs one line. ctests in `input_actions` cover:
- every transition above, with `paddle1` mapped, unmapped and remapped;
- a chord with two unmapped members;
- `guide+a` going inactive once `guide` is mapped;
- the press order: a guest member pressed first passes through and the chord does not fire;
- the `@N` hold of a derived modifier chord.

`struct xbox_host_pad` gains `InputRaw raw` beside the mapped `pad`, so the pad filter API changes only by addition.

### D5. Glyphs and controller family

`xbox_InputPadFamily(slot)` returns `xbox | playstation | nintendo | steam | generic`:
- **XInput:** `xbox`. XInput cannot tell Steam's virtual pad from a real pad.
- **SDL3,** from `SDL_GetGamepadType`:

  | `SDL_GetGamepadType` | Family |
  |---|---|
  | `STANDARD`, `XBOX360`, `XBOXONE` | `xbox` |
  | `PS3`, `PS4`, `PS5` | `playstation` |
  | `NINTENDO_SWITCH_*`, `GAMECUBE` | `nintendo` |
  | `STEAM`, or VID:PID 28de:1205 (the Deck's own pad) | `steam` (Deck and Steam Controller glyphs) |
  | `UNKNOWN` | `generic` |

  This table is a mapping, not detection, so 28de:1205 is fine here.

`input.glyphs = "auto" | "xbox" | "playstation" | "nintendo" | "steam"` (default `auto`) overrides the family. Until I1.3's probe runs, this is what ships for the Deck and for Proton: `auto` shows Xbox there, and the player can choose `steam`.

Glyph art (Q7, decided): Kenney's "Input Prompts" (CC0), baked into the overlay atlas at 3E. The audit allow-list names the files, as it does the Atkinson font.

**Nintendo pads:** the map is positional, so the east button is the guest's B, and its glyph reads "A", which is the label on the pad. The page is therefore truthful. But menu confirm on the south button and back on the east button is the reverse of what a Switch player expects. This is a known choice, stated in D8, not an oversight.

### D6. Steam Input: a shipped template, and honest detection

**Template.** A shortcut cannot ship an official config. The `steamos` package, and the `linux` one when it exists, gains `steam-input/<slug>_neptune.vdf`, one template per game.
- The base layout is **Gamepad with Mouse Trackpad** for a game whose defaults enable the mouse (BLiNX 2: the right trackpad drives its mouse look), and **Gamepad** otherwise. The CLI picks it from the game's `config.default.toml` `[input] mouse`.
- The face buttons, sticks and triggers keep Steam's stock layout.
- The template supersedes the overlay spec's follow-up F-6 ("grips to F10 and F6").

Its grips:

| Grip | Binding | Why |
|---|---|---|
| R4 | keyboard `F10` | `menu.open`'s default; reaches Proton and native |
| R5 | keyboard `F6` (BLiNX 2) | `[camera] free_toggle`. It does nothing unless the player sets `free = "on"`, so it is harmless by default. Other games: none, or their own key |
| L4 | **not bound until save-states task 4.0 lands**, then `F5` (quick save) | today F5 is BLiNX 2's `camera.free_reset_key` (only while flying) |
| L5 | **not bound until 4.0**, then `F9` (quick load) | today F9 is `input.mouse_release_key`, so it would free the cursor |

`install.sh` copies the template into `~/.steam/steam/controller_base/templates/` (the RetroDECK precedent) and prints one line: in the game's Controller settings, pick Templates > "<Game> (recommended)". It re-copies the file on every install, because a Steam update can clear the directory.

Writing the per-shortcut layout directly was rejected: it means editing Steam's state under a computed shortcut id while Steam may run (Q3, decided).

**Detection** (review finding 2):
- **SDL hosts:** the pad is Steam's virtual pad when `SDL_GetGamepadSteamHandle(pad) != 0` or its VID:PID is 28de:11ff. The VID alone is never used. On a native Deck with Steam Input off, the built-in pad (28de:1205) is therefore correctly *not* flagged, which is exactly the case where `paddle1` works. `xbox_InputSteamInput(slot)` returns `on`.
- **Proton (XInput):** the pad cannot be told apart. When `SteamGameId` or `SteamDeck` is set, `xbox_InputSteamInput` returns `maybe`.
- **Reads:** these two are host variables, not `RECOMP_*` keys. They are read through two config-tier rows in the toolkit's `recomp_env` table under their own names, marked "set by Steam, read only" and documented in `cat/docs/env.md`. If the table requires the `RECOMP_` prefix, the row format gains an explicit full-name field. No raw `getenv` is used.

The Pad group's line:
- for `on`: "Steam Input is on: its layout applies first; change it in Steam > Controller settings";
- for `maybe`: "Steam may apply its layout first".

The overlay never reads Guide on the Deck (it is never delivered), and it binds nothing to `...` or to Steam chords. Steam+A, which is screen recording on the Deck, never reaches the game.

### D7. Default overlay bindings

`menu.open` defaults to `["F10", "guide+a", "paddle1"]` in the toolkit, and each game adds one fallback chord (Q2, decided). The tracker item lands first (Q10).

| Candidate | Verdict |
|---|---|
| `F10` | **keep**. It works everywhere a keyboard or a Steam Input key binding exists |
| `guide+a` | **keep**. It is a modifier chord, so the game never sees the A. Desktop hosts that hand Guide over fire it. Where Guide is kept (Deck, Steam Input on, Game Bar on), it never completes |
| `paddle1` | **add**. It is the Elite's P1, the Deck's R4, the DualSense Edge's right back button and a right Joy-Con's SR (on the rail), and it is unmapped by default. Elite firmware profiles that copy a face button report the face button, which is mapped, so there is no clash |
| `guide` alone | **reject**. Game Bar, Steam Big Picture and macOS Launchpad act on the same press |
| `back+start@600` | **reject as a default**. START pauses BLiNX 2 before the chord completes (rule 3); a game may still pick it |
| `left_thumb+right_thumb@400` | **offer** as a suggestion in the Controls page; not a default (some games use both clicks) |
| Steam chords | impossible: Steam keeps them |
| A game fallback chord | **per game**. BLiNX 2: `back+left_thumb@400`, valid under any map (D4). JSRF and Burnout 3 each pick two buttons they ignore on a lone press |

### D8. The Controls page flow (overlay 3D.3, extended; overlay phase 9 folded in)

The page has three groups, each a scrolled list:
1. **Pad:** one row per guest control, as "<game label>: <glyphs of its sources>", with up to two cells per row (primary and alternate), for example "Jump: (A) (R4)". The D6 line heads the group when Steam Input is `on` or `maybe`.
2. **Keyboard and mouse:** the same rows for `[input.bindings]`, plus the mouse items that 3D.3 already specifies.
3. **Host actions:** the existing 3D.3 rows (`menu.open`, `overlay.stats`, `shot.window`, mod actions), plus quick save and quick load (`state.save`, `state.load`, registered by save-states with `[states]` defaults; Q12).

**Capture** (review finding 6):
1. Select a cell (confirm on the pad, or a click). The cell reads "Press an input... (Esc, or hold Start+Back: cancel)".
2. Capture arms only after every input that is down has been released, so the confirm press is never captured.
3. A single input is taken **on its release**, if it was the only new input down. Holding Start and Back together for 1 s cancels instead, so every source, Back and Start included, stays bindable alone. A trigger or stick direction counts past 0.6 (the dominant axis).
4. The Keyboard group takes a key or a mouse button. The Host actions group takes a key, a source, or a chord: inputs held together for 400 ms, as 3D.3 has it.
   - **Start+Back is reserved for cancel and is never captured as a chord** (review R2-3). It is already rejected as a default (D7). When exactly Start and Back are the inputs held, the 400 ms chord capture does not fire. At 1 s, capture cancels. Released earlier, the row shows "Start+Back is reserved for cancel" and capture stays armed.
   - Start+Back is still accepted when typed into `[input.actions]` in the file, where no capture is involved.
   - A chord containing Start, Back and another input is captured normally.
5. Capture times out after 5 s with no input.

**Conflicts across groups** (review finding 5). Before a change is applied, the page checks the new state of all three groups together:
- **Within one group:** "(LB) is on Pick up. Swap / Cancel". Swap is the default, because it keeps every control reachable. "Add here too" exists only in Host actions, because an action and the game can never share a source (rules 1 and 2).
- **Pad against Host actions:** mapping a source that an action uses alone (for example `paddle1` for `menu.open`) prompts: "(R4) opens the menu. Map it anyway (the menu keeps F10 ...) / Cancel". The prompt lists the bindings that would remain. A chord whose kind would change (D4) is named in the prompt.

**Never locked out** (review finding 5):
- The menu navigates on raw inputs that no remap touches: D-pad or left stick to move, the south button to confirm and the east button to go back (Nintendo note in D5), plus the arrows, Return and Esc.
- A **deliverability check** runs on every live apply, on menu close and on Save. `menu.open` must keep at least one binding that this host can deliver. A change that would leave none is refused, with the reason in the row, so the menu stays reachable without a restart. What counts:
  - **a key**, when a keyboard has been seen this session, or when `xbox_InputSteamInput` is `on`, because then a Steam Input key binding is likely;
  - **a source**, when it is unmapped and present on a connected pad;
  - **a chord**, when it is active (D4) and its members are present.
- **`maybe` is not trusted for keys** (review R2-5). Under Proton, `xbox_InputSteamInput` is `maybe` on every Deck run, even when the player never picked the template, so F10 may never arrive. With `maybe` and no keyboard seen, keys do not count. The binding that must survive is then a pad binding: the game's fallback chord, or `guide+a` off the Deck. A change that would deactivate the last such chord is refused, for example a remap that makes `back+left_thumb@400` all-mapped with a too-short hold, or one that maps all its members away.
- ctests in `enhance_menu` cover:
  - a Deck-like native host: no keyboard seen and `paddle1` only, so mapping `paddle1` is refused;
  - a Proton `maybe` host with no keyboard seen: a remap that deactivates the fallback chord is refused, even though F10 is bound;
  - a desktop host: F10 is left, so mapping is allowed;
  - the chord-kind prompt.

**Reset:** "Reset row" (back to the highest lower file, which is the game's defaults) and "Reset group". Changes apply at once (`enhance_actions_rebuild` and a map swap at the next poll) and are written by Save as differences only (`recomp_cfg_patch`, 3D.5).

**Test strip:** at the foot of the Pad group, a live readout of the guest Duke state, as the game will see it.

### D9. Labels: game data in config

The Pad group needs the game's words for the controls. `config.default.toml` gains `[input.labels]` (`a = "Jump"`, `x = "Attack"`, `left_stick = "Move"`, ...).
- It is read-only data: a label in the player's file is ignored with a warning, and Save never writes one.
- A control with no label shows its Duke name.
- Labels live in config, not in a C call, so that JSRF and Burnout 3 can add them without code, beside their default bindings.
- Each game's labels come from its own manual or HUD, written by hand.

### D10. Gyro (later, opt-in; Q9 decided)

`input.gyro = "off" | "right_stick"` (default `off`), with:
- `input.gyro_sensitivity`;
- `input.gyro_hold`, a source that enables the gyro while held, or `""` for always on;
- `input.gyro_invert_y`.

It runs on SDL hosts only, plus Windows with D2's SDL path. The gyro rate becomes a right-stick deflection, merged with `PadMerge`, with the same 0.41 floor as the mouse. On the Deck under Steam Input, the virtual pad has no gyro, and Steam's own gyro-to-stick setting is the answer there; the template leaves it off. It sits behind `XBOXRECOMP_ENHANCE`, and goldens never use it.

### D11. Toolkit and game split; upstream fit

| Part | Lives in | Upstream verdict | Why |
|---|---|---|---|
| `input_map.{c,h}` (#203) | toolkit `src/input` | **upstream's**, adopted unchanged | the rule "upstream first on duplicates" |
| `input_host.{c,h}` (the fork's table, renamed) and the `InputRaw` adapter | toolkit `src/input` | **conform**. It is the backend glue that #203 leaves to "a port that calls it" and could be offered | it wires #203 into `xinput_device.c` |
| The fork's identity settings (White = LB, deadzone 0, trigger threshold 0) and the raw-stick write-back at deadzone 0 | toolkit `input_core.c` | **argue upstream** that `PadMapDefaults` should say White = LB, which upstream's own README says is right, and that `ApplyStick` at 0 should pass the stick through. Until then, fork-only code after `PadMapDefaults` and after `PadMap` | Microsoft's and xemu's convention; the title applies its own deadzone; real pads report corners outside the circle |
| The alternate map merged with `PadMerge` | toolkit `input_core.c` | **fork-only** unless asked | composition, with no change to #203 |
| Raw host state in `host_pad.h` (`InputRaw`) | toolkit | **fork-only** while the actions layer is | it serves `enhance_actions` |
| The `[input.pad]` parser, `[input.labels]`, `input.glyphs`, Steam detection | toolkit `src/enhance` and `src/input` | follows the enhancements layer (fork-only today) | the TOML layer is the fork's |
| `xbox_InputPadFamily` | toolkit `src/input` | **conform** | small and useful without the overlay |
| The SDL3-on-Windows loader | toolkit `xinput_device.c` | **argue upstream**. Upstream says "no other external dependencies"; a run-time-loaded optional DLL with an XInput fallback keeps the build free of them | Q1 decided: opt-in |
| The Controls page and the glyph strip | toolkit overlay | with the overlay | |
| Gyro | toolkit `src/input` + `src/enhance` | **fork-only** at first | an enhancement |
| The Steam Input template, the `install.sh` step, `SDL3.dll` in the Windows bundle | CLI package templates | not toolkit | packaging |
| `[input.labels]`, the fallback chord, any non-identity `[input.pad]` default | each game's `config.default.toml` | game | |

Upstream PRs wait for stable releases of BLiNX 2, B3 and SSX 3. The Burnout 3 gate applies to every toolkit part: B3 reads `xbox_InputGetState`, so the map applies to it with no B3 code change. Its build and a menu run confirm the identity there.

### D12. Testability

- **ctest `input_map`:** upstream's #203 test, adopted as is.
- **ctest `input_host`:** the fork's former `input_map` test, renamed. It adds:
  - the identity through `PadMap` and the raw-stick write-back equals the old helpers, for every XInput and SDL state class: all 256 trigger values; the corners `(±32767, ±32767)`; `-32768` on each axis; a swapped stick;
  - a stick with a non-zero deadzone goes through #203's rescale;
  - inversion of `-32768` gives `32767`;
  - the direction sources are the half-axis magnitudes;
  - which XInput entry point is called with and without a filter or `guide` in the map.
- **ctest `input_pad_map`:**
  - each D3 conversion row;
  - the alternate map merged by magnitude;
  - inversion before a stick swap;
  - resolution across three files, including a conflicting source inside one file;
  - `[]` unbinds;
  - old names refused with a log line.
- **ctest `input_actions`,** extended:
  - host-space rule 1;
  - guest control names in chords, and old spellings refused;
  - masking through both maps;
  - every chord-kind transition (D4);
  - the `paddle1` default.
- **ctest `input_hotplug_sdl`:**
  - an `SDL_VirtualJoystickDesc` per family (including GameCube and 28de:1205) gives the D5 family;
  - a virtual 28de:11ff gives Steam Input `on`, and 28de:1205 does not;
  - paddles fire `paddle1`.
- **ctest `enhance_menu`** (3D.8), extended:
  - capture on release and the timeout;
  - the Start+Back cancel, including in Host actions: never captured as a chord, cancel at 1 s, and the message on an early release;
  - swap, the cross-group prompt and reset;
  - Save of `[input.pad]` as differences only;
  - the deliverability cases (D8).
- **ctest for the Windows SDL3 loader,** under `tests/proton_run.sh`: a missing DLL falls back to XInput, with the line. The real-device check, Guide included, is the native Windows gate.
- **Goldens:** `RECOMP_CONFIG=none` gives the identity map, plain `XInputGetState`, no labels and `hook=off`, so frames and logs are unchanged.

## Risks / Trade-offs

- **The rename of the fork's `input_map` touches every include site.** It is mechanical, and done in one commit with the ctests. The payoff is no clash at the next upstream merge.
- **Upstream changes #203 again before we adopt it.** We pin the cherry-pick sha, and any later upstream change arrives through the normal merge.
- **Steam Input and the overlay both remap, and the player is confused.**
  - The Pad group's line names Steam as first.
  - The test strip shows the result.
  - The template keeps Steam's face buttons stock.
- **A remap makes the overlay unreachable.** Navigation uses fixed raw inputs, and the deliverability check runs live (D8).
- **Under Proton, Steam Input is only `maybe`,** so the game cannot know whether F10 is bound to a grip. The check therefore protects the last pad fallback chord whenever no keyboard has been seen (D8). The remaining risk: a player who removes the fallback chord in the file, with no keyboard and no template, has no menu until they edit the file or pick the template. The Steam line in the Pad group and the README step point at the template.
- **Derived modifier chords are order-sensitive** (rule 7). A player used to `back+left_thumb` pressing Back first gets Back in the game when Back is mapped. The Controls page row shows the order, and the log line on a change of kind says which button goes first.
- **SDL3 inside Wine misbehaves.** The `steamos` bundle pins `input.backend = "xinput"` (D2).
- **The headless SDL pump on Windows reads pads while the game is unfocused,** or misses events. Hints and an explicit focus gate are planned, and the native gate checks both.
- **Templates in `controller_base/templates` disappear on a Steam update.** `install.sh` re-copies them, and the README keeps the manual "bind R4 to F10" fallback.
- **Glyph art licence.** Kenney's prompts are CC0, and the audit allow-list names them.

## Decisions taken (the user, 2026-10-23: "all recommended")

The user gave this answer before the review's changes. The revised wording is recorded with it.
- **Q1:** SDL3 on Windows, **opt-in for one release** (`input.backend = "xinput"` default), loaded at run time with XInput as the fallback. This follows the opt-in rule. The flip to `auto` comes later, with the user's OK.
- **Q2:** `F10`, `guide+a` and `paddle1` in the toolkit, plus one fallback chord per game. The DualSense Edge fact is corrected (D7).
- **Q3:** `install.sh` installs a Steam Input template, and the player picks it once.
- **Q4:** R4 = `F10` is accepted. The user wants L4 = quick save and L5 = quick load. That stays the target, but they are bound only once save-states task 4.0 frees F5 and F9; until then the template leaves L4 and L5 out. R5 = `F6` for BLiNX 2 and the base template (D6) were added by the review. **Needs the user's confirmation.**
- **Q5:** one pad map for all ports in v1.
- **Q6:** remaps per game, through the bundle's config; no cross-game file.
- **Q7:** Kenney's CC0 input prompts.
- **Q8:** under Steam Input the overlay's pad remap stays on, with the D6 line.
- **Q9:** gyro as a later opt-in phase (I7).
- **Q10:** merge the tracker item (`paddle1` default and the Deck docs) as the first step (I1.2).

- **Q11 (the user, 2026-10-23: "yes"):** adopt upstream #203's `input_map.{c,h}` unchanged and rename the fork's table module to `input_host`, the adapter (D3). The deviations, each kept outside #203's code, are:
  - **White = LB and Black = RB**, set after `PadMapDefaults`. This is Microsoft's and xemu's convention, the fork's fix of `7618629b`, and what upstream's README says. It is argued upstream.
  - **Deadzones 0 and trigger threshold 0** in the runtime's identity, because the title applies its own deadzone and goldens must not move.
  - **Raw sticks at deadzone 0:** after `PadMap`, a stick with deadzone 0 is overwritten with the raw selected physical stick, honouring the swap. #203's `ApplyStick` clamps to the unit circle even at 0 (review R2-1). This is raised upstream with the White = LB point.
  - **An alternate map merged with `PadMerge`,** for two bindings per control.
  - **Inversion of the host axis in the adapter,** because #203 has no inversion.
  - **`[input.pad]` keys use the `[input.bindings]` control names,** for one vocabulary in the TOML. Since input-vocab those are upstream's names; there are no aliases.
  - **Stock polling kept** (plain `XInputGetState` without a filter), because #203 has no device code.
  - **Dropped in v1, to stay inside #203's model:** digital sources driving one stick direction, and threshold hysteresis.
- **Q12 (the user, 2026-10-23: "yes"):** quick save and quick load go through save-states' `[states]` table. Save-states registers `state.save` and `state.load` through `enhance_action_register`, and `[states]` gives their default keys (`F5`, `F9`). The Controls page, `[input.actions]` and the template therefore agree. This is noted for the save-states spec (task I5.7).

## Open Questions (for the user)

- **Q4 confirmation:** R4 = `F10`; L4 and L5 left out until save-states task 4.0, then `F5` and `F9`; R5 = `F6` for BLiNX 2; base template Gamepad with Mouse Trackpad for BLiNX 2.
