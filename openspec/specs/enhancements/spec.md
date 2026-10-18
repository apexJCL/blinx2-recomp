# enhancements Specification

## Purpose
Defines the opt-in enhancements layer: render scale and the E1 present options (filter, resize, fullscreen), read from `enhance.toml` beside the executable or from the environment, all defaulting to stock so that goldens and stock behaviour never change.

## Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

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
