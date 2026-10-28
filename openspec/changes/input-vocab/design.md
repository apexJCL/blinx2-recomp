## Context

Upstream's `src/input/input_map.c` (v0.16) defines `InputControl` in Duke order (the eight `wButtons` bits, then the eight analog buttons A, B, X, Y, BLACK, WHITE, LEFT_TRIGGER, RIGHT_TRIGGER, then the stick directions) and the name functions over it. The fork's `input_names.c` had a parallel enum (`XBOX_CTL_A` first) and its own key table. Both encode keys as Win32 virtual-key codes, so the key side differs only in spelling.

## Decisions

1. **Upstream's enum is the control index.** The bindings table, `enhance_input.c` and `enhance_actions.c` index by `InputControl`; `control_bit` derives the `wButtons` bit (`1 << ctl` for the first eight) and the analog index (`ctl - INPUT_A`, which is the Duke's `XBOX_BUTTON_*` order). No second enum, no mapping table.
2. **Upstream's key names, plus three.** `xbox_InputNameToCode` tries the fork's extras first (`numpadenter` 0x0E, `wheelup`, `wheeldown`), then `xbox_InputMap_KeyFromName`. The fork keeps mouse buttons as their own input kind (codes 1..7), because the bindings and `kbm_script` treat them apart from keys; `mouse1`..`mouse5` arrive from upstream as VK 1, 2, 4, 5, 6 and are turned into that kind. Upstream's aliases (`return`, `esc`, `control`) stay, since they are upstream's own; the fork's old spellings get none (the user's decision).
3. **The trace prints the canonical name** (`xbox_InputMap_KeyName`: `A`, `F1`, `Numpad0`, the rest lower case). A player who copies a traced name into the file gets a name the parser takes.
4. **Host-only buttons are upstream sources.** `guide`, `misc1`, `paddle1`..`paddle4` and `touchpad` already were upstream's `InputSource` names; they are now read through `xbox_InputMap_SourceFromName` rather than a fork table.
5. **The pad table speaks the same words.** `pad_map.c`'s host column names the SDL/XInput control by its upstream source name, and the README row adds the Duke control's upstream name, so `[input.bindings]`, the actions and the pad table use one vocabulary. The test checks every host token is a source upstream knows.
6. **Out of scope, kept as is:**
   - the `RECOMP_PAD_SCRIPT` / `RECOMP_PAD_LIVE` grammar (`lt`, `lthumb`, `lleft`, `p2-`): upstream's harness syntax, used by every golden scenario; renaming it would break the goldens and is not a player config;
   - LB drives WHITE and RB drives BLACK, as before. Upstream's `PadMapDefaults` maps `left_shoulder` to BLACK; whether the fork follows is a behaviour change for a separate item;
   - upstream's `keyboard_map` README labels ("Up arrow", "D-pad up").

## Risks

- **Silent loss of a player's custom line.** Mitigated by the one-line log per unknown name (unchanged behaviour) and the CHANGELOG table.
- **CapsLock on macOS.** SDL reports Caps Lock as a toggle there (down on lock, up on unlock), so a `capslock` binding holds its control until the next press. Upstream's name is exposed as-is; noted in the handback, no workaround.
