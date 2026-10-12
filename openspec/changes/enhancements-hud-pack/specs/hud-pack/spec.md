## ADDED Requirements

### Requirement: The owner builds the HUD pack from their own dump
`blinx2 enhance hud [--scale 2|4] [--out DIR] [--font PATH] [--jobs N] [--only PATTERN]... [--list]` (the CLI's `xbr enhance hud`) SHALL read the `IPK1` archives named by `game.toml` `[enhance.hud] archives` under the game files directory, read-only, select the entries whose names match `[enhance.hud] textures` (fnmatch patterns with `/` separators, case-insensitive, narrowed by `--only`), decode each selected DDS (DXT1, DXT3, DXT5 without mip chains; any other format or a chain is skipped with a line naming the entry), hash its data block with the toolkit's `nv2a_tex_hash`, upscale it by `--scale` (default `[enhance.hud] scale`, 4) with the integer xBR kernel, and write `DIR/hud.pack` (default `dist/enhance/hud/`) and `DIR/hud-pack.toml` (tool version, kernel, scale, the XBE's sha256, the font's sha256 when used, and per entry the archive, name, hash, guest size and pack size). `--list` SHALL print the selected entries with their hashes and sizes and write nothing. Two runs of the same CLI commit on the same dump with the same options SHALL write byte-identical packs on any host.

#### Scenario: Default set from the dump
- **WHEN** `blinx2 enhance hud` runs on the owner's dump with the font given
- **THEN** `dist/enhance/hud/hud.pack` holds one entry per selected DXT texture at 4x, `hud-pack.toml` names them, the font atlas entry is rasterised rather than upscaled, and the command prints the entry count and the time taken

#### Scenario: Reproducible
- **WHEN** the command runs twice with the same options, or with `--jobs 1` and `--jobs 8`
- **THEN** both `hud.pack` files are byte-identical

#### Scenario: Font absent
- **WHEN** `--font` is not given and no face of the host's font folders has the full name `[enhance.hud] font` gives
- **THEN** the command says which font to install, and the atlas entry is upscaled like every other texture

#### Scenario: Font found by name
- **WHEN** `--font` is not given and a `.ttf`, or a face of a `.ttc`, in the host's font folders has that full name
- **THEN** the command uses that face and prints its name and file

### Requirement: The Latin atlas is rasterised onto the stock layout
With a font (`--font` as a file or an installed font's full name, else the face `[enhance.hud] font` names; PT Sans Narrow Bold for BLiNX 2), the command SHALL re-render the atlas named by `[enhance.hud] font_atlas` from the font onto the stock layout at the pack's scale. It SHALL find the atlas's bands of ink rows (alpha ≥ 64) and refuse, naming the bands, when their number differs from the number of `font_rows` strings. Per band it SHALL split the ink into column runs (a run holding several runs below the band's accent zone split at the column with the least ink between them), group the runs in order into the string's glyphs (spaces ignored) so that the sum over glyphs of the difference between the group's width and the font's ink width for that glyph is least (a glyph given no run costs its width plus the band's widest, and is reported on the terminal), and measure each glyph's ink box. It SHALL render each glyph at the band's cap height times the scale, then again condensed or widened and shortened or lengthened so its ink box equals the stock ink box times the scale, place it there, and store it white with the coverage in alpha. A glyph the font lacks, one whose fit would stretch the glyph outside 0.4-2.5x (reported on the terminal), and one written as U+FFFD in `font_rows` SHALL keep the upscaled stock pixels. The rasteriser SHALL be the CLI's own (standard library only): TrueType `glyf` outlines, non-zero winding, 4x4 supersampled coverage.

#### Scenario: Fitted glyphs
- **WHEN** a synthetic atlas of bands holding rectangles at known boxes is rendered with the test font at 4x
- **THEN** every rendered glyph's ink box equals four times its stock box, and the pixels of a glyph the test font lacks and of a U+FFFD glyph equal the xBR pixels

#### Scenario: Rows do not match the atlas
- **WHEN** `font_rows` has one string more than the atlas has ink bands
- **THEN** the command refuses with the band count and the rows found, and writes no pack

#### Scenario: Stage-1 HUD text in place
- **WHEN** Metal `@stage1` runs with the pack and dumps the frame with `Time:` and the name plate
- **THEN** each glyph's ink box, divided by the scale, lies within one guest pixel of the stock dump's ink box for the same glyph

### Requirement: Packs and game-derived images stay out of every repository
A pack, its manifest, a decoded texture, a frame or an atlas crop SHALL never be committed: `*.pack` and `enhance/` are gitignored in the game, `dist/` already is, and the CLI's `scripts/audit-public.sh` SHALL flag `*.pack`. Every test of the archive reader, the DDS decoder, the scaler, the font rasteriser, the atlas fit, the pack writer and the command SHALL build its own fixtures in a temporary directory (archives, DDS blocks, a TrueType font, packs); no test SHALL read the game files. The font file SHALL NOT be vendored; if it ever is, its licence text (the SIL Open Font License 1.1 of PT Sans Narrow) comes with it and `NOTICE` names it.

#### Scenario: Audit clean
- **WHEN** `scripts/audit-public.sh main..HEAD` runs on the CLI branch and `git status` runs in the game after a pack was generated
- **THEN** the audit is clean and the pack is neither untracked nor staged

#### Scenario: Tests without a dump
- **WHEN** `uv run pytest tests` runs on a host with no game files
- **THEN** every `enhance` test passes
