## Context

Read at CLI main a3208e4 (v0.7.0) and the implementer's worktree
`wt/wizard-ui/xboxrecomp-cli` (branch `feat/wizard-ui-polish`, same
tip); Fyne as pinned in `wizard/go.mod`: `fyne.io/fyne/v2` v2.8.2
(source in `xboxrecomp-cli/wizard/.tools/gomod/fyne.io/fyne/v2@v2.8.2`).

The pages today (`internal/screens/wizard.go`, 909 lines): `New` builds
every page once into `pages []*page{title, obj, enter, ready, next}`,
`render(i)` puts page i's object in a `container.NewStack` body and
sets the title to `"%s  (%d of %d)"`; the window is
`Border(top: Padded(title), bottom: Padded(HBox(back, widgetSpacer(),
next)), center: Padded(body))`, 780 by 580. `widgetSpacer()` returns an
empty `HBox`, which an `HBox` does not stretch, so Back and Next sit
together at the left (`layout.NewSpacer()` is the stretching one).
The checks page is `Border(top: checkBox, center: checksLog.list)`;
`runChecks` runs `Prepare` (work.go: uv, git, the clone or `--game`
tree, each `[[wizard.fetch]]` entry; one log line per step) then
`Doctor` on a goroutine and `showChecks` fills `checkBox` with one
monospace label per `doctor` line, a sentence per target from
`Doctor.Target(t)` (its `Blockers[t]`), a button per `runner.Action`
and Retry. The build page is `Border(top: VBox(stepLabel,
Border(right: cancelBtn, center: bar)), center: buildLog.list)`.
`logView` (logview.go) is a `widget.List` of monospace labels with a
5000-line cap and an optional tee to the wizard's log file. The summary
page is a disabled multi-line `Entry` with the commands and the seed.

What `doctor --json` gives the screen (`runner.Doctor`): `Lines` (the
CLI's report, each `key:` padded to a column: host, uv, lock, cmake,
ninja, tools py, cli, toolkit, llvm-mingw, game files, gen/, game env,
DEVELOPER_DIR on a Mac, makensis, next, plus `warning:` lines and
continuation lines starting with spaces), `Blockers[target]` (what
`setup` cannot install, each with its fix: `Command Line Tools:
xcode-select --install`, `Homebrew: brew install sdl2 ...`, `makensis:
brew install makensis` or `sudo apt install nsis` or the distrobox
recipe, `the macos target needs a macOS host (...)`), `Problems` (what
`setup` fetches itself: `no cmake in .venv (...)`, `no toolkit (...)`,
`no game_files/default.xbe`). `runner.Actions(reasons)` already turns
the fixes into `clt`, `brew` and `sudo` actions; `Prepare` returns a
`*NeedError` with an action when git is missing. A fresh root is the
normal case: every build tool "missing", every target buildable.

What Fyne 2.8.2 offers for the pieces the user asked for (checked in
the pinned source):

- Read-only text the player can select and copy: `widget.Label` with
  `Selectable: true` (`label.go`, since 2.6). A disabled `Entry` cannot
  be selected (every handler in `entry.go` returns on `Disabled()`) and
  there is no read-only mode; `RichText` and `TextGrid` have no
  selection. `fyne.App.Clipboard()` (since 2.6; `Window.Clipboard` is
  deprecated) takes the whole text for a Copy button.
- Small text: `Label.SizeName = theme.SizeNameCaptionText` (since 2.6)
  and `Importance: widget.LowImportance` (since 2.4) for the footer.
- Icons: `theme.ConfirmIcon`, `InfoIcon`, `WarningIcon`, `ErrorIcon`,
  `MenuDropDownIcon`, `MenuDropUpIcon`, `ContentCopyIcon` in
  `widget.Icon` or `widget.NewButtonWithIcon`; `widget.NewActivity`
  (since 2.5) for a row being checked.
- Rows that expand: `widget.Accordion` (a button-headed section per
  item), `widget.List` with `SetItemHeight` per row, or a plain `VBox`
  of rows whose detail container is shown and hidden. `widget.Table`
  has fixed cell templates and no row expansion.
- Thin bars: `widget.ProgressBar`'s minimum height is a text line plus
  twice the inner padding (`progressbar.go:25`), and it always draws a
  percentage; a thin bar is two `canvas.Rectangle`s (`CornerRadius`
  since 2.4) in a small custom widget.
