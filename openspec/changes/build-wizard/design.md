## Context

cat `main` 028efc9 (pins CLI v0.6.7 a7cdc15, toolkit blinx2-v0.3.1
ac27175). Facts below are from reading those trees on 2026-10-14 and from
the BLX-131 spike (`runs/wizard-spike/REPORT.md`, rounds 1 to 3;
prototypes under `runs/wizard-spike/proto/`, the one-Mac build in
`runs/wizard-spike/build-all.sh` and `docker/`).

What the player's route is today. `cat/blinx2` runs `blinx2.py` (the CLI's
`wrapper/game.py` vendored, stdlib, Python 3.9+): `find_uv()` wants uv
>= 0.5.31 on PATH or prints the per-OS hint (`UV_HINT`); `resolve()`
clones `xboxrecomp-cli` at `[cli] tag` locked to `[cli] commit` into
`external/xboxrecomp-cli` (or `$XBOXRECOMP_CLI_DIR`, or
`../xboxrecomp-cli`); then it `execve`s `uv run --project <cli> --locked
xbr --game <root> --prog blinx2 ARGS`. `xbr` with a path as its first
argument means `package <native target> --dump PATH` (`main.py`); `package`
prints its plan, runs `setup` when needed (`setup.run_setup`: `.venv` from
`uv.lock` with cmake and ninja, llvm-mingw from `config/setup-pins.json`
with sha256, NSIS on Windows, the toolkit clone at `[toolkit] tag`),
`analyze` + `recomp`, the build in `build-pkg-<target>/`, the bundle in
`dist/`. Its progress view (`package/progress.py`, `host.VIEW`) draws the
steps, a bar, elapsed and an estimate on a terminal and writes every
tool's output to `build-logs/<time>-<step>.log`; `--plain` prints a line
per step (also when stdout is not a terminal or `CI` is set). `doctor`
(`doctor.doctor_report`) returns `(lines, targets, blocked)`; `setup.
host_blockers(target, importing)` lists what setup cannot install, each
with its fix (`xcode-select --install`, `brew install sdl2 sdl3 openssl
libepoxy`, `makensis: ...`). `doctor.makensis_hints()` has the
per-distribution and immutable-host (distrobox) commands.

Options a player may want. `packaging/config.default.toml` is every key at
its stock default, shipped beside the game and replaced on update;
`config/config.toml` in the data folder (`%LOCALAPPDATA%\BLiNX2`,
`~/Games/BLiNX2`, `~/Library/Application Support/BLiNX2`) holds only what
the player changed, is created by the game on first launch and never
overwritten. The keys the wizard offers: `render.scale` (1, 2, 3),
`present.fullscreen`, `present.pacing` (`sleep` default, `spin`),
`input.keyboard` and `input.mouse`, and `--hud-pack` (a `package` option:
`enhance hud` first, which needs PT Sans Narrow Bold installed on Linux
and Windows, else the atlas is upscaled). The installers: the NSIS setup
installs under `%LOCALAPPDATA%\Programs\BLiNX2`; `install.sh` (steamos)
creates `config/` "when it is absent" and never changes what is in it; the
macOS app's launcher reads `../Resources/config.default.toml` then the
data folder's `config/config.toml`.

Host facts from the spike. Steam Deck (SteamOS, glibc 2.41, Wayland
session in Desktop Mode): `zenity`, `kdialog`, `konsole`, `xdg-open`,
`git`, `python3`, `curl`, `distrobox`, libGL, libX11 and the rest Fyne
links; no browser, no webkit2gtk, no uv. Windows 11 PC: WebView2,
winget. macOS 27.0 on this Mac: CLT, Docker Desktop 29.8 (arm64 engine;
bind mounts hung, `docker build --output` works), `codesign`, `hdiutil`.
Docker on this Mac is used only for the Linux build.

Prototype results that decide the design (binaries stripped, archives as
built by `build-all.sh`):

