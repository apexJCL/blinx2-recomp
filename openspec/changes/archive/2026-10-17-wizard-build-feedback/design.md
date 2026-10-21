## Context

Read at CLI main beb838f (v0.7.3) in the implementer's worktree (branch
`feat/wizard-build-feedback`, same tip); Fyne as pinned in
`wizard/go.mod`, `fyne.io/fyne/v2` v2.8.2.

**What the Build page does today** (`wizard/internal/screens/wizard.go`
`buildPage`, `startBuild`, `runSteps`): `top` is the intro sentence, the
step label and `Border(right: cancel, center: widget.ProgressBar)`; the
log pane fills the rest. `runSteps` writes the seed, then runs each
command of `model.Steps` through `runner.Start` (stdout and stderr merged
into one line stream), feeding every line to `w.buildLog.Append` and to
`runner.Progress.Feed`; when `Feed` reports a change the bar is set to
`Fraction()` and the label to `progressText()` ("Part n of m: stage
(label)"). Nothing on the page changes between two parsed lines. The
error returned is `fmt.Errorf("%s: %w", runner.Display(...), err)`, so
`wizard.log` reads `build: ./blinx2 package windows ... --plain: exit
status 1`. `fillDone` on a failure shows "The build did not finish.",
"It stopped at: %s." only when `Progress.Failed` was parsed from a
`  FAILED <label>  <time>` line, "The full log: %s." only when a
`full log:` line was, then "Open the log folder" (`<game>/build-logs`)
and "Retry". A cancel is the same page with `errors.New("canceled")`.

**What `package --plain` prints** (`src/xboxrecomp_cli/package/progress.py`,
`View`): `set_stage` prints `== [n/m] stage ==`; `begin` prints
`  <label> ...`; `progress` prints `  <label>: NN% (done/total)` when the
percentage moved 10 or more; `end` prints `  ✓ <label>  m:ss` or
`  FAILED <label>  m:ss`; `say` prints a permanent line. `paint()`
returns at once in plain mode. `line(text)` records the child's latest
line in `self.last` in every mode but prints it only in tty mode. The
view has a `clock` (injectable), `t0` (the step's start), `eta()` from
`build-logs/timings.json` (the step's last duration on this machine) and
`fmt_time`. `run_step` reads the child through a thread into a queue;
the main loop calls `view.paint()` on every 0.1 s timeout and
`view.line(text)` per fragment; the reader writes each chunk to the step
log with `log.write(chunk)` and no flush, so the file holds only the `$`
line until the child ends. A Python child is unbuffered
(`PYTHONUNBUFFERED=1`). recomp's own output: `Translating N
functions...` on stderr after it has loaded (minutes), then
`  [i/n] Translating name...` every 100 or 500 functions (the toolkit's
two verbose paths); the view parses both (`RecompParser`).

**Where the bundle lands:** `main.py` gives `package` `--out` with the
default `g().dist` (`<game>/dist`); `package()` does
`a.out = os.path.abspath(a.out)` and `os.makedirs(a.out)`. Each writer
takes `out`: `windows.wrap_windows` makes `<out>/<App>-<version>-windows/`
(an `rmtree` first, so a same-version re-run replaces it) holding
`<App>-<version>-setup.exe` and `game_files/` beside it (the ~3 GB dump
is not inside the installer; the installer copies it again at install
time, with `AddSize` counting it since 0.7.3); `steamos.wrap_steamos`
writes `<out>/<App>-<version>-steamos.tar` (tarfile `w`, overwrites);
`macos.wrap_macos` writes the `.dmg` through `hdiutil`. The `bundle:`
line names the result: on Windows that is the folder, and the wizard's
`installNow` runs `exec.Command(bundle)`, a folder, which cannot work
(found reading; fixed here, D5). The wizard's own `WIZARD_OWN_FLAGS`
already reserves `--out`, so no `[[wizard.option]]` flag can collide.
`model.PackageArgs` builds `package <target> --dump DUMP [flags]
[--seed-config S] --plain`.

**Folders and settings:** `hostinfo.DefaultRoot(slug)` is the per-OS
application-data folder; `Settings{Root, NoUpdateCheck}` in
`<user config>/<slug>-wizard/settings.json`; `hostinfo.Free(path)` walks
up to the nearest existing parent; `NeedBytes` is 15 GiB; the Your game
page (`checkDump`) checks the build folder's free space against
`NeedBytes` plus the image size. The Welcome row reads "Install folder",
"The tools, the source code and the build go here. About 15 GB." The
Summary has "Install folder: %s"; `main.go --root` says "the install
folder"; `--dry` prints `install folder: ...`.

**The icon today:** `[wizard] icon` is required and must be a PNG in the
tag's tree (`manifest.py`, `wizard.py` `_file_rules`); cat's is a 2 KB
placeholder (`packaging/wizard-icon.png`). `wizard_build.build_macos`
passes it to `fyne package -icon`, which makes the `.icns`.
`build_windows` is a plain `go build` with llvm-mingw's clang: no
resource, so Explorer shows the generic exe icon. `linux/Dockerfile`
tars the binary alone. The app never calls `SetIcon`. `wizard/embed.go`
embeds `pins.json`; `internal/gamecfg/config.json` is `{}` in the repo
and written in the staged copy by `wizard build`.

**Fyne 2.8.2, checked in the pinned source:** `widget.ProgressBar` has a
`TextFormatter` and draws the percentage inside; `ProgressBarInfinite`
is a separate widget of the same height whose segment sweeps while
`Running()`, with no determinate value; `widget.Activity` is the
inline-icon-sized spinner (`Start/Stop`), not drawn on the headless
canvas; `fyne.NewAnimation(d, fn)` with `RepeatForever` and
`AnimationLinear` drives a per-frame callback on the driver;
`canvas.Rectangle` takes an `NRGBA` with alpha and a `CornerRadius`;
`canvas.NewImageFromResource` renders an SVG or PNG resource at any size
through `software.Render` (the screenshot harness's path), which fills
the canvas with the theme's background colour; `fyne.App.SetIcon`
(since 1.4) sets the window icon the desktop shows while the app runs.
The wizard's `thinBar` (`thinbar.go`) is a 6-unit custom bar drawn from
rectangles; `quietText` (`quiet.go`) is the placeholder-coloured text;
`palette` (`palette.go`) darkens the success, warning and error colours
on a light background to at least 4.5:1.

## Goals / Non-Goals

Goals: while the build runs the page shows, every second, that the
process is alive and for how long; the collapsed log line never sits on
`recomp ...` for more than 20 s; when the build stops the player sees
where and why without opening a file, and `wizard.log` holds the same;
the private notice is read; the player chooses where the bundle goes and
the default is beside the wizard; the build folder and the output folder
cannot be confused; the wizard has a real icon on all three platforms;
`private_leaks` catches a Windows path; the module stays generic and
small, every change has a test, and the double-build gate still holds.

Non-goals: see the proposal's list (SCALE_MAX, a multi-core recompiler,
split generated files, an accessibility tree, a Checks-page Cancel,
translations, signing). Also: a per-step ETA computed by the wizard (the
CLI's `timings.json` ETA rides on the heartbeat instead); a richer plain
mode for humans (plain mode stays a CI-friendly log); re-wording the
CLI's stage names on the Build page (a `wizard-ui-polish` follow-up).

## Decisions

**D1. The plain-mode heartbeat (CLI).** `View` gains `HEARTBEAT_S = 20`
and `last_say` (the clock at the last permanent line, set in `say`).
`paint()`, which `run_step` calls on every 0.1 s queue timeout and on
every fragment, starts with the plain-mode branch:

```
if self.mode == "plain":
    if self.label and now - max(self.last_say, self.t0) >= HEARTBEAT_S:
        self.say(self.heartbeat())
    return
```

`heartbeat()` is

```
  <label> ... <elapsed>[, <eta>][ | <last>]
```

`elapsed` is `fmt_time(now - t0)` (`m:ss`, or `h:mm:ss` from an hour);
`eta` is `self.eta()` when it is not empty ("~7 min left", "under a
minute left"); `last` is `self.last` cut to 120 characters, absent while
the tool has printed nothing (recomp loading: `  recomp ... 2:30`).
`say` records `last_say` before it repaints, so the heartbeat cannot
recurse, and a `progress` or `say` line resets the wait, so the line
appears only after 20 s of silence on stdout: at most three a minute, and
none at all while Ninja or the importer print their own lines. tty and
line modes are untouched (they repaint in place with the same elapsed
time and ETA already). The format mirrors `begin`'s `  <label> ...`
on purpose: in a CI log the three lines `recomp ...`, `recomp ... 2:30`,
`recomp ... 4:12 | [1201/26190] Translating ...` read as one story.

Why not shorter, or adaptive: 20 s sits in the user's 15-30 s window; a
24-minute recomp gives 72 lines, which a CI log absorbs; a shorter
period would double that for no information. Why not `--verbose`'s
every line: that is what the step log is for, and it floods the wizard's
5000-line pane.

The flush: `reader()` calls `log.flush()` after each `log.write(chunk)`.
A chunk is up to 64 KiB, so the cost is one write per read, which is
what `tee` does.

**D2. `runner.Progress` parses the heartbeat (Go).**

```go
heartRE = regexp.MustCompile(`^  (.+?) \.\.\. (\d+:\d\d(?::\d\d)?)(?:, ([^|]*?))?(?: \| (.*))?$`)
```

A match sets `Label` when it is empty (the wizard missed the begin
line), `StepElapsed` (the string, for tests and the failure excerpt) and
`Tool` (the tool's latest line), and returns true so the label refreshes;
`Fraction()` is unchanged (a heartbeat never moves the bar). `beginRE`
is anchored at `\.\.\.$`, so the two cannot both match. The tool line
may hold ` | ` itself: the ETA group excludes `|`, so the first ` | `
after the elapsed time splits, and the rest is the tool line whole. A
new fixture `internal/runner/testdata/package-heartbeat.txt` (a recomp
step: begin, two bare heartbeats, three with tool lines, the 10% lines,
the end) drives `TestProgressHeartbeat`: `Tool` is the last tool line,
`Pct` follows only the percentage lines, the bar never moves on a
heartbeat.

**D3. The Build page: a bar that moves, and two clocks.**

The bar: `widget.ProgressBar` goes; the page uses the wizard's own
`thinBar` at `thinBarHeight` 10 (a `Height` field, default 6, so the
header's step bar and the checks bar keep theirs) with a new
`Pulse bool` and `StartPulse()/StopPulse()`. Pulsing, the renderer adds
one `canvas.Rectangle` ("sheen"): the primary colour at alpha 0x66, a
band one fifth of the bar wide, moved by a `fyne.NewAnimation(1600 ms,
fn)` with `AnimationLinear` and `RepeatForever` from the left edge to
the right edge of the *filled* part (the whole track while `Value` is 0,
so "Planning" moves too). The animation is started on `StartPulse` and
stopped on `StopPulse` and in the renderer's `Destroy`. `fn(t)` only
moves the sheen; nothing else is laid out per frame. Value 1 (the
bundle line) stops the pulse. `TestBuildBarPulse` calls the animation's
function directly with 0.25 and 0.75 and checks the sheen moved and
stayed inside the fill; no timer in the test. The headless screenshot
shows one frame of it.

Why a sheen on the determinate bar and not Fyne's `ProgressBarInfinite`
or an `Activity` beside the bar: the infinite bar has no value, so it
would replace the fraction the player watches, and two bars (one
moving, one not) read as two different things; the spinner is the
checks table's "checking" cue and small. The bar itself is what sat
still, so the bar itself moves. `thinBar` already belongs to this module
and draws rectangles only; the sheen is one more rectangle and one
animation, about 40 lines, theme-aware through the primary colour.

The clocks: `w.buildClock`, a `quietText` at the right of the step label
row, reads `buildClockText`:

```
42% · 4:12 in this part · 12:40 in all
```

(`%` from `Fraction()`; while the fraction is 0 the first field is
omitted.) `startBuild` records `buildStart`, sets `partStart` to the
same, and starts a `time.Ticker` goroutine (1 s) that calls `fyne.Do`
to set the text; the goroutine stops on a `done` channel closed when
`runSteps` returns. `partStart` resets when `Progress.Index` changes
(a new "Part n of m") and at the start of each command of `Steps` (the
`import` and `enhance hud` prerequisites have no plan line). The part
is the plan stage because that is what the label calls "Part"; the
step's own time inside a stage comes with the heartbeat line (D1) in
the collapsed log. `fmtClock` mirrors `fmt_time`: `m:ss`, `h:mm:ss`
from an hour. `TestBuildClock` sets the two starts by hand and checks the
text at 0, 65 s and 3700 s, and that a stage line resets the part.

The collapsed log line is the heartbeat line as the CLI printed it (the
pane shows its newest line; nothing to add). `buildIntro` gains nothing;
`buildStep` stays "Part %d of %d: %s".

**D4. The failure screen and `wizard.log`.**

`logPane` gains `Tail(n int) []string` (the last n kept lines). `runSteps`
returns a `*buildFailure{Step, Cmd string; Err error; Tail []string}`
for a non-zero exit or a start error, with `Tail` the pane's last 40
lines; a cancel stays `errCanceled` (a sentinel). `Step` is, in order:
`prog.Failed` (the CLI's `FAILED` line), else `prog.Label` inside
`prog.Stage` ("generate: recomp"), else `prog.Stage`, else
`buildPrepare` ("Getting ready", a crash before the plan).

`failureExcerpt(tail []string) []string`, pure and tested: from the last
line equal to `Traceback (most recent call last):` when one is within
the tail (so the traceback is shown whole), else the last 12 non-blank
lines; each line cut to 200 characters; at most 40 lines. The CLI's own
error line (`<slug>: the manifest would carry private data: ...`, a
`CliError` on stderr) is in the tail like any other line.

`fillDone` on a `*buildFailure`:

- title "The build stopped"; bold "The build did not finish.";
- "It stopped at: {Step}." (always now);
- bold `doneSaid` "What the build said:" and the excerpt in `mono()`
  (selectable, copyable, word-wrapped: the copy-friendly read-only box);
  under it the quiet line `doneExit` "(exit status N)" from `Err`;
- `doneLogs` "The full logs are in {dir}." where `dir` is
  `filepath.Dir(prog.Log)` when the CLI printed one, else
  `<game>/build-logs`; the buttons "Open the log folder" and "Retry",
  and `doneRetry` as today;
- the notice box (D5).

On `errCanceled`: title "The build stopped", bold `doneCanceled` "You
stopped the build.", then Retry and `doneRetry`; no excerpt, no log line
(there is nothing to read).

`wizard.log`: `runSteps`'s caller writes one entry,
`build stopped at <Step>: <Display(cmd)>: <err>` followed by the excerpt
lines indented two spaces (one `Logf` call with the lines joined by
`"\n  "`; `Logf` stamps the first line only). A cancel logs `build
canceled by the player`. A success logs `build done: <bundle>`.

`installNow` on Windows: the bundle is the folder; run
`fetch.Find(bundle, "*-setup.exe")`-style lookup (`filepath.Glob` on
`<bundle>/*-setup.exe`, one match) and `exec.Command(setup).Start()`;
no match is an error box. `TestInstallNowWindowsSetup` covers the lookup
on a temp folder.

**D5. The notice box.** `notice.go`: `noticeBox(lead, body, tail
string) fyne.CanvasObject`, a small `widget.BaseWidget` whose renderer
holds a `canvas.Rectangle` (the warning colour at alpha 0x2a, corner
radius `theme.InputRadiusSize()`) under a padded
`Border(left: Icon(NewWarningThemedResource(WarningIcon)), center:
RichText)`; the RichText is `lead` in `RichTextStyleStrong` with
`ColorName: theme.ColorNameWarning`, `body` inline, and `tail` strong
again; word-wrapped. `Refresh` re-reads the colours from the theme, so
light and dark both work and the palette's darker amber applies on
white. The page wraps it in
`layout.NewCustomPaddedLayout(2*pad, 2*pad, 0, 0)` for the space above
and below. The text:

- lead: "For your own computers only."
- body: "The bundle holds your own copy of {Game} and code made from
  it."
- tail: "Never share, upload or publish it."

`bundleRule` becomes the three constants; `TestCopy`'s word list still
holds. The box goes where the sentence is today: the Done page, success
and failure, the page the user called the Summary (the sentence appears
nowhere else; the Done page is the last page, which a player reads as the
summary of the build). Open Question 1 asks whether the Summary page
(step 6) gets it too; adding it there is one line once the widget
exists. `TestNoticeBox` renders it on the light and dark themes and
checks the lead is bold and in the warning colour and the rectangle's
colour is the theme's warning colour with the alpha.

**D6. The output folder.**

*Where it lives.* `hostinfo.Settings` gains `Out string
json:"out,omitempty"`. The Welcome page gets a second folder row under
the first: bold `outputFolder` "Output folder", the quiet sentence
`outputFolderIs` "The finished game bundle goes here. About %d GB." (4:
the dump is ~3.3 GB and the program under 0.5), the path and
"Change…" (`pickOut`, the same zenity folder dialog with Fyne's as the
fallback). An empty setting means the default, recomputed on every run
so a moved wizard is followed; a chosen folder is kept until changed.

*The default.* `hostinfo.DefaultOut(root string) (dir, why string)`:

1. `os.Executable()`, `filepath.EvalSymlinks`, its folder. On macOS,
   when a path element ends in `.app` (the exe is
   `X.app/Contents/MacOS/X`), the folder that holds the `.app`: "beside"
   means beside the app, not inside it.
2. Refused as a place for the bundle, each with a `why` for the log:
   under `os.TempDir()` (Explorer's zip preview runs the exe from a temp
   copy; macOS translocation runs a quarantined app from a path under
   `/private/var/folders/.../AppTranslocation/`, also temp); on Windows
   under `%ProgramFiles%`, `%ProgramFiles(x86)%`, `%ProgramW6432%` or
   `%SystemRoot%`; on macOS under `/Applications` or `/System`; on
   Linux under `/usr` or `/opt`.
3. A write probe: `os.CreateTemp(dir, ".wizard-*")` removed at once.
   Nothing lasting is created; `dist` itself is made by the CLI
   (`os.makedirs(a.out)`).
4. Any refusal or failure: `filepath.Join(root, "dist")`, the build
   folder's `dist` (the user's own fallback in TASKS.md), and the
   Welcome row shows that path. The log gets one line, `output folder:
   <why>; using <dir>`.

`~/Downloads` is not a special case: a wizard unzipped there is
writable, so the bundle lands in `~/Downloads/dist`, beside it, which is
what the user asked for. `TestDefaultOut` drives the pure part
(`outCandidate(goos, exe, tmp, env)`) with made-up paths: the `.app`
case, the temp case, Program Files, a plain folder.

*The command.* `model.PackageArgs(seedPath, out string)` appends
`--out out` before `--plain`; `Steps(seedPath, out)`; the Summary's
technical details and `--dry` show it. The CLI takes the path as one
argument (no shell), makes it absolute and creates it. Windows paths
with spaces or a drive letter need nothing more; `runner.Display` quotes
them for the player.

*What the pages show.* Welcome: the two rows. Summary: "Build folder:
%s" then "Output folder: %s". Done: the bundle path as today and the
button renamed `openBundleFolder` "Open the folder" (it opens the folder
holding the bundle, which on Windows is the output folder holding the
bundle folder). The bundle's final name is known only when `package`
computes the version, so the Summary names the folder, not the file.

*Free space.* `checkDump` (Your game page) keeps the build folder's
check (`NeedBytes` plus the image) and adds the bundle's:
`hostinfo.BundleNeed(dumpBytes)` is `dumpBytes + 1 GiB` (the program,
the launcher, a `.pdb`, slack), with `dumpBytes` the image's size or
`hostinfo.TreeSize(folder)` (a walk; a dump is a few hundred files).
`hostinfo.SameVolume(a, b)` (`filepath.VolumeName` on Windows,
`Stat_t.Dev` elsewhere, through the nearest existing parent as `Free`
does): on one volume the two needs add up against one free figure and
the message is the existing `prepareNoSpace` with the sum; on two, each
has its own check and the output folder's message is `dumpNoSpaceOut`
"The output folder's disk has %.1f GB free and the bundle needs about
%.1f GB. Free some space, or pick another output folder on the Welcome
page." The Windows install-time copy is the installer's business (0.7.3's
`AddSize`), not the wizard's; the Done page's Windows install sentence
gains "Installing copies the game files again, so the PC needs about as
much free space as the bundle takes."

*Re-runs.* The CLI replaces a same-version Windows bundle folder and
overwrites the tar; the `.dmg` is checked in task 2.7 and made to
overwrite too if `hdiutil` refuses. The wizard reuses the saved output
folder; when it no longer exists and cannot be made (a removed drive),
`DefaultOut`'s rule applies with a log line and the row shows the
result. The build folder is reused as before (the clone and the build
are incremental).

*The names.* "Install folder" becomes "Build folder" everywhere the
player reads it: `installFolder`, `pickFolderTitle`, `summaryFolder`,
`prepareOverlap`, `prepareNoSpace`, `dumpNoSpace` texts; `main.go`'s
`--root` help ("the build folder: the clone, the tools and the build");
`--dry` prints `build folder:` and `output folder:`; `docs/wizard.md`'s
section becomes "The build folder and the output folder"; cat's
`docs/packaging.md` paragraph says where the bundle goes. The settings
key `root` keeps its name (compatibility with saved files). The user's
suggested pair ("Build folder", "Output folder") is adopted: one names
what is built in it, the other what comes out of it.

**D7. `private_leaks` (CLI).**

```python
def private_leaks(text, home=None, host=None):
    ...
    if home and len(home) > 3 and home_pattern(home).search(text):
        leaks.append("home directory")
    ...
    if PATH_RE.search(text):
        leaks.append("absolute path")
```

`home_pattern(home)` is a compiled regex from the home path with every
separator run (`\` or `/`) matched by `(?:\\\\|\\|/)+` (the raw
backslash, the JSON-escaped double, or a slash) and `re.I`, so
a Windows home matches its JSON-escaped form, the same lower-cased with
forward slashes, and the home mid-string. The POSIX `/` guard stays (`home != "/"`). `PATH_RE` is

```python
re.compile(r"(?<![A-Za-z0-9_./\\-])(?:/[U]sers/|/[h]ome/|/var/[h]ome/|[A-Za-z]:[\\/])")
```

a path start anywhere in the text (after a quote, a space, a colon, a
bracket or the start), still with the bracketed letters so the public
audit's own search does not match the source. The look-behind keeps a
relative path out when its `home` segment follows a letter, and a
bare `C:X` out (no separator). Tests in `test_package_lib.py`: the four
new positives (the users-folder path with forward slashes in a JSON
string, a JSON-escaped Windows home mid-string after `built at`, a POSIX home after a space, the JSON-escaped home on Windows
with a Windows `home`), and the two negatives.

**D8. The icon.**

*The picture.* The generic icon is Tabler Icons' `device-gamepad-2`
(MIT; the SVG copied verbatim into `wizard/icon/device-gamepad-2.svg`
with the set's version in `wizard/icon/README.md` and the licence text in
the CLI's `LICENSES/tabler-icons-MIT.txt`, which `pyproject.toml`'s
`license-files` already ships) drawn white on an original rounded tile
(`wizard/icon/wizard-icon.svg`, 1024 by 1024: a square with corner
radius 22% filled `#1e4d6b`, a deep blue, the glyph scaled to 62% of the
tile with its stroke at 7% of its own size). Not the Xbox mark and not
its green: both are Microsoft's, and the previous round chose original
glyphs over vendor logos for the same reason. Why a set's glyph on an
original tile rather than drawing the gamepad too: an app icon is seen
large, where a drawn-by-hand gamepad would show its author; a licensed
glyph costs one licence file. Why Tabler over Material Symbols: MIT is
the shorter notice and the project already ships MIT texts.

*The sizes.* `wizard/cmd/icongen`, a Go program in the module:
`icongen -in FILE -out DIR` reads an SVG or a PNG and writes
`icon-16.png` to `icon-1024.png` (16, 24, 32, 48, 64, 128, 256, 512,
1024), `wizard.ico` (PNG-compressed entries at 16, 24, 32, 48 and 256:
one 6-byte header, one 16-byte directory entry per image, then the PNG
bytes; Explorer has read PNG entries since Vista) and `Icon.png` (the
1024 one, for `fyne package`). Rendering is Fyne's own
(`canvas.NewImageFromResource` with `ImageFillContain`, rendered at n by
n through `software.Render` under a theme whose background colour is
transparent), the same path as the screenshot tests: pure Go, no new
import, and deterministic for a given Fyne version, which the double
build checks. The game's own PNG goes through the same path, so a
512-pixel PNG is enough and an SVG is rendered crisp at every size.
`TestIcongen` renders the committed SVG at 32 and 256, checks the tile
colour at the centre and transparency at a corner, parses the `.ico`
header and entry count, and checks `icon-256.png` equals the committed
`internal/gamecfg/icon.png` (D8, the embed), so the two cannot drift.

*The embed and the window icon.* `internal/gamecfg/icon.png` is the
generic 256-pixel render, committed beside `config.json` (the one
binary file in the module, 10 KB or so, test-checked against the SVG);
`embed.go` embeds it as `wizard.IconPNG`; `main.go` calls
`a.SetIcon(fyne.NewStaticResource("icon.png", wizard.IconPNG))` before
`screens.New`, so the window and taskbar show it on Linux (and anywhere
the desktop asks the app). `wizard build` writes the game's 256-pixel
render over it in the staged copy, exactly as it writes `config.json`.

*Windows.* `wizard_build.build_windows` writes `wizard.rc` (`1 ICON
"wizard.ico"`) and runs llvm-mingw's `llvm-windres` (shipped in the
pinned llvm-mingw, so no new toolchain) with the pe-x86-64 target into
`cmd/wizard/rsrc_windows_amd64.syso` in the staged module before `go
build`; the Go linker takes any `.syso` in the package, and the
`_windows_amd64` suffix keeps it out of the other two builds (the staged
copy is shared). Explorer then shows the icon on the exe, the taskbar
and the window. `llvm-windres` writes a COFF object with a zero
timestamp, so the double build should still match; task 4.3 proves it,
and if it does not, `icongen` writes the `.syso` itself (the layout
`akavel/rsrc` uses: a `.rsrc` section with the RT_ICON entries and one
RT_GROUP_ICON, about 150 lines), which is then the one route.

*macOS.* Unchanged: `fyne package -icon Icon.png` makes the `.icns`,
now from the 1024-pixel render instead of the game's raw PNG.

*Linux.* The Docker context gains `icon/<name>.png` (256) and
`icon/<name>.desktop`:

```
[Desktop Entry]
Type=Application
Name=<Game> build wizard
Exec=<name>
Icon=<name>
Categories=Game;Utility;
```

and the tar holds the binary, the PNG and the desktop file. A desktop
file cannot point at a relative icon, so the entry works once the three
are put where XDG looks (`~/.local/bin`, `~/.local/share/icons/hicolor/256x256/apps/`,
`~/.local/share/applications/`); `docs/wizard.md` and cat's
`docs/packaging.md` give those three lines for a player who wants the
wizard in the Deck's menu. Running it from the unpacked folder shows the
window icon through `SetIcon` either way.

*The game's override.* `[wizard] icon` becomes optional; set, it is a
PNG (signature) or an SVG (starts with `<svg` or `<?xml`) in the tag's
tree; `wizard.py`'s rules check that and `docs/manifest.md` says so.
`wizard.resolve` returns `None` for the bytes when unset and `build`
takes the module's `icon/wizard-icon.svg`. cat drops its placeholder key
and file: the generic icon is the better placeholder, and a drawn BLiNX
icon is a later decision.

**D9. The release is v0.7.4, not 0.8.0.** Everything here is additive
or a fix: a new plain-mode line an older wizard ignores, a flag the
wizard already reserved, a key that becomes optional, a stricter leak
check that only refuses what should never have passed, wizard pages.
No schema change, no command or flag removed, no change to what a game
pinned at 0.7.x gets from its own commands. The project's own history
bumps the patch number for features inside a line (0.6.1 to 0.6.7, 0.7.1
to 0.7.3) and the minor for a new surface (0.6.0 `import`, 0.7.0 the
wizard). The wizard embeds the `[cli]` pin from the tag's `game.toml`,
so cat's pin bump is what carries 0.7.4 to players.

**D10. Game-agnostic and tested, as before.** The new strings live in
`copy.go` under `TestCopy`'s word list; `TestNoGameInSource` still scans
the package; the icon names no game; the screenshot harness
(`TestScreenshots` under `WIZARD_SHOTS`) gains the Build page mid-pulse
with the clocks, the Done page with a traceback excerpt, the Done page
cancelled, the Welcome page with the two rows and the notice box on the
Done page, dark for approval and light for contrast, into
`runs/wizard-fb/shots/`.

## Risks / Trade-offs

- The heartbeat is a line format two programs agree on; both ship in the
  same CLI release, and the wizard's parser tolerates the line's absence
  (an older CLI) and the CLI tolerates an older wizard (it just prints).
  A future change to the format updates `heartRE` and the fixture.
- An animation per frame on the build page: it moves one rectangle; the
  log pane's 100 ms coalescing is untouched. If the page stutters on the
  Deck, the sheen's period goes up, not off.
- PNG entries in a `.ico` at 16 pixels: Windows 10 and 11 render them;
  an old shell extension that wants BMP entries at small sizes would
  show nothing at 16. Task 4.4 looks at Explorer at the small sizes on
  the Windows PC; the fallback is BMP entries for 16-48 (a 40-line
  encoder in `icongen`).
- `llvm-windres` determinism (D8): proven by the double build or
  replaced by `icongen`'s own writer.
- The output folder's default depends on where the player put the
  wizard; a wizard run from inside a zip preview silently lands in the
  build folder's `dist`, which the Welcome row shows and the log
  explains.
- `TreeSize` on a dump folder on a slow disk: a few hundred `stat`
  calls, well under a second; it runs once, on Next.
- A stricter `private_leaks` could refuse a manifest that passed before:
  only one that carries an absolute path, which is the point. cat's
  manifests (a Mac and a Windows package run) are checked in task 1.5.
- One committed binary (`icon.png`, about 10 KB) in the CLI module, kept
  honest by `TestIcongen`.

## Migration Plan

Additive. Saved `settings.json` files load (`out` absent means the
default). A game's `[wizard] icon` keeps working. Players see the new
pages with the next wizard build of the game after cat pins v0.7.4.
Rollback is a revert of the squash commits (CLI, then cat's pin).

## Open Questions

1. The notice box is on the Done page (D5). Should the Summary page
   (step 6, before "Build") show it too? One line once the widget
   exists; decided by the user from the screenshots.
2. Tabler's `device-gamepad-2` on a deep-blue tile is the spec's pick;
   the user may prefer another glyph of the set or another tile colour
   from the rendered `icon-256.png` in the screenshots folder. Any such
   change is the SVG only.
