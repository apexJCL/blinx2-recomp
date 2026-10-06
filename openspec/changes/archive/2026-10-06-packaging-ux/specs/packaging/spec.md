## ADDED Requirements

### Requirement: One command packages for this host
Running `blinx2` with no arguments SHALL package for the host's native target: `macos` on macOS, `steamos` on Linux, `windows` on Windows. `blinx2.cmd` with no arguments SHALL do the same. `blinx2 package <target>` SHALL:
- run `setup` when the toolchain or toolkit that target needs is missing;
- regenerate `src/recomp/gen/` (analyze, then recomp) only when it is missing or stale;
- then build and package.

Before running anything, it SHALL print a plan naming each step it will run and why. When a prerequisite that `setup` cannot install is missing, it SHALL stop and print the one-line fix.

#### Scenario: Fresh clone to bundle
- **WHEN** a user runs `./blinx2` in a fresh clone on macOS, with only the game files in place
- **THEN** setup, generate, build and package run in order, and a DMG appears under `dist/`

#### Scenario: Nothing changed
- **WHEN** `./blinx2` runs again with no input changed
- **THEN** the plan lists only build and package, and no stage of the pipeline runs

### Requirement: Generated code is regenerated when its inputs change
The CLI SHALL record a generation key beside `src/recomp/gen/` once `recomp` succeeds. The key SHALL hold:
- the XBE's sha256;
- the toolkit commit, plus a hash of any uncommitted change under its `tools/`, including untracked or ignored files there that a stage reads (the icall database today);
- the sha256, or "absent", of every input file the pipeline stages read that the run does not itself produce;
- a hash of the argument lists the stages run;
- the extra arguments `recomp` ran with, which SHALL be empty for packaging.

Every pipeline stage command SHALL delete the key before it runs. `package` SHALL treat gen/ as stale when the key is absent or differs from the current one, or when the regeneration marker is present, and SHALL name the differing field in its plan line. The key and gen/ SHALL stay out of git.

#### Scenario: Toolkit icall database appears
- **WHEN** the toolkit's `tools/recomp/output/icall_targets.json` is created or changed after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Seed file edited
- **WHEN** `config/seed_functions.json` changes after a successful package
- **THEN** the next `./blinx2` plan includes generate

#### Scenario: Interrupted generation
- **WHEN** a run is interrupted between analyze and the end of recomp
- **THEN** the next run regenerates, because the key is absent

### Requirement: Packaging uses its own stock build
`package` SHALL build in its own directories (`build-pkg-macos/`, `build-pkg-win/`). It SHALL configure them on every run with the stock options passed explicitly: Release, `XBOXRECOMP_ENHANCE=ON`, and `CAT_GEN_OPT` unset. It SHALL NOT read, configure or build the developer's `build/` or `build-win/`. If the packaging cache still fails the stock check, the refusal SHALL name each failing option and print the exact command that fixes it.

#### Scenario: Developer cache with enhancements off
- **WHEN** `build/CMakeCache.txt` has `XBOXRECOMP_ENHANCE=OFF` and the user runs `./blinx2 package macos`
- **THEN** packaging succeeds from `build-pkg-macos/`, and `build/CMakeCache.txt` is unchanged

#### Scenario: Forced non-stock option
- **WHEN** the packaging cache ends up non-stock
- **THEN** the refusal prints the option, its stock value, and the `--reconfigure` command

### Requirement: Help shows player commands first
`blinx2 --help` SHALL list the player commands (no arguments, `package`, `doctor`, `setup`) first. It SHALL list the pipeline stages, `build` and `pins` under a separate "Developer commands" heading. Every developer command SHALL keep its current behaviour.

#### Scenario: Help
- **WHEN** a user runs `./blinx2 --help`
- **THEN** `analyze`, `recomp` and `build` appear only under "Developer commands"

### Requirement: Long steps show live progress and keep full logs
The CLI SHALL show a live progress view, built from the standard library only, for downloads, generation, build and wrapping.
- Progress SHALL come from:
  - download byte counts;
  - the output the toolkit tools print today;
  - Ninja's `[n/m]` status;
  - makensis file lines;
  - hdiutil percentages.
