## Context

- `enhancements-hud-pack` design D5 introduced the atlas fit.
  `xbr enhance hud` measures the stock Latin atlas
  (`dds/font_arialnarrow_bold.dds`, 256x256, ten bands, 148 glyphs fitted
  with PT Sans Narrow Bold). Per glyph it records:
  - the slot: the band's rows between the midpoints of the gaps to its
    neighbours;
  - the ink box (alpha >= 64);
  - per band, the baseline and the cap height (18 px in every band).
- `render()` then draws each glyph twice. The second pass uses
  `px * rx` across and `px * ry` down, so its ink box equals the stock
  box times the scale.
- The game lays text out from its own table, which the HUD spike did not
  find. The stock atlas stays in guest memory: the swap is host-side, at
  texture upload. So what a replacement must preserve is which atlas
  texels each glyph quad samples. Drawing the ink exactly in the stock
  box meets that trivially. It is also what makes the weight uneven.

Numbers on the owner's dump (`runs/hudfont/rx-before.txt`,
`simulate*.txt`; the scripts are in `wt/hudfont/tools/`, local only):

| | min | median | max | notes |
|---|---|---|---|---|
| `rx` (all 148) | 0.40 (`\`) | 0.988 | 1.52 (`J`) | 81 glyphs off the median by more than 8% |
| `rx` (stock width >= 6 px, 124 glyphs) | | 1.031 | | narrow glyphs bias the median down: 1 px is 17-33% of their width |
| `ry` | 0.76 (`_`) | 0.983 | 1.37 (`-`) | |

These are the glyphs that would overrun at the cap-height scale with the
font's own proportions (`simulate-cx1000.txt`), by the region the game
may sample; the shrink each needs is uniform, so it is also how much
shorter the glyph gets:

| region the game samples | shrink within 8% | shrink beyond 8% |
|---|---|---|
| bare ink box | 32 | 44 |
| ink box + 1 guest px on each side | 7 (`1 6 l x Ï ß ß`) | 4 (`/` 0.81, `\` 0.60, `f` 0.90, `ï` 0.87) |
| slot | 10 (`1 6 V X l x y ß î ß`) | 6 (`\` 0.60, `f` 0.90, `Í` 0.86, `Î` 0.91, `Ï` 0.86, `ï` 0.87) |
| slot, with the vertical need (as built) | 16 (`$ 1 6 Q V X j l p q x y Ç ß î ß`) | 14 (`\` 0.60, `(` `)` 0.884, `[` `]` `{` `}` 0.845, `f` 0.904, `g` `¿` 0.917, `Í` 0.864, `Î` 0.907, `Ï` 0.859, `ï` 0.873) |

(`\` is below the 0.4 mismatch guard either way and keeps its stock
pixels. An earlier draft of this design put a font-wide horizontal factor
of 1.031 on every glyph, the median `rx`; `simulate-cx1031.txt` has those
numbers, 59/6/9 beyond 8%. The user ruled out any one-axis scaling, so
the factor is gone and the counts above are the ones that matter.
`simulate.py` counts the horizontal need only. The last row adds the
vertical one: PT's descenders, `$`, `Q`, `Ç` and the brackets reach
further below the baseline than the slot does, so they shrink about the
baseline too; see the result under D1.)

So the answer depends on which region the game's quads sample, and that
is measured first (D1). In the two plausible cases (ink box + 1 px, or
the slot) four to six glyphs are named, each a real shape difference
between the typefaces (`f`, `ï` and the accented `I` are wider in PT).

A search of `default.xbe` and of the small `media`/`lng_us` entries for
the digit row's left edges or widths found no table. It tried int8,
int16, int32 and float values, raw and over 256, at strides up to 40
bytes and offsets of -2 to +2. The game may build the table at load
time, or keep it in a form the search did not cover. D1 therefore
measures the region at runtime instead of reading the table.

## Goals / Non-Goals

**Goals:**
- One stroke weight across the font, with no distortion. Every glyph is
  drawn at one scale on both axes, and only a glyph that would overrun
  the sampled region is shrunk, uniformly, by what it needs (the user:
  "proportionally so the glyph does not deform/distort - try to fit
  vertically first").
- The layout stays as it is: each glyph's ink stays inside the region
  its quad samples, centred where the stock ink is, on the stock
  baseline.
- The build says what it did: one font-wide line, plus one line per
  glyph that needed more than the bounded adjustment.
- Packs stay reproducible, byte-identical on every host.

**Non-Goals:**
- Changing the game's advances or kerning (they live in guest memory).
- Hinting, emboldening or stem-darkening filters.
- The Century Gothic atlas, which stays on the xBR path.
- Retaking the README image (that needs the user's approval).

## Decisions

### D1. Measure the region each glyph quad samples (probe pack)

A local script, `wt/hudfont/tools/probe_pack.py` (never committed, since
its output is game-derived; it goes to `notes/hudfont/` after the merge),
writes a pack with one entry: the font atlas's hash, at 4x. The script
uses the CLI's own `atlas.measure`, `texhash` and `pack.write`, so the
rings sit around the same alpha >= 64 ink box the fit uses. Every glyph
slot in it is painted in concentric rings around the stock ink box, in
grey levels:

- the ink box itself: 255;
- the 1st guest pixel outside it: 191;
- the 2nd: 127;
- the 3rd and beyond, up to the slot edge: 63.

All of it is at alpha 255, and the rest of the atlas is transparent. Grey
levels, not hues: the game multiplies the atlas by the vertex colour, and
a tint that zeroes a channel (yellow, red) would erase a blue or green
ring, while four grey levels keep their order in every channel the tint
leaves. The level on screen is read relative to the ink's.

`@stage1` then runs on Metal at `render.scale` 2 with this pack. One HUD
frame with the name plate and `Time:` is captured with
`RECOMP_DEBUG=window_shot=<flips>` (an SDL window shot at render size)
and read locally (`runs/hudfont/probe/`). The levels that show around
each glyph give the sampled margin per side, in guest pixels. `fb_dump`
(640x480, one pixel per guest pixel) is enough to read a 1-guest-px ring
too, so the probe does not depend on a render-size frame; the render
size only makes the reading easier.

- A ring of at most 1/8 guest pixel is bilinear bleed at the quad edge,
  not sampling. A full ring (four pack texels or more) is sampled.
- Whether the margin is the same for every glyph, and whether vertically
  the quad spans the ink box or the whole band, is read the same way.
  Soft stock edge pixels under alpha 64 lie outside the measured ink box
  and will show as part of the margin; that is wanted, since the fit
  measures the same box.

The result defines the **allowed box** `A` per glyph, in pack pixels: the
stock ink box grown by the measured margins and clipped to the slot. It
is written to `game.toml` as `[enhance.hud] font_margin` (D3), left
absent when the margin reaches the slot. If the margin differs between
glyphs, the smallest seen per side is used: a margin that is too small
only spaces a glyph more tightly inside its quad, one that is too large
cuts an edge.

- **Gate:** if the probe shows the game samples the bare ink box (no
  full ring on either side), 44 glyphs would be shrunk beyond 8% and sit
  1.5-4 px lower than the cap line. The implementing agent then stops
  and hands back with the frame and `simulate.py`'s output, because the
  remedy needs a decision:
  1. a font-wide uniform scale below the cap height (0.95, 0.9), so that
     nearly every glyph fits at one size. Proportions and weight stay
     even, which is the goal; the whole font gets that much smaller than
     the stock cap;
  2. accept up to 1 guest px of clipped edge on the overrunning glyphs;
  3. widen `FIT`, which only silences the notes: the glyphs are shrunk
     the same, and the heights are uneven.
- **No frame at all** (the game does not run with the probe pack, or
  neither `window_shot` nor `fb_dump` yields the HUD): stop and hand back
  as well. Neither guess is safe: `A` = slot cuts edges on up to 76
  glyphs if the game samples the bare box, `A` = bare box shrinks 76
  glyphs (44 beyond 8%) if it samples the slot, and without a frame the
  crops that would catch either cannot be made.

**Result (2026-10-12, `runs/hudfont/probe/`).** The game samples the
whole slot. On the `Time:` plate and the `TS-2000 LV1:` panel at render
scale 2 (window shot, 4 shot pixels per guest pixel), every ring shows:
between `2` and `0` the second ring of `0` is sampled in full up to the
slot edge, the rings run up to the slot top above the lower case and
past its bottom, and the last glyph's quad reaches past its slot. The
gate is not tripped. `A` is the slot on every side, so BLiNX 2's
`game.toml` gets no `font_margin` key. With it, the build names the
glyphs the slot table above predicts: 10 shrunk within 8%, and `f` 0.90,
`Í` 0.86, `Î` 0.91, `Ï` 0.86, `ï` 0.87 beyond; `\` keeps its stock
pixels.

That first build shifted 13 glyphs off the baseline without a note
(the review): whether a glyph might move down was decided from its
stock ink bottom, so every Arial descender and overshoot counted as off
the baseline, and `g ¿` rose 0.45 guest px, `( )` 0.66, `[ ] { }` 0.92,
`Q Ç j p q` 0.14-0.40 and `$` dropped 1.57. The font outline decides
now (D2.3), and the build names: 16 shrunk within 8%; `( )` 0.88,
`[ ] { }` 0.85, `f` 0.90, `g` `¿` 0.92 (0.917), `Í` 0.86, `Î` 0.91,
`Ï` 0.86, `ï` 0.87 beyond; `\` stock. Only `_` still moves (up 0.76
guest px, into its slot).

### D2. The fit: one proportional scale, placed in the slot

Per glyph that the font has, that is not U+FFFD and that has a run, all
in pack pixels:

1. **One scale, from the vertical fit:** `k = cap * scale / cap_units`
   per band, as now, on both axes. Every band of the BLiNX 2 atlas has
   the same cap, so this is one scale for the whole font. There is no
   horizontal factor of any kind: the glyph keeps the font's proportions,
   so its stems, counters and curves are the font's. (PT Sans Narrow Bold
   is about 3% narrower than Arial Narrow at the same cap; that shows as
   a hair more space inside the stock boxes, not as a change to the
   glyph.)
2. **Placement.**
   - Across: the centre of the font's outline box goes on the centre of
     the stock ink box. Centring splits the stock box's whole-pixel
     rounding between both sides; keeping the left edge would put all of
     it on the right.
   - Down: the font's baseline (y = 0) goes on the band's baseline.
   - The origin is a float. The rasteriser already takes one
     (`font.render(gid, px_x, px_y, ox, oy, ...)`), and its doubles are
     evaluated in a fixed order, so the result is still host-independent.
     The coverage-box shift of today's code goes away.
3. **Overrun: a uniform shrink.** Let the natural ink box be the outline
   box at `k` at that origin, and let `A` be the allowed box (D1).
   - If the natural ink overruns `A` on one side only and `A` has slack
     on the other, the glyph is first shifted inward by up to that slack
     (across: within the box; down: only for a glyph the font draws
     wholly above or wholly below its baseline, such as `_`, `-` or a
     quote). Every other glyph keeps the baseline, descenders and
     overshoots included: the stock ink cannot decide this, because
     Arial's descenders end off the baseline too.
   - If it still overruns, the glyph is shrunk by one factor
     `f = min(A_w / natural_w, A_h / natural_h, 1)` on both axes, about
     the centre of the stock ink box across and about the baseline down.
     A shrunk glyph is `(1 - f) * cap` shorter: at `FIT` that is 1.4 px
     of an 18 px cap at 1x; its baseline does not move.
   - `f` within `[1 - FIT, 1]`, `FIT = 0.08`, is applied silently. The
     stem changes by at most 8%, 0.2 guest px on a 2.8 px stem.
   - Below `1 - FIT` the glyph is still fitted, so it never overruns
     its neighbour or its quad, and the build names it with its factor
     (D4). `FIT` decides what is reported, never how a glyph is drawn.
   - A glyph smaller than `A` is never enlarged.
4. **Mismatch guard, unchanged.** The 0.4-2.5x test on the stock-to-font
   ratio still marks a run that is not the glyph (`\` today). Such a
   glyph keeps its stock pixels, and the build reports it.

The dot of an `i` and the marks of `"` stay apart. The glyph is not
stretched down anymore, so the gap rows the font has are kept. Vertical
overruns happen even with the slot as the region: PT's descenders, `$`,
`Q`, `Ç` and the brackets reach below the slot, and the accented
capitals above it. The shrink in step 3 handles them like a horizontal
overrun, about the baseline. Had the quads spanned only the ink rows,
35 glyphs would have left the stock rows by 0.8-3.6 px.

### D3. Constants

One constant joins `STRETCH` and `ACCENT` in `atlas.py`, with a comment
that says why: `FIT = 0.08`, the largest silent per-glyph shrink. It
describes the fit, not the game, so it stays out of `game.toml`.

The region the game samples is a property of the game, so it is a
manifest key, always implemented: `[enhance.hud] font_margin = [left,
top, right, bottom]`, stock atlas texels outside the stock ink box (guest
pixels when the game draws its text 1:1), documented
in the CLI's `docs/manifest.md`; absent means the slot (the most ink the
atlas holds without touching a neighbour). `hud.py` reads it and passes
it to `atlas.render`. D1 sets BLiNX 2's value: the key is written when
the probe finds a margin short of the slot, left out otherwise. Another
game sets its own.