- Headless rendering: `fyne.io/fyne/v2/test.NewApp()` plus
  `driver/software.RenderCanvas(c, theme)` or `software.Render(obj,
  theme)` returns an `image.Image` with no display; the test canvas's
  own `Capture()` has no painter and returns a blank image
  (`test/canvas.go:27`). The test app's default theme is the test
  theme (`test.Theme()`, flat colours for image masters), so a
  screenshot passes the built-in theme explicitly.

The user's click-through ran the `.app` on the Mac (`runs/wizard-click/`);
the Mac screen may be locked for the implementer, so page images come
from the headless renderer.

## Goals / Non-Goals

Goals: a player with no build knowledge reads each page in one pass;
progress through the eight steps and the version are visible without
being in the way; the checks page says what is ready, what the build
fetches itself and what the player has to do, in that order of
importance, with the explanation and the fix one click away; the logs
stay available (and copyable) without filling the page; the module
stays game-agnostic and small; every page can be rendered to an image
headless for the user's approval.

Non-goals: an accessibility tree (Fyne has none); changing what the CLI
prints (`doctor --json`, `--plain`); a Cancel button on the checks page
(review L-e, its own follow-up); translations; new pages or options; a
custom theme or font.

## Decisions

**D1. The page frame: header with the step bar, content, nav, footer.**
`New` builds `Border(top: header, bottom: VBox(Padded(nav), footer),
center: Padded(body))`.

- `header` is `Padded(VBox(HBox(title, layout.NewSpacer(), step),
  stepBar))`: `title` the page title in bold at
  `theme.SizeNameSubHeadingText`; `step` a caption-size,
  low-importance label "Step 2 of 8"; `stepBar` a `thinBar` (D2) with
  `Segments: 8`, filled up to and including the current page.
  `render(i)` sets the three. The Done page's title changes with the
  outcome as today ("Done", "The build stopped").
- `nav` is `HBox(back, layout.NewSpacer(), next)` (the stretching
  spacer; `widgetSpacer` goes).
- `footer` is `HBox(layout.NewSpacer(), version)` inside a container
  padded only at the right and bottom: `version` is a caption-size,
  right-aligned quiet text (D9) reading "Build wizard <version>", or
  "Build wizard <version> (developer build)" when `Release.Dev`.
  Decided (Open Question 1, the orchestrator for the user): the
  wizard's version alone, small at the bottom right; the release
  (tag and short commit), CLI and toolkit pins move to the first line
  of the Summary's "Technical details". It truncates with an ellipsis,
  never wraps. Always visible, every page.
- Why a segmented bar and not Fyne's `ProgressBar`: the eight steps are
  discrete; a bar with a percentage would read "25%" for a step. The
  text "Step 2 of 8" carries the meaning for a reader who cannot see
  the bar's fill (icons-plus-text rule, D6).

**D2. `thinBar`: one small custom widget for both thin bars.**
`internal/screens/thinbar.go`: a `widget.BaseWidget` with `Value
float64` (0 to 1) and `Segments int` (0 for a continuous bar), a
`SetValue`. Its renderer draws a track `canvas.Rectangle` in
`theme.ColorNameInputBackground` and, continuous, one fill rectangle
in `theme.ColorNamePrimary` whose width is `Value` of the track;
segmented, `Segments` rectangles with a gap of half the theme padding,
the first `round(Value × Segments)` in the primary colour and the rest
in the track colour. Height 6 (device-independent units; Fyne scales),
`CornerRadius` 3, `MinSize` (0, 6) so it takes the full width. About
60 lines, no state beyond the two fields; one `TestThinBar` renders it
at 0, 0.5 and 1 and checks the fill width. It is the one custom
widget in this change; everything else is Fyne's.

**D3. The checks page: a table of rows with status, detail and fix.**

The model (`internal/screens/checks.go`, no Fyne in it):

```go
type rowState int // stateBusy, stateOK, stateLater, stateWarn, stateFail
type checkRow struct {
    Name, Status string   // "Build tools", "Fetched when the build starts"
    State        rowState
    Detail       string   // the plain explanation; "" hides the toggle
    Actions      []runner.Action
}
func checkRows(cfg *gamecfg.Config, env *Env, d *runner.Doctor, prepErr error, brew bool) []checkRow
```

The rows, in this order, from `d.Lines` keyed by the text before the
first `:` (the CLI's keys; `doctor` is the CLI's, so the keys are the
same for every game) and from `d.Blockers`:

