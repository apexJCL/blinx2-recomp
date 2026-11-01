## ADDED Requirements

### Requirement: Hor+ display aspect
`display.aspect` (env `RECOMP_DISPLAY_ASPECT`, default `4:3`) SHALL accept any `W:H` ratio wider than 4:3. Any other value SHALL be reported once, and 4:3 used instead.

With a wide ratio, the Metal and D3D11 backends SHALL:
- pad every colour target whose guest shape is 4:3 within 1%, and its depth target, by `nv2a_host_pad` guest pixels on each side: `round((h * W/H - w) / 2)`, which is 107 for 640x480 at 16:9;
- pad every square colour target by the frame's share of its width, `round((w * 3W/(4H) - w) / 2)`, which is 85 for 512x512 and 43 for 256x256 at 16:9;
- leave every other shape unpadded (pad 0), for example 512x256;
- allocate `(w + 2 pad) * N` by `h * N` host pixels, where `N` is the render scale;
- map guest pixels to NDC with `2/(w + 2 pad)` and `-w/(w + 2 pad)` in x, so the title's columns 0..w sit centred and geometry projected beyond them is drawn in the pads.

A whole-clip clear SHALL clear the pads too, and a partial clear SHALL be offset by the pad. The flip SHALL present the whole padded target and write the centre `w x h` back to guest memory. Under `RECOMP_TRACE=aspect` the backend SHALL log, per flip, the target, its pad, its host size and the number of batches placed off centre. The CPU rasteriser SHALL ignore the key, render at 4:3 and log that once.

#### Scenario: Stage 1 at 16:9 on Metal
- **WHEN** `@stage1` runs on Metal with `RECOMP_DISPLAY_ASPECT=16:9`, `RECOMP_TRACE=aspect` and `metal_host_dump`
- **THEN** the log reads `display.aspect=16:9` and `[metal] flip N hor+: target 640x480 pad 107 (854x480 host)` lines
- **AND** the host dumps are 854x480, with the stage's 3D continuing into the outer 107 columns on each side

#### Scenario: Square targets padded by the frame's share
- **WHEN** the game draws into its 256x256 and 512x512 targets at 16:9
- **THEN** their pads are 43 and 85, their host sizes `342N x 256N` and `682N x 512N`, and a batch sampling them reads the stock texels for u in [0, 1]

#### Scenario: Other shapes keep their shape
- **WHEN** a 512x256 target is drawn at 16:9
- **THEN** its host size is `512N x 256N`, with no pad

