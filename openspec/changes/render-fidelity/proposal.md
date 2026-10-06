## Why

Placeholder, for after `render-gpu-backend`. Getting a frame out is not the same as getting the right frame. Known BLiNX-specific gaps:

- **Signed texture filtering for the ocean** in the first stage (`NV_PGRAPH_TEXFILTER_SIGNED`). In xemu, the water was black (#1405, fixed by about #2129) and full fidelity still needs #587. The toolkit's `d3d8_combiners.c` has signed and unsigned input mappings but no signed *filtering*. This is probably a BLiNX-specific contribution upstream.
- Register-combiner parity with xemu for the first stage.
- Depth and stencil.
- Quick-time-event and text-box fps dips, which xemu reports for this title.

## What Changes

- Each item gets a reference frame (an xemu capture of the same scene) and a requirement, written when the work starts.

## Capabilities

### New Capabilities
- `render-fidelity`: per-feature rendering parity with reference frames (requirements to be written when the work starts).

## Status

Placeholder (proposal only). `.openspec.yaml` sets `skip_specs: true` so it validates. Remove that, and add design, spec deltas and tasks, when the work starts.

## Current gaps (2026-10-06)

Still a placeholder: no work has started under this change. Since it was written, the D3D11 and Metal backends have landed and the golden frames pass, so the bucket is now what remains after them. From TASKS.md:

- `BUMPENVMAP` (texture mode 6) is unimplemented on every path and samples as plain 2D: the Boss 3 ripple and the stage-1 ocean (with the signed-filter item above).
- The Boss 1 sky wedges, the Shadow Claw ellipse and the Silver Claw horns draw the same on the CPU path; they need an xemu reference before anyone calls them bugs.
- Volume-texture mips on the GPU paths use 2D-chain offsets.
- CLIPPLANE on the GPU paths has its own change, `render-clipplane-gpu`.