| Row | From | OK | Later (info) | Warn | Detail |
|---|---|---|---|---|---|
| This computer | `host` | always: "Ready" | | | the host line's value, plus every line with a key this table does not name (gen/, game env, DEVELOPER_DIR, next, a newer CLI's additions), so nothing is lost |
| Build tools | `uv`, `cmake`, `ninja`, `tools py`, `toolkit`, `llvm-mingw`, `makensis`, and `env.UV`, `env.Git` | none of them missing: "Ready" | any says `missing` or starts a `Problems` entry: "Fetched when the build starts" | | "The build fetches these itself: cmake, ninja, …" then the raw lines |
| Game source | `Prepare`'s clone (or `--game`), `cli`, `lock`, `warning:` lines about drift | "Ready" | | `lock` failed, `cli` "not the pin", or `--game`: "Not at the release's version (developer mode)" | "<repo> <tag> in <folder>" and the raw lines |
| Your game files | `game files` | a dump is in place: "Ready" with its path | `MISSING`: "Chosen on the next page" | an "unknown dump" note: "Not the game this wizard is for" | the raw line |
| Build for Windows / macOS / Steam Deck or Linux (one row per `cfg.Targets`, names from a short map, `model.TargetLabels` stays for the Platform page) | `d.Blockers[t]` | empty: "Can be built on this computer" | | non-empty: "Needs something first" | `plainBlocker` of each reason, one paragraph each; `Actions` = `runner.Actions(reasons)` |
| Notes | `warning:` lines not used above | | | present: "Worth knowing" | the lines |

While `Prepare` runs (`d == nil`, `prepErr == nil`) the table has the
same rows in `stateBusy` with "Checking…" (an `Activity` for the
icon), so the layout does not jump when the results land. When
`Prepare` fails the table is one row, "Getting ready", `stateFail`,
status "Could not finish", `Detail` the error in plain words
(`plainPrepare`: the `NeedError` message as it is, the overlap and
disk-space messages reworded in D5) and the `NeedError`'s action; its
detail is open by default.

`plainBlocker(reason string, brew bool) string`, a table test case
each:

- contains `xcode-select --install`: "Apple's Command Line Tools are
  not installed. They bring git and the compiler. The button opens
  Apple's installer; it takes a few minutes, and this page checks again
  when it is done."
- starts with `Homebrew: brew install` and `brew` is installed: "Some
  libraries from Homebrew are missing: <the formulae>. The button
  installs them; no password is needed." Not installed: "The build
  needs a few libraries from Homebrew, which is not installed. The
  button opens Homebrew's installer in Terminal, where it asks for your
  password."
- starts with `makensis:`: "Making a Windows setup program needs NSIS
  (makensis)." then, by the hint: `brew install` "The button installs
  it."; `sudo …` "Run this in a terminal (it asks for your password
  there): <command>"; otherwise (the distrobox recipe) "On this system
  it runs in a container: <the hint as it is>".
- contains `needs a macOS host`: "A Mac app can only be built on a Mac.
  Pick another platform, or run this wizard on a Mac."
- anything else: the reason as it is.

The view: `Border(top: intro, bottom: VBox(Border(right: retry, center:
progress), logPane), center: VScroll(VBox(rows…)))`. Each row is a
`VBox(Border(left: icon, right: toggle, center: HBox(name, status)),
detail, Separator)`: `icon` a `widget.Icon` (Confirm, Info, Warning,
Error; an `Activity` while busy); `name` a normal label; `status` a
low-importance label; `toggle` an icon-only `Button` (`MenuDropDownIcon`
/ `MenuDropUpIcon`, `LowImportance`), present only when the row has a
detail or an action; `detail` a `VBox(para(Detail), action buttons…)`
indented by a padding, hidden until the toggle is tapped and the
`VBox` refreshed. No header row: the icon column and the status text
make the columns self-explanatory and the user asked for a simple
table.

Why a `VBox` in a scroll and not `widget.Table`, `List` or
`Accordion`: `Table` cannot grow a row; `List` can (`SetItemHeight`)
but then every detail's height is measured by hand and kept in step;
`Accordion` is the right mechanism with the wrong shape (a full-width
button per row, no status column). The table has at most a dozen rows,
so a plain container costs nothing and the show/hide of a child is all
the state there is.

The thin progress bar (`thinBar`, continuous) follows the phases:
`Prepare` gains a `step func(done, total int)` argument, called after
uv, git, the clone or `--game` check, and each host-filtered fetch
entry (`total` = 3 + the entries); the screen adds one for `doctor` and
sets the bar to `done / (total + 1)`, full when `doctor` has parsed,
and shows 0 on a failure. The bar, Retry and the log pane are outside
the scroll, so they stay in view. `runBrew` and the CLT and Homebrew
polls end in `runChecks` as today, so the table and bar restart from
the top.

