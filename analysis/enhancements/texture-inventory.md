# Texture inventory: the dump half

This is the measured inventory for task 0.1 of the `texture-upscale` change,
taken with the per-hash texture dump of task 1.5
(`RECOMP_DEBUG=tex_dump=<dir>`, toolkit `feat/tex-dump`). It covers
BLiNX 2 only. Still open:

- the magnification trace (1.5a);
- the b3 equivalent;
- the pack-byte and VRAM estimates of task 0.4.

This document holds names, hashes, sizes, counts and classes only. The
dumps hold game texels: they stay on the machines that made them and are
never committed, attached or published.

## Runs

- **Build:** the per-hash dump of task 1.5 (toolkit `nv2a_tex_dump`), as
  first written; later changes touch only its limits and error paths.
- **Settings:** the golden base env (stock resolution and frame rate,
  `RECOMP_MENU=0`), plus the dump directory.
- **Hosts:**
  - D3D11: native Windows on the PC. Each scenario ran at render scale 1
    and 3.
  - Metal: the Mac at scale 1. Its dumps cross-check the hashes.
- **Scenarios:**
  - `@stage1`: 105 s, the first level with the HUD.
  - `@attract`: 75 s, the title and attract demos.
  - `@story-hub`: 100 s, on a fresh save.

## Classes

- **Class:** `ui`, `font` or `text` when the hash is an entry of the
  current HUD pack (`dist/enhance/hud/hud.pack`, 427 entries), and `world`
  otherwise. `linear` stands apart: a linear texture gets a sidecar but
  no texels.
- **Facts** (design D2):
  - `palette`: P8;
  - `normal`: G8B8;
  - `data`: a texture with one side of 1, or no side over 8;
  - `alpha`: a format with an alpha channel;
  - `mipped`: more than one level.

## Totals per scenario (D3D11, scale 1)

| scenario | textures | ui | font | text | world | linear | texels (all levels) | volatile addresses |
|---|---|---|---|---|---|---|---|---|
| `@attract` | 284 | 0 | 0 | 0 | 273 | 11 | 5,617,513 | 1 |
| `@stage1` | 297 | 7 | 1 | 5 | 275 | 9 | 5,915,584 | 1 |
| `@story-hub` | 219 | 5 | 1 | 0 | 203 | 10 | 6,438,905 | 5 |

The three scenarios together hold 489 distinct hashes over both scales:

- world: 459;
- ui: 12;
- text: 5;
- font: 1;
- linear: 12.

That is 12.36M texels with every level counted (world 12.07M). Only 41
hashes appear in all three scenarios. Only 18 of the HUD pack's 427
entries were bound in these runs: the pack covers the game's whole
archive, while these runs see one level and the hub.

The raw A8R8G8B8 size of the world set gives an upper bound before any
compression:

| scale | raw size |
|---|---|
| 1x | 48 MB |
| 2x | 193 MB |
| 3x | 435 MB |
| 4x | 772 MB |

The BC1/BC3 pack bytes per preset are task 0.4.

## Per class and format (D3D11, scale 1)

### `@stage1`

| class | format | textures | mipped | levels | texels |
|---|---|---|---|---|---|
| ui | DXT3 | 7 | 0 | 7 | 51,200 |
| font | DXT5 | 1 | 0 | 1 | 65,536 |
| text | DXT3 | 5 | 0 | 5 | 118,784 |
| world | DXT1 | 190 | 110 | 888 | 4,235,627 |
| world | DXT3 | 35 | 14 | 122 | 624,640 |
| world | DXT5 | 6 | 0 | 6 | 120,832 |
| world | G8B8 | 17 | 17 | 51 | 365,568 |
| world | P8 | 18 | 0 | 18 | 307,200 |
| world | A4R4G4B4 | 7 | 0 | 7 | 25,600 |
| world | A8R8G8B8 | 2 | 1 | 6 | 597 |
| linear | LIN_YUY2 | 9 | 0 | 9 | (sidecar only) |

The world facts in `@stage1`:

- palette: 18;
- normal: 17;
- alpha: 50;
- mipped: 142;
- data: 1.

### `@attract`

| class | format | textures | mipped | levels | texels |
|---|---|---|---|---|---|
| world | DXT1 | 192 | 113 | 910 | 4,264,554 |
| world | DXT3 | 34 | 18 | 150 | 516,778 |
| world | DXT5 | 5 | 0 | 5 | 116,736 |
| world | G8B8 | 17 | 17 | 51 | 365,568 |
| world | P8 | 18 | 0 | 18 | 307,200 |
| world | A4R4G4B4 | 4 | 0 | 4 | 13,312 |
| world | A8R8G8B8 | 3 | 1 | 7 | 33,365 |
| linear | LIN_YUY2 | 11 | 0 | 11 | (sidecar only) |

### `@story-hub`

| class | format | textures | mipped | levels | texels |
|---|---|---|---|---|---|
| ui | DXT3 | 3 | 0 | 3 | 33,792 |
| ui | DXT5 | 2 | 0 | 2 | 17,408 |
| font | DXT5 | 1 | 0 | 1 | 65,536 |
| world | DXT1 | 65 | 28 | 254 | 2,434,980 |
| world | DXT3 | 48 | 4 | 74 | 1,600,000 |
| world | DXT5 | 7 | 0 | 7 | 332,800 |
| world | P8 | 78 | 0 | 78 | 1,683,456 |
| world | A4R4G4B4 | 2 | 0 | 2 | 8,192 |
| world | A8R8G8B8 | 3 | 1 | 7 | 262,741 |
| linear | LIN_YUY2 | 10 | 0 | 10 | (sidecar only) |

