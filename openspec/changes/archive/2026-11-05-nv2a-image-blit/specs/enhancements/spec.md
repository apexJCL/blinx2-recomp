## MODIFIED Requirements

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
- a 2D batch that would be centred and samples a frame copy is stretched over the whole target (`nv2a_aspect_place_copy`), full width or not. A frame copy is a padded render target a 2D-engine blit filled in this flip (`copy`, not drawn into since), sampled where the batch lies: over up to 32 of its vertices, `uv * size - xy` (size: the texture's for normalised coordinates, 1 for texel coordinates) varies by at most an eighth of the frame plus 2 pixels and is offset by at most a sixteenth of it on each axis (`nv2a_aspect_uv_tracks`). It is a lens effect over the frame, not HUD art; stretched, it reads the whole padded copy where it lies, so each such batch is `(w + 2 pad)/w` wider than at stock (1.33x at 16:9). A copy from an earlier flip, or a batch that maps a texture onto itself at another place or size, stays centred.

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

#### Scenario: Lens drops over a frame copy reach the wings
- **WHEN** Quantum Redshift draws its lens raindrops at 16:9, narrow 2D batches sampling the blit copy of the back buffer at 0x00A1C000
- **THEN** `RECOMP_TRACE=aspect` reports vs C8AF571F reading the copy as `tracks, stretched`, they are placed `stretch`, cover the wings as well as the 4:3 centre, and each refracts the part of the wide frame it lies over, on Metal and on D3D11

#### Scenario: A copy from an earlier flip is not a lens
- **WHEN** a 2D batch samples a padded blit copy that no blit refilled in this flip
- **THEN** it is placed as any other 2D batch (centred unless full width)

### Requirement: HUD keeps its 4:3 layout
With a wide aspect, every 2D batch that is not full width (the HUD, menus, text) and samples no frame copy (Hor+ batch placement) SHALL be drawn centred on its 4:3 columns, unscaled and scissored to them, as at stock. There SHALL be no option to move or scale the HUD: the game draws triangles with no element identity, so no rule can keep a HUD element whole (design H6). A config key the layer doesn't read, `display.hud` included, SHALL get the generic `[ENHANCE] unused key <key>, <file>:<line>` warning and SHALL change nothing; it SHALL NOT fail the load.

#### Scenario: Stage HUD on its 4:3 columns
- **WHEN** `@stage1` runs at 16:10
- **THEN** the status panel, the radar, the item counter and the dialogue box are where they are at 4:3, offset by `pad * N`, each the same size, with the world drawn in the pads beside them

#### Scenario: An unread key
- **WHEN** a `config.toml` sets `display.aspect = "16:10"`, `display.movie = "fit"` and `display.hud = "edges"`
- **THEN** the load succeeds, the log has one `[ENHANCE] unused key display.hud, <file>:<line>` line, and the options are those of the same file without the `hud` line