`ready` for Next is unchanged: `doctor` parsed, at least one target
without blockers, nothing running.

**D4. `logPane`: collapsed to the latest line; expanded, selectable
text with Copy. The same widget on the checks and build pages.**
`logview.go` becomes `logPane`, keeping `Append`, `Clear`, the
5000-line cap and the tee, and dropping the `widget.List`:

- Collapsed (the default on both pages): `Border(left: toggle, center:
  last)`: `toggle` a `Button` "Details" with `MenuDropUpIcon`,
  `LowImportance`; `last` a monospace, low-importance label with
  `Truncation: fyne.TextTruncateEllipsis` holding the newest line. One
  row high.
- Expanded: `Border(top: HBox(toggle "Hide details" with
  `MenuDropDownIcon`, layout.NewSpacer(), copy), center: scroll)`:
  `copy` a `Button` "Copy" with `ContentCopyIcon` that puts every kept
  line into `fyne.CurrentApp().Clipboard()`; `scroll` a
  `container.NewScroll` (both directions, `TextWrapOff`) around a
  `widget.Label{Selectable: true, TextStyle: Monospace}` holding the
  last 500 lines, `SetMinSize(0, 180)` so the page keeps its table or
  bar above it. The pane's own `fyne.Do` is coalesced: `Append` marks
  it dirty and arms one `time.AfterFunc(100 ms)` at a time, whose
  callback sets the label text and the last line once; a label is
  re-laid out per refresh, not per line. 500 shown and 5000 kept is
  the trade: the Copy button and the CLI's `build-logs/` hold the rest.
- The build page keeps `widget.ProgressBar` and the step label above
  the pane: they are the build's main progress and already in the
  user's requested shape. Consistency: both pages present the log the
  same way, and a player who learned the toggle on the checks page
  finds it on the build page.

Why `Label.Selectable` and not an `Entry`: see Context; a disabled
`Entry` cannot be selected and an enabled one is editable. Why not
keep the `List`: a list's rows are separate labels, so no text can be
selected across them, which is what the user asked for.

**D5. The copy: one file, plain words, the game only through the
config.** `internal/screens/copy.go` holds every player-facing string
as a constant or a `func(name string) string` (`cfg.Game.Name`), so
the test in D7 reads them and the pages stay readable. The strings:

Welcome ("Welcome"):

- Heading (bold, sub-heading size): "Build {Game} for your own
  computer"
- "This wizard turns your own copy of {Game} into a version that runs
  on a Windows PC, a Mac or a Steam Deck. It asks a few questions, then
  the build runs on its own: about half an hour on a PC or Mac, longer
  on a Steam Deck."
- Bold "Before you start", then three rows of `Icon(InfoIcon)` plus a
  wrapped label:
  - "No game inside. This program holds no code or files from {Game}.
    The game comes from your own disc image or game folder, and what it
    builds is for your own computers only."
  - "Downloads only what it needs. The free build tools and the game's
    source code come from their official sites, and each download is
    checked against a known checksum."
  - "Sends nothing of yours. Your game, your files and your settings
    stay on this computer. The one thing it asks the internet is
    whether a newer wizard exists, and you can turn that off below."
    (True at a3208e4: `update.Latest` is one GET of the latest-release
    endpoint with no body and no identifying header; every other
    network call is a download or a clone.)
- Bold "Install folder", "The tools, the source code and the build go
  here. About 15 GB." then the path and "Change…".
- Checkbox "Look for a newer wizard when this starts".
- First run only: "This program is not signed, so your system may have
  warned you before opening it. The release page lists the SHA256 of
  every download."
- The newer-release card: title "A newer wizard is available: {tag}",
  "This one keeps working. Download the new one from the release page
  if you like.", button "Open the release page".

Checks ("Checks"): intro while running "Getting the build tools and
the game's source code ready. The first run downloads a few hundred
MB."; after: all rows OK or Later "Everything is ready. Anything else
the build needs, it fetches by itself when it starts."; a Warn row
"Some platforms need one more thing. Open the row for what to do; you
can also continue with the platforms that are ready."; a Fail row
"Something went wrong while getting ready. Open the row for details,
fix it, then press Retry." Statuses: as D3's table; "Checking…";
"Could not finish". Buttons: "Retry", "Details", "Hide details",
"Copy", "Install Apple's Command Line Tools", "Install Homebrew",
"Install: {formulae}" (the brew action), "Run in a terminal:
{command}" (the sudo action). The log lines the page adds: "Apple's
installer is open; this page checks again when it finishes." and
"Homebrew's installer is open in Terminal; this page checks again when
it finishes."

