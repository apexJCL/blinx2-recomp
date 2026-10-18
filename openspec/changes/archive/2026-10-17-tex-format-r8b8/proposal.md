## Why

Spartan: Total Warrior logs one undecoded texture format during boot, on Metal and on D3D11:

```
[metal] texture format 0x29 (256x256 at 0x80720E00) not decoded: drawn magenta
```

Runs: `runs/spartan/20261015-001139-ITEM-mac/stdio.log` line 676 and `runs/spartan/20261015-001343-ITEM-deck/`. Toolkit b958798.

**0x29 is NV097 `SZ_R8B8`, the XDK's `D3DFMT_R8B8`.** Three references agree:
- Our own `src/nv2a/nv2a_regs.h:1221` and xemu's `hw/xbox/nv2a/nv2a_regs.h` both define `NV097_SET_TEXTURE_FORMAT_COLOR_SZ_R8B8 0x29`. Our `src/d3d/d3d8_xbox.h` has `D3DFMT_R8B8 = 0x29` and `D3DFMT_LIN_R8B8 = 0x16`.
- xemu `hw/xbox/nv2a/pgraph/gl/constants.h`: `[SZ_R8B8] = {2, false, GL_RG8, GL_RG, GL_UNSIGNED_BYTE, {GL_GREEN, GL_RED, GL_RED, GL_GREEN}}`. The Vulkan table (`pgraph/vk/constants.h`) says the same: `VK_FORMAT_R8G8_UNORM`, components (G, R, R, G). Both tables give `SZ_G8B8` the mirror swizzle (R, G, R, G).
- Cxbx-Reloaded `src/core/hle/D3D8/XbConvert.cpp`: `0x29 X_D3DFMT_R8B8` and `0x16 X_D3DFMT_LIN_R8B8` are 16-bit rows with the `R8B8` component converter. `____R8B8ToARGBRow_C` reads `b8 = src[0]` and `r8 = src[1]` and writes `dst[0..3]` (B, G, R, A) = `b8, b8, r8, r8`. Its `____G8B8ToARGBRow_C` writes `b8, g8, b8, g8`.

