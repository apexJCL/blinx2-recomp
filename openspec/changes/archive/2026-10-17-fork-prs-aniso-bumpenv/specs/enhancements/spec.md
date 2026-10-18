## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay even if the default of `present.pacing` changes or a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 present.pacing=spin (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`

#### Scenario: Legacy pin still stock
- **WHEN** `@stage1` runs with `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_CONFIG` unset, with a `config.default.toml` beside the executable that sets `scale = 2`
- **THEN** the log has one `[ENV] RECOMP_ENHANCE_CONFIG is deprecated; use RECOMP_CONFIG` line, reads no file, and shows `render.scale=1`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`, or `render.aniso=8`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

## ADDED Requirements

### Requirement: Anisotropic filtering key
`render.aniso = N` (env `RECOMP_RENDER_ANISO`, through the `recomp_env` enhancement keys; 0 or 1 off, 2..16 the anisotropy, default 0) SHALL be carried in `nv2a_host_opts.aniso`, read at start, clamped to 0..16 with a log line, applied by Metal and D3D11 on the rule in `gpu-backend`, ignored by the CPU backend, and documented in the toolkit's `docs/runtime/config.md` and the game's `docs/env.md`.

#### Scenario: Out of range
- **WHEN** `render.aniso = 32` is set
- **THEN** the layer logs the clamp and uses 16; `render.aniso = 1` is stock with no log