Your game ("Your game"): "Pick your own copy of {Game}: a disc image
(.iso or .xiso), or the folder that holds default.xbe. The wizard
checks that it is the right game and copies the files into its own
folder; your original is not changed." Buttons "Choose a disc image…",
"Choose a folder…"; the entry's placeholder "or type the path here".
Errors: "Nothing was found at {path}."; "{path} has no default.xbe.
Pick the game's top folder, or the disc image."; "The install folder's
disk has {x} GB free and this needs about {y} GB. Free some space, or
pick another install folder on the Welcome page."

Platform ("Platform"): "Which computer is the game for? This one is
already selected. A build for another computer of yours is copied
there and installed the same way." A blocked target: "{Target}: not
on this computer yet. {plainBlocker…}". Deck: "On a Steam Deck the
build is slow and needs a lot of memory; a PC or Mac is faster."
`model.TargetLabels` unchanged.

Options ("Options"): "These are the game's settings as it shipped.
Change what you like: your choices are saved with the game the first
time it is installed, and you can change them again later in its
config.toml." "This game has no settings to choose here." The option
labels are the config's.

Summary ("Summary", Next reads "Build"): plain rows "Game: {name}
{tag}", "Install folder: {root}", "Platform: {label}", "Settings: as
shipped" or one "{label}: {value}" line per changed option (a bool as
"on"/"off"), "Saves and settings go in {data} on the computer you
install it on." Then a closed `Accordion` item "Technical details"
whose content is a selectable monospace label with today's command
lines and seed text (the disabled `Entry` goes).

Building ("Building"): "This takes a while. You can keep using your
computer; closing this window stops the build." The step label as
today ("Starting", "Planning", "Step 2 of 5: setup (llvm-mingw)");
"Cancel"; the confirm "Stop the build? Next time it continues from
where it stopped." The window-close confirm "A build is running. Stop
it and quit? Next time it continues from where it stopped."

Done: success, title "Done": bold "Your build is ready.", the bundle
path, the install step for the target (`installText`, unchanged), the
buttons "Show the bundle" and "Install now", "Saves and settings live
in {data} on the computer you install it on." Failure, title "The
build stopped": bold "The build did not finish." then "It stopped at:
{step}." when known, "The full log: {path}.", buttons "Open the log
folder" and "Retry", "Retry runs the build again and skips what is
already done." Both end with "The bundle holds your own copy of {Game}
and code made from it. It is for your own computers only: never share,
upload or publish it."

Words that do not appear in player-facing text: uv, venv, xbr, cmake,
ninja, llvm-mingw, toolkit, clone, repo, sha256 (the signing note's
"SHA256" is the exception, because the release page uses it). The raw
CLI lines live in the rows' details and in the log pane, where a
player who is asked for them can copy them.

**D6. Accessibility: icon plus text, never colour alone.** Every state
has an icon and a status word (D3); the step bar has "Step n of 8"
(D1); the toggles and Copy are `Button`s, so they are focusable and
keyboard-operable like the rest; the selectable labels are focusable;
the thin bar's colours come from the theme, so the dark and light
variants both have contrast. `Importance` colours (success, warning)
are not used for meaning. An accessibility tree is still Fyne's gap,
recorded in TASKS as before.

**D7. Game-agnostic by test.** `TestNoGameInSource` reads every
non-test `.go` file of `internal/screens` and fails on `blinx`,
`BLiNX`, `burnout` or `b3` outside `testdata/`; the strings reach the
game's name only through `cfg.Game.Name`, the tags through
`cfg.Release`, `cfg.CLI`, `cfg.Toolkit`, and the data folder through
`cfg.Data`. The sample config in `internal/gamecfg/testdata/blinx2.json`
stays the test fixture.

**D8. Headless screenshots for the user's approval.** `TestScreenshots`
in `screens_test.go` runs only when `WIZARD_SHOTS` names a directory.
It drives the pages as `TestPages` does (the saved `doctor.json`, a
second sample with blockers, a fake dump path, one changed option, a
failed and a successful Done) and, for each page and for the two theme
variants, renders the window's content at 780 by 580 with
`software.RenderCanvas(win.Canvas(), theme)` (the test app's default
is the flat test theme, so the built-in theme is passed explicitly:
`theme.LightTheme()` and `theme.DarkTheme()`, deprecated in favour of
following the user's preference but present in 2.8.2 and right for a
fixed-variant image; one line notes it) and writes
`<nn>-<page>[-<state>]-<variant>.png` with `image/png`. The checks
page is captured three times: busy, all ready, and with a blocked
target whose row is expanded; the log pane once collapsed and once
expanded with a few lines. The implementer runs it with
`WIZARD_SHOTS=…/runs/wizard-ui/shots` and the user approves the images
before the merge; no live window and no unlocked screen is needed.

