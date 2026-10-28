## Why

**Spike (design only; nothing here is implemented).** The tracker item, branch `spike/input-ux` off cat `a93c649`, toolkit `posix-host/portability` `43327b8e`, 2026-10-23.

Revision 2 applies the review and the user's answers: Q1-Q12 are decided. Only the details of Q4 (the template's grips) wait for confirmation.

On 2026-10-23 the user asked for a plan for modern gamepads on every port (BLiNX 2, Burnout 3, JSRF) in place of wiring one Deck paddle to the overlay. Their idea: on PC and macOS the overlay menu does the remapping, and on the Steam Deck Steam Input's own UI does it.

What a player has today (toolkit `43327b8e`):

- **Keyboard and mouse:** done. `[input.bindings]` in the TOML config remaps keys and mouse inputs to the Duke's controls on every window (GDI, D3D11, SDL). The parked spike `input-selection` (cat `e09b325`, 2026-10-03) found the keyboard dead in D3D11 and SDL windows. That is no longer true: `keyboard.c`, the D3D11 `WM_KEY*` feeder and `keyboard_sdl.c` landed later.
- **Pad remapping:** none in the fork. A pad reaches the Duke through the fixed `input_map.c` table only. Upstream #203 (`4f887107`, 2026-10-19, not in the fork yet) adds a pure pad-remap model (`InputRaw`, `InputPadMap`, `xbox_InputMap_PadMap`) in a file with the same name. On Proton, Steam Input can remap. On macOS, native Windows and Linux without Steam, a player cannot remap at all.
- **Host actions:** `[input.actions]` (phase 3A) binds `menu.open`, `overlay.stats` and mod actions to keys, to host-only buttons (`guide`, `paddle1..4`, `misc1`, `touchpad`) and to chords. The defaults are `F10` and `guide+a`.
- **Steam Deck:** `guide+a` can never fire. SteamOS keeps the Steam button, and Steam+A starts and stops recording there anyway. The Windows exe reads pads through XInput, which has no paddles, so R4 never reaches it (findings). The one working path is a Steam Input binding of a grip to F10.
- **Windows native:** XInput only. A DualSense, a Switch Pro or an 8BitDo in Switch mode does nothing unless Steam or DS4Windows runs. No paddles reach the game, and the controller type is unknown, so there are no glyphs.
- **macOS, and Linux once `linux-native-vulkan` lands:** SDL3. It already sees the paddles, the controller type and the gyro, but uses only the paddles, and those only as host actions.

## What Changes

- **A pad map in the toolkit, `[input.pad]`, on upstream #203's model** (Q11). The fork adopts #203's `input_map.{c,h}` unchanged and renames its own table module to `input_host`, which becomes the adapter that fills `InputRaw`.
  - Each guest control takes up to two host sources: #203's map, plus an alternate map merged with `PadMerge`.
  - It uses the TOML config and the layering and resolution rules of `[input.bindings]`.
  - The runtime's identity keeps the fork's White = LB, deadzones of 0 and no trigger threshold, so a file with no `[input.pad]` changes nothing, and stock polling stays as it is.
  - It runs on every host and backend, under Steam Input or not.
  - One map serves all four ports in v1.
  - Design D3 lists each deviation from #203 with its reason.
- **Host actions read the physical pad.** A host button that the pad map gives to no guest control is free for actions, as the paddles are today. "Host-only" becomes "not mapped to the game", so a player can, for example, take Back away from a game that never uses it and open the menu with it.
- **The overlay's Controls page remaps** (extends overlay 3D.3 and absorbs phase 9). It has three groups: Pad, Keyboard and mouse, Host actions. A row is captured by pressing the input. Conflicts are checked across groups, so a pad remap cannot silently take an action's button. Swap is the default. Each row and the whole page can be reset, and changes apply at once and are saved as differences only. Menu navigation runs on fixed raw inputs. A change that would leave `menu.open` with no deliverable binding is refused live, not only at Save, so no remap can lock the player out.
- **Glyphs by controller family.** The toolkit reports a family per slot: SDL3's `SDL_GetGamepadType`, Xbox for XInput, and an override key `input.glyphs`. The overlay draws Xbox, PlayStation, Nintendo or Steam Deck labels. Game config supplies the controls' labels ("Jump"), so the page reads "Jump: A".
- **Steam Input stays in charge where it runs.**
  - **Detection:** on SDL, the pad is Steam's virtual pad when it has a Steam handle or is 28de:11ff, never the Valve vendor id alone, because the Deck's own pad is 28de:1205. Under Proton the answer is only "maybe", from `SteamGameId` or `SteamDeck`, which are read through `recomp_env` rows.
  - **The Pad group** then says that Steam's layout applies, or may apply, first. Remapping stays allowed.
  - **The template:** the SteamOS and Linux packages ship a Steam Input template per game, with R4 = F10 (menu) and, for BLiNX 2, R5 = F6 (free camera). L4 and L5 become quick save and quick load (F5 and F9) once save-states task 4.0 frees those keys. The base layout is Gamepad with Mouse Trackpad when the game uses the mouse. `install.sh` installs it, and the player picks it once. This supersedes the overlay's follow-up F-6.
