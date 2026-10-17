## Context

Read at CLI `main` 029e875 (wizard-build-feedback merged) and cat
`spec/wizard-build-feedback` 3d5b78c. Fyne v2.8.2, as pinned.

- `[[wizard.option]] hint_link` (manifest.py `WIZARD_OPTION`,
  `_hint_link_errors`) reaches the binary through `wizard config --json`
  (`wizard.problems` copies each option dict whole) as
  `gamecfg.Option.HintLink`. `screens.optionHint` builds the hint and a
  `widget.Hyperlink` once, when the page is made.
- Font lookup: `enhance/hud.py resolve_font(arg, name)` gives
  `font.find(name)` for a name that is not a file. `font.find` walks
  `font_dirs()` (on Windows `%LOCALAPPDATA%\Microsoft\Windows\Fonts`, then
  `%WINDIR%\Fonts`) and matches the face's full name (name ID 4), ignoring
  case and extra spaces.
- The wizard runs the CLI only through the game's bootstrap, at the
  game's `[cli]` pin (`runner.Runner`). The Options page comes after
  Checks, so `w.env.Runner` exists by then.
- Stop dialog: `dialog.ShowConfirm(stopTitle, stopText, ...)`.

## Decisions

**D1. One key, `font_hint`, tied to `[enhance.hud] font`.** The CLI has
one font, the HUD atlas face. That name already lives in game.toml, and
the build looks it up there. An option that names its own font would copy
that name and could drift from it; a dotted reference ("enhance.hud.font")
would be generality nobody uses. So the key is a sentence, and the
condition is implied: "this option needs the game's font". The manifest
refuses `font_hint` when `[enhance.hud] font` is empty. The words that
depend on the font (and the link that fetches it) move out of `hint`, so
`hint` reads true whether or not the font is installed. With `font_hint`
set, `hint_link` belongs to it: the link exists to get the font. Without
`font_hint`, a link shows always, as today.

**D2. Detection is the CLI's: `xbr wizard font --json`.** It prints
`{"font": NAME, "found": bool, "path": PATH|null}`, using
`hud.resolve_font(None, NAME)`, the build's own lookup. NAME is
`[enhance.hud] font`, or `--name` (for testing the missing case on a host
that has the font). With no font named, it prints `font: ""` and
`found: false`. It is a `wizard` subcommand, not a doctor line, because
the wizard repeats it each time the player opens Options, and doctor
takes seconds more. Doctor's report is also a contract the checks page
parses.

**D3. Three states in the wizard: unknown, missing and found.** The check
runs in a goroutine each time the Options page opens, if any option has
`font_hint`. A newer run makes an older answer stale: a counter
discards it. Until an answer comes, and when the call fails (no Checks
yet, or a CLI pinned before this command, such as v0.7.3: argparse exits
2), the state is unknown. Unknown shows `font_hint` and the link, the
safe side. Missing shows them too. Found hides both and shows "<font> is
installed." in the success colour (its text carries the meaning, not just
the colour). A font installed while the wizard is open is seen the next
time the player opens the page (Back, then Next). While a re-check
runs, the lines keep what the last answer showed, so a page that was
"installed" does not flash the link on every visit.

**D4. The link glyph.** Tabler `external-link` (3.34.1, MIT,
`LICENSES/tabler-icons-MIT.txt`), embedded as published. Fyne's themed
resources recolour fills only, and Tabler's glyphs are strokes in
`currentColor`. So a small `strokeIcon` resource replaces `currentColor`
with the current theme's colour when Fyne reads it. Its name carries the
colour name, so Fyne's icon cache keeps one copy per colour, and a theme
change re-renders it. The glyph takes `ColorNameHyperlink`, the link
text's colour, in both variants. It sits right after the text, at the
text's height. It is a tap target for the same handler with a pointer
cursor, but it takes no focus: the hyperlink stays the one focusable
control, and the screen reader reads the link text as the label.

**D5. The stop dialog.** `dialog.NewCustomWithoutButtons` with the
sentence in a word-wrapped label and the buttons in a trailing HBox
(spacer first), so they sit right-aligned. "Go back"
(`NavigateBackIcon`, medium importance) closes the dialog. "Cancel Build"
(`MediaStopIcon`, `DangerImportance`) closes it and stops the build. No
button is the default: the destructive action never sits under Enter.
The dialog's width is min(420, the window's width minus 2 × 24), so it
never overflows a narrow window. Fyne tells a window's content, not the
app, about a resize, so a widget under the page (`sizeWatch`) reports
each new size and the dialog, while it shows, is resized with it.

**D6. The sentence, checked.** What a re-run after a cancel skips
(`package_plan` and the prerequisite commands):
- import: skipped once the dump is in place (`dump.prepare` says
  `same`);
- setup: skipped once nothing is missing (`setup_needs`);
- generate: skipped when `gen/` is current. A recomp that was
  interrupted leaves the regen marker, so it starts again from the
  beginning;
- build: ninja keeps every object it finished, so the compile goes on
  from the files already compiled;
- package: the staging folder is removed and redone (seconds);
- `enhance hud` (the HUD pack): redone every time, 4 to 8 s (measured in
  `enhancements-hud-pack`).

So "resume from where you left" is only partly true. Nothing resumes
inside a step, and two steps always run again. The wording used is "Next
time, the build reuses most of what already finished." It is a proper
sentence and close to the user's text, and it is true for all the steps
above. The quit confirmation's matching claim ("continues from where it
stopped") gets the same sentence.

## Risks

- The pinned CLI (v0.7.3) has no `wizard font`. The wizard shows the
  link, as it does today, until the pin moves past this change. cat's
  `game.toml` gains `font_hint`, which v0.7.3's manifest check rejects as
  an unknown key, so the cat `[cli]` pin bump must land with this
  game.toml change (at merge).
- `font.find` walks every font file. On a Windows PC with about 1,000
  fonts that is about a second. The check is off the UI thread, and the
  page renders at once.
