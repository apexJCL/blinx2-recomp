## Why

The Full Diagonal Movement mod needs Square left stick for pads and the keyboard, but that switch lives on Controls > Sticks. The player turns on the mod in one place and the stick in another. The user (2026-11-05) wants both on the mod's page.

## What Changes

- **Toolkit (`posix-host/portability`)**: a new descriptor setting kind, `XBOX_SET_LINK`, and `XBOX_MOD_DESC_VERSION` 2. A link setting's `key` names a toolkit menu item (`input.pad_square_left`). The mod's page shows a row for it, and that row is the item's own menu slot: one value, one saved key, the same row state on both pages. The toolkit keeps no copy and the mod stores nothing.
- **Cat**: `src/fdm_mod.c` adds a `square_left` link row after Enabled. The Status hint and the About text point at it.

## Capabilities

### Modified Capabilities
- `mod-settings` (toolkit): a fifth setting kind.
- `fdm-mod`: the Square left stick row.

## Impact

- Toolkit: `src/enhance/mod.h`, `mod.c`, `mod_describe.c`, `enhance_menu.c`, `enhance_menu.h`, `tests/enhance_menu`, `tests/mod_desc`, `docs/runtime/config.md`.
- Cat: `src/fdm_mod.c`, `scripts/test_fdm.py`, `docs/env.md` only if a row's text changes.
- ABI: `struct xbox_mod_setting` and `struct xbox_mod_desc` keep their layout. Version 1 descriptors read as before. An older toolkit refuses the new kind ("unknown kind"), so a mod guards the row with `#if XBOX_MOD_DESC_VERSION >= 2`.
- Stock: no change. Goldens run with mods off and the menu off, and the link row writes nothing until the player changes it.
