## Why

The build wizard (`build-wizard`, the tracker item `wizard-ui-polish`; CLI
v0.7.3) had its first run on native Windows 11 on 2026-10-15 (rc.1). It
reached the Build page and the CLI failed there, and the run showed that
the wizard tells the player too little while the build runs and when it
stops. The user's notes, in TASKS.md and this change's brief:

- **The Build page looks dead.** The CLI's progress arrives in bursts and
  the recompile (24 minutes on a Ryzen 3700X) sat on one value for
  minutes; nothing on the page moved. The bar should show the process is
  still running, with the elapsed time of the current part and of the
  whole build.
- **The log sat on `recomp ...`.** The wizard runs `package --plain`,
  whose view prints a step's start, its end and at most every 10%
  (`package/progress.py`). recomp prints nothing the view parses while it
  loads (minutes on that PC, with Defender busy too), then `[i/n]` every
  few hundred functions. A tool's own lines never reach the wizard. The
  step log in `build-logs/` could not be read mid-run either: the reader
  writes it through a buffer it never flushes.
- **The failure screen gives nothing.** It said "The build did not
  finish", and `wizard.log` kept `<cmd> --plain: exit status 1`. The real
  error, a Python traceback, was only in the CLI's merged output.
- **The private notice** ("The bundle holds your own copy of ...") should
  stand out: spacing, colour, an icon, bold where it matters.
- **The output folder.** The bundle always lands in `<build
  folder>/src/dist/`, `package`'s `--out` default, deep in the wizard's
  tree. The player should choose where it goes, with a default beside the
  wizard itself. And the Welcome page's "Install folder" is really the
  build folder (the clone, the tools, the build); the game installs where
  its installer says.
- **The wizard has no icon** on Windows (an icon-less exe) and no desktop
  icon on Linux; the macOS app carries a placeholder. The user asked for
  "a free to use Xbox icon": the Xbox mark is Microsoft's, so the wizard
  gets an icon that reads as a gamepad without the mark, and a game may
  set its own.
- **One CLI hardening** found in the v0.7.3 review: `package/lib.py`'s
  `private_leaks` misses Windows paths (`home in text` never matches the
  JSON-escaped Windows home; the path pattern misses `C:/...` and a
  path in the middle of a string).

Spec by the reviewer; the implementation and its
Review are the next agent's (slug `wizard-feedback`).

## What Changes

Two repositories, no toolkit change, no runtime change.

**CLI, Python** (`xboxrecomp-cli`):

- `package --plain` prints a **heartbeat** while a step is silent: at most
  one line every 20 s, with the step's elapsed time, the ETA when one is
  known, and the tool's latest line. tty and line modes are unchanged.
  `run_step` flushes the step log after every chunk, so `build-logs/` can
  be read while a step runs.
- `private_leaks` catches the home directory in its JSON-escaped and
  forward-slash forms, and absolute Windows and POSIX paths anywhere in a
  string, with unit tests.
- `[wizard] icon` becomes optional and may be an SVG; without it the
  wizard carries the generic icon. `xbr wizard build` renders the icon
  set with a small Go program in the module (`cmd/icongen`), embeds it in
  the Windows exe through a resource object, hands the master PNG to
  `fyne package` for the `.icns`, and puts a PNG and a `.desktop` entry
  in the Linux tar.
- Release **v0.7.4** after the merge; cat's `[cli]` pin follows.

**CLI, Go** (`xboxrecomp-cli/wizard/`, the CLAUDE.md Go exception):

- The Build page: a bar that keeps moving while the process runs (a
  sheen sweeping the filled part of the wizard's own thin bar), the
  percentage and two clocks ("4:12 in this part, 12:40 in all") that
  tick every second, and the heartbeat line as the collapsed log line.
- The Done page after a failure: the part that stopped, the CLI's last
  lines (the traceback when there is one) in a selectable box, where the
  full logs are, and the same written to `wizard.log`. A cancelled build
  says the player stopped it.
- The notice box: a tinted, bordered block with a warning icon, the key
  words in bold, in the theme's warning colour (readable on light and
  dark), with space around it.
- Two folder rows on Welcome, "Build folder" and "Output folder", both
  remembered in `settings.json`; the output folder defaults to `dist`
  beside the wizard (beside the `.app` on a Mac) and falls back to the
  build folder's `dist` when that place cannot be written. The Summary
  shows both folders; the build passes `--out`; the Done page opens the
  folder. Free space is checked for the bundle as well as the build.
- The wizard sets its window icon from the embedded icon, so the taskbar
  shows it on Linux too.

**cat**: this spec; `game.toml` drops the placeholder `wizard.icon` (the
generic icon applies) and moves the `[cli]` pin to v0.7.4 at merge time;
`docs/packaging.md`'s wizard paragraph names the two folders.

## Impact

- **Render backends, hosts, goldens:** none. No runtime, renderer, audio
  or kernel code; no golden; no Proton run. The bundles the wizard makes
  are unchanged apart from where they land.
- **Toolkit:** not touched; nothing for upstream.
- **CLI (`xboxrecomp-cli`):** `package/progress.py` and `package/lib.py`
  (behaviour: a new plain-mode line, a stricter manifest leak check),
  `manifest.py` and `wizard.py` (an optional key), `wizard_build.py` and
  `wizard/linux/Dockerfile` (the icon), `wizard/` (the pages, the model,
  hostinfo, the runner's parser, a new `cmd/icongen`), docs, the version.
  A game pinned at an older CLI keeps working with an older wizard; a
  newer wizard on an older CLI just sees no heartbeat.
- **cat:** `game.toml`, `packaging/wizard-icon.png` (removed),
  `docs/packaging.md`, `TASKS.md`.
- **Public repos and legal:** the generic icon is a gamepad glyph from
  Tabler Icons (MIT) on an original tile, never the Xbox mark or its
  green; the licence text goes in the CLI's `LICENSES/`. No game data
  anywhere; the screenshots for approval are made headless from the
  sample config into `runs/wizard-fb/`, never a worktree, never
  published. The spec has no host names, private paths or links.
- **Not in scope (non-goals):** raising the toolkit's `SCALE_MAX`; a
  multi-core recompiler (the 24 minutes stay 24 minutes; this change
  makes them legible); splitting big generated files; an accessibility
  tree (Fyne has none); a Cancel on the Checks page; translations;
  signing the binaries; the other `wizard-ui-polish` follow-ups in
  TASKS.md.