The hub is the palette-heavy scene: 78 P8 textures, with no normal maps.

### Sizes (largest side, world, `@stage1`)

| largest side | 8 | 16 | 32 | 64 | 128 | 256 | 512 | 1024 |
|---|---|---|---|---|---|---|---|---|
| world textures | 1 | 2 | 37 | 77 | 120 | 30 | 7 | 1 |

The hub's world set is larger: 53 at 256, 14 at 512 and 6 at 1024. Every
linear texture is the 1024-wide YUY2 movie or overlay surface.

## Wrap modes and filters

- **Wrap mode does not tell ui from world.** 271 to 273 world textures
  per scenario use wrap/wrap. Every HUD entry (ui, font and text) uses
  wrap/wrap too: the game leaves D3D's default address mode on 2D quads.
  Only 2 world textures and every linear surface use clamp.
- **min filter is `linear_mip_linear` even on one-level textures.** The
  same default applies, so the min filter is no class signal either. The
  class rules have to rest on the hash (pack entry, archive name) and the
  draw. The magnification trace of 1.5a supplies the draw.

## Volatile addresses

The dump marks an address `volatile` once it has seen 8 distinct hashes
there. It then stops writing that address.

| address | size | scenarios | uploads skipped |
|---|---|---|---|
| `0x8039E000` | 1024x512 | all three | 129 (`@stage1`) to 161 (`@attract`) |
| `0x80514000` | 256x128 | `@story-hub` | |
| `0x8051C000` | 128x128 | `@story-hub` | |
| `0x804F8000` | 128x128 | `@story-hub` | |
| `0x804F7000` | 64x64 | `@story-hub` | |

- **`0x8039E000`** is the movie surface.
- **The four hub addresses** are P8 images that the hub rewrites in
  place: 257 uploads skipped over the five addresses in `@story-hub`. Their
  early hashes (the first 8, before the address turned volatile) depend on
  timing: the s1 and s3 runs differ by 12 P8 hashes, at two of these
  addresses and six others, all first seen between flips 1934 and 1991. A pack
  should not carry entries for them.

## Render targets

- **The D3D11 skip counts** of render-target binds (summary at the last
  flip):
  - `@stage1`: 143,465 binds, 5 targets;
  - `@attract`: 89,634 binds, 5 targets;
  - `@story-hub`: 68,204 binds, 4 targets.
- **Metal** skips a similar number per stage1 run, 48k to 82k by the
  time of the summary.
- **These are bind counts, not textures.** The game samples its own
  targets every frame (glow, shadows, the movie copy). The dump skips all
  of them, as designed.

## Render scale 1 vs 3

The texture set does not depend on the render scale: guest textures are
guest data.

| scenario | difference between scale 1 and scale 3 |
|---|---|
| `@stage1` | identical file sets |
| `@attract` | one linear sidecar more at scale 1 (a movie frame) |
| `@story-hub` | the 12 timing-dependent hub P8 hashes above; the counts per class are the same |

Only the render targets grow with the scale (GPU memory, scale 1 to 3):

| scenario | scale 1 | scale 3 |
|---|---|---|
| `@attract` | 47 MiB | 112 MiB |
| `@stage1` | 48 MiB | 113 MiB |
| `@story-hub` | 51 MiB | 140 MiB |

## D3D11 vs Metal

- **The hashes agree across backends.** In `@stage1`, the D3D11 and Metal
  sets differ by one linear sidecar; in `@story-hub`, by 3 files
  (sidecars of the same timing-dependent kind).
- **`@attract` differs by 22 world textures.** The PC run reached
  attract-demo content (first seen at flips 1171 to 2426) that the Metal
  run had not loaded: the attract cycle runs on game time, not flips. The
  Metal per-format table is otherwise the same shape. Metal at scale 1
  saw:
  - `@attract`: 263 textures (251 world);
  - `@stage1`: 299 textures (7 ui, 1 font, 5 text, 275 world);
  - `@story-hub`: 222 textures (5 ui, 1 font, 203 world).

## Cost of the dump

Flips/s, dump off vs on:

| host | scenario | off | on |
|---|---|---|---|
| D3D11, PC | `@stage1`, 105 s | 33.4 (3509 flips) | 33.4 (3506 flips) |
| Metal, Mac | `@stage1` | 34.5 | 34.5 |
| Metal, Mac | `@attract` | 46.5 | 45.4 |
| Metal, Mac | `@story-hub` | 54.2 | 54.2 |

- **The cost is in the noise,** well within the 25% bound. Every texture
  is written once, on its first upload.
- **Dump size:**
  - D3D11, per run: 23 to 26 MB;
  - Metal, per run: 20 to 26 MB;
  - all ten dumps: about 240 MB.
- **Goldens with the dump on:** Metal `@attract`, `@stage1` and
  `@story-hub` all pass. The image is unchanged because the dump only
  reads.

## What this sets

- **The world class is the bulk.** It holds 94% of the hashes and 98% of
  the texels. DXT1 is the largest format: 75% of the world texels in
  `@stage1` and `@attract`, 38% in the hub. A BC1 world path (1.1 to 1.4)
  covers most of the bytes.
- **The HUD seen in play is small:** 18 hashes, 0.29M texels. The
  existing v2 pack already covers them.
- **The hub's P8 set is large (78) and partly volatile.** Its palette
  variants need the palette in the hash, which `tex_hash_pal` already
  includes, and the volatile rule keeps the rewritten images out.
- **Wrap mode and min filter carry no class signal.** The class rules have
  to rest on the pack, the archive name and the magnification trace.
