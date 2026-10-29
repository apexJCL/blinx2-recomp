## Context

The NV2A draws at 640x480. Above `render.scale` 1, each guest pixel covers N x N host pixels, and a bilinear texture is sampled at every host pixel's centre. For a 2D quad drawn 1:1, a WRAP tile's edge host pixels then blend in the opposite edge's texel, and lines show between tiles. The 1x render samples once per guest pixel, at its centre, and shows no line.

`tex_scale.z` already carried a snap for linear-format unity blits (`+N`). Hor+ already scanned program batches through the CPU vertex interpreter (`nv2a_aspect_scan`) to tell 2D from 3D.

## Goals / Non-Goals

**Goals:**
- No seams between 2D tiles above scale 1, on Metal and D3D11, when the player asks for it.
- With the setting off, run what ran before: the same shaders, keys, constants and per-draw work.

**Non-Goals:**
- 3D batches, render targets, and STRETCH or COVER placements.
- The CPU rasteriser, which runs at scale 1 only.

## Decisions

### D1. A setting, default off
The snap makes magnified 2D art look as at 1x, in N x N blocks, instead of smoothed. Some players will prefer the smoothing, so the snap is `render.snap_2d`, default off and live. The rect blit snap (`+N`) stays always on, as before.

### D2. Which batches are 2D
- **Pre-transformed batches:** always 2D.
- **Program batches:** 2D when the scanned vertices share one whole `oPos.w` (the Hor+ scan) and one `oPos.z` (`vary_z`).
  - An orthographic 3D mesh (a menu model at w 1) shares w but not z.
  - Snapping only its axis-aligned faces would mix snapped and smooth faces in one mesh.
- **Placement:** only CENTRE, where a padded target keeps the guest grid on whole host pixels.
- **The decision:** `nv2a_ps_consts_snap` makes it once for both backends and marks the stage `-N`.

### D3. 1x gradients
Moving every host pixel of a block to one uv collapses the implicit derivatives, which would pick the wrong mip level and filter. So a `-N` stage samples with the host derivatives times N, which are the 1x ones.
- D3D11 uses `SampleGrad`, which applies the sampler's `MipLODBias`.
- Metal uses `gradient2d`, scaled by `exp2(bias)`, because `gradient2d` takes no `bias()`.

### D4. Stock text when off
The first version branched on a uniform inside the stock shader. At scale 1 that changed nothing it drew, yet the extra text moved JSRF's D3D11 loading flips on the Deck (dogenzaka FAIL twice where base is EXACT twice).

So the stock path now keeps the base text:
- the 2D helpers live in their own `SNAP_2D` macros;
- the combiner state has a `snap_2d` bit (`key[36]` bit 2) and emits the 2D sampling only with it;
- the basic shader with the snap is a separate variant, built the first time the setting draws (`nv2a_ps_diffuse_snap`, `fs_basic_snap`).

`basic_shaders` locks the stock basic texts to 6385aaf8's by checksum.

### D5. No draw merging under the snap
The walker merges back-to-back batches of one primitive. The snap classes a batch from its own vertices: w, z and a sample of 33. A merged chain would therefore snap differently from its parts: sprites at several depths are not snapped, and a 3D tail the samples miss is snapped. So `merge_on` is off while the snap is on, as under Hor+. Only players who opt in pay for the unmerged draws.

## Risks / Trade-offs

- **Metal shader cache:** the snap bit doubles the combiner variants, and `FS_MAX` (512) has no eviction. This is tracked in TASKS.md.
- **Pre-transformed batches** are taken as 2D without a depth or rhw check, as Hor+ takes them.
