## Why

At render scale 2x and 3x, characters switch to their low-detail models as
close to the camera as they do at 1x: flat goggle decals, blocky hands and
feet, no drop shadow. The spike found why. `sub_0019A2C0` picks a
level 0..5 for each character from its screen radius, measured in fixed
640x480 units (`P22 · (1/z) · 240`), and looks it up in the writable `.data`
table at `0x450B08`: (threshold, level) pairs (8,0) (24,1) (48,2) (80,3)
(160,4) (9999,5), the first threshold above the radius winning. The test is
blind to the render scale, so a model that covers twice the pixels at 2x
still gets the level it had at 480 lines.

Dividing thresholds 1..4 by the render scale makes a model reach each level
at the same physical size on screen as on the Xbox at 480p. Measured on Metal
in the Sweepers hub (settled end view): +27% batches per flip at 2x and +35%
at 3x, Mac flips/s unchanged, and the mid-distance NPCs get real goggles,
detailed gloves and boots and their shadow (spike crops,
`runs/lod-spike/crops/`).

## What Changes

- **A new cat mod, `lod`** (`src/lod_scale.c`, pure maths in
  `src/lod_table.c`), with a settings API v3 descriptor and default off:
  - `mods."lod.enable"`: enum `off`/`on`, the mod's enable setting, live;
    env `RECOMP_LOD`;
  - `mods."lod.follow_scale"`: bool, default `true`, live; env
    `RECOMP_LOD_FOLLOW_SCALE`;
  - `mods."lod.distance"`: float 0.5..4, step 0.25, default 1.0, live; env
    `RECOMP_LOD_DISTANCE`. A multiplier on how far full detail holds.
- While on, the mod writes thresholds 1..4 (`0x450B10`, `0x450B18`,
  `0x450B20`, `0x450B28`) as `stock / (scale × distance)`, rounded, at least
  1 (scale is 1 when `follow_scale` is off). It rewrites them when the render
  scale or a setting changes, and puts the stock values back when turned off
  and at exit.
- Threshold 0 (`0x450B08` = 8) is never written: game logic reads only
  "level 0" (the off-screen counter `sub_00143F80`), so visibility and that
  logic are unchanged. The game's 0.6 two-player factor (and 0.75 in mode 10)
  applies to the radius before the table and is kept.
- The mod checks the table holds the stock values before its first write and
  that it still holds what it last wrote before each later one; otherwise it
  logs one line and leaves the table alone for the rest of the run.
- Goldens stay stock: `game.toml` `enhance_stock` gains
  `"mods.lod.enable" = "off"`.
- No toolkit change: the render scale is read each frame with
  `nv2a_host_render_scale()`. No generated-code edit, no wrapper, no
  `src/fixes` patch (this is a visual enhancement, not a stock-crash fix).

## Capabilities

### New Capabilities
- `lod-scale`: the LOD table follows the render scale.

### Modified Capabilities
- `enhancements`: the `lod` mod's switch stays out of goldens.

## Impact

- cat: `src/lod_scale.{c,h}`, `src/lod_table.{c,h}` (new), `src/main.c` (mod
  table), `CMakeLists.txt`, `src/env/recomp_env_game.h` (3 rows),
  `docs/env.md`, `game.toml`, `packaging/config.default.toml` (commented
  keys), `scripts/test_lod_scale.py` (new).
- Cost when on: more draws (spike: +27% at 2x, +35% at 3x in the hub). The
  Deck is already draw-bound there, so the Deck numbers are
  measured and reported; the mod stays opt-in.