**D9. As built: where the implementation departs from the above.**

- Quiet text: low-importance labels draw in the disabled colour, which
  was unreadable in both themes' screenshots. The step caption, footer,
  row statuses, the log's newest line and the welcome page's folder note
  are a `quietText` (`quiet.go`): a RichText in `ColorNamePlaceHolder`.
- The thin bar's empty part uses `ColorNameInputBorder`, not
  `InputBackground`: the latter barely differs from the page background
  in light mode, so the eight segments did not read as a bar.
- `checkRow` gains `Raw []string`: the CLI's own lines behind the row,
  shown in its detail as selectable monospace text below the plain
  explanation and the fix button, so someone helping the player can ask
  for them without opening the log.
- "Your game files" reads "Ready" when present; the path stays in the
  row's raw lines rather than the status.
- The Platform page's blocked line is "<target>: not on this computer
  yet. The Checks page (step 2) says what it needs." instead of
  embedding `plainBlocker`: that page has no fix buttons, so "The
  button installs it" read wrong there.
- The dump page's checks return a `playerError` (a string type) for its
  sentences, since staticcheck's error-string rule (ST1005) applies to
  `fmt.Errorf` and `errors.New`.
- The busy rows' `widget.Activity` spinner is not drawn on the headless
  software canvas, so the busy screenshot shows no row icon; the real
  app animates it.
- The screenshots use `~`-relative made-up paths, so no home directory
  path lands in the public CLI's source.

After the Opus review (2026-10-15, merge after fixes):

- The log pane's timer is a field (`after`). The tests flush by hand,
  because Fyne's test driver runs `fyne.Do` inline on the timer's
  goroutine and raced the test. `check.sh` runs `go test -race` where
  Go supports it (darwin and linux on amd64 and arm64, windows/amd64).
