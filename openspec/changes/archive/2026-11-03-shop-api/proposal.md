## Why

The entity spike (`entity-system-spike` design E6) found the shop
reading a catalogue at `0x4AACE0` from `menu_shop` (`sub_00210660`), but
nothing more: not what the records hold, where a bought weapon goes, or
where a weapon's power, range, capacity and fire rate come from. A mod that
wants cheaper guns, more ammo or stronger shots has to find all of that
again. The tracker item asks for one game-level API over the shop and the
weapon stats, in the shape of the entity API, and a mod that
uses it.

## What Changes

- **Static map** (design "Findings"): the catalogue's 53 records, the shop's
  per-player state and lineup, the buy paths per category, the player
  status where owned weapons live, and the four weapon stats: the gun
  table `0x402860` (capacity, ammo per purchase), the shot table
  `0x4022E0` (power per shot type), and the two stats the code holds
  inline (shot speed and life, the fire interval).
- **cat, the shop API** (`src/shop_api.{c,h}`, the pure part in
  `src/shop_api_logic.{c,h}`):
  - read any catalogue record; override its price or value;
  - read a gun's stats; override its capacity, its ammo per purchase and
    its shot type's power; scale its shots' speed and life and its fire
    interval;
  - read and set the weapon and ammo each player's characters own.
  Table overrides keep the game's values and give them back when the mod
  turns off. Speed, life and fire interval act in a post hook of the fire
  function `sub_001A0260`, on the shots that call made.
- **cat, the `shop` mod** (`src/shop_mod.c`): the API's owner and its
  Mods page: `enable` (off by default), `price_pct`, `ammo_pct`,
  `power_pct`, `speed_pct`, `interval_pct`, a Status row, and a debug-tier
  proof driver (`RECOMP_DEBUG=shop_proof=...`).
- **One permanent `[mods] hook_functions` slot**: `0x001A0260`
  (`ent_player_gun_fire`). It changes gen, so this change takes goldens.

## What stays stock

- The mod defaults off. Off, its hook is dormant, it writes nothing, and
  a switch to off puts every table value it changed back. `game.toml`
  `[golden] enhance_stock` gains `"mods.shop.enable" = "off"`.
- The hook slot runs the function unchanged when no hook is live.
- Saves: the tables are `.data` and are never saved, so no save carries a
  mod's price or stat. What the player does with them (gold spent, a
  weapon bought or set) is game state and saves as a purchase does
  (design D6).

## Impact

- cat only (toolkit mod API v6 is already pinned, blinx2-v0.11.0):
  `src/shop_api*`, `src/shop_mod.{c,h}`, `src/main.c` mod table,
  `CMakeLists.txt`, `game.toml` (`[mods]`, `enhance_stock`), regenerated
  gen and `config/hook_functions.json`, env rows (`recomp_env_game.h`,
  `docs/env.md`), commented keys in `packaging/config.default.toml`,
  `config/symbols.toml`, `scripts/test_shop.py`.
