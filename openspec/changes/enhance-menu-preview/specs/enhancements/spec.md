## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `render.aniso`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`, `menu.enabled`, `overlay.stats`, `[input.actions]`) SHALL default to the stock behaviour, with one named exception: `present.pacing` defaults to `"sleep"` (decided by the user on 2026-10-12, after `sleep` gave every golden frame the same verdict as `spin` on Metal and D3D11, the same pace within `spin`'s own run-to-run spread, the same Burnout 3 screens and race pace, and no new audio starves, while cutting process CPU from 130% to 60% on the Mac and from 173% to 137% under Proton; `openspec/changes/archive/2026-10-17-fps-pacing`, D9). `"spin"` SHALL remain available as the console-original timing. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `render.aniso >= 2`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, a host-option request is pending, an overlay layer is visible, or the frame and the output differ in size. The overlay, the stats counters and the host-action hook SHALL compile only under `XBOXRECOMP_ENHANCE`. The stats counters SHALL be bumped only while the stats strip or the menu's Stats page is shown. The host-action hook (`xbox_enhance_pad_filter`) SHALL do nothing and return at its first test unless one of these is on: `menu.enabled`, `overlay.stats`, or a mod's own feature key (`camera.free`). A mod that registers actions SHALL NOT, by registering, turn the hook on. The startup line `[ENHANCE] actions hook=off|on` SHALL say which applies. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did; at `"sleep"` it SHALL draw the same frames and reach each screen at the same pace (`frame-pacing`). Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_CONFIG=none` (the legacy name `RECOMP_ENHANCE_CONFIG=none` SHALL keep working through the environment table's legacy column, with its one deprecation line), `RECOMP_RENDER_SCALE=1`, `RECOMP_PRESENT_PACING=spin` and `RECOMP_MENU=off`. These pins SHALL stay although the default of `present.pacing` is `sleep`, because goldens measure the console's timing, and even if a shipped `config.default.toml` turns a key on. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `render.aniso`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, `menu.enabled` or `overlay.stats` other than `off`, `actions hook=on`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with `RECOMP_CONFIG=none` and the per-key pins
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] config: none (RECOMP_CONFIG)`, then `[ENHANCE] render.scale=1 render.aniso=0 present.filter=nearest present.fullscreen=0 present.pacing=spin present.surface=window(auto) (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none`, `[ENHANCE] menu.enabled=off`, `[ENHANCE] overlay.stats=off` and `[ENHANCE] actions hook=off`

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

#### Scenario: Golden harness rejects a menu run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] menu.enabled=on open=F10,back+lthumb@400`, without `--allow-enhance menu.enabled=on`
- **THEN** the run is marked FAIL with a reason naming `menu.enabled`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a hooked run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] actions hook=on` (for example `camera.free=on` with the menu off)
- **THEN** the run is marked FAIL with a reason naming the action hook, unless `--allow-enhance` names the key that turned it on

### Requirement: Texture pack key
`textures.pack` (env `RECOMP_TEXTURES_PACK`, a path; a relative path resolves against the directory `xbox_enhance_init` was given) SHALL name a texture pack file (toolkit `docs/formats/texture-pack.md`: `XRTP` version 1 or 2, an index of `(hash, width, height, levels, flags, payload offset)` sorted by hash, and per entry A8R8G8B8 texels or, with `XRTP_FLAG_BC3`, BC3 blocks). In version 2 the entry flags SHALL carry the entry's kind (art, `FONT`, `TEXT`) and the BC3 flag; any other bit, and any non-zero flag in version 1, SHALL be refused. The layer SHALL read the file once at startup, before the guest starts, load the index, and log `[ENHANCE] textures.pack=none` when unset or `[ENHANCE] textures.pack=<path> (<n> entries: <a> art, <f> font, <t> text; scale <s>, text <ts>; <b> bc3) textures.font=<on|off> textures.text=<on|off>` when loaded, the path ending at the first space. `textures.font` (env `RECOMP_TEXTURES_FONT`) and `textures.text` (env `RECOMP_TEXTURES_TEXT`), `on` by default, SHALL turn the pack's entries of that kind off: a lookup for such an entry misses. A file that is missing, has another magic or version, an entry outside the file, or an unsorted index SHALL be refused whole with one line naming the reason, and the run SHALL continue at stock.

#### Scenario: Pack loaded
- **WHEN** `config.toml` holds `[textures] pack = "enhance/hud.pack"` and that file beside the executable is a valid version-2 pack of 41 entries, one of them `FONT`
- **THEN** the log reads `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on` and `tests/tex_pack` finds each of its hashes

#### Scenario: Bad pack refused
- **WHEN** the named file is truncated inside its index, or a version-2 entry sets flag bit 2
- **THEN** the log names the file and the reason, `nv2a_tex_pack_count()` is 0, and the frames equal a stock run's

#### Scenario: Font entries off
- **WHEN** `textures.font = "off"` and a pack with a `FONT` entry is loaded
- **THEN** `nv2a_tex_pack_find` returns NULL for that entry's hash and the art entries still match, and the log reads `textures.font=off`

### Requirement: Texture swap at upload
With a pack loaded, the Metal and D3D11 backends SHALL look up, on every texture upload (a cache miss, a changed hash, or a texture-cache generation older than the pack's), the texel hash they compute for the guest texture (`nv2a_tex_hash` over the bytes `nv2a_tex_extent` gives, without the P8 palette fold) in the pack's index, and on a hit SHALL create the host texture at the pack entry's width, height and level count and fill it from the pack's texels (A8R8G8B8 as BGRA8, or BC3 blocks in the backend's BC3 format) instead of the decoded guest texels. On a miss they SHALL record `(hash, width, height, format)` in the pack's miss ring (64 distinct entries with counts, each marked candidate when swizzled or DXT without mips), which `RECOMP_TRACE=tex_pack` prints every 600 flips. Everything else (the cache key, eviction, the per-flip rehash, samplers, UV scaling) SHALL be unchanged, so a texture the game rewrites stops matching and returns to its guest bytes on the next upload. The pack's texels SHALL be read from the file on the entry's first use and kept. Without a pack the only added statement per upload SHALL be the entry-count test. The CPU rasteriser SHALL ignore the pack and log `[ENHANCE] textures.pack ignored: the CPU rasteriser samples guest memory` once.

#### Scenario: HUD texture replaced on Metal
- **WHEN** `@stage1` runs on Metal with a pack holding the Latin font atlas and the life bar at 4x, and dumps a flip where the HUD is visible
- **THEN** the log's pack hit count is at least 2, the texels of the `Time:` text in the dump have more distinct edge levels than the stock dump at the same flip (sharper), the glyphs sit where the stock glyphs sit, and no magenta texel appears

#### Scenario: Rewritten texture leaves the pack
- **WHEN** the game writes new bytes over a texture that matched a pack entry
- **THEN** the next flip's rehash misses the index and the backend uploads the guest texels at the guest size

#### Scenario: Pack toggled live
- **WHEN** the pack is turned off from the menu while a replaced texture is resident, and on again a second later
- **THEN** within one flip of each change the texture is re-uploaded from the guest texels and then from the pack again, with no other cache entry disturbed

#### Scenario: Misses visible
- **WHEN** `@stage1` runs with a pack and `RECOMP_TRACE=tex_pack` and the game draws a `512x32` DXT3 texture the pack does not hold
- **THEN** a `[TEXPACK] miss <hash> 512x32 DXT3 x<n> candidate` line appears within 600 flips and the menu's Pack page lists the same hash and size

#### Scenario: CPU backend
- **WHEN** the CPU backend runs with `RECOMP_TEXTURES_PACK` set to a valid pack
- **THEN** the log says once that the pack is ignored and the frames equal a stock run's within the golden limits

## ADDED Requirements

### Requirement: Host options change at the flip
The enhancements layer SHALL change `render.scale`, `present.filter`, `present.fullscreen` and the texture pack's enabled kinds at run time only through `nv2a_host_opts_request(opts, mask)`, which queues one pending change that the active backend applies with `nv2a_host_opts_apply()` at the start of its next flip, on the thread that owns its GPU objects. A scale change SHALL drop every render target (Metal after writing it back to guest memory) and every cached texture there; a pack change SHALL advance the texture-cache generation so every resident texture is re-uploaded on its next bind. Without a pending request the flip SHALL cost one atomic load. The null and CPU backends SHALL apply requests too, and SHALL log their "ignored" line again when the scale changes. `present.pacing` SHALL change through `xbox_PacingSetMode` at once.

#### Scenario: Scale changed live on Metal
- **WHEN** `@stage1` runs on Metal with the menu open and `render.scale` steps 1, 2, 3, 1
- **THEN** the window shows each size within two flips, the run continues without a crash or a stuck target, the guest-sized write-back stays 640x480 throughout, and `[METAL] flip` lines show the uploads of the rebuilt targets

#### Scenario: Request from another thread
- **WHEN** `tests/host_opts_live` queues a scale request from a second thread while a fake flip loop runs `nv2a_host_opts_apply()`
- **THEN** exactly one apply returns the `SCALE` mask, `nv2a_host_opts()` reads the new value only after that apply, and the generation moved once

### Requirement: Overlay panel on the present path
The kernel library SHALL provide an overlay panel (`nv2a_overlay.h`): a CPU-rasterised RGBA8 buffer with rectangles and 8x8 bitmap text at an integer scale, in three layers (menu, stats, toasts), each with one writer thread, triple-buffered and published with one atomic exchange, and drawn through a canvas handle so no two writers share state. The overlay SHALL compile only under `XBOXRECOMP_ENHANCE`. Each presenter (the SDL renderer, the CAMetalLayer pass, the D3D11 flip) SHALL, when the overlay's `visible` mask is non-zero, upload each visible layer as one texture when its generation changes and draw it alpha-blended as one quad inside the frame's placement rectangle, after the frame (on D3D11 after `dump_frame()`); when the mask is zero nothing beyond that one load SHALL run. Frame dumps (`RECOMP_FB_DUMP`, `fb_dump_at`, `d3d11_dump`) SHALL never contain the panel. The Win32 GDI window of the CPU backend draws no panel (recorded).

#### Scenario: Panel drawn on three presenters
- **WHEN** the menu is open over `@stage1` on Metal (layer window), on the CPU backend (SDL renderer) and on D3D11 under Proton
- **THEN** a window shot of each shows the same panel at the same place relative to the frame (on D3D11 a host screenshot, since `RECOMP_WINDOW_SHOT` has no D3D11 implementation yet), and a frame dump of the same flip shows no panel

#### Scenario: Hidden panel costs nothing
- **WHEN** the menu is closed
- **THEN** no overlay texture is bound or drawn by any presenter and the presenter's per-frame work equals a build without the layer

### Requirement: In-game enhancements menu
With `menu.enabled` (env `RECOMP_MENU`, default off), the layer SHALL open and close the menu on the `menu.open` host action (default `F10` plus the pad chord the shipped `config.default.toml` names; see "Host actions"). While open the title SHALL receive a neutral pad (no buttons, triggers or stick deflection, packet number unchanged) and the menu SHALL navigate from the physical pad and keyboard (D-pad or left stick and arrows; A or Enter; B or Esc; left and right to step a value; Y to save). The guest SHALL keep running. The menu SHALL show pages Render (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`), Pack (`textures.pack` on/off, `textures.font`, `textures.text`, entries per kind, scales, hits, misses and the first four missed candidates with size and format, the CPU path's "ignored"), Game (items a title registers with `enhance_menu_add`), Mods (each registered mod, its state, a toggle through the mod's `on_enable` and its own items), Stats (flips/s, frame ms, backend, scale in force, the stats-strip toggle), Controls (every action's bindings, with capture and clear, live at once and persisted by Save), Debug, Save and Reset to stock; an item that cannot change live SHALL say "applies at restart". It SHALL log `[ENHANCE] menu.enabled=off` or `[ENHANCE] menu.enabled=on open=<bindings>` at startup. A scripted pad (`RECOMP_INPUT_SCRIPT`) SHALL never open the menu.

#### Scenario: Open, change, close
- **WHEN** F10 is pressed over `@stage1` with the menu enabled, the Render page's `render.scale` is stepped to 2, and F10 is pressed again
- **THEN** the panel appears within one flip, the frame renders at 1280x960 within two flips, the character has not moved while the panel was open, and the panel disappears with the game's input restored

#### Scenario: Chord consumed in BLiNX 2
- **WHEN** `menu.open` is bound to `back+lthumb@400` in BLiNX 2, and BACK then LTHUMB are held together for 400 ms on a real pad during play
- **THEN** the menu opens, and from the moment both are down the title's pad poll (through `cat_pad_get_state`) reports neither button; a START alone still pauses the game

#### Scenario: Game item
- **WHEN** a title registers `fx.glow` as a toggle on the Game page and the player toggles it
- **THEN** the item's `set` runs on the poll thread with `"off"` and the next frame is drawn without the glow

#### Scenario: Scripted pad ignored
- **WHEN** a `RECOMP_INPUT_SCRIPT` presses BACK and START together for a second with the menu enabled
- **THEN** the menu does not open and the title sees the presses

### Requirement: Menu saves to the configuration file
Save SHALL write the changed keys into the `config.toml` the layer read (the title file when there was one, else the data root's) through `recomp_cfg_patch`, as differences from `config.default.toml`: a key whose value differs is written (replaced in place keeping any comment, or appended under its table header, the header appended at the end when missing) and a key returned to its default is deleted (its header too once empty); the patcher writes a temporary file and renames it, never reorders or drops a comment, never touches another key, and refuses when its output does not parse to the original plus the changes. `config.default.toml` SHALL never be written. When the layer read no user file (`RECOMP_CONFIG=none`) Save SHALL be shown disabled with "no config file". A key an environment variable forces SHALL be marked "(env: RECOMP_...)" with the forced value shown; Save writes the file value all the same and the variable wins again at the next start. Unsaved live changes are lost at exit and the footer SHALL say "unsaved" while any exists.

#### Scenario: Difference written, comment kept
- **WHEN** `config/config.toml` holds `[render]` and `scale = 2   # my choice` and the player saves `render.scale = 3`
- **THEN** the line reads `scale = 3   # my choice`, every other byte of the file is unchanged, and the next start logs `render.scale=3`

#### Scenario: Missing table appended
- **WHEN** the file has no `[textures]` table and the player saves `textures.font = "off"`
- **THEN** the file ends with a blank line, `[textures]` and `font = "off"`, and it parses

#### Scenario: Reset deletes the key
- **WHEN** the file holds only `[render]` and `scale = 2` and the player resets `render.scale` to its default
- **THEN** the key and the then-empty `[render]` header are removed, the file is the comment header alone, and the next start reads `render.scale` from `config.default.toml`

#### Scenario: No file
- **WHEN** the run started with `RECOMP_CONFIG=none`
- **THEN** Save is shown disabled and nothing is written

### Requirement: Host actions
The enhancements layer SHALL provide named host actions with a registry that the toolkit and mods (mod API v2 `action_register`) fill at init. Actions are bound in `[input.actions]` to lists of bindings:
- a key, with optional modifiers;
- a pad chord of two or more buttons with an optional hold `@<ms>`;
- a single host-only button (`guide`, `misc1`, `paddle1`..`paddle4`, `touchpad`).

Actions SHALL be evaluated by one title-glue filter, `xbox_enhance_pad_filter(port, host, st)`. The toolkit's `xbox_InputGetState` and a title's own pad glue (cat's `cat_pad_get_state`) SHALL both call it after their merge. It reads the host pad and its host-only buttons apart from any script.

The layer SHALL refuse, with a warning:
- a single guest-pad button;
- a guest-button chord held less than 200 ms;
- a key or modifier present in the effective key map (the compiled-in defaults, `[input.bindings]`, `input.walk_key`, `input.mouse_release_key`).

A fired chord's buttons SHALL be reported released to the title from the moment all are down until each is physically released. A scripted pad (`RECOMP_INPUT_SCRIPT`) SHALL never fire an action. Keys injected by a kbm script fire key-bound actions like real keys. Actions SHALL never remap the title's pad.

The SDL2 backend SHALL report the host-only buttons. The XInput backend SHALL report `guide` through `XInputGetStateEx` when available.

The filter SHALL be armed only by a feature key (`menu.enabled`, `overlay.stats`, or a mod's enable key such as `camera.free`), never by registration alone. The layer SHALL log `[ENHANCE] actions hook=off` or `[ENHANCE] actions hook=on (<keys>)` at startup. Each fire SHALL log `[ACTION] <name> via <binding>`, limited to 10 lines a second.

#### Scenario: Chord fires and is consumed
- **WHEN** `menu.open` is bound to `back+start@400` and BACK and START are held together for 400 ms on a real pad
- **THEN** `menu.open` fires once and the title's poll reports neither button down from the moment both were down until each is released

#### Scenario: Single guest button refused
- **WHEN** `[input.actions]` binds `"camera.free.toggle" = ["a"]`
- **THEN** the binding is refused with one warning, the action keeps its other bindings, and the A button reaches the title

#### Scenario: Paddle on a native host
- **WHEN** `overlay.stats` is bound to `paddle1` on macOS with an Elite-style pad and the paddle is pressed
- **THEN** the stats strip toggles, and the title sees no change in its pad state

#### Scenario: Golden run disarmed
- **WHEN** `@stage1` runs with `RECOMP_CONFIG=none` on a build that includes the free-camera mod
- **THEN** the log reads `[ENHANCE] actions hook=off`, no `[ACTION]` line appears, and the filter returns at its first test on every poll

#### Scenario: Deck grip through Steam Input
- **WHEN** under Proton on the Deck a back grip is bound in Steam Input to F10 and pressed
- **THEN** `menu.open` fires through the key binding

### Requirement: Stats strip
With `overlay.stats` (env `RECOMP_OVERLAY_STATS`, default off) or the `overlay.stats` action, the overlay's STATS layer SHALL show fps, frame ms (average and worst of the last second), flips/s, the pacing mode, the scale in force and the backend, refreshed at 2 Hz. The counters behind it SHALL be bumped only while the strip, the menu's Stats page or `RECOMP_TITLE_STATS` is shown (one relaxed flag test per site otherwise). It SHALL be drawn by the three presenters like the menu and never appear in a frame dump. With the strip on, flips/s SHALL stay within 5% of the strip off on Metal and D3D11. The layer SHALL log `[ENHANCE] overlay.stats=off` or `=on` at startup, and the golden harness SHALL fail a run whose log shows `on` unless `--allow-enhance` names it.

#### Scenario: Strip absent from dumps
- **WHEN** `@stage1` runs on Metal with `RECOMP_OVERLAY_STATS=on`, a window shot and an `fb_dump` of the same flip
- **THEN** the window shot shows the strip and the dump does not
