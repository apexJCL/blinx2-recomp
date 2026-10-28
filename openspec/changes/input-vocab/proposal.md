## Why

The tracker item. The fork's input layer grew its own names for the Duke's controls (`ltrigger`, `lthumb`, `lstick_up`) and for keys (`KP8`, `KPEnter`, `LBracket`, `MouseLeft`) before upstream xboxrecomp had any. Upstream v0.16 now ships a binding vocabulary in `src/input/input_map.c` (`xbox_InputMap_ControlName`, `KeyFromName`, `KeyName`, `SourceName`): `left_trigger`, `left_thumb`, `left_stick_up`, `numpad8`, `leftbracket`, `mouse1`, and source names such as `south` and `left_shoulder` for host pad controls. Two vocabularies for the same thing in one toolkit mean two tables to keep in step, two sets of docs, and config files that read differently in the fork and upstream.

The user's decision (2026-10-24): take upstream's names everywhere (toolkit, games, packaging defaults, docs), read no old name in player configs (no translation, no aliases), and say so in the release notes with the old-to-new table.

## What Changes

- **Toolkit (`feat/input-vocab` off `posix-host/portability`):**
  - `src/input/input_names.{c,h}` drop the fork's `XBOX_CTL_*` enum and name table and run on upstream's `InputControl` and `input_map.c` functions. The fork keeps only what upstream lacks: `numpadenter` (keypad Enter, code 0x0E), `wheelup` and `wheeldown`, the mouse buttons as their own input kind, and the host-only buttons (`guide`, `misc1`, `paddle1`..`paddle4`, `touchpad`), now named through `xbox_InputMap_SourceName`.
  - `enhance_input.c`, `enhance_actions.c` and `keyboard.c` use `INPUT_*` and `xbox_InputMap_Control*`. The trace and the warnings print upstream's canonical key name (`[KEY] down enter`, `'lalt'`).
  - `keyboard_sdl.c` maps `SDLK_PAUSE` and `SDLK_CAPSLOCK`, so upstream's `pause` and `capslock` bind on SDL hosts as on Win32.
  - `pad_map.c`'s host column uses upstream's source names (`south`, `left_shoulder`, `left_stick_click` ...), and the generated README table gains a Control column with upstream's control name.
  - Tests: `input_bindings`, `enhance_cfg`, `input_actions`, `input_keyboard_sdl`, `pad_map` move to the new names and check that the old ones are refused.
  - Docs: `src/input/README.md`, `docs/runtime/config.md`.
- **cat:** `packaging/config.default.toml`, `docs/input.md` (with an "Old names" table), the `docs/env.md` rows, `scripts/test_config_default.py` (a new check that every bound control and key is an upstream name), and the CHANGELOG's breaking-change entry.
- **b3, skates:** a CHANGELOG entry. Neither ships `[input.bindings]` or `[input.actions]` defaults or input docs with the old names.
- **Unchanged:** the `RECOMP_PAD_SCRIPT` grammar (`lt`, `lthumb`, `p2-a`: a test-harness syntax, not a player config); upstream's `keyboard_map` labels; which host button drives WHITE and BLACK.

## Capabilities

### Modified Capabilities
- `input`: "The mapping lives in the configuration files" (upstream's control and key names, old names unknown), "The cursor is captured while the window has focus" (the default binding's names), "Key and mouse events can be injected for tests" and "Host inputs are named in the trace" (canonical names in the trace).

## Impact

A player's `config/config.toml` that uses an old name logs one `unknown control` / `unknown input` / `unknown name` line each. An old control name is ignored and that control keeps its default. An old key name is skipped but the rest of its line applies, so a line left with no valid entries unbinds that control (`start = "KPEnter"` leaves Start with no key). An action line keeps only its valid entries. The CHANGELOG entry carries the table. No env key, no change for stock configs, no change to what the game executes beyond the parser and the trace text.
