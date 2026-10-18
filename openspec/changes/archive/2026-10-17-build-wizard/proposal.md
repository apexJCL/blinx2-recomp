## Why

The user asked (2026-10-14) for "packing scripts" for players,
shipped as release artifacts on the public `apexJCL/blinx2-recomp`: a
minimal cross-platform wizard that takes the player's own BLiNX 2 dump (an
ISO, an XISO or a folder with `default.xbe`), asks for the target (Windows,
macOS, Steam Deck / Linux PC) and a few options with the defaults
preselected, and ends with the installable for that target. The tracker item
spike (`runs/wizard-spike/REPORT.md`, three rounds) measured Go (a
terminal wizard, Gio, Fyne), Rust (egui) and Python (tkinter and PySide6
through PyInstaller) prototypes on the Mac, the Windows PC and the Deck,
and the user decided (round 3): **Fyne**, on the condition that "a single
machine can build all three platforms (macbook can build all
distributables and push them to the repo)"; the Windows asset is a zip
with one exe; a script builds everything on the Mac, and GitHub Actions'
free tier runs the same script if it fits. Earlier answers hold: a GUI
as the front door; releases unsigned ("personal and non-distributable");
default install folders the player can change; Homebrew installed
through Apple's Terminal or the commands shown; at start the wizard only
tells the player when a newer wizard exists and opens the release page.

Today the route is `./blinx2 /path/to/BLiNX2.iso` in a checkout of the
repo, which already imports, verifies, sets up, lifts, builds and
packages. What it asks of the player first is the part that loses people:
install uv and git (and on Windows a Python), clone the repo at a release,
open a terminal in it, know the three target names and the `--hud-pack`
flag, and edit `config/config.toml` by hand for the options. The CLI's
`doctor` and `setup` cover everything after that point and nothing before
it (`xboxrecomp-cli/src/xboxrecomp_cli/{doctor,setup,env}.py`: uv is
"never downloaded", the hints are `brew`, `winget` and `curl | sh`).

The spike's evidence for the pick: Fyne 2.8.2 opens a window unpatched on
macOS 27.0 and on the Deck's Desktop Mode; the Windows exe (25.2 MB)
cross-builds on the Mac with the game's own llvm-mingw as the cgo
compiler; the Linux binary (24.9 MB) builds on the Mac in a Docker image
pinned by digest (Debian multiarch, an arm64 container cross-compiling
to amd64, no emulation, 72 s) and ran on the Deck; the macOS universal
`.app` (46 MB on disk, 23 MB zipped) comes from `fyne package`; every
binary reproduces byte for byte, and the Deck-box build of round 2 was
reproduced on the Mac in an emulated Fedora image with the same sha256,
so the output depends on the toolchain image alone. One script
(`runs/wizard-spike/build-all.sh`) produced the three assets and
`SHA256SUMS` on the Mac in 9 s warm. Set aside: Gio (10 MB, but macOS 27
refuses `CVDisplayLink`; a local patch exists and is offered upstream),
the Go terminal wizard (not a window), Rust egui (a second toolchain and
a Linux sysroot), Python tkinter + PyInstaller (recorded as the fallback:
12 to 16 MB, per-OS builds, not reproducible, 1.2 s start).

