## Context

Spec written by the reviewer on 2026-10-07 against cat `885d62f`, toolkit
`posix-host/portability` `a0b9a55` and the CLI `f476bfa`, from the
feasibility spike `analysis/enhancements/hud-typography.md` (branch
`spike/hud-typography` 97bc787) and the user's decisions of 2026-10-06.
No separate spec review is needed.

Facts the design rests on (spike, "What the investigation found"):

- The game loads a `.dds` through `D3DXCreateTextureFromFileInMemoryEx`
  with the size and format from the file. The DDS data block is the guest
  texture byte for byte, so a hash of the file's data block equals the hash
  the backends compute over guest memory.
- D3D11 (`nv2a_pb_d3d11.c`, `tex_bind`/`tex_upload`) and Metal
  (`nv2a_pb_metal.m`) decode every texture to A8R8G8B8 with
  `nv2a_tex_decode` and upload it at the guest size. Both key their cache
  on `(offset, format, size, pitch, palette, levels)` and rehash once per
  flip with `nv2a_tex_hash` (4-lane FNV over the bytes `nv2a_tex_extent`
  gives: for DXT, the packed blocks of every level).
- Swizzled and DXT textures are sampled with normalised UVs, so a
  replacement of another size needs no shader change; linear textures and
  render targets use texel coordinates and are out of scope (they never
  match a pack entry anyway: render targets hash from their own guest
  bytes).
- The Latin HUD font is `media\dds\font_arialnarrow_bold.dds`, 256x256
  DXT5, no mips. It is not a grid (the spike's 16x16-cell reading was
  wrong): ten bands of ink rows, the six ASCII rows at a 24-px pitch and
  four Latin-1 rows at ~28, each a string of glyphs packed left to right
  with 1-3 px gaps, cap height 18 px. The glyph order is the game's own
  (`@` is drawn as `©`, `^` as an arrow icon, the Latin-1 rows a custom
  subset) and is a game constant (`font_rows`). White glyphs with the
  shape in alpha, tinted by the vertex colour (the stage-1 HUD draws it
  blue with a dark shadow pass). The advance table was not located, so
  glyph metrics must come from the stock atlas itself.
- `IPK1` archives: `.iph` index (`"IPK1"`, u32 alignment, u32 count, u32
  total; 80-byte entries `name[64]`, u32 flags (1 = LZSS), u32 stored
  size, u32 offset, u32 uncompressed size) and `.ipk` data; Okumura LZSS
  (4096-byte ring, write pointer at 4096-18, 18-byte max match, flag bit
  set = literal).

## Goals / Non-Goals

Goals: a pack that the owner builds from their own dump in one command, a
runtime swap that costs nothing when no pack is configured, agreement
between Metal and D3D11, synthetic-only tests, and no path by which a pack
or a game-derived image enters a repository.

Non-goals: see the proposal. Also not here: a pack browser or hot reload;
packs for Burnout 3 (the command is generic, the set is per game).

## Decisions

### D1. Runtime swap at upload, keyed by the hash the cache computes (toolkit)

Both GPU backends get the same four-line change in `tex_upload`: the
caller passes the texel hash it has (or computes) for the entry, and if a
pack is loaded and holds that hash, the texture is created at the pack
entry's size and level count and filled from the pack's texels instead of
`nv2a_tex_decode`'s. Everything else (cache key, LRU, rehash per flip,
samplers, UVs) is untouched. The hash passed is the plain
`nv2a_tex_hash` of the guest bytes; the palette fold for P8 is not in the
pack's key, so P8 textures never match (none in the UI set; documented).

Why upload, not draw: uploads happen on a miss or a changed hash, draws
every batch. Why the existing hash: the pack is built offline from the
DDS bytes with the same function, so no runtime tracing and no name
mapping is needed.

Cost at stock: one load of the pack's entry count per upload
(`nv2a_tex_pack_count()`), the same shape as `nv2a_host_render_scale()`
in the target allocator. No pack, no further statement runs.

The reader lives in the kernel library (`src/kernel/nv2a_tex_pack.c`,
beside `nv2a_backend_common.c`) because the backends never link the
enhancements layer; the layer only resolves the path and calls
`nv2a_tex_pack_load`. This is the `nv2a_host_opts` pattern.

Metal's `tex_bind` today uploads before it hashes on a miss; it is
reordered to hash first (the hash is needed either way), which D3D11
already does.

