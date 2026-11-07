## Why

In BLiNX 1 a diagonal runs faster than a straight line: the walk uses the stick's length as it comes, and a corner of the square Xbox stick gate (or a keyboard corner) has length sqrt(2). Speedrunners use it. BLiNX 2 clamps the length to 1 before the deadzone, so a diagonal runs exactly as fast as a straight line. The tracker item asks for an opt-in mod that gives BLiNX 2 the BLiNX 1 behaviour, for speedrunners, documented in the menu.

## What Changes

- **New cat mod `fdm`, shown as "Full Diagonal Movement"** (`src/fdm_mod.c`, `src/fdm_logic.h`), off by default, behind `XBOXRECOMP_ENHANCE` (the mod API). On, the walk's target speed follows the stick's unclamped length: a full corner runs (sqrt(2) - 0.4) / 0.6 = 1.690 times a straight line, BLiNX 1's ratio. Nothing else that reads the stick changes.
- **Two hook slots** in `game.toml` `[mods] hook_functions`: `0x002D675C` (the CRT pow, `st0`) and `0x00176150` (`ent_player_update`, `no_st0`), regenerated into `config/hook_functions.json` and gen.
- **Menu**: the switch on the Mods page and the mod's page. Its short help, "Diagonals run up to 1.69x as fast as straight, as in BLiNX 1. Needs Square left stick (pads and keyboard).", is the tooltip card under the Mods list row and the Enabled row. The mod's About text: "Stock BLiNX 2 caps diagonal speed at straight speed. This mod lifts the cap: diagonals run up to 1.69x as fast, as in BLiNX 1. Pads and the keyboard need Controls > Sticks > Square left stick." A live Status row says when Square left stick is off.
- **Knob**: `RECOMP_FDM` (`mods."fdm.enable"`, config tier), a row in `src/env/recomp_env_game.h` and in `docs/env.md`; `game.toml` `[golden] enhance_stock` gains `"mods.fdm.enable" = "off"`.
- **New debug mod `speed`, shown as "Speed readout"** (`src/speed_mod.c`, `src/speed_logic.h`; `RECOMP_SPEED_READOUT`, `mods."speed.enable"`), off by default: the run speed on the toolkit's status card, the card Speed, `now 1.00  peak 1.00`, the speed over a full straight push's and its peak over the last second (design §7). Its own mod, so the card shows with fdm off too. It only reads the guest.
- **Not in this change**: a menu button that turns Square left stick on from the mod's page. It needs a toolkit API to set another item by key and save it (asked for in the hand-back).

## Capabilities

### New Capabilities
- `fdm-mod`: the opt-in unclamped walk speed.
- `speed-readout`: the opt-in run speed card.

### Modified Capabilities
- None.

## Impact

- cat only: `src/fdm_mod.c`, `src/fdm_mod.h`, `src/fdm_logic.h`, `src/main.c`, `CMakeLists.txt`, `src/env/recomp_env_game.h`, `docs/env.md`, `docs/reset-statics.md`, `game.toml`, `config/hook_functions.json`, `src/speed_mod.c`, `src/speed_mod.h`, `src/speed_logic.h`, `scripts/test_speed.py`, `scripts/test_fdm.py`.
- Generated code: two new hook slot wrappers. The mod's menu entry publishes the hooks under `XBOXRECOMP_ENHANCE` even while the mod is off, so every pow call (seven call sites, the D3DX range among them) and every `ent_player_update` go through `recomp_hook_run` and its state check; the pre hooks themselves do not run, so stock is unchanged (Metal and D3D11 goldens; the cost is in design §5).
- No toolkit change. The Square left stick mapping it relies on is the toolkit's (c3d8ee52).
