## Context

Every texel the toolkit samples passes through one table in `src/kernel/nv2a_backend_common.h`:

- `nv2a_tex_linear_twin(fmt)` maps a swizzled format to the linear format with the same texel encoding. Swizzling changes only where a texel lives, so one decoder serves both.
- `nv2a_tex_texel_bytes(lin)` gives the bytes per texel of a linear format, or 0 when there is no decoder.
- `nv2a_tex_decode_texel(lin, p, u, ...)` turns one texel into A8R8G8B8.

`nv2a_tex_extent` (in `nv2a_backend_common.c`) returns 0 for a format whose twin has no texel size. Both GPU backends treat an extent of 0 as "not decoded". They bind a 1x1 magenta texture and print the line Spartan shows, once per format per run (Metal `tex_bind`, `nv2a_pb_metal.m:1411`; D3D11 `tex_bind`, `nv2a_pb_d3d11.c:1756`). When the extent is non-zero, they call `nv2a_tex_decode`, which walks the swizzle with `nv2a_tex_decode_level`, and upload BGRA8. The CPU sampler (`nv2a_pb_exec.c:1535-1565`) calls `nv2a_tex_linear_twin` and `nv2a_tex_decode_texel` directly, and samples magenta (`[GPU] texture format 0xNN has no decoder; sampling magenta`, once) when the decoder returns 0.

## D1. One table change covers all three paths

The fix is the three table entries, nothing else:

| function | change |
|---|---|
| `nv2a_tex_linear_twin` | `case 0x29: return 0x16;  /* R8B8 -> LIN_R8B8 */` |
| `nv2a_tex_texel_bytes` | 0x16 joins the 2-byte list |
| `nv2a_tex_decode_texel` | `case 0x16`: `t = u16; argb = hi<<24 \| hi<<16 \| lo<<8 \| lo` |

The case sits next to `0x17` (LIN_G8B8), with a comment that names the two references and the difference from G8B8.

No per-backend mapping is needed. `nv2a_pb_d3d11.c` and `nv2a_pb_metal.m` have no switch on texture format apart from the render-target alias check (`rt_texture`, `rt_16bit`); checked at review (no `case 0x1X/0x2X/0x3X` label in either file). That check is about formats a surface can be written in, and R8B8 is not one. So "backends agree" holds by construction: Metal, D3D11 and CPU decode the same bytes with the same function. The CPU rasteriser's texel path is in the change, although it is not in the routine gates.

Every other case label in the three switches is untouched and disjoint from 0x29 and 0x16, so no format the toolkit already decodes can change: the only texels this change can alter are texels of 0x29 and 0x16.

**Rejected: a native two-channel upload** (`MTLPixelFormatRG8Unorm` or `DXGI_FORMAT_R8G8_UNORM` plus a swizzle). That would be the only native format in either backend, and it would need per-backend swizzle state that the shared decode avoids. The texture is 128 KB at most. Decoding it on the CPU costs as much as the G8B8 path, which has never shown up in a profile.

## D2. Channel order, and why LIN_R8B8 is included

The reference decodes, each checked against the source at review:
- xemu GL (`pgraph/gl/constants.h`): `GL_RG8` with swizzle (r, g, b, a) = (GREEN, RED, RED, GREEN). `GL_RG`/`GL_UNSIGNED_BYTE` puts byte 0 in texture red and byte 1 in texture green, so out.R = byte 1, out.G = byte 0, out.B = byte 0, out.A = byte 1.
- xemu Vulkan (`pgraph/vk/constants.h`): `VK_FORMAT_R8G8_UNORM`, components (G, R, R, G), the same.
- Cxbx-Reloaded `____R8B8ToARGBRow_C` (`XbConvert.cpp`): `b8 = src[0]`, `r8 = src[1]`; `dst[0..3]` = `b8, b8, r8, r8`, that is B, G, R, A = byte 0, byte 0, byte 1, byte 1, the same.

The control is G8B8, which the toolkit already decodes: xemu's swizzle is (RED, GREEN, RED, GREEN) in both tables and Cxbx's `____G8B8ToARGBRow_C` writes `b8, g8, b8, g8`, so there out.R = out.B = byte 0 and out.G = out.A = byte 1, which is what `case 0x17` does today. The two formats are mirrors: the high byte goes to the channel the name puts first (R or G) and to A; the low byte goes to B and to the other one.

The names agree with this: in a little-endian 16-bit word "R8B8" is `0xRRBB` and "G8B8" is `0xGGBB`. The replication of each byte into the channel the name does not mention is how xemu and Cxbx model the hardware; no reference reads those channels as 0 or 1.

For bytes `AB 12`, R8B8 gives `0x1212ABAB` and G8B8 gives `0x12AB12AB`. The ctest pins both, so the two formats cannot be swapped by mistake.

