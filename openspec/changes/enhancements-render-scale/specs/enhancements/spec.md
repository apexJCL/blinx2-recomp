## ADDED Requirements

### Requirement: Enhancements default to stock
Every key of this change (`render.scale`, `present.filter`, `present.fullscreen`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as before the change: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, or the frame and the output differ in size. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_RENDER_SCALE=1`, and the golden harness SHALL fail a run whose log reports a non-stock `render.scale` or `display.aspect`.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as on `main` and the log reads `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 (display.aspect=4:3)`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

### Requirement: Internal resolution scale
`render.scale = N` (env `RECOMP_RENDER_SCALE`, 1..4, default 1) SHALL make the Metal and D3D11 backends allocate every colour and depth target at N× its guest size (lower for a surface that would exceed the API's texture limit), set the viewport to that size, and keep the pixel-to-NDC constants on the guest size. Render-to-texture SHALL sample the scaled target with normalised coordinates from the guest size; self-copies SHALL be host-sized. A Metal render target created from guest bytes SHALL be filled with those bytes expanded N×. Bytes written back to guest memory SHALL be at guest size (box-downsampled), so `RECOMP_FB_DUMP`, `fb_dump_at` and the title see guest-sized frames. Debug pixel reads (`read_pixel`, `px_probe`) SHALL scale their coordinates and their own targets. Visibility-test counts reported to the title SHALL be divided by N², a non-zero count staying non-zero and the synthetic visible fallback untouched. The CPU rasteriser SHALL ignore the key, render at 1× and log that once. Values outside 1..4 SHALL be clamped with a log line.

#### Scenario: Sharper frame at 2x on Metal
- **WHEN** the attract scenario runs on Metal with `RECOMP_RENDER_SCALE=2`
- **THEN** the window receives 1280x960 frames, a window shot of a flip shows finer geometry edges than the same flip at 1×, and the run lasts 120 s without a crash

#### Scenario: Guest-size write-back
- **WHEN** Metal writes the presented surface back to guest memory at scale 2
- **THEN** the bytes are 640x480 at the guest pitch, and an `fb_dump_at` frame compares with the 640x480 golden reference within its limits

#### Scenario: Visibility count scaled
- **WHEN** a visibility test at scale 2 counts 4 host samples, or 1 host sample
- **THEN** the title's report reads 1 in both cases, and a test the hardware counted as 0 still reads 0

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_RENDER_SCALE=2`
- **THEN** the log says once that the key is ignored and the frames equal the 1× frames within the golden limits

### Requirement: Present filter, resize and fullscreen
The SDL presenter and the D3D11 window SHALL place each frame with `present.filter` (env `RECOMP_PRESENT_FILTER`): `nearest` and `linear` fit the frame's aspect, centred, with that filtering; `integer` shows the largest whole multiple that fits, centred, and falls back to a linear fit when even 1× does not fit, never cropping. Sizes are device pixels. `present.fullscreen = true` (env `RECOMP_PRESENT_FULLSCREEN`) SHALL open a borderless window covering the display. The D3D11 window SHALL follow resizes (`ResizeBuffers` on the thread that owns the device context) and present through a scaling blit when the frame and the back buffer differ in size or the filter is `linear`; at stock it SHALL keep the direct copy into a 640x480 back buffer. The SDL presenter at the default filter SHALL keep today's logical-size letterbox path. The D3D11 frame dump SHALL read the back buffer when the direct copy ran and the presented render target otherwise, so no filter or window size ever reaches a dump; under scale the dump is at host size and is not golden material.

#### Scenario: Integer mode in a large window
- **WHEN** a 640x480 frame is shown in a 1920x1080 output with `present.filter = integer`
- **THEN** it is drawn at 1280x960, centred, with black borders

#### Scenario: Integer mode falls back instead of cropping
- **WHEN** a 1280x960 frame (scale 2) is shown in a 1024x768 output with `present.filter = integer`
- **THEN** the whole frame is shown, fitted and centred with linear filtering

#### Scenario: Stock window unchanged
- **WHEN** the SDL presenter runs with the defaults
- **THEN** its SDL calls are the same as before the change and a `RECOMP_WINDOW_SHOT` of a flip has the same letterbox geometry as on `main`

#### Scenario: D3D11 dump independent of the window
- **WHEN** a D3D11 run at stock has its window resized by the user or the compositor
- **THEN** the dumped frame is the 640x480 render target's bytes, and the golden verdict is the same as for an unresized window

### Requirement: Configuration file beside the executable
The enhancements layer SHALL read its file from the directory of the running executable (`<exe dir>/enhance.toml`; with a title name, `<exe dir>/<title>/enhance.toml` first), resolved portably with a working-directory fallback, keeping the precedence env > title file > root file > default. `RECOMP_ENHANCE_CONFIG=<path>` SHALL replace the file and `RECOMP_ENHANCE_CONFIG=none` SHALL read none. The layer SHALL log the files it read, so the resolved root is visible in every run log.

#### Scenario: File next to the binary
- **WHEN** `enhance.toml` with `[render] scale = 2` sits in the executable's directory and the game is started from another working directory with no `RECOMP_*` enhancement variables set
- **THEN** the log names that file and reads `render.scale=2`, and the backends render at 2×

#### Scenario: Bench reads no file
- **WHEN** a golden run starts with `RECOMP_ENHANCE_CONFIG=none` and a file sits beside the executable
- **THEN** the file is not read and every key is at its default
