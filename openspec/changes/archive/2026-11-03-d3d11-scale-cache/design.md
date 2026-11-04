## Is the D3D11 texture cache scale-independent?

Yes. I read the code at toolkit `18607bd9`:

- **Entries are guest-sized.** `tex_upload` makes each `TexEntry` texture
  at the stage's guest width, height and levels, or at a texture pack's
  size. Nothing in `tex_alloc`, `tex_upload`, `decode_texture` or `tex_bind`
  reads `nv2a_host_render_scale()`. In this file the scale is read only by
  the target and depth sizing (`nv2a_host_size`), the window size, the
  shader key bit and the occlusion scale.
- **Render to texture never goes through the cache.** `rt_texture` binds the
  target's own view (`rt->srv`). For a target being drawn into, it binds a
  copy, `s_self`. `rt_self_copy` remakes that copy when the target's `w`,
  `h`, `hw` or `hh` differ, so a scale change resizes it. The stage loop
  calls `rt_texture` before `tex_bind`, so a stage over a live target never
  reads a cache entry.
- **Released targets cannot leave stale entries.** D3D11 never writes a
  target back to guest memory, so there is nothing like Metal's
  `tex_cache_stale`. `tex_bind` rehashes each entry once per flip
  (`e->gen != g->flips`) and uploads again if the bytes moved. After
  `scale_drop`, a stage over a released target decodes the guest bytes at
  its address, both with the kept cache and with a fresh one. Its entry
  holds the same texels either way. The first frame at the new scale shows
  `rtt 0` for that stage on base too, until the title draws the target
  again.
- **Memos stay valid.** The stage-loop memo checks `s_rt_gen` (moved by
  `rt_release`), `s_tc_gen` and the flip number. The `s_tc_hint` table
  points at entries that still exist, and `tex_bind` checks every hint
  against the key, so it can stay too.

The drop and its "sized by scale" comment came in with live host options
(`1cae22ef`). By then `rt_texture` already bound the target directly
(`b4f4540c`), so no code depended on the drop. It was a precaution.

## Testing

`scale_drop` needs a D3D11 device, so the POSIX ctests cannot test it. The
D3D11 backend smoke (`tests/d3d11_backend_smoke`, run under Proton) gets a
case: after each of 2x, 3x and 1x, the next flip uploads no texture, the
cached checker still samples right, a texel rewritten after the change
uploads the checker once and shows the new colour (the per-flip rehash,
which needs `FLIP_INCREMENT_WRITE` to move the flip count), and a target
cleared to a colour of its own at each scale samples that colour at
64 times the scale. On base the upload count fails. The game check is a JSRF run on the Deck under Proton, base and
fix, with `opts_at=3200:scale=2,3800:scale=3,4400:scale=1`. The run records:

- the wall ms of the first flip after each change;
- the upload count of that flip;
- `d3d11_dump` frames before and after each change, compared between base
  and fix.
