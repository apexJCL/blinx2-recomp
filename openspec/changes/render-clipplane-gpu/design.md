## Context

- CPU reference: `stage_clip_kills()` in `nv2a_pb_exec.c`. Bit `n * 4 + j` of `clip_plane_mode` set means the pixel dies at `tc[j] >= 0`, clear means it dies at `tc[j] < 0`, where `tc` is the stage's perspective-correct interpolated coordinate. xemu emits the same compares on `pT<n>` (psh.c, PS_TEXTUREMODES_CLIPPLANE).
- Since 35e17dd, the Metal and D3D11 combiner keys carry mode 5 for a CLIPPLANE stage, and the emitters bind no texture for it and leave its register 0.

## Decisions

1. **One packed constant, not a shader variant per mode word.** `clip_mode[n]` is a nibble per stage in a `uint4`, so a title that flips plane signs per batch does not compile a shader each time. The compare is four `select`s and a discard, and only stages whose key says CLIPPLANE emit it, so other shaders are unchanged.
2. **Append, don't reuse.** Packing the nibble into `tex_mode`'s high bits would avoid the layout change. But `tex_mode` is compared with `==` in both emitters and in `fs_basic`, and a packed field is an easy future bug. The cbuffer grows by 16 bytes. Both backends upload the struct as a whole, and the `_Static_assert`s pin it.
3. **Discard before sampling.** The kill does not depend on any texture, so it goes first, which also skips the samples for a dead pixel.
4. **Depth.** A discarded fragment writes neither colour nor depth, as on the CPU path (it `continue`s before the depth write).

## Risks

- D3D11 cbuffer size: `NV2APSConstants` must stay a multiple of 16 bytes (432 is). The PS_ABI_SAME asserts cover the shared prefix only, so add one for `clip_mode`.
- Interpolation: Metal and D3D11 interpolate texcoords perspective-correct, as the CPU path's `tc` is. No `noperspective`.
