## Context

The overlay's theme tokens are sized for 1080 lines. Before this change
the scale followed only the output height, so a small, dense screen held
close got the smallest text. The atlas is baked once, at arm time, in cat
`main.c` before `xbox_HostWindowMain`, so no window exists yet.

## Decisions

- **D1: floor from the display, not a new constant.** The floor is
  `max(OS scale, handheld ? ppi / 160 : 0)`, capped at 3. The 160 ppi
  reference is Android's dp, the usual rule for a screen read at arm's
  length; a desktop's 96 dpi is the theme's 1.0.
  Considered and rejected: a fixed Deck multiplier (it does not explain
  itself and does not cover HiDPI desktops); a physical size from EDID
  (not reachable from Proton, nor portable).
- **D2: the Deck is recognised by its hardware plus a 1280x800 display.**
  The hardware is `SteamDeck=1` or the SMBIOS names Valve Jupiter (LCD) /
  Galileo (OLED). Steam sets `SteamDeck` only in Game Mode: the first Deck
  check (Desktop Mode, bench launch through umu) logged `floor 1.00`. The
  names come from `/sys/class/dmi/id` on Linux and from
  `HKLM\HARDWARE\DESCRIPTION\System\BIOS` on Windows, which Wine's
  wineboot fills from the same DMI, so Proton needs no special case.
  The name test is `nv2a_overlay_is_deck_board` in the kernel.
  Docked to a TV, the display is not 1280x800, so it stays a desktop.
  Both the LCD (7") and the OLED (7.4", 5% less dense) use the 7" figure.
  The test is in the kernel (`nv2a_overlay_display_mark_deck`), so the
  overlay ctest covers it.
- **D3: a lazy probe.** The enhance layer installs a probe
  (`enhance_display.c`). Win32 uses `GetDeviceCaps(LOGPIXELSY)` and the
  screen metrics; the process is not DPI aware, so these are the
  virtualised ones its window is laid out in. Windows has no SDL: the
  window is GDI's and the exe declares no DPI awareness (no manifest
  entry, no `SetProcessDpiAwareness*`), so a 175% desktop reads 96 dpi
  and a scaled size, and DWM stretches the window, menu included, by
  1.75. The OS term is 1 there; a DPI-aware exe would change the game
  window's size too, which is out of scope. Elsewhere it uses SDL3's
  primary display, but only once SDL's video is up. The first bake runs
  at enhance init, before the presenter's `SDL_Init`, and almost every
  run arms the overlay (stats and toasts), so starting the video there
  would bring it up twice. The probe answers "not yet" (-1) instead, and
  the SDL presenter calls `nv2a_overlay_display_ready` after `SDL_Init`
  and before the guest thread starts. That probes and bakes the atlas
  again for the display, since no layer has drawn yet. A headless run
  never probes.
- **D4: output pixels and a cap.** The floor is in window pixels. Under
  `present.surface = internal` (Proton on the Deck) the lists are drawn at
  the output's size and stretched, so the floor is multiplied by the
  view's output-per-window ratio. A cap of `out_h / 600` keeps a list page
  and its footer on screen in a small window.
- **D5: bake for the display.** The atlas is baked for the display's
  height (the size of a fullscreen menu), so the Deck's text is not grown
  from a 1080-line bake. Past 2.0 the bake keeps to the output's own
  scale (a small window on a large display draws smaller). Both scales
  include the display floor and `overlay.ui_scale`, so a Retina floor of
  2 at `ui_scale` 1.5 or more asks for 3.0; every scale stops at 3.0
  (`OVL_UI_SCALE_MAX`), and `tests/overlay` `test_fit` bakes the
  largest reachable cases (Retina at 1.5 and 2.0, full and windowed; 4K
  at 150%) and checks they fit 2048x2048 with every symbol.
- **D6: legible glyphs.** A pad glyph in the small slot gets the body
  size's square, centred on the line (`nv2a_ovl_glyph_box`). Icons and
  key caps keep the line's size.
- **D7: the panel width.** At a scale over the output height's own, 40%
  of the width would squeeze the rows. The compact panel keeps 500 token
  columns, up to 3/4 of the width. At the height's own scale the panel is
  unchanged, so every stock layout pin holds. D6 and D7 hold under
  `ui_fit = output` too: D7 when `overlay.ui_scale` lifts the scale, D6
  always. They are a look change, not a size rule.

## Risks

- The probe reads the primary display once. A window moved to another
  monitor later keeps the first monitor's floor. `ui_scale` and
  `ui_fit = output` remain the way out. A Deck docked to a 1280x800
  external screen counts as its own panel.
- An explicit `SteamDeck=0` does not override the SMBIOS names: whether
  Steam sets 0 in the Deck's Desktop Mode is not pinned down. Documented;
  `ui_fit = output` is the way out.
- SDL's desktop mode on Linux (native, not Proton) under gamescope
  reports the nested size; on the panel that is still 1280x800.
