Conventions: **CLI** = branch `feat/wizard-build-feedback` off `main`
beb838f (v0.7.3) in the CLI worktree `wt/wizard-fb/xboxrecomp-cli`,
commits authored and committed as
`carlos <4037632+apexJCL@users.noreply.github.com>`, no tracker ids, host
names, private paths or claude.ai links in the messages (the squash
message leaves out any `Claude-Session:` line); **cat** =
`wt/wizard-fb/cat`, branch `spec/wizard-build-feedback` (this spec, the
`game.toml` and docs changes; the `[cli]` pin bump at merge time is the
main session's, 7.2). The toolkit is not touched. Go runs in user space
only: `./blinx2 wizard check --dev` from the cat worktree with
`XBOXRECOMP_CLI_DIR=<wt>/xboxrecomp-cli`, or `xbr wizard check` from the
CLI, fetches the pinned Go into `wizard/.tools/` and runs `check.sh` with
`GOTOOLCHAIN=local`; `DEVELOPER_DIR=/Library/Developer/CommandLineTools`
on the Mac. Design decisions are cited as D1-D10. Screenshots, logs and
any raw run go to `<workspace>/runs/wizard-fb/`, never inside a worktree.
The Windows PC is used under `D:\xbr` only, never `C:`; ask the user
before switching the PC's boot. No sound on the Mac; no game is launched
anywhere. Each phase ends in one or more commits with `area: what
changed` subjects.

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 1 CLI Python: heartbeat, flush, private_leaks, optional icon key | CLI (Python) | S | - |
| 2 Wizard: parser, build page, failure screen, notice, folders | CLI (Go) | M | 1.1 (the line format) |
| 3 The icon: icongen, the three builds, the embed | CLI (Go + Python) | M | - |
| 4 Gates, screenshots, host runs | CLI | M | 2, 3 |
| 5 Docs and cat | CLI, cat | S | 2, 3 |
| 6 Review and merge | main session | S | 4, 5 |
| 7 Follow-through | main session | XS | 6 |

## 1. CLI, Python (D1, D7, D8)

- [x] 1.1 `src/xboxrecomp_cli/package/progress.py`: `HEARTBEAT_S = 20`;
  `View.last_say` set in `say()`; `View.heartbeat()` returning
  `  <label> ... <elapsed>[, <eta>][ | <last>]` (D1: `fmt_time(now -
  t0)`, `eta()` when not empty, `self.last` cut to 120 characters, the
  ` | ` part absent while `last` is empty); `paint()`'s plain-mode branch
  prints it through `say` when `label` is set and `now -
  max(last_say, t0) >= HEARTBEAT_S`, then returns as before. The
  module docstring's "plain" line gains "and a heartbeat every 20 s of
  silence". In `run_step`'s `reader()`, `log.flush()` after
  `log.write(chunk)`.
- [x] 1.2 `tests/test_progress.py`: `test_plain_heartbeat_clock` with
  `View("plain", out, clock=lambda: t[0])`: no line at 0 s; one line
  `  recomp ... 0:20` after 20 s with `last` empty; `line("[1/2] x")`
  then 20 s more gives `  recomp ... 0:40 | [1/2] x`; a `progress()`
  line resets the wait (15 s after it: nothing; 20 s: a line); with
  `timings = {"recomp": 600.0}` the ETA appears as `, ~9 min left`
  between the elapsed time and the ` | `. `test_plain_heartbeat_child`:
  a fake child that sleeps 0.7 s with `HEARTBEAT_S` monkeypatched to
  0.25 prints between one and four heartbeat lines and nothing in tty
  mode changes (`test_silent_child_still_repaints` still passes).
  `test_step_log_is_live`: a child that prints one line and sleeps
  0.8 s; a `v.line` hook reads the step log at the first line and finds
  it there (the flush).
- [x] 1.3 `src/xboxrecomp_cli/package/lib.py` `private_leaks` (D7):
  `home_pattern(home)` (separator runs as `(?:\\\\|\\|/)+`, `re.I`,
  `len(home) > 3`, the `/` guard kept) and the module-level `PATH_RE`
  with the look-behind and `[A-Za-z]:[\\/]`, bracketed letters kept
  with the existing comment. `tests/test_package_lib.py`
  `test_private_leaks` gains the positives (the Windows users-folder
  path with forward slashes in a JSON string, written split as the
  existing `"/Us" + "ers/"` case is so the public audit stays clean;
  `'note: built at C:\\\\Users\\\\x'` mid-string; `'at /home/x'`;
  `home=r"C:\Users\x"` against `'{"p": "C:\\\\Users\\\\x\\\\g"}'` and
  against the same lower-cased with forward slashes) and the negatives (`'game_files/home/x'`,
  `'"C:X"'`, `home="/"` on `'/x'`).
- [x] 1.4 `src/xboxrecomp_cli/manifest.py`: `wizard.icon` `(STR, "")`
  (optional); `wizard.py` `_file_rules`: when set, the file exists in
  the tag's tree and is a PNG (signature) or an SVG (bytes start with
  `<svg` or `<?xml` after optional whitespace or a BOM); `resolve()`
  returns `None` bytes when unset. `docs/manifest.md`'s wizard table:
  "icon: optional; a PNG or SVG; the wizard's own gamepad icon
  otherwise". `tests/test_wizard.py`: a config without `icon` passes;
  an SVG passes; a JPEG is refused with "not a PNG or SVG".