- The bar SHALL move only on real updates. Between coarse updates the view MAY show a time estimate as text, marked as an estimate, from this machine's previous run of the same step.
- Every child process's full output SHALL go to a log file under `build-logs/`. On failure the CLI SHALL print the step, its exit code, the log's last lines and the log path.
- The view SHALL fall back to plain line output, with no carriage returns or escape sequences, when stdout is not a TTY, with `--plain`, when `CI` is set, or when `TERM=dumb`.
- On Windows, the ANSI view SHALL be used only after enabling virtual-terminal mode succeeds. Otherwise the view SHALL fall back to single-line updates.
- The view SHALL use ASCII glyphs unless stdout's encoding is UTF-8, and SHALL keep drawing (elapsed time, spinner) while a child prints nothing.

#### Scenario: Unrecognised output
- **WHEN** a step's child prints lines no parser matches
- **THEN** the view shows a spinner and elapsed time, the lines reach the log, and the step's exit code alone decides success

#### Scenario: Build failure
- **WHEN** the build step fails
- **THEN** the CLI prints the last lines of the build log and its path under `build-logs/`, and exits non-zero

#### Scenario: Piped output
- **WHEN** `./blinx2 | tee out.txt` runs
- **THEN** `out.txt` contains no carriage returns or ANSI escape sequences

### Requirement: Bundles carry the game's icon, never committed
`package` SHALL extract the title image from the user's XBE (`$$XTIMAGE`, else `$$XSIMAGE`), decode its XPR0 DXT1, DXT3 or DXT5 texture with the standard library, and write PNG, `.icns` and `.ico` files from it. The icon SHALL be used as:
- the macOS app icon;
- the icon resource of the Windows launcher and of the game exe;
- the NSIS installer and uninstaller icon;
- a PNG beside the steamos launcher, used for the Steam shortcut.

The icon is game data. It SHALL be written only to packaging build directories and private bundles, never to tracked paths, and `.gitignore` SHALL cover `*.ico` and `*.icns`. If extraction or decoding fails, packaging SHALL use a generic icon generated without game data, print the reason, and continue. Tests SHALL use synthetic textures only. Builds without the opt-in icon option SHALL be unchanged. The icon set SHALL be rebuilt only when the XBE or the icon tool changes.

#### Scenario: Title image present
- **WHEN** the XBE has a 128×128 DXT1 `$$XTIMAGE`
- **THEN** the DMG's app shows that image as its icon, and `BLiNX2.exe` and `cat_recomp.exe` contain `RT_GROUP_ICON` resources

#### Scenario: No usable image
- **WHEN** the image section is missing or in an unsupported format
- **THEN** packaging prints `icon: generic (<reason>)` and the bundle uses the generic icon

#### Scenario: Nothing committed
- **WHEN** a package run finishes
- **THEN** `git status` shows no icon file

### Requirement: The macOS alert passes its message as data
The macOS launcher's failure alert SHALL pass its message to `osascript` as a run argument, never as script text, so a message with quotes or backslashes displays verbatim.

#### Scenario: Quoted path
- **WHEN** the launcher fails with a message containing `"` and `\`
- **THEN** `osascript` receives the message unchanged as an argument

### Requirement: An incomplete dump is reported, not refused
`blinx2 doctor` and `blinx2 package` SHALL scan the XBE for names of media files under `adx/`, `voice/` and `movie/` and SHALL list every one absent from `game_files/`, saying that the dump is likely incomplete and should be extracted from the disc again. The check SHALL only warn; it SHALL never block packaging.

#### Scenario: Songs missing from the dump
- **WHEN** the XBE names `song_TITLE` and `game_files/adx/` has other `song_*` files but not `song_TITLE.adx`
- **THEN** doctor and package print a warning naming `adx/` and `song_TITLE`, and package still produces a bundle

### Requirement: Players see only the game's name
Everywhere a bundle shows the product's name (the installer's title, the Add/Remove Programs entry, the shortcuts, the macOS app name, launcher alerts, the steamos desktop entry and Steam shortcut, README.txt, and the CLI's messages) it SHALL be the game's name, `BLiNX 2`, with no project suffix. The name SHALL be defined once and rendered into every template.

#### Scenario: Windows uninstall entry
- **WHEN** the windows bundle is installed
- **THEN** Add/Remove Programs lists `BLiNX 2`

