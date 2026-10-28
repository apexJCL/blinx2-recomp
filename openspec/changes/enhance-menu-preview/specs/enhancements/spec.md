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

### Requirement: Overlay on the present path
The kernel library SHALL provide an overlay (`nv2a_overlay.h`) with four layers (menu, stats, toasts, cursor). Each layer SHALL have one writer at a time, be triple-buffered and be published with one atomic exchange. A layer's slot SHALL hold a draw list of textured, coloured triangles with scissor commands, built from vendored microui (MIT) commands by one shared converter, with text from a font atlas baked by vendored stb_truetype from an embedded SIL OFL 1.1 face (Atkinson Hyperlegible Regular and Bold, under 0.7 MB embedded). The atlas SHALL never be baked on the guest's poll thread or a presenting thread. The overlay and the vendored code SHALL compile only under `XBOXRECOMP_ENHANCE`, each vendored file with its licence in `LICENSES/` and a `NOTICE` entry.

Each presenter (the SDL3 renderer, the CAMetalLayer pass, the D3D11 flip) SHALL draw the visible layers' draw lists with one renderer of its own, inside the frame's placement rectangle and after the frame (on D3D11 after `dump_frame()`). It SHALL upload a list's buffers only when its generation changes. The SDL3 renderer SHALL blend with `SDL_BLENDMODE_BLEND_PREMULTIPLIED`. On D3D11, a present that copied no guest frame SHALL clear the back buffer before drawing the overlay. When the `visible` mask is zero, nothing beyond that one load SHALL run. A golden run (`RECOMP_CONFIG=none`) SHALL never arm the overlay, create a UI context or bake an atlas.

Frame dumps (`RECOMP_FB_DUMP`, `fb_dump_at`, `d3d11_dump`, the Metal dump) SHALL never contain a layer. A CPU reference rasteriser of the same draw list SHALL back the `overlay` ctest. The Win32 GDI window of the CPU backend draws no overlay (recorded).

#### Scenario: Same picture on three presenters
- **WHEN** the menu is open over `@stage1` on Metal (layer window), on the CPU backend (SDL renderer) and on D3D11 under Proton
- **THEN** the Metal and SDL window shots each match the CPU reference raster of the same draw list within the stated tolerance, the D3D11 host screenshot shows the same panel at the same place relative to the frame, and a frame dump of the same flip shows no panel

#### Scenario: Hidden overlay costs nothing
- **WHEN** the menu, the stats strip and every toast are hidden
- **THEN** no overlay buffer is bound or drawn by any presenter, and the presenter's per-frame work equals a build without the layer apart from one atomic load

#### Scenario: Atlas baked off the poll thread
- **WHEN** the window is resized with the menu open so that the body text size changes
- **THEN** the atlas is rebaked on the overlay's worker thread, the old atlas is drawn scaled until the new one is published, and the guest's poll and flip times show no stall

#### Scenario: Golden run never arms the overlay
- **WHEN** `@stage1` runs with `RECOMP_CONFIG=none`
- **THEN** the log has no `[OVERLAY] atlas` line and no UI context or draw-list storage is allocated

### Requirement: Overlay theme and scale
The overlay SHALL size everything from theme tokens defined at 1080 output lines, multiplied by `clamp(out_h / 1080, 0.5, 3.0) * overlay.ui_scale`, where `out_h` is the placement rectangle's height in output pixels and `overlay.ui_scale` (default 1.0, 0.75 to 2.0) applies live. It SHALL NOT depend on `render.scale`. Every token (colours, radius, padding, gap, row height, font sizes, shadow) and the UI font files SHALL be settable in `[overlay.theme]`, from a game's `config.default.toml` and from the player's `config.toml`. A bad value SHALL be refused with one warning and the default kept. A font file that fails to parse SHALL leave the embedded face in use. A theme SHALL hold values and open-licensed fonts only. Labels SHALL be UTF-8 within the supported range (Latin-1, Latin Extended-A, general punctuation and arrows), and other code points SHALL draw a box.

#### Scenario: Same layout at any render scale
- **WHEN** the menu is open at 1080 output lines and `render.scale` steps from 1 to 3
- **THEN** the menu's draw list is unchanged

#### Scenario: Larger output, larger panel
- **WHEN** the same page is built at 720 and at 2160 output lines
- **THEN** every size in the 2160-line list is three times the 720-line size, rounded to whole pixels

#### Scenario: Game theme under the player's file
- **WHEN** a game's `config.default.toml` sets `[overlay.theme] accent = "#FF8800"` and the player's `config.toml` sets `accent = "#00FF00"`
- **THEN** the selection bar is drawn in `#00FF00`

