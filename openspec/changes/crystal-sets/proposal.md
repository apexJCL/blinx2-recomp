## Why

BLiNX 2 turns crystals into time controls per colour: three crystals of one
colour, in any order and with any others between them, make that colour's
control. BLiNX 1 used a row instead: the crystals go into four slots in the
order they are picked up, three of one colour in the row give that control
and four of one colour give it twice, and the row empties once it is full.
The crystal spike (`spike/crystals` f696490 and d709fe6) mapped the
pickup `tc_crystal_collect` `0x8BFD0`, the per-team record that holds the
counts, the held controls and the cap, and the HUD that draws them. Tracker
The tracker item asks for BLiNX 1's rule as an opt-in mod.

The user's choices (2026-10-31): the row as above; a completed set goes into
BLiNX 2's own stock and is picked live with the d-pad as today; BLiNX 2's
per-colour caps stay, and a set completed while that control is full pays
gold as BLiNX 2 does. BLiNX 1's freezing power-up picker and its frozen
countdown after a control are left out on purpose.

## What Changes

- **A permanent hook slot** on `tc_crystal_collect` `0x0008BFD0`
  (`game.toml` `[mods] hook_functions`; gen regenerated).
- **The `crystals` mod** (`src/crystals_mod.c`, pure rules in
  `src/crystals_logic.{c,h}`), off by default:
  - in Sweepers stages only, a pre and a post hook on the pickup that let
    the game's own code run every time: the mod prepares the record so the
    game grants exactly when the row says so, and puts the row back after;
  - the row lives in the record's per-colour count bytes, so checkpoints,
    retries and the time-record ring carry it like the stock counts;
  - the HUD shows the four slots in the time-control panel instead of the
    stock pips for the selected colour, drawn through the game's sprite add
    `0x42190` (a slot the HUD mod already uses);
  - settings `enable` (menu, Mods page) and a Status row; a debug-tier
    proof driver for the live runs.
- **Symbols** from `spike/crystals` f696490.
- `game.toml` `[golden] enhance_stock`: `mods.crystals.enable = "off"`.
- Env rows `RECOMP_CRYSTALS` (config) and `RECOMP_CRYSTALS_PROOF` (debug).

## Capabilities

### New Capabilities
- `crystal-sets`: BLiNX 1's crystal row in BLiNX 2 as an opt-in mod.

## Impact

- Generated code: one more hook slot (`0x8BFD0`); with the mod off the slot
  only checks its empty table, as the other slots do.
- Stock behaviour unchanged with the mod off (the default and every golden).
- VS and Tom Tom stay on the stock rule even with the mod on.
