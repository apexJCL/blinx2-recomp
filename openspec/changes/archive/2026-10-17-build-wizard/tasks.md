Conventions: **CLI** = branch `feat/build-wizard` off `main` a7cdc15
(v0.6.7) in a fresh CLI worktree (`wt/wizard/xboxrecomp-cli`), commits
authored and committed as the noreply identity, no tracker ids, host names
or private paths; **cat** = branch `feat/build-wizard` off `main` (028efc9
or later) in `wt/wizard/cat`. The toolkit is not touched. Go is installed
in user space only (the official tarball at the `go.mod` version under
`wizard/.tools/` or the workspace's `runs/wizard-spike/toolchains/go`,
sha256 `76812b21...` for darwin-arm64); Docker Desktop on the Mac is used
only for the Linux build, with `docker build --output`, never bind
mounts. Design decisions are cited as D1-D16. The split: phases 1-2 land
in the **CLI repo** (the generic wizard, its build command, the manifest
schema, the workflow template), phase 3 in **cat** (BLiNX 2's `[wizard]`
config, icon, workflow, docs, the CLI pin); each has its own gates
(phase 4). Tasks marked **needs-user** need the user's disc image or a
decision.

Phase map:

| Phase | Where | Size | Depends on |
|---|---|---|---|
| 0 Decisions | user | XS | - |
| 1 CLI (Python): manifest `[wizard]`, `xbr wizard`, `doctor --json`, `--seed-config`, the workflow template | CLI | M | 0 |
| 2 CLI (Go): the generic wizard module | CLI | L | 1.1 (the config shape) |
| 3 cat: `[wizard]` config, icon, workflow, docs, CLI pin | cat | S | 1, 2 committed and tagged |
| 4 Gates | CLI, cat | S | 2, 3 |
| 5 Host runs | Mac, Windows PC, Deck | M | 4 |
| 6 Review and merge | main session | S | 5 |
| 7 Follow-through | main session | XS | 6 |

## 0. Decisions (needs-user)

- [ ] 0.1 (Done 2026-10-15: the Go exception is in CLAUDE.md.) Still
  open: the BLiNX 2 wizard icon (a placeholder PNG in v1 unless the user
  provides one; design Open Question 2) and whether the release job runs
  on tag push (Open Question 3). D16 is updated if the answer differs.

## 1. CLI, Python: the config schema, the build command, the two additions

- [ ] 1.1 `manifest.py`: the optional `wizard` table (D2a): `repo` (URL,
  required), `icon` (a path to an existing PNG, required), `targets`
  (subset of `package.targets`, default all), `[[fetch]]` entries
  (`name`, `url`, `sha256`, `dest` relative to the clone, `unpack`,
  `hosts`), `[[option]]` entries (`key`, `label`, `kind` bool/choice,
  `values`, `default`, exactly one of `config` or `flag`); the
  validation rules in D2a (`config` keys checked against
  `packaging/config.default.toml`, `flag` against `package`'s parser,
  `default` within `values`). `docs/manifest.md` gets the table. Tests
  in `tests/test_manifest.py`: a valid table, each rule's refusal, a
  game without the table (unchanged behaviour).
- [ ] 1.2 `xbr wizard config [--json] [--tag T]` (D2a, D12): the embedded
  config as JSON from the resolved manifest (`game`, `release` with
  repo/tag/commit, `fetch`, `targets`, `data`, `options`, the `[cli]`
  pin); the tag from `--tag`, else the checkout's tag on HEAD, else an
  error naming both routes. Test: cat's `game.toml` plus a `[wizard]`
  table decodes to the expected JSON; a dirty or untagged checkout is
  refused without `--tag`.