### D4. What the build prints

- Once: `font: cap 18 px, one proportional scale; N glyphs shrunk
  within 8% to fit their slot`.
- Per glyph beyond `FIT`: `'f': shrunk 0.90 to stay in its slot
  (more than 8%: it is thinner and shorter)`.
- The existing notes stay (not in the font, no run of its own, not
  matched).

`render()` returns the notes as before. `hud.py` prints them under the
atlas line, so the command's output stays the one place to see them.

### D5. Tests (CLI, synthetic only)

The test font gains no glyph shapes beyond rectangles. Rectangles make
every ink edge exact, so stem widths are directly comparable.

1. **One weight.** Two glyphs with the same outline sit in stock boxes
   of different widths, both wider than the glyph's natural width. They
   render with equal ink widths and heights, to within one pack pixel.
   Under the old fit they differ by the ratio of the boxes.
2. **Centred on the baseline.** A rectangle glyph's rendered ink centre
   is the stock box centre (to within one pack pixel), and its bottom
   edge is the baseline times the scale.
3. **Overrun within FIT, proportional.** A stock box 5% narrower than the
   natural ink renders exactly the allowed width, 5% shorter, with its
   bottom edge still on the baseline, and no note is printed.
4. **Overrun beyond FIT.** A box 20% narrower renders inside the box,
   20% shorter, and exactly one note names the glyph with `0.80`.
