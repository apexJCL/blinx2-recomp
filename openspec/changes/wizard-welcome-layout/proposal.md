## Why

The user asked (2026-10-19) for four changes to the build wizard, after
using the build that has the two paths (`wizard-paths`):

- **The credits take Welcome's best place.** "Made with these open-source
  projects" sits right under the intro as an eight-row list, and on the
  other pages the credits hide behind a bare info glyph in the header.
  The user wants them in a modal dialog, opened from a button that reads
  "Made with the effort of all this open-source projects <3", centred in
  the footer on every page.
- **Welcome's statements are three paragraphs.** "No game inside",
  "Downloads only what it needs" and "Sends nothing of yours" each show
  a lead and a full sentence. The user wants only the leads, in three
  columns on one row, each with its own icon, and the sentence as a
  tooltip on hover or click. Fyne has no tooltip, and a click has to
  work too, because the Steam Deck's screen has no hover.
- **The path choice reads like a form.** Fresh and Update are two radio
  groups, each with its sentence under it. The user wants two large
  buttons in a row, an icon over each label, still acting as radios,
  with the chosen one's sentence under both.
- **Developers' errors reach players.** An error the wizard has no plain
  words for is shown as it is. The user saw "this developer build names
  no release tag to clone: run it with --game DIR" in the Details of the
  Getting ready row on Checks. The user wants the page to say to check
  the log, show where it is, and offer Copy error, Copy log path and Open
  the log folder, on every failure path, with the error's own words
  still in the log.

## What Changes

- **Credits:** Welcome loses its list. A button in the footer, between
  Back and Next, on every page, opens the existing "Open-source credits"
  dialog. The header's info button goes. In a later round the user set
  its text to "♥️ Open-source" and asked for an outline button with no
  fill and a pink outline.
- **Statements:** a three-column row of tip items: an icon, the bold
  lead, an info glyph. The pointer over an item opens its tip under it
  (above it when the window ends first), and leaving closes it. A tap
  opens it too, and a second tap closes a tip a tap opened. The tip is
  drawn in a layer of the window's content, not an overlay.
- **Path choice:** two tiles in a two-column grid, Fresh with
  `FileApplicationIcon` and Update with `ViewRefreshIcon`, 48 px over a
  bold label. The chosen tile has a primary-colour frame and the
  selection fill. The line under them shows the chosen path's sentence,
  or "Pick one to see what it makes." before a choice. The tiles keep
  driving the path, the saved setting and Next.
- **Errors:** one helper says where `wizard.log` is (selectable) and
  gives Copy error, Copy log path and Open the log folder. It is used by:
  - the Getting ready row when Prepare fails; an unknown error there now
    reads "Something went wrong while getting ready.";
  - a new error box that replaces Fyne's `ShowError` everywhere the
    wizard called it;
  - the build failure page, where the buttons sit with Retry.
  The error's own words go to `wizard.log` and to the clipboard, never to
  the page. An error the wizard already words for the player (a
  `playerError`) is the exception: the error box shows it as it is, with
  the same help under it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `build-wizard` (added by `wizard-paths`, not archived yet): the
  Welcome page's layout, the credits' place, and how a failure is shown.

## Impact

- **Code** (all in `xboxrecomp-cli/wizard/internal/screens/`):
  `wizard.go` (footer, header, Welcome, error box and helper), the new
  `tip.go` and `pathtile.go`, `paths.go` (the tiles), `checks.go` (the
  row's error), `credits.go`, `copy.go`, `icons.go`, the tests, and
  `docs/wizard.md` plus the Tabler README.
- **No new Go module.** Fyne's widgets, theme icons and canvas are
  enough.
- **Games:** none. cat and b3 take the change with the next CLI pin.
- **Not in scope:**
  - the build excerpt on the failure page ("What the build said"), which
    stays: it is the build's own output for whoever helps the player, in a
    selectable box, and the Done design already chose it;
  - plan errors on the Base, Changes and Summary pages, which are already
    plain notes with the error only in the log;
  - a keyboard path to the tips.