| Candidate | macOS | Windows x64 | Linux x64 | macOS 27 window | Deck window | Reproducible | Built on the Mac |
|---|---|---|---|---|---|---|---|
| Go Fyne 2.8.2 (the pick) | 23.6 MB arm64, 46 MB universal `.app` (23.2 MB zip) | 25.2 MB (12.0 MB zip) | 24.9 MB (11.9 MB tar.gz) | yes, unpatched | yes (both the Deck-box build and the Mac-Docker build) | yes: each binary twice equal; the Deck-box build reproduced on the Mac in an emulated Fedora image, same sha256 | all three: native cgo; llvm-mingw cgo; Docker multiarch cross, 72 s |
| Go Gio 0.10.3 | 10.3 MB | 9.0 MB | 10.0 MB | only with a local patch (`CVDisplayLink` refused, -6661) | yes | yes | Windows pure Go; Linux needs the same image |
| Python tkinter + PyInstaller (fallback) | 11.9 MB (27 MB `.app`) | 11.5 MB | 15.6 MB | yes | yes | no | no: each OS builds its own |
| Go TUI (huh) | 6.0 MB | 4.7 MB | 4.4 MB | terminal | konsole | yes | yes, no cgo |

## Goals / Non-Goals

Goals: a player with nothing installed goes from a download to an
installed game on their own machine through one windowed program, with
the stock defaults one click away; the same program makes a bundle for
another machine of theirs; every build step stays the CLI's; the wizard
is generic (the CLI's) and each game repo configures, builds and
publishes its own binaries, adapted to that release; one command on the
Mac builds the three distributables, pinned and reproducible; the same
command runs in the game repo's GitHub Actions; a Burnout 3 wizard is the
same code with b3's config.

Non-goals: self-update, signing and notarization, building without git,
installing Homebrew by itself (it opens Apple's Terminal on the official
installer instead), a second progress implementation (the CLI's plain
lines are shown), any change to the game, the runtime or the toolkit,
accessibility beyond Fyne's (a follow-up).

## Decisions

**D1. Go with Fyne.** `fyne.io/fyne/v2` v2.8.2 (cgo on every platform:
GLFW and OpenGL), `ncruces/zenity` for the file and folder dialogs (the
OS's own: win32 on Windows, `osascript` on macOS, `zenity`/`kdialog` on
Linux, both on SteamOS; Fyne's `dialog.ShowFileOpen` when none is
found). No TOML reader: the game's config reaches the binary as JSON
(D2a) and the seed is written by the model.
Rationale: the user's choice after the spike's table (Context); the
condition it came with, "a single machine can build all three", is met
(D12). Known costs, accepted: 24 to 25 MB binaries (12 MB zipped),
Fyne's own Material-like look on every OS, no accessibility tree. The
fallback, recorded: Python tkinter + PyInstaller (round 2's pick; per-OS
builds, not reproducible, 1.2 s start) if Fyne fails in practice on a
player's machine (an OpenGL-less VM is the known case: Fyne needs GL
2.1 or GLES; the wizard prints Fyne's error and the command-line route).

**D2. Where: the generic wizard is `xboxrecomp-cli/wizard/`, its own Go
module; each game repo configures, builds and publishes its own binaries
(the user, round 4: "the wizard could be offered as a generic tool within
xboxrecomp-cli and each repo does its own implementation").** The Go
module knows no game: not a name, a URL, a target or an option. Layout:
`cmd/wizard/main.go` (flags); `internal/gamecfg` (the embedded config of
D2a decoded and validated; no I/O beyond the embed); `internal/model`
(the choices from the config's options, the `package` argument list and
the seed text; no I/O); `internal/hostinfo` (OS, arch, install root, free
space, the settings file); `internal/fetch` (sha256-checked downloads
into `<root>/tools/` and into the clone: uv, MinGit, the Homebrew
installer from `wizard/pins.json`, and the config's `[[wizard.fetch]]`
entries); `internal/repo` (git clone of the config's repo at its tag,
the commit check); `internal/runner` (the `uv run --project <cli>
--locked xbr --game <root> --prog <slug> ...` line built the way
`wrapper/game.py` builds it, the `external/` clone of the CLI at `[cli]`
with its `.xbr-pin` marker, `doctor --json`, the `package` run streamed);
`internal/update` (the release check); `internal/screens` (the Fyne
containers). A Burnout 3 wizard is the same module built against b3's
`game.toml`.

**D2a. The game's wizard config is a `[wizard]` table in `game.toml`,
embedded at build time.** `game.toml` rather than a `wizard.toml`:
`game.toml` is already "what xboxrecomp-cli needs to know about this
game", read on every command and validated by `manifest.py` (which has
optional tables, `package` and `enhance`, so `wizard` is a third with
schema checks and defaults for free); the facts the wizard needs are
mostly there already (`[game] name`/`slug`, `[package] app`/`targets`,
`[data]` folders, `[cli]`), so a second file would repeat them or
cross-reference them; `xbr new` scaffolds `game.toml`, so it scaffolds
the `[wizard]` table with it; and one file is one thing to pin at the
release. The table adds only what is the wizard's:

```toml
[wizard]
# The game repo: cloned at the release tag; also where the update check
# looks for a newer wizard. Required.
repo = "https://github.com/apexJCL/blinx2-recomp.git"
# The icon fyne package bakes into the binaries (a plain PNG, no game
# data). Required.
icon = "packaging/wizard-icon.png"
# A subset of [package] targets to offer; default: all of them.
targets = ["windows", "steamos", "macos"]
# Anything else the final build needs that the clone does not carry:
# archives by sha256, unpacked into the clone (dest relative to it),
# optionally per host. Empty for BLiNX 2 today: the CLI, the toolkit and
# llvm-mingw are pinned in [cli], [toolkit] and setup-pins.json and the
# CLI fetches them itself.
# [[wizard.fetch]]
# name = "extra-assets"
# url = "https://.../extra-assets-1.0.tar.gz"
# sha256 = "..."
# dest = "third_party/extra-assets"
# hosts = ["windows", "macos", "linux"]   # default: all
# The options screen, in order. Each maps to a package flag or a
# config.toml key; the default is what the screen preselects and what
# the seed omits.
[[wizard.option]]
key = "scale"
label = "Render scale"
kind = "choice"
values = ["1", "2", "3"]
default = "1"
config = "render.scale"
[[wizard.option]]
key = "fullscreen"
label = "Fullscreen"
kind = "bool"
default = false
config = "present.fullscreen"
[[wizard.option]]
key = "hud_pack"
label = "HUD texture pack (needs PT Sans Narrow Bold on Linux and Windows)"
kind = "bool"
default = false
flag = "--hud-pack"
```

`manifest.py` validates it: `repo` a URL, `icon` an existing PNG,
`targets` within `[package] targets`, each option with exactly one of
`config` (a key in `packaging/config.default.toml`) or `flag` (an
argument `package` accepts), `kind` in `bool`/`choice`, `default` within
`values`. At build time `xbr wizard build` (D12) resolves the manifest
and writes `wizard/internal/gamecfg/config.json` (generated, gitignored,
`//go:embed config.json`): `game` (name, slug, app), `release` (repo,
tag, commit), `fetch`, `targets`, `data` folders, `options`, the CLI's
`[cli]` pin for the runner. One generated file rather than `-X` strings
(no quoting of structured text through the linker) and rather than
reading `game.toml` in Go (the manifest's rules and defaults stay in one
implementation, Python). A binary with an empty `config.json` is in
developer mode: `--game DIR` runs `xbr --game DIR wizard config --json`
through the uv and CLI checkout on the developer's machine (the same
resolution as `wrapper/game.py`: `$XBOXRECOMP_CLI_DIR`, `../xboxrecomp-cli`)
and uses that; `--config FILE` takes the JSON directly (tests).