5. **No distortion.** For every rendered glyph, ink width over ink
   height equals the outline's ratio to within one pack pixel on each
   side, whether its stock box is wider, narrower or taller than the
   glyph.
6. **Margin.** With `font_margin` given, a glyph fits the ink box grown
   by it and not the slot; without it, the slot.
7. **Unchanged paths.** The U+FFFD glyph, the glyph the font lacks, and
   a glyph without a run behave as today. The `i` dot stays separate.
8. **Vertical fit and shifts.** A glyph wider than its stock box but
   not its slot moves across at its natural size, from either side,
   unnamed. An accent past the slot top and a descender past its bottom
   shrink uniformly with the baseline kept (the descender pins the rule
   in D2.3). A mark drawn clear of the baseline past the slot moves into
   it unshrunk. A stock box taller than its glyph does not enlarge it.
9. The reproducibility test (`--jobs 1` and the default give the same
   sha256) stays green.

Test names, docstrings and fixtures stay game-agnostic (rectangles and
letters, no BLiNX 2 glyph lists or numbers from the dump).

`test_atlas_fit`'s assertion "ink box equals four times the stock box"
is replaced by tests 1-4: equality with the stock box is exactly what
this change drops.

### D6. Verification on the owner's dump (Mac, Metal)

- **Packs.** Two packs that hold only the font atlas
  (`--only 'dds/font_*'`, about 4 MB each instead of 159 MB; the Mac
  disk is at 95%):
  - `runs/hudfont/pack-before` from CLI main (a018aea);
  - `runs/hudfont/pack-after` from the branch.
