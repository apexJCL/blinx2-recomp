## ADDED Requirements

### Requirement: LOD thresholds follow the render scale
With `mods."lod.enable" = "on"` (env `RECOMP_LOD`), the `lod` mod SHALL write
thresholds 1..4 of the table at `0x450B08` (`0x450B10`, `0x450B18`,
`0x450B20`, `0x450B28`) as `max(1, lround(stock / (s × d)))`, stock 24, 48,
80 and 160, where `s` is the render scale when `mods."lod.follow_scale"` is
true (default) and 1 otherwise, and `d` is `mods."lod.distance"` (0.5..4,
step 0.25, default 1). It SHALL NOT write threshold 0 (`0x450B08`) or the
level words. It SHALL recompute the thresholds every guest frame from the
current render scale and settings and write them only when they change, from
the guest's thread.

#### Scenario: 2x in the hub
- **WHEN** the Sweepers hub runs on Metal at render scale 2 with `RECOMP_LOD=on`
- **THEN** the log shows `thresholds 8/12/24/40/80 (scale 2, distance 1)`,
  and the mid-distance NPCs draw full-detail parts (goggles, gloves, boots,
  shadow) with more batches per flip than the same run with the mod off

#### Scenario: Render scale changed live
- **WHEN** the menu changes `render.scale` from 2 to 3 while the mod is on
- **THEN** the next frame writes 8/16/27/53 and logs it once

#### Scenario: 1x is stock
- **WHEN** the mod is on at render scale 1 with distance 1
- **THEN** the table keeps the stock values and no write is made

### Requirement: The LOD mod is off by default and restores stock
The `lod` mod SHALL be a settings API v3 descriptor mod with the enable
setting `enable` (enum `off`/`on`, default `off`, live), `follow_scale` (bool,
default true, live) and `distance` (float, live), shown on the Mods page and
in the `RECOMP_MODS_DESCRIBE=json` dump. Turning it off (the setting, the
Mods page, or at exit) SHALL write the stock thresholds back. Before its
first write it SHALL check that the ten words at `0x450B08` hold the stock
table, and before each later write that thresholds 1..4 hold its last
values; on a mismatch it SHALL log one line and not write the table again
in that run.

#### Scenario: Off at start
- **WHEN** the game starts with no `lod` keys set
- **THEN** the log shows `[ENHANCE] mods.lod.enable=off`, no `[MOD lod]`
  thresholds line, and the table is never written

#### Scenario: Turned off from the menu
- **WHEN** the mod is on at 2x and the Mods page turns it off
- **THEN** the next frame writes 24/48/80/160 back and logs it

#### Scenario: Table not stock
- **WHEN** the table does not hold the stock values at the first write
  (a `RECOMP_DEBUG=poke` run)
- **THEN** the mod logs that it leaves the table alone and never writes it
