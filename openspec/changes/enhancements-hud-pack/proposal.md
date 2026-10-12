# Change: HUD texture pack and HUD font (enhancements layer)

## Why

At 2x and 3x `render.scale` the 3D scene gets sharper but the HUD does not:
the life bar, the radar, the counters and the 18-px font glyphs are DXT
textures sampled with normalised UVs, so the backends magnify them
bilinearly and they are the blurriest thing on screen. The feasibility
spike (`analysis/enhancements/hud-typography.md`, `spike/hud-typography`
97bc787) found that the backends already hash every uploaded texture
(`nv2a_tex_hash`, the per-flip change check), that the HUD and UI set is
DXT with no mip chains (40 textures in a stage-1 run), and that the Latin
HUD font is one 256x256 atlas (`font_arialnarrow_bold.dds`) sampled with
normalised UVs, so a larger atlas with its glyphs in the same places is a
drop-in. (The spike read it as a 16x16 grid of cells; the implementation
found ten rows of proportionally packed glyphs, design D5.)

The user decided (2026-10-06): 4x by default; an xBRZ-class deterministic
scaler, never a CNN; a narrow sans rasterised on the
owner's machine onto the stock atlas's layout; the CPU path ignores the pack;
an `xbr enhance hud` command plus an `xbr package` flag that puts the pack
in the owner's private bundle. The font was Liberation Sans Narrow Bold
until the operator picked PT Sans Narrow Bold (OFL 1.1) on 2026-10-07
(BLX-29): Liberation's Narrow cut is GPLv2 with the font exception, not OFL.

## What changes

- **Toolkit** (`posix-host/portability`, upstream-neutral and off by
  default): a texture-pack reader in the kernel library
  (`nv2a_tex_pack.c`), one lookup in `tex_upload` of the Metal and D3D11
  backends keyed by the hash `tex_bind` already computes, the
  `textures.pack` key (env `RECOMP_TEXTURES_PACK`) read by the
  enhancements layer, a "pack ignored" line on the CPU rasteriser, a
  standalone ctest for the reader and the lookup, and the pack format doc.
  It is meant for upstream later as part of the enhancements layer, not
  the core.
- **CLI** (`xboxrecomp-cli`, public, game-agnostic): `xbr enhance hud`
  reads the game's `IPK1` archives (LZSS, DDS), selects the UI set from
  `game.toml`, upscales each texture with a deterministic integer xBR
  kernel, rasterises the Latin atlas from a font file the owner points at,
  and writes one pack file plus a manifest into `dist/enhance/hud/`.
  `xbr package --hud-pack` copies that pack into the bundle and enables
  the key in the bundle's `enhance.toml.default`. The golden check
  refuses a run whose log shows a pack. Tests use synthetic archives,
  textures and a synthetic font built in the test; no game bytes.
- **Game** (`cat`): the `[enhance.hud]` table in `game.toml` (archives,
  texture name patterns, the atlas name and its rows of glyphs,
  the default scale), the `docs/env.md` row, a commented `[textures]`
  section in `packaging/enhance.toml.default`, `.gitignore` for packs,
  and the packaging doc.

## Backends, hosts and goldens

- Metal and D3D11 take the same hook, in the same place; both are in code
  on this branch. Metal is verified on the Mac with a locally generated
  pack and frame dumps. D3D11 is compiled on the Mac only where the file
  compiles there (it does not: `nv2a_pb_d3d11.c` is WIN32-only), so its
  verification under Proton is an open task for the Linux/Proton queue.
- The CPU rasteriser samples guest memory and cannot use a host pack; it
  logs `[ENHANCE] textures.pack ignored` once, like `render.scale`.
- Goldens are unaffected: `textures.pack` defaults to none, the golden
  configuration pins `RECOMP_ENHANCE_CONFIG=none`, and the harness fails a
  run whose log reports a pack. The stock Metal goldens are re-run on this
  branch with the key unset.

## Legal

The owner makes a pack locally from their own dump. A pack is never
distributed and never committed: it lives under `dist/` (gitignored) or
wherever `--out` points, the manifest written beside it names archive
entries and hashes only, and the public-push audit stays clean because the
repositories carry only code, synthetic fixtures and documentation.
In-game screenshots may show a pack; standalone pack images may not. The
font is installed by the owner (macOS ships PT Sans) and found by the
name `game.toml` gives it, or pointed to with `--font`; it is not
vendored. If it is ever vendored, its OFL licence file comes with it and
`NOTICE` names it.

## Non-goals

- Upscaling world textures (`--set all` of the spike) and mip chains: the
  pack format carries a level count so a later change can add them, the
  command does not.
- The Century Gothic atlas: it goes through the xBR path like any other
  texture; there is no metric-compatible free font.
- Japanese text and dialogue strips: pre-rendered, upscaled only if their
  names are added to the set; not in the default set (926 strips per
  language would take minutes to upscale in pure Python and the gain is
  small).
- A runtime font rasteriser (spike option b), a text-draw hook (option c),
  a recompilation-time archive rewrite, and BC-compressed uploads.
