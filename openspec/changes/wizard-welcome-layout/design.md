## Context

`xboxrecomp-cli` `main` f8949f6 (Fyne 2.8.2, Go 1.27.2). Facts below are
from that tree on 2026-10-19. Paths are under
`xboxrecomp-cli/wizard/internal/screens/` unless stated.

- Welcome (`wizard.go`, `welcomePage`): heading, intro, the credits
  heading and an eight-row scroll (`credits.go`, `welcomeCredits`), three
  statements as bold lead plus sentence, the path radios (`paths.go`,
  `pathChoice`), then the folders.
- The header holds an info button (`w.info`, Tabler `info-circle`) that
  opens `creditsDialog`, hidden on Welcome.
- `plainPrepare` (`checks.go`) rewords NeedError, OverlapError and
  SpaceError, and returns `err.Error()` for anything else. The Getting
  ready row puts that in its Detail, and the checks pane's last line
  repeats it.
- `errorBox` is `dialog.ShowError(err, w.win)`. It shows the raw error.
  Callers: `openURL`, `openPath`, the terminal launch, Install now, a
  failed option Set and the Homebrew installer.
- The failure page (`fillDone`) names the build's log folder and has
  Open the log folder and Retry.

## Goals / Non-Goals

Goals: the four requests, with the same tests and gates as the rest of
the wizard and no new module.

Non-goals: new copy for errors the wizard already words, the build's
own excerpt, keyboard tips, other pages' layout.

## Decisions

### D1. The credits: a footer button, the same dialog