**Layout.** Two bytes per texel, unsigned 8-bit channels, swizzled (Morton order, like every non-`LIN_` format). The low byte is B and the high byte is R, as the name reads in a little-endian 16-bit word (`0xRRBB`). Expanded to A8R8G8B8, R and A take the high byte and G and B take the low byte. G8B8 (0x28 and 0x17), which the toolkit already decodes, is the same layout with the high byte in G and A instead of R and A. xemu and Cxbx both mark the pair "this might be signed". Neither decodes it signed, and on the NV2A sign is a per-stage state (`SET_TEXTURE_FILTER` bits 28-31, the XDK's `D3DTSS_COLORSIGN`), not a property of the format (design.md D3). Spartan's stage-1 filter word is `0x02022000`: those bits are clear.

**What Spartan uses it for.** The texture is a 256x256 lookup table read through a bump-map stage in the game's glow or bloom pass. A CPU-backend run with the texture survey and texture-state report on (`runs/ITEM/20261015-051845-r8b8-cpu-texdump/`) shows this sequence:
1. The 640x480 frame is drawn down to a 320x240 target (0x00611000).
2. One batch draws into a second 320x240 target (0x0065C000). It reads three stages:
   - stage 0: the downsampled target, read as `LIN_R8G8B8A8` (0x41), the same bytes re-read in the channel order the bump stage expects;
   - stage 1: the R8B8 texture, with texture-shader mode 6 (`BUMPENVMAP`). This is its only use in the run (`fmtword 0x08812929`, one mip level, 256x256, `stages 0x2`);
   - stage 2: the same target, read as `LIN_A8R8G8B8`.
3. The chain blurs down through 160x120 and 80x60, then composites back into the 640x480 frame.

Mode 6 offsets stage 1's coordinates by a matrix times the *input* stage's texel (xemu `psh.c` reads stage 0's `.b` and `.g`, remapped to signed), so the reordered frame colour indexes the table. This is the usual Xbox way to do a 2D dependent lookup, here a brightness threshold or colour remap. The table's own channel order decides only the colour the lookup returns, not where it reads. The same report shows one batch with stage 3 in mode 6 as well, with no texture logged for that stage (`[VSH] stage 3 shader modes ... 6=1`); the BUMPENVMAP follow-up should look at it.

The lookup itself is a separate gap. `BUMPENVMAP` is not implemented on any path (cat `TASKS.md`: "BUMPENVMAP (texture mode 6) is unimplemented on every path; it samples as plain 2D"). Once this change decodes the table, every backend samples it at stage 1's own interpolated coordinates. That pass is then wrong in a quieter way: it reads the wrong texels instead of drawing magenta. In the boot runs so far (Spartan stalls after flip 4), all dumped frames are a single colour, so the pass does not reach a presented frame yet.

**BLiNX 2 and Burnout 3 never bind 0x29 or 0x16.** Both GPU backends print `texture format 0xNN (...) not decoded: drawn magenta` once per run for every format that has no decoder, and on main 0x29 and 0x16 have none. The newest main runs contain no such line at all: the Deck D3D11 goldens of 2026-10-15 (`bench-logs/20261015-002717`, `-002836`, `-003028`: attract, stage1, story, all pass), the Metal attract runs in `runs/ITEM/metal-base-quiet/` and `metal-fix-quiet/`, and the Burnout 3 race-gate logs `runs/ITEM/b3-deck/20261014-234827/game-stdio.log` (86995 flip lines) and `runs/ITEM/b3-mac/20261014-234205-base/`. So their output cannot change (design.md, Validation).

## What Changes

- **Decode R8B8 and its linear twin in the shared texel table** (`xboxrecomp/src/kernel/nv2a_backend_common.h`). Three changes:
  - `nv2a_tex_linear_twin` maps 0x29 to 0x16;
  - `nv2a_tex_texel_bytes` returns 2 for 0x16;
  - `nv2a_tex_decode_texel` gains a 0x16 case: R and A from the high byte, G and B from the low.

  All three texel paths read this table, so one change covers them all:
  - Metal: `tex_bind` in `src/d3d/nv2a_pb_metal.m`, through `nv2a_tex_extent` and `nv2a_tex_decode`;
  - D3D11: `tex_bind` and `tex_extent` in `src/d3d/nv2a_pb_d3d11.c`, through the same functions;
  - the CPU sampler and pb_exec texture path in `src/kernel/nv2a_pb_exec.c`, through `nv2a_tex_linear_twin` and `nv2a_tex_decode_texel`.

  Neither GPU backend maps formats to native host formats. Both upload the shared decode as BGRA8, so the backends agree by construction (design.md D1).
- **0x16 `LIN_R8B8` is included.** It is the one neighbour that is a one-line addition: it uses the same texel encoding, and only the address calculation differs. The XDK defines it (`D3DFMT_LIN_R8B8 = 0x16`; Cxbx's `XbD3D8Types.h`, which mirrors the XDK, has `X_D3DFMT_LIN_R8B8 = 0x16`), and the toolkit's `d3d8_format_is_swizzled` already lists 0x16 as linear. xemu has no `LU_IMAGE_R8B8` define or table entry, so its row comes from the XDK and from the swizzled twin's encoding (design.md D2).
- **A ctest of known texels** in `tests/nv2a_tex` (design.md, Validation).
- The neighbours that are not one-line additions are listed as follow-ups (design.md D4).

## Impact

- Toolkit: `src/kernel/nv2a_backend_common.h` (+12 lines) and `tests/nv2a_tex/test_main.c`. No backend file, env key, renderer state or generated code changes.
- The decoded texture becomes cacheable and hashable like any 16-bit format. Metal's and D3D11's render-target-as-texture fast path (`rt_texture`) still skips it, because it is neither 4 bytes nor one of D3D11's 16-bit surface formats. That is correct: no NV2A surface format writes R8B8.
- Spartan: the magenta line disappears on Metal, D3D11 and CPU. The glow pass is still not right until BUMPENVMAP lands (follow-up).
- BLiNX 2 and Burnout 3: no format they bind changes, so no golden or race-gate verdict can move. The gate plan in tasks.md is sized to that (one Metal golden check as the game-build sanity run; the Deck D3D11 golden is the post-merge integrate run).
- Upstream's HLE D3D8 layer (`src/d3d/d3d8_resources.c`, `d3d8_to_dxgi_format`) maps `D3DFMT_R8B8`, `LIN_R8B8`, `G8B8` and `LIN_G8B8` to `DXGI_FORMAT_R8G8_UNORM` with no swizzle, so a title on that layer reads R from the low byte. None of our titles runs that layer (all three go through the pushbuffer executor). Recorded with follow-up 3 (design.md D4), not changed here.
- Upstream: a title-agnostic decode fix with a test. It is a candidate for the PR stack on the same terms as the other decode additions.
- Prototype: toolkit branch `ITEM/tex-format-0x29` at a3e3de5, off `posix-host/portability` b958798, in `wt/ITEM/xboxrecomp`. The review found the decode and the tests correct; one test comment needs a fix (tasks.md 1.2).
