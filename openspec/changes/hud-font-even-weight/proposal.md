# Change: one stroke weight across the HUD pack font

## Why

The operator saw it in the README's `hud-pack.png` (2026-10-11, BLX-97):
in `Stick` the S and c look heavier than the t and k and the i thinner;
in `Time:` the i is thin and the m wide. The stock Arial Narrow Bold
atlas has an even weight.

The cause is our build, not the game. `xbr enhance hud` (CLI
`enhance/atlas.py`) draws each glyph at the band's cap height, then
stretches it on its own by `rx = stock ink width / font ink width`
across and `ry` down, so that its ink box equals the stock ink box. The
stock widths are whole 1x pixels of another typeface, so `rx` is
different for every glyph, and the stems widen or narrow with it.

Measured on the owner's dump with PT Sans Narrow Bold (148 drawn glyphs,
`runs/hudfont/rx-before.txt`):

- `rx` runs from 0.40 to 1.52 (median 0.988, standard deviation 0.157).
  81 glyphs are more than 8% off the median, 27 more than 20%.
- `ry` runs from 0.76 to 1.37, so horizontal strokes vary too: `-` is
  1.37 times as thick as the font draws it, `"` and `+` 1.26.
- The reported glyphs: `S` 1.078, `c` 1.118, `t` 0.830, `k` 1.054,
  `i` 0.778, `m` 1.071, `T` 0.936, `e` 0.841, `:` 0.810. So the S, c
  and m stems are 30-45% wider than the i and t stems. That is the
  uneven weight the operator saw.
- Much of the spread is quantisation. The narrow glyphs are 3-6 stock
  pixels wide, so one pixel is 17-33% of their width. The rest is the
  two typefaces' shapes: PT's `l` has a tail, its `f` and `1` are wider,
  and its `J` is narrower.

The user's instruction (2026-10-12, binding on this spec): "the resizing
must happen proportionally so the glyph does not deform/distort - try to
fit vertically first." So the fit scales every glyph uniformly, never one
axis alone; the scale comes from the vertical fit (the cap height), and
a glyph that would overrun across is shrunk on both axes together.

## What changes

- **CLI** (`xboxrecomp-cli`, public, game-agnostic):
  - `enhance/atlas.py` draws every glyph at one scale on both axes: the
    band's cap height, as now. There is no horizontal factor, font-wide
    or per glyph: a glyph keeps the font's proportions exactly.
  - The glyph's ink is centred on the stock ink box across, and its
    baseline sits on the band's baseline. It is no longer stretched to
    the stock box.
  - A glyph is shrunk, uniformly on both axes about its centre across
    and the baseline down, only when its ink would overrun the region
    the game samples for it (measured in task 1), and then by exactly
    what it needs to fit. `FIT` (8%) is a reporting threshold, not a
    cap: a glyph shrunk by up to 8% is silent, one shrunk further is
    named with its factor. No glyph is enlarged. A shrunk glyph is a
    little shorter (8% is 1.4 px of the 18 px cap at 1x), its baseline
    unmoved.
  - The sampled region is `[enhance.hud] font_margin` (guest pixels per
    side around the stock ink box) when the manifest gives it, else the
    slot. The probe in task 1 sets BLiNX 2's value.
  - The build prints one font-wide line (cap height, one proportional
    scale, the number of glyphs shrunk within `FIT`) and then only the
    glyphs shrunk beyond `FIT`.
  - The 0.4-2.5x mismatch guard stays, unchanged, as the test for a run
    that is not a glyph.
  - Tests and the version bump (0.6.3).
- **Game** (cat): this change, the pin of CLI v0.6.3 in `game.toml`
  (a local tag on the CLI commit first; the public tag goes out in the
  next push round, the CLI's round before cat's, as v0.3.0 did),
  `[enhance.hud] font_margin` if the probe finds a margin, and the
  `hud-pack` requirement text updated (delta below). The comment above
  `[enhance.hud] font` in `game.toml` changes from "draws each glyph
  into its stock ink box" to "places each glyph on its stock slot at
  one scale", and records the probe's result.
- **Toolkit:** nothing. The runtime swap is unchanged, so no Proton run:
  the pack is the same bytes on Metal and D3D11.

## Impact

- The pack's font entry changes: the same hash and size, other texels.
  Owners rebuild their pack with `blinx2 enhance hud`. A pack from an
  older CLI keeps working as before.
- Stock goldens do not move, because they run with `textures.pack=none`.
- The README image `docs/images/hud-pack.png` shows the old weight. It
  is retaken only with the user's approval, not in this change.
- Spacing: the game's layout does not change (it keeps its own advances
  in guest memory). A glyph narrower than its stock box now leaves a
  little more space on each side: well under a guest pixel for most
  glyphs (`B C G P S U` and the like, `rx` 1.08-1.13, 0.5-0.7 px), but
  1-2 px per side for the glyphs PT draws much narrower than Arial
  Narrow (`E` 0.95, `O` 1.1, `É Ê Ë` 1.45, `J` 1.7, `©` 2; the accented
  `O` family about 1.1), which at 2x and 3x is 2-6 screen pixels. A
  shrunk glyph (`1` 0.93 against its slot, `f` 0.90) is also a little
  shorter than its neighbours: 1.2-1.8 px at 1x. That is the price of
  one undistorted weight with the game's fixed advances, and the user
  chose it. The before/after crops check it in `Stick`, `Time:` and a
  menu string at 2x and 3x, and the user looks at them before the merge.