Round 4 (2026-10-15), the user's layout: "I'd like the wizard to be as
game-agnostic as possible ... the wizard could be offered as a 'generic'
tool within xboxrecomp-cli and each repo does its own implementation
(where the repo defines a config file, builds the binaries and publishes
them). The binaries each repo publishes would be adapted for that
specific release." So: the generic wizard is the CLI's; each game repo
has a `[wizard]` table in its `game.toml` (what to show, what to fetch,
where to publish), builds its binaries with `xbr wizard build` (the
config embedded, so the binary is that release's) and attaches them to
its own release through its own workflow.

Spec by the reviewer; the
implementation and its review are the next agent's. The CLAUDE.md
Go exception was approved and applied by the user (2026-10-15, "Code
style").

## What Changes

- **The generic wizard: a Go module in the CLI repo,
  `xboxrecomp-cli/wizard/`,** on Fyne. It knows nothing about BLiNX 2:
  no name, URL, target or option in the source. The file and folder
  dialogs are the OS's own through `ncruces/zenity` (win32, `osascript`,
  `zenity`/`kdialog`), with Fyne's dialog as the fallback.
- **Each game repo configures it: a `[wizard]` table in `game.toml`**
  (design D2a; `game.toml` because the manifest already holds the name,
  slug, targets and data folders and `manifest.py` validates it): the
  release repo (the clone and the update check), the icon, the targets
  offered, extra archives the final build needs (by sha256, unpacked
  into the clone; none for BLiNX 2 today), and the options shown, each
  mapped to a `package` flag or a `config.toml` key with its default.
  At build time the CLI resolves the manifest for the release tag and
  commit and embeds the result (`go:embed` of a generated JSON), so each
  release's binary is adapted to that release. Without an embedded
  config the binary is in developer mode and reads `--game DIR`. The
  player is asked only for the dump; there is no repo question.
- **Screens:** welcome (version, the three pins, the install folder with
  Change, the Gatekeeper/SmartScreen note, the new-release notice when
  there is one); checks (`doctor --json` rows, what the wizard fixes
  itself and what it offers to install); the dump; the target (only those
  this host can package, the host's own preselected, the others greyed
  with the reason); options (render scale, fullscreen, HUD texture pack,
  keyboard and mouse, frame pacing) with the stock defaults; the summary;
  the build, with the CLI's `--plain` lines in a log pane and a bar; the
  result (the bundle, Install now for the host's own target, the data
  folder) or the failure (the step, the log file, Open the log folder,
  Retry).
- **Bootstrap, nothing system-wide:** an install root (defaults per OS,
  changeable), uv from the Astral release archive at a pinned version and
  sha256 into `<root>/tools/`, MinGit the same on Windows, the Command
  Line Tools through `xcode-select --install` on macOS, the game repo
  cloned at the baked tag with the commit checked, then `uv run --project
  <cli> --locked xbr --game <root> --prog <slug> package <target> --dump
  PATH ...` exactly as `blinx2.py` runs it, so no system Python is needed.
  What the wizard cannot install silently it offers: Homebrew through
  Apple's Terminal on the pinned official installer (the password is
  sudo's, in the terminal, never the wizard's), `brew install` of the
  formulae without a password, `xcode-select --install` (Apple's dialog);
  on Linux the distribution's `nsis` in a terminal where `sudo` prompts.
  Or it shows the commands.
- **The CLI gains two small things the wizard needs:** `xbr doctor
  --json` (the report as data) and `xbr package --seed-config FILE` (the
  player's chosen options staged as `config.seed.toml`, copied by each
  installer to the data folder's `config/config.toml` only when that file
  does not exist).
- **Release check, notice only:** at start the wizard asks GitHub for the
  latest release (one API call, 3 s timeout, in a goroutine); when it is
  newer than the baked tag it shows "A newer wizard is available" with
  the release notes and a button that opens the release page in the
  browser. Offline, timeout or rate limit: no notice, never an error. No
  self-replace, no download, no dependency pull: a self-swapped binary is
  a fresh download to Gatekeeper and SmartScreen, which would push
  towards signing, not worth it unless free (the user, 2026-10-14).
- **The build entry point is the CLI, run from the game repo:** `xbr
  wizard build` (`./blinx2 wizard build` through the bootstrap) reads
  the game's `[wizard]` config, embeds it and makes
  `blinx2-wizard-<tag>-windows-x64.zip` (one exe, cgo through llvm-mingw),
  `blinx2-wizard-<tag>-macos.zip` (the universal `.app` from `fyne
  package`, ditto-zipped), `blinx2-wizard-<tag>-linux-x64.tar.gz` (the
  binary from a `docker build --output` against a builder image pinned
  by digest; the exec bit kept) and `SHA256SUMS`, from pinned inputs (the
  Go tarball by sha256, llvm-mingw by the CLI's setup pins, the fyne tool
  by version, the image by digest). Two runs give equal hashes. The
  Linux fallback if Docker on the Mac turns fragile: the same Dockerfile
  on WSL on the Windows PC (the user's offer; the distro's vhdx on D:) or
  on the Linux/Proton host; the pinned image makes the hash the same.
- **Each game repo owns its publishing:** the free tier fits
  (public repos use standard hosted runners free, `macos-15` included;
  no secrets beyond `GITHUB_TOKEN`, no game data). A workflow template
  in the CLI's `templates/new-game/` (scaffolded by `xbr new`; cat gets
  its copy) runs on `v*` tags in the game repo: two build jobs call the
  game's bootstrap, `./<slug> wizard build` (macOS + Windows on
  `macos-15`; Linux on `ubuntu-24.04`, which has Docker; macOS runners
  do not), which resolves the CLI at the pinned `[cli]` sha as a
  player's machine does, and a release job attaches the four files to
  that repo's release. The implementer adds and dry-runs it
  (`workflow_dispatch`, no release); public pushes and releases stay the
  user's batched rounds.
- **Release assets, unsigned:** the README, `docs/packaging.md` and the
  welcome screen carry the Gatekeeper and SmartScreen steps.
- **Docs:** `docs/packaging.md` gets "The wizard" first in the player
  route; the public README's "Install and run" points at the wizard first
  and the command second; `docs/env.md` is unchanged. The CLI's `docs/`
  gets `wizard.md` (the build, the pins, the gates).
- **Rules:** the CLAUDE.md Go exception (design D14) is applied: Go with
  Fyne for the wizard only, a pinned toolchain, gofmt, vet, tests,
  staticcheck and the reproducibility check as gates, `<slug>-wizard-*`
  built and published by each game repo. This change does not edit
  CLAUDE.md.

## Impact

- **Render backends, hosts, goldens:** no render backend, runtime, audio
  or kernel code changes; no golden is affected. Hosts: the wizard runs on
  Windows, macOS and Linux (the Deck's Desktop Mode); the bundles it makes
  are the ones `package` makes today.
- **Toolkit:** not touched. Nothing here is for upstream (the Gio patch
  from the spike is offered to gioui.org separately and is not part of
  this change).
- **CLI (`xboxrecomp-cli`):** the generic Go module beside the Python
  package with `pins.json` and `check.sh`; in Python the `[wizard]`
  manifest schema, `xbr wizard build|config|check`, `doctor --json`,
  `package --seed-config` and the workflow template in `templates/
  new-game/`, with tests. The CLI's gates grow by the Go ones when
  `wizard/` changed.
- **cat:** `game.toml` gains the `[wizard]` table (BLiNX 2's repo, icon,
  targets, options); `packaging/wizard-icon.png`; the release workflow
  builds and attaches the wizard; `docs/packaging.md` and the
  README change; the `[cli]` pin moves to the CLI release that carries
  the wizard.
- **Public repos and legal:** the wizard carries no game data and the
  bundle rules stay (private, never uploaded). The player's dump stays on
  their machine; the wizard reads it only through `xbr import`.
- **Not in scope:** self-update; code signing; a no-git tarball route
  (the CLI's toolkit clone needs git); vendoring the macos target's
  Homebrew libraries; a Deck build-host mode that avoids the gen build's
  memory (the Deck still warns and builds); the Python fallback (recorded
  in design D1 if Fyne fails in practice); accessibility beyond what Fyne
  gives (none; a follow-up).
