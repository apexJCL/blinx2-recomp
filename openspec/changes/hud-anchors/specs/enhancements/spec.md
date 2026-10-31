## ADDED Requirements

### Requirement: HUD anchor service
The mod API SHALL offer a HUD anchor service, appended after mod-connectivity-layer's fields:
- `hud_table` registers a game's HUD table, given as TOML text: a canvas, the 2D vertex layout (stride, x and u offsets, vertices per primitive), wrappers, groups (a name, a kind of `centre`, `left`, `right`, `proportional`, `world` or `stretch`, an optional reference x and, for `world`, an optional `park` bound) and sites (a call's return address, an element name and a group). A duplicate return address, an unknown group or kind, a wrapper with no hook slot, a bad canvas or an unknown table version SHALL fail registration with a log line. A site with no group SHALL be its own group.
- Each wrapper's entry SHALL push the return address on a per-guest-thread chain, at most 8 deep, and its exit SHALL pop it. Only the owning thread SHALL write a chain: `xbox_mod_frame`, once per guest frame on the guest thread and outside any wrapper, SHALL bump a global epoch; each entry SHALL carry the epoch of its push, and a push SHALL first drop its own entries 2 or more epochs old. A pop on an empty chain SHALL do nothing.
- `hud_apply`, called from a hook on the call that takes the vertices, SHALL resolve the element from the chain's outermost entry inwards, then from the call's own return address, taking the first matching site. No match SHALL mean an unlisted site.
- A call whose vertex count is not a multiple of the layout's vertices per primitive, or one over the restore cap, SHALL be left unchanged and unclipped, with one `[hud.skip]` trace line per site.
- `hud_apply` SHALL then shift, clip or map the call's primitives, in guest pixels of the canvas's target:
  - a full-width primitive (its span reaches both 4:3 edges within 2 guest pixels) in a group that is not `stretch`, and a `world` primitive within its group's `park` bound, SHALL be left unchanged; a `world` primitive past that bound SHALL be moved past the wide frame's edge;
  - a `stretch` primitive SHALL be mapped as the Stretch kind requirement says;
  - every other primitive SHALL be shifted by its group's offset (0 for `centre` and unlisted); all primitives of one group in one frame SHALL get the same offset, its reference held with its epoch in one atomic set by compare-and-swap;
  - a primitive wholly outside its window (the target's 4:3 columns [0, w] in guest pixels, moved by the offset; a view only maps units) SHALL be moved past the wide frame's edge on its side;
  - an axis-aligned primitive crossing its window SHALL be clamped to it, with u interpolated at the new x;
  - a primitive that crosses its window and is not axis-aligned SHALL be left as it is and counted.
- With `XBOX_HUD_RESTORE`, the layer SHALL save the vertices it changed (up to 1024 per call) and `hud_restore` SHALL put them back at the hook's exit.
- The service SHALL keep one atomic active flag, set while the registering mod's switch is on, a table is registered and the pad is above 0, or while a capture runs, and recomputed in `xbox_mod_frame` and on a switch or aspect change. The wrappers' entry and exit and `hud_apply` SHALL return on a clear flag before any other work. With the flag clear, `hud_apply` SHALL change no byte; a capture sets it for recording only and also changes no byte.

Under `RECOMP_TRACE=hud` the layer SHALL log each distinct site with its element, group, kind and offset; each distinct unlisted site whose primitives cross or lie outside the 4:3 window, with its x range; each site with a crossing primitive that is not axis-aligned; each site whose call was skipped; the canvas whenever it changes; and the lift state.

#### Scenario: An element named through two wrappers
- **WHEN** BLiNX 2's Time is drawn by `sub_0006B1F0` through the font routine and a sprite helper, with the mod on at 16:9
- **THEN** all five outline passes resolve to the Time row, from the font routine's caller, and move together by -107

#### Scenario: Unlisted sprite keeps the stock clip
- **WHEN** a pause panel sprite from an unlisted site reaches x 330 at 16:9 with the mod on
- **THEN** it is not shifted and is clamped to x 320, as the backend's 4:3 scissor clipped it under H6

#### Scenario: Unbalanced wrapper across frames
- **WHEN** a wrapper's entry pushes a site, the guest leaves it without its exit, two guest frames pass, and the stray exit then pops
- **THEN** the next push on that thread drops the stale entry, the pop does nothing, and no other thread's chain is touched

#### Scenario: A wrapper open across one frame boundary
- **WHEN** a wrapper's entry pushes a site and `xbox_mod_frame` runs once before the sprite add inside it
- **THEN** the add still resolves the element through that entry

#### Scenario: Stock aspect with the mod on
- **WHEN** the HUD mod is on (its default) and the aspect is 4:3
- **THEN** the active flag is clear, each hooked call returns after one branch, no byte changes, and `hud` is absent from `mods=`

#### Scenario: A parked world marker
- **WHEN** a `world` group with a `park` bound of ±360 sees a marker at x -400 at 16:9
- **THEN** the marker is moved past the wide frame's edge and does not show in the left pad

#### Scenario: Parked piece stays hidden
- **WHEN** a `left` element's sprite is parked at x -400 at 16:9
- **THEN** it is moved past the wide frame's left edge and nothing of it shows in the left pad

#### Scenario: The caller's vertices are restored
- **WHEN** the mod applies `XBOX_HUD_RESTORE` on a call that copies the vertices
- **THEN** the call sees the shifted vertices and, after it returns, the caller's buffer holds its original bytes

#### Scenario: A bad table is refused
- **WHEN** a mod registers a table with two sites at the same return address, or a site naming a group the table does not declare
- **THEN** `hud_table` returns an error with one log line and the mod fails

### Requirement: HUD canvas
A HUD table SHALL describe the game's canvas: its width and height in canvas units, its origin (`centre` or `top-left`), its y direction, the view it covers in the target in guest pixels (default the whole target), the target (the back buffer's guest size, or a declared size) and a source for its size (`fixed`, `memory` with typed guest addresses, or `target`). The layer SHALL convert canvas units to guest pixels by `view_w / w` from the view's origin, apply every rule in guest pixels of the target, and convert back before writing. The view SHALL only map units: the pad and each group's window SHALL come from the target's 4:3 columns, not from the view. A `memory` source SHALL be read in `xbox_mod_frame`, at the same point as the target's size, and published with it as one snapshot; a value that is not finite, not positive or above 4096 SHALL fall back to the declared values with one log line per change. No coordinate SHALL be assumed to be 640x480.

