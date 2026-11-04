# enhancements Specification

## Purpose
Defines the opt-in enhancements layer: render scale and the E1 present options (filter, resize, fullscreen), read from `enhance.toml` beside the executable or from the environment, all defaulting to stock so that goldens and stock behaviour never change.

## Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `display.aspect`, `display.movie`, `display.overscan`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL either return the stock value with every key at its default (as `nv2a_present_crop` does at `display.overscan = 0`: the whole frame, its stock UV scale and a zero offset, so the blit samples the same UVs) or be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, `display.overscan` is above 0, `display.aspect` is wider than 4:3 (a target with a non-zero `nv2a_host_pad`), a texture pack is loaded, or the frame and the output differ in size; `display.movie` acts only on a padded target. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 and pad 0 return their inputs, every Hor+ placement at pad 0 leaves the stock constants, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect`, `display.overscan` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

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
The enhancements layer SHALL read two files under the environment. The **defaults file** `config.default.toml` SHALL be read from the directory of the running executable (`recomp_exe_dir()`, resolved portably with a working-directory fallback; on Apple platforms, when absent there, from `<exe dir>/../Resources/`, the app bundle's layout), SHALL never be written by the layer or the game, and SHALL ship with every build and bundle so that a new version's keys apply to an existing install. The **user file** `config.toml` SHALL be read from `<root>/<title>/config.toml` (when a title is given) and then `<root>/config/config.toml`, where `root` is the user data root `xbox_enhance_init` was given; `RECOMP_CONFIG=<path>` SHALL replace both user locations with that one file and keep the defaults file; `RECOMP_CONFIG=none` SHALL read no file at all. The precedence SHALL be env > title file > user file > defaults file > the caller's default. `RECOMP_ENHANCE_CONFIG` SHALL be the row's legacy name, honoured when `RECOMP_CONFIG` is unset with the table's one deprecation line. The layer SHALL log one `[ENHANCE] config:` line naming every file it read with that file's key count (or `none (RECOMP_CONFIG)`), SHALL report an unparseable file with its line and skip it whole (the defaults file included), and SHALL list unread keys of every file through `enhance_cfg_report_unused`, a key a higher file overrides counting as read. A relative `textures.pack` SHALL resolve against the executable's directory, the root the defaults file is read from.

#### Scenario: File next to the binary
- **WHEN** `config.default.toml` beside the executable holds `[render] scale = 2`, no user file exists, the game is started from another working directory and no `RECOMP_*` enhancement variable is set
- **THEN** the log names that file with its key count, `enhance_cfg_source_of("render.scale")` is `ENHANCE_SRC_DEFAULTS`, and the backends render at 2×

#### Scenario: User file over defaults, environment over both
- **WHEN** the defaults file holds `scale = 2`, `config/config.toml` under the root holds `scale = 3`, and the game starts from another working directory with `RECOMP_CONFIG` pointing at that user file
- **THEN** the log names both files, `render.scale=3` is read from the user file; with `RECOMP_RENDER_SCALE=1` set as well the log adds `render.scale = 1 from RECOMP_RENDER_SCALE` and the backends render at 1×

#### Scenario: Bench reads no file
- **WHEN** a golden run starts with `RECOMP_CONFIG=none` while a defaults file and a user file exist
- **THEN** neither is read, the log reads `[ENHANCE] config: none (RECOMP_CONFIG)` and every key is at its code default

#### Scenario: Broken defaults file
- **WHEN** `config.default.toml` has a duplicate key
- **THEN** the log reports the file and line with `(file ignored)`, the user file and the environment still apply, and the run otherwise proceeds

#### Scenario: Pack path from the executable
- **WHEN** the user root is the working directory and `config.default.toml` beside the executable holds `[textures] pack = "enhance/hud.pack"`
- **THEN** the pack is opened at `<exe dir>/enhance/hud.pack` and the log's `textures.pack=` line names `enhance/hud.pack`

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

### Requirement: Texture pack key
`textures.pack` (env `RECOMP_TEXTURES_PACK`, a path; a relative path resolves against the executable's directory, `recomp_exe_dir()`) SHALL name a texture pack file (toolkit `docs/formats/texture-pack.md`: `XRTP` version 1, an index of `(hash, width, height, levels, payload offset)` sorted by hash, and A8R8G8B8 texels per entry). The layer SHALL read it once at startup, before the guest starts, load the file's index, and log `[ENHANCE] textures.pack=none` when unset or `[ENHANCE] textures.pack=<path> (<n> entries: <a> art, <f> font, <t> text; scale <s>, text <ts>; <b> bc3) textures.font=<on|off> textures.text=<on|off>` when loaded. A file that is missing, has another magic or version, an entry outside the file, or an unsorted index SHALL be refused whole with one line naming the reason, and the run SHALL continue at stock.

#### Scenario: Pack loaded
- **WHEN** `config.default.toml` holds `[textures] pack = "enhance/hud.pack"` and that file beside the executable is a valid pack of 41 entries at scale 4
- **THEN** the log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on` and `tests/tex_pack` finds each of its hashes

#### Scenario: Bad pack refused
- **WHEN** the named file is truncated inside its index
- **THEN** the log names the file and the reason, `nv2a_tex_pack_count()` is 0, and the frames equal a stock run's

### Requirement: Texture swap at upload
With a pack loaded, the Metal and D3D11 backends SHALL look up, on every texture upload (a cache miss or a changed hash), the texel hash they compute for the guest texture (`nv2a_tex_hash` over the bytes `nv2a_tex_extent` gives, without the P8 palette fold) in the pack's index, and on a hit SHALL create the host texture at the pack entry's width, height and level count and fill it from the pack's texels instead of the decoded guest texels. Everything else (the cache key, eviction, the per-flip rehash, samplers, UV scaling) SHALL be unchanged, so a texture the game rewrites stops matching and returns to its guest bytes on the next upload. The pack's texels SHALL be read from the file on the entry's first use and kept. Without a pack the only added statement per upload SHALL be the entry-count test. The CPU rasteriser SHALL ignore the pack and log `[ENHANCE] textures.pack ignored: the CPU rasteriser samples guest memory` once.

#### Scenario: HUD texture replaced on Metal
- **WHEN** `@stage1` runs on Metal with a pack holding the Latin font atlas and the life bar at 4x, and dumps a flip where the HUD is visible
- **THEN** the log's pack hit count is at least 2, the texels of the `Time:` text in the dump have more distinct edge levels than the stock dump at the same flip (sharper), the glyphs sit where the stock glyphs sit, and no magenta texel appears

#### Scenario: Rewritten texture leaves the pack
- **WHEN** the game writes new bytes over a texture that matched a pack entry
- **THEN** the next flip's rehash misses the index and the backend uploads the guest texels at the guest size

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_TEXTURES_PACK` set to a valid pack
- **THEN** the log says once that the pack is ignored and the frames equal a stock run's within the golden limits

### Requirement: Present surface for a scaling compositor
`present.surface` (env `RECOMP_PRESENT_SURFACE`) SHALL take `auto` (default), `window` or `internal`; another value SHALL be reported once and read as `auto`. `window` SHALL keep the existing behaviour: the swap chain follows the window and the game scales the frame into it. `internal` SHALL size the D3D11 window's client area and swap chain to the frame (640x480 × `render.scale`), SHALL NOT consult the screen size `present.fullscreen` uses nor resize the swap chain on `WM_SIZE`, and SHALL copy the frame into the back buffer without a scaling blit under every `present.filter`, so that the compositor scales it. `auto` SHALL resolve to `internal` when `RECOMP_HOST_GAMESCOPE` is true and to `window` otherwise; the resolved value and its reason SHALL appear on the `[ENHANCE]` options line, and the resolution SHALL happen once at init (no live change). The Metal presenter SHALL honour `internal` by keeping its drawable at the frame size and letting the layer scale it with the present filter's geometry. The SDL presenter SHALL ignore the key with one log line. `RECOMP_HOST_GAMESCOPE` SHALL be a config-tier row of the enhancement keys that no configuration file key binds, and the runtime SHALL NOT read gamescope's own variables. The SteamOS launcher SHALL export `RECOMP_HOST_GAMESCOPE=1` when `XDG_CURRENT_DESKTOP` is `gamescope` or `GAMESCOPE_WAYLAND_DISPLAY` is set, unless the variable is already set, and SHALL do so before `launch.env.default` and `config/launch.env` are loaded, so a user line wins.

#### Scenario: FSR-ready surface under gamescope
- **WHEN** the D3D11 build runs under gamescope at 1280x800 through the SteamOS launcher with `present.fullscreen = true`, `render.scale = 1` and no `surface` key
- **THEN** the log reads `present.surface=internal(auto: gamescope)` and `first present: back buffer 640x480 ... copy (surface internal)`, and gamescope receives a 640x480 surface to scale

#### Scenario: Scaled frame reaches the compositor whole
- **WHEN** the same run uses `render.scale = 2`
- **THEN** the back buffer is 1280x960 and the frame is copied into it with no box-downscale

#### Scenario: Desktop unchanged
- **WHEN** the D3D11 build runs with no hint and no key, with `present.fullscreen = true`
- **THEN** the window covers the screen, the back buffer follows it and the frame is placed by the scaling blit, exactly as before this change

#### Scenario: User override of the hint
- **WHEN** `config/config.toml` sets `present.surface = "window"` and the hint is set, or `config/launch.env` sets `RECOMP_HOST_GAMESCOPE=0` under gamescope
- **THEN** the surface is `window` and the log says `present.surface=window` (with `(auto)` in the second case)

#### Scenario: Bare executable under gamescope
- **WHEN** the D3D11 build is started without the SteamOS launcher under gamescope, with no key
- **THEN** no hint is set, `auto` resolves to `window`, and `RECOMP_PRESENT_SURFACE=internal` gives the `internal` behaviour

#### Scenario: Metal parity
- **WHEN** the Metal build runs with `RECOMP_PRESENT_SURFACE=internal`, `present.fullscreen = true` and `render.scale = 1`
- **THEN** the drawable is 640x480, the layer shows it letterboxed in the fullscreen view, and the frame dump is the same as under `window`

### Requirement: Guest-rate sampling of unity rect textures under scale
When `render.scale = N > 1`, a texture stage that samples a linear (rect) format from guest memory with a linear MIN or MAG filter SHALL, where its texcoords map one texel to one guest pixel along the screen axes (no cross derivatives, and a derivative of 1/N texel per host pixel on each axis, both within 1/64), sample at the coordinate the 1× render uses for the guest pixel that contains the host pixel. Stages whose source is a scaled render target, point-filtered stages, swizzled and compressed formats, magnified, minified, rotated or perspective mappings, and every stage at `render.scale = 1` SHALL sample as before. D3D11 and Metal, fixed-function, combiner, debug and probe shaders, SHALL apply the same rule, and the combiner shader text at `render.scale = 1` SHALL be unchanged.

#### Scenario: No padding at the movie edge
- **WHEN** the attract FMV (a 1024x512 YUY2 texture whose picture fills 640x480, drawn 1:1) renders at `render.scale = 2`
- **THEN** both host pixels of guest column 639 sample u = 639.5 (the probe reports `uv0 0.624512`), and the dumped frame's last column and row match the interior within the golden limits on Metal and D3D11

#### Scenario: Render-target source keeps host-rate detail
- **WHEN** a stage at `render.scale = 2` samples a scaled render target through a linear format
- **THEN** its snap constant is 0 and it samples at host rate, as before this change

#### Scenario: Stock sampling unchanged
- **WHEN** any scene renders at `render.scale = 1`
- **THEN** every stage samples at the same coordinates as before this change, the generated combiner shaders are byte-identical, and the goldens pass with the same verdicts

### Requirement: The user file holds differences only
`config.toml` SHALL hold only the keys whose value differs from `config.default.toml`: a writer (the in-game menu's Save, a later change) writes a key whose value differs from the defaults file's (or, when the key is absent there, from the code default) and deletes a key returned to that value; `config.default.toml` SHALL never be written. The layer SHALL expose what a writer needs: `enhance_cfg_user_path()` SHALL return the file Save writes (the title file when one was read or created, else the user root file or the `RECOMP_CONFIG` file; NULL under `none`), and `enhance_cfg_defaults()` SHALL return the parsed defaults file or NULL. When the user file the layer would read is absent and its directory exists, `enhance_cfg_init` SHALL create it as a comment header (no key) that names `config.default.toml` beside the executable and says that only changed keys live here and that the environment overrides it; the layer SHALL never create a directory, SHALL create nothing under `RECOMP_CONFIG=none`, and SHALL say once and go on when the write fails. A key present in the user file with the defaults file's value SHALL be read as any other (the layer does not judge equality on read).

#### Scenario: Header created on first launch
- **WHEN** the game starts with `RECOMP_CONFIG=<data>/config/config.toml`, `<data>/config/` exists and holds neither `config.toml` nor `enhance.toml`
- **THEN** `config.toml` is created holding only comment lines, parses to 0 keys, the log names it with `(0 keys)`, and `enhance_cfg_user_path()` returns its path

#### Scenario: No directory, no file
- **WHEN** the user root has no `config/` directory and `RECOMP_CONFIG` is unset
- **THEN** no file or directory is created, the log names the defaults file alone, and `enhance_cfg_user_path()` returns the path the file would have had

#### Scenario: Save path under none
- **WHEN** the run started with `RECOMP_CONFIG=none`
- **THEN** `enhance_cfg_user_path()` is NULL and `enhance_cfg_defaults()` is NULL

#### Scenario: A writer's comparison
- **WHEN** the defaults file holds `[render] scale = 1` and `[present] filter = "nearest"` and a writer is given `render.scale = 2` and `present.filter = "nearest"`
- **THEN** `enhance_cfg_defaults()` answers `1` and `"nearest"`, so the writer writes `scale = 2` and deletes any `filter` key the user file holds

### Requirement: One-time migration of enhance.toml
Before loading a user location whose basename is `config.toml` (the `RECOMP_CONFIG` file, `<root>/<title>/config.toml`, `<root>/config/config.toml`), when that file is absent and `enhance.toml` exists in the same directory, `enhance_cfg_init` SHALL rename `enhance.toml` to `config.toml` and log one line `[ENHANCE] config: renamed <dir>/enhance.toml to config.toml (one-time migration)`; a failed rename SHALL be said once and the run SHALL go on without that file. The layer SHALL NOT migrate `<root>/enhance.toml` (the pre-change root location), a `RECOMP_CONFIG` file with another basename, or anything under `RECOMP_CONFIG=none`, and SHALL NOT delete any file. The launchers SHALL stop copying any template, SHALL remove the `config/enhance.toml.default` copy they wrote in earlier versions, and SHALL set `RECOMP_CONFIG`. There is no compatibility window: the next release reads `config.toml` only.

#### Scenario: Renamed once
- **WHEN** `<data>/config/enhance.toml` holds `[render] scale = 2`, no `config.toml` exists there, and the game starts with `RECOMP_CONFIG=<data>/config/config.toml`
- **THEN** the file is now `config.toml` with the same bytes, the log has the rename line and reads `render.scale=2`; a second start shows no rename line

#### Scenario: Not a candidate
- **WHEN** `RECOMP_CONFIG=ecfg_init.toml` names a file that does not exist while `enhance.toml` sits beside it, or `<root>/enhance.toml` exists with `RECOMP_CONFIG` unset
- **THEN** nothing is renamed and no rename line is printed

#### Scenario: Developer build reads the repository's user file
- **WHEN** `./build/cat_recomp` starts from the repository root with `config/config.toml` holding `[render] scale = 2` and the build directory's `config.default.toml` at stock
- **THEN** the log names `build/config.default.toml` and `config/config.toml`, and `render.scale=2` is in force; `git status` shows `config/config.toml` neither untracked nor staged

### Requirement: Anisotropic filtering key
`render.aniso = N` (env `RECOMP_RENDER_ANISO`, through the `recomp_env` enhancement keys; 0 or 1 off, 2..16 the anisotropy, default 0) SHALL be carried in `nv2a_host_opts.aniso`, read at start, clamped to 0..16 with a log line, applied by Metal and D3D11 on the rule in `gpu-backend`, ignored by the CPU backend, and documented in the toolkit's `docs/runtime/config.md` and the game's `docs/env.md`.

#### Scenario: Out of range
- **WHEN** `render.aniso = 32` is set
- **THEN** the layer logs the clamp and uses 16; `render.aniso = 1` is stock with no log

### Requirement: Frame pacing key
`present.pacing` (env `RECOMP_PRESENT_PACING`) SHALL select how lowered spin-wait loops wait: `"spin"` busy-waits as the console did, `"sleep"` blocks in the runtime wait (`frame-pacing`). The layer SHALL read it once at startup, before the guest starts, and SHALL report it on the `[ENHANCE]` settings line. Without the layer the mode SHALL be `spin`. With the layer the default SHALL be `"sleep"`, set by a commit that can be reverted on its own, and the game's shipped `config.default.toml` SHALL state the key (`pacing = "sleep"`) so that a bundle's default is the file's, not the toolkit's. The default was allowed to change only once `sleep` met the acceptance rule against `spin` on the same build: the same verdict for every golden frame on the Metal goldens and on the D3D11 goldens under Proton (a frame exact in every `spin` run exact in every `sleep` run); flips/s, interval p50/p95 and the anchors' flip indices of `@stage1` and `@story-hub` within `spin`'s own run-to-run spread; no new `[AUDIO-HOST]` starves; and, on Burnout 3 under Proton, the same screens at the same flips, the race pace within spread, and no site over 5% timeout exits. The golden pins stay at `spin`.

#### Scenario: Sleep is the default
- **WHEN** the shipped `config.default.toml` has `[present] pacing = "sleep"`, the player's `config/config.toml` has no `pacing` key and no `RECOMP_PRESENT_PACING` is set
- **THEN** the `[ENHANCE]` line reads `present.pacing=sleep`, and the `pacing` trace reports `mode sleep` with wakes counted at site `0x00060475`

#### Scenario: Console-original timing on request
- **WHEN** the player puts `[present] pacing = "spin"` in `config/config.toml`, or sets `RECOMP_PRESENT_PACING=spin`
- **THEN** the `[ENHANCE]` line reads `present.pacing=spin`, the lowered loop busy-waits, and the `pacing` trace reports `mode spin` with no site counters

#### Scenario: Flip reverted
- **WHEN** the default-flip commits are reverted (the toolkit's and cat's)
- **THEN** the default is `"spin"` again in the code and in `config.default.toml`, and the golden configuration is unchanged

### Requirement: Packaged bundles say how to get the console-original pacing
When the game's `config.default.toml` staged into a bundle sets `[present] pacing = "sleep"`, `package` SHALL add one paragraph to the bundle's README.txt, after the paragraph on the two settings files, and SHALL print one note after the `bundle:` line. Both SHALL say that frame pacing defaults to `sleep` (the frame wait sleeps until the next vblank, which saves CPU and battery), that `spin` is the console-original timing (the wait holds a CPU core as on the Xbox), and how to select it: `pacing = "spin"` under `[present]` in `config/config.toml`, or `RECOMP_PRESENT_PACING=spin` in `config/launch.env`. When the file sets `"spin"` or has no `pacing` key, neither SHALL appear. A defaults file the CLI cannot parse SHALL produce one `WARNING:` line naming the error and no note. The note SHALL NOT be shown by a launcher or on game start. The CLI SHALL hold no game name or toolkit default for this: the text is game-agnostic and the condition is the game's own file.

#### Scenario: BLiNX 2 bundle
- **WHEN** `blinx2 package` runs with `packaging/config.default.toml` at `pacing = "sleep"`
- **THEN** the bundle's README.txt holds the frame-pacing paragraph with `pacing = "spin"` and `RECOMP_PRESENT_PACING=spin`, and the command prints the note once under `bundle:`

#### Scenario: A game that ships spin
- **WHEN** a game's `config.default.toml` has `pacing = "spin"`, or no `[present] pacing` key
- **THEN** README.txt has no frame-pacing paragraph, no placeholder is left in it, and nothing is printed about pacing

### Requirement: Frame-rate mode reports what is available
The title SHALL read `fps.mode` (env `RECOMP_FPS_MODE`, choices `lock30`, `lock60`, `free`, default `lock30`) before the layer reports unused keys. `lock30` SHALL run the game's own pacing and log `[ENHANCE] fps.mode=lock30`. `lock60` and `free` SHALL each log exactly one line saying the mode is not available for this title and why, and then run `lock30`, writing nothing to guest memory. A value outside the choices SHALL be reported once by the layer and treated as the default.

#### Scenario: lock60 asked for
- **WHEN** BLiNX 2 starts with `RECOMP_FPS_MODE=lock60`
- **THEN** the log has one line `[ENHANCE] fps.mode=lock60 not available for this title (...); using lock30`, the game runs at its stock 30 fps in 3D, and frames match a `lock30` run

#### Scenario: Key in the file is not reported unused
- **WHEN** `enhance.toml` sets `[fps] mode = "lock30"`
- **THEN** the unused-key report does not list `fps.mode`

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

### Requirement: Render-target reads agree across GPU backends
A texture stage whose address is a live render target's (low 27 bits) SHALL sample that target in place, on D3D11 and on Metal alike, when it reads the bytes the target's surface holds: R5G6B5 (linear or swizzled) for an R5G6B5 surface, A1R5G5B5 or X1R5G5B5 for an X1R5G5B5 surface, any 32-bit format for a 32-bit surface; swizzled for a swizzled surface, and linear at the target's pitch for a linear one; never DXT. Any other read at that address SHALL decode guest memory. A target sampled as a format with no alpha (R5G6B5, X1R5G5B5, X8R8G8B8) SHALL read alpha 1, in every shader path.

#### Scenario: Burnout 3 speed blur at 16:9
- **WHEN** the race-gate route runs at `display.aspect = "16:9"` on Metal or D3D11
- **THEN** the speed-blur chain's 320x240 and 160x120 R5G6B5 targets are sampled as render targets, the full-width composite `C8AF571F` is placed as a stretch, and the host frame shows no step at the old 4:3 edges beyond the scene's own

#### Scenario: A read the target cannot serve
- **WHEN** a target's address is sampled in another colour layout (a 32-bit target as 16-bit, R5G6B5 as X1R5G5B5, any target as A4R4G4B4), in the other memory order, or as a linear texture at another pitch
- **THEN** the stage decodes guest memory on both backends. On Metal a 16-bit read decoded memory before too; on D3D11 this is stricter than before, when a matching texel size (and pitch, if linear) was enough, and since D3D11 writes no target back such a read shows black. Under `RECOMP_TRACE=aspect` each rejected (surface format, pitch, texture format, pitch) is logged once as `[aspect.rt-reject]`

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

### Requirement: Free camera keys stay out of goldens
The `camera.*` keys (`camera.free`, `camera.free_speed`, `camera.free_look_sens`, `camera.free_hud`, `camera.free_toggle`, `camera.free_hud_key`, `camera.free_freeze_key`, `camera.free_reset_key`; env `RECOMP_CAMERA_FREE` and `RECOMP_CAMERA_FREE_*`) SHALL be game keys of the enhancements layer, read through the mod API's config getters before the unused-key report, and SHALL default to stock: `camera.free = "off"` registers no frame callback and no batch filter, and no wrapper writes guest memory. The game SHALL log `[ENHANCE] camera.free=<off|on>` once at start, `game.toml` `[golden] enhance_stock` SHALL list `camera.free = "off"`, and the golden harness SHALL fail a run whose log shows `camera.free=on`, unless the run is an evaluation run started with `--allow-enhance camera.free=on`. Such a run SHALL NOT be used to record references. `packaging/config.default.toml` SHALL hold every `camera.*` key at its stock value.

#### Scenario: Stock run untouched
- **WHEN** the Metal goldens run on the layer-ON build with `RECOMP_CONFIG=none`
- **THEN** each log has `[ENHANCE] camera.free=off`, no `[MOD camera.free]` line after the init line, and the same verdicts as before the module existed

#### Scenario: Harness rejects a free-camera run
- **WHEN** `blinx2 golden check` evaluates a run whose log contains `[ENHANCE] camera.free=on`
- **THEN** the run is marked FAIL with a reason naming `camera.free`; with `--allow-enhance camera.free=on` its frames are judged and the reason is printed as a note

### Requirement: Language setting
The kernel SHALL answer `ExQueryNonVolatileSetting(XC_LANGUAGE)` and the `XC_MAX_OS` block's +0x30 field with the language in force: `system.language` (env `RECOMP_SYSTEM_LANGUAGE`), one of `en ja de fr es it ko zh pt` as `XC_LANGUAGE` 1..9. Unset SHALL be English (1). An unknown code, or a code outside the game's declared list, SHALL be logged once and give English.

#### Scenario: Stock
- **WHEN** a game runs with no `system.language`
- **THEN** index 7 reads 1 and the block's +0x30 reads 1, as before this change

#### Scenario: French
- **WHEN** BLiNX 2 runs with `RECOMP_SYSTEM_LANGUAGE=fr`
- **THEN** index 7 reads 4 and the title screen and menus are in French

#### Scenario: Not shipped
- **WHEN** a game declaring `en, ja, fr, es` runs with `system.language = "de"`
- **THEN** one line names the declared list and the game runs in English

### Requirement: Declared languages
A game SHALL declare the languages it ships in `game.toml` `[system] languages`; the CLI SHALL pass them to the build as `XBOXRECOMP_LANGUAGES`. The in-game menu SHALL list a `Language` choice on the Game page with only those codes, marked as applying at restart, and SHALL list none for a game with no list.

#### Scenario: Menu
- **WHEN** a player picks `fr` in BLiNX 2's menu and saves
- **THEN** `config/config.toml` gains `language = "fr"` under `[system]`, and the next start is in French

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

### Requirement: Mods declare a static descriptor
The enhancements layer SHALL offer `XBOX_MOD_API_VERSION 3`. It SHALL add
an optional `desc` pointer at the end of `struct xbox_mod`, pointing to a
`const struct xbox_mod_desc`. The descriptor SHALL carry:
- `version` and `size`;
- title, summary, author and version text;
- typed settings;
- controls.

The layer SHALL read a descriptor before any `init` and only within its
`size`. A mod table without descriptors SHALL behave as under v2. A
descriptor that fails validation SHALL mark only that mod failed, with one
`[MOD]` line. Validation fails on any of:
- duplicate names or ids;
- `lo` greater than `hi`;
- an enum without choices;
- an unknown kind.

#### Scenario: Off mod still described
- **WHEN** cat runs with the menu on and `camera.free = "off"`
- **THEN** the free camera's detail page shows its title, summary, controls
  and settings

#### Scenario: v2 table
- **WHEN** a title registers a mod with no descriptor
- **THEN** its Mods row and sub-page are the ones 3D shows, and it runs
  unchanged

#### Scenario: Bad descriptor
- **WHEN** a descriptor declares two settings named `speed`
- **THEN** that mod's state is Failed with one `[MOD]` line, and the other
  mods and the game run

### Requirement: The layer owns mod settings
Each descriptor setting SHALL be bool, int, float or enum, with a default,
a range and step or its choices, help text and a live class. The live class
SHALL be one of:
- live;
- next activation;
- restart.

The layer SHALL resolve the value by this precedence, highest first:
1. the setting's env row;
2. the user file's key, then an alias in the user file;
3. the defaults file's key, then an alias in the defaults file;
4. the descriptor default.

A setting's key SHALL be its declared legacy key, or else the flat
`mods."<id>.<name>"`. The layer SHALL then clamp the value and snap it to
`step`, or fall back to the default for an unknown enum. Each adjustment
SHALL log one `[MOD]` line. Mods SHALL read the value through
`api->setting` without a lock. Changes from the menu SHALL reach
`on_setting` on the guest thread at the next mod frame. A restart-class
change SHALL only be recorded. No mod setting SHALL use the host-options
flush path.

At start, the layer SHALL print `[ENHANCE] <key>=<value>` for every
descriptor mod's enable setting, whether or not the mod is inited.

#### Scenario: Out of range
- **WHEN** `camera.free_speed = 50`
- **THEN** the camera uses 20 and the log has one
  `[MOD] camera.free.speed: 50 -> 20` line

#### Scenario: Live change
- **WHEN** the player changes Speed on the detail page while flying
- **THEN** the next frames fly at the new speed with no restart

#### Scenario: Stock enable line
- **WHEN** cat runs with no feature keys and the menu off
- **THEN** the free camera's `init` does not run, and the log still has
  `[ENHANCE] camera.free=off`

#### Scenario: Env-forced
- **WHEN** `RECOMP_CAMERA_FREE_SPEED=2` is set
- **THEN** the Speed row is greyed with "set by RECOMP_CAMERA_FREE_SPEED",
  and Save does not write it

### Requirement: Mod config keys survive edits
A mod's switch SHALL stay the flat `mods."<id>"` bool, default true, and
`false` SHALL keep the mod from being inited. A mod with an enable setting
SHALL show that setting as its Enabled row. Turning that row on SHALL also
remove a `mods."<id>" = false`.

A descriptor mod with its enable setting off SHALL be inited dormant only
when the menu is on and the enable setting is live-class; otherwise it
SHALL NOT be inited.

Aliases read from the user file SHALL be rewritten to the current key at
the next Save, even when nothing was edited. Aliases in the defaults file
SHALL NOT be rewritten.

Save, "Reset this mod" and "Reset all" SHALL NOT remove keys the layer does
not own:
- undeclared `mods."<id>..."` keys;
- undeclared `[input.controls]` keys;
- keys of mods missing from the build.

The unused-key report SHALL list those keys, including keys under a
descriptor mod that is off.

#### Scenario: Flat keys side by side
- **WHEN** a config has `[mods]` `"x" = true` and `"x.speed" = 2.0`, and
  mod `x` declares a setting `speed`
- **THEN** `x` is on with speed 2.0, and a Save of another change leaves
  both lines as they are

#### Scenario: Stale 3D switch
- **WHEN** a config has `[mods] "camera.free" = false` and
  `camera.free = "on"`
- **THEN** the free camera is not inited, its State reads
  "Off (mods."camera.free" = false)", and turning Enabled on and saving
  removes the `mods."camera.free"` line

#### Scenario: Live enable from the menu
- **WHEN** the menu is on, `camera.free = "off"`, and the player turns
  Enabled on
- **THEN** the camera was inited dormant at start, and F6 starts flight
  without a restart

#### Scenario: Unknown key kept
- **WHEN** a config has `[mods] "camera.free.colour" = "red"` and the
  player resets the free camera and saves
- **THEN** the line is still in the file, and the log lists it as unused

#### Scenario: Alias
- **WHEN** the user file has `camera.free_freeze_key = "F8"` and the player
  saves without editing anything
- **THEN** `camera.free.freeze` is bound to F8, and the file has
  `"camera.free.freeze" = ["F8"]` in `[input.actions]` and no
  `camera.free_freeze_key`

### Requirement: Mod controls are shown and rebindable
Descriptor controls SHALL be actions, captured buttons, captured sticks or
info rows. Actions SHALL be registered from the descriptor as
`<id>.<verb>`, owned by the mod, and a mod SHALL get their ids through
`api->control_action`. An action's env row, when set, SHALL replace its
bindings.

While the mod is off, its actions SHALL be dormant:
- they are listed and rebindable;
- they are conflict-checked and count in the "one input fires one action"
  resolution;
- they never fire, never consume input and never arm the actions hook.

Captured controls SHALL be bound in `[input.controls]` to guest buttons,
triggers or sticks, or to host keys. They SHALL be read through
`api->control_value` from port 0's guest state, which the layer records
after the consumed-chord mask and before the neutral pad. The layer SHALL
record it only while a mod holds input capture, and SHALL record whether
the port is connected. `xbox_InputGetState` SHALL record it whether or not
the pad filter is installed, and while a mod holds capture SHALL give the
guest a connected, released port 0 with a new packet number when the
neutral pad starts and ends.

Capture SHALL refuse:
- a binding another action owns, dormant ones included;
- a captured binding another captured control of the same mod uses;
- a captured key that is an action's single key, and an action binding on
  a key a captured control names;
- a host source with no guest slot for a captured control.

A captured single button SHALL coexist with an action chord that contains
it.

#### Scenario: Dormant action blocks a duplicate
- **WHEN** the free camera is off and the player binds F6 to `shot.window`
- **THEN** the capture is refused, and the footer reads "F6 is Free camera:
  Toggle flight"

#### Scenario: Stock run
- **WHEN** cat runs with no feature keys
- **THEN** the log has `[ENHANCE] actions hook=off`, no dormant action
  reads input, and no port-0 state is recorded

#### Scenario: Chord over a captured button
- **WHEN** the player is flying and presses Y
- **THEN** the camera sinks, and when the player holds Guide and presses Y,
  flight toggles off and the camera does not sink

#### Scenario: input_core title with the hook disarmed
- **WHEN** a title on input_core has a mod holding capture, no feature key
  arms the actions hook, and the player pushes the left stick
- **THEN** the mod reads the stick through `control_value`, and the guest
  reads port 0 connected and released

#### Scenario: Dormant default over a live default
- **WHEN** a dormant mod's action default and another action's default
  name the same input
- **THEN** the first registered keeps the input and one `[MOD]` line names
  both actions and the input

#### Scenario: Paddle refused for a fly control
- **WHEN** the player captures `paddle1` for `camera.free.rise`
- **THEN** the capture is refused with "fly controls take buttons the game
  sees"

#### Scenario: Remapped pad
- **WHEN** the player's pad mapping sends the host A button to the guest X
  button, and the player presses host A to capture `camera.free.rise`
- **THEN** the binding stored is `x`, and pressing host A raises the camera

### Requirement: Mods page detail view
Every row on the Mods page SHALL open a detail page with these rows:
- the title and version;
- Author;
- About, word-wrapped to the panel width;
- State;
- Enabled;
- a Controls section;
- a Settings section;
- "Reset this mod".

Each setting row SHALL show whether it applies live, at next activation or
at restart. Control rows SHALL list their bindings, the keys that reach the
same pad source through `[input.bindings]`, and their "when" note. The
footer SHALL show the selected row's help. A failed mod's page SHALL
still list its controls and settings, marked unavailable. The Controls page SHALL group
actions by owner under the owner's title. Metal and D3D11 SHALL draw the
page the same way.

#### Scenario: Help text
- **WHEN** the player selects the Speed row
- **THEN** the footer shows the setting's help text

#### Scenario: Restart-only setting
- **WHEN** a mod declares a restart-class setting and the player changes it
- **THEN** the row reads "applies at restart", and the mod's value is
  unchanged until the next start

### Requirement: The free camera declares its info, controls and settings
The cat free camera SHALL declare a descriptor with these parts.

**Actions:**

| action | defaults | alias | env |
|---|---|---|---|
| `camera.free.toggle` | `F6`, `guide+y` | `camera.free_toggle` | `RECOMP_CAMERA_FREE_TOGGLE` |
| `camera.free.hud` | `F7` | `camera.free_hud_key` | `RECOMP_CAMERA_FREE_HUD_KEY` |
| `camera.free.freeze` | `End` | `camera.free_freeze_key` | `RECOMP_CAMERA_FREE_FREEZE_KEY` |
| `camera.free.reset` | `Home` | `camera.free_reset_key` | `RECOMP_CAMERA_FREE_RESET_KEY` |

**Captured controls** (in `[input.controls]`):

| control | kind | defaults |
|---|---|---|
| `move` | stick | `left_stick` |
| `look` | stick | `right_stick` |
| `rise` | button | `rt`, `x` |
| `sink` | button | `lt`, `y` |
| `fast` | button | `white` |
| `slow` | button | `black` |
| mouse look | info | none |

**Settings:**

| setting | type | values | applies |
|---|---|---|---|
| `camera.free` | enable | off/on | live |
| `camera.free_speed` | float | 0.05..20, default 1 | live |
| `camera.free_look_sens` | float | 0.05..10, default 1 | live |
| `camera.free_mouse_sens` | float | 0.05..10, default 1 | live |
| `camera.free_invert_x` | bool | default false | live |
| `camera.free_invert_y` | bool | default false | live |
| `camera.free_fast` | float | 1..20, default 4 | live |
| `camera.free_slow` | float | 0.05..1, default 0.25 | live |
| `camera.free_hud` | enum | keep/hide | next activation |

With the default bindings and settings it SHALL fly exactly as before,
each stick with its own dead zone. The toolkit SHALL print the `[ENHANCE] camera.free=on|off`
line with today's text.

#### Scenario: Invert
- **WHEN** `camera.free_invert_y = true` and the player pushes the right
  stick up while flying
- **THEN** the camera pitches down, and mouse motion is inverted the same
  way

#### Scenario: Fast multiplier
- **WHEN** `camera.free_fast = 8` and the player holds White while flying
- **THEN** the camera moves at 8 times its normal speed, and with the
  default 4 it moves as it does today

#### Scenario: Mouse sensitivity alone
- **WHEN** `camera.free_mouse_sens = 2` and `camera.free_look_sens = 1`
- **THEN** mouse look turns twice as fast as today and stick look is
  unchanged

#### Scenario: Rebound rise
- **WHEN** the player binds `camera.free.rise` to Space on the detail page
  and flies
- **THEN** Space raises the camera, and the guest receives the neutral pad

#### Scenario: Off from the menu mid-flight
- **WHEN** the player turns Enabled off on the detail page while flying
- **THEN** at the next frame the game camera is restored, freeze is
  dropped and the HUD is shown

### Requirement: Mods expose every sensible setting
A mod with a descriptor SHALL expose as a setting every value it holds
that a player could sensibly want to change. Each value kept as a
constant SHALL have a recorded reason: another setting covers it, the
toolkit owns it for every input, it keeps the game or the maths correct,
or it is a game fact or a diagnostic.

#### Scenario: Free camera audit
- **WHEN** a reviewer reads the free camera's descriptor
- **THEN** a comment above its settings table lists each constant left
  out (the stick dead zones, the pitch limit, the frame-time cap, the
  trigger threshold, roll, FOV, the freeze rules) with its reason

### Requirement: Descriptor dump
With `RECOMP_MODS_DESCRIBE=json` the toolkit SHALL write every registered
mod's descriptor and resolved values as JSON (schema 1), then exit 0
before the game starts. It SHALL run no mod `init` and arm nothing. With
`RECOMP_MODS_DESCRIBE_OUT=<path>` it SHALL write the JSON to that file,
otherwise to stdout. Each setting and binding SHALL carry its value and
the precedence source that won. Each mod SHALL carry what the init rule
would do. Later versions SHALL only add fields unless they bump `schema`.

#### Scenario: Stock dump
- **WHEN** cat runs with `RECOMP_MODS_DESCRIBE=json` and no config
- **THEN** stdout holds one JSON document listing `camera.free` with
  `"init": "no"`, every setting at its default with `"source": "default"`,
  and its 11 controls, and the process exits 0 without a window

#### Scenario: Env-forced value in the dump
- **WHEN** `RECOMP_CAMERA_FREE_SPEED=3` and the dump is requested
- **THEN** the `speed` setting reads `"value": 3` and `"source": "env"`

#### Scenario: Dump to a file
- **WHEN** `RECOMP_MODS_DESCRIBE_OUT` names a writable path
- **THEN** the JSON is written there, replacing the file, and nothing is
  written to stdout; an unwritable path logs one `[MOD]` line and exits 1

### Requirement: Shader profiles default to stock
`present.profile` SHALL default to `"none"`. With it `none` and
`present.shader` `none`, no profile SHALL be composed, no chain built and the
present SHALL be stock, and no profile file SHALL be read before the menu
opens the Shaders page. With `RECOMP_CONFIG=none` no profile file SHALL be
read.

#### Scenario: Golden run
- **WHEN** a golden runs with `RECOMP_CONFIG=none`
- **THEN** the log shows `present.profile` off and the frames match stock

### Requirement: A profile is an ordered chain with its own values
A shader profile SHALL be a TOML file `<root>/config/shader-profiles/<slug>.toml`,
in that folder even when a per-title config file exists, with `version = 1`, a `name`, a `stages` array of 1 to 8 preset references
(the `present.shader` grammar), and `[params.<preset key>]` tables holding
only the values that differ from the composed preset's. A file with an
unknown higher version SHALL be listed read-only and never written; a file
that does not parse SHALL be listed as broken and never written. A value
for a parameter shared by several stages SHALL be read from any stage's
table and saved under the first stage that declares it.

#### Scenario: Round trip keeps comments
- **WHEN** the menu saves a hand-written profile after moving a stage
- **THEN** only the `stages` line changes, unless a shared value changes owner, and its comments and unknown keys stay

### Requirement: A multi-stage profile runs as one composed preset
A profile of two or more stages SHALL be composed into one `.slangp` (passes
in stage order, each preset's own pass settings, absolute paths, the earlier
stage winning a preset parameter value) and run through the same path as
`present.shader` on Metal and D3D11. A one-stage profile SHALL run its
preset as `present.shader` does. A parameter name declared by more than one
stage SHALL be one value, and the menu SHALL mark its row "shared with
stage N", naming the first stage that declares it. Preset-level
`parameters` lists SHALL be merged without duplicates. Paths SHALL be
written quoted with forward slashes. Two stages declaring the same alias or
texture name SHALL NOT compose, nor SHALL a stage after the first that
refers to a pass by index (`PassOutputN`, `PassFeedbackN`).

#### Scenario: FSR then CRT
- **WHEN** the profile's stages are `fsr`, `crt-lottes`
- **THEN** the chain has three passes on Metal and on D3D11, and the menu lists the parameters of both

### Requirement: A failed profile presents stock and says so
A profile that is missing, broken, refused by the composer or whose chain
fails to build SHALL give the stock present, one `[SHADER]` line naming the
profile and, where known, the stage, and a red row on the Shaders page. It
SHALL NOT be retried until the next change.

#### Scenario: A stage is missing
- **WHEN** a profile names a `.slangp` that does not exist
- **THEN** the present is stock, the log names the stage, and the Chain header is red

### Requirement: The existing shader setting keeps working
`present.shader` and `present.shader_params` SHALL keep their meaning. The
bundled presets SHALL appear as built-in one-stage profiles whose values are
those keys. `RECOMP_PRESENT_SHADER` SHALL win over a profile, and
`RECOMP_PRESENT_PROFILE` over the config. Among the config layers the
highest layer that sets either `present.profile` or `present.shader` SHALL
decide, and within it a set `present.profile` SHALL win over
`present.shader`; a set but missing profile SHALL give stock, not
`present.shader`. When the menu saves a choice that needs a key gone and a
lower layer sets that key, it SHALL write the key as `"none"`.

#### Scenario: A per-title shader over a shared profile
- **WHEN** the per-title config sets `present.shader = "fsr"` and `<root>/config/config.toml` sets `present.profile = "soft-crt"`
- **THEN** the run presents `fsr`

#### Scenario: An existing config
- **WHEN** a config has `present.shader = "crt-lottes"` and tuned `[present.shader_params.crt-lottes]` and no profile
- **THEN** the run is unchanged and the Shaders page shows the built-in *crt-lottes* with those values

### Requirement: The Shaders page edits profiles on pad and keyboard
The Shaders page SHALL let the player pick the active profile (Off, the
built-ins, user profiles), add a stage, move a stage earlier or later, remove
a stage (with a confirm, never the last), edit a stage's parameters, reset
them, save as new, duplicate, rename and delete a profile, with the menu's
existing events on the pad and the keyboard. Save SHALL write only the
profiles that changed and only the values that differ from the presets'.

#### Scenario: Reorder and save
- **WHEN** the player moves a stage with Right and presses Save
- **THEN** the chain changes at the next present and the profile file's `stages` line is the only line rewritten, unless a shared value changes owner

#### Scenario: Typing a name
- **WHEN** the player renames a profile on the keyboard and types Q, E, Y or Space
- **THEN** the characters go into the name and no page change or Save fires

### Requirement: Profile limits and the user presets folder
A profile SHALL hold at most 8 stages, and its composed preset at most 16
passes. An edit past either limit SHALL be refused with a footer message,
and a file past the stage limit SHALL load its first 8 stages with one log
line. The Add shader picker SHALL list the bundled presets and then the
`.slangp` files in `<root>/shaders/`; a user preset whose name equals a
bundled one SHALL be refused. A stage's relative or bare name SHALL resolve
against `<root>/shaders/` before the executable's directory. A profile SHALL NOT carry per-pass
scale or filter settings: each pass SHALL keep its preset's own.

#### Scenario: Ninth stage
- **WHEN** the player adds a stage to a profile that has 8
- **THEN** the Add row is dimmed and the footer names the limit

### Requirement: 2D textures on the guest grid
`render.snap_2d` (env `RECOMP_RENDER_SNAP_2D`, default `false`, live) SHALL do the following above `render.scale` 1 on Metal and D3D11. A bilinear texture stage on a 2D batch SHALL sample at its guest pixel's 1x sample point, with gradients equal to the 1x ones.

A batch is 2D when either:
- it is pre-transformed; or
- it is a program batch whose scanned vertices share one whole `oPos.w` and one `oPos.z`.

In addition, the batch must be on an unpadded target or centred on a padded one. The stage's mapping must be axis-aligned, with u along x and v along y.

The snap SHALL leave alone render-target stages, 3D batches, STRETCH and COVER placements, and 90-degree mappings.

While it is on, the walker SHALL NOT merge back-to-back batches.

With the key off, the backends SHALL compile the same basic and combiner shader texts as before the key existed. They SHALL write the same constants and do no 2D scan beyond the one Hor+ runs.

#### Scenario: Stock run unchanged
- **WHEN** JSRF runs the dogenzaka golden on D3D11 on the Deck with `render.snap_2d` off
- **THEN** every checked frame is EXACT, as on the toolkit before the key

#### Scenario: Seams gone at scale 2
- **WHEN** BLiNX 2 shows its loading screen at `render.scale` 2 with `RECOMP_RENDER_SNAP_2D=1`
- **THEN** no light line shows between the loading-screen tiles, and the snap shader variants build with no `FAILED` line
