# Design: texture-upscale

## Context

Read on cat `main` 51d980a, toolkit `posix-host/portability` 6f34a1c3 and
the CLI `main` 5cdddb4 (v0.9.0), with read-only commands.

**What exists.** The CLI's `enhance/` package (2,568 lines, stdlib only):
`ipk.py` (IPK1 + LZSS), `xpr.py` (MIX/XPR0), `dds.py` (DXT1/3/5, with
`extent` over a chain), `texhash.py` (the runtime's FNV), `scaler.py`
(integer xBR lv2, 2x and 4x), `bc3.py` (integer DXT5), `font.py`,
`atlas.py`, `pack.py` (XRTP v2 writer) and `hud.py` (`xbr enhance hud`:
select by `[enhance.hud]` globs, skip non-DXT, skip chains, skip over
`max_texels`, assign kinds art/font/text, upscale in processes, write).
The toolkit's `nv2a_tex_pack.c` reads v1 and v2 (kinds 0-2, `BC3`), looks
an upload's hash up with an aspect check, and both `tex_make`s already
create a host texture with the entry's level count and upload each level
(BGRA8 or BC3). `textures.font` and `textures.text` switch kinds off live;
a miss ring and `RECOMP_TRACE=tex_pack` list what a pack lacks. Pack
texels are read on first use and kept for the process.

**What a whole-game pack runs into**, from the code:

- v2 refuses kind 3 and any flag bit beyond `BC3`, so a world kind or a
  BC1 payload is a new version.
- The runtime hashes guest memory as the GPU holds it: for DXT the file's
  block data (so an archive build matches); for an uncompressed texture
  the swizzled bytes, which D3DX produces at load, so an archive build
  must swizzle before hashing; for P8 the palette is folded in
  (`nv2a_pb_metal.m:1320`); a linear texture hashes `pitch*(h-1)+w*bpp`.
- A linear (rect) texture's texel coordinates are turned into normalised
  ones in the shader by `tex_scale = 1 / guest size`
  (`nv2a_backend_common.c:364`), so a larger replacement samples
  correctly; `texture-pack.md`'s "should not be put in a pack" is stricter
  than the code. What a linear texture *is* in these games (movie frames,
  CPU-written surfaces) is the reason to leave it out by default, not the
  coordinates.
- A stage that aliases a render target never reaches the hash path
  (`rt_texture` binds the target), so render targets can never match a
  pack; a CPU-written texture rehashes every flip and would match once.
- The texture cache keys on `(offset, color, w, h, pitch, palette, levels)`
  and re-uploads on a hash change; nothing in it needs to change.
- Pure Python xBR is ~1 s per 256x256 at 4x per core; BC3 encode is of the
  same order. A whole game is thousands of textures.

**Measured:** the HUD set is 427 entries, 158.8 MB at 4x
(267 art 140 MB raw, 1 font, 159 text 14 MB BC3 at 2x). The 1024x512
backgrounds left out would be 32 MB each raw at 4x, 4 MB in BC1.

## Goals / Non-Goals

Goals: every packable texture of a game reachable; the owner chooses the
upscaler per class from a GUI, registers their own tool or service, sets
coverage from HUD-only to everything (or lets a magnification trace
propose it), previews on real textures at the render scale they play at,
and builds a reproducible pack when every upscaler is built in; the
wizard offers the presets with honest estimates; the runtime loads the
result the same way on Metal and D3D11; nothing is distributed.

Non-goals: see the proposal. Also: no change to how the runtime keys
textures, no GPU-side upscaling at run time (a pack is pre-computed; a
runtime shader upscaler is a different feature with different limits),
no sampler feedback APIs (D3D12/Metal 3 only).

## Decisions

### D1. Two feeders, one inventory, joined on the hash

The CLI today reaches textures only through one game's archive formats.
A game-agnostic feature cannot depend on a reader per game, and no reader
sees what a game composes in memory. The design takes the emulator
convention (Dolphin, PCSX2, Azahar: dump every texture the game draws
under its hash, replace by that name) and keeps the archive path for
completeness:

- **Runtime dump** (toolkit, both GPU backends, the debug entry
  `RECOMP_DEBUG=tex_dump=<dir>`, like `fb_dump=<prefix>`; no config key
  and no variable of its own; it lives in the kernel library beside
  `nv2a_tex_pack`, so a build without the enhancements layer has it
  too, off unless the entry is set). On every upload (a cache
  miss or a changed hash) while the directory is set, the backend writes
  the texture once per hash: `<hash>.xtd` (a 64-byte header, then the
  decoded A8R8G8B8 levels, exactly what `nv2a_tex_decode` produced and
  what the pack would replace) and `<hash>.json` (hash, w, h, levels,
  pitch, the format id and name, swizzled/linear/dxt, palette, wrap u/v,
  min/mag filters, first-seen flip, upload count). Three things are not
  written and are counted instead: stages bound to a render target (they
  never hash), addresses whose hash changed more than 8 times (`volatile`:
  CPU-written surfaces, movie frames; the counter is per `(offset, size)`
  and the files already written for that address are marked volatile in
  a final `volatile.json`), and uploads over `NV2A_TEX_PACK_MAX_DIM`. The
  trace of D14 (magnification) writes into the same sidecar. A
  `[TEXDUMP]` line every 600 flips and at exit gives the counts. The CPU
  backend says once that it does not dump. Cost: one file write per new
  hash, on the upload path; measured in 1.8 and acceptable for a trace
  run (the dump is never on in play).
- **Archive feeders** (CLI, `enhance/sources/`): the readers the CLI has
  (`archive`: IPK1 with DDS and MIX/XPR0 entries), `loose` (`.dds`,
  `.xpr`, `.xbx` files under globs of the dump), and `hook` (a Python
  script in the game repo, run the way `pipeline.names_hooks` scripts
  are, that prints an index and serves entries by name; this is where a
  game's own container format lives, never in the CLI). The feeder
  reproduces the guest bytes before hashing, and the dump stays the
  authority on what the runtime actually hashed: DXT as the file's block
  data; uncompressed DDS data through a port of `d3d8_swizzle` (checked
  against the dump in 2.2's test with a vector the toolkit shares);
  XPR0 data as it is, since an XPR resource is already in GPU layout
  (`xpr.py` hashes it so today; it is never swizzled twice); DDS decoded
  by the rules the game's D3DX load uses and nothing else (no format
  change, no generated levels: a file with one level stays one level).
  The runtime hashes only the levels it binds: `nv2a_stage_decode` clamps
  the count to `MAX_LOD + 1` and `no_mips` drops the chain, so a mipped
  file gets **one hash per level prefix** (1, 2, ... L levels) and the
  inventory keeps whichever the dump confirms. P8 is **dump only**: the
  runtime folds the palette into the hash (`tex_hash_pal`,
  `nv2a_pb_metal.m:1316`), the archive has no way to know which palette
  a frame bound, and `nv2a_tex_pack.h`'s "P8 never matches" comment and
  the miss record's `candidate` rule (P8 and mipped entries are
  candidates now) are updated in 1.1.
- **The join.** `inventory.json` under `dist/enhance/` keys by hash. An
  archive entry gives a name, a source and the bytes; a dump entry gives
  the authoritative hash, the runtime facts (wrap, filters, use count,
  magnification) and the decoded texels. Both present: one entry with a
  name and facts. Archive only: `not seen` (unused in the runs made, or
  a hash the feeder got wrong; both are listed). Dump only: `unnamed`
  (composed at run time, a format no feeder reproduces, or no feeder for
  this game) and still packable from the dumped texels. Complete
  coverage is the union; a game with no reader (b3 at first) runs on the
  dump alone and covers what was played, and the `[TEXPACK] miss` trace
  after a session says what a longer dump would add.

Weighed and rejected: a reader per game in the CLI (not game-agnostic;
the user's rule), the dump alone (misses what was not played, and loses
the names the GUI groups by), hashing archive files without the swizzle
port (the uncompressed set would silently never match).

### D2. Classes, sub-classes and the per-class defaults

Every inventory entry gets one **class** that the runtime can switch off
(the pack kind) and zero or more build-time **facts** that pick its
treatment:

| Class (kind) | How it is decided | Default scale | Default upscaler | Alpha | Edges | Mips | Encode |
|---|---|---|---|---|---|---|---|
| `font` (1) | `[enhance.hud] font_atlas`, or `[enhance.textures.classes] font` patterns | 4 | the atlas fit when the game names a font, else `xbr` (`alpha_edge`) | split | clamp | none | raw |
| `text` (2) | only in one language's archives (see below), `text` patterns | 2 | `xbr` | split | clamp | none | bc3 |
| `ui` (0) | `ui` patterns (cat: today's `[enhance.hud] textures`), or a dump fact: drawn only by pre-transformed (2D) batches | `clamp(R, 2, 4)` | `xbr` | split | clamp | none | raw |
| `world` (3) | everything else that is packable | 2 with `lanczos`; `clamp(R, 2, 3)` with a CNN | `lanczos` built in; a CNN preset when the owner has one | split | the recorded wrap mode | full | auto (bc1 opaque, bc3 with alpha) |

Facts and what they do:

| Fact | From | Effect |
|---|---|---|
| `alpha` | the format has alpha and the texels use it | split handling (D7); `bc3` under `auto`; `binary` for cutouts the owner marks |
| `normal` | bump/env formats (`LIN_G8B8`/`V8U8`, DSDT) or a stage sampled with a BUMPENVMAP mode in the dump | **skipped** by default (a CNN invents slopes; a resampled normal map must be renormalised, which `lanczos` + a renormalise step does when the owner opts a rule in) |
| `data` | `min(w, h) == 1`, or `max(w, h) <= 8`, or sampled point-filtered with no mips at a footprint of 1 texel (D14) | skipped: ramps, lookup tables, gradients read as data |
| `linear` | a linear (rect) format | skipped by default; a rule may include it (D3) |
| `volatile`, `cube` | the dump (D1) | never packable; listed with the reason |
| `rt` | the dump (D1): a hash uploaded at an address and size a stage also sampled as a live target | **skipped** by default, since its texels may be the game's own rendering; a rule may include it (the fact is one sighting, and memory reused for a same-sized target is a false positive). The targets themselves have no hash and can't be entries |
| `palette` | P8 | packable from the dump only; each palette variant is its own entry; the inventory says how many variants a base image has |
| `grid` | a font atlas, or a `ui` texture the owner marks as a sprite sheet | `edges = cells` with the cell size, in the same table (a `cell` with any other `edges` is refused): each cell has its clear texels' colour extended, is padded and is upscaled on its own, so no stroke or colour crosses a cell border |

**Text by language (stricter than the table's first draft).**
An entry is `text` only when every origin it has is in one language's
archive. A language archive also carries shared art, a stage's own
textures copied per language, and that art is not text. On BLiNX 2,
3,707 entries are in `lng_us` alone and are `text`; 1,822 are in
`lng_us` and in another archive too and are not (1,589 `world`, 232
`ui`, 1 `font`).

**Dump facts (review).** Sidecars hold `bump`, `rt` and,
once a draw showed it, `drawn_2d`, rewritten at each summary. `ui` comes
from the patterns, then from `drawn_2d`, but a name the owner gave outranks
what a run saw: a `classes.world` or `[enhance.hud] exclude` match stays
`world` whatever was drawn. `normal` comes from the format, then from `bump`.
2D is a pass-through batch or a program batch at one z and one w, that w a
whole screen layer or, with the depth test off, a near layer (Burnout 3's
menus at w 0.1). A fact that is no real bool reads as absent and is counted in
the report. A stage bound to a render target has no hash, so a target is never
an entry: it is listed in the dump's `render_targets.json`, and `rt` marks a
hash uploaded at the address and size of a target a stage *sampled*, so a
write-back only rendered to and read as a plain texture is not flagged. The
CLI does not read `render_targets.json`, by design: a row has no hash, so no
pack entry could match it, and what it can say about a texture the sidecar's
`rt` already says; it stays a diagnostic of the run. Dumps from before the tracker item
have none of the three, which reads as unknown. The limits of these facts
(draw merging, software-transformed 3D, backends that differ) are in the
toolkit's `docs/formats/texture-dump.md`.

The defaults are the spike's to confirm (0.4): the table is what the
GUI shows and the owner edits. The tracker item (2026-11-01, "Measured" below)
confirmed the upscaler per class at 3x and set **the default-scale
rule**: with `R` the config's `render_scale`, a class whose cell reads
`clamp(R, 2, 4)` defaults to `R` bounded to 2..4 (2 at `R = 1` and 2,
3 at `R = 3`, 4 at `R >= 4`); `font` stays 4 (the atlas fit) and
`text` stays 2 (it is the largest class; 3 is the owner's choice where
the budget allows). The reason: a 4x entry drawn at render scale 3
holds 16 texels per source texel where the screen shows 9, so 7/16
(about 44%) of its texels only feed minification. World keeps
`lanczos` at 2x by default because it needs nothing installed, is
reproducible, and halves the pack of a 4x choice; picking a CNN for
world (the GUI or `pick`) switches its default scale to `clamp(R, 2,
3)`. World with a CNN is capped at 3 until D14's trace shows a
magnification of 3 or more: in the in-game A/B ("Measured"), a native
4x CNN pack was invisible against 3x even at `R = 4`, for about 78% more
pack bytes and VRAM. `ui`, `font` and `text` keep the rule above. A
scale of 3 needs the fractional sampler shift of D4; until 1.2 lands, a
3x entry is only safe for unmipped textures (`mips = none`). An
unmipped-only world pack puts sharp props beside soft mipped surfaces,
and the mixed sharpness shows up close, so the world CNN preset is worth
offering only once 1.2 lands.

**Coverage presets** are a game's named sets over classes and rules
(`game.toml [enhance.textures.presets]`): `hud` (= today's `[enhance.hud]`
set, cap and no mips: the same entries, scale, encode and payload size as
`enhance hud`, compared with a real pack in "Measured"; its byte equality is
the build's, the test of D8), `ui` (every
`ui`/`font`/`text` entry, no cap), `world` (`ui` plus `world` diffuse),
`all` (everything packable), and `traced` (D14). The wizard offers them
as one choice.

### D3. The exact-size classes, each with its reason

- **Linear (rect) textures.** Sampled with texel coordinates on the
  console; the backends normalise them with `1 / guest size`, so a
  bigger entry samples right. Two reasons keep them out by default: in
  these games they are movie frames and CPU-written surfaces (`volatile`
  catches most), and a linear texture drawn as a unity blit at
  `render.scale > 1` is snapped to guest texel centres by the
  `enhancements` spec's rect rule, so a replacement is read at guest
  rate anyway. A rule may include a linear texture; the runtime needs no
  change, and the preview's render-scale view (D15) shows that it gains
  nothing when drawn 1:1. The rule can only build what has texels: the
  dump writes no `.xtd` for a linear texture (`texels: false`), so one
  with no source named stays skipped as `no_texels`, rule or not, and
  the estimate leaves it out. A linear texture with a source that a
  feeder named can be built from that source.
- **Cube maps.** D3D11's `tex_upload` and Metal's `tex_upload_body`
  both return for a cube before `nv2a_tex_pack_find`, so an entry could
  never be read: excluded as `cube`, and no rule brings one back. Six
  dumps of BLiNX 2 hold none.
- **Render targets.** Bound directly by `rt_texture`, never hashed, the
  content is the game's own frame: excluded, by construction.
- **Dynamic and CPU-written textures.** The hash changes each frame, so
  a pack entry would match one frame at most: excluded as `volatile`.
- **Palettized.** The hash folds the palette: packable from the dump,
  one entry per palette variant (the GUI shows the variant count so a
  32-palette character skin is a conscious choice).
- **Lookup, ramp and data textures, bump/env and normal maps.** Skipped
  by default as `data` and `normal` (D2); a normal-map rule, when opted
  in, resamples with `lanczos` and renormalises each texel.
- **Font atlases on a fixed grid.** The `grid` fact: cells upscaled
  independently, and with a named font the atlas fit of `hud-pack`
  (which already keeps each glyph in its stock box times the scale).

### D4. Mip chains

The runtime already loads an entry with a chain and both backends upload
every level, so this is a CLI change. For a source with `L` levels the
builder upscales level 0 by `s` and regenerates the chain from it by an
integer 2x2 box filter weighted by alpha (premultiplied average so a
cutout's fringe does not darken), `full` down to 1x1 (the default:
`1 + floor(log2(max(w*s, h*s)))` levels, within what the reader allows),
`keep` (the source's `L` levels, the chain ending at `s` x `s` texels; a
far surface then clamps to that level: slight aliasing, smaller files),
or `none` (UI, which the game draws without mips). Consequence the owner
should know: at the same screen footprint the GPU samples `log2(s)`
levels deeper into the new chain, i.e. approximately the box-filtered
upscale, so a distant surface looks as it did and the detail appears
where it is magnified. This is the intended behaviour, and the reason
D14 exists: where nothing is ever magnified, the upscale buys nothing.
**The samplers must follow the entry's chain** (review of the first
draft). Both backends derive mip filtering from the *guest's* level
count and apply `lod_min`/`lod_max` as absolute levels
(`nv2a_pb_metal.m` ~1575-1597: `mip = t->levels > 1 ? filter_mip : 0`,
`lodMinClamp/lodMaxClamp = mip ? t->lod_min/max : 0`;
`nv2a_pb_d3d11.c` ~1954-1958 the same). Left alone, a one-level guest
texture with a full pack chain is sampled without mips and aliases
worse than stock, and on a mipped guest the last `log2(s)` levels of the
new chain can never be reached. The GPU computes the LOD against the
entry's real size, so guest level `k` is entry LOD `k + shift` with
`shift = log2(entry_w / guest_w)`: the entry's LODs below `shift` are
the new detail, reached only at magnification. **The shift is
fractional at 3x** (`log2 3 ≈ 1.585`): both APIs take float clamps
(`lodMinClamp`/`lodMaxClamp`, D3D11 `MinLOD`/`MaxLOD`), so the clamps
below are floats, and the sampler key carries the entry's integer
scale `s` (2, 3 or 4; 1 for stock) rather than the float, which
quantises the shift by construction. A 3x chain's levels fall between
the guest's (guest level `k` is entry LOD `k + 1.585`), so with linear
mip filtering the GPU blends two entry levels where the guest read one;
nearest-level filtering picks the closer. Toolkit task 1.2
therefore, for pack entries only: shifts **`lod_max`** by `+shift`
(the far end follows the guest's clamp into the longer chain); leaves
**`lod_min` at 0** when the guest's is 0, shifting it by `+shift` only
when the guest sets it above 0 (a guest that already clamps away its
own level 0 keeps that intent, in entry levels); and for a one-level
guest with a pack chain turns mip filtering on (nearest-level) with
`min 0, max shift` (the full chain when the entry has one; `max
1.585` at 3x). Shifting
`lod_min` to `shift` would have blocked the upscaled levels outright,
and on a one-level guest left `min = max = shift`, the pack doing
nothing: the first draft's mistake. The shift is part of the sampler
key; stock textures take the unchanged path. The CLI's `ui` default stays
`mips = none`, so UI drawn without mips keeps its look, and the
preview's render-scale view shows the level picked at a footprint. Task
7.4 checks a distant floor and wall against stock.

### D5. Pack v3 and the encoders

v3 keeps the layout of v2 and adds what v2 refuses: kind 3 `WORLD`,
flag bit 5 `XRTP_FLAG_BC1` (8-byte blocks, 1-bit alpha unused: opaque),
and header word +28 `classes` (a bit per kind present, informational).
The reader takes v1, v2 and v3, and validates by version: a v2 file
still refuses kind 3 and bit 5 (`XRTP_KIND_MASK`, `XRTP_FLAGS_KNOWN` are
per version); a v3 file refuses any kind or bit it does not define. The
multiple-of-4 dimension check covers BC1 as it covers BC3. A v3 file
with only art/font/text entries is what today's `enhance hud` writes
from now on (one writer). BC1 uploads natively on both GPUs
(`DXGI_FORMAT_BC1_UNORM`, `MTLPixelFormatBC1_RGBA`; the Metal `s_bc`
probe already gates the BC family). The CLI's BC1 blocks are always the
opaque four-colour form (`c0 > c1`, as `bc3.py` orders them; a test
asserts no generated block decodes a transparent texel). Sizes per source texel at 4x: raw 64 B, BC3 16 B, BC1 8 B; a
1024x512 background is 32 MB raw, 8 MB BC3, 4 MB BC1, plus a third for a
full chain.

The CLI's BC1 encoder is the colour half of `bc3.py` (integer endpoint
fit, deterministic). Encode speed is the build's long pole after a CNN:
the pure path is the reference and the test oracle; an optional
vectorised path (`numpy` when importable, same integer arithmetic, a test
asserts identical blocks) and an external encoder command (the same
template mechanism as D7, for `nvcompress`/`compressonator`/`texconv`
owners already have; blocks then differ, `reproducible: false`) are
offered. BC7 and ASTC are follow-ups: no cheap encoder, and ASTC has no
D3D11 path.

### D6. Budgets: pack size, VRAM, load and lookup, build time

- **Pack size** is the sum over entries of the encoded chain; `estimate`
  prints it per preset, scale and encode; the config's
  `[budget] pack_mb` makes the GUI flag a choice that exceeds it (it does
  not refuse: the owner's disk).
- **VRAM.** Resident host textures are what the backend's cache holds; a
  4x raw entry is 16x the texels of the guest's BGRA8 upload, BC1 2x,
  BC3 4x. The dump's per-hash use counts give a resident-set estimate
  per scene; `[budget] vram_mb` (0, no warning, until the phase 0 spike
  sets it in 0.4) flags a preset above it. The cache's eviction is unchanged; a scene
  over budget evicts and re-uploads, which the `tex_pack` trace shows as
  repeated reads. Pack texels are **released from host memory** once the
  GPU texture exists (1.3): today each entry's buffer is kept for the
  process, which for a whole-game pack would be the pack resident twice.
- **Load and lookup.** The index is 32 bytes per entry, validated once
  (sorted order, bounds) and binary-searched: 10,000 entries are 320 KB
  and 14 probes; `NV2A_TEX_PACK_MAX_ENTRIES` (1M) stays. First use reads
  the entry from the file on the upload thread: a 4x 1024x512 BC1 chain
  is ~5 MB, a few ms on an SSD, once per eviction cycle. A prefetch
  thread is a follow-up if the trace shows stalls; the design keeps the
  lazy read.
- **Build time.** Per texture the costs add: decode, pad, upscale
  (measured by the tracker item in seconds per source megatexel on an M4 Max:
  `xbr` 8.2, the CLI's pure-Python kernel; ncnn tools 1-12; spandrel on
  MPS 0.3-8.3, the CPU 6.5-11x slower; "Measured" below; the spike's
  `lanczos`, `nearest` and `epx` were numpy/Pillow stand-ins and its
  pad, alpha split and down-to-scale were numpy/Pillow outside the
  timed call, so the CLI's pure-Python versions of all of them are
  still to be timed in 3.1, and a CNN's figure grows by a down-to-scale
  over its 16x output), chain, encode (same order as xBR in pure
  Python; timed in 3.4). `estimate` multiplies per-megatexel
  figures from a calibration cache (`build-logs/timings.json`, seeded by
  0.3's CNN rows and 3.1's and 3.4's pure-Python rows, refreshed by
  every build) by the preset's texels, divided by
  the job count `resources` allows, and the wizard shows minutes per
  preset. The built-ins run one texture per process task (deterministic
  whatever the job count, as today); command and service backends run
  batches of a directory per call so a tool's start-up is paid once per
  batch, not per texture.

### D7. The pluggable upscaler interface

`enhance/upscalers/`: a registry of objects with `name`, `kind`
(`builtin | command | http`), `scales`, `alpha`
(`rgba | rgb`), `deterministic`, `batch`, `describe()` (parameters with
types, ranges and defaults for the GUI) and `upscale(images, scale,
params) -> images` over `(w, h, rgba bytes)` tuples.

1. **Built-in** (`nearest`, `xbr` 2/3/4 with `level`, `eq`, `weights`,
   `alpha_edge`; `epx` 2/3/4; `lanczos` fixed-point 3 lobes with an
   integer kernel table; `box`): integer, reproducible across hosts,
   nothing to install, the defaults. The `xbr` kernel is the CLI's own
   integer implementation of Hyllian's algorithm; xBRZ (GPL-3) and
   ScaleFX are not used.
2. **Command** (`[upscaler.<name>] template = "..."`, a local-only key, D8;
   a preset's template ships in the CLI and is chosen by name): a template over
   PNG files in a temporary directory, `{in}`/`{out}` per texture or
   `{in_dir}`/`{out_dir}` per batch, `{scale}`, `{model}`, `{tile}`,
   `{gpu}` (an ncnn tool's `-g` index: `0`, `1`, or `-1` for its CPU
   mode) and `{device}` (the torch plugin's `auto|cuda|mps|cpu`), each
   from the local file per upscaler; the template is `shlex.split` first and the placeholders
   substituted into the resulting argv list, so the tool runs without a
   shell and a texture name or model can never become a command; a
   timeout; the tool's sha256 and `--version`/first line recorded in
   `textures-pack.toml`. The program's `path` and any model directory
   are owner-machine facts and live in the untracked local file (D8). `presets.toml` ships templates,
   never binaries, for the local open-source tools the community uses
   (D16): Real-ESRGAN ncnn-vulkan (`-i -o -s -n -m -g -j -t -f`, MIT; the
   models `realesrgan-x4plus`, `realesrgan-x4plus-anime`,
   `realesr-animevideov3`; the tool's own source names an output by scale only
   for that last model, so the two x4plus models offer 4x alone and only
   `realesr-animevideov3` offers 2-4), waifu2x ncnn-vulkan (`-i -o -n -s
   -t -m -g -j -x -f`, MIT; `-g -1` is its documented CPU mode; scales
   1/2/4/8+), Upscayl's `upscayl-bin` (AGPL-3.0, the same ncnn family; its bundled
   models, or an owner's ncnn model with `-m DIR -n NAME`, whose input
   blob must be named `data`), chaiNNer `chainner run chain.chn --override overrides.json`
   (experimental per its wiki; the owner exports a chain whose input and
   output directory nodes the template overrides), and Real-ESRGAN's
   Python `inference_realesrgan.py -n -i -o -s -t --suffix "" --ext png` (BSD-3;
   the script's source gives `<name>.png` for an empty suffix, it has no
   shebang so `path` must be a wrapper, and no run confirmed it, so the preset
   carries `flag = "unverified..."`), Real-CUGAN
   ncnn-vulkan (MIT; `-n -s -m models-se|models-pro`, native 2/3/4x; on
   macOS the preset runs **one file per process and pads a side under
   128 by the edge**, since the 20220728 build segfaults on wide thin
   inputs such as 512x64 and a directory batch dies with it), and the
   PyTorch plugin of D7.4 (`xbr-upscale-torch upscale --model {model}
   --scale {scale} --in-dir {in_dir} --out-dir {out_dir} --device
   {device} --tile {tile} --dtype fp32`). **Model presets** name a model file the
   owner downloads (homepage, licence, sha256 to expect), never a URL
   the CLI fetches; the GUI and `compare` show a licence flag on any
   model whose licence is non-commercial (CC-BY-NC*), custom with
   restrictions (HDcube), or disputed between its repository and
   OpenModelDB. Packs are never distributed, so a flag informs; it
   does not refuse. Each preset
   has a found-on-PATH probe (`shutil.which`, plus the GUI's path field),
   its licence and homepage shown, and a line that the model files are
   the tool's own and come with it. The CLI runs nothing it did not find
   and downloads nothing.
3. **HTTP service** (`[upscaler.<name>] url = "http://host:port"`): the
   **xbr upscale service contract v1**, small enough to implement in an
   afternoon in any language:
   - `GET /v1/info` → `{"name", "version", "scales": [2,4], "models":
     [{"name", "scales", "alpha": "rgb|rgba"}], "max_side", "batch": N}`;
   - `POST /v1/upscale?scale=4&model=NAME` with a body of `image/png`
     (RGBA) → `image/png` of `w*scale x h*scale`, or a JSON error with a
     status 4xx/5xx; `Authorization: Bearer` from the environment
     variable the config names (`token_env`), never the token itself;
   - `urllib` only on the client; retries with back-off; a per-request
     timeout; batches by `info.batch`; the client allowlists `model`
     against `info.models` and `scale` against `info.scales` before a
     request, caps the response body and checks the PNG `IHDR` against
     the expected size before decoding, and **refuses to send the bearer
     token over plain `http://` to a host that is not loopback** unless
     the local file sets `allow_plain_http = true` for that service
     (it warns even then).
   The server side (`xbr enhance serve`) requires a token when `--host`
   is not loopback (`--token-env VAR`; compared with
   `hmac.compare_digest`), caps the request body and the image size (the
   `IHDR` check before decoding), allowlists `model` and `scale` against
   its own `info`, and times out a stuck backend.
   Two adapters speak existing APIs through the same object: `a1111`
   (AUTOMATIC1111's `--api`: `GET /sdapi/v1/upscalers` for the list,
   `POST /sdapi/v1/extra-single-image` with `image` base64,
   `upscaling_resize`, `upscaler_1`; the result base64 in `image`) and
   `comfyui` (`POST /upload/image`, `POST /prompt` with an owner-supplied
   API-format workflow JSON whose load and save nodes the adapter fills,
   poll `GET /history/{id}`, fetch `GET /view`); the ComfyUI adapter is
   phase 4's last task because every workflow differs. `xbr enhance
   serve` is the reference server of the contract over any registered
   backend, the torch plugin included through its `worker` mode (D7.4),
   so the Mac that builds the pack can use the Windows PC's GPU across
   the room; bound to `127.0.0.1` unless `--host` is given.
   A remote or paid service is the owner's URL and responsibility; the
   GUI says so beside the field, and nothing in the CLI's defaults names
   a network host.
4. **PyTorch backend** (the user, 2026-11-01: "Let's allow PyTorch
   backend", reversing 2026-10-18's command-and-service-only). It ships
   as **a separate optional package, `xbr-upscale-torch`**, in the CLI
   repository under `plugins/torch/` with its own `pyproject.toml`,
   never a dependency or an extra of the CLI: an extra would land in the
   per-tag `.venv` that every re-pin replaces and pull torch (0.7 GB on
   the Mac, a few GB with CUDA wheels) onto every player's machine.
   - **Install.** The package is not on PyPI. `xbr enhance textures
     backend install torch` prints, and never runs, one `uv tool
     install` line per platform: the source is the CLI repository at the
     CLI's own tag with `#subdirectory=plugins/torch` (or a local path
     to a clone); torch comes from PyPI on macOS (MPS) and CPU-only
     hosts, and from the PyTorch CUDA index (`--index
     https://download.pytorch.org/whl/cu<NN>`, the ROCm index on AMD
     Linux) where a GPU is wanted, since PyPI's Windows torch is
     CPU-only. `uv tool install` ignores the plugin's `uv.lock`, so
     `plugins/torch/pyproject.toml` pins `torch` and `spandrel` to exact
     versions (the line passes the same pins as constraints).
   - **Contract version.** The plugin outlives the CLI's re-pins. Its
     JSON line (and `--version`) reports `contract = <major>.<minor>`;
     the CLI refuses a plugin whose major differs from its own, with the
     install line for its tag, and warns on a newer minor.
   - **Driven as a command** backend (2) with a fixed argv (`upscale
     --model PATH --scale S --in-dir --out-dir --device
     auto|cuda|mps|cpu --tile N --dtype fp32`), batch = a directory per
     call, so the CLI's process never imports torch and its
     stdlib-first default stays dependency-free.
   - **No `serve` of its own** (the review; the choice and
     its reason): remote use goes through `xbr enhance serve --backend
     torch` (3), so the network surface and its hardening (loopback
     bind, the token, the caps, the allowlists, the timeout) exist once,
     in the CLI, tested once. The cost is torch's start-up per process:
     measured on the M4 Max at ~0.85 s to import torch and spandrel,
     0.01-0.06 s to load a Compact model, and 0.02-0.4 s for the first
     inference (MPS warm-up), about 1.3 s per call at worst. A local
     build pays it once per batch directory (a few hundred textures),
     which on a world pass is seconds against minutes of upscaling. A
     process per request behind `serve` would pay it per texture (about
     2 h over the 5,481 world hashes), so `serve` keeps one plugin
     process alive in a `worker` mode instead: length-prefixed JSON
     headers and PNG bodies over its stdin and stdout, no socket, each
     model loaded once. The plugin never listens on a port.
   - **Model loading.** `--model` takes `.safetensors` (preferred, no
     code in the file), `.pth` or `.ckpt`, loaded **only** through
     `spandrel.ModelLoader` (MIT), whose pickle path is its
     `RestrictedUnpickle` (spandrel 0.4.1, checked), never a raw
     `torch.load`; core architectures only: `spandrel_extra_arches` is
     never installed, its architectures carry non-commercial licences.
     When a model preset names an expected sha256, the plugin hashes the
     file before loading and refuses a mismatch unless
     `--allow-model-mismatch` (the record then says so); an owner's own
     file has no expectation and is hashed for the record. A test feeds
     a pickle with a forbidden global (`os.system`) and asserts the
     refusal.
   - The plugin reports the architecture, native scale and the model
     file's sha256; a 4x-only model reaches 3x through the down-to-scale
     step below.
   - **Determinism**: the tracker item found every model byte-identical run to
     run on MPS and on the CPU, and MPS against the CPU within 1 LSB on
     a few texels. The pack record (`textures-pack.toml`) therefore
     stores `backend = "torch"`, `model_sha256`, `arch`, native scale,
     torch and spandrel versions, `device`, `dtype`, `tile`,
     `reproducible = false`, and `reproducible_scope = "host"` for
     `--device cpu` with `torch.use_deterministic_algorithms(True)`
     (equal bytes expected again on the same host, versions and tile),
     else `"none"`. `reproducible` stays a boolean everywhere; a pack of
     built-ins records `reproducible_scope = "any"`. Goldens never load
     packs.

**Down to scale**: an upscaler whose native scale differs from the
class's (a 4x model for a 3x class) is followed by the premultiplied
`lanczos` to the target size, inside the padded image before the crop;
under `alpha = binary` the threshold is applied after this downscale,
so the coverage check sees the final size; the record names both
steps.

**Alpha** (all kinds): a model trained on RGB sees a transparent texel's
colour as data. `split` (default): the colour is edge-extended under
transparent texels (the nearest opaque colour, so a cutout's halo is not
black), RGB is upscaled, A is upscaled as a grey image with the same
upscaler, and both recombine; `native` passes RGBA to an upscaler that
declares it; `binary` thresholds the upscaled alpha and matches the
source coverage within 1%, for alpha-tested cutouts. **Edges**: the
source is padded by 8 texels before upscaling by the address mode the
dump recorded (`wrap`: the opposite edge, never a mirror, which would
seam a repeating tile; `mirror`: the guest's MIRROR mode, the edge
reflected; `clamp`: the edge extended; `cells`: per cell, D2) and
cropped after, so a tiled floor has no seam row and a sprite does not
bleed into its neighbour. A recorded mode always wins, per axis. Scenes that
recorded different modes merge per axis to the one that repeats (`wrap` over
`mirror` over the clamps, a recorded mode over none), whatever the order of the
dumps: a clamped pad on a tile shows at its seam, a repeating pad on a texture
drawn once only touches its rim (BLiNX 2's six scenes disagree on none). With none,
a `world` entry falls back to `wrap` (BLiNX 2's dumps: 415 wrap, 14 clamp_edge
where a mode was seen, 4,649 world entries of the inventory unrecorded; clamp's mean seam step 23.8
against wrap's 7.0) and every other class to `clamp`; the build's summary and
the record's `wrap_defaulted` count the entries that fell back. **Size limits**: an entry whose
side would exceed `NV2A_TEX_PACK_MAX_DIM` (16384) or the class's
`max_side` is built at the largest scale that fits, and said.

### D8. The config the build consumes

Two files, so the tracked one never carries an owner's machine:

- `config/enhance-textures.toml`, **tracked** in the game repo: the
  preset, the render scale, classes, rules, upscaler names and their
  numeric parameters, the font face, budgets. Names, numbers and hashes
  only; no path, no URL, no texel, and nothing that says what runs:
  `template`, `binary`, `model` and `overrides` are local-only, and a tracked
  one is refused before anything runs, with a message naming the local file.
  A cloned repo's config must not be able to run a program. A preset stays
  selectable from here by name, since its template ships in the CLI.
- `config/enhance-textures.local.toml`, **untracked** (gitignored by
  `xbr new`'s template and each game's `.gitignore`, which `layout.report`
  checks; cat has the lines, and the others gain them before their CLI pin
  moves, tasks 3.9; the export refuses it):
  per upscaler the `template`, `binary`, program `path`, `model`, model
  directory, `overrides`, service `url`,
  `token_env`, `allow_plain_http`, `gpu` (ncnn), `device` (torch). The GUI writes the two files
  from one form and says which key goes where; `build` merges them
  (local over tracked) and records in `textures-pack.toml` only the
  identities (sha256, version, `info`), never the paths or URLs.

They replace enhance-menu-preview D13's `enhance-hud.toml` before that
file exists; the `[font]` table is D13's, unchanged, and `[text]
languages` moves under `[class.text]`.

```toml
schema = 1
preset = "world"                    # a game preset, or "custom"
render_scale = 2                    # the render scale the owner plays at (D14, D15)

[coverage]
mode = "classes"                    # classes | traced (D14)
untraced = "class"                  # traced: skip | class (what an untraced texture gets)
languages = ["us"]

[class.ui]
scale = 4
upscaler = "xbr"
alpha = "split"
edges = "clamp"
mips = "none"
encode = "raw"
max_texels = 0                      # 0: no cap (the hud preset sets 65536)

[class.world]
scale = 2
upscaler = "lanczos"
alpha = "split"
edges = "auto"                      # the recorded wrap mode
mips = "full"
encode = "auto"                     # bc1, bc3 with alpha
max_side = 4096

[class.font]
scale = 4
upscaler = "atlas"                  # the font fit when [font] names a face, else xbr

[class.text]
scale = 2
upscaler = "xbr"
encode = "bc3"

[rule."dds/radar*"]                 # fnmatch over names, any class; later rules win
upscaler = "nearest"

[rule."hash:0B060D91FB09F186"]      # an unnamed dump entry, by hash
skip = true

[rule."dds/floor_*"]
edges = "wrap"
scale = 4
upscaler = "esrgan"

[upscaler.xbr]
level = 2
eq = 300000
weights = [48, 7, 6, 48]
alpha_edge = true

[upscaler.esrgan]                   # a command preset; its path and model are in the local file
preset = "realesrgan-ncnn-vulkan"
tile = 0

[upscaler.remote]                   # a service; its url and model are in the local file
                                    # (realesr-general-x4v3, BSD-3; a CC-BY-NC* model works too, flagged in the GUI)

[budget]                            # defaults from the phase 0 spike
pack_mb = 0                         # 0: no warning
vram_mb = 0

[font]                              # enhance-menu-preview D13, unchanged
face = "PT Sans Narrow Bold"
```

`config/enhance-textures.local.toml` (untracked), the same tables with
the machine's half:

```toml
[upscaler.esrgan]
path = "<where the owner unpacked realesrgan-ncnn-vulkan>"
gpu = "auto"

[upscaler.remote]
url = "http://127.0.0.1:8711"       # or an https:// host; plain http off loopback needs allow_plain_http
token_env = "XBR_UPSCALE_TOKEN"
```

`xbr enhance textures build --config FILE` (default the tracked file
when present, the local file beside it) applies, per entry: the class
defaults, then the class table, then the trace's proposal (D14), then
matching rules in order, with `max_side` clamping last; records
the tracked config's path and sha256, each upscaler's identity (built-in
name and CLI version; a command's sha256 and version line; a service's
`info`), `reproducible = true` only when every upscaler used is built
in, and `reproducible_scope` (`any`, `host` or `none`, D7.4), in
`textures-pack.toml` beside `textures.pack`. Without a config the `hud`
preset is what `enhance hud` makes today (a test pins the art and font
payloads byte for byte; the header is v3).

### D9. The GUI: the local web UI, not the wizard

| Option | Fit |
|---|---|
| Extend the Go/Fyne wizard | It would need image decoders, every filter, the crop and compare views and the estimates, in Go: a second pipeline (forbidden by the wizard rule), new dependencies, and a preview that is not the bytes the build writes. It also runs on the player's machine, where no upscaler is installed. Rejected for the preview; kept for the offer (D11). |
| A native CLI GUI (tkinter, SDL) | Tk is absent from several system Pythons and the Deck's; an SDL/C tool duplicates the Python modules. Rejected (as enhance-menu-preview D12 did). |
| **`xbr enhance preview`, the planned local web UI** | `http.server` on `127.0.0.1`, one static page, PNGs from the same modules that build the pack, every host with a browser, no dependency, no network. The font page of enhance-menu-preview phase 8 shares the server. **Chosen.** |

The page's Textures tab has four panels:

- **Upscalers**: the registry (built-ins first; each command preset with
  found/not-found, version, licence and homepage; registered services),
  a form to register a service (name, URL, token
  env name, Test → `info`), a path field for a tool off PATH, and the
  parameters of the selected upscaler from `describe()`.
- **Coverage**: the game's presets, the class table (D2) as editable
  rows, the rule list (a rule is added from a texture in the compare
  panel: "nearest for this one", "skip", "wrap edges for `floor_*`"),
  the exclusions with their reasons, and three bars per preset from
  `estimate`: pack MB, resident VRAM MB per dumped scene, build minutes.
- **Compare** (D15).
- **Runtime**: the `[TEXPACK] miss` log import (hashes joined to the
  inventory, hash-only rows for unknown ones) and, when a trace is
  loaded, the magnification table of D14.

**Save** writes the two config files of D8 and prints the `build`
command; **Build** is not in the tool (the CLI command is the one
pipeline). The server binds `127.0.0.1`, serves its page and JSON routes
only, writes nothing but the configs and the per-user font cache, holds
decoded images in memory and exits on `/quit`, Ctrl-C, or when the
wizard that started it exits.

**The page can register commands and service URLs, so loopback alone is
not enough** (a page in another tab could post to it: CSRF, DNS
rebinding, SSRF through a registered URL). The server therefore: puts a
random per-session token in the URL it opens and requires it on every
route (page, JSON and images alike; a missing or wrong token is 403 with
no body); checks the `Host` header is `127.0.0.1:<port>` or
`localhost:<port>`; rejects any request with a foreign `Origin`; takes
POST bodies as JSON only (`Content-Type: application/json`, no form
encoding, so a cross-site form cannot reach a route); and never follows
a registered service URL except through the `http` backend's own
allowlisted requests. The tests of 5.6 cover each refusal.
The token is as strong as a shell: whoever holds it can make the page
run the owner's local upscalers, a local `template` included, through
the render route. So it goes only to the terminal and the URL the
browser opens, and the page drops it from the address bar once read.

### D10. Where the preview's textures come from

The compare panel lists the inventory grouped by class and language:
the game's `[enhance.textures] preview` picks first, then the dump's
most-used, then the rest; a search box over names and hashes. Texels
come from the dump file when there is one (what the runtime decoded) or
from the archive feeder. Crops are 128x128 by default (a 4x xBR crop
renders in ~250 ms; a CNN crop in under a second on a GPU) and the owner
drags them; a whole-texture render is on demand and cached by
`(upscaler, params, hash, crop)`.

### D11. The wizard offers the presets, and hands off to the GUI

The wizard stays a front end over the CLI:

- `[[wizard.option]]` gains `flag` on `kind = "choice"`: the chosen value
  is passed as `--texture-preset VALUE`; cat's option lists `off`, `hud`,
  `ui`, `world`, `all` with the labels the game writes. `wizard config`
  checks the values against the tag's presets. `off` passes nothing.
- The estimate under the choice comes from `package --plan --json`'s new
  `textures` row (minutes and MB per preset, from the inventory and
  calibration cache in the clone; "not measured yet" before a first
  inventory, which the wizard's Checks page can run after the dump is
  known as one more row, `enhance textures inventory`, a few seconds).
- **Configure…** (enabled after Checks and Dump): runs `<game> enhance
  preview --no-browser` through the runner, opens the printed URL (token
  included) with the wizard's `OpenURL`, shows "Saved:
  config/enhance-textures.toml" when the file appears in the clone, and
  stops the server (`/quit`, then the process) when the page is left or
  the wizard exits; the build then reads the configs. Before any runtime
  dump exists the page shows the archive feeder's inventory (every
  texture a reader names, with "not seen at runtime" on each) and, for a
  game with no reader, an empty compare list with the one-paragraph way
  to make a dump (`RECOMP_DEBUG=tex_dump=<dir>` on a run of the installed
  game, then `enhance textures inventory --dump DIR`); the estimates
  then come from the archive counts alone and say so. The button's note
  says that CNN upscalers need a tool the owner installs and that the
  built-in filters need nothing.
- The wizard's `Tweaks` map (`internal/model/model.go`) gains the
  `--texture-preset` entry (plan row `textures`, keep
  `--keep-texture-pack`, clear `--clear-texture-pack`) beside the
  `--hud-pack` one, so an Update build keeps, clears or remakes the pack
  as it does the HUD pack today.
- Summary and Build name the preset and the config's sha; the stage
  shows its estimate and progress like `enhance hud` does today.

Nothing new is linked into the wizard and no upscaler runs in its
process; `wizard/check.sh` is the gate.

### D12. Relationship to the HUD pack, pack versions, the tracker item and enhance-menu-preview

- **HUD pack, names and migration.** `xbr enhance hud` is kept as
  `enhance textures build --preset hud` with its flags, and **keeps its
  output names** (`dist/enhance/hud/hud.pack`, `hud-pack.toml`), so the
  tweaks (`--hud-pack`, `--keep-hud-pack`, `--clear-hud-pack`), the
  incremental reader of `hud-pack.toml`, the manifest record
  `enhance.hud_pack` and the wizard's `hud_pack` plan row keep working
  unchanged. `build` with any other preset writes
  `dist/enhance/textures/textures.pack` and `textures-pack.toml`, staged
  by `package --texture-pack [DIR]` (`--texture-preset NAME` builds it
  first; `--keep-texture-pack`, `--clear-texture-pack` mirror the HUD
  flags; the manifest record is `enhance.texture_pack` with the same
  fields). A bundle carries **one** pack, named by the runtime
  configuration key `textures.pack` (a key, not a file name: it points
  at `enhance/hud.pack` for a HUD-only bundle and at
  `enhance/textures.pack` otherwise; the user, 2026-10-18: one pack per
  bundle, the kinds as the runtime's switches): `--texture-pack` and
  `--hud-pack` are separate flags, refused together with one line, and `--texture-pack` over a base that carries a HUD pack
  replaces it (said in the plan). `package/incr.py` and `tweaks.py` read
  either manifest name; `[enhance.hud]` keeps its keys (`max_texels` is
  the hud preset's cap, no longer the command's). Tasks 3.6 and 3.7.
- **Pack v2 → v3.** One writer; the reader takes all three; the public
  pin note of enhance-menu-preview (a CLI ahead of the pinned runtime)
  applies until the next push round.
- **The tracker item** is superseded: its inventory, mips, DXT re-encoding,
  per-class scalers, VRAM, opt-in surface and privacy are D1-D8 and the
  tasks; it is closed as absorbed at the first merge.
- **enhance-menu-preview.** Phase 7 (7.1-7.5: the filters, `preview_cfg`,
  the server and page in upscale mode, the command, the gates) moves
  here as 3.1, 3.5 and 5.1-5.6; D12-D15 there get a pointer; phase 8
  (font mode) stays there and its page is a tab of this server
  (8.3 depends on 5.1); phase 10 (baked-text re-render) is unchanged.
  Phases 1-6 and 9 are untouched.
- **The tracker item** (`[enhance]` in `game.toml`): `[enhance.textures]` is one
  more table under it, read by the CLI like `[enhance.hud]`.

### D13. Keys, env rows, logging, goldens

- `textures.world` (`RECOMP_TEXTURES_WORLD`, config tier, `on`): the
  fourth kind switch; live from the menu as the others, with its own
  menu item on the Pack page beside font and text; in the pack log line.
  `golden.py`'s `ENHANCE_STOCK` and `manifest.TOOLKIT_ENHANCE_KEYS` (which
  `tests/test_manifest.py` asserts equal) both gain `textures.font`,
  `textures.text` and `textures.world` (stock `on`; the first two are in
  neither list today, which was safe only because `golden.json` pins
  `RECOMP_CONFIG=none` and no pack); cat's `docs/env.md` gets the
  `RECOMP_TEXTURES_WORLD` row.
- The dump is the debug entry `RECOMP_DEBUG=tex_dump=<dir>`, not a
  variable of its own (as `fb_dump=<prefix>` is): a developer's tool,
  not a player's setting; cat's `env.md` gets a row in the `RECOMP_DEBUG`
  entries; never set in goldens (it changes no frame, but it writes
  files).
- The trace is `RECOMP_TRACE=tex_mag`, one more name in the trace list
  beside `tex_pack`; cat's `env.md` names it in the `RECOMP_TRACE` row.
- The pack line: `[ENHANCE] textures.pack=<path> (<n> entries: <a> ui,
  <f> font, <t> text, <w> world; v<ver>; scale <s>, text <ts>; <b1> bc1,
  <b3> bc3) textures.font=.. textures.text=.. textures.world=..`.
- Goldens: `RECOMP_CONFIG=none`, no pack, no dump, no trace; the harness
  fails a run showing a pack or `textures.world=off`.

### D14. Coverage by on-screen magnification (the trace)

An upscale helps only where a texel covers more than one screen pixel.
At stock 640x480 a HUD piece drawn 1:1 gains nothing; a floor two metres
away samples a lower level and gains nothing; the gain grows with
`render.scale` and with close-ups. "Everything at 4x" is the simplest
rule and the most expensive one.

**The trace.** `RECOMP_TRACE=tex_mag` (both GPU backends): the fragment
shader variant used under the trace computes, per sampled stage, the
unclamped LOD the GPU would pick (`calculate_unclamped_lod` in Metal,
`CalculateLevelOfDetailUnclamped` in HLSL; the derivatives are taken in
uniform control flow, before the one-in-64 subsample branch, so they are
defined) and keeps an atomic max of `-lod` under a **biased unsigned
encoding** (an atomic max of a negative float is not a max; the value
is stored as `uint(clamp(-lod + 32, 0, 64) * 1024)`) in **one device
buffer with a slot per draw id and stage** for the frame, not a per-draw
readback (which would stall the GPU); the backend reads the buffer back
when the command buffer completes (Metal `addCompletedHandler`) or at
the frame's end (a D3D11 staging copy, one frame behind) and folds it
into a per-hash table (max magnification, draws, the render scale of the
run). D3D11 binds the buffer as a pixel-shader UAV through
`OMSetRenderTargetsAndUnorderedAccessViews` on the trace's pipelines
only. Occluded fragments count (the depth test runs after the shader
on this path), which over-estimates a texture behind a wall; the
figure is an upper bound, and the page says so. The trace runs with
no pack loaded, or the backend divides by the entry's scale when one
is, so the figure is always source texels per screen pixel. The CLI drops a
figure that is no number or past `traced.MAG_BOUND` (2048; `traced.sane_mag`),
since a corrupt sidecar must not propose a scale. At exit,
and into the dump's sidecars when the dump is also on, each hash gets
`mag_max` (host pixels per source texel at that render scale) and
`mag_scale1 = mag_max / render.scale`. The atomics cost is paid only
under the trace; without it the generated shader text is unchanged,
which a test asserts by diffing the output of `d3d8_combiners_hlsl.c`
and `d3d8_combiners_msl.c` for the existing fixture set against the
current text (the enhancements spec's stock rule), and the goldens
confirm. A CPU-side estimate for pre-transformed (2D) batches is exact
and free and is used for them without the shader path.

Weighed: a sampler-feedback API (D3D12 and Metal 3 only), a per-draw
bounding-box estimate from vertex data (free, but the CPU has no
projected positions for 3D batches: wrong by the perspective), a mip
histogram per texture from a debug render target (an extra attachment on
every pipeline). The atomic max on a subsample is the smallest change
that gives the real number on both backends.

**What the tool does with it.** With `coverage.mode = "traced"` and the
owner's `render_scale` `R`, each traced entry's proposed scale is
skip when `mag_scale1 * R <= 1` (never magnified), else the smallest of
{2, 3, 4} at or above `mag_scale1 * R`, capped at 4 (a texture at most
0.9 pixels per texel at 1x is skipped for `R = 1`, gets 2x for `R = 2`
and 3x for `R = 3`; one at 1.3 gets 2x, 3x and 4x); a 3x proposal on a
mipped entry waits for D4's fractional shift (1.2); untraced entries get the class default or are
skipped (`coverage.untraced`). A traced world entry
with a CNN gets 4 only here, where the trace shows a magnification above
3; D2's class default for it stops at 3. The GUI shows the table (name, class,
`mag` at 1x, the proposal at `R`, the bytes saved against the class
default) and the owner overrides per entry; the result is written as
rules, so the build stays declarative and the trace is advice. Since
rules apply in order, `--write-rules` puts its block before the owner's
first rule and leaves out any hash the owner rules, so a glob the owner
wrote still beats a traced line. An owner's rule with a `scale` answers
a proposal to skip (review). The
trace covers what was played: the golden scenarios plus a playthrough;
the `[TEXPACK] miss` import names what a later session found.

Against globs and "everything": globs are what a game's maintainer
knows (names say HUD or world; the trace does not), "everything" is
complete but pays for texels nobody magnifies, the trace is exact about
the benefit but partial about coverage. The design offers all three and
recommends: classes and globs for the defaults, the trace to cut what
the chosen render scale cannot show, `all` when disk and VRAM do not
matter.

### D15. The preview at the render scale

A texel view zoomed in isolation flatters every upscaler. The compare
panel has two views:

- **Texels**: side by side and a slider (wipe) between two results on
  the crop, each panel labelled with the upscaler, time per texture and
  bytes after encode, raw beside BC1/BC3 on request.
- **On screen at `render_scale` R**: the same crop resampled to the size
  it has on screen, using the entry's magnification from the trace (or
  a magnification the owner types: "drawn at 1.0 px/texel", "close-up
  at 3") times R, through the guest's recorded filter (nearest or
  linear, with the chain's level the LOD picks for that footprint).
  Below the stock texture's own on-screen render for the same footprint.
  Both views build their mip chains with the pack's box filter, so the
  stock view's lower levels are not the dump's authored mips.
  This is a software resample of the result, not the game's frame, and
  the page says so; a texture drawn 1:1 at R = 1 shows no difference,
  which is the point.

The real check stays the game: a Metal window shot with the pack
(tasks 7.4) and the D3D11 run (7.5).

### D16. Platforms, backends and licences

| Backend | macOS (Apple Silicon) | Windows | SteamOS/Linux | CPU fallback | Licence |
|---|---|---|---|---|---|
| built-in filters | yes (CPU) | yes | yes | they are CPU | the CLI's |
| realesrgan-ncnn-vulkan | runs through MoltenVK; Apple Silicon verified on an M4 Max (20220424) | Vulkan GPU | Vulkan GPU (the Deck's too, but the Deck never builds) | `-g -1` per ncnn, undocumented in its README (verify) | MIT (the port); Real-ESRGAN BSD-3; model licences as published with the tool |
| waifu2x-ncnn-vulkan | prebuilt Apple Silicon binaries | yes | yes | `-g -1` documented | MIT |
| realcugan-ncnn-vulkan | MoltenVK, verified; segfaults on wide thin inputs (D7.2's preset works around it) | Vulkan GPU | Vulkan GPU | `-g -1` | MIT: the ncnn port (nihui) and Real-CUGAN with its weights (`bilibili/ailab` `Real-CUGAN/LICENSE`; no separate model terms) |
| upscayl-bin | arm64 build verified (MoltenVK) | not documented on the repo page | yes | as ncnn | AGPL-3.0 (invoked as a program; never linked or vendored) |
| chaiNNer `run` | yes | yes | yes | per backend | GPL-3.0 (invoked); PyTorch, NCNN, ONNX, TensorRT backends |
| HTTP service / a1111 / ComfyUI | any host | any | any | the server's | the server's |
| `xbr-upscale-torch` (spandrel + PyTorch, D7.4) | MPS, verified | CUDA | CUDA, ROCm | `--device cpu` (6.5-11x slower than MPS: 6.5-7.3x the compact models, 11x x4plus) | spandrel MIT, PyTorch BSD-3; each model its own licence, flagged when restricted |

The Deck installs packs; builds happen on the Mac or a PC (the standing
rule). An owner on a Mac without a GPU tool uses the built-ins, or
`xbr enhance serve` on the Windows PC and the `http` backend. Nothing
is downloaded, vendored or run that the owner did not install; every
preset's licence and homepage are shown in the GUI and in
`docs/texture-pack.md`; the pack, the dump and the inventory's texels
never leave the owner's machines.

## Risks / Trade-offs

- **Seams on tiled surfaces.** Edge padding by the recorded wrap mode
  (D7) removes the seam a CNN or Lanczos makes at a texture border; a
  texture tiled by the mesh but sampled with `clamp` keeps the seam the
  game already had. Detection: the on-screen view and 7.4's floor crop.
- **Alpha bleed and halos.** `split` with edge-extended colour; `binary`
  for cutouts. Detection: the coverage test (3.3) and the preview.
- **Texel-exact draws.** UI drawn 1:1 with nearest filtering and an
  upscaled entry without mips samples every `s`-th texel: close to the
  source, with the risk of a one-texel shimmer at scale 1. The `ui`
  class keeps `mips = none` (the game draws UI without mips and a chain
  would blur it at `render.scale = 1`); the trace tells which UI pieces
  are magnified at the owner's render scale and the rest can be skipped.
- **Grid atlases and sprite sheets.** A CNN draws strokes across cell
  borders; `grid`/`cells` edges and `xbr` for fonts. The named-font fit
  stays the better answer where the game has rows.
- **Normal and data textures.** Skipped by default; the dump's facts
  catch bump stages and 1xN ramps; a game may still read a texture as
  data in a combiner the facts do not see (a palette image, a wave
  table): the owner's preview and `[rule] skip`.
- **CNN colour shifts and invented detail.** Shown in the compare view;
  per-class choice; `lanczos` as the safe world default.
- **Build time.** Hours for `all` with a CNN on a CPU; the estimate is
  printed before the build and the wizard shows it; batches, processes
  and the optional vectorised encoder bound it.
- **Reproducibility.** Only built-ins give one pack from two hosts;
  `textures-pack.toml` says `reproducible = false` otherwise (with
  `reproducible_scope = "host"` for a deterministic CPU torch run) and the
  incremental packaging treats the pack by sha as it does today.
- **The dump is game data.** Gitignored, flagged by the audit, kept in
  `runs/` in this workspace; the inventory JSON holds no texels.
- **Pack v3 and the public pin.** As with v2: the next push round
  re-pins.
- **Pure-Python preview speed.** Crops, caching, on-demand full renders.
- **Trace cost and shader variants.** One more compile-time flag on the
  combiner shader; the stock text is unchanged, asserted by the shader
  text diff of D14 (not by `RECOMP_PB_FAST_AB`, which compares only the
  CPU rasteriser's fast and slow paths) and by the goldens.
- **The preview server is a local web service.** The token, Host and
  Origin rules of D9; the tests of 5.6 cover each; the wizard stops it.

## Migration Plan

0. Inventory spike (numbers first; confirms D2's defaults and D6's
   budgets; no merge).
1. Toolkit: v3, BC1, `WORLD`, `textures.world`, the dump, the release
   of pack texels, the trace shader flag; ctests; Metal goldens; D3D11
   cross-built, run in phase 7.
2. CLI: sources, inventory, classes, estimates.
3. CLI: the upscaler interface with built-ins and the command backend,
   alpha, edges, mips, BC1, the config, `build`, `enhance hud` as the
   preset, `package --texture-pack`; the `compare` grid and `pick`
   (3.6a) and the optional `xbr-upscale-torch` plugin (3.2a).
4. CLI: the HTTP contract with its hardening, the a1111 and ComfyUI
   adapters, `enhance serve`.
5. CLI: the preview GUI's Textures tab (absorbs enhance-menu-preview
   phase 7).
6. Wizard: the choice flag, estimates, Configure….
7. Games: cat and b3 tables and docs; the owner's packs on Metal and
   under Proton; the b3 dump-only path.
8. Reviews and merges; the tracker item closed; enhance-menu-preview updated.

Rollback: every key defaults to stock; a build without
`XBOXRECOMP_ENHANCE` loads no pack (the layer is the loader), while the
dump and the trace live in the always-built kernel library and run only
under their `RECOMP_DEBUG` entry and `RECOMP_TRACE` name, never by
default; a v3 pack on an older runtime is refused whole with its one
line and the run stays stock.

## Measured (phase 0 in part, 2026-11-01)

From `analysis/enhancements/texture-upscalers.md` (cat; names, hashes,
sizes and timings only).

- **Inventory (archives and six dumps, 2026-11-06)**: `media`,
  `lng_us` and `tank_tex` against `@attract`, `@stage1` and `@story` at scale
  1 and 3: 9,082 entries, 349 joined, 8,593 not seen, 140 unnamed (P8 101,
  G8B8 17, YUY2 12, DXT3 7, A8R8G8B8 3). **A DDS whose chain has a level with
  a side under 4 cannot be joined by hash through that level**: of 5,803 such
  files none joins at a prefix holding it (9 join at level 0 alone, bound with
  no chain), while mipped MIX/XPR files join at 6-9 levels. Their
  levels from 4x4 up decode to the file's within 1, the ones below differ by
  up to 6, and no byte prefix of the file hashes to the dumped hash (53 of 53
  tested): the game's load re-encodes those small levels. Such an entry is
  `hash_guess`, skips as `needs_dump` (2,182 in this inventory, 2,178 of them
  world, 60.8 M texels not packable from the archive alone), and a dump names
  it by decoded content (83 joined that way). The world figures below count
  them; a pack reaches them only through a dump, until the runtime has a key
  that ignores those levels or the encoder is reproduced.
  This is one game's load, so it sits behind `[enhance.textures]
  reencodes_small_levels` (default false; cat sets it at task 2.6). The
  switch covers chains: of the DXT candidates, chains with a level under
  4 are 7,022 files, 128 hash-joined: 119 of 1,219 MIX and 9 of 5,803 DDS.
  Chains with every level at 4 or more are 27 files, 0
  joined; one level at 4 or more is 15,007 files, 1,317 joined. No file
  has one level with a side under 4, so that case has no evidence and is
  not flagged. No DXT file is NPOT either; one would be flagged in any
  game, since no GPU takes it as it stands and the load has to resize it.
  A content name is confirmed on level 0 after the probe level hits, so
  one small level cannot name the wrong texture: the joined count stays
  349 with the check on.
- **Inventory after the review**: font 1 of 1 packable, text 3,703
  of 3,707, ui 296 of 296, world 2,831 of 5,078; skipped `needs_dump` 2,182,
  `volatile` 42, `normal` 17, `data` 6, `linear` 4; palettized 81 variants of
  18 images. Estimates: `all` 1,226.1 MB, `world` 1,226.1, `ui` 1,037.5, `hud`
  158.8. With the dump alone, `@stage1`: 297 entries, 270 packable, 16.1 MB.
  A dump's bad `.xtd` is listed in `problems`; it
  stays packable when a source was hash-joined, since the source is good,
  and skips as `no_texels` otherwise. These dumps have none.
- **`hud` preset against a real `enhance hud` pack (BLiNX 2, scale
  4, font named, language us)**: 427 entries in both, none
  only in one, none of 427 with another payload size. 158,769,152 B of
  payload in both: art 140,353,536, font 4,194,304, text 14,221,312; the
  file is 158,782,848 B, the rest being header and index, which the estimate
  does not count. The first comparison was wrong by one entry,
  `mis_sub_abxy` (128x32 DXT3, six mips): the runtime binds one level, and
  `enhance hud` refuses a mipped file. The preset now leaves those out, so
  the set agrees. This compares the set, scale, encode and size. Equal
  texels are the build's to show (3.6's test).
- **Inventory (archives only)**: 22,931 entries (22,056 DXT, 874
  non-DXT, 1 skipped archive), 8,926 unique DXT hashes; unique source texels world 158.5 M (5,481 hashes, 2,959
  mipped), text 161.4 M (3,048; an upper bound), ui 13.7 M (294), font
  0.13 M (2), effects 0.8 M (101); 874 non-DXT entries (829 TGA8) need
  the dump. World entries repeat ~3.2x across stage archives: the hash
  join is what keeps the build linear.
- **Pack bytes**, BC1 for DXT1 sources and BC3 otherwise, full chains
  for mipped sources: all classes 1.1 GiB at 2x, 2.4 GiB at 3x, 4.3 GiB
  at 4x; world alone 456 MiB / 1.0 GiB / 1.8 GiB; raw RGBA world at 3x
  would be 6.1 GiB, so world and text are BC-only. VRAM per scene
  waits for the dump (0.1).
- **Seconds per source megatexel** (M4 Max; the upscaler call only,
  over the padded and split inputs; the pad, the alpha split and the
  down-to-scale ran in numpy/Pillow outside the timed call):
  `nearest`/`epx` 0.01 and `lanczos` 0.27 (numpy/Pillow stand-ins,
  spike only: the CLI's integer versions are pure Python and of
  `xbr`'s order, timed in 3.1), `xbr` 3x 8.2 (the CLI's pure-Python
  kernel, per job); realesr-animevideov3 x3 (ncnn) 1.07,
  realesrgan-x4plus (ncnn) 11.7, x4plus-anime 4.1, waifu2x cunet 2.6,
  Real-CUGAN se 3x 9.6 (one process per file), upscayl-bin + 2xHDCube
  1.0; spandrel on MPS: realesr-general-x4v3 0.57, 4xHDCube4Compact
  0.34, 4x-PBRify SPANV4 0.51, PBRify RPLKSRd 3.6, RealESRGAN_x4plus
  8.3; the CPU 2.2-91 (6.5-7.3x MPS for the compact models, 11x for
  x4plus). The ncnn figures include each tool's start-up (one process
  per batch, or per file for Real-CUGAN); the torch figures exclude the
  import and model load (the harness kept the model in-process), which
  a cold process adds at ~1.3 s per call (D7.4), so `compare` (3.6a)
  times the plugin as a subprocess. A world pass at 3x (158 M texels):
  about a minute on MPS (HDCube4 54 s, realesr-general 90 s) to 31 min
  on a GPU (ncnn x4plus; Real-CUGAN 25 min), 22 min for `xbr` per job,
  and 4 h for x4plus on the CPU; every CNN figure is optimistic by the
  down-to-scale over its 4x output, still untimed.
- **Determinism**: every upscaler byte-identical on two runs; torch MPS
  against the CPU within 1 LSB.
- **Per class at 3x** (the grids, kept in `runs/`): world gains from a
  restrained CNN (realesr-general-x4v3, realesr-animevideov3,
  PBRify RPLKSRd, HDCube4) and is repainted by x4plus/x4plus-anime;
  ui, text and font are best with `xbr` (CNNs halo strokes and invent
  a grid from DXT blocks in translucent panels); effects with
  `lanczos` (CNNs flatten glow cores and invent leaf veins). D2's
  upscalers stand; its scales follow the render-scale rule now written
  into the table (`clamp(R, 2, 4)` for ui, `clamp(R, 2, 3)` for world
  with a CNN until D14's trace shows a magnification of 3 or more).
- **Presets to ship**: the built-ins; command presets for
  realesrgan-ncnn-vulkan (`realesr-animevideov3` as the world CNN
  default for ncnn, x4plus offered with a "repaints" note),
  waifu2x-ncnn-vulkan, realcugan-ncnn-vulkan (per-file workaround),
  upscayl-bin with an owner model, chaiNNer `run`; the torch plugin with
  model presets `realesr-general-x4v3` (BSD-3, the world default when
  torch is present), `4x-PBRify_RPLKSRd_V3` and `_UpscalerSPANV4`
  (CC0), `RealESRGAN_x4plus` (BSD-3), `4xHDCube4Compact` (flagged:
  custom licence, OpenModelDB lists the HDCube versions as CC0,
  CC-BY-4.0 and CC-BY-NC-SA-4.0).
- **Measured in game** (0.3a, 2026-11-01;
  `analysis/enhancements/texture-upscalers.md` section 8): `@stage1` on
  the PC (D3D11) at render scale 3 with hand-made v2 packs of the 2,607
  unmipped world and fx hashes. The CNN (`realesr-general-x4v3`) is the
  best for world (crisp props, foliage keeps its width, no halos);
  `lanczos` is soft and thins alpha-tested strands; `xbr` is the worst
  for world (posterised, stair-stepped). The packs cost no speed (flips
  per second within run-to-run spread). A native 4x CNN pack matches the
  4x-to-3x one by eye at render scale 3 and 4 (1 to 4% detail energy at render scale 4)
  for about 78% more bytes and VRAM. With no sampler shift, sharp
  unmipped props beside soft mipped surfaces show mixed sharpness up
  close until 1.2 lands. Build-time correction: end to end the CNN pack
  build ran about 5 s per source megatexel (448 s for 87 M texels),
  against 0.57 for the model call alone, so the "about a minute" world
  pass above is closer to 13 min.
- **Still open in phase 0**: 0.1 (the dump and the trace), the BC1/BC3
  encoder timings (moved to 3.4) and the pure-Python built-in timings
  (moved to 3.1), and VRAM in 0.4 (the mipped world hashes need 1.2's
  sampler shift, fractional at 3x, before a pack can carry them).

## Measured (phase 3, 2026-11-06)

The whole-game pack from the BLiNX 2 archives and six dumped scenes, built-in
upscalers only, `--preset all --jobs 8 --dump ...` for the six scenes, on the Mac.

- 6,821 entries (296 art, 1 font, 3,703 text, 2,821 world; 2,088 BC1, 4,436
  BC3, 297 raw), 1,227.5 MB. 10 entries are left out, each said by the build: no
  source decoder here and no dump holding the texels (5 A4R4G4B4, 4 A8R8G8B8, 1
  DXT1). Without `--dump` the same inventory leaves 95 out: those 85 textures are
  in the dumps, and the earlier "no dump holds it" for them was wrong, since that
  run passed none and the inventory had no `.dumps` file.
- Reproducible: two builds on the final code give the same bytes (sha256
  `c77d091ef026`, `cmp` clean) and the same `textures-pack.toml`. It replaces
  `4c14a7189788` for two causes, and only those: the 85 entries the dumps add and
  the wrap fallback of D7. Against the old pack, every art, font and text payload
  is equal; of the 2,736 world entries in both, 2,420 changed and 316 did not.
  2,466 of the pack's world entries fell back to wrap.
- The review's later changes do not move that sha, shown and not rebuilt: per-cell
  colour extension only differs under `edges = "cells"`, which no class row or cat
  config uses; the wrap merge has nothing to merge, since no hash of the six
  scenes' 490 disagrees or is recorded by only some of them. A rebuild of 103 real
  textures (alpha, opaque, `ui`) matches this pack payload for payload.
- 555 s on 8 jobs (3,393 s of CPU, 478 MB peak per process), and under a second
  when nothing changed (0.75 s to "is current", hashing every input).
- The toolkit's C reader (`nv2a_tex_pack.c`, 348ec96c) loads it as v3 and finds
  and reads all 6,821 entries. `--preset hud`: 427 entries, every payload equal
  to `enhance hud`'s v2 pack, which keeps its sha256 `8df7c673a31c`. That equality
  is proven on BLiNX 2 only.
- Not measured: an external upscaler (none on this Mac), the pack in a running
  game (phase 7), `enhance serve` (phase 4).

## Decided (the user, 2026-10-18)

The five open questions of the first draft, answered the same day:

1. **One pack per bundle**, the kinds as the runtime's switches; the
   HUD-only case is the `hud` preset (D12).
2. **Budgets** are left to the phase 0 inventory spike: the config ships
   `pack_mb = 0`, `vram_mb = 0` (no warning) until 0.4 sets them (D6).
3. ~~Command and HTTP service backends only.~~ **Reversed by the user,
   2026-11-01: "Let's allow PyTorch backend".** The spandrel/PyTorch
   backend ships as the optional `xbr-upscale-torch` package, driven as
   a command and outside the CLI's dependencies (D7.4).
4. **The wizard offers the presets with their estimates, plus
   Configure…** (D11).
5. **`xbr enhance serve` ships** (D7.3), with the hardening above.

## Still open

No design question. The measurements still owed are listed under
"Measured" ("Still open in phase 0"); they fill D2's defaults and D6's
budgets without a further question to the user.

## Sources

- Real-ESRGAN ncnn-vulkan (MIT; flags, models): https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan
- Real-ESRGAN (BSD-3; `inference_realesrgan.py`): https://github.com/xinntao/Real-ESRGAN
- waifu2x-ncnn-vulkan (MIT; `-g -1`, Apple Silicon builds): https://github.com/nihui/waifu2x-ncnn-vulkan
- upscayl-ncnn (AGPL-3.0; macOS arm64 build): https://github.com/upscayl/upscayl-ncnn
- chaiNNer (backends; CLI `run` with `--override`, experimental): https://github.com/chaiNNer-org/chaiNNer and https://github.com/chaiNNer-org/chaiNNer/wiki/05--CLI
- spandrel (MIT; architectures; `spandrel_extra_arches`): https://github.com/chaiNNer-org/spandrel
- OpenModelDB FAQ (formats; "models carry their own licenses"; tools): https://openmodeldb.info/docs/faq
- AUTOMATIC1111 API (`--api`, `/docs`): https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API
- ComfyUI HTTP routes (`/prompt`, `/upload/image`, `/history`, `/view`): https://9elements.com/blog/hosting-a-comfyui-workflow-via-api/
- Dolphin custom textures (`tex1_<w>x<h>_<hash>_<fmt>` names, dump-then-replace): https://forums.dolphin-emu.org/Thread-is-there-a-way-to-calculate-hashes-from-original-texture-files
- Azahar/Citra custom textures (dump as PNG, load by hash): https://citra.azahar-emu.org/help/feature/custom-textures/
- PCSX2 texture replacement (per-serial folders, load textures): https://www.moddb.com/tutorials/pcsx2-qt-texture-replacement-tutorial
- DuckStation texture replacements (per-game folder, XXH3 hash names): https://repo.retrodeck.net/Xargon/Duckstation/src/branch/main/src/core/texture_replacements.cpp
- xBRZ licence (GPL-3; why the CLI keeps its own integer xBR): https://www.vogons.org/viewtopic.php?p=449925
