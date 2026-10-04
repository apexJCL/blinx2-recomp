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