### Requirement: In-game enhancements menu
With `menu.enabled` (env `RECOMP_MENU`, default off), the layer SHALL open and close the menu on the `menu.open` host action (default `F10` and `guide+a`; a game's `config.default.toml` may add a fallback chord for hosts where Guide does not reach the process; see "Host actions"). While open the title SHALL receive a neutral pad (no buttons, triggers or stick deflection, packet number unchanged) and the menu SHALL navigate from the physical pad and keyboard (D-pad or left stick and arrows; A or Enter; B or Esc; left and right to step a value; Y to save). The guest SHALL keep running; the menu SHALL NOT pause the title. The menu SHALL also take the mouse (see "Mouse in the menu"). It SHALL be drawn with microui on the overlay's menu layer. The menu SHALL show pages Render (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`), Pack (`textures.pack` on/off, `textures.font`, `textures.text`, entries per kind, scales, hits, misses and the first four missed candidates with size and format, the CPU path's "ignored"), Game (items a title registers with `enhance_menu_add`), Mods (each registered mod, its state, a toggle through the mod's `on_enable` and its own items), Stats (flips/s, frame ms, backend, scale in force, the stats-strip toggle), Controls (every action's bindings, with capture and clear, live at once and persisted by Save, plus the mouse capture state), Save states (see "Save states page"), Debug, Save and Reset to stock; an item that cannot change live SHALL say "applies at restart". It SHALL log `[ENHANCE] menu.enabled=off` or `[ENHANCE] menu.enabled=on open=<bindings>` at startup. A scripted pad (`RECOMP_INPUT_SCRIPT`) SHALL never open the menu.

#### Scenario: Open, change, close
- **WHEN** F10 is pressed over `@stage1` with the menu enabled, the Render page's `render.scale` is stepped to 2, and F10 is pressed again
- **THEN** the panel appears within one flip, the frame renders at 1280x960 within two flips, the character has not moved while the panel was open, and the panel disappears with the game's input restored

#### Scenario: Guide+A opens the menu
- **WHEN** Guide is held and A is pressed on a real pad on macOS during play with the menu enabled
- **THEN** the menu opens on the next flip, the title's pad poll never reports A down for that press, and the title keeps running behind the panel

#### Scenario: Fallback chord consumed in BLiNX 2
- **WHEN** BLiNX 2's shipped `menu.open` fallback `back+lthumb@400` is used: BACK then LTHUMB are held together for 400 ms on a real pad during play
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

Actions SHALL be evaluated by one title-glue filter, `xbox_enhance_pad_filter(port, host, st)`. The toolkit's `xbox_InputGetState` and a title's own pad glue (cat's `cat_pad_get_state`) SHALL both call it after their merge. It reads the host pad and its host-only buttons apart from any script. A modifier chord SHALL also be evaluated once per guest flip by a tick that makes its own host read (`xbox_input_backend_read_host`), so the menu opens even when the title has stopped polling the pad; with no pad open the tick SHALL clear its snapshot.

The layer SHALL refuse, with a warning:
- a single guest-pad button;
- a guest-button chord held less than 200 ms;
- a key or modifier present in the effective key map (the compiled-in defaults, `[input.bindings]`, `input.walk_key`, `input.mouse_release_key`).

A fired chord's buttons SHALL be reported released to the title from the moment all are down until each is physically released. A scripted pad (`RECOMP_INPUT_SCRIPT`) SHALL never fire an action. Keys injected by a kbm script fire key-bound actions like real keys. Actions SHALL never remap the title's pad.

A binding MAY be a modifier chord: a host-only button plus guest buttons (`guide+a`). It SHALL fire when the guest buttons are pressed while the host-only button is already down, with no hold. A guest button pressed before the host-only button SHALL NOT fire it. The guest buttons of a fired modifier chord SHALL be reported released to the title until each is physically released, and the button that closes the menu SHALL stay masked after closing until released. The guest-button-chord minimum hold does not apply to a modifier chord.

The SDL3 backend SHALL report the host-only buttons. The XInput backend SHALL report `guide` through `XInputGetStateEx` when available. Where a host takes Guide before the process (Steam Input on the Deck, the Windows Game Bar), the documented per-host table SHALL name the fallback binding, and F10 SHALL stay bound by default on every host.

One input SHALL fire one action. Two bindings take the same input when they are the same key with the same modifiers (an either-side modifier matching either side), or the same pad buttons on the same port whatever their holds. `menu.open`'s bindings SHALL never give way to another action's. Of any other two such bindings the one written in a file or the menu SHALL win over a default, and otherwise the action registered first SHALL keep it; the other SHALL be dropped at table build with one line, and no line SHALL report a binding as winning that is then dropped. The menu's capture SHALL refuse a binding another action owns, with a status line and a toast naming the owner and its binding. A pad binding whose buttons all belong to a longer binding on the same port SHALL fire on its release after its hold, and only if no longer binding was held whole while it was held, whether or not the longer one fired (a longer chord let go before its hold fires neither); it SHALL never read as held. No action SHALL fire while the menu captures a binding nor on port 0's next step after the capture ends (where keys are read; pad ports need no such step), and the inputs held during a capture SHALL stay spent until released.

The filter SHALL be armed only by a feature key (`menu.enabled`, `overlay.stats`, or a mod's enable key such as `camera.free`), never by registration alone. The layer SHALL log `[ENHANCE] actions hook=off` or `[ENHANCE] actions hook=on (<keys>)` at startup. Each fire SHALL log `[ACTION] <name> via <binding>`, limited to 10 lines a second.

#### Scenario: Chord fires and is consumed
- **WHEN** `menu.open` is bound to `back+lthumb@400` and BACK and LTHUMB are held together for 400 ms on a real pad
- **THEN** `menu.open` fires once and the title's poll reports neither button down from the moment both were down until each is released

#### Scenario: Modifier chord hides its guest button
- **WHEN** `menu.open` is bound to `guide+a`, Guide is held, A is pressed, and A is held after Guide is released
- **THEN** `menu.open` fires once on the A press, and the title's poll reports A released until A is physically released

#### Scenario: Guest button first does not fire
- **WHEN** A is held first and Guide is pressed after it
- **THEN** `menu.open` does not fire and the title sees A down

#### Scenario: Single guest button refused
- **WHEN** `[input.actions]` binds `"camera.free.toggle" = ["a"]`
- **THEN** the binding is refused with one warning, the action keeps its other bindings, and the A button reaches the title

#### Scenario: Paddle on a native host
- **WHEN** `overlay.stats` is bound to `paddle1` on macOS with an Elite-style pad and the paddle is pressed
- **THEN** the stats strip toggles, and the title sees no change in its pad state

#### Scenario: Golden run disarmed
- **WHEN** `@stage1` runs with `RECOMP_CONFIG=none` on a build that includes the free-camera mod
- **THEN** the log reads `[ENHANCE] actions hook=off`, no `[ACTION]` line appears, and the filter returns at its first test on every poll

#### Scenario: Guide+A while the title does not poll
- **WHEN** the title polls no pad (a loading screen) and Guide then A are pressed
- **THEN** the flip tick fires `menu.open` once from its own host read, and the title's next poll reports A released until A is physically released

#### Scenario: Deck grip through Steam Input
- **WHEN** under Proton on the Deck a back grip is bound in Steam Input to F10 and pressed
- **THEN** `menu.open` fires through the key binding

#### Scenario: Capture of an owned key refused
- **WHEN** the player captures a binding for `overlay.stats` on the Controls page and presses F10 (or the Deck grip Steam Input sends as F10)
- **THEN** the capture ends with `F10 refused: Open the menu has it (F10); clear it there first` as status and toast, `overlay.stats` gains no binding, and the menu stays open

#### Scenario: The menu keeps its input
- **WHEN** `[input.actions]` holds `overlay.stats = "F10"` (the binding the Deck capture saved) and F10 is pressed
- **THEN** the log has `overlay.stats: 'F10' refused: menu.open has it ('F10')`, the menu opens, and the stats strip does not toggle

#### Scenario: Written binding takes a default's input
- **WHEN** two mods register `zoom.toggle` (first) and `camera.toggle` with the default F6, `[input.actions]` holds `camera.toggle = "F6"`, and F6 is pressed
- **THEN** the log has `zoom.toggle (default): 'F6' gives way to camera.toggle ('F6')`, and only `camera.toggle` fires

#### Scenario: Longest match
- **WHEN** `menu.open` is bound to `guide+a` and `overlay.stats` to `guide`, and Guide is held, A pressed, and both released
- **THEN** only `menu.open` fires; Guide pressed and released alone fires `overlay.stats` once, on its release

#### Scenario: Longer chord let go before its hold
- **WHEN** `menu.open` is bound to `back+start+left_thumb@400` and `overlay.stats` to `back+start@400`, and Back+Start is held 400 ms, Left Thumb added for 200 ms, and all released
- **THEN** neither action fires

### Requirement: Mouse in the menu
While the menu is open the layer SHALL release the game's mouse capture (`xbox_InputMouseSuspend(1)`), so mouse-look and mouse buttons never reach the title, and on close SHALL restore the capture by mode: under `input.mouse_capture = "focus"` the capture returns, and under `"click"` the cursor stays free until the next click in the window. While the capture is suspended, and after a resume until each button has been released once, `mouse.c` SHALL drop mouse button and wheel edges, so the click that closes the menu never reaches the title.

`input.mouse_capture` SHALL accept `focus`, `click` and `never` (code default `focus`). cat's shipped file SHALL set `click` (the user, 2026-10-22). `input.mouse_free_keys` (a list of key names, code default `[]`, cat ships `["Escape"]`) SHALL free the capture when pressed without consuming the key, SHALL never grab, and SHALL be exempt from the key-map clash rule. These are file-only keys with no environment variable. The OS cursor SHALL be hidden over the window while the menu is open and the overlay's cursor drawn instead. `input.cursor_hide` (`never`, `idle`, `always`; code default `never`, shipped default `idle` after `input.cursor_idle_ms`, default 2000) SHALL govern the OS cursor while the menu is closed.

The window threads (SDL3 and Win32) SHALL publish the pointer as one atomic snapshot (position in output pixels, buttons, wheel, a sequence bumped last) before the game's mouse gate, and the menu SHALL read it on its own step. The menu SHALL support hover highlighting, left click to activate, the wheel to scroll a list or step a value under the pointer, and right click as back. A pad or key press SHALL hide the overlay cursor until the mouse moves again.

#### Scenario: Click a toggle
- **WHEN** the menu is open on macOS and the player clicks the stats-strip toggle on the Stats page with a trackpad
- **THEN** the strip toggles at the next flip and the game camera has not turned

#### Scenario: Capture restored
- **WHEN** the game had captured the mouse, the menu is opened and then closed
- **THEN** while the menu is open the OS cursor is hidden and the overlay cursor is drawn, and after closing the capture is back and mouse-look works

#### Scenario: Capture on click
- **WHEN** `input.mouse_capture = "click"` and `mouse_free_keys = ["Escape"]`, the game starts, the player clicks in the window, then presses Esc
- **THEN** the cursor is free until the click, which captures it and does not reach the title; Esc frees it and also reaches the title's bindings

#### Scenario: Click mode after the menu
- **WHEN** under `"click"` the mouse is captured, the menu is opened and then closed with a mouse click
- **THEN** the cursor stays free after closing, the closing click drives nothing in the title, and the next click captures the mouse again

#### Scenario: Idle hide
- **WHEN** `input.cursor_hide = "idle"` and the mouse rests for 2 seconds with the menu closed
- **THEN** the OS cursor is hidden and shows again on the next motion

### Requirement: Overlay cursor
The overlay SHALL draw its cursor on the cursor layer while the menu is open, in the style `[overlay.cursor] style` names (`arrow` default, `dot`, `image`). `image` SHALL take a PNG of at most 128x128 with a hotspot and a size, loaded through vendored stb_image built for PNG only. A file that is missing, too large or not PNG SHALL be refused with one warning and the arrow kept. A cursor image SHALL be the player's own file, never a distributed game asset. On D3D11 the cursor SHALL move at the guest flip rate (recorded).

#### Scenario: Owner cursor image
- **WHEN** `[overlay.cursor]` sets `style = "image"` and a 64x64 PNG with hotspot `[4, 4]`
- **THEN** the image is drawn with its hotspot at the pointer while the menu is open

#### Scenario: Oversized image refused
- **WHEN** the image is 256x256
- **THEN** one warning is logged and the arrow is drawn

### Requirement: Save states page
The menu SHALL have a Save states page over the save-states slot store: the slots with thumbnails and times, load, save to a new slot, rearrange, delete with a confirm row, export to `[states] export_dir` (default `<save dir>/exports/<game>/`, beside the saves; the user, 2026-10-22) and through the SDL3 save dialog where the host supports it, an Open folder row that opens the export folder in the host's file manager, and import with the save-states header refusals. It SHALL be shown only when save states are enabled, and SHALL say why an action is unavailable.

#### Scenario: Delete with confirm
- **WHEN** the player chooses Delete on slot 3 and confirms
- **THEN** slot 3 is removed from the store and the list shows the remaining slots in order

#### Scenario: Foreign file refused
- **WHEN** the player imports a state written by another game or build
- **THEN** the import is refused with the header's reason and no slot changes

### Requirement: Stats strip
With `overlay.stats` (env `RECOMP_OVERLAY_STATS`, default off) or the `overlay.stats` action, the overlay's STATS layer SHALL show fps, frame ms (average and worst of the last second), flips/s, the pacing mode, the scale in force and the backend, refreshed at 2 Hz. The counters behind it SHALL be bumped only while the strip, the menu's Stats page or `RECOMP_TITLE_STATS` is shown (one relaxed flag test per site otherwise). It SHALL be drawn by the three presenters like the menu and never appear in a frame dump. With the strip on, flips/s SHALL stay within 5% of the strip off on Metal and D3D11. The layer SHALL log `[ENHANCE] overlay.stats=off` or `=on` at startup, and the golden harness SHALL fail a run whose log shows `on` unless `--allow-enhance` names it.

#### Scenario: Strip absent from dumps
- **WHEN** `@stage1` runs on Metal with `RECOMP_OVERLAY_STATS=on`, a window shot and an `fb_dump` of the same flip
- **THEN** the window shot shows the strip and the dump does not
