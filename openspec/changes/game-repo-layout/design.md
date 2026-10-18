# game-repo-layout: design

Status: survey and spec only (agent `repo-layout`, 2026-10-17). No
game repo or CLI is changed by this change's spec phase.

The facts below were checked against these commits:

| Repo | Commit |
|---|---|
| cat `main` | 82d6449 |
| b3 `main` | 0a2d8bd (`public/main` f7baab9, `origin/main` 79b578d) |
| `ssx3/recomp` `main` | d8bd99f |
| `spartan/tca` `main` | 4ccbc9c |
| xboxrecomp-cli `main` | f34648a (v0.7.7) |
| CLI `feat/wizard-incremental-builds` | 57f705a (`[wizard] private` added in 5133641) |

## Survey

### Trees and tooling

| Item | cat (BLiNX 2) | b3 (Burnout 3) | SSX 3 | Spartan |
|---|---|---|---|---|
| Slug / bootstrap | `blinx2`, `.cmd`, `.py` | `burnout3`, `.cmd`, `.py` | `ssx3`, `.cmd`, `.py` | `tca`, `.cmd`, `.py` |
| Bootstrap `.py` | 292 lines, the CLI's template | identical | identical | identical |
| Other top-level tracked | `analysis/` (golden.json, audio.json), `.claude/`, `NOTICE`, `.python-version` | upstream's `regen.sh`, `Setup.cmd`, `tools/`; `CONTRIBUTING.md`, `CONTRIBUTORS.md`, `ROADMAP.md` | none | `game.toml.bak-20261016` (a stray backup) |
| `[cli]` pin | tag v0.7.7 + commit | tag v0.7.5 + commit | commit only (v0.7.6's) | tag v0.7.6 + commit |
| `[toolkit]` pin | tag blinx2-v0.5.0, `blinx2/portability` | tag blinx2-v0.4.0, `blinx2/portability` | tag blinx2-v0.5.0, `blinx2/portability` | **commit 70c4371 on `posix-host/portability`**: not on the public fork, which has only `main`, `blinx2/portability` and open PR branches |
| game.toml tables | all, plus `[golden]`, `[input]`, `[enhance.hud]`, `[bench]`, `[bench.gc]`, `[[wizard.*]]` | all but `[enhance.hud]`; `[golden] json = ""` | scaffold set, `[package]`; `[wizard]` commented out | scaffold set; minimal `[package]` (no `product`); `[wizard] private = true` |
| `pyproject.toml` | dev: pytest, ruff, tomli, numpy; `[tool.ruff]`, `testpaths = ["scripts"]` | as cat, ruff excludes `_local`, `docs`; no testpaths | scaffold (pytest, ruff; no config) | scaffold |
| Tests (`scripts/test_*.py`) | 12 | 2 | 0 | 0 |
| `src/` | `main.c`, `recomp_manual.c`, `env/recomp_env_game.h`, game C files (`glow.c`, `pad_*.c`, `save_seed.c`) | upstream's `src/game/main.c`, `src/game/recomp/recomp_manual.c`, `src/game/CMakeLists.txt`, `src/env/recomp_env_game.h` | `main.c`, `recomp_manual.c` | `main.c`, `recomp_manual.c` |
| gen | `src/recomp/gen` | `src/game/recomp/gen` | `src/recomp/gen` | `src/recomp/gen` |
| `config/` | `seed_functions.json`, `setup-pins.json`, `spin_waits.json` | same three | `seed_functions.json`, `setup-pins.json` | same two |
| `packaging/` | `config.default.toml`, `launch.env.default.{macos,windows}`, `macos/{BLiNX2.in, Info.plist.in, README.part}`, `windows/{BLiNX2.rc.in, README.part}` | `README.intro`, `config.default.toml`, launch.env x2, `macos/*` (3), `steamos/README.part`, `windows/README.part` | launch.env x2, `macos/{Info.plist.in, README.part, Ssx3.in}`, `windows/README.part` | `launch.env.default.windows`, `windows/README.part` |
| `docs/` | `env.md`, `input.md`, `packaging.md`, `images/` | `architecture.md`, `boot.md`, `running.md` (its env doc), `images/`, `research/`, upstream's `screenshots/` | none | none |
| Data folder | `game_files` | `Burnout 3 Takedown` (upstream's name) | `game_files` | `game_files` |

### Docs, private files and openspec

| Item | cat | b3 | SSX 3 | Spartan |
|---|---|---|---|---|
| README / CHANGELOG / LICENSE | 561 / 128 lines / MIT | 338 / 96 / MIT | 28 / 9 / MIT | 28 / **none** / MIT |
| CONTRIBUTING, CONTRIBUTORS, ROADMAP, TESTING | none | first three tracked; `TESTING.md` local (`.git/info/exclude`) | none | none |
| Private notes | **tracked**: `TASKS.md`, `RESUME.md`, `RESUME-golden.md`, `RESUME-walker.md`, `WORKTREES.md`, `OPEN_QUESTIONS.md`, `.git-blame-ignore-revs` | untracked: `_local/` (gitignored), `TESTING.md` (excluded) | none in repo (tracker; `notes/untracked-projects.md`) | none in repo |
| `openspec/` | `config.yaml`, `specs/` (22), 14 active changes, archive | `config.yaml`, `specs/`, 2 changes, archive (moved from cat by the tracker item, scrubbed) | `changes/ssx3-bringup` only, **no `config.yaml`** | none |

### Ignores, publishing and CI

| Item | cat | b3 | SSX 3 | Spartan |
|---|---|---|---|---|
| `.gitignore` | its own (80 lines); gen, game data, `dist/`, `timeline/`, `user-logs` | its own (upstream's plus scaffold lines) | scaffold's | scaffold's plus `build-pkg-*/`, `tca-old/` |
| `.git/info/exclude` | `src/recomp/gen`, `/bench-logs`, `/.venv` | `/Burnout 3 Takedown`, `TESTING.md`, `runs/`, `analysis/`, `build-*/`, `gen/`, `/.venv`, `/third_party` | empty | empty |
| Nested worktrees | `wt/upstream-sync/` (an empty leftover directory, not ignored) | **`wt/apulife/b3`**, a live worktree at detached 56574b4; not ignored (`?? wt/`) | none | none |
| Remotes | none: the export goes to a separate clone | `origin` = sp00nznet (push disabled); `public` = apexJCL/burnout3-recomp, live | **`origin` = apexJCL/ssx3-recomp** (public, empty; push disabled since 2026-10-17, task 0.1) | **`origin` = apexJCL/spartan-recomp** (public, empty; push disabled since 2026-10-17) |
| Publish | `scripts/export-public.sh`: a fresh one-commit repo; EXCLUDE list; REWRITE (perl rules for the host's name); refuses bundles and the personal email; then `commit-tree` onto the public tip by hand | direct push of `main`; `scripts/audit-public.sh` (the CLI's audit, plus upstream screenshots allowed, a PNG chunk check, a refusal list, identities on `origin/main..`) | none | none |
| Audit private patterns | inside the export script (excluded) | `.git/info/audit-private` | none | none |
| CI (`.github/`) | `release-wizard.yml`, older than the template | same, older | `release-wizard.yml` = the CLI's template | none |
| `[wizard]` | `repo` = blinx2-recomp, options, credits | `repo` = burnout3-recomp, options, credits | commented out ("this repo is not published"; `private = true` waits for the CLI) | `private = true`, no `repo` (an unknown key in v0.7.6's schema, where `repo` is required) |

### What the CLI already assumes or writes

- **`xbr new`** (`scaffold.py`) writes these files:
  - `game.toml`, the three bootstrap files, `pyproject.toml`;
  - `.gitignore`, `.gitattributes`;
  - `README.md`, `CHANGELOG.md`;
  - `.github/workflows/release-wizard.yml`;
  - `config/seed_functions.json`.

  It also copies the toolkit's `templates/new-game/` (`CMakeLists.txt`,
  `src/main.c`, `src/recomp_manual.c`). It writes no `LICENSE`,
  `openspec/`, `scripts/`, ruff or pytest configuration, and no
  `packaging/`.
- **Paths come from `game.toml`.** gen, out, exclude_manual,
  data.game_files, build dirs, env_header and env_doc are all manifest
  keys with scaffold defaults. The CLI hard-codes no game layout, so b3's
  `src/game/...` and `Burnout 3 Takedown/` work unchanged.
- **The CLI already checks two templates.** `wrapper --check` compares the
  bootstrap with the CLI's template. The workflow's own header says "keep
  it the same as the CLI's template", but nothing checks the workflow.
- **`package` refuses a game without `LICENSE`.** The release workflow
  stops when the tag has no `CHANGELOG.md` section.
- **Publishing:** the CLI's `scripts/audit-public.sh` is for the CLI repo
  itself (`origin/main..main`). The CLI has no export and no game-facing
  audit command. `docs/maintainers.md` describes
  `.git/info/audit-private`.
- **`[wizard] private`** (the branch, 5133641) lets a game without
  a public repo build a wizard from a local checkout. With public repos
  for every game it is no longer needed by any of the four, but it stays
  in the CLI for a game that has none.

## Decisions

### D1. Required, conditional and optional entries

The layout is defined by `game.toml`: wherever a manifest key names a
path, the key wins and the standard name is its default. The CLI's
`docs/layout.md` (new) carries this table, and `doctor` checks it (D12).

| Entry | Status | Notes |
|---|---|---|
| `game.toml` | required | `schema`, the tables the CLI requires, `[public]` (D6) |
| `<slug>`, `<slug>.cmd`, `<slug>.py` | required | byte-equal to the CLI's template (`wrapper --check`) |
| `pyproject.toml`, `uv.lock` | required | dev group with pytest and ruff; `[tool.ruff]` and `[tool.pytest.ini_options] testpaths = ["scripts"]` (D4) |
| `.gitignore`, `.gitattributes` | required | the baseline (D3), plus the game's own lines |
| `README.md`, `CHANGELOG.md`, `LICENSE` | required | D2 |
| `CMakeLists.txt` | required | |
| the main C source | required | `[layout] main`, default `src/main.c` (b3: `src/game/main.c`) |
| the manual C source | required | `[pipeline] exclude_manual`, default `src/recomp_manual.c` (b3: `src/game/recomp/recomp_manual.c`) |
| `config/seed_functions.json`, `config/setup-pins.json` | required | |
| `scripts/` with `test_*.py` | required | at least `test_gitignore.py` (D4); the game's tools live here too |
| `openspec/config.yaml`, `openspec/specs/`, `openspec/changes/` | conditional | required with `[public]`, and exported scrubbed (Q4, decided). Without `[public]`, `doctor` gives a note: openspec is this workspace's workflow, not every CLI user's |
| `src/env/recomp_env_game.h` and its env doc | conditional | once the game has its own env keys (`[game] env_header`, `env_doc`); the doc is `docs/env.md` unless the game names another (b3: `docs/running.md`) |
| `config/spin_waits.json` | conditional | when `[pipeline] spin_waits` names it |
| `packaging/` | conditional | with `[package]`: the files `package` itself looks up for each `[package]` target (`launch.env.default.<family>`, `<target>/README.part`, the macOS `Info.plist.in` and launcher, `README.intro`, `config.default.toml` for a game with the enhancements layer), where the CLI's templates are the fallback. A file with a template fallback is not required. `layout.py` takes this list from the package module, so the two cannot drift |
| `.github/workflows/release-wizard.yml` | conditional | with `[wizard]`: the CLI's template, filled (D11) |
| `.github/workflows/checks.yml` | conditional | required with `[public]`: the CLI's template (D11; Q3, decided) |
| `docs/` | optional | `docs/images/*.png` are the only tracked images (README screenshots, the CLAUDE.md exception) |
| `CONTRIBUTING.md`, `CONTRIBUTORS.md`, `ROADMAP.md`, `NOTICE`, `TESTING.md` | optional | public documents. A `TESTING.md` that names private hosts is private (b3's), so it lives in `_local/` |
| the private set (D5) | known | `layout.py` knows these names, so they never count as undeclared extras |
| `analysis/` | untracked | the pipeline's `out`; a game's golden thresholds may be negated back in (cat's `analysis/golden/golden.json`, `audio.json`), never frames or audio |
| anything else at the top level | declared | `[layout] extra` (D2) |

**Naming.** The slug is the command, the bootstrap's name,
`pyproject`'s `[project] name` and the prefix of the wizard's assets
(`<slug>-wizard-*`). `[package] product` is the public repo's name,
`<something>-recomp` (`blinx2-recomp`, `burnout3-recomp`, `ssx3-recomp`,
`spartan-recomp`). Spartan's slug becomes `spartan` before its first
push (Q2, decided), so the slug reads as the game in public asset names.

**URLs.** `[public] url` is always the ssh form,
`git@github.com:<owner>/<repo>.git`. `[wizard] repo` is the https form,
`https://github.com/<owner>/<repo>`. Every comparison of two repo URLs
in the CLI normalises both to `<owner>/<repo>`, ignoring case, the
scheme (ssh, https, `ssh://`) and a trailing `.git`.

### D2. `[layout]`: upstream-inherited files and other extras

A game whose repo continues another project (b3 continues
`sp00nznet/burnout3`) keeps that project's files where the upstream has
them. Moving them would break upstream's own build path (`regen.sh`, MSVC
from `Setup.cmd`) and make every upstream PR diff a rename.

`[layout]` is optional and has two keys:
- `main`: the main C source, default `src/main.c`; b3 sets
  `src/game/main.c`.
- `extra = [...]`: the extra top-level entries a game tracks. `doctor`
  reports any other unknown top-level tracked name as a note:
  - b3: `regen.sh`, `Setup.cmd`, `tools`, `CONTRIBUTING.md`,
    `CONTRIBUTORS.md`, `ROADMAP.md`;
  - cat: `analysis`, `NOTICE`, `.claude`, `.python-version`. Its private
    notes need no entry (D1, "known").

The gen and manual source paths need no entry: they come from
`[pipeline]`.

**README sections** (in this order, each short; a game may add more):
1. what it is, and the "no game data here" notice;
2. progress: platforms and state;
3. playing: the wizard and the releases;
4. building from source with `./<slug>`;
5. credits and the licence.

The scaffold's README already has 1 and 4. `doctor` checks only that
`README.md` exists. The sections are guidance, written in each game's
conform task.

**CHANGELOG.md:** Keep a Changelog, with a `## [Unreleased]` section; a
release tag's section is the release notes (the workflow refuses a tag
without one).

### D3. The `.gitignore` baseline

The scaffold's `GITIGNORE` becomes the baseline, with these additions:
- `/wt/`: a worktree that lands in the tree by mistake is never
  committed. `doctor` still reports it (D12), so the ignore does not hide
  it.
- `_local/` and `runs/`: local notes, and A/B or probe output, which
  belong in the workspace's `runs/`.
- `*.bak` and `*.bak-*`: Spartan's tracked `game.toml.bak-20261016` is
  how a backup gets in.
- `*.pack`, `hud-pack.toml`, `*.xmv`, `*.rws`, `*.awd` and `CACHE/`: the
  game-data extensions b3's audit already refuses but the scaffold's
  ignore does not cover.
- `.claude/settings.local.json` and `CLAUDE.local.md`: per-user agent
  settings.

The game's own lines go below a marker comment,
`# --- this game ---`, so a later diff against the baseline is mechanical.
A game whose data folder or gen differs gets the baseline filled with its
own values, as the scaffold does with `@GAME_FILES@` and `@GEN@`.

**Worktrees never inside a game repo.** Every worktree lives in the
workspace's `wt/<name>/`, one per writing agent (CLAUDE.md). The
`.gitignore` line is a safety net, not a place: `doctor` lists every
`git worktree list` entry and every directory with a `.git` file or
directory under the repo root, and `public audit` refuses any gitlink
(mode 160000) in the tree.

### D4. Gates in every repo

`pyproject.toml` carries cat's `[tool.ruff]` (line-length 100, py39, the
same rules, extend-exclude naming gen, `external`, `third_party`,
`.venv*`, `analysis`, `build*`, `dist`, `_local`) and
`[tool.pytest.ini_options] testpaths = ["scripts"]`, so the CLAUDE.md
gates (`uv run pytest scripts`, `uv run ruff check . && uv run ruff format
--check .`) run the same way in every game.

`scripts/test_gitignore.py` (cat's, generalised: it reads `game.toml` for
the data folder and gen) is the one test every game has. It checks that
the dump, its `.partial`/`.old` siblings, gen, `dist/`, `/wt/` and the
data extensions are ignored, and that `game.toml` and `scripts/` are not.
The scaffold writes it.

### D5. The private set

These files are private working notes. They are never exported, and in
history mode (D8) never tracked:

| Pattern | What |
|---|---|
| `TASKS.md` | the running task list (cat) |
| `RESUME*.md`, `**/RESUME*.md` | resume notes, including inside openspec changes |
| `OPEN_QUESTIONS.md` | decision log |
| `WORKTREES.md` | worktree bookkeeping |
| `.git-blame-ignore-revs` | private-history shas: the export is a fresh commit |
| `_local/` | untracked local notes and scratch (gitignored) |

The CLI holds this list as the default `[public] exclude`. A game adds to
it and cannot remove from it. SSX 3 and Spartan keep their task state in
the tracker (Plane, BLX). They may add `TASKS.md` later; it stays private
the same way. The workspace's `notes/<topic>/` and `runs/` are outside
every repo and stay there: no game repo document cites them (the SSX 3
finding, tasks.md 2.3).

**Session names.** The orchestrator's session names (`xb-upstream`,
`ssx3-ec`, `xb-windows`, `xbox-recomp-e7`) are private workspace detail,
as in the toolkit's public rounds. They go in the private `rewrite` file
(D6), so the exported openspec says "the Burnout 3 session" and so on.
Tracker ids (`BLX-NNN`) may stay in the exported game repos. They never go
into upstream PRs (a separate rule).

**Excluded but not private:** game data, frames and bundles are never in
git at all. The export refuses them rather than dropping them (D7), so a
commit that tracks one is fixed at the source.

### D6. `[public]` in game.toml

```toml
[public]
# The public repository (ssh form, D1): export rounds land on its main.
url = "git@github.com:apexJCL/ssx3-recomp.git"
remote = "public"          # default "public"
branch = "main"            # default "main"
mode = "export"            # "export" (default) or "history" (D8)
author = "carlos <4037632+apexJCL@users.noreply.github.com>"
# Beyond the CLI's private set (D5); glob patterns on tracked paths.
exclude = []               # b3: [".claude/**", "CLAUDE.md", "TESTING.md"]
# Images and binaries allowed besides docs/images/*.png.
allow = []
# A fork's upstream ref. Commits reachable from it are already public
# (the upstream's own): the audit skips their text, messages and
# identities, and the export adds the upstream commit REF contains as a
# second parent (D7).
upstream = ""              # b3: "origin/main"
# Paths allowed only while they equal upstream's blob (b3's
# docs/screenshots/*).
upstream_files = []
```

Nothing private goes in `[public]`: the table is published with the tree.
The author is the noreply identity, which is public by design.

**Private inputs** are kept outside every repo, in the directory
`$XBR_PUBLIC_DIR`. For this workspace it points at `notes/public/`, so the
four games share them. The CLI refuses an `XBR_PUBLIC_DIR` inside the
game's work tree. The directory holds two files:
- `audit-private`: one extended regex per line, matched case-insensitively
  (the bench host's names, the personal email, the Windows PC's bench
  paths, the session names). The same format as today's
  `.git/info/audit-private`.
- `rewrite`: ordered rules, one per line (D7 step 4 has the semantics):
  - `regex<TAB>replacement`, in Python `re` syntax; groups are `\1`, not
    perl's `$1`;
  - `!fail <regex>`: a check, not a rule.

  cat's perl REWRITE list and its "awkward wording" check translate one
  to one.

**Lookup order** for the private patterns, in `public audit`,
`public export` and doctor: `$XBR_PUBLIC_DIR/audit-private`, then
`$XBR_AUDIT_PRIVATE`, then `<git dir>/info/audit-private`. That is the
CLI's own `scripts/audit-public.sh` order with `XBR_PUBLIC_DIR` put
first, so one file serves the CLI repo and the games. The `rewrite` file
is read only from `$XBR_PUBLIC_DIR`, or `<git dir>/info/xbr-public/` when
it is unset. A missing or empty `audit-private` (no line other than
comments and blanks) counts as missing, and then `public audit` and
`public export` refuse to run (exit 2), as both audit scripts do today.

### D7. `public export`

`<slug> public export [REF] [--tag TAG] [--message MSG]` builds the
public commit inside the private repo. It creates no throwaway clone and
writes no large files:

1. `git fetch <remote>`, then refuse unless `<remote>/<branch>` equals
   `git ls-remote <url> <branch>`. The new commit must be a fast-forward
   of what is really public.
2. List `REF`'s tree (default `HEAD`). Refuse when the working tree is
   dirty and REF is HEAD (`--allow-dirty` to override).
3. Drop the private set and `[public] exclude`. Then refuse (not drop)
   every path on the refusal list below. The fix belongs in the private
   commit.
4. Rewrite. A text blob is one with no NUL byte in its first 8000 bytes
   (git's own test). For each text blob that matches an `audit-private`
   pattern:
   - apply the `rewrite` rules in order, line by line, each line keeping
     its line ending;
   - write the result with `git hash-object -w`.

   Then, over every rewritten blob, refuse if an `audit-private` pattern
   still matches or a `!fail` rule matches. `!fail` regexes are
   case-insensitive. Tracked path names are checked against
   `audit-private` too; a path is never rewritten.
5. Build the tree with a temporary index (`GIT_INDEX_FILE`,
   `update-index --index-info`, `write-tree`). Commit it with
   `commit-tree` in a clean environment (`GIT_CONFIG_NOSYSTEM=1`,
   `GIT_CONFIG_GLOBAL=/dev/null`, and author and committer both set to
   `[public] author`):
   - the first parent is `<remote>/<branch>`, or none for an empty public
     repo;
   - with `[public] upstream` set, let `U = git merge-base REF <upstream>`,
     the newest upstream commit that REF contains. When `U` is not already
     an ancestor of the public tip, `U` becomes the second parent, so a
     fork stays level with the upstream it has merged on GitHub. An
     upstream commit that REF has not merged is never added;
   - the message is `[public] message`, default `<game name> static
     recompilation: <YYYY-MM-DD> round`, or `--message`.
6. If the tree equals the first parent's and no second parent is added,
   stop with "nothing to publish".
7. Point the local ref `refs/public/<branch>` at the commit. With
   `--tag TAG`, also create the annotated tag `refs/public-tags/TAG` on
   it, in the same clean environment, with `[public] author` as the
   tagger and the tag's `CHANGELOG.md` section as its message. Private
   tags never share a name with a public one. The one exception is b3's
   `v2026.10.0-rc.1`, made before this change, which exists under the
   same name in both repos. Tags already on the remote are not pushed
   again, and the audit skips them.
8. Append `<public sha> <REF sha> <date>` to `$XBR_PUBLIC_DIR/<slug>.map`.
9. Run `public audit` (D8) on the result, and print the summary (files,
   excluded, rewritten) and the push command:

   ```sh
   git push <remote> refs/public/<branch>:refs/heads/<branch> [refs/public-tags/TAG:refs/tags/TAG]
   ```

The push is never run by the CLI. CLAUDE.md's rules apply: the user's
standing go for push rounds, fast-forward only, and the audit first.

**The refusal list** (the CLI's default; refused at step 3 and by the
audit, and reported by doctor):
- data and bundle extensions, matched without case: `xbe`, `iso`, `xiso`,
  `bmp`, `png`, `wav`, `sav`, `pack`, `xpr`, `xwb`, `adx`, `sfd`, `ipk`,
  `xsv`, `xmv`, `rws`, `awd`, `ppm`, `raw` (b3's list), and `dmg`, `exe`,
  `pdb`, `nsi`, `tar`, `ico`, `icns` (cat's bundle list);
- `hud-pack.toml` at any depth;
- the paths `[data] game_files`, `[pipeline] gen` (and its `gen.*`
  siblings), `dist/`, `build*/`, `bin/`, `_local/`, `saves/`, `runs/`,
  `bench-logs/`;
- gitlinks (mode 160000).

The data-extension rule has the same exemptions as the audit (D8):
`docs/images/*.png`, `[public] allow`, and `[public] upstream_files`
while they equal upstream's blob. b3's `.claude/`, `CLAUDE.md` and
`TESTING.md` refusals are not in the default list, because cat publishes
`.claude/` (its openspec commands). They move to b3's `[public] exclude`.

### D8. `public audit` and the two modes

`<slug> public audit [RANGE | --all]` merges the CLI's audit script and
b3's, and reads its settings from `[public]`.

**What it checks.** The default range is `<remote>/<branch>..<tip>`, where
the tip is `refs/public/<branch>` in export mode and `<branch>` in
history mode.
- **The content diff.** `git diff <remote>/<branch> <tip>`, so the export
  commit, which may be a merge, is checked against its first parent. A
  merge shows no diff in `git log -p`, so the audit never relies on it.
  When `<remote>/<branch>` does not exist, the diff is against the empty
  tree. In history mode, each commit in `<range> ^<upstream>` is also
  checked against its first parent. Checked here:
  - the added lines for home-directory paths (macOS, Linux, an immutable
    host's `/var` home, Windows), links into the assistant's web app, and
    the `audit-private` patterns;
  - the added and changed paths: their names against `audit-private`;
    binaries and the refusal list, except `docs/images/*.png` (which must
    carry no text or Exif chunks), `[public] allow`, and
    `[public] upstream_files` while they equal upstream's blob.
- **Messages and identities** over `<range> ^<upstream>` (the whole range
  when `upstream` is empty). Upstream's own commits are already public
  and keep their identity. Each message is checked as the added lines
  are, and every author and committer must be `[public] author`.
- **Tags** that the push would add: each `refs/public-tags/*` tag not yet
  on the remote must have `[public] author` as tagger, and its message is
  checked as the added lines are.
- **The tip's tree**, for the refusal list and the private set.
- **The layout** (D12): any layout problem fails the audit.
- **The pins.** The tip's `[cli]` and `[toolkit]` tags must be in
  `git ls-remote <url>` of their public URLs and name the pinned commits.
  A public clone must be able to run `setup`. This is the Spartan
  finding.

**`--all`** means one thing per mode:
- export mode: audit a dry-run export of HEAD. That covers steps 2-4 of
  D7 (the tree, the rewrites, the refusals), the layout and the pins,
  with no ref moved. It never reads the private history's identities or
  messages, which export mode does not publish.
- history mode: every tracked file at HEAD, and every message and
  identity in `HEAD ^<upstream>`.

The exit codes are those of today's scripts: 1 on any hit, 2 when the
audit cannot check.

**The modes.**
- `mode = "export"` (default). The private history may use the local
  identity and may track the private set.
- `mode = "history"`: the private branch itself is pushed. Every commit
  must use the noreply identity. The private set must not be tracked. A
  leak in any intermediate commit blocks the push until that history is
  rewritten. `public export` refuses to run in this mode. No current game
  uses it (Q1).

### D9. `public init` and the push guard

`<slug> public init` makes the publish remote safe:
- It finds every remote whose fetch URL or push URL normalises (D1) to
  the same `<owner>/<repo>` as `[public] url`. It renames the first one
  to `[public] remote` and removes the others. With none, it adds the
  remote.
- It sets the remote's URL to `[public] url`. It replaces any `pushurl`,
  including the `DISABLED-no-push` placeholder (task 0.1), with that URL,
  since the guard now governs pushes.
- It sets `remote.<remote>.tagOpt = --no-tags`, so a fetch never mixes
  the public tags into the private ones.
- In export mode, it sets `remote.<remote>.push =
  refs/public/<branch>:refs/heads/<branch>`, so a bare `git push public`
  can only push the export.
- It installs a `pre-push` hook in `<git common dir>/hooks/` (untracked).
  The hook chains to an existing `pre-push`. In export mode, for a push
  whose URL normalises to the public repo (any form: ssh, https, with or
  without `.git`), it allows a ref update only when one of these holds:
  - the destination is `refs/heads/<branch>`, and the pushed sha equals
    `refs/public/<branch>`;
  - the destination is `refs/tags/*`, and the pushed sha is a
    `refs/public-tags/*` tag that peels to a commit reachable from
    `refs/public/<branch>`.

  It refuses everything else: other refs, raw shas, deletes (the zero
  sha), and any update to `refs/heads/<branch>` that is not a fast-forward
  of the remote sha.

**How each game migrates:**
- **cat** has no remote: `public init` adds `public`. The separate export
  clone is no longer needed. The transition and the equality check are
  in tasks.md 4.3. The REWRITE rules go to `notes/public/rewrite`, and
  the email check becomes an `audit-private` pattern.
- **b3** keeps the `public` remote. `origin` (upstream, push disabled)
  has another URL and is left alone. `scripts/audit-public.sh` and
  `scripts/test_audit_public.py` are removed once `burnout3 public audit`
  passes and fails on the same cases (the CLI's tests carry them, with a
  made-up host name).
- **SSX 3 and Spartan**: their `origin` is the public repo, with push
  disabled since 2026-10-17 (task 0.1). `public init` renames it to
  `public` and puts the guard in place of the placeholder.

### D10. b3: export, not direct push (Q1, decided by the user, 2026-10-17)

The b3-public-release D7 chose direct push so that the fork shows its
commit-by-commit delta to the upstream author. Since then:
- upstream PRs are cut from `origin/main` as few squashed topic commits
  (b3-upstream-prs; the memory notes on PR shape), not from the fork's
  `main`;
- The tracker item moved b3's openspec changes into b3. They held 43 audit hits
  before its scrub. In history mode, any such text in any commit blocks
  the push and needs a history rewrite.

| | export (chosen) | history (until now) |
|---|---|---|
| Public history | stays as it is (f7baab9). New work arrives as one commit per round. When REF contains upstream commits that the public tip does not, `git merge-base REF origin/main` is the second parent | every commit |
| Leak handling | one diff audited; rewrite rules apply; a fix is a new private commit | every commit audited; a leak in an old commit needs a rewrite and a force push |
| Private notes | may be tracked (D5) | never tracked |
| Identity | local identity allowed privately | noreply on every commit, or a filter-branch before each push |
| Upstream PRs | unchanged (cut from `origin/main`) | unchanged |
| GitHub fork view | "N commits ahead": the rounds and upstream merges | the full delta |

Export mode was chosen (the user, 2026-10-17): one mechanism across the
four games and no history rewrites. The cost is the per-commit public
view of future work. The tool still supports both modes, so the choice
is only a `[public] mode` value in b3's `game.toml`.

### D11. CI and release

- **`release-wizard.yml`:**
  - stays the CLI's template, filled with the slug;
  - cat's and b3's copies are brought up to it;
  - the new `<slug> workflow --check` (like `wrapper --check`) compares
    the file with the template, and `doctor` runs it;
  - the workflow runs in the public repo, on tags pushed there.
- **Release tags:** `vYYYY.MM.N` and `-rc.N` (first-release-meaning). A
  tag is made by `public export --tag` on the export commit and pushed
  with the round. The tag's `CHANGELOG.md` section is in the exported
  tree because `CHANGELOG.md` is never private.
- **`checks.yml`** (required for every game with `[public]`; Q3, decided
  by the user, 2026-10-17):
  - runs on push and pull request to `main`, on ubuntu-latest, with
    `permissions: contents: read`;
  - runs `uv sync --locked --group dev`, `uv run pytest scripts` and both
    ruff checks;
  - pins its Python in the template (`UV_PYTHON`, one version for every
    game, within the games' `requires-python`) and its actions by tag;
  - uses no game data and no toolkit clone, so it runs on the public tree
    as exported;
  - the scaffold writes it, and `workflow --check` compares it with the
    template like the release workflow.

### D12. Scaffold and doctor

- **`xbr new`** writes every required D1 entry except two kinds:
  - `LICENSE`, written only with `--license mit` (the owner chooses);
  - the entries `finish` writes once the network, git and uv are there
    (`CMakeLists.txt` and the C sources from the toolkit's template,
    `config/setup-pins.json`, `uv.lock`). Offline, `finish` lists them as
    "left to do".

  New in the scaffold:
  - `scripts/test_gitignore.py`, the ruff and pytest configuration in
    `pyproject.toml`;
  - `openspec/config.yaml` with empty `specs/` and `changes/`.
    `--no-openspec` skips it, for a game that will have no `[public]`;
  - `checks.yml` and the D3 `.gitignore`;
  - a commented `[public]` stub, and a `[wizard]` stub that names the
    https form of `[public]`'s URL.
- **`doctor`** gains a "layout" block, printed in text and in `--json`
  under its own `layout` key. It is separate from doctor's other checks:
  - it is never added to `PROBLEMS` or to the `--json` `problems` and
    `blockers`;
  - it never changes `next:` or doctor's exit status;
  - only `public audit` and `public export` fail on its problems.

  Problems:
  - a missing required entry;
  - in a game with `[public]`: a missing `checks.yml` or `openspec/`;
  - a baseline pattern that does not ignore its sample path
    (`git check-ignore --no-index`);
  - a tracked file under the refusal list;
  - a nested worktree or embedded repo;
  - the bootstrap or a workflow differing from its template;
  - in export mode, where a remote with `[public] url` exists: no push
    guard (hook, push refspec, `--no-tags`), or a `pushurl` that is not
    `[public] url`;
  - a set `core.hooksPath`, which would bypass the guard in
    `<git common dir>/hooks/`;
  - `[wizard] repo` that is not the same repo as `[public] url` (D1).

  Notes:
  - an absent `openspec/` in a game without `[public]`;
  - an unknown top-level name not in `[layout] extra` and not in the
    private set;
  - an env header without its doc row file.

### D13. Migration order

The work goes one session at a time (sequential work mode), each in its
own worktree under the workspace's `wt/`:

1. **CLI**, after the tracker item (`wizard-incremental-builds`) merges, because
   both change `manifest.py`, `scaffold.py` and the wizard docs: the
   `[public]` and `[layout]` tables, `public init|export|audit`, the
   doctor layout block, `workflow --check`, the scaffold additions, docs,
   tests (a made-up host name, never the real one), then a release. A
   CLI push round goes first so that the pin exists publicly.
2. **SSX 3** (ssx3-ec) and **Spartan** (xb-windows): conform, pin the new
   CLI, and fix the audit findings. Spartan also renames its slug to
   `spartan` (Q2). `public init` comes first of all, because their
   `origin` is the public repo (push disabled since task 0.1).
3. **cat** (orchestrator): conform, then one round through the CLI whose
   tree must equal `export-public.sh`'s for the same commit (tasks.md
   4.3); then remove the script.
4. **b3** (xb-upstream): conform, set `[public] mode = "export"` (Q1),
   and replace the audit script.
5. **First push round** for SSX 3 and Spartan:
   - order: the CLI, then each game;
   - each game: `public export` (with `--tag` when the round is a
     release), `public audit`, then the printed push;
   - then CLAUDE.md's "Public repos and legal" gains the two repos (a
     user or orchestrator edit; agents never edit CLAUDE.md), and
     `notes/untracked-projects.md` is retired.

## Risks

- **A rewrite rule that reads badly** in a new text, as cat's REWRITE has
  shown. The `!fail` rules carry over cat's doubled-article check, and the
  first CLI round's tree is diffed against the script's.
- **Patterns only one script knew.** cat's export checks only the bench
  host's name and the personal email, not the other private patterns that
  b3's audit reads. The Windows bench path reached the public
  `blinx2-recomp` tree that way (tasks.md 4.7). The shared
  `audit-private` (D6) closes the gap for every game.
- **The pre-push hook is per clone and untracked.** A fresh clone has no
  guard until `public init` runs. `doctor` reports it, and the
  `remote.<name>.push` refspec still covers a bare `git push public`.
- **A second parent from upstream** adds upstream commits to the public
  history. They are already public (upstream's own), and the audit skips
  their text, messages and identities through `[public] upstream`.
- **Spartan's toolkit pin** moves from a private integration commit to a
  public tag. That is a toolkit change for that game, so its Windows
  gates and a Proton run on the Deck both run on it.

## Decisions on the open questions (the user, 2026-10-17)

The user took the recommendation on all four questions.

- **Q1. b3 moves to export mode.** b3's `[public] mode` is `export`
  (D10). Its public history up to f7baab9 stays. Each round is one export
  commit on top of it, with the merged upstream commit as a second parent
  when there is one. The tool keeps `history` mode for a game that wants
  it, but no current game uses it.
- **Q2. Spartan's slug becomes `spartan` before the first push.** The
  full list and its effects on players are in tasks.md 3.2. It costs one
  commit now. After the push, players would see `tca-wizard-*` assets and
  a `./tca` command that does not name the game.
- **Q3. `checks.yml` is required for every public game**, so all four
  repos have it (D1, D11). It is free on public repos, holds no write
  token and needs no game data. It catches an export that drops a file
  the tests need.
- **Q4. `openspec/` stays public, scrubbed.** The specs are the project's
  design record. They go through the rewrite rules and the audit like any
  other file. A game can still list a path under `openspec/` in
  `[public] exclude`. For a game with `[public]`, a missing `openspec/` is
  a layout problem, not a note (D12).

## Open questions (follow-ups, not blocking)

- **A game's own data extensions.** The refusal list (D7) is the union of
  cat's and b3's lists. SSX 3 and Spartan may have their own data formats
  (for example EA's or Creative Assembly's archive extensions) that
  neither list names. Recommendation: a `[public] data_ext = [...]` key
  that adds to the default list and cannot remove from it, added when
  the first such format turns up in a game's survey. Until then, a game's
  `.gitignore` lines cover them.