`LIN_R8B8` (0x16) uses the same encoding as R8B8 at linear addresses. It is well-founded without xemu: the XDK defines `D3DFMT_LIN_R8B8 = 0x16` (our `d3d8_xbox.h:210`; Cxbx's `XbD3D8Types.h`, which mirrors the XDK enum, has `X_D3DFMT_LIN_R8B8 = 0x16` with a 16-bit linear `R8B8` row in its table), and the toolkit itself already calls 0x16 linear in `d3d8_format_is_swizzled` (`d3d8_swizzle.h:424`) and maps it in the HLE layer. xemu's `nv2a_regs.h` skips from 0x13 to 0x17 and neither of its tables has an entry, so a title that bound 0x16 would fail there; that is a gap in xemu, not evidence against the format. Adding it costs one `case` label and one twin entry, and leaving it out would let the next title hit the same magenta line through a linear upload. It is included, and it has its own ctest case.

## D3. Unsigned, as the references decode it

xemu and Cxbx-Reloaded both note "This might be signed" next to R8B8, and both decode it unsigned. Four facts settle it:

1. On the NV2A, sign is per stage, not per format: `SET_TEXTURE_FILTER` bits 28-31 (`ASIGNED`, `RSIGNED`, `GSIGNED`, `BSIGNED`; our `nv2a_regs.h:575-578`). The XDK exposes them as the texture-stage state `D3DTSS_COLORSIGN` (our `d3d8_xbox.h:427`), which a title sets alongside the texture.
2. The XDK's signed bump formats are aliases of the unsigned ones, so the format word cannot carry sign: Cxbx's header, which mirrors the XDK's `d3d8types.h`, has `X_D3DFMT_V8U8 = 0x28 // Alias` (G8B8), `L6V5U5 = 0x27` (R6G5B5), `X8L8V8U8 = 0x07` (X8R8G8B8), `Q8W8V8U8 = 0x3A` (A8B8G8R8), `LIN_V8U8 = 0x17`, `LIN_L6V5U5 = 0x37`, `LIN_X8L8V8U8 = 0x1E`.
3. xemu does not implement the SIGNED bits either: `pgraph/glsl/psh.c` reads only the MIN filter and the convolution kernel out of `TEXFILTER0`, and its snorm texture path is under `#if 0 // FIXME`. Its BUMPENVMAP remaps the unsigned texel with `sign3()` instead. So every reference decodes unsigned and applies sign downstream.
4. Spartan does not ask for sign here: the texture-state report shows stage 1's filter method `0x1B54 = 0x02022000` (MIN 2, MAG 2, bits 28-31 clear) in the batch that binds the table.

The toolkit does not read the SIGNED bits on any path today, for any format. That gap is wider than R8B8, so it is a follow-up (D4), not a reason to decode this one format signed.

## D4. Neighbouring formats: what is in, what is a follow-up

Each format below was checked against the references:

| fmt | name | status |
|---|---|---|
| 0x29 | SZ_R8B8 | **this change** |
| 0x16 | LIN_R8B8 | **this change** (D2) |
| 0x28 / 0x17 | G8B8 / LIN_G8B8 | already decoded |
| 0x27 / 0x37 | R6G5B5 / LIN_R6G5B5 | already decoded |
| 0x08, 0x09, 0x0A, 0x0D, 0x14, 0x15, 0x18 | — | Cxbx: "undefined" (empty rows); xemu: no define. Our `d3d8_xbox.h` names them `X8L8V8U8`, `L6V5U5`, `V8U8`, `Q8W8V8U8`, `LIN_X8L8V8U8`, `LIN_V8U8` and `LIN_L6V5U5` ("distinct from" the unsigned formats), which disagrees with the XDK, where those are aliases of 0x07, 0x27, 0x28, 0x3A, 0x1E, 0x17 and 0x37 (D3). The values come from upstream commit d48a8a2 (`d3d8: extended texture formats`). They have no decoder, so a title that wrote one of them would get the magenta line, not a wrong picture. The toolkit's `docs/technical/gap-analysis.md` (line 27) marks the HLE "Signed texture formats" row DONE on those values, so that row is revisited with them. Follow-up 3. |
| 0x33 / 0x36 | V16U16 / LIN_V16U16 | 32-bit signed two-channel. No xemu entry; Cxbx has the rows but no component converter (`NoCmpnts`), and calls 0x36 "unused on Xbox". Not a one-line addition: follow-up if a title uses it. |
| 0x2A-0x2D, 0x2E-0x31 | D24S8, F24S8, D16, F16 (swizzled and linear) | depth textures. They need depth-compare semantics (`SET_TEXTURE_CONTROL0` shadow compare) and float-depth decode, not a texel row. Follow-up. |

**Follow-ups to file:**
1. **BUMPENVMAP (texture mode 6), every path.** Spartan's glow pass needs it for the R8B8 table to be read at the right texels (the offset comes from stage 0's `.b` and `.g`, as xemu's `psh.c` reads it, through the bump matrix). BLiNX 2's Boss 3 ripple and stage-1 ocean already need it (cat TASKS.md). Spartan's report also shows one batch with stage 3 in mode 6 and no texture logged for it.
2. **`SET_TEXTURE_FILTER` `SIGNED` bits** (28-31), on every path. Spartan's R8B8 stage has them clear (D3); the first title that sets them is the test case.
3. **`d3d8_xbox.h` bump-format values and the HLE format map.** `D3DFMT_X8L8V8U8 = 0x08`, `L6V5U5 = 0x09`, `V8U8 = 0x0A`, `Q8W8V8U8 = 0x0D` and `LIN_X8L8V8U8`/`LIN_V8U8`/`LIN_L6V5U5` = 0x14/0x15/0x18 are not XDK values (D3, item 2). Their only readers are the HLE layer's `d3d8_to_dxgi_format` (`d3d8_resources.c`, called from `d3d8_device.c`) and `d3d8_format_is_swizzled`; the pushbuffer decode switches on raw values. The same HLE map sends `R8B8`, `LIN_R8B8`, `G8B8` and `LIN_G8B8` to `DXGI_FORMAT_R8G8_UNORM` with no swizzle, so on that layer R8B8 reads R from the low byte, the opposite of the shared decode and of both references. None of our titles runs the HLE layer. This is upstream code, so the fix is an upstream PR candidate; audit `d3d8_device.c`'s callers before changing the enum.
4. **Depth texture formats** 0x2A-0x31, and V16U16 0x33/0x36, when a title samples one.

## Validation

- **ctest** (`tests/nv2a_tex/test_main.c`; the prototype has it):
  - `nv2a_tex_linear_twin(0x29) == 0x16` and `nv2a_tex_texel_bytes(0x16) == 2`;
  - linear texel `AB 12` → `0x1212ABAB`, `00 FF` → `0xFFFF0000`, and G8B8 on the same bytes → `0x12AB12AB` (the control);
  - a swizzled 2x2 R8B8 level `01 10 02 20 03 30 04 40` decodes to `0x10100101, 0x20200202, 0x30300303, 0x40400404` in row-major order, and the level takes 8 bytes;
  - `nv2a_tex_extent` for Spartan's 256x256 is 131072 bytes at one level and 174762 bytes for a 9-level chain, and a linear 4x2 at pitch 16 is 24 bytes.

  Against the base header, the test fails at the twin check. With the change it passes. Fix the comment on the swizzled case: Spartan's texture has one level (`fmtword 0x08812929`, `mips 1`); the 9-level extent is the full-chain check, not Spartan's chain.
- **Spartan, Metal and D3D11:** the magenta line for 0x29 is gone, and no `not decoded` line appears for any format. Spartan does not present the glow pass yet (all frames are one colour; BLX-134), so there is no screenshot to compare. When it does, a frame dump of that pass goes to `runs/blx136/` only. On a CPU run with the survey on (`RECOMP_TRACE=tex=2`), the bind line reads `[TEXLOG] new 0x80720E00 fmt 0x29 swz 256x256 ... decode ok`; the prototype's run already shows it.
- **Gate titles: no golden or race verdict can move, and the plan is sized to that.** D1 shows the change can only alter texels of 0x29 and 0x16. Both GPU backends print `texture format 0xNN (...) not decoded: drawn magenta` once per run for every format without a decoder, and on main those two have none, so a title that bound either would have left that line in every main run. The newest main logs have no `not decoded` or `no decoder` line at all: the Deck D3D11 goldens `bench-logs/20261015-002717` (attract), `-002836` (stage1), `-003028` (story), all pass; the Metal attract runs under `runs/blx132/metal-base-quiet/` and `metal-fix-quiet/`; the Burnout 3 race-gate logs `runs/blx132/b3-deck/20261014-234827/game-stdio.log` (86995 flip lines) and `runs/blx132/b3-mac/20261014-234205-base/game-stdio.log`. Therefore:
  - one BLiNX 2 Metal golden check against the branch is run as the game-build sanity gate (a cat build against the new header must still link and render; it is minutes on the Mac), with no A/B timing series: nothing on the hot path changes for the formats BLiNX binds;
  - the Burnout 3 race gate is not a pre-merge gate for this change (B3 builds the toolkit at its own pin, and its logs show it binds no undecodable format); its next pin bump runs the gate as usual;
  - the Deck D3D11 BLiNX golden is the post-merge `integrate --golden` run that CLAUDE.md step 5 requires anyway (Mac build, copy, `blinx2 bench golden`; memory note *deck-proton-bench*), not a second pre-merge run. The D3D11 code path for the new format is exercised by the Spartan Deck run, which is pre-merge.
  The texture survey (`RECOMP_TRACE=tex`) is not the check: `tex_log_note` runs from `raster_batch_vsh_one`, the CPU rasteriser, so it never fires on a Metal or D3D11 run.
