## Why

The user tested the rc wizard (CLI 029e875, wizard-build-feedback) on
native Windows 11 on 2026-10-15 and asked for these changes (verbatim):

1. "is it possible to only show the font link if not detected?"
2. "also add an icon to the link itself so it's clear its going to open
   the browser"
3. "currently building and the timer says "MM:SS in this part...", can we
   show the actual part/step name instead of "this part"?"
4. The Building page as a checklist of the build's parts, each with its
   own icon, state colours, progress, clock and log; the aggregated log
   stays in Details at the bottom. This is the companion change
   `wizard-build-checklist`, which also answers request 3 (see there).
5. The stop-the-build dialog: buttons right-aligned, title "Are you
   sure?", the description "next time the build will resume from where
   you left", actions "Go back" (back arrow) and "Cancel Build" (stop
   icon, red).

The HUD option's hint today tells every player to install PT Sans Narrow
Bold and always shows the Google Fonts link, even on a Mac (which ships
the font) or a PC where the player already installed it. The link opens
the browser with nothing on it that says so. The stop dialog is Fyne's
stock confirm (left/centre buttons, "No"/"Yes", the confirm button the
highlighted default) and its sentence claims more than the CLI does.

## What changes

- **Font-gated hints (CLI and wizard).** A `[[wizard.option]]` may set
  `font_hint`: words shown after `hint` only while the game's font
  (`[enhance.hud] font`) is not installed on this computer, or while the
  wizard cannot tell. When an option sets `font_hint`, its `hint_link`
  follows the same rule. When the font is found the wizard hides both and
  shows its own line, "<font> is installed." A new
  `xbr wizard font --json` reports whether the font is installed, with the
  same lookup `enhance hud` uses (`hud.resolve_font` and `font.find`). The
  wizard runs it each time the player opens the Options page.
- **Link glyph.** Every hint link gets Tabler's `external-link` glyph
  after its text, in the link colour of the current theme. The text stays
  the hyperlink, the accessible label and the keyboard target. Tapping
  the glyph opens the same address.
- **Stop dialog.** A custom dialog titled "Are you sure?". Its sentence is
  checked against what a re-run really skips (see the design). The
  buttons sit right-aligned: "Go back" with a back arrow, and "Cancel
  Build" with a stop icon in the danger (red) style. Neither is a default
  button. The dialog is never wider than the window.
- **Docs:** `docs/wizard.md` and `docs/manifest.md` in the CLI; in cat,
  `game.toml`'s `hud_pack` option moves its font sentence to `font_hint`,
  and `docs/packaging.md` says the wizard checks for the font.

## Not in scope

- Installing the font from the wizard. The player installs it; the CLI
  never ships a font.
- Request 3 and the Building page layout: `wizard-build-checklist`.
- A CLI release, a tag or the cat `[cli]` pin bump. Those happen at merge.
