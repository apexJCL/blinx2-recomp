## Context

A descriptor setting (`struct xbox_mod_setting`, mod.h) is owned by `mod.c`: it resolves the value from env, the user files and the defaults, and the menu gives it its own slot on the mod's page. A toolkit item such as `input.pad_square_left` already has a slot on its own page, with `set_square` and `get_square` behind it. A second setting with the same key would give two slots, two cached values and two writers for one key.

## Decisions

### D1. A setting kind, not a new API call

`XBOX_SET_LINK` (value 4) goes in the descriptor, after the four kinds. The mod lists the row where it wants it, and the dump and the page read it without running the mod's code, like any other setting. No new `xbox_mod_api` field, so `XBOX_MOD_API_VERSION` stays 8.

`XBOX_MOD_DESC_VERSION` becomes 2. The structs do not change, so the toolkit reads version 1 descriptors as before. The version is a compile-time test for a mod: an older toolkit refuses kind 4 with "unknown kind", so a mod that must also build against it puts the row under `#if XBOX_MOD_DESC_VERSION >= 2`.

### D2. Fields

- `name`: required, as for every setting (duplicates refused).
- `key`: required, the toolkit item's key. A key that names no toolkit item refuses the descriptor. Only the toolkit's built-in items can be linked: a title's or another mod's item may not exist when the descriptor is checked.
- `label`, `help`: NULL takes the item's.
- `env`, `aliases`, `XBOX_SET_ENABLE`: refused. The item has its own env row and key history; a link adds none.
- The other fields are ignored.

### D3. One slot

The mod's page puts the item's own slot on its row (`R_SLOT` to that slot), with the link's label and help. Changing it there is the same change as on Controls: the same `set`, the same unsaved mark, Save writes the key once. An env row that forces the item makes both rows read-only. "Reset this mod" leaves the row alone, as it is a toolkit setting.

### D4. What `mod.c` keeps

Nothing but the key. The Mods tab carries the unsaved dot while a link row's slot is unsaved, as the item's own tab does. `api->setting` reads the item now: a toggle 0 or 1, a choice its index (a numeric choice its number), a range its number. `on_setting` is never called for a link: the mod reads it when it needs it. `xbox_mod_setting_set` (the menu does not use it for a link) calls the item's `set`, clamped to the item's range and snapped to its step as the item's own row does, and refused while the item's env row forces it. `RECOMP_DEBUG=mod_set_at` does not take a link's key: it runs on the walker thread, and the item's `set` there would leave the menu slot's copy stale and add a third caller of the item's setter (for Square left stick, `xbox_InputSetPadSetup`). A link is only as thread-safe as the item's `get`, since `api->setting` and the describe dump call it; `input.pad_square_left`'s reads the pad setup with one atomic load. A version 1 descriptor with a link is refused. The source name is `link`. The dump lists the kind as `link`, with the key, the shown label and help, and the value in the item's form.

### D5. The fdm row

`square_left` links `input.pad_square_left`. Its label is the item's own, "Square left stick"; its help is "Pads and the keyboard need it for full diagonals. The same switch as Controls > Sticks." It is listed after Enabled, under Settings and above Status. The Status hint becomes "Turn on Square left stick above", and the About text ends "Pads and the keyboard need Square left stick, below." The switch's own help keeps "Needs Square left stick". The row and both texts sit behind `#if XBOX_MOD_DESC_VERSION >= 2`: built against an older toolkit header, the mod has no row and the texts name Controls > Sticks as before.

## Risks

- A mod built against version 2 with a link fails on an older toolkit. Cat pins its toolkit, so the pin move carries the toolkit change.
- The link reads the item through its `get`, from any thread. `get_square` reads the pad setup, which is safe from any thread.
