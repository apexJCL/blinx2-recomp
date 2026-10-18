## Why

The player build wizard (`openspec/changes/build-wizard`, CLI
v0.7.0 a3208e4, cat abf7ae9) works end to end, and the user's first
click-through of the Mac `.app` (2026-10-15, `runs/wizard-click/`) found
the pages hard to read for the people it is for. The user's requests,
verbatim:

- Show a progress bar for the 8 steps in the upper section.
- Move version to the bottom-right corner, as a footer, with small text.
  It is always visible but out of the way.
- Shorten 1st step welcome message, as for overall messages remember this
  is oriented to non-technical users. We can show disclaimers at the very
  beginning, that this tool does not contain proprietary code, that it'll
  never upload anything anywhere and that by all means is intended solely
  for personal usage.
- For step 2, the checklist, show it as a simple table with individual
  status icons. If any of them have issues, just show a warning icon that
  when clicked, expands a row underneath and gives a more sensible
  overview of what went wrong. Show a general "progress" indicator as a
  smaller progress-bar (thinner) below the table of dependencies; the
  table itself is scrollable but the progress remains always visible. For
  the bottom part, which looks like a log text block: keep it collapsed
  and only display the latest line at any given time; once expanded,
  render the log in an appropriate read-only text box so the user can
  copy text if needed.

What the pages do today (`xboxrecomp-cli/wizard/internal/screens/`,
read at a3208e4): the window is a `Border` with a bold title label on
top ("Checks  (2 of 8)"), Back and Next at the bottom, and the page in
the middle. The welcome page is one bold line with the version, a line
with the four pins, a three-sentence paragraph, the install folder, the
update checkbox and, on a first run, the signing note. The checks page
prints `doctor --json`'s `lines` verbatim in monospace (host, uv, lock,
cmake, ninja, tools py, cli, toolkit, llvm-mingw, game files, gen/, game
env, DEVELOPER_DIR, makensis, next), then one sentence per target, then
the fix buttons, then the clone and download log as a `widget.List` of
monospace rows filling the rest of the page. The build page is the same
list under a `widget.ProgressBar`. The text everywhere is the CLI's own
words (`.venv`, `uv.lock`, `blinx2 setup`), which the player never
needs.

Spec by the reviewer; the implementation and
its review are the next agent's.

## What Changes

All of it is in the generic Go module `xboxrecomp-cli/wizard/` (the
CLAUDE.md Go exception), in `internal/screens` and one callback in
`internal/screens/work.go`; nothing in Python, in cat's code or in the
game. The strings name the game only through the embedded config.

- **Page frame.** A header with the page title, "Step n of 8" and a
  segmented step bar; the wizard's version in a small, low-contrast
  footer at the bottom right under the Back and Next row (the release,
  CLI and toolkit pins move to the Summary's technical details). The window
  size stays 780 by 580.
- **Welcome page.** A one-line heading, a two-sentence introduction and
  three short "Before you start" statements: no game inside, downloads
  only what it needs, sends nothing of yours (the honest form: the one
  request it makes is the release check, which the checkbox below turns
  off). Then the install folder, the checkbox and the first-run signing
  note, all shortened.
- **Checks page.** A table of rows with an icon and a status in plain
  words (this computer, build tools, game source, your game files, one
  row per platform, notes), each row with a Details toggle that opens an
  explanation and the fix button under it. A thin progress bar below the
  table, always visible while the table scrolls, that follows the
  preparation phases (uv, git, the clone, each extra download, doctor).
  Retry beside it.
- **Log pane** on the checks and build pages: collapsed to the latest
  line with a Details toggle; expanded, a read-only selectable monospace
  text box with a Copy button. The build page keeps its wide progress
  bar and step label on top (they are the build's primary progress).
- **Copy on every page** rewritten for a non-technical player, in one
  file, with the error texts the pages show (missing file, no
  `default.xbe`, disk space, a stopped build) included.
- **Tests:** the row mapping on saved `doctor --json` samples, the plain
  explanations for the known blockers, the log pane's collapsed line and
  expanded text, the frame's footer and step text, a check that the
  screens package names no game, and a screenshot test (opt-in by an
  environment variable) that renders every page headless through Fyne's
  test app into `runs/wizard-ui/` for the user's approval before the
  merge.

## Impact

- **Render backends, hosts, goldens:** none. No runtime, renderer, audio
  or kernel code; no golden is affected. The wizard runs on Windows,
  macOS and Linux as before; the bundles it makes are unchanged.
- **Toolkit:** not touched; nothing for upstream.
- **CLI (`xboxrecomp-cli`):** `wizard/internal/screens/` (the frame,
  the checks table, the log pane, the copy file, the thin bar, tests)
  and `Prepare`'s signature in `work.go` (a progress callback). The
  Python package, `docs/wizard.md`'s build and pin sections and the
  workflow template are unchanged; the release after the merge is
  v0.7.1 and cat's `[cli]` pin moves to it so cat's wizard builds carry
  the new pages.
- **cat:** this spec; the `[cli]` pin bump at merge time (one line in
  `game.toml`), and `docs/packaging.md`'s "The wizard" paragraph only if
  it describes a page's text (task 5.4).
- **Public repos and legal:** the new disclaimers say what the binary
  does and nothing more: it holds no game code or data; it downloads the
  pinned tools and the game's source by checksum; it sends nothing of the
  player's anywhere, and the one request it makes (the GitHub release
  check) can be switched off. Screenshots for the user's approval go to
  `runs/wizard-ui/` (never a worktree, never published; they show the
  sample config's game name, no game data).
- **Not in scope:** an accessibility tree (Fyne has none; a follow-up as
  before), a Cancel button on the checks page (review L-e, a separate
  follow-up), new options or pages, any change to the CLI's `doctor` or
  `--plain` output, translations.
