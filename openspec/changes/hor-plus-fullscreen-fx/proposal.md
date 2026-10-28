## Why

In the 2026-10-21 Windows playtest (native D3D11, `render.scale = 3`, `display.aspect = "16:9"`), full-viewport effects stayed at the 4:3 centre under Hor+: JSRF's Can boost blur and tint, the SSX 3 passes the user called "the same Hor+ issues", and Burnout 3's speed-blur seam. The tracker item asks for one generic toolkit rule, the same on D3D11 and Metal, before any per-game `[aspect.*]` override.

The probe (`RECOMP_TRACE=aspect` on the Burnout 3 race route at 16:9, with the trace line now naming the target's address and pitch and the stage's pitch) found the speed blur's chain:

| Pass | Draws into | Samples | Placed |
|---|---|---|---|
| `AA62A9B3` | 0x80A98000, 320x240, pitch 640 (R5G6B5, pad 53) | the 640x480 frame, a render target | stretch |
| `AA62A9B3` | 0x80AC0000, 160x120, pitch 320 (pad 27) | 0x80A98000 as `LIN_R5G6B5` | **centre** (Metal) |
| `A48BAFD2` | 0x80ACC000, 160x120 | 0x80AC0000 as `LIN_R5G6B5` | **centre** (Metal) |
| `C8AF571F` | the 640x480 frame | 0x80A98000 as `LIN_R5G6B5` | **centre** (Metal): the seam |

So the "copy of the post buffer" that native-widescreen D6 expected to need blit provenance is a 16-bit render target the game draws into on the GPU. D3D11 binds it in place (its inline 16-bit test, since it writes nothing back). Metal's `rt_texture` took only 32-bit formats, so it decoded the bytes its write-back had left: the stock 320 columns, a 4:3 picture, classed as one and centred.

## What Changes

- **One rule for both backends**, `nv2a_rt_tex_reads()` in `nv2a_backend_common.h`: a texture stage at a render target's address samples that target in place when it reads the bytes the surface holds. Its colour layout matches the surface format the target was drawn with (`LIN_R5G6B5`/`R5G6B5` an R5G6B5 surface, `A1R5G5B5`/`X1R5G5B5` an X1R5G5B5 one, any 32-bit texture a 32-bit one); its memory order matches the surface type (swizzled as swizzled, linear as linear at the target's pitch); it is not DXT. D3D11's `rt_texture` had its own inline test; it now calls the helper. Metal's `rt_texture` adopts it, so its 16-bit targets bind too.
- Both backends' render targets record the `SET_SURFACE_FORMAT` word they were drawn with (`fmt`).
- Metal reads alpha 1 from a target sampled as a format with no alpha (`nv2a_rt_no_alpha`: R5G6B5, X1R5G5B5, X8R8G8B8), in the combiner path and in `fs_basic`, as D3D11 does.
- `RECOMP_TRACE=aspect` lines name the target's address and pitch and the stage's pitch.
- A ctest (`render_scale`) covers the rule.

Stock behaviour changes (the goldens gate them):

- Metal: a 32-bit read of a target's address samples the target only when the surface is 32-bit and, for a linear read, at the target's pitch; before, any 32-bit read at the address did.
- Metal: a target read as `LIN_X8R8G8B8` (or `R5G6B5`, `X1R5G5B5`) reads alpha 1 instead of the alpha the draws left.
- Metal: a 16-bit frame copy samples its target directly, at the target's 8 bits a channel instead of the write-back's 5 or 6, and without the GPU wait the write-back cost.
- D3D11: a read in another 16-bit layout than the surface's (R5G6B5 against X1R5G5B5), in the other memory order than the surface type, or as `A4R4G4B4` (no surface format has that layout) now decodes guest memory. Before, a matching texel size and pitch was enough.

Placement is unchanged at stock: at 4:3 there is no pad and every batch is centred.

## Reach

The Burnout 3 seam was Metal-only: D3D11 already bound the 16-bit chain in place. So this change fixes Metal and leaves D3D11's Hor+ picture as it was. The rest of the user's 2026-10-21 D3D11 report is not fixed here:

- The tracker item: Burnout 3's crash-cam letterbox bars cover only the 4:3 centre.
- The tracker item: SSX 3's remaining Hor+ gaps (sun glare, HUD and flare sprites). No SSX 3 stage samples a render target, so the rule does not reach them.
- The tracker item: JSRF's Can boost, which needs a route into gameplay before it can be probed.

Task 3.5 (native D3D11 on the PC) stays as a no-regression check of the shared rule there.

## Known gaps

- An X1R5G5B5 surface read as `A1R5G5B5` (0x10) takes the target's alpha (whatever the draws left). The console reads the X bit: 0 for a Z1R5G5B5 surface, 1 for O1R5G5B5. Fixing it needs an "alpha 0" mode next to `alpha_only` 2 in both backends' shaders. No game seen so far reads a target that way (the reject trace and the probes found none), so it waits for one that does.
- A target's `fmt` is the format of its last draw. A target is reused by offset and size only, so one drawn first in one format and then in another is judged by the second.
- A rejected read on D3D11 decodes guest memory that nothing wrote back, so it shows black. On the Deck under Proton at stock, a Burnout 3 race (bench-logs 20261022-020707) and a JSRF boot to the title (20261022-022032) logged no rejected read.

## Capabilities

### Modified Capabilities

- `enhancements`: Hor+ frame copies bind as padded render targets on both backends (the native-widescreen change's "Hor+ frame copies" requirement, narrowed to what the probe found).

## Impact

- Toolkit: `src/kernel/nv2a_backend_common.h`, `src/d3d/nv2a_pb_metal.m`, `src/d3d/nv2a_pb_d3d11.c`, `tests/render_scale/test_main.c`.
- native-widescreen D6 and tasks 6.x: the probe is done here; the provenance table and the CPU-copy match are not needed for Burnout 3.
- No env key, no config key, no game code.