- [ ] 1.3 `xbr wizard build [--tag T] [--only macos,windows,linux] [--out
  DIR]` (D12), `src/xboxrecomp_cli/wizard_build.py`: needs the CLI as a
  checkout (refuses from a pip install, naming the bootstrap route);
  writes `wizard/internal/gamecfg/config.json` from 1.2; fetches Go and
  llvm-mingw by sha256 into `wizard/.tools/` (or `$WIZARD_GO`,
  `$LLVM_MINGW`) from `wizard/pins.json`; the macOS universal `.app`
  through `fyne package` with the config's icon, the Windows exe, the
  Linux binary through `docker build --output` with
  `wizard/linux/builder.Dockerfile` (base by digest) and
  `wizard/linux/Dockerfile`; the three archives with fixed mtimes
  (`SOURCE_DATE_EPOCH` from the tag's commit) and `SHA256SUMS`, named
  `<slug>-wizard-<tag>-*`; each binary run with `--dry` (the Linux one
  in the builder image under `--platform linux/amd64`, or skipped with a
  note when emulation is off). `xbr wizard check` runs `wizard/check.sh`
  (D14). Tests: the command lines built for each target from a fake
  pins file (no toolchain run), the archive naming, the `--only` parse;
  the real build is the gate (4.1). `docs/wizard.md`: the config, the
  build, the pins, the gates, the game-repo workflow.
- [ ] 1.4 `doctor --json` (D6): `doctor.doctor_report()` already returns
  `(lines, targets, blocked)`; add `host` (`host_os`, `host_arch`,
  Python), `problems` (`PROBLEMS`), `next` (`next_step`'s line) to a dict
  and print it with `json.dumps(indent=2)` when `--json`. No change to the
  text output. Tests in `tests/test_doctor.py`: a fresh tree (every row
  missing) and a tree with a fake `.venv`, each decoded and the keys
  checked; `blocked` carries `setup.host_blockers`'s words.
- [ ] 1.5 `package --seed-config FILE` (D8a): `package/lib.py` stages the
  file as `config.seed.toml` beside `config.default.toml` in every target's
  payload; the manifest records `seed_config: true`. Installers: NSIS
  template copies it to `$LOCALAPPDATA\<app>\config\config.toml` under
  `IfFileExists` (and the uninstaller leaves it, like the rest of the data
  folder); `steamos/install.sh` copies it in the branch that creates
  `config/`; the macOS launcher copies it on the first-launch path that
  renames `enhance.toml`. The seed is refused when it is not valid TOML
  (`tomllib`) or names a key not in `config.default.toml`. Tests:
  `tests/test_package_*.py` cases for staging, the manifest flag, the
  refusals; the steamos installer test (the existing one that runs
  `install.sh` into a tmp root) with and without an existing
  `config/config.toml`.
- [ ] 1.6 The workflow template (D16): `templates/new-game/.github/
  workflows/release-wizard.yml` with `@SLUG@` filled by `xbr new`
  (`scaffold.py`'s `fill`): on tags `v*` and `workflow_dispatch` (input
  `release`, default false); `build-macos` (`macos-15`): checkout at the
  tag, uv installed (action pinned by sha), `./@SLUG@ wizard build --only
  macos,windows --tag $TAG`, upload the two archives; `build-linux`
  (`ubuntu-24.04`): the same with `--only linux`; `release`: download
  both, `SHA256SUMS`, compare with the jobs' printed hashes, `gh release
  upload` when `release` is true. `templates/new-game/game.toml` gets a
  commented `[wizard]` table with one option of each kind. Test: `xbr
  new` into a tmp dir writes both with the slug filled.
- [ ] 1.7 `docs/` and `--help`: the new command and options in the CLI's
  reference and in `wrapper` help; CHANGELOG entry. Commit, `uv run
  pytest tests`, ruff.

## 2. CLI, Go: the generic wizard module (D1-D5, D7-D14)

- [ ] 2.1 `wizard/go.mod` (`module wizard`, `go 1.27`, `toolchain
  go1.27.2`), `wizard/README.md` (what it is, the embedded config and
  developer mode, each dependency and why: `fyne.io/fyne/v2` v2.8.2,
  `ncruces/zenity`; the build and the pins), `wizard/pins.json` (the Go
  tarballs per build host by sha256, llvm-mingw as `setup-pins.json` has
  it, `fyne.io/tools/cmd/fyne@v1.7.1`, the builder image digest, uv,
  MinGit, the Homebrew installer commit), `wizard/check.sh` (D14),
  `wizard/internal/gamecfg/config.json` gitignored with an empty
  placeholder committed so `go build` works in developer mode.
- [ ] 2.2 `internal/gamecfg` (D2a): the embedded JSON decoded into a
  struct, `Empty()` for developer mode, validation (a target not in the
  list, an option with neither `config` nor `flag`, a fetch without a
  sha256 refused). Tests on a saved sample from `xbr wizard config` on
  cat's `game.toml` and on hand-written bad ones.
- [ ] 2.3 `internal/model` (D3, D8): the choices built from the config's
  options with their defaults; `Args()` (the `package` line: target,
  `--dump`, the set `flag` options, `--seed-config`) and `Seed()` (the
  `config` keys whose value differs from the declared default, grouped
  by table). Table tests on the sample: all defaults (empty seed, no
  flags), scale 2 + fullscreen, keyboard off, pacing spin, hud pack.
- [ ] 2.4 `internal/hostinfo` (D4): OS/arch, the default root per OS from
  the config's slug, the settings file (JSON, the saved root, the
  update-check switch), free space, the Deck detection (`/etc/os-release`
  `steamos`).
- [ ] 2.5 `internal/fetch` (D5, D11, D2a): the downloader to a temp file
  with sha256 and size checked before the move, unpack of zip and tar.gz,
  used for the tools (`<root>/tools/<name>/`) and for the config's
  `fetch` entries (into the clone at `dest`, filtered by `hosts`); a uv
  on PATH at >= 0.5.31 honoured (the same version parse as
  `env.find_uv`). Tests with `httptest`: right hash, wrong hash (nothing
  left behind), truncated, a `hosts` filter. `xbr pins refresh --wizard`
  (Python, CLI) rewrites the uv and MinGit entries from the GitHub API.
- [ ] 2.6 `internal/repo` (D5, D2): `git clone --branch <tag> --depth 1
  <repo> <root>/<slug>-recomp` (with the fetched or system git), `git
  rev-parse HEAD` must equal the embedded commit, else stop with both; a
  present clone at the commit is reused. macOS: `xcode-select -p` check,
  `xcode-select --install` and the poll. Linux: the git hint by
  `/etc/os-release` (the same mapping as `doctor.linux_flavour`).
- [ ] 2.7 `internal/runner` (D6, D9): the `uv run --project
  <root>/<slug>-recomp/external/xboxrecomp-cli --locked xbr --game
  <root>/<slug>-recomp --prog <slug> ...` line with the tools dirs
  prepended to PATH and the CLI cloned at the config's `[cli]` pin the
  way `blinx2.py` does it (tag, commit lock, `external/` with the
  `.xbr-pin` marker); developer mode runs `xbr --game DIR wizard config
  --json` the same way and decodes it; `Doctor()` decodes `doctor
  --json`; `Package()` runs with `--plain`, `CI=1`, merged output into a
  channel for the log pane, the plan line and step lines parsed for the
  bar; cancel by SIGINT / `CTRL_BREAK_EVENT` on the process group.
  Tests: the command builder (developer mode against a tmp game tree),
  the decoder on a saved `doctor --json` sample, the plan-line parser on
  saved `--plain` output.
- [ ] 2.8 `internal/update` (D13): `Latest()` with `net/http` against the
  config's repo, 3 s timeout, the tag comparison, nil on every failure;
  tests with a stubbed transport: newer, same, older, timeout, 403, bad
  JSON.
- [ ] 2.9 `internal/screens` (D3, D7, D8, D10, D11): the Fyne pages in
  order (welcome with the game name and release from the config, the
  root, Change, the notice box and the release-page button; checks with
  Install/Run/Retry; dump with the dialogs through `ncruces/zenity` and
  Fyne's dialog as the fallback, the entry fallback; target; options
  generated from the config; summary; build with the log pane and the
  bar; done). The Linux terminal launcher (`konsole -e`,
  `x-terminal-emulator -e`) tested as a pure argument builder. A test
  builds every page once with `fyne.io/fyne/v2/test.NewApp()` on the
  sample config (headless, no display needed). `cmd/wizard/main.go`:
  flags `--game DIR`, `--config FILE`, `--root DIR`, `--no-dialog`,
  `--dry` (print the command for the defaults), `--no-update-check`,
  `--version`. Commit; `xbr wizard check` green on the Mac with cat's
  config (developer mode).

## 3. cat: BLiNX 2's config, icon, workflow, docs

- [ ] 3.1 `game.toml` `[wizard]` (D2a, D8): `repo` the public
  blinx2-recomp URL, `icon = "packaging/wizard-icon.png"` (a plain PNG
  committed; placeholder in v1 unless the user provides one), `targets`
  all three, no `fetch` entries (with the comment saying why), the
  options: `--hud-pack` (flag), `render.scale` (choice 1/2/3, default
  1), `present.fullscreen` (bool), `present.pacing` (choice sleep/spin),
  `input.keyboard` and `input.mouse` (bool), defaults equal to
  `packaging/config.default.toml`. `blinx2 doctor` and the manifest
  check pass.
- [ ] 3.2 `.github/workflows/release-wizard.yml`: the CLI's template with
  `blinx2` filled (D16; one file, kept identical to the template so a
  later `xbr new` diff is empty). Dry-run it with `workflow_dispatch` on
  the branch (`release: false`); never push a tag or publish a release
  (the user's batched rounds). If the free-tier macOS runner is
  unavailable to the repo for any reason, record it and fall back to the
  Mac-only path (D12) as the release path.
- [ ] 3.3 `docs/packaging.md`: a "The wizard" section first in the player
  route (download, open, the Gatekeeper and SmartScreen steps, what it
  installs where, the data folder, the new-release notice), the command
  route kept after it, and a maintainer paragraph (`./blinx2 wizard
  build`, the workflow); README "Install and run": the wizard first.
  `docs/env.md` unchanged.
- [ ] 3.4 `game.toml` `[cli]` moves to the CLI release that carries
  phases 1 and 2 (tag + commit), `blinx2 pins refresh` output checked;
  commit.

## 4. Gates

- [ ] 4.1 CLI: `uv run pytest tests`, `uv run ruff check . && uv run ruff
  format --check .`, `xbr wizard check` (gofmt, vet, test, staticcheck,
  and `xbr --game <cat> wizard build` twice with equal hashes for the
  three binaries and three archives).
- [ ] 4.2 cat: `uv run pytest scripts`, ruff; `./blinx2 wizard config
  --json` and `./blinx2 wizard build --tag <local tag>` succeed from the
  cat worktree; Mac build with
  `DEVELOPER_DIR=/Library/Developer/CommandLineTools`; no golden is
  affected (no runtime change), stated in the review notes.

## 5. Host runs

- [ ] 5.1 **Mac (needs-user: the disc image):** the `.app` from
  `./blinx2 wizard build`, from a fresh root (`--root` in a scratch
  folder under `runs/wizard/`): uv fetched, the clone at the tag (a
  local tag on `wt/wizard/cat` until a release exists), the checks
  screen with the CLT and Homebrew rows (the Terminal launch for the
  Homebrew installer exercised, cancelled at the password prompt), the
  dump dialog with the user's image, the defaults building the macos
  bundle with the log pane and bar, Install now opening the dmg, the
  release notice against a stubbed newer release. `SDL_AUDIODRIVER=dummy`
  for any launch; no sound.
- [ ] 5.2 **Deck (Desktop Mode):** the Linux binary from the Mac's build,
  copied to `~/wizard-r4/` (removed after), run over ssh with the
  desktop's `DISPLAY`/`WAYLAND_DISPLAY` from `systemctl --user
  show-environment`: Dolphin's double-click, the `kdialog` dump dialog,
  steamos target preselected, the slow-host line shown. The game build
  itself runs on the Mac (the Deck rule: the gen build gets OOM-killed
  there); on the Deck the run stops at the summary and the Mac-built
  steamos tar is installed with `./install.sh --steam` as today.
- [ ] 5.3 **Windows PC (native, at the PC or with the user present; the
  scratch is `D:\bench\scratch\wizard\`, never `C:`):** the zip from the
  Mac's build; double-click; the SmartScreen dialog text recorded for
  the docs; MinGit and uv fetched into `tools\`; the win32 dump dialog;
  windows target preselected; a build to the setup program; Install now
  runs it; saves land in `%LOCALAPPDATA%\BLiNX2`.
- [ ] 5.4 The seed: on one host, scale 2 + fullscreen chosen; after
  install, `config/config.toml` holds exactly those two keys and a second
  install leaves it alone (D8).

## 6. Review and merge (main session)

- [ ] 6.1 Review of both branches; fixes go back to the branch's
  agent.
- [ ] 6.2 CLI: squash merge to `main` as the noreply identity, tag the
  release (`v0.7.0`), cat's `[cli]` pin follows (3.4). cat: squash merge
  (`openspec: build-wizard: ...` is the spec's commit; the feature's is
  `wizard: ...`).

## 7. Follow-through (main session)

- [ ] 7.1 Copy the agent's notes to `notes/wizard/`; the raw runs to
  `runs/wizard/` with `cp -c`; remove the worktrees (`git worktree remove
  --force` plus `rm -rf wt/wizard`), keep the branches.
- [ ] 7.2 `cat/TASKS.md`: the merge entry, the follow-ups (vendored macos
  dylibs; a no-git route; accessibility; the Python fallback note; the
  Gio macOS 27 patch offered upstream; b3's `[wizard]` table); the tracker item's
  asset list gains the wizard and the workflow; the tracker item closed.
- [ ] 7.3 Archive the change (`openspec archive build-wizard`).
