## ADDED Requirements

### Requirement: Dashboard video flags
The kernel SHALL answer `ExQueryNonVolatileSetting(XC_VIDEO)` with the raw EEPROM word from `xbox_video_flags_raw()`, whose bits are those of `XGetVideoFlags` shifted left by 16. The stock value SHALL be 0. `display.widescreen = "native"` on a declaring game SHALL add only `0x00010000`. `RECOMP_DEBUG=video_flags=0x...` SHALL replace the word and log it once.

#### Scenario: Stock
- **WHEN** a game runs with no `display.widescreen` and no debug key
- **THEN** the raw word is 0, and the game's `XGetVideoFlags` returns 0, as before this change

#### Scenario: Native
- **WHEN** b3 runs with `display.widescreen = "native"`
- **THEN** the raw word is 0x00010000, and byte 0x4D617D reads 1 after boot

### Requirement: Native widescreen
`display.widescreen` (env `RECOMP_DISPLAY_WIDESCREEN`, default `off`) SHALL accept `off` and `native`. `native` SHALL take effect only on a game that registered a native mode with `enhance_native_register()`; otherwise it SHALL be logged once and ignored. When it is in effect:
- `display.aspect` SHALL be ignored with a log line, and every target SHALL be stock-sized;
- at each flip where the registered probe reads wide (or always, with no probe), Metal and D3D11 SHALL present the frame at a 16:9 display aspect, letterboxed or pillarboxed into the window;
- guest targets, write-back and frame dumps SHALL be unchanged.

#### Scenario: b3 at 16:9
- **WHEN** b3 runs with `display.widescreen = "native"` in a 16:9 window
- **THEN** the 640x480 frame fills the window's width, and `RECOMP_TRACE=native` logs `stretch on` once

#### Scenario: Following the game's setting
- **WHEN** an SSX 3 player picks 16:9 (letterboxed) in the game's menu with `native` on
- **THEN** the probe reads not wide, and the frame is presented at 4:3 with the game's own bars

#### Scenario: Native with no probe
- **WHEN** a game registers a native mode with `va = 0` and runs with `display.widescreen = "native"`
- **THEN** every flip is presented at 16:9

#### Scenario: Stock window size
- **WHEN** b3 starts with `display.widescreen` unset and `display.aspect` at 4:3
- **THEN** the window, the drawable or swap chain, and the present rectangle have the same sizes as before this change, and `xbox_video_flags_raw()` returns 0

#### Scenario: Game without native support
- **WHEN** BLiNX 2 runs with `display.widescreen = "native"` and `display.aspect = "16:9"`
- **THEN** the log names the key as ignored, and Hor+ runs as for `display.aspect = "16:9"` alone

### Requirement: Hor+ frame copies
Under a wide `display.aspect`, a texture whose surface holds a copy of a padded render target, recorded by the backend's copy path (or, if implemented, matched as a CPU copy), SHALL be bound as a host render target with its pad, and SHALL be placed and sampled as one.

#### Scenario: Burnout 3 race at 16:9
- **WHEN** the race-gate route runs at 16:9 on Metal and D3D11
- **THEN** the speed blur and glow show no seam at x = 107 and 747

### Requirement: Hor+ tiled backdrops
Under a wide `display.aspect`, a menu backdrop that the `aspect` trace shows as the cause of the strip at the old 4:3 edges SHALL fill the pads. A backdrop tiled across the guest width by 2D batches sharing one texture and one program SHALL be stretched as one. A full-width 2D batch whose texture repeats more than once SHALL be extended in u rather than placed as a picture. The HUD SHALL keep its centred 4:3 placement. A backdrop that is 3D and culled at the 4:3 edge is the frustum limit and is out of scope.

#### Scenario: Burnout 3 menus at 16:9
- **WHEN** the b3 menus run at 16:9 on Metal and D3D11
- **THEN** the grid backdrop has no strip at the old 4:3 edges, and the menu text stays in its 4:3 columns

## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `display.aspect`, `display.movie`, `display.widescreen`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, `display.aspect` is wider than 4:3 (a target with a non-zero `nv2a_host_pad`), a texture pack is loaded, or the frame and the output differ in size; `display.movie` acts only on a padded target; `display.widescreen` acts only when it is `native` on a game that registered a native mode, and without the layer its `nv2a_host_opts` fields are 0 (raw video flags 0, no stretch). A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 and pad 0 return their inputs, every Hor+ placement at pad 0 leaves the stock constants, `nv2a_present_rect` with the display aspect equal to the frame's returns today's rectangle, `xbox_video_flags_raw()` returns 0, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `display.widescreen` other than `off`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3) display.widescreen=off` followed by `[ENHANCE] textures.pack=none`, with no `hor+` line

#### Scenario: A plain run sleeps
- **WHEN** the game starts with no `present.pacing` key in either settings file and no `RECOMP_PRESENT_PACING`
- **THEN** the log reads `present.pacing=sleep`, and the frames and pace match a run at `spin`

#### Scenario: Legacy pin still stock
- **WHEN** `@stage1` runs with `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_CONFIG` unset, with a `config.default.toml` beside the executable that sets `scale = 2`
- **THEN** the log has one `[ENV] RECOMP_ENHANCE_CONFIG is deprecated; use RECOMP_CONFIG` line, reads no file, and shows `render.scale=1`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 and pad-0 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_host_pad`, `nv2a_present_rect` for an exact fit, the occlusion scaling, `nv2a_aspect_map` and `nv2a_aspect_box` at pad 0) returns its input or the stock constants unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`, or `render.aniso=8`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a wide run
- **WHEN** `golden.py` evaluates a run whose log contains `display.aspect=16:9`
- **THEN** the run is marked FAIL with a reason naming `display.aspect`, and its frames are not compared

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a native run
- **WHEN** `golden.py` evaluates a run whose log contains `display.widescreen=native`
- **THEN** the run is marked FAIL with a reason naming `display.widescreen`, and its frames are not compared

#### Scenario: Burnout 3 stock goldens unchanged
- **WHEN** the b3 stock goldens run on Metal and on the Deck's D3D11 with this change
- **THEN** each passes with the same verdict as before it, since the raw video flags stay 0