#### Scenario: Bad value
- **WHEN** `RECOMP_DISPLAY_ASPECT=wide` or `=3:4`
- **THEN** the layer logs that it is not a `W:H` ratio wider than 4:3, uses 4:3, and every target is stock-sized

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_DISPLAY_ASPECT=16:9`
- **THEN** the log says once that the key is ignored, and the frames are 640x480

### Requirement: Hor+ batch placement
With a wide aspect, each batch drawn into a padded target SHALL be classified by the shared helpers.

**2D.** A pass-through batch is 2D. A program batch is 2D when `nv2a_aspect_scan` runs a sample of its vertices through the vertex-program interpreter and every vertex shares one `oPos.w` that is an exact whole number from 1 to 1024 (a screen layer; `oPos.xy` are pixels whatever `w` is). The scan SHALL be gated per program:
- a program is checked every batch until 16 batches have been checked;
- after that, a program never seen 2D is checked only every 256th batch;
- a program seen 2D once is checked every batch.

**Full width.** A 2D batch is full width when one of its triangles spans the guest width within 2 pixels (`nv2a_aspect_full_tris`), not merely its bounds.

**Placement.** `nv2a_aspect_place` SHALL then decide:
- a 3D batch is centred, and its scissor reaches the target's edges where its clip box meets the frame's edges;
- a 2D batch that is not full width is centred and scissored to the guest columns, so pieces the title parks off-screen never show in the pads;
- a full-width 2D batch that samples an unpadded render target is centred;
- a full-width 2D batch that samples only padded render targets or no texture, or whose guest texture is not a picture (`nv2a_aspect_picture`: at most a quarter of the frame's width), is stretched over the whole target;
- a full-width 2D batch over a guest picture is a movie or still, and follows `display.movie`.

**Sampling.** A centred batch sampling a padded render target SHALL read only its guest columns, and a stretched or covering one SHALL read it whole. `RECOMP_TRACE=aspect` SHALL print each distinct program, texture and placement once.

#### Scenario: Corner triangles stay their size
- **WHEN** the title screen draws its four corner triangles as one batch whose bounds span the screen
- **THEN** no single triangle spans the width, the batch is centred, and the triangles are their 4:3 size

#### Scenario: Post passes and fades cover the frame
- **WHEN** `@stage1` runs at 16:9 past the first 3D flip
- **THEN** C8AF571F and 489640CD are traced as `stretch`, the glow covers the outer columns with no seam at the 4:3 edge, and a fade through the 16x16 white texture darkens the pads with the centre

#### Scenario: HUD centered and parked pieces hidden
- **WHEN** a HUD batch narrower than the frame is drawn at 16:9
- **THEN** it lands on its 4:3 columns offset by `pad * N`, and any part of it at guest `x < 0` or `x > w` is scissored away

#### Scenario: HUD layer at a fixed depth
- **WHEN** `@stage1` draws the status panel's frame with every vertex at `oPos.w` 3, and world sprites each at one non-whole `oPos.w`
- **THEN** the frame is 2D and placed with the rest of the panel, and the sprites stay 3D

#### Scenario: Movie pillarboxed by default
- **WHEN** the title movie plays at 16:9 with no `display.movie` key
- **THEN** its full-width quad (B2913952, a 1024x512 guest texture) is centred, with black 107-column bars on each side

### Requirement: HUD keeps its 4:3 layout
With a wide aspect, every 2D batch that is not full width (the HUD, menus, text) SHALL be drawn centred on its 4:3 columns, unscaled and scissored to them, as at stock. There SHALL be no option to move or scale the HUD: the game draws triangles with no element identity, so no rule can keep a HUD element whole (design H6). A config key the layer doesn't read, `display.hud` included, SHALL get the generic `[ENHANCE] unused key <key>, <file>:<line>` warning and SHALL change nothing; it SHALL NOT fail the load.

#### Scenario: Stage HUD on its 4:3 columns
- **WHEN** `@stage1` runs at 16:10
- **THEN** the status panel, the radar, the item counter and the dialogue box are where they are at 4:3, offset by `pad * N`, each the same size, with the world drawn in the pads beside them

#### Scenario: An unread key
- **WHEN** a `config.toml` sets `display.aspect = "16:10"`, `display.movie = "fit"` and `display.hud = "edges"`
- **THEN** the load succeeds, the log has one `[ENHANCE] unused key display.hud, <file>:<line>` line, and the options are those of the same file without the `hud` line

### Requirement: Movie side fill
`display.movie` (env `RECOMP_DISPLAY_MOVIE`, default `black`) SHALL set how a full-width 2D batch over a guest picture fills a wide target:
- `black` keeps it centred, with the pads cleared;
- `fit` stretches its columns 0..w over the whole target width;
- `fill` scales it in x and y by the same factor `(w + 2 pad)/w` about the frame's centre, so it covers the width and its top and bottom are cropped.

Any other value SHALL be reported, and `black` used.

#### Scenario: Fit and fill
- **WHEN** the title movie plays at 16:9 with `display.movie = "fit"`, and again with `"fill"`
- **THEN** with `fit` the picture spans all 854 columns at its full height; with `fill` it spans all 854 columns and shows only the middle 75% of its rows (12.5% cropped at each of the top and bottom)

### Requirement: Hor+ cost
On Metal and D3D11, Hor+ at 16:9 SHALL NOT raise the unpaced cost per frame by 1.5x or more over stock, measured on `@attract`, `@stage1` and `@story` (the golden runs are game-paced, so flips/s can't show it):
- GPU ms per flip;
- the flip interval's p95;
- process CPU.

The figures SHALL be recorded in the change's tasks.

#### Scenario: Measured on Metal
- **WHEN** the three scenarios run on Metal with `RECOMP_TRACE=metal_prof,pacing` at stock and at 16:9
- **THEN** each figure at 16:9 is under 1.5x its stock value, and the flips and durations match stock

## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `display.aspect`, `display.movie`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, `display.aspect` is wider than 4:3 (a target with a non-zero `nv2a_host_pad`), a texture pack is loaded, or the frame and the output differ in size; `display.movie` acts only on a padded target. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 and pad 0 return their inputs, every Hor+ placement at pad 0 leaves the stock constants, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`, with no `hor+` line

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

### Requirement: Internal resolution scale
`render.scale = N` (env `RECOMP_RENDER_SCALE`, 1..4, default 1) SHALL make the Metal and D3D11 backends allocate every colour and depth target at N× its guest size, widened by `display.aspect`'s pad when one is set (`(w + 2 pad) * N` by `h * N`; lower for a surface that would exceed the API's texture limit), set the viewport to that size, and keep the pixel-to-NDC constants on the guest size and pad. Render-to-texture SHALL sample the scaled target with normalised coordinates from the guest size; self-copies SHALL be host-sized. A Metal render target created from guest bytes SHALL be filled with those bytes expanded N× into the centre columns. Bytes written back to guest memory SHALL be at guest size (box-downsampled from the centre columns), so `RECOMP_FB_DUMP`, `fb_dump_at` and the title see guest-sized frames. Debug pixel reads (`read_pixel`, `px_probe`) SHALL scale and offset their coordinates and their own targets. Visibility-test counts reported to the title SHALL be divided by N², a non-zero count staying non-zero and the synthetic visible fallback untouched. The CPU rasteriser SHALL ignore the key, render at 1× and log that once. Values outside 1..4 SHALL be clamped with a log line.

#### Scenario: Sharper frame at 2x on Metal
- **WHEN** the attract scenario runs on Metal with `RECOMP_RENDER_SCALE=2`
- **THEN** the window receives 1280x960 frames, a window shot of a flip shows finer geometry edges than the same flip at 1×, and the run lasts 120 s without a crash

#### Scenario: Scale and aspect together
- **WHEN** `@attract` runs on Metal with `RECOMP_RENDER_SCALE=2` and `RECOMP_DISPLAY_ASPECT=16:9`
- **THEN** the host frames are 1708x960 and the run lasts its length without a crash

#### Scenario: Guest-size write-back
- **WHEN** Metal writes the presented surface back to guest memory at scale 2
- **THEN** the bytes are 640x480 at the guest pitch, and an `fb_dump_at` frame compares with the 640x480 golden reference within its limits

#### Scenario: Visibility count scaled
- **WHEN** a visibility test at scale 2 counts 4 host samples, or 1 host sample
- **THEN** the title's report reads 1 in both cases, and a test the hardware counted as 0 still reads 0

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_RENDER_SCALE=2`
- **THEN** the log says once that the key is ignored and the frames equal the 1× frames within the golden limits