- [x] 1.5 Run `uv run pytest tests` and `uv run ruff check . && uv run
  ruff format --check .`. Check the stricter leak test against a real
  manifest: `blinx2 package macos --no-build` is too slow for a gate, so
  read the two `manifest.json` files from the user's last Mac and
  Windows bundles when they exist under `runs/` (ask the orchestrator
  for the paths) through `python -c` with `private_leaks` and expect
  `[]`; record the result in the commit body. Commit (`package: a
  heartbeat in plain mode, the step log flushed, Windows paths in the
  leak check`, and `wizard: [wizard] icon is optional and may be an
  SVG`).

## 2. The wizard (D2-D6)

- [x] 2.1 `wizard/internal/runner/progress.go`: `heartRE`, the fields
  `Tool` and `StepElapsed`, the `feed` case (sets `Label` when empty,
  returns true, never moves `Fraction`). `testdata/package-heartbeat.txt`
  (a recomp step as D2 lists; one line in `testdata/README` says it was
  written by hand from the 1.1 format). `runner_test.go`
  `TestProgressHeartbeat`: `Tool` and `StepElapsed` after the file;
  `Pct` 21 after the `21%` line and unchanged by the heartbeat after
  it; the bar values never go back; a tool line holding ` | ` is kept
  whole.
- [x] 2.2 `wizard/internal/screens/thinbar.go`: `Height` (default
  `thinBarHeight`), `Pulse`, `StartPulse`, `StopPulse`, the sheen
  rectangle and its `fyne.Animation` (D3); the renderer's `Destroy`
  stops it. `screens_test.go` `TestBuildBarPulse`: at `Value` 0.5 the
  animation's function at 0.25 and 0.75 puts the sheen at two
  positions inside `[0, 0.5*width]`; at `Value` 0 inside the whole
  track; `StopPulse` hides it; `Value` 1 stops it.
