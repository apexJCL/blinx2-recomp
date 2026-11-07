# Design: nv2a-dot-stages

## D1. Semantics follow xemu's psh.c

For stage i of a dot mode, `dot_i = dot(T_i.xyz, map(input texel))`,
where T_i is the stage's texture coordinate and the input is stage 0,
or the stage `SET_SHADER_OTHER_STAGE_INPUT` names (`nv2a_stage_input`,
the same helper BUMPENVMAP uses). `map` is the stage's 3-bit field of
`SET_DOT_RGBMAPPING`: stage 1 in bits 0-2, stage 2 in 4-6, stage 3 in
8-10. With x the channel's byte value (0-255), the fields are xemu's:

- 1: `(x - 128) / 127`, D3D's signed mapping (sign1);
- 2: `x >= 128 ? (x - 255.5) / 127.5 : (x + 0.5) / 127.5`, the GL
  mapping (sign2);
- 3: two's complement, `x >= 128 ? (x - 256) / 127 : x / 127` (sign3);
- 0 and 4-7: the texel as is (unsigned; HILO formats are not decoded,
  see D5).

By mode:

| Mode | Stages | Reads |
|---|---|---|
| DOTPRODUCT 0x11 | 1, 2 | nothing (0); its dot feeds a later stage |
| DOT_ST 9 | 2, 3 | 2D at (dot of the previous stage, its own dot) |
| DOT_ZW 0xA | 2, 3 | 0 (depth replace is not emulated) |
| DOT_RFLCT_DIFF 0xB | 2 | cube at (dot1, dot2, dot3 from stage 3's coordinate) |
| DOT_RFLCT_SPEC 0xC | 3 | cube at `2n·dot(n,e)/dot(n,n) - e`, e = (T1.w, T2.w, T3.w) |
| DOT_STR_3D 0xD | 3 | 2D at (dot1, dot2): slice 0 (D5) |
| DOT_STR_CUBE 0xE | 3 | cube at (dot1, dot2, dot3) |
| DPNDNT_AR / GB 0xF, 0x10 | 1-3 | 2D at the input texel's (a, r) or (g, b) |
| BRDF 8, SPEC_CONST 0x12 | 2, 3 / 3 | 0, as xemu |

A mode outside its stages is something the hardware would not run, so it
is sampled as 2D, as before (`nv2a_dot_mode_ok`). The 2D samples apply
the stage's `tex_scale`, plus the Hor+ offset when a render target is
read, the same way the plain 2D path does.

## D2. A disabled DOTPRODUCT stage keeps its mode

`nv2a_stage_decode` gates a disabled stage to mode 0. A DOTPRODUCT stage
samples nothing, and QR leaves stage 1 disabled, but stage 3 still
needs its dot. `nv2a_stage_ps_mode` therefore reads the dot family from
`raw_mode`. A dot stage that samples nothing (DOTPRODUCT, DOT_ZW, BRDF,
SPEC_CONST) declares no texture and gets no `alpha_only` fix-up, since
it holds 0, not a texel. Under the combiners' shader both backends bind
it the black view without decoding its texture; D3D11 rebinds the real
2D texture if the batch falls back to the basic shader.

The stages a later stage reads (`nv2a_bump_sources`: no anisotropy,
and never taken as a hor+ picture) are every input of a mode from 6
on: BUMPENVMAP, the dot family and DPNDNT. Under a DOT_RFLCT_DIFF stage
2, stage 3's input counts too: its third dot product reads it.

## D3. Cube maps are bound as cubes only for the combiners' shader

`nv2a_stage_cube_bind` holds when four things are true: a cube-reading
mode (CUBEMAP, RFLCT_DIFF, RFLCT_SPEC, STR_CUBE), a bound stage,
`CUBEMAP_ENABLE`, and a square texture. Both backends then decode six
faces at `offset + f * nv2a_stage_face_stride`. The stride uses the
FORMAT level count (the memory layout), and sampling uses the stage's
levels. They hash and cache the whole span (`nv2a_stage_cube_extent`),
with the cube flag in the cache key. They upload with Metal's
`MTLTextureTypeCube` or D3D11's `TEXTURECUBE` array of six. A failed
decode gets a 1x1 black cube, so the declaration and the view always
agree. A cube is never a render target: a cube over one is read as 2D
(D5).

Only the combiners' shader declares cubes (`tex_cube` in
`NV2ACombinerState`, set from the key). When a batch ends up on the
basic shader, the stage keeps the face-0 2D view: no MSL or HLSL, a
compile failure, or Metal's FS_MAX. Metal knows this before it binds
(`s_fs_comb`, set by `fs_select`). D3D11 picks its shader after binding,
so it rebinds those stages as 2D.

CUBEMAP (mode 3) stages also take the cube path now. They were demoted
to a face-0 2D read before. This changes the frame wherever a title uses
an environment cube. QR's ships do (stage program 0x18C21), and BLiNX 2
is checked by its goldens.

## D4. Keys

`nv2a_ps_stage_key` gives `modes` (5 bits a stage) and `extra`:

- bits 0-15: the input stage of every stage in mode 6 or above, and of
  stage 3 under a DOT_RFLCT_DIFF stage 2;
- bits 16-27: the dot mappings of stages 1-3 (stage 3's also under
  DOT_RFLCT_DIFF);
- bits 28-31: the cube bits.

Both backends put `extra` in key word 37 and unpack it into `tex_input`,
`dot_map` and `tex_cube`. The generators emit the dot helpers
(`nv2a_dotmap`, `nv2a_cube_2d`) and the `dp1..dp3` locals only when
some stage is a dot mode, so the text for every other state stays as it
was. Text is unchanged for the D3D8 front end (`bump_on` 0), whose 4-bit
modes 8 and above are not texture-shader modes.

## D5. Known limits

- DOT_STR_3D samples slice 0: 3D textures stay 2D, as everywhere in the
  backends.
- HILO dot mappings read the texel's rgb. No HILO format is decoded yet.
- DOT_ZW does not replace depth.
- The CPU rasteriser samples every one of these modes as 2D (TASKS).
- A cube over a live render target binds no cube. Before the key, each
  backend sets `nv2a_stage.cube_rt` on a stage whose six-face span
  (`nv2a_stage_cube_extent`) overlaps a live target
  (`nv2a_stage_cube_over_rt`, the low 27 bits). `nv2a_stage_cube_bind`
  then fails, so the key's cube bit, the shader's declaration and the
  bind all take the 2D read the same way on both backends: CUBEMAP
  becomes a 2D read at (s, t), and a cube-reading dot mode reads 2D
  through `nv2a_cube_2d`. The stage binds the target's own texture when
  one starts at its offset (`rt_texture`), else face 0 from guest memory,
  as any 2D stage. Neither backend decodes six faces from bytes a target
  covers (stale on D3D11; up to six write-backs a flip on Metal).
  Only a live target counts: an overlapping one the title has since
  overwritten (`rt_drop_if_stale`, as `rt_texture` and `surface` check)
  is dropped there, so a cube loaded over a leftover target binds as a
  cube again at once rather than after the target's eviction. D3D11's
  stage-loop memo is not kept when the loop itself dropped a target,
  since the next draw's `cube_rt`, and so its shader, can differ.