- **Quick save and load are actions** (Q12). Save-states registers `state.save` and `state.load`, with `[states]` giving the default keys, so the Controls page, `[input.actions]` and the template agree.
- **Default overlay bindings:** `F10`, `guide+a` and `paddle1` in the toolkit (`paddle1` is the Deck's R4, the Elite's P1 and the DualSense Edge's right back button; the tracker item `74fd70e9`). Each game adds its own two-button fallback chord with a hold (BLiNX 2: `back+left_thumb@400`). Guide alone, Back+Start and Steam chords are rejected (design D7).
- **Windows: an optional SDL3 input backend, opt-in for one release** (Q1; design D2).
  - The player opts in with `input.backend = "sdl"`. The game then loads `SDL3.dll` from the bundle at run time through a function-pointer table, and falls back to XInput when the DLL is missing.
  - It brings PlayStation and Switch pads, paddles, glyph types and gyro to native Windows.
  - The default stays `"xinput"` until a later release, which needs the user's OK.
  - The build needs the vendored SDL3 headers, a thread shim and a headless SDL pump, because the GDI and D3D11 windows never pump SDL. Size L, about 3.5 to 4 days.
  - The Proton route stays on XInput with Steam Input.
- **Gyro, later and opt-in:** `input.gyro = "off" | "right_stick"` on SDL hosts, off by default. On the Deck, Steam Input's gyro already works.

## What this keeps, changes and drops from `input-selection`

| `input-selection` (e09b325) | Status here |
|---|---|
| D1 backends behind the seam | **kept**; Windows gains an optional SDL3 backend (D2) |
| D2 per-port sources, GUID pins | **deferred**: pad-slot-ports (first press takes player 1) covers the common case; pins wait for a request |
| D3-D5 keyboard switch, one key table, WASD with ramps | **landed** (keyboard.c, D3D11 and SDL feeders, BLiNX 2 `config.default.toml`) |
| D6 `input.ini`, `RECOMP_INPUT_CONFIG` | **dropped**: the TOML config (`config-layering`) and `RECOMP_CONFIG=none` replaced it |
| D7 SDL hot-plug | **landed** (then pad-slot-ports) |
| D8 pad rebinding layered on `input_map` | **kept and widened**: `[input.pad]` in TOML on upstream #203's model, on every host, not only macOS and bare umu |
| D9 no in-game UI | **reversed**: the overlay exists (3B), and the Controls page remaps |
| D10 XInput on Windows | **changed**: an optional SDL3 backend, opt-in for one release, with XInput as the fallback (Q1) |
| D11 toolkit/game split, upstream verdicts | **kept**, re-done for the new parts (design D11) |
| D12 deterministic goldens | **kept**: `RECOMP_CONFIG=none` means the identity map and no actions |
| Open Q1, Q2, Q4, Q6 | answered by work that landed (keyboard on in BLiNX 2's defaults, WASD, config layering, the overlay) |
| Open Q3 (unplug behaviour), Q7 (macOS host-pad default) | left where they are; not input UX |

## Capabilities

### New Capabilities
- `input-remap`: the pad map (`[input.pad]` on #203), the physical-pad rule for host actions, the controller family and glyph key, the Steam Input detection, the Controls page's remap flow, and the optional SDL3 backend on Windows.

### Modified Capabilities
- `input`: where pads map to the Duke (the configured map in place of the fixed table) and the optional SDL3 backend on Windows.
- `enhance-menu` (enhance-menu-preview, 3D.3 and phase 9): the Controls page gains the Pad and Keyboard groups and glyphs.

## Impact

- **toolkit:** `src/input/input_map.{c,h}` taken from upstream #203, the fork's table renamed to `input_host.{c,h}` (the `InputRaw` adapter), `host_pad.h` (`InputRaw` beside the mapped pad), `input_core.c` (identity, alternate map), `xinput_device.c` (family and Steam detection per slot; SDL3-on-Windows behind `input.backend`), `recomp_env` rows for Steam's variables, `src/enhance/enhance_input.c` (`[input.pad]`), `enhance_actions.c` (host-space rules), the Controls page in `enhance_menu.c`, a glyph strip in the overlay atlas, `docs/runtime/config.md`, the ctests `input_map` (upstream's), `input_host`, `input_pad_map`, `input_actions`, `input_hotplug_sdl` and `enhance_menu`.
- **CLI:** the steamos and linux package templates gain a `controller_neptune` template and an install step. The Windows package optionally ships `SDL3.dll` (zlib, NOTICE).
- **cat, b3 and jsrf:** `config.default.toml` `[input.labels]` and the game fallback chord. Save-states registers its two actions (Q12). Nothing in `pad_input.c`: the map is applied before the title's glue sees the pad.
- **goldens:** unchanged (`RECOMP_CONFIG=none`: identity map, `actions hook=off`).
