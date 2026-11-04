## ADDED Requirements

### Requirement: Free camera keys stay out of goldens
The `camera.*` keys (`camera.free`, `camera.free_speed`, `camera.free_look_sens`, `camera.free_hud`, `camera.free_toggle`, `camera.free_hud_key`, `camera.free_freeze_key`, `camera.free_reset_key`; env `RECOMP_CAMERA_FREE` and `RECOMP_CAMERA_FREE_*`) SHALL be game keys of the enhancements layer, read through the mod API's config getters before the unused-key report, and SHALL default to stock: `camera.free = "off"` registers no frame callback and no batch filter, and no wrapper writes guest memory. The game SHALL log `[ENHANCE] camera.free=<off|on>` once at start, `game.toml` `[golden] enhance_stock` SHALL list `camera.free = "off"`, and the golden harness SHALL fail a run whose log shows `camera.free=on`, unless the run is an evaluation run started with `--allow-enhance camera.free=on`. Such a run SHALL NOT be used to record references. `packaging/config.default.toml` SHALL hold every `camera.*` key at its stock value.

#### Scenario: Stock run untouched
- **WHEN** the Metal goldens run on the layer-ON build with `RECOMP_CONFIG=none`
- **THEN** each log has `[ENHANCE] camera.free=off`, no `[MOD camera.free]` line after the init line, and the same verdicts as before the module existed

#### Scenario: Harness rejects a free-camera run
- **WHEN** `blinx2 golden check` evaluates a run whose log contains `[ENHANCE] camera.free=on`
- **THEN** the run is marked FAIL with a reason naming `camera.free`; with `--allow-enhance camera.free=on` its frames are judged and the reason is printed as a note
