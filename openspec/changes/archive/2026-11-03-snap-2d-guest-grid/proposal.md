## Why

Above `render.scale` 1, BLiNX 2's loading-screen tiles and menu bars show thin light lines, one host pixel wide, between tiles. The tiles are swizzled DXT1 screen-space quads, sampled bilinear with WRAP. A tile's edge host pixels sample 1/(2N) of a guest texel from the edge, and the wrap pulls in part of the opposite edge's texel, which is often transparent. The existing UV snap covered only linear-format unity blits (movie frames), so these stages were never snapped.

Snapping every 2D texture to the guest grid removes the seams, but it trades host-rate bilinear smoothing for 1x-looking art in N x N blocks. The user put that trade behind its own setting, default off.

## What Changes

- **`render.snap_2d`** (env `RECOMP_RENDER_SNAP_2D`, `opts_at` `snap_2d`, default `false`). It is live from the menu: Render, "2D on guest grid".
- **When it is on above scale 1**, a bilinear texture on a 2D batch samples at its guest pixel's 1x point. The texture may be any format, swizzled and compressed included.
  - A batch is 2D when it is pre-transformed, or when it is a program batch whose scanned vertices share one whole `oPos.w` and one `oPos.z`.
  - It must also be on an unpadded target, or centred on a padded one.
  - The mapping must be axis-aligned, with u along x and v along y.
- **Explicit 1x gradients.** A snapped stage samples with gradients equal to the 1x ones (`SampleGrad` on D3D11, `gradient2d` on Metal), so it keeps its 1x mip level and filter.
- **Left alone:** 3D batches, render-target stages, STRETCH and COVER placements, and mappings turned 90 degrees.
- **Draw merging** is off while the snap is on, as under Hor+, since the snap classes each batch from its own vertices.
- **Off, the run is stock.**
  - The basic shaders are the base texts, locked by checksum.
  - The combiner key and text are the base ones.
  - The 2D scan runs only where Hor+ runs it, and no snap constants are written.
  - The shaders with the snap are separate variants, built the first time the setting draws.
- **The rect unity-blit snap** (movie frames, `tex_scale.z > 0`) is unchanged and does not depend on the setting.

## Capabilities

### Modified Capabilities
- `enhancements`: new requirement "2D textures on the guest grid".

## Impact

- **Toolkit** (`xboxrecomp`, branch `fix/snap-uv-swizzled` off `posix-host/portability`):
  - `src/kernel/nv2a_backend_common.{h,c}` and `nv2a_aspect.c`: `nv2a_snap_2d_on`, `nv2a_ps_consts_snap`, `nv2a_snap_flat2d`, and the scan's `vary_z`;
  - `src/kernel/nv2a_pb_exec.c`: `merge_on` turns off under the snap;
  - `src/d3d/d3d8_hlsl.h` and `d3d8_msl.h`: the `SNAP_2D` helpers;
  - `d3d8_combiners_{hlsl,msl}.c`: emit the 2D sampling only for the `snap_2d` state bit;
  - `nv2a_basic_hlsl.h` and `nv2a_basic_msl.h`: the basic shaders as text, stock and snap;
  - `nv2a_pb_d3d11.c` and `nv2a_pb_metal.m`: the key bit, the lazy variants and the per-draw decision;
  - the enhancements layer and menu: the `render.snap_2d` key and row;
  - `docs/runtime/config.md`.
- **Tests:** `render_scale`, `d3d8_hlsl_split`, `d3d8_msl_split`, `basic_shaders` (new), `pb_draw_merge`, `opts_at`, `host_opts_live`, `enhance_cfg`, `enhance_menu` and `d3dcompile_smoke` (Windows).
- **cat:** the `docs/env.md` row.
- **Goldens:** stock only. They do not set the key.
- **Performance:** off, none. On, one gradient sample per snapped stage, and back-to-back batches drawn one by one.
