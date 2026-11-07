## Context

The tracker item. The data the mod reads is in `openspec/changes/collision-spike/design.md` §1–4: 0x48-byte triangles at 0xC21EA8 (count 0xCC9E2C), the octree at 0xCAE8A8 (0x38-byte nodes, count 0xCC9E30), the reference cells at 0xBACB98, all in the bake's space (RotX(π) of tree space, Y down), which is also the player's and the renderer's world space. The toolkit's mods could poke memory, hook functions and draw 2D overlay panels, but nothing in the game's 3D space.

## Decisions

### D1. The view and projection come from the mod, not from the GPU state

The draw API takes the matrices with the geometry (`draw3d_begin(m, view, proj)`), row-vector D3D convention (`clip = [x y z 1] · V · P`, clip z in [0, w], NDC y up).

- Why: the NV2A state has no clean "camera". BLiNX 2's vertex constants hold world × view per model (c[100..103]) with the projection folded into a transposed c[0x80] block, and a title with its own vertex programs has no fixed layout at all. Only the game knows which of its view builds is the camera the frame is drawn with (BLiNX 2 builds about 17 views a frame, the reflection targets included).
- BLiNX 2: the per-viewport build `sub_000292A0` (for the game camera, `ebx == [0x4B271C]`) and the stage view build `sub_0021B1F0` (both wrapped in `recomp_manual.c`) write the view the stage's models are drawn with (the free camera's D1). Right after each, `collision_mod_view()` copies V from 0xA72380 and P from 0xAC1870 (sub_00042AE0 writes it inside the build) and hands the frame over; the frame's last build wins. A substituted free camera is in V by then, so the overlay follows it.
  - Found in the verification: M23 never runs `sub_0021B1F0` and builds the game camera five times a frame (all five the same V), so a hook on `sub_0021B1F0` alone drew nothing there. Each build re-submits the same vertex arrays (selected and built once a frame); a few thousand vertices copied five times.
- Alternative (rejected): reconstruct V·P from the vertex constants at the draw. Title-specific anyway, and wrong for skinned or 2D batches.

### D2. Drawn at the flip, into the presented target, before present and the dumps

Both backends take the latest list at the flip, after `present_target` and before anything copies or reads the frame. The overlay is therefore in screenshots and frame dumps (wanted for the verification), and over the HUD (a debug view; a game-chosen draw point is a follow-up). Depth is the depth buffer of the last pass of that colour target:

- Metal: `rt->dt`, through `begin_pass(rt, 0, …)` (load colour and depth).
- D3D11: the `DepthTarget` of the same guest size with the latest `last_use` (no per-draw cost to track it). The draw path's state shadow is reset after (`s_sc_init = 0`), as the overlay does.

Both store normalised z (z / zmax), and BLiNX 2's viewport z scale is zmax with offset 0, so the stored depth is the projection's NDC z and the overlay's clip z compares with it directly (`LESS_EQUAL`).

### D3. The transform is done on the CPU, in the kernel library

`src/kernel/nv2a_dbg_draw.{c,h}` (ENHANCE builds only) transforms each vertex to clip space when the mod submits it and keeps five segments: opaque triangles (depth test and write), translucent triangles (test, no write), lines (test), x-ray triangles and x-ray lines (no test). Draw order: opaque, lines, translucent, x-ray triangles, x-ray lines. The shaders are a pass-through with one x scale, and the module is testable without a GPU (the ctest). It lives in the kernel because the backends link it and the layer links the kernel, never the other way round (as the batch filter and the HUD capture glue).

