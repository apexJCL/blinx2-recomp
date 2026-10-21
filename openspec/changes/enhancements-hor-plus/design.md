## Context

Sources: the enhancements layer's user decisions (2026-10-04, D3 "generic hor+"), the spike `analysis/enhancements/hor-plus.md` (2026-10-07) and the decisions (2026-10-17). Code read and changed at toolkit `posix-host/portability` 878d473a and cat `main` 4317f84.

What exists:
- Both GPU backends map surface pixels to NDC with `nv2a_vp_consts_fill`: `2/w, -2/h, -1, 1`.
  - Every BLiNX 2 batch is a vertex program ending in the XDK's viewport epilogue (`c[58]`, `c[59]` = `320, -240`, `320.53, 240.53`), so `oPos` is in surface pixels.
  - The host clips at NDC ±1, the target's edge.
- The targets are 640x480 (the frame), 320x240 (the post downsample), and 256x256 and 512x512 (shadow, environment, glow).
- `render.scale` already separates the guest size from the host size (`RenderTarget{w, h, hw, hh, n}`), with the write-back at guest size. Hor+ reuses that seam.
- `blinx2 golden check` (the CLI's `golden.py`) fails a run whose log shows `display.aspect` other than `4:3`.

What the runs showed (Metal, `RECOMP_TRACE=aspect`, `runs/hor-plus/trace3`, `@stage1` and `@story` at 16:9; each `[aspect.program]` line is one program, texture and placement):

| run | lines | 5474DB2A | B2913952 | C8AF571F | 489640CD |
|---|---|---|---|---|---|
| stage1 centred | 52 | 48 | 1 | 2 | 1 |
| stage1 edges | 96 | 92 | 1 | 2 | 1 |
| story centred | 71 | 66 | 2 | 2 | 1 |
| story edges | 107 | 102 | 2 | 2 | 1 |

- **5474DB2A** is the whole HUD, every menu, the text and the corner triangles.
- **B2913952** is the movie quad (a 1024x512 guest texture, full width).
- **C8AF571F** and **489640CD** are the post passes (full width, over render targets).

So a per-program override can't tell a HUD piece from a menu panel; the WIP spec's `[aspect.program]` and `[aspect.texture]` tables are dropped. Placement is decided per batch from what it draws instead (H3 to H5). The edges rows are from the per-piece HUD mode of the tracker item to the tracker item, which is gone (H6).

## Goals / Non-Goals

**Goals**
- A `display.aspect` wider than 4:3 gives Hor+ on Metal and D3D11 with no per-game tables:
  - more horizontal view at the same vertical view and pixel scale;
  - screen passes that cover the whole frame;
  - movies at their own aspect unless `display.movie` says otherwise.
- The HUD, menus and text keep their 4:3 layout, centred, with no option to move or scale them (H6).
- Stock is the identity. At `4:3` every size, region and constant is what it is on main, so the goldens hold by construction.
- It works with `render.scale`, the present filters and the host-size dumps.

**Non-Goals**
- **Frustum pop-in at the edges.** The title culls against its 4:3 frustum, so objects past the old edge appear late. This is the documented limit. The fix (widen the projection the culling uses) needs the game's projection build. It is a follow-up after free-camera M0, which locates the camera and projection code (TASKS.md). Measured at 21:9 on stage1: the guest's batches per flip are within 2% of stock (runs `uw/`, `golden-stock2/`), so it draws only what its 4:3 frustum keeps. The pop grows with the ratio: small at 16:10, plain at 21:9.
- **The window.** A window opens at the padded frame's shape (`nv2a_host_window_w`, 854x480 at 16:9). Before this, D3D11's windowed copy at scale 1 put the left 640 columns of the 854-wide target on screen and cut off the right pad (Deck, run 20261017-194644). A window wider than the screen is clamped by the OS, and the frame is letterboxed in it.
- `display.aspect = auto` from the window: the window can change, but the target shape can't without re-creating every target.
- The CPU rasteriser, which draws into guest memory at the guest pitch; it logs that it ignores the keys.
- Per-program overrides (see the table above).

## Decisions

### H1. Padding: one helper, guest units, 4:3 and square targets
`nv2a_host_pad(w, h)` is 0 unless the aspect is set and the target is 4:3 within 1% (`3w` against `4h`) or square. A 4:3 target gets `round((h * aw/ah - w) / 2)`: 107 for 640x480 at 16:9, 53 for 320x240, 240 for 640x480 at 21:9. A square target gets the same share of its width plus an eighth of its width a side of overscan, `round((w * 3aw / 4ah - w) / 2 + w / 8)`: 149 for 512 and 75 for 256 at 16:9, 115 and 58 at 16:10 (85, 43, 51 and 26 before).

- The host size is `hw = (w + 2 pad) * n` and `hh = h * n`, where `n` is the render scale (lowered by `nv2a_host_size` past the API limit).
- `RenderTarget` and `DepthTarget` carry `pad` and `n`.

A frame that isn't 4:3 within 1% gets no pad, so Hor+ does nothing there. Burnout 3's 640x464 clip is one (3w/4h = 1.034). Its square targets are still padded when an aspect is set, and their samplers read the stock texels through `rt_offset` on either backend, whether or not the target being drawn is padded (the review fix, toolkit 992e6ad1). A Burnout 3 race at 16:9 on Metal shows no squeezed or seamed picture from them; D3D11 is untested on Burnout 3.

Why 4:3 targets: the frame and its half-size post buffer are the picture.

Why square targets too (toolkit fix/hor-plus-scale db83e597): BLiNX 2 draws its screen-space reflections (the hub's stair pit and floor, stage 1-1's sea and pond) as the mirrored 4:3 view into a 512 or 256 square, then samples it at the fragment's screen position. Left unpadded, the pads read u outside [0, 1], which clamps to the edge column: a seam at the old 4:3 edge on both backends and at any scale, the hub's stair tearing and edge smear and the 1-1 water tint that stopped at x = 107 of 1280. Padded, the mirrored pass reaches the pads through the same centred mapping as the frame, and a batch sampling the square gets the usual `rt_offset`, so texel reads in [0, 1] are unchanged; full-width passes over the squares now stretch (`flat_rt` is not set for a padded source). A 16:9 `RECOMP_TRACE=aspect` run over the hub and 1-1 found no such pass: no 2D batch drew into or sampled a 256 or 512 square; the only stretched passes sampling a render target were the 320x240 and 640x480 glow passes (C8AF571F, 489640CD), with no seam at x = 107 or 747. Squares are never movies or HUDs: both backends place them with `display.movie = black`. Stock (no aspect) and 4:3 keep pad 0.

Why the square overscan: the water perturbs its reflection read with BUMPENVMAP. On 1-1 the matrices (`RECOMP_TRACE=bump`, Metal 16:10 stage1) move u by up to 0.106 of the square's width at full-scale du, dv (`du' = du m00 + dv m10`, the largest `|m00| + |m10|`). With the ratio's pad alone the frame's edge reads exactly the square's edge, so a bumped read past it clamps to the edge column: the end of the water effect showed at the viewport's edge. `w / 8` (0.125) covers the measured offset with about five texels of a 256 square to spare. It costs 21% more pixels on the mirrored pass at 16:10 (a 512 square is 742 wide instead of 614) and nothing elsewhere. Every read of a square goes through `nv2a_rt_guest_read` and every draw into it through its own pad, so the stock columns stay where they were on both backends. A stretched or covering batch keeps to the ratio's pad (`nv2a_host_pad_ratio`): drawn into a square it spans that pad only, and reading a square it takes the same columns (`nv2a_rt_stretch_read`), so a full-width 2D copy between the frame and a square lines up as before the overscan and the overscan columns stay out of it (review). Neither BLiNX 2 (the trace) nor Burnout 3 (a 16:9 race-gate run) draws a 2D batch into a square. The 4:3 targets keep exact pads: their full-width passes stretch, and the frame is what is shown.

Why guest units: the write-back, the dumps and the game's own read-backs want the guest frame unchanged. The pad is host-only state, like the scale.

### H2. Mapping: the pad enters `nv2a_vp_consts_fill`
`c[0] = 2/(w + 2 pad)` and `c[4] = -w/(w + 2 pad)`; y is unchanged.

- Guest x = 0 lands on host column `pad n`, and x = w on `(w + pad) n`.
- Geometry beyond 0..w used to be clipped at the target edge and is now drawn in the pads. That is the whole of Hor+ for 3D: the game's own projection and FOV, with the host no longer clipping at the 4:3 edge.
- The shaders are untouched; they already apply `vp_scale` and `vp_off`.

`nv2a_aspect_map(vc, w, h, pad, place)` adjusts the constants per placement:

| placement | mapping |
|---|---|
| CENTRE | as filled |
| STRETCH | stock `2/w, -1` over the padded viewport |
| COVER | x as STRETCH; y scaled by the same factor about the centre |

With pad 0, every placement is stock.

### H3. The 2D classifier: run the program, gated
Every batch is a program, so the output decides. `nv2a_aspect_scan` runs up to 33 evenly spaced vertices of a batch through `nv2a_vsh_run` with the batch's constants. A batch is 2D when every vertex shares one `oPos.w` and that w is an exact whole number from 1 to 1024 (`nv2a_aspect_layer_w`), and the scan returns its x range.

`oPos.xy` are surface pixels whatever w is: w only steers perspective-correct interpolation and the depth. Orthographic output has w 1. BLiNX 2 also draws its stage status panel's frame and its two lamps through the world projection at a fixed view depth, every vertex at w 2 or 3 (run dbg4: the frame at w 3, z 0.667 of the depth range; the lamps at w 2). Its title movie is drawn at w 100, which a bound of 16 left centred under `display.movie` (rev2). With a w == 1 test the panel's text moved to the left edge while its frame stayed centred. A world sprite also shares one w across its vertices, but its depth is not a whole number (dbg4: 5.646, 39.51, 259.141 and so on), so it stays 3D. A sprite whose depth is exactly a whole number is the rare miss; it is then scissored to the 4:3 columns for that frame.

Interpreting one vertex costs about as much as a draw, so a `struct nv2a_aspect_gate` per program keeps the cost down:
- `two_d = -1` until the first check.
- A program whose first 16 batches were all 3D is checked only every 256th batch after that. The same program with an orthographic matrix is then caught late, which is acceptable: the 3D programs never draw the HUD in any run.
- A program seen 2D once is checked on every batch.

`nv2a_aspect_due(gate)` tells a backend whether the next scan will run. D3D11 must gather the vertex inputs from its streams first, and skips that when the scan won't run; it then calls the scan with count 0 to advance the gate. The pass-through path (not seen in BLiNX 2, but present in other titles) uses attribute 0 directly and is always 2D.

### H4. Full width per triangle
A batch's bounds aren't enough. BLiNX 2 draws its four blue corner triangles as one batch whose bounds are the whole screen; stretching that batch widened them by a third (seen on the title screen in trace2). `nv2a_aspect_full_tris` instead asks whether one triangle spans `[2, w - 2]`. A fade, a post quad or a movie frame has such triangles; the corner set does not. The test runs on batches the backend draws as triangle lists, which covers the quads, since they are expanded to lists; any other topology falls back to the batch bounds.

### H5. Placement table and scissor
`nv2a_aspect_place(two_d, full_w, guest_tex, movie_mode)`:

| batch | placement | why |
|---|---|---|
| 3D | CENTRE | the world, widened by H2 |
| 2D, not full width | CENTRE | HUD, text, menus (H6) |
| 2D, full width, padded render targets or no texture | STRETCH | fades and post passes: their source is padded too, or they are flat |
| 2D, full width, an unpadded render target (a 512x256 buffer: neither 4:3 nor square) | CENTRE | stretching would widen its 4:3 picture (`flat_rt`, the merge review) |
| 2D, full width, guest texture | `display.movie` | a movie or still keeps its shape by default |

`guest_tex` means that a stage enabled in the combiner samples a guest texture (not a render target) that is a picture: `nv2a_aspect_picture(tex_w, w)`, which is wider than a quarter of the frame.
- A smaller texture over the whole screen is magnified 4x or more, so it is a flat colour or a gradient, and the batch is a fade.
- BLiNX 2 fades through a 16x16 white texture, and draws that quad on every frame of a stage. Without the test such a fade leaves the pads unfaded (trace4).
- Fades are therefore stretched like untextured ones.
- The movie frame (1024 wide) and the menu backdrops (256 and up) are pictures.

The scissor comes from `nv2a_aspect_box(box, w, h, pad, n, place, two_d)`, starting from the guest surface-clip box (`nv2a_draw_box`):
- **Centred 2D** keeps to the guest columns. A HUD piece the title parks off-screen (`x < 0`, slid out between menus) must not show in the pads (the user).
- **Centred 3D** pushes the box edges at 0 and w out to the target edges, so the world fills the pads.
- **STRETCH and COVER** scale the box with the mapping.

Sampling a padded render target: a stretched or covering batch reads the whole target, short of a square's overscan. Any other batch reads only its guest columns, through `tex_scale[k].x *= w/pw` and `tex_scale[k].w = pad/pw`, where `pw = w + 2 pad`. The MSL and HLSL combiners and D3D11's basic shader add `tex_scale.w` to u (key bit `rt_offset`), and the term is absent at stock.

### H6. The HUD keeps its 4:3 layout
There is no HUD option. Every 2D batch that is not full width (the HUD, menus, text, the dialogue box) is centred and scissored to the guest's 4:3 columns, so it looks as it does at stock, with the world in the pads beside it. The decision is the user's (2026-10-18): Hor+ widens the world and leaves the HUD alone. Moving or shrinking HUD pieces isn't worth it in the current state, for these reasons.

**The game sends triangles, not elements.** One vertex program (5474DB2A, Context) draws every HUD piece, menu and string, and the same font texture serves corner text and centred text. A batch is a run of triangles with no element identity: which triangles form the item counter, the face or the name tag isn't in the stream. Every rule has to guess the grouping from geometry.

**The per-piece guesses kept splitting elements.** The edges mode (then the tracker items) grouped touching triangles into pieces with a union-find, sided each piece by its x extent (the outer thirds moved to the new edges), let a centred piece inherit its neighbour's side from the previous frame, and kept a whole frame centred when it looked like a layout screen (a full-width picture, one piece over a third of the frame, or the pieces' clipped cover summing to the frame). After the tracker item the user's Deck run at 16:10 still showed:
- the item counter staying centred while the items beside it split to the edges;
- in dialogue, the face going left, the box staying centred, the button going right, and the name landing beside the face instead of in the box;
- Mission complete drawn split for its first frames, then centred.

Each of these is one screen's layout, and each fix would be another rule tuned on that screen (alone added the off-layer test, the cover sum and its hysteresis).

**The layout decision comes late in the frame.** A screen is only known as one once enough of its batches have been drawn (the cover sum grows as they arrive), so the frame's first batches are placed before the decision and the screen's first frame can show split. Fixing that needs the whole frame buffered before any 2D batch is drawn, which changes the backends' draw order.

**Maintenance and CPU cost.** The mode was about 700 lines across the shared helpers, both backends and the tests. It ran every vertex of every HUD batch through the CPU interpreter (not the 33-vertex sample), grouped up to 1024 triangles per batch, kept anchor sets across frames, and split a batch into one draw per run. All of it ran per frame on the CPU, which is the Deck's limit, for a result that was wrong on some screens of the one title it was tuned on.

**Shrinking was considered and dropped.** Two variants were weighed: an anchored shrink (pieces scaled about their own anchor at the edges) has the same grouping problem as moving them; a uniform shrink of the whole 2D layer about the centre needs no grouping but changes the stock picture on every screen for a small gain. The user dropped both (2026-10-18); neither is planned.

What stays is the batch-level placement of H5, which needs no grouping: a full-width 2D batch is a fade, a post pass or a movie, and is stretched or follows `display.movie`.

### H7. Movie side fill (`display.movie`)
The coordinator (2026-10-18) asked for an assessment of each side-fill mode. "Detection" means telling a movie or still from everything else.

| mode | what the pads show | detection | overlays | Metal / D3D11 work | cost | size | v1 |
|---|---|---|---|---|---|---|---|
| `black` | black | H5's rule (full width, guest texture), as B2913952 in every run | subtitles and HUD stay centred | none: the pads are cleared | 0 | S | default |
| `fit` | the picture stretched 4:3 to 16:9 (33% wider) | same | centred overlays drift off the picture's features | STRETCH placement, existing | 0 | S | yes |
| `fill` | the picture scaled up to the width, top and bottom cropped (12.5% each side at 16:9) | same | overlays near the top and bottom of the movie may be cropped; HUD overlays are not moved | COVER placement: the y term in `nv2a_aspect_map`, box scaled | 0 | S | yes |
| `frame` | a border image (an owner-made asset or a solid tint per title) | same | unchanged | a fixed quad per side at present or after the movie draw; an asset path key | about 2 draws | M | later |
| `blur` | the picture's edge columns, blurred and stretched into the pads (the TV-style fill) | same, but a still that lasts one frame must not flicker the blur on and off; needs a dwell of N frames | unchanged | a two-pass separable blur of a downsampled copy, per backend (MSL and HLSL), plus a pass per side | not measured: the blur samples a downsampled copy, a few hundred thousand texel reads per movie frame, and the Deck's APU is the host to measure on before it ships | L | later |

The readings of `fit` and `fill` are confirmed in the open questions. A still drawn full width over a guest texture follows the same key as a movie, since the rule can't tell them apart and the user asked for both to be pillarboxed.

### H8. Backends
- **Metal** (`nv2a_pb_metal.m`): the full list of changes (inventory in tasks 2.1).
- **D3D11** (`nv2a_pb_d3d11.c`) mirrors it from the same shared helpers:
  - the padded `RenderTarget` and `DepthTarget`, plus `rt_grow`;
  - partial clears offset by the pad;
  - the scan from the gathered inputs (`vtx_input`);
  - placement through `set_vp`;
  - `tex_scale.w` in the basic shader and `tex_uv`;
  - `read_pixel` and `px_probe` offsets;
  - the present blit of `(cw + 2 pad) n`;
  - the `hor+` flip line.
  D3D11 has no guest write-back of the padded frame, so it needs nothing there.
- **CPU**: one `[ENHANCE] display.aspect=... ignored` line, as for `render.scale`.

### H9. Keys and configuration
| key | env | default | values |
|---|---|---|---|
| `display.aspect` | `RECOMP_DISPLAY_ASPECT` | `4:3` | `W:H` wider than 4:3; anything else is logged and falls back to 4:3 |
| `display.movie` | `RECOMP_DISPLAY_MOVIE` | `black` | `black`, `fit`, `fill` |

- **Logging**: the summary line keeps `(display.aspect=W:H)`. With a wide aspect, a second line gives both keys.
- **Reading**: `display.movie` is read even at 4:3, so it is never reported unused. A key the layer doesn't know gets the generic `[ENHANCE] unused key <key>, <file>:<line>` warning and changes nothing.
- **Env rows**: in `recomp_env.h` (CONFIG tier) and in cat `docs/env.md`.
- **Packaged TOML**: `packaging/config.default.toml` `[display]` lists both, at their defaults.
- **Trace**: `RECOMP_TRACE=aspect` prints one `[aspect.program]` line per program, texture and placement, plus the target per flip.

### H10. Cost
The goldens are game-paced: flips and duration were the same at stock and at 16:9 (attract about 1140 flips in 24.8 s, stage1 2650 in 77.9 s, story 4340 in 81 s), so flips/s says nothing. Cost is measured with `RECOMP_TRACE=metal_prof,pacing`: GPU ms per flip, flip-interval p50 and p95, and process CPU. The limit is the workspace rule: a drop of 25% or more in the unpaced headroom, or a 1.5x rise in frame ms, on Metal or D3D11 blocks the merge. The figures are in tasks 3.3.

Where the cost comes from:
- the 854-wide targets (1.33x the pixels);
- the scan on 2D programs, which runs every batch for 5474DB2A (a 33-vertex sample).

## Risks / Trade-offs

- **Pop-in at the edges** (the documented limit; H1 Non-Goals).
- **A screen layer is a guess from w.** A batch whose vertices share one exact whole w from 1 to 1024 is 2D. A world sprite whose depth is exactly a whole number is drawn as HUD for that frame, scissored to the 4:3 columns. Another title that puts its HUD at a fractional depth needs this rule widened.
- **A 3D program used once orthographically** is caught late, up to 256 batches. That is harmless for BLiNX 2; another title may need the gate tuned.
- **`fill` crops** movie subtitles drawn into the movie picture itself (not seen in BLiNX 2's movies).
- **`black` pads rely on the game's clear.** Nothing draws black into the pads beside a movie. They are black because the title clears the whole target, and a clear covers the pads. A title that skips the clear under a full-screen movie would leave the last frame's pixels there.
- **Occlusion counts include the pads.** With the aspect on, a query counts the pad pixels the batch covers, so a wide frame's counts can exceed stock. BLiNX 2 only compares them with zero.
- **The w test can misfire.** A world batch whose depth lands exactly on a whole w is taken for a screen layer: about once in 10^4 batches or less (the screen-layer risk above).
- **The present crop assumes the extent is the target's width.** The flip shows `(cw + 2 pad) * n` columns from x = 0. An extent narrower than the target would lose part of the right pad and shift the frame. BLiNX 2's extent always equals the target's width; this is a TASKS follow-up.
- **The CPU backend's window is padded.** `nv2a_host_window_w` doesn't know the backend, so on the CPU rasteriser a wide aspect opens a wide window that pillarboxes the 4:3 frame (TASKS, under the CPU follow-up).

## Open Questions

- **`fit` and `fill`.** `fit` = the 4:3 picture stretched horizontally to the full width (distorted, nothing lost). `fill` = scaled uniformly until it covers the width, with the top and bottom cropped (no distortion; 12.5% lost at each of the top and bottom at 16:9). These are the readings implemented; the user confirms them at review.
- **Whether `frame` and `blur` are wanted at all**, and whether `blur` is worth L on the Deck. Not needed for v1.
