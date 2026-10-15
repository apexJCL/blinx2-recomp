Conventions: **CLI** = branch `feat/wizard-ui-polish` off `main` a3208e4
(v0.7.0) in the CLI worktree `wt/wizard-ui/xboxrecomp-cli`, commits
authored and committed as `carlos <4037632+apexJCL@users.noreply.github.com>`,
no tracker ids, host names, private paths or claude.ai links in the
messages (the squash message leaves out any `Claude-Session:` line);
**cat** = `wt/wizard-ui/cat`, branch `spec/wizard-ui-polish` (this spec;
the `[cli]` pin bump at merge time is the main session's, 6.2). The
toolkit and the Python package are not touched. Go runs in user space
only: `./blinx2 wizard check --dev` from a cat worktree, or `xbr wizard
check` from the CLI, fetches the pinned Go into `wizard/.tools/` and runs
`check.sh` with `GOTOOLCHAIN=local`; `DEVELOPER_DIR=/Library/Developer/CommandLineTools`
on the Mac. Design decisions are cited as D1-D8. Screenshots and any
raw run go to `runs/wizard-ui/`, never inside a worktree.

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 1 Frame: header, step bar, footer, thin bar | CLI | S | - |
| 2 Checks page: rows, details, fixes, phase progress | CLI | M | 1 |
| 3 Log pane on both pages; summary details | CLI | S | 1 |
| 4 Copy on every page | CLI | S | 2, 3 |
| 5 Tests, screenshots, gates | CLI | S | 4 |
| 6 Review and merge | main session | S | 5 |
| 7 Follow-through | main session | XS | 6 |

## 1. The frame (D1, D2)

- [x] 1.1 `internal/screens/thinbar.go`: the `thinBar` widget (`Value`,
  `Segments`, `SetValue`, the two-rectangle renderer, height 6, corner
  radius 3). `TestThinBar`: rendered with `software.Render` at 0, 0.5
  and 1, continuous and with 8 segments; the fill width and the number
  of primary-coloured segments match.
- [x] 1.2 `wizard.go` `New`: the `Border` becomes header / padded body /
  `VBox(nav, footer)`; `header` = title (bold, sub-heading size), the
  "Step n of 8" caption and the segmented `thinBar`; `nav` uses
  `layout.NewSpacer()` (`widgetSpacer` removed); `footer` = the
  right-aligned caption-size, quiet version line "Build wizard
  <version>" (Open Question 1: version only; the welcome page's `pins`
  string moves to the Summary's "Technical details"). `render(i)` sets the
  title, the step text and the bar. Window size unchanged.
- [x] 1.3 `TestFrame`: after `render(1)` the step label reads "Step 2
  of 8", the bar's value is 2/8, the footer contains `Options.Version`
  and the Summary's technical details the release tag; the footer object is the same on every page.

## 2. The checks page (D3)

- [x] 2.1 `work.go`: `Prepare(ctx, cfg, pins, root, devGame, log, step)`
  with `step func(done, total int)` called after uv, git, the clone (or
  the `--game` check) and each host-filtered fetch entry; `total` = 3 +
  the entries; `nil` allowed. `TestPrepareSteps` is not possible
  without a network, so `TestPrepareStepTotal` covers the counting
  helper (`prepareTotal(cfg, host)`) on the sample config with and
  without fetch entries.
- [x] 2.2 `internal/screens/checks.go`: `rowState`, `checkRow`,
  `checkRows(cfg, env, d, prepErr, brew)` building the rows of the D3
  table from `d.Lines` (keyed by the text before the first `:`), the
  catch-all into "This computer", the per-target rows from
  `d.Blockers` with `runner.Actions`, the "Notes" row, the busy table
  when `d == nil`, and the single "Getting ready" failure row.
  `plainBlocker(reason, brew)` and `plainPrepare(err)` with the D3 and
  D5 strings.
- [x] 2.3 `internal/runner/testdata/doctor-blocked.json`: a saved
  `doctor --json` from a Mac without Homebrew formulae and with no
  makensis (take it from a real run with `./blinx2 doctor --json` on a
  tree where `brew` lacks one formula, or edit the existing sample's
  `blockers` by hand and say so in the file's neighbour `README` line),
  so a blocked target has a fixture. `TestCheckRows`: on `doctor.json`
  every target row is OK, "Build tools" is Later with the five fetched
  tools in its detail, "Your game files" is Later, "This computer"'s
  detail carries the `gen/`, `game env`, `DEVELOPER_DIR` and `next`
  lines; on `doctor-blocked.json` the macOS and Windows rows are Warn
  with one `brew` action each and the detail text from `plainBlocker`;
  with `d == nil` every row is Busy; with a `NeedError` the table is
  the one failure row with its action. `TestPlainBlocker`: the five
  cases of D3 plus the fall-through.
- [x] 2.4 `wizard.go` `checksPage`, `runChecks`, `showChecks`: the view
  of D3 (intro label, the scroll of rows with icon, name, status, the
  Details toggle and the hidden detail with the action buttons, the
  separator; the thin bar and Retry beneath the scroll; the log pane
  under them). `runChecks` passes the `step` callback that sets the
  bar from the UI goroutine (`fyne.Do`), the bar reaches 1 when
  `doctor` has parsed and 0 on a failure. The action buttons keep
  their behaviour (`actionButton`), only their labels change (D5).
  `ready` unchanged.
- [x] 2.5 `TestChecksView`: with the saved blocked sample, the page
  renders, the blocked row's toggle exists and tapping it
  (`test.Tap`) shows the detail container with the action button; with
  `doctor.json` no toggle is on a target row; the intro text is the
  "Some platforms…" line for the blocked sample and the "Everything is
  ready…" line for the other.

## 3. The log pane and the summary (D4)

- [x] 3.1 `logview.go` becomes `logPane`: collapsed row (toggle plus the
  latest line), expanded view (toggle, Copy, the scroll around the
  selectable monospace label with the last 500 kept lines), the 100 ms
  coalesced refresh, `Append`, `Clear`, the tee and the 5000-line cap
  kept. Copy uses `fyne.CurrentApp().Clipboard()`.
- [x] 3.2 The checks and build pages use it; the build page keeps the
  `ProgressBar` and the step label on top and gains the one-line
  "This takes a while…" sentence (D5). `startBuild` leaves the pane
  collapsed.
- [x] 3.3 `summaryPage`: the plain rows of D5 and the closed
  `Accordion` "Technical details" with the selectable monospace label
  carrying today's commands and seed text; `fillSummary` fills both.
  `TestPages`'s `--seed-config` / `scale = 2` assertion moves to the
  details text.
- [x] 3.4 `TestLogPane`: after three `Append`s and the coalescing delay
  (the test calls the flush directly rather than sleeping), the
  collapsed label holds the third line; after `test.Tap` on the toggle
  the selectable label holds all three; Copy puts them in the test
  app's clipboard; 600 appends keep the shown text at 500 lines and
  the copied text at 600.

## 4. The copy (D5, D6, D7)

- [x] 4.1 `internal/screens/copy.go`: every string of D5 as constants
  and `func(name string) string`s; the pages use them (welcome, checks,
  your game, platform, options, summary, building, done, the two
  confirms, the dump errors in `checkDump`, the overlap and disk-space
  errors in `Prepare` through `plainPrepare`). The welcome page's three
  "Before you start" rows with `InfoIcon`. The signing note and the
  release card keep their place.
- [x] 4.2 `TestCopy`: the welcome text names the game from the config
  and none of the player-facing strings contains `uv`, `venv`, `xbr`,
  `cmake`, `ninja`, `llvm-mingw`, `toolkit`, `clone` or `repo` (a list
  in the test); `TestNoGameInSource` scans the package's non-test `.go`
  files for `blinx`, `BLiNX`, `burnout` and `b3`.

## 5. Tests, screenshots and gates (D8)

- [x] 5.1 `TestPages` still renders every page on the sample config
  (updated for the new widgets). `TestScreenshots` under
  `WIZARD_SHOTS`: every page, the checks page busy / ready / blocked
  with the row open, the log pane collapsed and expanded, each in the
  light and dark built-in themes, 780 by 580, written as PNG through
  `software.RenderCanvas`.
- [x] 5.2 Run it: `WIZARD_SHOTS=<workspace>/runs/wizard-ui/shots go test
  ./internal/screens -run TestScreenshots` with the pinned Go (from
  `wizard/.tools/`, `GOTOOLCHAIN=local`). Look at the images (the
  `Read` tool shows PNGs) and fix what reads wrong: truncated footer,
  a clipped row, a bar that does not fill, text that wraps badly at
  780. List the files in `runs/wizard-ui/README.md` with one line each
  and tell the orchestrator they are ready for the user. The user's
  approval of the images is a gate for 6.2; changes they ask for go
  back to this branch.
- [x] 5.3 Gates: `./blinx2 wizard check --dev` from a cat worktree
  pointed at the branch (`XBOXRECOMP_CLI_DIR=<wt>/xboxrecomp-cli`) or
  `xbr wizard check`: gofmt empty, vet, every package's tests,
  staticcheck when installed, and the double build with equal sha256s
  for the three binaries and archives (`check.sh` plus the build, as
  BLX-130 ran it; log to `runs/wizard-ui/check.log`). The CLI's `uv
  run pytest tests` and `uv run ruff check . && uv run ruff format
  --check .` are run once to show nothing in Python moved. No golden,
  no Proton run: no runtime change (say so in the review request).
- [x] 5.4 Docs: cat's `docs/packaging.md` "The wizard" paragraph and
  the CLI's `docs/wizard.md` are read; a sentence that describes a
  page's old text or layout is updated (none is expected: both describe
  the flow, not the words). `wizard/README.md`'s package table gets
  `thinbar.go`, `checks.go`, `copy.go` and the renamed `logPane` in
  the `internal/screens` row if the row lists files; otherwise
  unchanged.
- [x] 5.5 One smoke of the real binary on the Mac: `./blinx2 wizard
  build --dev --only macos` from the cat worktree, the app run with
  `--root <runs/wizard-ui/root> --no-update-check` to the checks page
  on a fresh root (the download and clone, the table filling, the thin
  bar moving), then quit. The screen may be locked: if the window
  cannot be seen, record that and rely on 5.2. No game launch, no
  sound. Done 2026-10-15: the build and `--dry` passed; the screen was
  locked, so the app was only launched for 8 s on a fresh root (it
  stayed up) and the checks page was not walked by hand.

## 6. Review and merge (main session)

- [ ] 6.1 Opus review of the CLI branch; fixes go back to the branch's
  agent. The review checks the disclaimers against the code (one GET in
  `update.Latest`, downloads by checksum in `fetch`, no other network
  use), the copy's reading level, and that no game word reached the
  module.
- [ ] 6.2 After the user's approval of the screenshots: squash merge to
  CLI `main` as the noreply identity (`wizard: step bar, footer, plain
  copy, checks table and collapsed logs` or similar), bump to v0.7.1
  and tag locally; cat `game.toml` `[cli]` moves to the v0.7.1 sha
  (`blinx2 pins refresh` output checked), committed on cat with the
  spec's branch merged (`openspec: wizard-ui-polish` is this spec's
  commit; the pin bump is `wizard: ...`). Public pushes stay the user's
  batched rounds (the CLI's round before cat's).

## 7. Follow-through (main session)

- [ ] 7.1 Copy the agent's untracked notes to `notes/wizard-ui/`; the
  screenshots and logs stay in `runs/wizard-ui/`; remove the worktrees
  (`git worktree remove --force` plus `rm -rf wt/wizard-ui`), keep the
  branches.
- [ ] 7.2 `cat/TASKS.md`: the merge entry under the wizard's; the
  follow-ups that stay (the accessibility tree; the checks-page Cancel
  button L-e; Open Question 1's footer content if the user changes it
  later); BLX-138 closed.
- [ ] 7.3 Archive the change (`openspec archive wizard-ui-polish`).
