## Why

The enhancements layer's user decisions (2026-10-04) ask for a generic Hor+ widescreen mode. It keeps the game's own vertical field of view and adds picture at the sides, keeps the HUD where the game put it, and leaves the goldens at stock. Today `display.aspect` is read and refused, and a 16:9 window shows the 4:3 frame pillarboxed.

The spike (`analysis/enhancements/hor-plus.md`, 2026-10-07) found that one shared function maps every vertex the game draws from surface pixels to NDC (`nv2a_vp_consts_fill`). So widening the target and shifting that mapping gives Hor+ with no knowledge of the game's projection. The catch it found is that BLiNX 2 draws every batch, the HUD included, with vertex programs. So "is this 2D?" has to come from running the program, not from the pass-through path. The tracker item (2026-10-17) adds the user's decisions for v1:

- the HUD in its centred 4:3 layout (to the tracker item also had an edges mode that moved pieces to the nearest edge; the tracker item took it out, since the game's triangles carry no element identity and elements split; design H6);
- parked HUD pieces that never show in the pads;
- movies and stills pillarboxed by default;
- a separate movie side-fill key.

## What Changes

- **`display.aspect`** (env `RECOMP_DISPLAY_ASPECT`, default `4:3` = stock). It accepts any `W:H` wider than 4:3 (`16:9`, `16:10`, `21:9`). The Metal and D3D11 backends pad every 4:3-shaped colour and depth target by `nv2a_host_pad` guest pixels a side (107 for 640x480 at 16:9), and square targets by the frame's share, and draw with the pixel-to-NDC mapping shifted so that the title's columns sit centred. The game's own perspective then fills the pads. The flip presents the whole padded target; the write-back keeps the 640x480 centre.
- **The 2D classifier.** `nv2a_aspect_scan` runs a sample of each batch's vertices through the CPU interpreter (`nv2a_vsh_run`); every vertex sharing one `oPos.w` that is an exact whole number from 1 to 1024 means 2D (a screen layer: `oPos.xy` are pixels whatever `w` is; BLiNX 2 draws its stage status panel's frame at a fixed view depth of 2 or 3 and its title movie at 100). A per-program gate keeps the cost down. Full width is decided per triangle (`nv2a_aspect_full_tris`), so the four corner triangles in one batch are not stretched.
- **Placement.** One rule table, `nv2a_aspect_place`, gives each batch a placement:
  - 3D is centred.
  - 2D that is not full width is centred and scissored to the 4:3 frame, so parked pieces never show.
  - A full-width 2D pass over render targets or nothing is stretched (fades, post passes).
  - A full-width 2D pass over a guest texture is a movie or still and follows `display.movie`.
- **The HUD** keeps its 4:3 layout, centred, with no option to move or scale it (design H6).
- **`display.movie = "black" | "fit" | "fill"`** (env `RECOMP_DISPLAY_MOVIE`, default `black`):
  - `black` pillarboxes.
  - `fit` stretches the 4:3 picture to the width.
  - `fill` scales it to cover the width and crops the top and bottom.
  - `frame` and `blur` are assessed in the design (sizes, costs) and left for later.
- **CPU rasteriser**: ignores the keys and logs one line. This is listed in TASKS.md.
- **Goldens**: unchanged and stock-only. `RECOMP_CONFIG=none` keeps a shipped TOML out, and the harness already fails a run whose log shows another `display.aspect`.
- **Not in this change:**
  - The projection fix for the frustum pop-in at the edges. The game culls against its 4:3 frustum. This is the documented limit, and the fix is a follow-up after free-camera M0 (TASKS.md).
  - The per-program `[aspect.program]` overrides of the WIP spec, dropped: BLiNX 2's HUD is one program.
  - `display.aspect = auto`.

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `enhancements`: new requirements "Hor+ display aspect", "Hor+ batch placement", "HUD keeps its 4:3 layout", "Movie side fill" and "Hor+ cost". "Enhancements default to stock" and "Internal resolution scale" are amended to name the new keys and the padded host size.

## Impact

- **Toolkit** (branch `feat/hor-plus` off `posix-host/portability` 878d473a):
  - `src/kernel/nv2a_aspect.c` (new: the scan, the gate, full_tris, map, box);
  - `src/kernel/nv2a_backend_common.{c,h}` (opts, `nv2a_host_pad`, the pad term in `nv2a_vp_consts_fill`, the placement table);
  - `src/enhance/enhance.{c,h}` (the two keys);
  - `src/platform/recomp_env.h` (env rows, the `aspect` trace, `metal_host_dump`);
  - `src/d3d/nv2a_pb_metal.m` and `nv2a_pb_d3d11.c`;
  - the MSL and HLSL combiners (the `tex_scale.w` x offset);
  - `tests/render_scale`;
  - `docs/runtime/config.md`.
- **cat** (branch `feat/hor-plus` off `main` 4317f84): `docs/env.md` (two rows), `packaging/config.default.toml` (`[display]`), `TASKS.md` (follow-ups), this change.
- **Backends**: Metal and D3D11 (D3D11 cross-built with llvm-mingw and checked under Proton on the Deck); the CPU backend ignores it with a log line.
- **Goldens**: none change; stock is the identity (`pad = 0` leaves every constant, region and size as on main).
