## ADDED Requirements

### Requirement: Pack entries carry a kind, a scale of their own and an optional BC3 payload
`blinx2 enhance hud` (the CLI's `xbr enhance hud`) SHALL write version-2 packs: each entry's `flags` SHALL name its kind (`0` art for `.dds` textures, `FONT` for the entry named by `[enhance.hud] font_atlas`, `TEXT` for images read from `MIXF`/`XPR0` containers and for entries matching `[enhance.hud] text` patterns) and, where chosen, `XRTP_FLAG_BC3` with the payload encoded as BC3 blocks by the CLI's own deterministic integer DXT5 encoder. Each kind SHALL be built at its own scale (art `[upscale] scale`, default 4; text `[text] scale`, default 2); the header's `scale` is the art scale. `[enhance.hud] languages` in `game.toml` SHALL group archives by language and `[text] languages` in the config SHALL select which are built. `hud-pack.toml` SHALL record per kind the entry count, the scale, the BC3 count and the bytes. Two runs with the same config SHALL write byte-identical packs on any host, BC3 included.

#### Scenario: Kinds and scales
- **WHEN** the command runs on a synthetic tree with one `.dds` HUD piece, one font atlas and one `MIXF` text image with `[text] scale = 2, bc3 = true`
- **THEN** the pack has three entries flagged art, `FONT` and `TEXT|BC3`, the text entry is at 2x in BC3 blocks, the others at 4x in A8R8G8B8, and `hud-pack.toml` lists `text: 1 entry, scale 2, 1 bc3`

#### Scenario: Language left out
- **WHEN** `game.toml` names `languages = { us = ["lng_us"], jp = ["lng_jp"] }` and the config selects `["us"]`
- **THEN** no entry from `lng_jp` is in the pack and `--list` shows them as `skipped: language jp not selected`

#### Scenario: BC3 vector shared with the runtime
- **WHEN** the encoder runs on the 4x4 block the toolkit's `tests/tex_pack` fixes
- **THEN** the 16 bytes equal the toolkit test's vector

### Requirement: The preview tool
`blinx2 enhance preview [--config FILE] [--port N] [--no-browser]` SHALL start a local HTTP server bound to `127.0.0.1` on a random or given port, open the page in the default browser, and serve one HTML page with no external resource. The page SHALL list the `[enhance.hud]` set from the owner's dump grouped by kind and language with `[enhance.hud] preview` entries first and a size readout per group (entries, raw and BC3 bytes at the chosen scales); SHALL render a chosen crop of a texture at 2x, 3x or 4x side by side through `nearest`, `xbr` (level, `eq`, weights, alpha edge), `epx`, `lanczos` (fixed-point) and, when configured, `external` (the owner's own command), each with its time, with raw beside BC3 on request; SHALL accept a `RECOMP_TRACE=tex_pack` log and list its missed candidate hashes joined to the dump's entries (hash only for unknown ones); in font mode SHALL show the stock atlas row, the fitted row and a free-text line rendered through the real fit for a face chosen from the installed fonts, three curated OFL faces, a font file the owner drops on the page or picks (stored in the per-user cache under its sha256; CFF outlines refused), or a Google Fonts family fetched from the google/fonts repository (`ofl/`, `apache/` or `ufl/` only, at a pinned commit, the TTF and its licence file stored together in the per-user cache, never in the tree), with `size`, `weight`, `dx`, `dy`, `outline`, `shadow` and `overhang` knobs and a mark where two glyphs would touch; SHALL offer external upscalers only as command templates the owner fills, with presets for local open-source tools found on the host and no network call of its own; and SHALL save the choices to `enhance-hud.toml` (default `config/enhance-hud.toml`). Every image SHALL be rendered in Python by the modules the pack build uses and encoded as PNG in memory; the tool SHALL write no image to disk and nothing but the config file and the font cache.

#### Scenario: Side by side
- **WHEN** the page requests a 64x64 crop of the life bar at 4x
- **THEN** it receives one PNG per filter with the filter's parameters applied and the time each took, and the `xbr` PNG at the default parameters equals the crop of what `enhance hud` writes for that texture

#### Scenario: Log import
- **WHEN** a log with `[TEXPACK] miss 0123456789ABCDEF 512x32 DXT3 x400 candidate` is posted and the dump holds an entry with that hash
- **THEN** the page lists the entry's archive and name as "seen at runtime, not in the pack"; a hash the dump does not hold is listed as hash only

#### Scenario: Font text line
- **WHEN** the owner types `Time: 00:42`, picks a curated face not yet cached and sets `weight = 1`
- **THEN** the face and its licence file are downloaded once to the cache with their sha256s verified, the line is rendered through `atlas.render` with the stroke, and no file appears under the game tree

#### Scenario: Google Fonts family
- **WHEN** the owner pastes `https://fonts.google.com/specimen/Roboto+Condensed` and asks for weight 700
- **THEN** the tool reads `ofl/robotocondensed/METADATA.pb` at the pinned commit, downloads the static Bold file and `OFL.txt` into the cache, and the saved config names the family, file, URL, licence file and both sha256s

#### Scenario: Own font imported
- **WHEN** the owner drops a `.ttf` on the page
- **THEN** it is stored in the cache under its sha256 with the face name read from the file, appears in the selector, and the saved config names it by face and sha so the build refuses another file

#### Scenario: Local only
- **WHEN** the server runs
- **THEN** it listens on `127.0.0.1` only, serves no path outside its page and image routes, and exits on `/quit` or Ctrl-C

### Requirement: The pack build consumes the preview config
`blinx2 enhance hud --config FILE` (default `config/enhance-hud.toml` when it exists) SHALL apply per kind the scale, filter, parameters and BC3 choice, then the `[override."<pattern>"]` tables per entry, the `[font]` face and knobs in the atlas fit, and `[text] languages`; it SHALL refuse a font file whose sha256 differs from the config's. `hud-pack.toml` SHALL record the config's path and sha256. Without a config the art and font entries SHALL have the same texels as before this change.

#### Scenario: Reproducible from a config
- **WHEN** the owner saves a config from the preview tool and runs `enhance hud --config` twice, on two hosts
- **THEN** the packs are byte-identical and `hud-pack.toml` names the config and its sha

#### Scenario: No config, same texels
- **WHEN** the command runs without a config on the synthetic tree of the existing end-to-end test
- **THEN** every art and font entry's payload bytes equal the previous version's, the header is version 2 and the flags name the kinds

#### Scenario: Config only names and numbers
- **WHEN** `scripts/audit-public.sh` runs on a branch that adds `config/enhance-hud.toml`
- **THEN** the audit is clean: the file holds filter names, numbers, font names, URLs and hashes, and no game bytes
