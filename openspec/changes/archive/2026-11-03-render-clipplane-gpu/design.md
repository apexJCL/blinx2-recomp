## Context

- CPU reference: `stage_clip_kills()` in `nv2a_pb_exec.c` (~3663). Bit `n * 4 + j` of `clip_plane_mode` set means the pixel dies at `tc[j] >= 0`, clear means it dies at `tc[j] < 0`, where `tc` is the stage's perspective-correct interpolated coordinate (not divided by q). A killed pixel `continue`s before the depth test and write. xemu emits the same compares on `pT<n>` (psh.c, PS_TEXTUREMODES_CLIPPLANE).
- Since 35e17dd1 the Metal and D3D11 combiner keys carry mode 5 for a CLIPPLANE stage (`nv2a_stage_ps_mode` reads `raw_mode`), and the emitters bind no texture for it and leave its register 0.
- `build_stages` in both backends binds a mode-5 stage as mode 0, so `pc.tex_mode[n]` is 0 for it. The no-combiner shaders read only `tex_mode`, so they cannot see the stage at all today.

## Decisions

1. **One packed constant, not a shader variant per mode word.** `clip_mode[n]` is a word per stage in a `uint4`, so a title that flips plane signs per batch does not compile a shader each time. The compare is four `select`s and a discard, and only stages whose key says CLIPPLANE emit it, so other shaders gain only the constant.
2. **A flag bit, `0x10`.** `nv2a_ps_consts_fill` writes `0x10 | ((clip_plane_mode >> 4n) & 0xF)` for a stage whose `raw_mode` is 5, else 0. The combiner emitters already know the mode from the key, but `fs_basic` and `s_ps_src` only have the constant, and nibble 0 is a real setting (all four die at `< 0`). Every kill is gated on the flag, so the legacy path's zero and every non-CLIPPLANE stage keep their behaviour.
3. **Append, don't reuse.** Packing the nibble into `tex_mode`'s high bits would avoid the layout change. But `tex_mode` is compared with `==` in both emitters and in `fs_basic`, and a packed field is an easy future bug. The constant grows by 16 bytes, to 560. Both backends upload the struct as a whole, and the `_Static_assert`s pin it (`PS_AT` in `nv2a_pb_metal.m`, `PS_ABI_SAME` and the size assert in `nv2a_pb_d3d11.c`).
4. **Discard at the end, beside the alpha test.** The kill needs no texture, so it could go first and skip the samples, but a conditional discard ahead of them puts the samples in non-uniform control flow, where implicit derivatives (and so mip selection) are undefined and fxc warns on gradient ops. The toolkit's alpha-test discard already sits at the end, so the clip test goes beside it: `if (nv2a_clip_kills(...)) discard_fragment();` in MSL and `discard;` in HLSL, not `clip()`, so one helper serves both languages and the four compares stay readable.
5. **Depth.** A discarded fragment writes neither colour nor depth, as on the CPU path.

## Risks

- D3D11 cbuffer size: `NV2APSConstants` must stay a multiple of 16 bytes (560 is). The `PS_ABI_SAME` asserts cover each shared field, so add one for `clip_mode`.
- Interpolation: Metal and D3D11 interpolate texcoords perspective-correct, as the CPU path's `tc` is. No `noperspective`.
- CPU no-combiner edge: the CPU basic path tests the planes only when stage 0 also has a valid texture (`T->textured`), and then modulates by the zero texel. The GPU no-combiner shaders kill on the flag alone and leave survivors at oD0, so a no-combiner CLIPPLANE stage 0 differs from the CPU path in which pixels die (no texture) or in the survivors' colour (texture valid). That is a CPU-side gap (xemu kills regardless); it is recorded in TASKS.md, not changed here.
