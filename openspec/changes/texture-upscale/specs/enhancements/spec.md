## ADDED Requirements

### Requirement: Pack version 3: a world kind and BC1 payloads
The texture pack reader SHALL accept versions 1, 2 and 3, each validated by its own version's kind mask and known flags (a version 2 file still refuses kind 3 and bit 5). Version 3 SHALL keep version 2's layout and add the entry kind `WORLD` (kind 3), the flag `XRTP_FLAG_BC1` (bit 5: the payload is BC1 blocks of each level, 8 bytes per 4x4 block; the multiple-of-4 dimension check applies to BC1 as to BC3) and a header word at offset 28 naming the kinds present; any kind or flag bit version 3 does not define SHALL be refused whole. Metal and D3D11 SHALL upload a BC1 entry natively (`MTLPixelFormatBC1_RGBA`, `DXGI_FORMAT_BC1_UNORM`) with block-row pitch, level by level, and SHALL count an entry the device refuses as a miss tagged ` (entry refused)`. For a pack entry, with `shift = log2(entry width / guest width)`, both samplers SHALL shift `lod_max` by `+shift`, SHALL leave `lod_min` at 0 when the guest's is 0 and shift it by `+shift` only when the guest set it above 0, SHALL carry the shift in the sampler key, and for a one-level guest texture with a pack chain SHALL turn mip filtering on with `lod_min` 0 and `lod_max` equal to the shift (the full chain when the entry has one), so the entry's levels below the guest's level 0 are sampled at magnification; a texture not from the pack SHALL be sampled exactly as before. Once a backend has created the host texture it SHALL release the entry's host-memory copy; a later upload reads it again. The miss record SHALL count P8 and mipped uploads as candidates. The pack log line SHALL read `[ENHANCE] textures.pack=<path> (<n> entries: <a> ui, <f> font, <t> text, <w> world; v<ver>; scale <s>, text <ts>; <b1> bc1, <b3> bc3) textures.font=<on|off> textures.text=<on|off> textures.world=<on|off>`.

#### Scenario: v3 world entry in BC1
- **WHEN** a pack holds one `WORLD|BC1` entry of 512x256 with 10 levels and `@stage1` draws the texture on Metal and on D3D11
- **THEN** the host texture is created with 10 BC1 levels, no magenta texel appears, the hit count rises, and the shared block vector decodes within the toolkit test's tolerance

#### Scenario: Upscaled levels sampled near, far end no worse than stock
- **WHEN** a one-level 256x256 guest texture is replaced by a 4x entry with a full chain and drawn once at four pixels per source texel and once at a quarter texel per pixel
- **THEN** the sampler has mip filtering on with `lod_min` 0 and `lod_max` 2, the magnified draw samples the entry's level 0 (its texels show the upscaled detail, not the box-filtered guest level), and the distant draw's aliasing at that surface is no greater than the stock run's at the same flip

#### Scenario: Guest clamp kept in entry levels
- **WHEN** a mipped guest texture with `lod_min` 1 and `lod_max` 5 is replaced by a 2x entry
- **THEN** the sampler's clamps are 2 and 6

#### Scenario: Older packs still read
- **WHEN** the existing version 2 HUD pack is named
- **THEN** it loads with the same entries and the log line shows `v2` and `0 world`

#### Scenario: Unknown bit refused
- **WHEN** a v3 file sets flag bit 6
- **THEN** the file is refused whole with the reason and the run stays stock

### Requirement: World entries can be turned off
`textures.world` (env `RECOMP_TEXTURES_WORLD`, `"on"` or `"off"`, default `"on"`) SHALL switch the pack's `WORLD` entries off and on like `textures.font` and `textures.text`: read with or without a pack, in the pack log line, an item of the menu's Pack page, applied at the next flip when changed from the menu, with a turned-off entry's miss tagged ` (world off)`. The golden harness SHALL fail a run whose log shows `textures.font`, `textures.text` or `textures.world` other than `on` without `--allow-enhance`, and the CLI's `ENHANCE_STOCK` and `TOOLKIT_ENHANCE_KEYS` SHALL both name the three keys.

#### Scenario: World off, HUD on
- **WHEN** `@stage1` runs with a pack holding world and ui entries and `RECOMP_TEXTURES_WORLD=off`
- **THEN** the world textures go up from the guest, tagged in the `tex_pack` trace, and the HUD entries still hit

### Requirement: Texture dump and magnification trace
With the debug entry `RECOMP_DEBUG=tex_dump=<dir>` (no configuration key and no variable of its own; it lives in the kernel library, so a build without the enhancements layer has it too), the Metal and D3D11 backends SHALL write each uploaded texture once per hash as `<hash>.xtd` (a 64-byte header, then the decoded A8R8G8B8 levels) and `<hash>.json` (hash, width, height, levels, pitch, format, swizzled/linear/dxt, palette, wrap modes, filters, first flip, upload count), SHALL skip stages bound to a render target and addresses whose hash changed more than 8 times (marking the files already written as volatile), and SHALL print a `[TEXDUMP]` summary every 600 flips and at exit. With `RECOMP_TRACE=tex_mag`, the backends SHALL record per hash the largest on-screen magnification (host pixels per source texel) seen, from the unclamped LOD the fragment shader computes on a subsample of pixels (derivatives taken in uniform control flow, an atomic max of a biased unsigned encoding into one buffer with a slot per draw and stage, read back when the command buffer completes or at the frame's end, never per draw; divided by the entry's scale when a pack entry was bound; occluded fragments counted and said) and, for pre-transformed batches, from the vertices, and SHALL write it into the sidecars and the summary with the run's render scale. Without the entry or the trace, no file is written, the generated shader text is byte-identical to the current output, and the CPU rasteriser says once that it does not dump.

#### Scenario: Dump of a scene
- **WHEN** `@stage1` runs on Metal with the directory set
- **THEN** one `.xtd` and one `.json` exist per distinct packable hash drawn, the movie frames of the attract are counted as volatile and not kept, render-target stages are counted and not written, and the frames equal a stock run's

#### Scenario: Magnification recorded
- **WHEN** the same run has `RECOMP_TRACE=tex_mag` at `render.scale = 2`
- **THEN** a HUD piece drawn 1:1 reads `mag_max` near 2.0 and `mag_scale1` near 1.0, and a close wall reads higher than a distant one

#### Scenario: Stock unchanged
- **WHEN** the goldens run with neither the entry nor the trace, and the shader generators run on their fixture set
- **THEN** the generated HLSL and MSL text equals the current output byte for byte and every golden verdict is the same