The CPU rasteriser samples guest memory through its own texel cache and
has no decoded host copy to replace. It logs
`[ENHANCE] textures.pack ignored: the CPU rasteriser samples guest memory`
once, where it reports `render.scale` ignored.

### D2. Pack file format: one raw file, lazy reads (toolkit)

`hud.pack` is one little-endian file:

```
header (32 bytes)   "XRTP", u32 version = 1, u32 count, u32 scale,
                    u64 index offset, u64 reserved (0)
index               count entries of 32 bytes, sorted by hash:
                    u64 hash, u32 width, u32 height, u32 levels, u32 flags (0),
                    u64 payload offset
payload             per entry, every level packed (level 0 first), one
                    u32 A8R8G8B8 texel per pixel: the bytes `nv2a_tex_decode`
                    produces and the backends upload as BGRA8
```

The reader maps the index at load and reads an entry's texels on first
use (`nv2a_tex_pack_texels`), caching them for the process; a 4x HUD set
is ~50 MB of texels and the live subset is what is read. It validates the
magic, version, count, every entry's bounds against the file size, and
the sort order; a bad pack is refused whole with one line and the run
stays stock.

Why not PNG: the toolkit's runtime has no image decoder and upstream's
rule is no external dependencies; `stb_image` would be the first vendored
library in the runtime for one feature. Why not per-entry files: one file
is one `fopen`, one index, and one path in `enhance.toml`. Why not DXT in
the pack: the backends upload BGRA8 everywhere; a BC path is a later VRAM
optimisation (noted in the spike), and a 4x pack of the HUD set is well
under 200 MB resident.

A human-readable `hud-pack.toml` is written beside the pack by the CLI:
tool version, scale, kernel name, the dump's XBE sha256, the font file's
sha256 if one was used, and per entry the archive, the entry name, the
hash and the sizes. The runtime never reads it. It names game files but
holds no game bytes; it stays with the pack, which is never distributed.

### D3. The key: `textures.pack` (toolkit, enhancements layer)

`enhance.toml` `[textures] pack = "<path>"`, env `RECOMP_TEXTURES_PACK`
(config tier, `RECOMP_ENV_ENHANCE_KEYS`, naming rule `RECOMP_` + key).
Default unset: stock. A relative path is resolved against the directory
`xbox_enhance_init` was given (the executable's directory, the same root
as `enhance.toml`), so a bundle can name `enhance/hud.pack`. The layer
logs one line after the settings line:

```
[ENHANCE] textures.pack=none
[ENHANCE] textures.pack=enhance/hud.pack (41 entries, scale 4)
```

or, when the file cannot be read or is invalid,
`[ENHANCE] textures.pack=<path>: <reason>; no pack` and the run stays
stock. The golden harness (`xboxrecomp_cli.golden.ENHANCE_STOCK`) learns
the key with stock value `none`, so a run with a pack fails as a golden
unless `--allow-enhance textures.pack=<path>` names it. The documented
`[ENHANCE] render.scale=...` line is unchanged, so every existing check
and scenario holds.

### D4. The scaler: an integer xBR kernel in pure Python (CLI)

`xboxrecomp_cli.enhance.scaler` implements Hyllian's xBR edge-directed
kernel (the family the user named: xBR, xBRZ, ScaleFX are its
descendants) for 2x and 4x, in integer arithmetic only: the colour
distance is the weighted YUV distance of the reference shader scaled to
integers, edge decisions compare integer sums, and the blends are fixed
ratios (1/2, 1/4, 3/4 of the 4x kernel) computed with integer rounding.
Alpha is a fourth channel: it enters the distance (so a glyph edge against
transparent is an edge) and the blends (so edges stay anti-aliased in
coverage). Two runs on any machine give the same bytes; the hash of every
pack entry's texels is in `hud-pack.toml` so two owners or two hosts can
compare. No float, no threads inside one texture; textures are processed
in parallel with `concurrent.futures` processes, each texture
independent, so the result does not depend on the job count.