- [x] 2.3 `wizard.go` `buildPage`, `startBuild`, `runSteps`,
  `progressText`: the bar is a `thinBar{Height: 10}` pulsing from
  `startBuild` to the end; `w.buildClock` (a `quietText`) at the right
  of the step label row with `buildClockText(frac, part, all)`; the
  ticker goroutine (1 s, `fyne.Do`, stopped by a channel closed when
  `runSteps` returns); `buildStart`, `partStart` reset on a stage index
  change and on each command's start (D3). `copy.go`: `buildClock =
  "%s in this part · %s in all"`, `buildClockPct = "%d%% · "`.
  `TestBuildClock`: the text at 0, 65 and 3700 s from set starts; a
  `== [2/5] setup ==` line through `Feed` resets the part start (test
  the reset function directly, no sleeping).
- [x] 2.4 Failure and cancel (D4). `logpane.go` `Tail(n)`;
  `wizard.go`: `buildFailure`, `errCanceled`, `failureExcerpt` (pure,
  in its own small file `failure.go` with `fmtClock`), `runSteps`
  returning them, `startBuild`'s `Logf` entries (`build stopped at
  <step>: <cmd>: <err>` plus the indented excerpt; `build canceled by
  the player`; `build done: <bundle>`), `fillDone`'s failure and cancel
  layouts (the step, "What the build said:" over `mono(excerpt)`, the
  quiet exit line, "The full logs are in {dir}.", the buttons; the
  cancel page), `installNow`'s Windows setup lookup. `copy.go`:
  `doneSaid`, `doneExit`, `doneLogs`, `doneCanceled`. Tests:
  `TestFailureExcerpt` (a tail with a traceback in the middle and lines
  after it: the excerpt starts at the traceback; no traceback: the last
  12 non-blank lines; a 300-character line is cut to 200; 60 lines of
  traceback are cut to 40); `TestDoneFailure` (a `*buildFailure` with a
  three-line tail renders the step, the excerpt text in a selectable
  label and the logs line with `build-logs`; `wizard.log` in the test's
  settings dir holds the excerpt); `TestDoneCanceled` (no excerpt, the
  cancel sentence, Retry present); `TestInstallNowWindowsSetup` (the
  `*-setup.exe` lookup on a temp folder, zero and one match).
- [x] 2.5 `notice.go` `noticeBox` (D5), the three constants replacing
  `bundleRule` in `copy.go`, `fillDone` using it with the vertical
  padding on both outcomes. `TestNoticeBox` as D5 (both themes through
  `Theme(theme.LightTheme())` and `Theme(theme.DarkTheme())`, with the
  `lint:ignore SA1019` note the screenshot test uses); `TestCopy`
  unchanged and passing.
- [x] 2.6 The folders (D6). `hostinfo.go`: `Settings.Out`,
  `DefaultOut(root) (dir, why)` over a pure `outCandidate(goos, exe,
  tmp, env map) (dir, why)`, `BundleNeed`, `TreeSize`, `SameVolume`
  (`volume_windows.go` with `filepath.VolumeName`, `volume_unix.go`
  with `Stat_t.Dev`, both through the nearest existing parent).
  `model.go`: `PackageArgs(seedPath, out)`, `Steps(seedPath, out)`;
  `model_test.go` expectations gain `--out`. `wizard.go`: `w.out`
  resolved in `New` (the setting when set, else `DefaultOut(w.root)`
  with the `why` logged), the Welcome row (`outLabel`, `pickOut`,
  `outputFolder`, `outputFolderIs` with 4 GB), `pickRoot` recomputing a
  defaulted `w.out`, `checkDump`'s bundle check with `dumpNoSpaceOut`,
  `fillSummary`'s "Output folder: %s" row, `seedArg`/`Steps` callers
  passing `w.out`, `fillDone`'s button text `openBundleFolder`.
  `main.go`: `--root`'s help, `dry()` printing `build folder:` and
  `output folder:` (the same resolution, through `hostinfo`);
  `main_test.go` updated. The renames of D6 in `copy.go` ("Build
  folder" everywhere "Install folder" was; `installText["windows"]`'s
  added sentence). Tests: `TestDefaultOut` (the `.app` case, the temp
  case, Program Files, `/Applications`, a plain writable folder, an
  unwritable folder through a 0o500 temp dir, each with its `why`);
  `TestWelcomeFolders` (two rows, the saved `out` round-trips through
  `settings.json`, an empty setting shows the default); `TestSummaryOut`
  (the row and `--out` in the technical details); `TestDumpSpace`
  (`SameVolume` true: one check with the sum; a fake `Free` per path
  giving two volumes: the output message names the output folder).
- [x] 2.7 `package/macos.py` `wrap_macos`: check whether `hdiutil
  create` refuses an existing `.dmg`; if it does, remove the old file
  first (as `wrap_windows` does) so a same-version re-run from the
  wizard succeeds; `tests/test_package_lib.py` or a new
  `test_package_macos.py` covers the removal with `hdiutil` faked.
  Commit the phase (`wizard: a bar that moves, clocks, the failure
  excerpt, the notice box, the output folder`).

## 3. The icon (D8)

- [x] 3.1 `wizard/icon/`: `device-gamepad-2.svg` copied verbatim from
  Tabler Icons at a named version (the version, the URL and the
  licence in `wizard/icon/README.md`), `wizard-icon.svg` composed as
  D8 (1024 square, radius 22%, fill `#1e4d6b`, the glyph white at 62%
  with a 7% stroke), `LICENSES/tabler-icons-MIT.txt`; `wizard/README.md`'s
  Dependencies section names the icon set and its licence.
- [x] 3.2 `wizard/cmd/icongen/main.go`: `-in FILE -out DIR`, the nine
  PNG sizes, `wizard.ico` (PNG entries at 16, 24, 32, 48, 256),
  `Icon.png` (1024), rendered through `canvas.NewImageFromResource`
  and `software.Render` under a transparent-background theme wrapper
  (D8); `-size N` renders one PNG to stdout for the test and the
  staging step. `main_test.go` `TestIcongen` as D8 (centre colour,
  corner alpha, the `.ico` header and entries, `icon-256.png` equal to
  `internal/gamecfg/icon.png`).