The button sits in the centre of the footer's Border, between Back and
Next, so it is on every page and never competes with Next. Its text is
the user's, word for word: "♥️ Open-source" (changed on 2026-10-19 from
the first, longer text). It is an outline button (`outline.go`): a
`widget.Button` at `LowImportance` (no fill) under a transparent
rectangle with a 1.5 px stroke and the input corner radius. The stroke
is a deep pink (#c2185b) on a light background and a light pink
(#f48fb1) on a dark one, picked from the theme's background on each
refresh, so it reads on both. The dialog,
its size and its tests stay. Welcome's list, `welcomeRows` and the
header's info button go. `info-circle` stays as the statements' glyph.

### D2. The tips: a layer in the content, not an overlay

Fyne has no tooltip. A `PopUp` shown on `MouseIn` does not work: while an
overlay is up, Fyne looks for hover targets in the top overlay only, so
the item under it gets `MouseOut` at once and the tip blinks. Instead,
the window's content is `Stack(sizeWatch, page, tips.layer)`. The layer
is a container without a layout that holds one bubble: a rounded
rectangle in the overlay background colour with an input-border stroke,
under a wrapping RichText at most 320 wide. Nothing in the layer is
Hoverable, so the pointer reaches the page under it. The bubble is
Tappable: a tap on it closes it and goes no further, so it cannot choose
the path tile under it. While a tap holds a tip open, a transparent,
Tappable catcher fills the layer under the bubble, so a tap anywhere
closes the tip and does nothing else, as a pop-up would. A window resize
or a scroll of Welcome closes any tip, because the bubble does not
follow its item.

`tipItem` is a widget that is Hoverable and Tappable:

- `MouseIn` shows the tip and `MouseOut` hides it, only when the tip is
  its own.
- `Tapped` shows it, or hides it when a tap opened it. So a click after
  a hover leaves it open, and on the Deck a tap opens and a second tap
  closes.
- Its lead is RichText, not a Label: a Label holds a tappable selection
  that would take the item's taps.
- Changing page closes any tip.

The bubble goes under the item, clamped inside the window, and above the
item when there is no room below.

### D3. The path tiles: drawn radios

Fyne's buttons have no chosen state and put the icon beside the text, so
`pathTile` draws its own:

- a rounded rectangle under a padded VBox of a 48 px icon and a bold
  centred label;
- the chosen tile: the selection colour as fill and a 3 px primary
  frame;
- the other tile: the button colour as fill and a 1 px input-border
  frame;
- hover and focus: their theme tint laid over the fill.

It is Tappable, Hoverable and Focusable (Space or Return chooses), so the
keyboard reaches it as it reaches buttons. A tap calls `setPath`, so the
saved setting and Next behave as before. Tapping the chosen tile keeps
it chosen: as with the radios, a choice cannot be cleared. `syncPath`
marks the tiles and sets the line under them to `pathFreshHint`,
`pathUpdateHint` or `pathPickHint`.

### D4. Errors: plain words, the log, three buttons

`errorHelp(err, logPath)` returns:

- "The log says what went wrong. Send it, or the error, to whoever helps
  you:";
- the path, in a selectable mono label;
- Copy error (only with an error), Copy log path, and Open the log
  folder (the path itself when it is a folder, else its folder).

Copying uses the app clipboard, as the log pane's Copy does. Where it is
used:

- **Getting ready:** `plainPrepare`'s fallback becomes `prepareOther`.
  `checkRow` gains `Err`, and `rowView` adds `errorHelp(r.Err,
  wizard.log)` under any failed Prepare row (a worded one keeps its
  words). The error's own words go to the checks pane's full log and to
  `wizard.log`. The pane's last line stays plain.
- **Error box:** `errorBox` logs `error: <err>` and shows a modal with
  `errorText` and `errorHelp`. Open the log folder in the box logs a
  failure instead of opening another box.
- **Player errors in the error box** (the user, 2026-10-19): an error
  the wizard already words for the player is shown as it is. The
  mechanism is the existing `playerError` type, not a test of the text:
  `errorBody` shows `string(pe)` when `errors.As(err, &pe)` finds one in
  the chain (wrapped or not), else `errorText`. `errorHelp` stays under
  both, so the log path and Copy error are always there. Install now's
  "no install.sh" is now a `playerError` (`installNoScript`).
- **"What the build said" stays** on the failure page as it is (the
  user, 2026-10-19): it is the build's own output, in a selectable box,
  for whoever helps the player.
- **Build failure:** Copy error (the failure's command and error) and
  Copy log path (the build's log folder, or `wizard.log` when the build
  stopped before it had one) sit before Retry, after Open the log
  folder.

New copy: `creditsButton`, `pathPickHint`, `prepareOther`, `errorTitle`,
`errorText`, `errorSeeLog`, `copyErrorText` and `copyLogPathText`.
`TestCopy` checks them for jargon. `creditsHeading` goes.

### D5. Tests

- **Credits:** the button is visible and centred on every page, has the
  user's text, and opens the dialog. Welcome has no credits.
- **Statements:** three items with their icons, and no sentence on the
  page.
- **Tips:** hover opens and leaving closes; a click after a hover keeps
  the tip; tap opens and a second tap closes; another item's
  `MouseOut` leaves the tip alone; a page change closes it; the bubble
  stays inside the layer; a tap on the bubble or, after a tap opened it,
  anywhere else only closes it; a resize or a scroll closes it.
- **Tiles:** none chosen at first; a tap chooses one and clears the
  other; the line under them follows; Next waits; Space chooses; the
  chosen frame is primary and thicker.
- **Errors:**
  - an unknown Prepare error gives `prepareOther`, and the page shows
    neither "release tag" nor "--game";
  - `errorBody` shows `errorText` for a raw error and a wrapped
    `playerError`'s own sentence for a player one, with Copy error and
    Copy log path under both;
  - Copy error and Copy log path fill the clipboard;
  - a worded error keeps its words;
  - `errorBox` writes the error to `wizard.log`;
  - the failure page's buttons copy the failure and the log folder.
- **Screenshots:** `TestScreenshots` adds an open tip, a chosen tile, the
  credits dialog, an unknown Checks failure and the error box.

## Risks / Trade-offs

- **The tips have no keyboard path.** The sentences are a convenience:
  `docs/wizard.md` and the README say the same. Adding one is a later
  change.
- **The custom tile is not a theme widget.** It reads only theme colours
  and sizes, so the light, dark and Deck themes apply. The screenshots
  cover light and dark.
- **The software painter cannot fill a rectangle with no colour.**
  `sizeWatch` now draws a transparent one, which changes nothing on
  screen.

## Migration Plan

None: the settings file is unchanged.

## Open Questions

None.