- **Atlas contact sheet.** `runs/hudfont/atlas-before.png` and
  `atlas-after.png` show all 148 glyphs, on a dark ground, with the
  stock slots outlined.
- **Stem widths.** `runs/hudfont/stems.txt` holds, for the straight-stem
  glyphs `H I T i l t k h n m E F L` and the reported `S c`, the ink run
  width at the middle of the x-height (or the cap height), before and
  after, and the ink height of the capitals and digits. The expected
  spread after is the font's own design (PT Sans Narrow Bold stems agree
  within a few %) plus at most `FIT` on the shrunk glyphs. Before, it
  runs to about ±25%.
- **HUD crops.** `@stage1` on Metal at `render.scale` 2 and 3 with each
  pack, through `notes/mac-run-lock.sh` with `SDL_AUDIODRIVER=dummy`.
  The frames are captured at render size with
  `RECOMP_DEBUG=window_shot=<flips>` (`fb_dump` downsamples to 640x480).
  They give 1:1 crops of `Stick`, `Time: 0'..` and `Press the A Button`,
  before and after side by side, in `runs/hudfont/crops/`. Nothing is
  published.
- **Spacing and height.** On the crops, no glyph touches or crosses into
  a neighbour, the gaps in `Time:` and `Stick` look even, and the
  shrunk glyphs (`1` in the digits, `f`) are no shorter than the design
  predicts (D2.3).