Why xBR and not a vendored xBRZ: xBRZ is C++ under GPLv3 and would need a
compiler at `xbr enhance` time or a vendored library in an MIT repo;
Hyllian's xBR is documented as an algorithm and reimplemented here from
its description in ~200 lines of stdlib Python. Why not ImageMagick or
Pillow: the CLI is standard-library only (dev-tooling spec, "Runtime code
stays standard-library"); and the CLI must not grow a runtime dependency
for one command.

Speed: a 256x256 texture at 4x is ~1 s per core in CPython 3.12; the
default set (fonts, HUD pieces, icons, menu pieces: ~300 small textures,
~1.5 Mtexels) takes a minute or two on an 8-core machine. `--only
PATTERN` narrows a run for iteration, `--jobs N` sets the processes.

### D5. The font: rasterised on the owner's machine and fitted to the stock glyphs (CLI)

The font is PT Sans Narrow Bold (OFL 1.1; the operator's pick on
2026-10-07, over Liberation Sans Narrow Bold, whose Narrow cut is
GPLv2 with the font exception). `game.toml` names it by its full name,
`[enhance.hud] font = "PT Sans Narrow Bold"`, and `xbr enhance hud` looks
for that face in the host's font folders (user ones first; a `.ttf`, or a
face of a `.ttc` collection, which is how macOS ships PT Sans in
`/System/Library/Fonts/Supplemental/PTSans.ttc`), reading only each
file's directory and `name` table. `--font` takes a file (in a collection,
the face `game.toml` names) or another installed font's full name. When
no font is found the CLI says what to install and falls back to the xBR
path for the atlas, so a pack without a font still works. The file is not
vendored; the game constant (the face) is in `game.toml`, not the CLI.

