## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`, `textures.pack`, `textures.font`, `textures.text`, `menu.enabled`, `menu.hotkey`, `menu.chord`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, a texture pack is loaded, a host-option request is pending, an overlay panel is visible, or the frame and the output differ in size; the input hook SHALL be NULL and never called unless `menu.enabled` is on. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none`, `RECOMP_RENDER_SCALE=1`, `RECOMP_PRESENT_PACING=spin` and `RECOMP_MENU=off`. These pins SHALL stay even if a default changes. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `display.aspect` or `present.pacing`, a `textures.pack` other than `none`, `textures.font` or `textures.text` other than `on`, `menu.enabled` other than `off`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 present.pacing=spin (display.aspect=4:3)` followed by `[ENHANCE] textures.pack=none` and `[ENHANCE] menu.enabled=off`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a packed run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] textures.pack=enhance/hud.pack (41 entries: 40 art, 1 font, 0 text; scale 4, text 2; 0 bc3) textures.font=on textures.text=on`, without `--allow-enhance textures.pack=enhance/hud.pack`
- **THEN** the run is marked FAIL with a reason naming `textures.pack`; with the flag the frames are judged and the reason is printed as a note

#### Scenario: Golden harness rejects a menu run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] menu.enabled=on hotkey=F10 chord=back+start`, without `--allow-enhance menu.enabled=on`
- **THEN** the run is marked FAIL with a reason naming `menu.enabled`; with the flag the frames are judged and the reason is printed as a note

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
The kernel library SHALL provide an overlay panel (`nv2a_overlay.h`): a CPU-rasterised RGBA8 buffer with rectangles and 8x8 bitmap text at an integer scale, double-buffered and published with one atomic swap. Each presenter (the SDL renderer, the CAMetalLayer pass, the D3D11 flip) SHALL, when `nv2a_overlay_frame()` is non-NULL, upload the buffer as one texture when its generation changes and draw it alpha-blended as one quad inside the frame's placement rectangle, after the frame; when NULL nothing SHALL run. Frame dumps (`RECOMP_FB_DUMP`, `fb_dump_at`, `d3d11_dump`) SHALL never contain the panel. The Win32 GDI window of the CPU backend draws no panel (recorded).

#### Scenario: Panel drawn on three presenters
- **WHEN** the menu is open over `@stage1` on Metal (layer window), on the CPU backend (SDL renderer) and on D3D11 under Proton
- **THEN** a window shot of each shows the same panel at the same place relative to the frame, and a frame dump of the same flip shows no panel

#### Scenario: Hidden panel costs nothing
- **WHEN** the menu is closed
- **THEN** no overlay texture is bound or drawn by any presenter and the presenter's per-frame work equals a build without the layer

### Requirement: In-game enhancements menu
With `menu.enabled` (env `RECOMP_MENU`, default off), the layer SHALL install an input hook on `xbox_InputGetState` that opens and closes the menu on the pad chord `menu.chord` (default `back+start`, both held 400 ms on port 0; `lthumb+rthumb`; `none`) or the keyboard key `menu.hotkey` (default `F10`; `F1`..`F12`; `none`), consuming the chord's buttons so the title never sees them. While open the title SHALL receive a neutral pad (no buttons, triggers or stick deflection, packet number unchanged) and the menu SHALL navigate from the physical pad and keyboard (D-pad or left stick and arrows; A or Enter; B or Esc; left and right to step a value; Y to save). The guest SHALL keep running. The menu SHALL show pages Render (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`), Pack (`textures.pack` on/off, `textures.font`, `textures.text`, entries per kind, scales, hits, misses and the first four missed candidates with size and format, the CPU path's "ignored"), Game (items a title registers with `enhance_menu_add`), Stats (flips/s, frame ms, backend, scale in force), Controls (`menu.chord` and `menu.hotkey` as choices plus a capture of the next two-button chord or F-key, live at once and persisted by Save), Save and Reset to stock; an item that cannot change live SHALL say "applies at restart". It SHALL log `[ENHANCE] menu.enabled=off` or `[ENHANCE] menu.enabled=on hotkey=<k> chord=<c>` at startup. A scripted pad (`RECOMP_INPUT_SCRIPT`) SHALL never open the menu.

#### Scenario: Open, change, close
- **WHEN** F10 is pressed over `@stage1` with the menu enabled, the Render page's `render.scale` is stepped to 2, and F10 is pressed again
- **THEN** the panel appears within one flip, the frame renders at 1280x960 within two flips, the character has not moved while the panel was open, and the panel disappears with the game's input restored

#### Scenario: Chord consumed
- **WHEN** BACK and START are held together for 400 ms on a real pad
- **THEN** the menu opens and the title's pad poll never reports START or BACK down for that press; a START alone still pauses the game

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