- **The user looks.** The change is a look the user flagged, so the
  crops go to the user and the merge waits for their verdict: even
  weight, no distortion, acceptable gaps and heights.
- **Goldens.** The stock Metal goldens stay unchanged (pack `none`).
  No toolkit code changes, so no Proton run; the pack is the same bytes
  on D3D11.

### D7. Public CLI hygiene

- The CLI commit text explains the change in game-agnostic terms: "one
  scale for the whole font; a per-glyph adjustment only to stay inside
  the stock slot".
- It cites no tracker refs, host names or private paths, and no numbers
  from the dump beyond what the docs already say.
- The CLI bumps to 0.6.3 (`__init__.py`), and the docs line in
  `docs/manifest.md` or the enhance docs that describes the fit is
  updated.
- `scripts/audit-public.sh a018aea..HEAD` is clean.

### D8. After the crops2 review: stock widths and full-height brackets

The user's look at `crops2` (2026-10-12) raised four points. Measured on
the stock atlas, the packs and the screen:

- **Text sits high in `( )`; caps sit high in stock `[ ]`.** The game
  draws each glyph as its slot quad and advances by the slot width times
  the text scale (about 0.833 for stage text, 0.667 in menus); every
  glyph's position is the same with any pack, only the ink in the slot
  differs. Arial's parens and brackets start at the cap top and descend
  4 texels below the baseline (stock rows: parens 1-23, brackets 2-24
  against caps 2-20 relative to the slot top), so in stock the caps look
  high inside them: that is the font's design, not the renderer. PT
  Sans's brackets, kept on the baseline at the one scale and shrunk,
  dropped 2-2.75 texels below the cap top (`(` 3-24, `[` 4.75-25): that
  part was ours.
- **The new `S` looks spaced wide.** The advances are the game's, and PT
  Sans Narrow's `E S O` are narrower than Arial's (`E` 9 vs 11, `S` 10
  vs 11, `O` 12.5 vs 15 texels), so the gaps around them opened: ours.
