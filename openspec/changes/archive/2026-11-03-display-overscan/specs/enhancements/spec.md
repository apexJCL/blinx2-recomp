## ADDED Requirements

### Requirement: Display overscan crop
`display.overscan` (env `RECOMP_DISPLAY_OVERSCAN`, default `0`) SHALL be a whole number of guest pixels from 0 to 64. A larger value SHALL be clamped to 64 with one warning, and a value that is not a number SHALL be reported once and ignored: the next source answers (the environment, then the config file, then the default 0).

With a value `n` above 0 and `display.aspect` at 4:3, the Metal and D3D11 presenters SHALL show only the part of each flipped frame that `nv2a_present_crop` returns:
- `n` guest columns cut from each of the left and right edges;
- `n * h / w` guest rows cut from each of the top and bottom;
- the result zoomed uniformly into the destination rectangle that `nv2a_present_rect` gives under the current `present.filter`, fullscreen and `present.surface`. For `nearest` and `linear` that rectangle SHALL be computed from the uncropped frame size, because the crop keeps the frame's aspect. For `integer` it SHALL be computed from the cropped size, with the vertical cut rounded to whole host rows so that whole multiples exist.

Under `present.surface = internal` the crop SHALL fill the whole surface, sampled with the `present.filter` sampler, except that `integer` samples `nearest`, on both backends.

The presenters SHALL do this on every present path, including those that skip the blit at 0 (D3D11 at scale 1 with `nearest`, the same-size shortcut and the internal surface's copy). A frame no wider than `2n` guest pixels SHALL be presented whole. A value below 0 SHALL be clamped to 0 with one warning.

The crop SHALL NOT change the guest frame, the host render targets, the write-back to guest memory, `fb_dump`, `metal_host_dump` or the D3D11 dump. `window_shot` SHALL show the cropped picture.

When `display.aspect` parses to a ratio wider than 4:3 (an invalid aspect falls back to 4:3 and does not count), a non-zero value SHALL be reported once (`display.overscan=N ignored with display.aspect=W:H`) and 0 used, because the 4:3 frame's edges are inside the padded frame and no source rectangle cuts them. The CPU rasteriser SHALL ignore the key and log that once. The key SHALL be read at start only.

#### Scenario: SSX 3 title screen at 9 on Metal
- **WHEN** SSX 3 shows its title screen on Metal with `RECOMP_DISPLAY_OVERSCAN=9` at render scale 2 in a 4:3 window
- **THEN** the `[ENHANCE]` summary line ends `(display.aspect=4:3 display.overscan=9)`
- **AND** a `window_shot` has no dark columns at the left and right edges, and `fb_dump` frames match a run at 0

#### Scenario: Stock path untouched at 0
- **WHEN** a title runs on D3D11 at scale 1 with `nearest`, a window the frame's size and `display.overscan` at 0
- **THEN** the flip takes the no-blit path as before, and the `[ENHANCE]` summary line is the same as before the key existed

#### Scenario: Crop forces the blit
- **WHEN** the same run sets `RECOMP_DISPLAY_OVERSCAN=9`
- **THEN** the flip blits with UV offset `(9/640, 6.75/480)` scaled to the render target, the back buffer's pixel at `(0, y)` is the frame's column 9, and the D3D11 dump shows the uncropped render target at its own size

#### Scenario: Integer filter keeps whole multiples
- **WHEN** `present.filter = "integer"`, scale 1, `display.overscan = 9` in a 1920x1080 window
- **THEN** the shown part is 622 x 466 guest pixels (the vertical cut rounded to 7 rows) drawn at 1244 x 932, centred

#### Scenario: Refused under Hor+
- **WHEN** `display.aspect = "16:9"` and `display.overscan = 9`
- **THEN** the log has one `display.overscan=9 ignored with display.aspect=16:9` line and the padded frame is presented whole

#### Scenario: Out of range
- **WHEN** `display.overscan = 100`
- **THEN** one warning names 100 and the crop uses 64

#### Scenario: Golden check
- **WHEN** a golden run's log reports `display.overscan=9` and no `--allow-enhance display.overscan=9`
- **THEN** the golden harness fails the run as not stock

## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `display.overscan`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL either return the stock value with every key at its default (as `nv2a_present_crop` does at `display.overscan = 0`: the whole frame, its stock UV scale and a zero offset, so the blit samples the same UVs) or be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, `display.overscan` is above 0, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect`, `display.overscan` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`

#### Scenario: A plain run sleeps
- **WHEN** the game starts with no `present.pacing` key in either settings file and no `RECOMP_PRESENT_PACING`
- **THEN** the log reads `present.pacing=sleep`, and the frames and pace match a run at `spin`

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
