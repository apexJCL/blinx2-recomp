## MODIFIED Requirements

### Requirement: The Latin atlas is rasterised onto the stock layout
With a font (`--font` as a file or an installed font's full name, else the face `[enhance.hud] font` names; PT Sans Narrow Bold for BLiNX 2), the command SHALL re-render the atlas named by `[enhance.hud] font_atlas` from the font onto the stock layout at the pack's scale. It SHALL find the atlas's bands of ink rows (alpha ≥ 64) and refuse, naming the bands, when their number differs from the number of `font_rows` strings. Per band it SHALL split the ink into column runs (a run holding several runs below the band's accent zone split at the column with the least ink between them), group the runs in order into the string's glyphs (spaces ignored) so that the sum over glyphs of the difference between the group's width and the font's ink width for that glyph is least (a glyph given no run costs its width plus the band's widest, and is reported on the terminal), and measure each glyph's ink box and slot.

It SHALL draw every glyph proportionally, at one scale on both axes: the band's cap height times the pack scale. It SHALL never scale one axis alone, so a glyph keeps the font's proportions and is not distorted, except as the two manifest keys below allow. With `[enhance.hud] font_stretch` (a percent, 0-99, default 0) each glyph's width SHALL be multiplied by its stock-to-font ink width ratio, limited to 1 ± the percent, and the command SHALL print how many glyphs stopped at the limit. Each glyph named in `[enhance.hud] font_full_height` (a string, default empty) SHALL be scaled vertically to span its stock ink box and centred on it, rather than placed on the baseline. Each glyph's ink SHALL be centred across on its stock ink box, with the font's baseline on the band's baseline. A glyph SHALL keep the baseline, descenders and overshoots included, unless the font draws it wholly above or wholly below its baseline (a dash, an underscore, a quote). The region the game samples for a glyph is its stock ink box grown by `[enhance.hud] font_margin` (stock atlas texels per side: left, top, right, bottom) when the manifest gives it, else its slot. Only a glyph whose ink would leave that region SHALL be adjusted: shifted inward by at most the slack on the other side when it overruns one side only (vertically only a glyph that may leave the baseline), then shrunk uniformly on both axes, about its centre across and about the baseline down, by exactly what it needs to fit. A shrink factor below 0.92 SHALL be reported on the terminal with the glyph and the factor. No glyph SHALL be enlarged beyond the one scale. The command SHALL print one line with the cap height and the number of glyphs shrunk. Each glyph SHALL be stored white with the coverage in alpha. A glyph the font lacks, one whose stock-to-font width or height ratio lies outside 0.4-2.5x (reported on the terminal), and one written as U+FFFD in `font_rows` SHALL keep the upscaled stock pixels. The rasteriser SHALL be the CLI's own (standard library only): TrueType `glyf` outlines, non-zero winding, 4x4 supersampled coverage.

#### Scenario: One stroke weight
- **WHEN** a synthetic atlas holds the same test-font glyph in two stock boxes of different widths, both wider than the glyph, and is rendered at 4x
- **THEN** both rendered glyphs have the same ink width and the same ink height to within one pack pixel

#### Scenario: Placed in the stock slot
- **WHEN** a glyph fits its region at the one scale
- **THEN** its rendered ink centre lies within one pack pixel of four times its stock box centre, its bottom edge is four times the band baseline, and no line names it

#### Scenario: Overrun shrunk proportionally
- **WHEN** a glyph's ink at the one scale is 5% wider than its region, and another's is 25% wider
- **THEN** both render exactly as wide as their region, each as much shorter as it is narrower, with its bottom edge still on the baseline, and only the second is named on the terminal with its factor

#### Scenario: Descenders keep the baseline
- **WHEN** a glyph that crosses the font's baseline overruns its region at the bottom, and a mark the font draws wholly below the baseline overruns it too
- **THEN** the first is shrunk uniformly with its baseline at four times the band baseline, and the second is moved up into the region at its natural size

#### Scenario: No distortion
- **WHEN** the synthetic atlas is rendered with stock boxes wider, narrower and taller than the glyphs they hold
- **THEN** every rendered glyph's ink width over ink height equals its outline's ratio to within one pack pixel on each side

#### Scenario: The sampled region from the manifest
- **WHEN** `[enhance.hud] font_margin` is given and a glyph's ink at the one scale fits its slot but not its stock ink box grown by the margin
- **THEN** the glyph is shrunk to the grown box; without the key it is drawn unshrunk in its slot

#### Scenario: Stock pixels kept
- **WHEN** `font_rows` holds a glyph the test font lacks and a U+FFFD glyph
- **THEN** their pixels equal the xBR-upscaled stock pixels

#### Scenario: Rows do not match the atlas
- **WHEN** `font_rows` has one string more than the atlas has ink bands
- **THEN** the command refuses with the band count and the rows found, and writes no pack

#### Scenario: Stage-1 HUD text in place
- **WHEN** Metal `@stage1` runs with the pack at render scale 2 and 3, and the frames with `Time:`, the name plate and a menu string are captured at render size
- **THEN** no glyph is cut at its quad's edge or touches a neighbour, no glyph is stretched or squashed on one axis by more than `font_stretch`, and the stems of `S c t k i m` in `Stick` and `Time:` are of one width to within the font's own design, 8% and `font_stretch`

#### Scenario: Widths towards stock, bounded
- **WHEN** `font_stretch` is 10 and a glyph's stock ink box is 20% wider than its font ink at the one scale, and another's is 5% narrower
- **THEN** the first is drawn 10% wider and counted in the line of glyphs stopped at the limit, the second exactly as wide as its stock box, and both keep their height

#### Scenario: Brackets span the stock ink box
- **WHEN** `font_full_height` names a glyph whose font ink reaches further below the baseline than its stock ink box
- **THEN** its rendered ink spans four times the stock box's top and bottom rows, its width is the one scale's times any stretch, and no line names it