- **A yellow edge on the stock `R` at render scale 3.** A one-column
  line between `R` and `]` at about guest x 221, in pack-before and
  after2 alike, at x3 only. No ink sits within a texel of either seam in
  the pack, and the pack is uploaded without mips. Not settled
  statically: it needs a true stock run (no pack) at x3 with linear and
  with `RECOMP_DEBUG=metal_point`. If stock shows it with linear and not
  with point, it is the game's rect sampled past the slot at a higher
  render scale: a renderer finding, not fixed here.
  **Result (true stock runs, 2026-10-12):** the line is in stock with no
  pack at render scale 3 (guest x 220.75-221, rows 39-41) and not at 1x,
  and it is gone with `metal_point`; pack-after3 shows the same faint
  line, also gone with point. The `]` quad's first render pixels at 3x
  sample within half a texel of its left edge, and bilinear filtering
  blends in the last ink column of `\`, its atlas neighbour across one
  empty column. That is the game's UV rect at a higher render scale: a
  renderer finding (render scale >1 linear filtering bleeds
  the neighbouring atlas glyph), not the font.

The fix, in the CLI (`render(..., stretch, full)`) and named here:

1. **`font_stretch = 10`.** Each glyph's horizontal factor moves from 1
   towards its stock-to-font ink width ratio, limited to ±10%. After:
   `S` 11 (stock 11), `E` 10 (11, at the limit), `O` 14 (15), `W` 17
   (17). 64 glyphs stop at the limit. This is the one-axis scaling D2
   ruled out, bounded: the user asked for the spacing to match stock.
2. **`font_full_height = "()[]{}"`.** These glyphs are scaled vertically
   to span the stock ink box and placed on it, not on the baseline:
   `( )` 1-23 and `[ ]` 2-24, equal to stock; `[` is 5 texels wide
   against stock's 4.
3. Shrinks after both: 10 glyphs within 8%, `g` and `¿` at 0.92; `\`
   keeps the stock pixels (the 0.4-2.5x guard).

**Trade-off.** The stretch brings back some stem spread: straight stems
measure 2.75-3.5 texels after (`H` 3.5, `I T` 3.0, `i l t` 2.75,
`h n m` 3.25, `E F L` 3.5), against 3.0-3.25 in after2 and 1.75-3.75
before. A smaller `font_stretch` trades spacing back for evenness.

Checked on game-like mocks (`runs/hudfont/mock/`: slot advance, aligned
baselines, from each pack; `*-before-after2-s5-s10.png` compares
`font_stretch` 5 and 10) and on screen (`runs/hudfont/crops3/`, true
stock over after2 over after3, x1-x3): at 1x the stock `[` spans rows
27-45 with the caps at 27-42, after2's 29-46, after3's 27-45 again.

## Risks / Trade-offs

- **The probe is on the critical path.** Without its frame the work
  stops (D1): neither guess for the region is safe. The capture has two
  routes (`window_shot`, `fb_dump`), so this is unlikely; the gate on a
  bare-box result is the real decision point.
- **Glyphs named beyond FIT are smaller.** These are the font-shape
  mismatches (`f`, `ï`, `Í Î Ï`, `/` in the ink+1 case): a uniform shrink
  makes them thinner and shorter together, 1.6-3.4 px below the cap or
  accent line at 1x. The alternative, letting them overrun, would draw
  into ink the game does not sample, or into a neighbour. Four to six
  named glyphs is much better than today's 81 silent ones.
- **Shrunk glyphs within FIT are a little shorter too.** `1` against its
  slot (0.93) sits 1.2 px lower than `0` and `2` at 1x, 2.4 px at 2x,
  in every `Time:` reading. The user chose proportional scaling over
  distortion knowing a shrunk glyph gets shorter; the crops show the
  digits for their verdict.
- **The look changes for everyone who rebuilds.** Packs are owner-made
  and opt-in, so this is a rebuild, not a migration.
- **The proportions are PT's own**, at one scale. That is the point of
  the change: the weight is even and the font looks like PT Sans Narrow.
  It no longer looks like PT reshaped glyph by glyph into Arial's boxes.
- **Gaps grow around the glyphs PT draws narrow** (`E J O ©`, the
  accented `E` and `O`): 1-2 px a side at 1x. The advances are the
  game's; D8's bounded stretch closes most of it, at the cost of a
  2.75-3.5 texel stem spread.

## Alternatives considered

- **Keep the per-glyph stretch and compensate the stems** (an emboldening
  or thinning pass inverse to `rx`). This keeps the stock ink boxes
  exactly, but stem compensation on outlines needs offset curves and
  joins, which is a lot of code in a stdlib-only rasteriser. It would
  still distort the counters and the curves.
- **Clamp the stretch to ±8% without the probe** (stretch toward the
  stock box but no further). This lowers the spread but keeps it:
  within 0.92-1.08 the `i`/`S` difference would still be 16%, and the
  overruns then go unmeasured.
- **One scale, no overrun handling.** For 11-76 glyphs, depending on
  the region, the ink would leave what the game samples: cut edges in
  game.
- **A font-wide horizontal factor** (the first draft: every glyph
  condensed by the median `rx`, 1.031, so PT's average width matches
  Arial Narrow's). Rejected by the user: no one-axis scaling, however
  small. It also raised the overrun counts (59/6/9 beyond 8% against
  44/4/6).
- **A horizontal-only condense for the overrunning glyphs.** Fits the
  width with no height change, but it is exactly the distortion the
  user ruled out; a uniform shrink keeps the shape and gives up a little
  height instead.
- **Widening up to FIT toward the stock box**, to close the gaps around
  `E`, `J` and `O`. Rejected at first (no glyph enlarged); after the
  crops2 review the user asked for stock spacing, so D8 does this with
  a ±10% bound.
- **Shrinking the brackets about the baseline** (after2). Kept the one
  scale but dropped their tops below the caps; D8 spans the stock box
  instead.
