# enhancements Specification

## Purpose
Defines the opt-in enhancements layer: render scale and the E1 present options (filter, resize, fullscreen), read from `enhance.toml` beside the executable or from the environment, all defaulting to stock so that goldens and stock behaviour never change.

## Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `present.filter`, `present.fullscreen`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, or the frame and the output differ in size. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_RENDER_SCALE=1`, and the golden harness SHALL fail a run whose log reports a non-stock `render.scale` or `display.aspect`.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 (display.aspect=4:3)`

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
The SDL presenter and the D3D11 window SHALL place each frame with `present.filter` (env `RECOMP_PRESENT_FILTER`): `nearest` and `linear` fit the frame's aspect, centred, with that filtering; `integer` shows the largest whole multiple that fits, centred, and falls back to a linear fit when even 1× does not fit, never cropping. Sizes are device pixels. `present.fullscreen = true` (env `RECOMP_PRESENT_FULLSCREEN`) SHALL open a borderless window covering the display. The D3D11 window SHALL follow resizes (`ResizeBuffers` on the thread that owns the device context) and present through a scaling blit when the frame and the back buffer differ in size or the filter is `linear`; at stock it SHALL keep the direct copy into a 640x480 back buffer. The SDL presenter at the default filter SHALL keep today's logical-size letterbox path. The Metal backend's CAMetalLayer window SHALL place frames with the same filters and geometry (`gpu-backend`, "Metal frames reach the window without a CPU round trip"). The D3D11 frame dump SHALL read the back buffer when the direct copy ran and the presented render target otherwise, so no filter or window size ever reaches a dump; under scale the dump is at host size and is not golden material.

#### Scenario: Integer mode in a large window
- **WHEN** a 640x480 frame is shown in a 1920x1080 output with `present.filter = integer`
- **THEN** it is drawn at 1280x960, centred, with black borders

#### Scenario: Integer mode falls back instead of cropping
- **WHEN** a 1280x960 frame (scale 2) is shown in a 1024x768 output with `present.filter = integer`
- **THEN** the whole frame is shown, fitted and centred with linear filtering

#### Scenario: Stock window unchanged
- **WHEN** the SDL presenter runs with the defaults
- **THEN** it uses the logical-size letterbox path, and a `RECOMP_WINDOW_SHOT` of a flip has the same letterbox geometry as a build without the layer

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

### Requirement: Glow toggle and intensity
BLiNX 2 SHALL offer two game keys in the enhancements layer, read once at startup before any guest thread runs, and only when the layer is built (`XBOXRECOMP_ENHANCE`):
- `fx.glow`: `"on"` (default) or `"off"`, env `RECOMP_GLOW`;
- `fx.glow_intensity`: a float clamped to 0.0..2.0, default 1.0, env `RECOMP_GLOW_INTENSITY`.

Both SHALL be bound to their env variables through `recomp_env` (CONFIG tier, `src/env/recomp_env_game.h`) and reported on one `[ENHANCE] fx.glow=<v> fx.glow_intensity=<v>` line.

The keys SHALL act only on the game's mode-3 glow composite, `sub_0005B7D0`, through a wrapper around its generated body:
- With `fx.glow = "on"` and `fx.glow_intensity = 1.0`, the wrapper SHALL call the generated body and SHALL neither read nor write guest memory.
- Otherwise it SHALL scale each colour byte of the glow weight at `0xADC744` by the cube root of the intensity, rounded to the nearest byte and clamped to 0xFF, keeping byte 3; `"off"` uses intensity 0. It SHALL call the generated body through `RECOMP_ABI_CALL`.
- After the call, the wrapper SHALL write the game's value back, unless the word no longer holds the scaled value, in which case it SHALL keep the newer game value.

The post mode, mode 4 (`sub_0005BC60`), both downsamples (`sub_0005B330`) and the game's per-frame fade of the weight (`sub_000E4140`) SHALL run as stock: the fade SHALL never read a scaled value.

#### Scenario: Defaults are stock
- **WHEN** the game runs with the layer and neither key set, or with `fx.glow = "on"` and `fx.glow_intensity = 1.0`
- **THEN** no guest word is written by the wrapper, the log reads `[ENHANCE] fx.glow=on fx.glow_intensity=1`, and the Metal goldens pass with the same verdicts as before the change

#### Scenario: Glow off
- **WHEN** Metal `@attract` runs with `RECOMP_GLOW=off` and dumps flip 1141
- **THEN** the frame matches a run with `RECOMP_DEBUG=poke=0xADC738:0` (the pass not issued) at that flip within the golden limits (channel mae ≤ 0.5, ≤ 0.5% pixels off by more than 8), and is darker than stock by 12 to 18 levels in mean RGB

#### Scenario: Half and double intensity
- **WHEN** Metal `@attract` runs with `RECOMP_GLOW_INTENSITY=0.5` and with `2.0`, each dumping flip 1141
- **THEN** each frame's mean glow layer (the frame minus the glow-off frame) is 0.40 to 0.60 and 1.5 to 2.2 times the stock layer, respectively

#### Scenario: Game weight restored
- **WHEN** the wrapper has run with `fx.glow_intensity = 0.5` and the game has not written `0xADC744` during the call
- **THEN** `0xADC744` holds the game's value again after the call; and when the game wrote it during the call, the game's new value is kept

#### Scenario: Game fade unchanged
- **WHEN** `@attract` runs for 60 s with `fx.glow_intensity = 0.5` and a write watchpoint on `0xADC744`
- **THEN** the values the game itself writes (every write that is not the wrapper's store-and-restore pair) form the same sequence as in a stock run of the same length

#### Scenario: Other post effects untouched
- **WHEN** the post mode is 4 or any value other than 3
- **THEN** the wrapper is not reached and the frame equals the stock frame

### Requirement: Glow keys stay out of goldens
The golden configuration SHALL pin `RECOMP_GLOW=on` and `RECOMP_GLOW_INTENSITY=1`. The golden harness SHALL fail a run whose log reports `fx.glow` other than `on` or `fx.glow_intensity` other than 1, unless the run is an evaluation run started with `--allow-enhance` for that key. Such a run SHALL NOT be used to record references.

#### Scenario: Harness rejects glow off
- **WHEN** `golden.py check` evaluates a run whose log contains `[ENHANCE] fx.glow=off fx.glow_intensity=1`
- **THEN** the run is marked FAIL with a reason naming `fx.glow`; with `--allow-enhance fx.glow=off` its frames are judged and the reason is printed as a note

#### Scenario: Backends agree
- **WHEN** one D3D11 run under Proton and one CPU run on the Mac each dump flip 1141 of `@attract` with `RECOMP_GLOW=off`
- **THEN** each matches the same backend's `poke=0xADC738:0` frame within the golden limits, as Metal does