- The newer-wizard check is sent only when the player leaves the Welcome
  page with the box ticked, once per run; nothing goes out before the
  box has been seen (the user's decision). A newer release shows in a
  dialog, not as a card on the page the player has just left.
  - The statement reads "Apart from the downloads above, the only other
    request is a check for a newer wizard, which you can turn off
    below."
  - The box reads "Check for a newer wizard".
  - `brew` runs with `HOMEBREW_NO_ANALYTICS=1`. So does the Homebrew
    installer, through a wrapper script beside the pinned one.
- Welcome:
  - The intro names the computers from `cfg.Targets` and promises no
    build time ("this can take a while"). The checks intro no longer
    promises a size.
  - The "Before you start" subheading is dropped, and the unsigned note
    is one line, so the first-run page fits without scrolling.
- A checks row opens from its whole line: the icon, name and status are
  one tap target (`tapRow`). The toggle is a focusable "Details" button
  with a chevron.
- Lows fixed:
  - The expanded build log fills the space under the bar.
  - "About 15 GB" and the disk-space sentence both come from
    `hostinfo.NeedBytes`, counted in GiB.
  - The NSIS text matches the button when Homebrew is missing.
  - The checks log ends on "Checks finished." or "The checks stopped:
    ..." in plain words.
  - The brew regexp match is checked before it is used.
  - "Getting ready", the release text and the technical-details
    headings are in `copy.go`. The `tech*` constants are exempt from
    `TestCopy`'s word list.
  - The build page says "Part n of m".
  - The raw lines use the normal text colour, and monospace text wraps
    at words.
  - A separator under the checks intro marks the top of the table.
- Follow-ups, not done here:
  - Target rows do not carry the CLI's blocker strings in their raw lines
    (L5).
  - A quarantined llvm-mingw reads as "Fetched when the build starts"
    with "Every build tool is in place." (L7).
  - A CLT or Homebrew poll can start a second check if Retry was pressed
    while it waited (L8, pre-existing).
  - The build page's stage name is the CLI's ("setup (llvm-mingw)").
  - D3's `env.UV` is not added to the Build tools raw lines; doctor's
    `uv:` line is already there (L13).

After the second review (2026-10-15, merge) and the user's notes on the
Checks page:

- Small fixes:
  - The Homebrew wrapper is chmodded 0755 after writing, since
    `WriteFile` keeps a leftover file's mode. A test covers the wrapper
    and `brewEnv()`, which `runBrew` uses.
  - `TestUpdateCheckWaits` taps Next and Back instead of calling
    `leaveWelcome`.
  - The Welcome list puts the Steam Deck item last, with a serial comma.
  - An open row's toggle reads "Hide details", like the log pane's.
  - "The checks stopped: ..." no longer capitalises after the colon.
- The Checks page lists only what the build depends on (the user's
  decision): build tools, game source, and one row per target, plus
  Notes when doctor has a warning not tied to a pin.
  - D3's "Your game files" row is gone. The game files are the next
    page's job, and doctor's `game files` line stays in the raw log only.
  - D3's "This computer" row is gone too. It never blocked anything:
    - the host's limits (an OS that cannot package a target) reach the
      page as that target's blockers;
    - too little disk, no git, or an overlapping folder reach it as the
      failed "Getting ready" row.
    Its lines (host, gen/, game env, DEVELOPER_DIR, next, any key a newer
    CLI adds) are information and stay in the log only, which replaces
    the "catch-all, never lost" rule in Risks.
  - "Game source" stays. It is the game's code clone at the release tag,
    a download the build depends on, not the player's game.
- The checks intro is gone in every state, and so is the separator that
  divided it from the table. The page is the list, the bar with Retry,
  and the log. The rows carry the state:
  - "Checking…" while busy;
  - amber "Needs something first" on a blocked target, with Next still
    enabled when another target is ready;
  - an open red "Getting ready: Could not finish" row on a failure, with
    the log's last line in red.
  - The intro's "you can also continue with the platforms that are
    ready" has no replacement; the enabled Next and the green target
    rows imply it.
- D6 is amended: state now has colour as well as its icon and words.
  - Icon and status colours by state: ready green (`ColorNameSuccess`),
    needs something amber (`ColorNameWarning`), failed red
    (`ColorNameError`). Info and busy use a primary-coloured icon and
    quiet text.
  - The same colours apply to the Platform page's blocked lines (an
    amber icon and amber text) and to the checks log line that reports a
    failure (`logPane.Fail`).
  - `palette.go` wraps the app theme. Fyne's green, amber and red are
    too light to read as text on white (green is about 1.7:1), so on a
    light background they become darker shades of the same hues, each at
    least 4.5:1 (`TestPalette`). The dark theme keeps Fyne's own colours.
  - Colour is never the only cue: the icon and the words still say the
    state.