#### Scenario: BLiNX 2's canvas
- **WHEN** BLiNX 2's table declares a 640x480 centre-origin canvas covering its 640x480 target and the mod runs at 16:9
- **THEN** a canvas x of -320 is guest pixel 0, and a `left` element moves by -107 guest pixels, written as -107 canvas units

#### Scenario: A smaller view
- **WHEN** a table declares a top-left canvas whose view covers part of a 640x480 target, at 16:9
- **THEN** the window is the target's columns [0, 640] moved by the offset, not the view, the offset still comes from the target's pad of 107, and a `left` element keeps its gap to the view's edge as the game's margin

#### Scenario: A bad memory read
- **WHEN** a `memory` canvas reads a width of 0 or NaN in a guest frame
- **THEN** the layer uses the declared size and logs one `[hud.canvas] ... fallback` line

### Requirement: Stretch kind
A `stretch` group SHALL map every vertex x of its primitives, full width included, by `cx + (x - cx) × W/w` about the target's centre `cx`, with `W` the wide frame's width in guest pixels, so positions and widths scale together. It SHALL use the frame's full pad, ignoring `display.hud_aspect` and `display.hud_margin`, and SHALL apply no window or in-game clip; the wide frame clips it. A mapped primitive that covers the 4:3 columns but reaches less than 9 guest pixels past them SHALL have its outer x pushed out to 9 pixels past them, with its u kept, so no texel outside the sprite's own u range is sampled. While the active flag is set, the backends SHALL use a bounded variant of the per-triangle full-width test on the canvas's target: a triangle counts as full width only if it spans `[2, w - 2]` and lies within `[-8, w + 8]` guest pixels, so H5 never stretches a mapped primitive a second time, and a batch with any such triangle stays full width. At 4:3 the map SHALL be the identity. Zero-area primitives SHALL never be listed as `stretch`.

#### Scenario: Loading band slides in stretched
- **WHEN** BLiNX 2's loading band slides in from x -1280 to its rest position with the mod on at 16:9
- **THEN** it stays off the frame while parked, moves across the left pad while sliding, and at rest meets its partner at the wide frame's edges, with no jump and no second stretch

#### Scenario: Cinematic bars cover the pads
- **WHEN** a BLiNX 2 cutscene draws its top and bottom black bars with the mod on at 16:9, 16:10 or 21:9
- **THEN** the bars span the wide frame's full width with no gap at its edges, whether a `stretch` row maps them or H5 stretches them, never both, and a bar that overhangs the 4:3 columns by more than 8 guest pixels has a `stretch` row