The grouping of runs into glyphs (below) lets a glyph take no run, for
two glyphs whose ink touches. That costs the glyph's expected width plus
the widest expected width in the band: at the width alone, PT Sans
Narrow's `[` (narrower than the stock one) went into its `\`'s group.
A glyph left without a run is named on the terminal. With PT Sans the fit
draws 147 of the 148 glyphs; the stock `\` (4x17 px) is too steep for
PT's (10x21) within the 0.4-2.5x stretch and keeps its xBR pixels.

`xboxrecomp_cli.enhance.font` is a TrueType reader (`head`, `hhea`,
`hmtx`, `maxp`, `loca`, `glyf` simple and composite glyphs, `cmap`
formats 4 and 12) and a scanline rasteriser: quadratic contours flattened
to segments, non-zero winding, 4x4 supersampling into 8-bit coverage. No
hinting; at 72-px cap heights it is not needed.

Fitting: the game lays out text from a table this spike did not find, and
the stock atlas stays in guest memory (the swap is host-side), so metrics
are never read from the pack. What must match is where ink sits in the
atlas. The CLI measures the stock atlas (decoded from the owner's own
dump at generation time): the bands of ink rows from the alpha projection
(one per `font_rows` string, else the command refuses); per band the
column runs of ink, a run that holds several runs below the band's accent
zone (touching accents, a `1` whose flag reaches the `0` before it) split
at the column with the least ink between them; the runs grouped, in
order, into the string's glyphs by the dynamic programme that minimises
the total difference between each group's width and the font's own ink
width for that glyph (so `"` is two runs and one glyph, and a run the
string does not explain is left over); per glyph the ink box (alpha
threshold 64) inside its slot (the band's rows between the midpoints to
its neighbours); per band the baseline (the most common bottom edge of
its capitals and digits, else of every glyph) and the cap height (of its
unaccented capitals, else the atlas-wide one). It then renders each glyph
at the size whose cap height is the band's times the scale, measures its
ink, and draws it again condensed or widened and shortened or lengthened
so its ink box is exactly the stock ink box times the scale, placed
there. The second pass is what keeps an accented capital's accent inside
its band (the font's accents sit higher than the stock ones) and gives
every glyph the stock width, which is what the game's layout expects. A
glyph the font lacks, one the fit cannot match (a stretch outside 0.4-2.5x,
reported), and one written as U+FFFD in `font_rows` (an icon the game
draws for that code, such as the arrow at `^`) keep the xBR-upscaled
stock pixels. Glyphs are white with the coverage in alpha, as the stock
atlas is, so the vertex-colour tint and the shadow pass look as they do
today.

Layout facts are game constants in `game.toml` `[enhance.hud]`:
`font_atlas` (the entry name) and `font_rows` (one string per band, the
glyphs in atlas order, spaces ignored, read off the dump). The CLI has no
BLiNX 2 knowledge.

The Century Gothic atlas has no metric-compatible free font and goes
through the xBR path like any other texture.

### D6. The commands (CLI, game-agnostic)

`xbr enhance hud [--scale 2|4] [--out DIR] [--font PATH] [--jobs N]
[--only PATTERN]... [--list]`:

1. reads `game.toml` `[enhance.hud]`: `archives` (basenames of the `IPK1`
   archives, under `data.game_files`), `textures` (fnmatch patterns over
   entry names with `/` separators, case-insensitive), `scale` (the
   default, 4), and the font keys of D5;
2. reads each archive's index (read-only, the dump is never written),
   decodes the selected entries (LZSS where flagged), parses the DDS
   header (DXT1, DXT3, DXT5; others and mip chains are skipped with a
   line), decodes DXT to RGBA, and hashes the data block with
   `nv2a_tex_hash` (the `--list` output ends here);
3. upscales every texture (D4), rasterises the atlas when a font is given
   (D5), and writes `hud.pack` and `hud-pack.toml` to `--out` (default
   `dist/enhance/hud/`, under the gitignored `dist/`).

`xbr package <target> --hud-pack [DIR]` copies `DIR/hud.pack` (default
`dist/enhance/hud/hud.pack`) into the payload as `enhance/hud.pack`,
appends `[textures] pack = "enhance/hud.pack"` (macOS:
`"../Resources/enhance/hud.pack"`, since the executable is in
`Contents/MacOS` and the payload in `Contents/Resources`) to the staged
`enhance.toml.default`, and records `enhance.hud_pack = {sha256, scale,
entries}` in `manifest.json`. Without the flag the bundle is what it is
today. The flag is the opt-in: the owner asked for the pack in their own
bundle, so that bundle plays with it on; the stock keys in the same file
stay at stock and the owner can comment the line out.

### D7. Legal boundaries in code

- `dist/` is already gitignored in cat; `*.pack` is added so a pack placed
  anywhere else in the tree cannot be committed, and `enhance/` for a
  pack dir dropped beside a build. The CLI's `scripts/audit-public.sh`
  gains `pack` in its data-extension list.
- Tests build their own `IPK1` archives, DDS files (hand-encoded DXT
  blocks), fonts (a minimal TrueType with a square and a triangle glyph
  written by the test) and packs in temp dirs. `tests/testdata` gains no
  binary.
- The manifest in the bundle records the pack's sha256, scale and entry
  count only; `private_leaks` still checks the manifest text.
- Nothing in the three repositories holds a decoded texture, a frame or a
  pack. Verification frames go to `xbox-recomp/runs/hudpack/`.

### D8. Backends agree

Metal and D3D11 get the identical hook (D1), on this branch, in the same
commit. Metal is verified on the Mac; the D3D11 file does not compile on
the Mac (WIN32-only), so its verification is the Proton task list in
`tasks.md` section 7, to run when the orchestrator sends "go". The CPU
path's "ignored" line is the recorded difference.

## Risks / Trade-offs

- **Alpha-test edges.** DXT3's 4-bit alpha and DXT1's 1-bit alpha become
  smooth 8-bit edges after xBR; a combiner that assumed hard alpha may
  show soft fringes. Checked on the stage-1 HUD on Metal; the Proton task
  covers D3D11.
- **Glyph fit.** If the run grouping misreads a band (a glyph split
  into runs the font's widths do not explain), the glyph keeps its stock
  pixels and the command says so, since every drawn glyph is fitted to
  the stock ink box the group gave it. The verification dumps `Time:` and
  the name plate, which cover rows 0-5; every row is checked on atlas
  crops read locally (all 148 glyphs of the BLiNX 2 atlas fit).
- **Pure-Python speed.** Minutes, not seconds, for the default set.
  Acceptable for a one-off owner step; `--only` and `--jobs` exist, and a
  future native helper can keep the same output (the kernel is integer).
- **Memory.** Texels are read lazily and kept; the whole HUD set at 4x is
  ~50 MB. Acceptable on every target.
- **A stale pack.** A pack from another dump or an older set simply
  misses (hash keyed), and the log's entry count and `hud-pack.toml`'s
  dump sha say why.

## Migration Plan

1. Toolkit: reader, key, hooks, ctest, docs. Stock goldens on Metal.
2. CLI: archive reader, DDS, hash, scaler, font, pack writer, command,
   package flag, golden refusal, tests, audit.
3. Game: `game.toml` table, env doc row, default config comment,
   gitignore, packaging doc.
4. Mac verification with a local pack in `runs/hudpack/`.
5. Proton: D3D11 verification (tasks 7.x) when the Linux/Proton host is free.
Rollback: the key defaults to none and the flag defaults off; removing a
pack file returns a bundle to stock.

## Open Questions

None blocking. Two choices for the user, made here and reversible:
- the bundle made with `--hud-pack` plays with the pack on (D6);
- the default set is fonts, HUD, icons and menu pieces from `media`
  (`game.toml`), not the per-language text strips.
