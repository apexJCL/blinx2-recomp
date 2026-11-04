## Why

The tracker item: on the Steam Deck (1280x800, 7" panel, BLiNX 2 on D3D11 under
Proton) the in-game menu is too small to read and its pad glyphs blur into
one another. The overlay scales with the output height alone,
`clamp(out_h / 1080, 0.5, 3) * overlay.ui_scale`. On the Deck that gives
0.74: body text is 16 px and small text 12 px, on a 216 ppi screen held
at arm's length. The pad glyphs inside the footer's small text are 12 px,
so Back, Start and Guide look alike. The same rule also ignores a
desktop's OS UI scale (a Retina Mac; a scaled Windows desktop already
stretches the DPI-unaware window).

## What changes

- New toolkit config key `overlay.ui_fit`: `display` (default) or
  `output` (the old rule). It has its env row `RECOMP_OVERLAY_UI_FIT` and
  an "Overlay fit" row on the Render page that applies at restart.
  `overlay.ui_scale` gets its env row `RECOMP_OVERLAY_UI_SCALE` and keeps
  its menu row.
- Under `display`, the scale is
  `max(clamp(out_h / 1080, 0.5, 3), floor)`, then times
  `overlay.ui_scale`. The floor is:
  - the primary display's OS UI scale (DPI / 96 on Windows; SDL3 pixel
    density times content scale elsewhere);
  - on a handheld, its density over 160 ppi. The one handheld known is
    the Deck's own panel: `SteamDeck=1` or the Deck's SMBIOS names
    (Valve Jupiter/Galileo), and a 1280x800 display. At 216
    ppi that is 1.35;
  - converted to output pixels under `present.surface = internal`, and
    held to `out_h / 600`.
  The display is probed once: at the first atlas bake on Windows, and
  with SDL once the presenter's video is up (then the atlas is baked again,
  before the guest starts). A headless run never probes.
- The atlas is baked for the display's height; past 2.0 it keeps to the
  output's own scale, and never past 3.0, where the atlas is proven to fit.
- Over the output height's own scale, the compact panel keeps 500 token
  columns, up to 3/4 of the width.
- A pad glyph in small text is drawn at the body size, centred on the
  line (the legible minimum).

## Impact

- Default behaviour: on the Deck the menu grows by about 1.8x (body 16 to
  29 px). A desktop at 100% scale and 1080 lines or more is unchanged. A
  desktop window under 1080 lines grows to the OS scale: a 1280x720
  window at 100% goes from 0.667 to 1.0. A HiDPI SDL desktop (a Retina
  Mac) grows to its OS scale. Pad glyphs in small text grow
  everywhere. Only the overlay changes, never a game frame: the overlay
  is never in a frame dump, and goldens run with `RECOMP_MENU=0`.
- D3D11 and Metal share the rule: it lives in the kernel overlay, and both
  presenters draw the same lists.
- Toolkit branch `fix/ovl-display-scale`; cat: this spec and
  `docs/env.md`.
