## ADDED Requirements

### Requirement: The LOD mod stays out of goldens
`game.toml` `[golden] enhance_stock` SHALL list `"mods.lod.enable" = "off"`,
so the golden check fails a run whose log shows `[ENHANCE]
mods.lod.enable=on` unless the run is an evaluation run started with
`--allow-enhance mods.lod.enable=on`. With the mod off, the goldens SHALL
keep their verdicts.

#### Scenario: Stock golden
- **WHEN** the Metal goldens run on a build with the `lod` mod
- **THEN** each log has `[ENHANCE] mods.lod.enable=off` and the verdicts are
  unchanged