The player is asked only for the dump: the repo, the tag and the targets
come from the embedded config; there is no repo question in the normal
flow.

**D3. The model is separate from the screens.** `internal/model` holds
the state and the two outputs (the `package` argument list and the
`config.toml` seed text), with table tests; `internal/screens` only
reads and writes it. Screens, in a `container.NewStack` with one visible
page, Back and Next (or Build) at the bottom, Next the default: welcome
(version and the three pins, the install root with Change, the
Gatekeeper/SmartScreen note on first run, the release notice of D13 when
there is one); checks (D6); dump (image or folder, then the dialog;
`--no-dialog` or no dialog tool: an entry with path validation: exists;
a folder has `default.xbe`); target (D7); options (D8); summary (the
command and the seed in full, Build and Back); build (D9); done (D10).
Closing the window during a build asks first.

**D4. Install root, default and changeable.** Defaults: Windows
`%LOCALAPPDATA%\b2` (short, for `doctor`'s 60-character path warning and
`LongPathsEnabled`); macOS `~/Library/Application Support/blinx2-recomp`;
Linux `~/.local/share/blinx2-recomp` (on the Deck the home survives
SteamOS updates). The welcome screen shows it with a Change button (a
folder dialog); the choice is saved in the wizard's settings file
(`%APPDATA%\blinx2-wizard\settings.json`, `~/Library/Application
Support/blinx2-wizard/settings.json`, `~/.config/blinx2-wizard/settings.json`)
and offered next time. Inside the root: `tools/uv/`, `tools/git/`
(Windows, MinGit), `<slug>-recomp/` (the clone) and the clone's own
`external/`, `third_party/`, `.venv/`, `build-pkg-*/`, `dist/`. Free space
is checked against 15 GB before the clone (`doctor`'s figure), plus the
image's size when the dump is an image.

**D5. uv and git are fetched, not installed.** uv: the Astral release
archive for the host (`uv-x86_64-pc-windows-msvc.zip`,
`uv-aarch64-apple-darwin.tar.gz`, `uv-x86_64-apple-darwin.tar.gz`,
`uv-x86_64-unknown-linux-gnu.tar.gz`) at a version and sha256 pinned in
`wizard/pins.json` (the shape of `config/setup-pins.json`; `xbr pins
refresh --wizard` rewrites it from the GitHub API). A uv already on PATH
at >= `env.UV_MIN` is used instead. git: on Windows, MinGit (Git for
Windows' portable zip) the same way; on macOS the Command Line Tools
(`xcode-select -p`; when missing the wizard runs `xcode-select
--install`, Apple's own dialog, and polls `/Library/Developer/
CommandLineTools`; a Mac with Xcode passes too); on Linux the
distribution's git (present on SteamOS; else the apt/dnf/pacman line
from `doctor.linux_flavour`'s mapping). Both tool folders are prepended
to the child's PATH; the user's PATH is never edited. No system Python
is needed: the CLI runs in its locked `.venv` through uv, which fetches
Python 3.12 with its built-in hashes.

**D6. The checks screen is `doctor --json`.** The CLI gains `xbr doctor
--json`: `{"host": {...}, "lines": [...], "targets": [...], "blocked":
{target: reason}, "problems": [...], "next": "..."}` from
`doctor_report()` and `PROBLEMS`, nothing recomputed. The wizard runs it
after the clone (with the uv it fetched) and shows one row per line, the
blocked targets with their reasons, and for each thing `setup` cannot
fetch, either an Install button (D11) or the command to run and a Retry.

**D7. Targets come from the config and `doctor`, the host's own
preselected.** The radio group has the config's `targets` (the
`[wizard] targets` subset of `[package] targets`), enabled when
`doctor`'s `targets` has them, otherwise disabled with the `blocked`
reason beside it. The
default is the host's native target (`main.native_target()`'s rule:
macos on a Mac, windows on Windows, steamos on Linux). On the Deck the
wizard adds one line: the build is long and memory-heavy here; a PC is
faster.

**D8. Options come from the config and map to the CLI and the seed,
never to a new pipeline.** The options screen is built from the config's
`options` (D2a), in order, each a checkbox (`bool`) or a radio group
(`choice`) with its label and default. An option with `flag` adds that
argument to the `package` line when set; an option with `config` writes
that `config.toml` key to the seed when its value differs from the
declared default (the default is declared in `game.toml` beside the key
and validated against `config.default.toml` at build time, so a changed
game default means a changed `[wizard]` entry, caught by the manifest
check). BLiNX 2's list (cat's `[wizard]` table, task 3.1): `--hud-pack`
(a `package` argument: the wizard runs `enhance hud` first; the label
says PT Sans Narrow Bold is needed on Linux and Windows, else the atlas
is upscaled), `render.scale`, `present.fullscreen`, `present.pacing`,
`input.keyboard`, `input.mouse`. The seed goes two ways: (a) `xbr
package --seed-config FILE` (new, CLI): the file is staged into the
bundle as `config.seed.toml` beside `config.default.toml`, and each
installer copies it to the data folder's `config/config.toml` only when
that file does not exist (NSIS: `IfFileExists` guard; `install.sh`: in
the branch that creates `config/`; macOS: the launcher's first-launch
path that already renames `enhance.toml`); (b) until (a) is merged, when
the target is the host, the wizard writes the seed to the data folder's
`config/config.toml` itself under the same not-exists rule and says so.

**D9. The build is the CLI's; the wizard shows its lines.** The wizard
runs `xbr package <target> --dump PATH [--hud-pack] [--seed-config F]
--plain` with `CI=1`, stdout and stderr merged through a pipe into a
scrolling log pane, and parses only what `--plain` already prints: the
plan line (the step list and the bar: step n of m) and each step's start
and end. Nothing new is added to the CLI's output. The full tool output
is where the CLI puts it (`build-logs/`), named on the done screen.
Cancel sends SIGINT (`CTRL_BREAK_EVENT` on Windows) to the child's
process group and waits; the wizard then reports the stop and the log
path.

**D10. Done screen.** Success: the bundle path (`dist/...`), the install
step for that target in the words of `docs/packaging.md` section 3, 4 or
5, and for the host's own target an "Install now" button: Windows runs
the setup program; macOS opens the `.dmg` (`open`); steamos runs
`./install.sh --steam` from the unpacked tar in a terminal (it asks about
umu as today). Failure: the step that failed, the log's path, "Open the
log folder" and "Retry" (which reruns `package`, whose plan skips what is
done). The data folder is named so the player knows where saves and
`config/config.toml` live. Both end with the bundle rule: private, for
the player's own machines.

**D11. Privileges: never the wizard's.** What needs a password is run
where the OS asks for it, by the tool that needs it:
- macOS, Homebrew missing: the checks screen shows the two commands and
  an "Install Homebrew" button, which writes the official installer
  (fetched from a pinned commit of `Homebrew/install` with a pinned
  sha256 in `pins.json`) to `<root>/tools/` and opens it in Terminal.app
  (`open -a Terminal <script>`); the installer asks for the password
  through `sudo` in that terminal; the wizard polls for
  `/opt/homebrew/bin/brew` or `/usr/local/bin/brew` and then enables
  Retry. `brew install sdl2 sdl3 openssl libepoxy` and `brew install
  makensis` need no password: an "Install now" button runs them in the
  log pane. `xcode-select --install` is Apple's dialog (D5).
- Linux, `nsis` missing: the distribution's command (from
  `doctor.makensis_hints`) shown, and a "Run it" button that opens it in
  `konsole -e` / `x-terminal-emulator -e` where `sudo` prompts; on an
  immutable host the distrobox recipe is shown as text only (v1).
- Windows: nothing needs elevation (NSIS, llvm-mingw, MinGit and uv are
  per-user downloads).
Rejected: `osascript ... with administrator privileges` (it would run
Homebrew as root, which Homebrew refuses, and the prompt would carry the
wizard's name) and any password field in the wizard.

**D12. The build entry point is the CLI: `xbr wizard build` makes the
three distributables from the game repo's config.** `xbr --game DIR
wizard build [--tag T] [--only macos,windows,linux] [--out DIR]`
(Python, `src/xboxrecomp_cli/wizard_build.py`; through a game's
bootstrap it is `./blinx2 wizard build`): it resolves the manifest,
takes the release tag (`--tag`, else the checkout's tag, else refuses:
a wizard is built for a release) and its commit, writes the embedded
`config.json` (D2a) into the CLI checkout's `wizard/` module, builds the
binaries with the Go toolchain, packages them and names the assets
`<slug>-wizard-<tag>-{windows-x64.zip,macos.zip,linux-x64.tar.gz}` plus
`SHA256SUMS`. It needs the CLI as a checkout (the `uv run --project`
form the bootstrap already uses; `wizard/` sits beside `src/`), not a
pip install; `xbr wizard config --json` prints the config it would
embed; `xbr wizard check` runs the Go gates (D14). The spike's
`build-all.sh` is its shape; every input is pinned in `wizard/pins.json`:
- Go: the official tarball for the build host by sha256, unpacked under
  `wizard/.tools/go/` (or `$WIZARD_GO`), `GOTOOLCHAIN=local`; `go.mod`'s
  `toolchain` line names the same version. Flags for every binary:
  `-trimpath -ldflags="-s -w -buildid="` (the version from the tag through `-X main.version`; the game facts come from the embed, D2a).
- macOS: two cgo builds (`GOARCH=arm64`, `GOARCH=amd64`, Apple clang from
  the Command Line Tools, `DEVELOPER_DIR` as the CLI sets it), `lipo`,
  then `fyne package -os darwin` (the tool at `fyne.io/tools/cmd/fyne@v1.7.1`,
  run with `go run`; the icon is the config's `[wizard] icon`, a plain
  PNG in the game repo, never from the dump) makes `<slug>-wizard.app`;
  `ditto -c -k --keepParent` makes `<slug>-wizard-<tag>-macos.zip`.
- Windows: one cgo build with `CC=<llvm-mingw>/bin/x86_64-w64-mingw32-clang`
  (`CXX` likewise), `-H windowsgui`; llvm-mingw is the one the CLI's
  `setup-pins.json` pins (`fetch.fetch_mingw` fetches it into the game
  checkout; the script takes `$LLVM_MINGW` or fetches the same archive
  by the same sha256 into `wizard/.tools/`). `zip -X -j` makes
  `blinx2-wizard-<tag>-windows-x64.zip` with the one exe inside (the
  user's form).
- Linux: `docker build --platform linux/arm64 -f wizard/linux/Dockerfile
  --output type=local,dest=...` with the sources as the build context.
  The builder image (`wizard/linux/builder.Dockerfile`) is
  `golang:1.27.2-bookworm` **by digest** plus Debian multiarch
  (`crossbuild-essential-amd64` and the amd64 `libgl1-mesa-dev`,
  `libx11-dev`, `libxcursor-dev`, `libxrandr-dev`, `libxinerama-dev`,
  `libxi-dev`, `libxxf86vm-dev`, `libxkbcommon-dev`, `libwayland-dev`,
  `libegl1-mesa-dev`): an arm64 container whose gcc targets amd64, no
  emulation, no bind mount (Docker Desktop's mounts hung on the spike's
  Mac; `--output` needs none and is hermetic). `tar --uid 0 --gid 0
  --numeric-owner --mtime=@$SOURCE_DATE_EPOCH -czf` makes
  `blinx2-wizard-<tag>-linux-x64.tar.gz` with the exec bit kept.
- `SHA256SUMS` over the three archives; the archives' entries get a fixed
  mtime (`SOURCE_DATE_EPOCH` from the tag's commit date) so the archives
  reproduce as well as the binaries.
The Linux step inside the image gets the generated `config.json` with
the sources (the build context is the module directory). Evidence: the
spike's script produced the three assets and `SHA256SUMS`
on the Mac (9 s warm, about 3 min cold); each binary built twice has one
sha256; the Linux binary ran on the Deck (every library found, window
opened); and the round-2 Deck-box build was reproduced byte for byte on
the Mac in an emulated Fedora 42 image, so the Linux output depends on
the image alone. Fallback for the Linux step, if Docker on the Mac turns
fragile: the same Dockerfile on WSL on the Windows PC (the user's offer;
the distro and its vhdx on `D:\xbr\`) or on the Linux/Proton host; the pinned digest
gives the same hash. Why not fyne-cross (needs Docker too, pins by tag,
one more tool), zig cc (a sysroot with the X11/GL headers to assemble)
or UTM (a VM for one compile).

**D13. Release check: a notice, nothing more.** At start, in a goroutine
with a 3 s timeout, `internal/update` fetches
`https://api.github.com/repos/<owner>/<repo>/releases/latest` for the
config's `[wizard] repo` (one unauthenticated call per run; the limit is
60 an hour per address) and compares `tag_name` with the embedded
release tag (the game repo's version scheme, compared as dotted
numbers). Newer: the welcome screen shows "A newer wizard is available:
<tag>" with the release notes (`body`, as text in a scrolling box) and a
button "Open the release page" (`fyne.CurrentApp().OpenURL`). The player
downloads and runs it by hand; this wizard keeps working. Not newer,
offline, timeout, HTTP 403 (rate limit) or any other error: no notice,
never an error; one line in the wizard's log file. `--no-update-check`
and a settings-file key turn it off. No self-replace, no download, no
dependency pull: the user's decision, because a self-swapped binary is a
fresh download to Gatekeeper and SmartScreen and would push the project
towards signed executables, which are not worth it unless free; releases
stay unsigned for the same reason. The trust the check needs is TLS to
github.com for a tag and some text; what the player then downloads sits
beside the release's `SHA256SUMS`.

**D14. Gates for the Go module: the CLAUDE.md exception.** The user's
approval of the text in REPORT.md section 21 is phase 0. `wizard/check.sh`:
`gofmt -l` empty, `go vet ./...`, `go test ./...` (model tables, the seed
writer, the pins reader, the fetch against a local HTTP server with a
wrong hash refused, the runner's command builder in developer mode, the
`doctor --json` decoder on a saved sample, the plan-line parser on saved
`--plain` output, the update check with a stubbed transport for newer,
same, older, timeout, 403 and bad JSON, the Linux dialog and terminal
argument builders), `staticcheck` when available, and the
reproducibility check: `xbr wizard build` run twice gives equal sha256s for the
three binaries and the three archives. The CLI's `uv run pytest tests`
and ruff stay as they are; the Go gates run beside them when `wizard/`
changed. Dependencies are few and each is named in `wizard/README.md`
with why; cgo is used only by Fyne.

**D15. Privacy and legal.** The wizard never reads the dump itself (the
CLI's `import` does, after the title check); it never uploads anything;
the only network calls are the pinned downloads, the clones, uv's own
fetches and the one release-check request. The bundle rules are repeated
on the done screen.

**D16. GitHub Actions: the free tier fits; the same script runs there.**
GitHub's billing page: Actions "is free for self-hosted runners and for
public repositories that use standard GitHub-hosted runners"; "larger
runners are always charged for, even when used by public repositories";
the January 2026 price changes left that as it is. `apexJCL/blinx2-recomp`
and `apexJCL/xboxrecomp-cli` are public; `macos-15` (Apple silicon),
`ubuntu-24.04` and `windows-2025` are standard runners. The build needs
no secret beyond the workflow's `GITHUB_TOKEN` and no game data. **Each
game repo owns its publishing:** the workflow lives in the game repo
(blinx2-recomp), not in the CLI, as `.github/workflows/release-wizard.yml`
from the CLI's `templates/new-game/` (so `xbr new` scaffolds it for the
next game; cat gets the same file by hand in task 3.2). It runs the
game's bootstrap, which resolves the CLI at the pinned `[cli]` tag and
commit exactly as a player's machine does, so the CLI needs no separate
checkout step and no action of its own. macOS runners have no Docker, so
the template has three jobs (on tags `v*`, and `workflow_dispatch` with
a `release: false` input for dry runs): `build-macos` on `macos-15`
checks out the game repo at the tag, installs uv (`astral-sh/setup-uv`
pinned by sha, or the pinned archive by sha256) and runs `./<slug>
wizard build --only macos,windows --tag $TAG` (the CLI fetches Go and
llvm-mingw itself, sha256-checked) and uploads the two archives;
`build-linux` on `ubuntu-24.04` runs `./<slug> wizard build --only
linux` (Docker is on ubuntu runners; the same digest-pinned image, so
the same hash as the Mac's) and uploads the tar.gz; `release` (only when
`release`) downloads both, writes `SHA256SUMS`, checks the hashes against
what each job printed, and attaches the four files with `gh release
upload` (no third-party action). The implementer adds the template and
cat's copy and dry-runs it with `workflow_dispatch` on a branch; pushing
tags and publishing releases stay the user's batched push rounds
(CLAUDE.md). The Mac-only path (D12 by hand, the assets uploaded with
the release) stays the fallback when the runners are unavailable.

## Risks / Trade-offs

- Fyne's own look (Material-like, not native) on every OS, and no
  accessibility tree; the native dialogs and one question per screen
  carry the "normal app" feel. A follow-up can revisit when Fyne gains
  a11y or when Gio's macOS 27 fix lands upstream.
- 24 to 25 MB binaries (12 MB zipped); fine for a one-shot download.
- cgo everywhere: three compilers (Apple clang, llvm-mingw, the image's
  gcc) in one script; all three are pinned and the spike ran them all
  from one Mac. If the Docker step turns fragile, D12's WSL or the Linux/Proton host
  fallback runs the same Dockerfile.
- Fyne needs OpenGL 2.1 or GLES on the player's machine; a VM without GL
  is the known failure; the wizard prints Fyne's error and the
  command-line route. The Python fallback (D1) does not have this
  dependency.
- Windows interactive runs were not possible from the spike's ssh
  session (no desktop); task 5.3 covers them at the PC.
- Homebrew remains a Mac-player requirement (the macos target's four
  formulae; `makensis` for the windows target); D11 makes it two clicks.
  Vendoring the dylibs into `setup-pins.json` is a CLI follow-up.
- A Deck host builds slowly and the gen build is memory-heavy there (the
  bench's OOM note); the wizard warns, does not refuse.
- Two Go module caches and a Docker image on the maintainer's Mac (about
  2 GB each); the build script keeps them under `wizard/.tools/` and the
  image is one `docker rmi` away.
- A Go module in a Python repo: `uv run pytest tests` and ruff do not see
  it; D14's script (`xbr wizard check`) is the gate and the CLI's own CI
  runs it.
- The split puts the schema in the CLI and the values in each game repo:
  a `[wizard]` entry that names a config key the game dropped is caught
  by the manifest check at build time, not at runtime, so `xbr wizard
  build` (and the game's workflow) is the place that fails. A game repo
  that pins an older CLI than the one its `[wizard]` table needs gets the
  manifest's "unknown key" error; `schema` in `game.toml` is unchanged
  (the table is optional).

## Migration Plan

Additive. The command-line route (`./blinx2 PATH`) stays and the docs keep
it as the second route. `package --seed-config` and `doctor --json` are
optional arguments; nothing changes without them. Rollback: remove the
assets from a release; the module can stay unbuilt.

## Open Questions

1. (Closed, 2026-10-15: the user approved the Go exception and it is in
   CLAUDE.md, "Code style".)
2. The wizard's icon is the game repo's `[wizard] icon` PNG (D2a), never
   from the dump; cat needs one committed (`packaging/wizard-icon.png`,
   task 3.1). Who draws it: a plain placeholder in v1 unless the user
   provides one.
3. Whether the workflow's `release` job runs on tag push or only by hand
   (`workflow_dispatch`), given the batched push rounds. The spec assumes
   tag push with a dry-run input.