#### Scenario: A mixed batch keeps H5
- **WHEN** one batch holds a fade triangle spanning 0..640 and a shifted piece at -107..-20, with the active flag set at 16:9
- **THEN** the batch still counts as full width and H5 stretches it

#### Scenario: A game fade keeps H5
- **WHEN** an unlisted full-screen fade spanning 0..640 is drawn with the active flag set at 16:9
- **THEN** it still counts as full width and H5 stretches it over the frame as with the mod off

### Requirement: HUD offset rule and keys
The offset SHALL derive from the target's Hor+ pad: `pad_hud = max(0, min(pad, pad_at(display.hud_aspect)) - display.hud_margin)`, with `pad_at(W:H) = roundf((h * W/H - w) / 2)`. `left` SHALL move by `-pad_hud`, `right` by `+pad_hud`, `centre` and `world` by 0, and `proportional` by `roundf(cx / (w/2) * pad_hud)` clamped to `±pad_hud`, with `cx` the group's reference x from the target's centre: its declared reference, else the first primitive of its first member added in the current guest frame. Every offset SHALL be a whole guest pixel.

`display.hud_aspect` (env `RECOMP_DISPLAY_HUD_ASPECT`, default `display`, meaning the configured `display.aspect`) SHALL accept `display` or a `W:H` ratio; a ratio narrower than 4:3 SHALL be logged and read as 4:3. It SHALL be a file and env key only, with no menu item. `display.hud_margin` (env `RECOMP_DISPLAY_HUD_MARGIN`, default 0) SHALL accept 0 to 64 guest pixels; values outside SHALL be clamped with a log line. Both keys SHALL be read at start whether or not a HUD mod runs. A live "HUD margin" Display menu item SHALL appear only once a HUD mod has registered a table. Both keys SHALL be added to the `[ENHANCE]` aspect line while a HUD mod runs at a wide aspect.

#### Scenario: Offsets at the common ratios
- **WHEN** the mod runs on a 640x480 target with `display.hud_aspect=display` and no margin
- **THEN** `left` moves by -64 at 16:10, -107 at 16:9 and -240 at 21:9, and `right` by the same amounts to the right

#### Scenario: A 16:9 HUD on a 21:9 world
- **WHEN** `display.aspect=21:9` and `display.hud_aspect=16:9`
- **THEN** the world fills 240 guest pixels per side and the HUD's edge elements move by 107

#### Scenario: Margin
- **WHEN** `display.aspect=16:9` and `display.hud_margin=20`
- **THEN** edge elements move by 87

#### Scenario: A proportional group moves as one
- **WHEN** two members of one `proportional` group have x centres of 100 and 200 at 16:9, and the group declares no reference
- **THEN** both move by the offset computed from the first member drawn, and the group keeps its shape

#### Scenario: Stock aspect
- **WHEN** `display.aspect=4:3`, whatever the HUD keys say
- **THEN** every offset is 0 and the frame matches the mod-off frame

### Requirement: Clip lift for centred 2D
While the HUD service's active flag is set, `nv2a_aspect_box` SHALL, for a batch placed CENTRE, 2D, not a near layer (`nv2a_aspect_flat`) and not full width, on a padded 4:3 target whose guest size equals the canvas's target, push a guest clip edge at 0 or at w out to the target's edge, as it does for centred 3D. A narrower clip the game set SHALL keep its edges. Square targets, other sizes, unpadded shapes, near layers, STRETCH, COVER and full-width batches SHALL keep their H5 box. Metal and D3D11 SHALL compute the lift and the already-wide rule with one shared helper from the same inputs (2D, near layer, full width per triangle, the batch's x range, the target's size), called before placement, and take the box from `nv2a_aspect_box`. The lift SHALL be off while the flag is clear: under `mods=none`, with the mod off or dormant, at 4:3, and before any table is registered. The batch's x range SHALL serve only the lift decision. Under `RECOMP_TRACE=aspect`, the `[aspect.program]` lines SHALL show the lift and any batch the already-wide rule took out of full width.

#### Scenario: Lift on
- **WHEN** the BLiNX 2 mod is on at 16:9 and the HUD panel batch is drawn
- **THEN** its scissor spans the whole padded host frame (854N wide at render scale N), and the panel shows 107 guest pixels further left than at H6

#### Scenario: Lift off
- **WHEN** the mod is off at 16:9
- **THEN** every centred 2D batch is scissored to the 4:3 columns exactly as under H6

#### Scenario: Near layers stay clipped
- **WHEN** a HUD mod is on at 16:9 and a batch at a near layer's w (rhw 10) is drawn
- **THEN** it is scissored to the 4:3 columns as under H6

