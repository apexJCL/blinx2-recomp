## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, or the frame and the output differ in size. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_RENDER_SCALE=1`, and the golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso` or `display.aspect`.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as a build without the layer and the log's `[ENHANCE]` line reads `render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 ... (display.aspect=4:3)`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`, or `render.aniso=8`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

## ADDED Requirements

### Requirement: Anisotropic filtering key
`render.aniso = N` (env `RECOMP_RENDER_ANISO`, through the `recomp_env` enhancement keys; 0 or 1 off, 2..16 the anisotropy, default 0) SHALL be carried in `nv2a_host_opts.aniso`, read at start, clamped to 0..16 with a log line, applied by Metal and D3D11 on the rule in `gpu-backend`, ignored by the CPU backend, and documented in the toolkit's `docs/runtime/config.md` and the game's `docs/env.md`.

#### Scenario: Out of range
- **WHEN** `render.aniso = 32` is set
- **THEN** the layer logs the clamp and uses 16; `render.aniso = 1` is stock with no log