- Lines can be pulled toward the eye (`XBOX_DBG_PULL`, view space × (1 − 0.002), the Godot view's EDGE_PULL) so crease lines on faces win the depth test against them.
- Hor+ and render scale: the viewport is the whole host texture, and the shader scales clip x by w / (w + 2·pad), which puts the guest's 0..w in the middle of the padded target as the backends place the 3D draws.
- Clip-space vertices (no divide on the CPU), so the GPU clips triangles that cross the near plane.

### D4. One list per frame, a lock-free triple buffer

The guest thread fills the back list between `draw3d_begin` and `draw3d_end`; `end` publishes it by swapping it with the middle slot (an atomic exchange with a fresh bit). The flip takes the middle slot when fresh and keeps drawing the last one taken until a newer one arrives, so a guest frame that presents twice draws the overlay on both. An empty published list clears it. Before any publish the flip pays one atomic load, and without `XBOXRECOMP_ENHANCE` nothing at all: the goldens with the mod off are byte-unchanged.

- The list is published at the view build, inside the frame's render and before its flip, so the overlay is drawn with the frame it was built for. The player's sphere queries run after the view build, so the contact shown is the previous frame's (one frame behind the sphere's motion).
- One producer: the draw calls are for the guest thread only (in a mod callback). One mod owns the list from its `begin` to its `end`, and its `begin` sets the matrices: another mod's `begin` while that frame is open is refused (-1), and the frame it publishes replaces the last one whole, so two drawing mods show the last one to `end`, not both. A frame left open by a mod switched off before its `end` is dropped at the next mod's `begin`. Turning the mod whose frame is on screen off hides it (sequentially consistent stores and loads on both sides, so the hide is never lost).

### D5. Alpha blending, straight alpha

`src·a + dst·(1 − a)`. Opaque faces (alpha 255) write depth so they hide each other; translucent ones do not. The depth written lands in the game's own depth buffer after the frame's last pass; BLiNX 2 clears depth at the start of each frame, so nothing carries over. Write-back (Metal `wb_always`) puts the overlay into guest memory, with the mod on only.

### D6. The CPU rasteriser draws nothing

It keeps building; the gap is in `TASKS.md`.

### D7. The mod reads the octree, not every triangle

Each frame (mod on), `on_frame` walks the octree from node 0, rejecting nodes whose box (centre ± half-size) misses the sphere of radius R around player 0, and collects the triangles of the reference lists it reaches, once each (a per-triangle frame stamp). Every pointer is checked against its buffer and count, and the walk is bounded, so a stage load in progress draws nothing rather than reading garbage. The triangles' per-stage data (flatness band, sliver, crease and open edges) is computed once when the stage's triangle buffer changes (count and a hash of the records), not per frame.

### D8. The look matches the Godot view

From `xboxrecomp-cli/src/xboxrecomp_cli/extract/collision.py`:

- class colour, shaded `0.3 + 0.7·|n·L|` with L the extract's light (0.5, 1, 0.25) taken into the bake's space (y and z negated);
- flatness: degrees off flat or vertical, whichever is nearer, from `atan2(hypot(nx, nz), |ny|)` (BLiNX's up is ±Y, so the bake's half turn changes no band), bands at 0.1, 2 and 10 degrees: flat 0x9A9A9A, near 0xF0D020, tilted 0xF08020, slope 0xE02020; a sliver (two corners within 0.001 on every axis) 0x4A4A4A;
- crease edges where faces meet at more than 20 degrees (the two sides of a face are one plane, so a fold sharper than 160 degrees draws none), and open edges, corners welded within 0.001; the class colour × 0.3;
- translucent faces at alpha 0.35 by default, opaque on request.

Per class visibility: solid, enemy_wall, camera_floor, camera_pass, unused_blue, untested (0xFFFFFF, off by default), other.

### D9. The push face (stretch goal)

With "Contact" on, the mod hooks the sphere query (`sub_001636C0`) and the triangle test (`sub_00165630`), both hook slots already in `game.toml`, as the walls mod does: inside player 0's query (its seven call sites by return address) the last triangle the test took is the contact, and the post hook reads the contact normal (entry esp − 0x28) and push (esp + 0x10). The frame's last hit is drawn: the face filled bright, the push as a line from the centre. Player 0's sphere is drawn as three great circles at its query centre and radius. Without "Contact", no hook runs.

### D10. Settings, controls, env

`debug.collision`-style id `collision`: switch `mods."collision.enable"` (`RECOMP_COLLISION`, off), and live settings for faces, opaque, edges, flatness, x-ray, radius, contact and the seven classes. A rebindable `toggle` action (F4) hides and shows the drawing while the mod is on. Only the switch gets an env row (as the other game mods); `game.toml` `[golden] enhance_stock` gets `"mods.collision.enable" = "off"`, so a golden run with it on fails.