- [x] 3.3 `internal/gamecfg/icon.png` (the generic 256 render,
  committed; the module's one binary), `embed.go` `IconPNG`,
  `cmd/wizard/main.go` `a.SetIcon(...)` before `screens.New`.
- [x] 3.4 `src/xboxrecomp_cli/wizard_build.py`: `stage_module` writes
  the game's 256 render over `icon.png` when the game has an icon
  (`go run ./cmd/icongen -in <game icon> -size 256`); `build()` runs
  `icongen -in <game icon or icon/wizard-icon.svg> -out <work>/icon`;
  `build_macos` passes `<work>/icon/Icon.png`; `build_windows` writes
  `<work>/icon/wizard.rc` and runs `<mingw>/bin/llvm-windres` with the
  pe-x86-64 target into `<src>/cmd/wizard/rsrc_windows_amd64.syso`
  before `go build` and removes nothing (the staged copy is scratch);
  `build_linux` stages `icon/<name>.png` and `icon/<name>.desktop` into
  the Docker context and `wizard/linux/Dockerfile`'s `tar` lists the
  three files. `tests/test_wizard.py`: the windres command line, the
  desktop file's text, the `Dockerfile` naming the three, `stage_module`
  with and without a game icon.
- [x] 3.5 `wizard/check.sh` unchanged; `xbr wizard check` already
  builds twice and compares. Commit (`wizard: a gamepad icon on every
  platform, from a pinned SVG`).

## 4. Gates, screenshots and host runs

- [x] 4.1 Go: `./blinx2 wizard check --dev` from the cat worktree
  (gofmt, vet, every package's tests, `-race`, staticcheck, the cold
  double build of the three assets with equal sha256s); log to
  `runs/wizard-fb/check.log`. Python: `uv run pytest tests`, `uv run
  ruff check . && uv run ruff format --check .` in the CLI; `uv run
  pytest scripts` and the ruff pair in cat. No golden, no Proton run:
  no runtime change (say so in the review request).
- [x] 4.2 Screenshots (D10): `TestScreenshots` gains the states listed
  in D10; run `WIZARD_SHOTS=<workspace>/runs/wizard-fb/shots go test
  ./internal/screens -run TestScreenshots` with the pinned Go; look at
  the dark set and the light set for contrast (the notice box, the
  clocks, the excerpt); list them in `runs/wizard-fb/README.md` with
  one line each, plus `icon-256.png` and `icon-32.png` from `icongen`
  for Open Question 2; tell the orchestrator they are ready. The user's
  approval is a gate for 6.2.
- [x] 4.3 The double build with the icon: in `check.log` the Windows
  binary's two sha256s are equal with the `.syso` in place. If they
  differ, `icongen` writes the `.syso` itself (D8's fallback) and the
  windres route is removed; note which route shipped in the commit body
  and in `docs/wizard.md`.
- [ ] 4.4 Native Windows run (the Windows PC, `D:\xbr` only; ask the
  user before switching the boot). Build the Windows asset on the Mac
  (`./blinx2 wizard build --dev --only windows` from the cat worktree)
  and copy the exe to `D:\xbr\wizard\`. Run it as `blinx2-wizard.exe
  --game D:\xbr\cat --root D:\xbr\wizard-root --no-update-check` with
  the user's dump on that PC (never copied anywhere else). Check and
  record in `runs/wizard-fb/windows.md`:
  - Explorer shows the gamepad icon on the exe at the small and large
    views, in the taskbar and on the window;
  - Welcome has "Build folder" and "Output folder", the latter
    `D:\xbr\wizard\dist`; changing it is remembered across a restart;
  - on the Build page the bar's sheen moves and the clocks tick every
    second through a silent stretch (watch the recomp step: the
    collapsed log line shows `recomp ... m:ss` within 20 s of the
    `recomp ...` line and later the `[i/n] Translating` line; the
    `build-logs/*-recomp.log` file grows while the step runs);
  - the bundle lands in the output folder and "Open the folder" opens
    it; "Install now" starts the setup program (do not finish the
    install unless the user wants it; cancel it);
  - a forced failure: make a second output folder read-only (`icacls
    D:\xbr\wizard\out-ro /deny Users:(W)`), pick it, build: the Done
    page shows "It stopped at: Getting ready." (or the stage the CLI
    reached), the `PermissionError` traceback excerpt, the `build-logs`
    line; `wizard.log` holds the same; Retry works after the folder is
    writable again (`icacls ... /remove:d Users`);
  - Cancel mid-build shows the cancel page. No `cmd` window flashes at
    any point (the children run with `CREATE_NO_WINDOW` as before).
  Clean up `D:\xbr\wizard-root` and the bundles afterwards (the user's
  rule: tidy the scratch drive).
- [ ] 4.5 Mac run: `./blinx2 wizard build --dev --only macos`; run the
  app with `--game <cat worktree> --root <runs/wizard-fb/root>
  --no-update-check`; check Finder shows the icon on the `.app`, the
  Dock while it runs, and that "Output folder" defaults to `dist`
  beside the `.app` (the unpacked dev app sits in `runs/wizard-fb/`);
  copy the app into `/Applications` and check the default falls back
  to `<root>/dist` with the log line; `xattr` the quarantine on and
  check the translocated run falls back too. No build to the end is
  needed here (the Windows run covers the Build page); if the screen is
  locked, record it and rely on 4.2. `SDL_AUDIODRIVER=dummy` is
  irrelevant (no game runs); never play sound.
- [ ] 4.6 Deck or Linux (when the Deck is reachable; otherwise record a
  follow-up in 7.2): unpack the Linux tar, run `./blinx2-wizard
  --dry`, then the window: the taskbar shows the icon; copy the three
  files as `docs/wizard.md` says and check the menu entry shows it.

## 5. Docs and cat

- [x] 5.1 CLI docs: `docs/commands.md` `--plain` row gains "and a
  heartbeat line every 20 s of silence (`  <step> ... m:ss | <last
  line>`)"; `docs/wizard.md`: the page list (Welcome's two folders, the
  Build page's clocks, the Done page's excerpt), "The install folder"
  becomes "The build folder and the output folder" (the default, the
  fallback rule, the setting), a new "The icon" section (the generic
  icon, `icongen`, the override, the Linux three-line install for a
  menu entry), the build table's Windows row mentions the resource;
  `docs/manifest.md` from 1.4; `wizard/README.md`'s package table gains
  `cmd/icongen` and the icon folder.
- [x] 5.2 cat (branch `spec/wizard-build-feedback`): `game.toml` drops
  `wizard.icon` and its comment; `git rm packaging/wizard-icon.png`;
  `docs/packaging.md`'s wizard paragraph: the build folder table keeps
  its name as "the wizard's build folder", a sentence says the bundle
  goes to `dist` beside the wizard unless another output folder is
  chosen, and the Deck row gains the menu-entry lines. `uv run pytest
  scripts` (`test_game_pins`, `test_export_public`) and ruff. Commit
  (`wizard: generic icon, output folder in the packaging doc`).
- [x] 5.3 Release notes for the commit body of 6.2: the heartbeat line,
  the optional icon, the stricter leak check, the `--out` the wizard
  now passes.

## 6. Review and merge (main session)

- [ ] 6.1 Opus review of the CLI branch and of cat's branch; fixes go
  back to the branch's agent. The review checks: the heartbeat's rate
  bound and that tty mode is unchanged; the `.syso` determinism
  evidence; the icon's licence file and that no vendor mark is in the
  SVGs; the leak regex against the public audit's own patterns (the
  bracketed letters); the output-folder fallback cases; that
  `TestCopy`'s word list still excludes tool names; that no game word
  reached the module.
- [ ] 6.2 After the user's approval of the screenshots and the icon:
  squash merge to CLI `main` as the noreply identity (`wizard: a live
  build page, failure details, output folder and a real icon` or
  similar, body from 5.3), bump `src/xboxrecomp_cli/__init__.py` to
  0.7.4 (`release: 0.7.4, ...`) and tag `v0.7.4` locally; cat
  `game.toml` `[cli]` moves to the v0.7.4 tag and sha, committed on cat
  with the spec's branch squash-merged (`openspec: wizard-build-feedback`
  is this spec's commit; the pin bump is `cli: pin v0.7.4, ...`).
  Public pushes stay the user's batched rounds (the CLI's round before
  cat's, as always).

## 7. Follow-through (main session)

- [ ] 7.1 Copy the agent's untracked notes to `notes/wizard-fb/`; the
  screenshots, `windows.md` and logs stay in `runs/wizard-fb/`; remove
  the worktrees (`git worktree remove --force` plus `rm -rf
  wt/wizard-fb`), keep the branches.
- [ ] 7.2 `cat/TASKS.md`: the merge entry under the wizard's; the
  follow-ups that stay (Open Questions 1 and 2 if deferred; the Deck
  check if 4.6 did not run; the `wizard-ui-polish` leftovers already
  listed); BLX-143 closed.
- [ ] 7.3 Archive the change (`openspec archive wizard-build-feedback`).