#### Scenario: Movie keeps its pillarbox
- **WHEN** a movie plays with the mod on and `display.movie=black`
- **THEN** the full-width movie batch keeps its H5 box and the pads stay black

### Requirement: HUD mapping framework
The toolkit SHALL offer a DEBUG key `hud_capture=<dir>`, with a guest-frame window `hud_capture_at=<from>:<count>`, that sets the active flag for recording only and records without changing any vertex: one JSONL line per sprite (guest frame, queue, call chain outermost first, resolved site and group if listed, vertex count, bounding box in canvas units, primitive count, texture hash when given) and one per frame (guest frame, flip, canvas), plus one picture of each captured guest frame taken at the flip that presents it. At level 0 it SHALL record at the D3D draw entries the table lists, with return addresses found on the stack inside the code sections. With `hud_capture_table=<path>` the capture SHALL load that table itself and hook its wrappers and draws, so a title is located without a mod; a table registered by a mod SHALL win.

The CLI SHALL offer a game-agnostic `hud-map` command group, separate from the player's `enhance hud`, with an optional `[hud]` table in the game manifest's schema:
- `capture` runs a game's scenario at stock aspect with the capture keys and the game's table;
- `propose` groups captured sprites into elements by call site and chain and suggests a kind by position (left third `left`, right third `right`, middle third `centre`, spanning the canvas `stretch`, beyond the edges and moving independently `world`, slide-ins by their on-canvas frames, zero-area primitives never), writing every row marked `proposed`;
- `review` writes a static HTML contact sheet of the captured frames with boxes coloured by kind, at 4:3 and as a wide-ratio preview;
- `emit` validates a proposal against the analysis and writes the game's table, refusing rows still marked `proposed` unless told to accept them; `emit --check` validates the existing table and writes nothing;
- `check` runs the per-ratio scenarios with the mod on and off and writes a comparison sheet.

The CLI SHALL hold no game constants: `game.toml` SHALL only name the table path and the scenarios. Captures, sheets and frames SHALL stay outside the repos' tracked files and SHALL never be published.

#### Scenario: Capture changes nothing
- **WHEN** a scenario runs with `hud_capture` set and the HUD mod's switch on
- **THEN** no vertex is shifted, nothing is clipped, and the capture lists each sprite with its chain and box

#### Scenario: A proposal needs review
- **WHEN** `hud-map emit` is given a proposal whose rows are still marked `proposed`
- **THEN** it refuses them and writes nothing unless `--accept-proposed` is passed

#### Scenario: A row inside a wrapper is rejected
- **WHEN** `hud-map emit --check` reads a table with a site whose return address lies inside a listed wrapper's body
- **THEN** it reports that row and exits 1

### Requirement: HUD anchors leave stock unchanged
While the HUD service's active flag is clear (with `mods=none`, with no HUD mod, with the mod switched off, or at 4:3 with the mod on by default) the frames SHALL match the build without the HUD service: no vertex is changed, the lift is off and the already-wide rule is off, and `hud` SHALL be absent from the `mods=` token. The goldens SHALL run with `mods=none` at stock aspect, resolution and frame rate, on Metal and on D3D11, and SHALL pass unchanged on a build that has the HUD hook slots. A game without goldens (BLiNX 1) SHALL show the same by an A/B frame comparison: the default config at 4:3 against the build without the HUD slots, equal frames on Metal and on D3D11.

#### Scenario: Goldens with the hook slots
- **WHEN** the BLiNX 2 build with the five HUD hook slots runs the golden suite with `mods=none`
- **THEN** every golden passes on Metal and on D3D11 with the stock references

#### Scenario: BLiNX 1 stock by A/B
- **WHEN** BLiNX 1's build with the HUD slots and the mod on by default runs its scripted scenarios at 4:3
- **THEN** its frame dumps equal those of the build without the slots, on Metal and on D3D11