- Platform glyphs (the user's request):
  - Each platform has a small original monochrome SVG for its kind of
    computer, not a vendor logo (the logos are trademarks and the binary
    is published):
    - `windows`: a window with four panes;
    - `macos`: a laptop;
    - `steamos`: a handheld with two sticks;
    - `linux` and any unknown target: a monitor on a stand.
    Fyne's own ComputerIcon is a laptop and would read as macOS, so it
    is not the fallback.
  - The glyphs are keyed by the config's target key (`platforms.go`) and
    themed with `theme.NewThemedResource`. Fyne's rasteriser fills by the
    non-zero rule, so each hole winds against its outline.
  - Checks rows lead with an icon for what the row is about: the platform
    glyph, a gear for Build tools and Getting ready, a download for Game
    source, a document for Notes. The state's icon and colour sit with
    the status.
  - The Platform page gives each buildable platform its own one-choice
    radio group with its glyph in front. Choosing one clears the others.
    Blocked platforms show their glyph before the amber line.
  - `TestPlatformIcons` checks that every known target has its own glyph,
    that an unknown target falls back to the generic one, and that the
    choices are exclusive.
- The screenshot set for approval is dark only. Light renders are kept
  only to check contrast.
- The Options page (the user's request: basic tweaks only, proper
  controls, and where config.toml is once installed):
  - A new option kind, `range`: integer `min`, `max`, `step` (default 1)
    and `default`, plus optional `labels` from a value to its words.
    `manifest.py`, `gamecfg.go` and `wizard config` refuse min not below
    max, a step that does not divide max - min, a default off the range or
    off a step, and a label for a value outside the range. Range keys on
    another kind are refused too. Every option may carry a `hint`.
  - One control per kind: a checkbox for a bool; radio buttons for a
    choice of up to three values and a drop-down above that; a slider
    for a range, with the value and its label beside it ("2 (1280×960)").
    The Slider takes keyboard focus and moves on the arrow keys. A hint
    is quiet caption text under its control. The Summary shows a
    labelled value the same way.
  - BLiNX 2 lists only render scale, fullscreen and the HUD pack. Frame
    pacing, keyboard and mouse leave the wizard; their defaults stay in
    `config.default.toml`. The HUD pack's font caveat moved into its hint.
  - The scale slider stops at 4, not 6. The toolkit clamps
    `render.scale` to 1..4 (`SCALE_MAX` in `src/enhance/enhance.c`); a
    6× surface (3840×2880) would fit both backends' 16384 limit, so 6
    needs only a toolkit change, which this change does not make.
  - The intro is one line. A quiet note at the page's foot gives the
    chosen platform's config.toml, built from the config's data folder
    plus `config/config.toml` in that platform's separator, e.g.
    `%LOCALAPPDATA%\BLiNX2\config\config.toml`; it follows the platform
    on each visit. It shows the default data folder: `data.dir_env` is not
    in the wizard config.
  - A hint may end in a link (the user's request: a place to get the
    HUD font). `hint_link = { text, url }` needs both keys, words to show
    and an https address with a host; `manifest.py`, `wizard config` and
    `gamecfg.go` refuse anything else. The page draws it as a Hyperlink
    under the hint and opens it through the same opener as the update
    note. Any https host is allowed here: the address is the game
    author's, embedded from the release tag. The update dialog's
    github.com rule is unchanged.
  - BLiNX 2's HUD option links "Get PT Sans Narrow (free, Google Fonts)"
    to `https://fonts.google.com/specimen/PT+Sans+Narrow` (the family
    has the Bold weight, 700), and its hint ends "install it, then
    build".
  - A checkbox's hint and link line up with its words, after the box;
    a slider's or a choice's line up with its label.
  - Round-3 review fixes:
    - The slider runs over the range's indexes (0 to n-1, step 1), each
      mapped to `min + i*step`. Fyne snaps a slider to multiples of Step
      counted from 0, so a range from 1 by 2 driven by value showed 2
      and kept the old value. A value the state refuses is logged and
      shown, never dropped. `TestOptionsRangeOffStep` covers 1..7 by 2.
    - `manifest.py` now applies the binary's rules too: label keys in
      plain decimal form, a span of at most 10000, and no control
      characters in a hint link's address. A broken address is reported
      against its option instead of raising.
    - Web addresses (the hint link, the release page) open on Windows
      through `rundll32 url.dll,FileProtocolHandler`, not explorer, which
      treats a comma as a switch separator. Folders still open in
      explorer.
    - `new`'s commented [wizard] example shows the scale as a range.
  - `TestOptionsPage` checks the slider's range, value, readout and that
    moving it sets the option, the note on Windows and macOS, and the HUD
    option's link.

## Risks / Trade-offs

- `Label.Selectable` is new in Fyne 2.6; selecting across 500 monospace
  lines re-lays the label on each refresh. The 100 ms coalescing keeps
  the UI thread idle during a fast log; if a build's output still
  stutters the expanded view's line count drops to 200 (one constant).
- The deprecated `theme.LightTheme()`/`DarkTheme()` are used in one
  test for fixed-variant images only; Fyne 3 would need the
  `fyne.Theme` wrapper the deprecation note describes.
- The row table keys on the CLI's `doctor` line keys. A key the CLI
  renames drops out of its row and is only in the log (there is no
  catch-all row since D9); `TestCheckRows` on the saved samples catches
  a drift when the CLI's test data is refreshed.
- The thin bar's phases are coarse (five to seven steps); the clone and
  the uv download dominate the time and each is one phase. The log's
  latest line beneath it shows the download percentage, so the player
  sees movement inside a phase.
- Longer copy on the welcome page: at 580 high it fits above the fold
  with the three statements; the page keeps its `VScroll` for small
  screens and large text scales.
- The CLI release moves to v0.7.1 and cat's `[cli]` pin follows, as
  with any wizard change the game's binaries must carry; nothing else
  in the CLI changes, so the pin bump is argv-neutral for the game's
  own commands.

## Migration Plan

Additive inside the module; no config schema change, no CLI flag
change, `--dry` and developer mode unchanged. Rollback is a revert of
the squash commit. Players see the new pages with the next wizard
release of the game.

## Open Questions

1. Resolved: the footer shows the wizard version only; the four pins
   go in the Summary's "Technical details" (see D1).
2. The step bar fill: the current page counted as reached (2 of 8
   fills two segments, as specified) or as pending (fills one). Decided
   here as reached; a one-line change if the screenshots read wrong.