### Requirement: BLiNX 2 HUD mod
BLiNX 2 SHALL ship a `hud` descriptor mod, with an enable setting that defaults on (an exception to default-off, approved by the user on 2026-10-30), that:
- hooks the sprite add `sub_00042190`, the helpers `sub_000177F0`, `sub_000178C0` and `sub_00047A00`, and the font routine `sub_00048600` through `game.toml` `[mods] hook_functions`;
- embeds `config/hud.toml` at build time and registers it: a 640x480 centre-origin canvas (or the memory source the first check finds), 16-byte vertices with x at 0 and u at 8, quads, the helpers and the font routine as wrappers, and groups built with the mapping framework and checked against the tracker item's element table: the top-left panel and the radar `left`; the TS label and the item counter `right`; the time-control slots, the yellow arc, the round banner and the dialogue (box, face, text, A button, label) `centre`; the world markers `world`, with a `park` bound if the capture shows parked markers; the loading bands `stretch`; the cinematic top and bottom bars `stretch` unless they stay within `[-8, w + 8]`, where H5 covers them; and the cutscene dim and backdrops `stretch` only where the review keeps them;
- leaves the full-width zero-height quads of `sub_00216D70` unlisted;
- registers no state gate: menus, the pause panel and movies are not in the table, and the stage HUD stays anchored while paused.

A `scripts/test_*` case SHALL check that every row's return address follows a call to a hooked function or a listed wrapper in the analysis xrefs, that no return address lies inside a listed wrapper's body (such a site is reached from menus too), and that no row is duplicated.

The mod's switch SHALL be its descriptor's `XBOX_SET_ENABLE` setting (`mods."hud.enabled"`, default true in the descriptor and in `config.default.toml`). The mod SHALL act only through the active flag. A dormant init (switch off, menu on) SHALL register the table but apply nothing. The mod SHALL be listed in `mods=` only while the flag is set.

#### Scenario: Stage HUD at the edges
- **WHEN** `@stage1` runs on Metal or D3D11 with the mod on at 16:9
- **THEN** the panel, lives, Time and radar sit 107 guest pixels further left, the item counter 107 further right, the time-control slots stay centred, the HUD pack's art stays sharp, and no parked piece shows in the pads

#### Scenario: World markers in the pads
- **WHEN** a world marker's projected position lies past the 4:3 edge with the mod on at 16:9
- **THEN** it shows in the pad at that position, unshifted

#### Scenario: Paused HUD stays anchored
- **WHEN** the pause menu opens during a stage with the mod on at 16:9
- **THEN** the stage HUD behind it stays at its anchors and plays its animations as at stock, and the pause panel matches the mod-off frame

#### Scenario: Menus and dialogue keep their layout
- **WHEN** a menu or a dialogue opens with the mod on at 16:9
- **THEN** the menu matches the mod-off frame, and the dialogue's box, face, text and button stay centred together, clipped to the 4:3 columns

#### Scenario: Any wide aspect anchors the HUD
- **WHEN** a player sets `display.aspect=16:9` in the menu, the file or the wizard, with the default config
- **THEN** the HUD sits at the wide frame's edges

#### Scenario: The Mods page turns it off
- **WHEN** a player at 16:9 switches the `hud` mod off on the Mods page
- **THEN** the HUD returns to the 4:3 centre as under H6 from the next frame, and `hud` leaves the `mods=` token

### Requirement: BLiNX 1 HUD mod
BLiNX 1 SHALL ship a `hud` descriptor mod of the same shape as BLiNX 2's (enable setting default on, acting only through the active flag, an embedded `config/hud.toml`, hooks through its `game.toml`, a row test), once its Hor+ is finished at wide ratios, including the seam at the old 4:3 edges. Its sprite path and canvas SHALL be located with the mapping framework's level-0 capture, and no BLiNX 2 address SHALL be reused. If its HUD is drawn from vertex buffers filled ahead of the draw, the mod SHALL not ship and the finding SHALL be recorded for the mark route.

#### Scenario: BLiNX 1 HUD at the edges
- **WHEN** a BLiNX 1 stage runs with the mod on at 16:9
- **THEN** its edge elements sit at the wide frame's edges, its centre elements stay centred, no parked piece shows in the pads, and the mod-off frames match H6

### Requirement: Hor+ in the wizard anchors the HUD
A game's build wizard that offers Hor+ SHALL offer it as one aspect option (`display.aspect`, default 4:3), with no separate HUD item and no other key: the HUD mod is on by default, so a wide aspect anchors the HUD wherever it is set. The CLI's wizard manifest SHALL need no new field for it.

#### Scenario: Wide aspect in the wizard
- **WHEN** a player picks 16:9 in a game's wizard
- **THEN** the seed config holds `display.aspect = "16:9"` and no HUD key, and the game starts with the HUD at the edges

#### Scenario: Stock in the wizard
- **WHEN** a player keeps 4:3
- **THEN** the seed config does not set the aspect, and the game runs as stock

#### Scenario: Aspect changed later
- **WHEN** a player who installed at 4:3 later sets `display.aspect=16:9` in the menu
- **THEN** the HUD moves to the edges, as it would have from the wizard
