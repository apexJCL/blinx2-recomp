## 0. Leak window

- [x] 0.1 Close the plain-push leak window in SSX 3 and Spartan, whose `origin` is the public repo: `remote.origin.pushurl = DISABLED-no-push` in `ssx3/recomp` and `spartan/tca` (the orchestrator, 2026-10-17). `public init` later replaces the placeholder with the guarded `public` remote (D9)

## 1. CLI: layout and publishing (xboxrecomp-cli, own worktree off `main`, after the tracker item merges)

- [x] 1.1 `manifest.py`: the `[public]` table (D6: url, remote, branch, mode, author, exclude, allow, upstream, upstream_files, message) and `[layout]` (`main`, `extra`; D2), with unknown keys rejected as for every table; one URL normaliser (`<owner>/<repo>`, ignoring case, scheme and `.git`; D1); `docs/manifest.md` rows
- [x] 1.2 `layout.py`: the D1 table resolved through the manifest's paths, with the packaging files taken from the package module's own per-target lookups (template fallbacks not required); the private set (D5) as known names; the D3 baseline patterns with sample paths; the refusal list as D7 spells it, with its exemptions
- [x] 1.3 `public init` (D9): find remotes by normalised URL, rename or add `[public] remote`, replace any `pushurl` (including `DISABLED-no-push`), `tagOpt --no-tags`, the push refspec, and the chained `pre-push` guard (any URL form; pushed sha equals `refs/public/<branch>` or is a `refs/public-tags/*` tag peeling to a commit reachable from it; no deletes, raw shas or non-fast-forwards)
- [x] 1.4 `public export` (D7): `XBR_PUBLIC_DIR` (refused inside the work tree) and the D6 lookup order, an empty `audit-private` treated as missing; temporary index; text blobs by the NUL test; the D6 rule format applied to every text blob; `audit-private` and case-insensitive `!fail` over every exported blob; path names against `audit-private`; `commit-tree` in a clean environment; the second parent `git merge-base REF <upstream>` only when it is not an ancestor of the public tip; `refs/public/<branch>` moved only after the audit passes; `--tag` as an annotated tag in `refs/public-tags/` with `[public] author` as tagger; the sha map; the printed push command; refused in history mode
- [x] 1.5 `public audit` (D8): merge the CLI's `scripts/audit-public.sh` and b3's `scripts/audit-public.sh` checks. Content from `git diff <remote>/<branch> <tip>` (a merge's diff against its first parent); messages and identities over `<range> ^<upstream>`; taggers and messages of the tags the push adds; path names against `audit-private`; gitlinks, the layout and the public pins; `--all` per D8 (export mode: a dry-run export of HEAD, no private-history identities or messages); exit 1 on a hit, 2 when it cannot check
- [x] 1.6 `doctor`: the layout block (D12) in text and under its own `--json` key, never in `PROBLEMS`, `problems` or `blockers`, never changing `next:` or the exit status; the push-guard check only where a remote with `[public] url` exists; `core.hooksPath`; `workflow --check` for `release-wizard.yml` and `checks.yml`
- [x] 1.7 `xbr new`: `scripts/test_gitignore.py`, ruff and pytest config in `pyproject.toml`, `openspec/` (`--no-openspec` only without `[public]`), `--license mit`, `checks.yml`, the D3 `.gitignore`, the `[public]` and `[wizard]` stubs
- [x] 1.8 `templates/new-game/checks.yml` (D11; required for every game with `[public]`, Q3 decided), with its Python pinned (`UV_PYTHON`) and its actions pinned by commit sha (tag in a comment); doctor reports a public game without it or without `openspec/` (Q4 decided)
- [x] 1.9 Tests, with a made-up host name in every fixture, never the real one:
  - each check with a hit and a clean case;
  - export round trips: empty public repo, existing tip, upstream second parent (REF has merged upstream, and REF has not), nothing to publish;
  - rewrite per line: line endings kept, `\1` groups, `!fail` case-insensitive, a binary blob (NUL in the first 8000 bytes) untouched;
  - the audit of an export merge commit that adds a private-pattern line fails;
  - tags: the tagger is `[public] author`; a tag with another tagger, or a private pattern in its message, fails the audit;
  - the hook: refuses a push of `main` over the https URL, a raw sha, a delete and a non-fast-forward; allows the export ref and a public tag;
  - the pins check against a `file://` remote (tag present, tag missing, tag naming another commit);
  - `doctor --json` problems and blockers, `next:` and the exit status unchanged by layout problems
- [x] 1.10 Docs: `docs/layout.md` (new), `docs/commands.md`, `docs/maintainers.md` (`XBR_PUBLIC_DIR`, its relation to `XBR_AUDIT_PRIVATE` and `.git/info/audit-private`, the rewrite file format)
- [ ] 1.11 Gates: `uv run pytest tests`, ruff check and format; release tag; review; the CLI push round (noreply identity, `scripts/audit-public.sh`)
- [x] 1.12 Workspace: create `notes/public/` with:
  - `audit-private`: the patterns of today's two `info/audit-private` files and the session names;
  - `rewrite`: cat's REWRITE rules translated to Python `re` (`$1` to `\1`); its email and wording checks as patterns and `!fail` lines; each session name rewritten to its game's session (D5).

  - [ ] After the merge (the orchestrator): point `XBR_PUBLIC_DIR` at it in each session's environment.

## 2. SSX 3 (the SSX 3 session, worktree off `ssx3/recomp` `main`)

- [ ] 2.1 `ssx3 public init` first: it renames `origin` (the public repo, push disabled by 0.1) to `public` and replaces the placeholder `pushurl` with the guard
- [ ] 2.2 `game.toml`: replace the `[wizard]` comment block (it says "this repo is not published") with `[wizard] repo = "https://github.com/apexJCL/ssx3-recomp"` and an own `[[wizard.credit]]`; add `[public]`
- [ ] 2.3 Audit finding: `openspec/changes/ssx3-bringup/design.md:23` cites the workspace's `runs/ssx3/saves/`; describe the save location without the workspace path
- [ ] 2.4 `[cli]`: add the tag (the pin has only the commit), moving to the 1.11 release
- [ ] 2.5 Baseline: `.gitignore` (D3), ruff and pytest config, `scripts/test_gitignore.py`, `openspec/config.yaml`, `openspec/specs/`, `.github/workflows/checks.yml`
- [ ] 2.6 README sections (D2); `CHANGELOG.md` `[Unreleased]`
- [ ] 2.7 Gates: `ssx3 doctor` with no layout problem; `uv run pytest scripts`; ruff; `ssx3 public audit --all`, which in export mode audits a dry-run export of HEAD (tree, rewrites, refusals, layout, pins; no ref moved, no push); review

## 3. Spartan (the Spartan session, worktree off `spartan/tca` `main`)

- [ ] 3.1 `public init` first: as 2.1, for `apexJCL/spartan-recomp`
- [ ] 3.2 Rename the slug `tca` to `spartan` before the first push (Q2, decided by the user, 2026-10-17).
  - In the repo:
    - the bootstrap trio (`spartan`, `spartan.cmd`, `spartan.py`);
    - `[game] slug`, `exe = "spartan_recomp"` and the `game.toml` comments that name `tca`;
    - CMake `project(spartan_recomp C)`;
    - `.gitattributes` (the wrapper's `eol=lf` line), `README.md`, the `pyproject.toml` name and comments, the `.gitignore` comments, and the `tca-old/` line if nothing uses it;
    - re-lock `uv.lock`, and update the `config/setup-pins.json` `_comment`;
    - rename the `.tca-pin` marker to `.spartan-pin`.
  - Outside the repo: delete the old `build-win/tca_recomp.exe` build trees. The checkout stays at `spartan/tca` locally. The PC's bench paths and the workspace notes are renamed there, not in the repo.
  - Effects for players and testers, recorded in `CHANGELOG.md` and the test notes:
    - `TCA_ROOT` becomes `SPARTAN_ROOT`;
    - the wizard assets become `spartan-wizard-*`, with the app id `io.github.apexjcl.spartan-wizard`;
    - the wizard's settings move from `tca-wizard` to `spartan-wizard`, and its default root from `tca-recomp` to `spartan-recomp`, so testers pick the dump and the root again;
    - saves do not move, because `[package] app` (`SpartanTotalWarrior`) is unchanged.
- [ ] 3.3 Untrack `game.toml.bak-20261016` (`git rm --cached`; the D3 `*.bak-*` line keeps the next one out)
- [ ] 3.4 `game.toml`: replace `[wizard] private = true` (an unknown key on its v0.7.6 pin) with `repo = "https://github.com/apexJCL/spartan-recomp"`; add `[package] product = "spartan-recomp"`; add `[public]`
- [ ] 3.5 Toolkit pin: move from commit 70c4371 on `posix-host/portability` (not on the public fork) to a public tag (blinx2-v0.5.0 or later). Run the game's Windows gates on it, plus a Proton run on the Deck
- [ ] 3.6 Add `CHANGELOG.md`, `.github/workflows/release-wizard.yml` (the template), `.github/workflows/checks.yml`, `openspec/`, ruff and pytest config, `scripts/test_gitignore.py`; the D3 `.gitignore` with `build-pkg-*/` under the game's marker
- [ ] 3.7 Gates as 2.7 (`spartan public audit --all` on a dry-run export of HEAD)

## 4. cat (orchestrator, worktree off `cat` `main`)

- [x] 4.1 `[public]` (url `git@github.com:apexJCL/blinx2-recomp.git`, export mode); `blinx2 public init`. Done: the remote `public` (push only `refs/public/main:refs/heads/main`, no tags) and the pre-push guard; there was no remote and no hook before
- [x] 4.2 `[layout] extra`: `analysis`, `NOTICE`, `.claude`, `.python-version`
- [x] 4.3 Transition from `scripts/export-public.sh`:
  - while both exist, `[public] exclude` lists `scripts/export-public.sh` and `scripts/test_export_public.py`, as the script excludes itself;
  - for one commit A, compare the tree of the script's export (B) with the CLI export's. They are equal when `git rev-parse A^{tree}` and `git rev-parse B^{tree}` match. A difference is acceptable only when it is a line the script missed that a rewrite rule or a source fix now covers, for example the 4.7 lines;
  - then remove both scripts and their two exclude entries, and add the separate export clone to the cleanup list
  - Done: for the same commit the trees differ in 12 openspec files and one file. The 12 are only the lines a rule now covers: the Windows bench path (4.7) and each session name rewritten to its game's session (D5). The one file is `analysis/enhancements/hor-plus.md`: tracked under the ignored `analysis/*`, so the script, which rebuilt the tree with `git add`, never published it, and the CLI, which reads the tracked tree, would. The user chose to publish it (2026-10-18): `.gitignore` un-ignores it, the rules' rewrites in it read cleanly, and `scripts/test_public_exclude.py` fails on any other tracked file on an ignored path that no `[public] exclude` glob names. Both scripts are removed; `docs/packaging.md` and the packaging spec name `blinx2 public export`. Before that, the CLI audit refused home-path examples and Claude chat links in the specs, so a source commit gives them generic wording
- [x] 4.4 `.gitignore` to the baseline (adds `/wt/`, `_local/`, `runs/`, `*.bak*`, `*.xmv`, `*.rws`, `*.awd`). The empty `wt/upstream-sync/` directory: check that it is empty and holds no git data, then hand its removal to the user as a one-line `!` command. `notes/cleanup-derived.py` refuses paths inside a main checkout
- [x] 4.5 `release-wizard.yml` to the template, and add `checks.yml` (`blinx2 workflow --check`)
- [ ] 4.6 Gates: cat's usual set; review
- [x] 4.7 Public finding (read-only check, 2026-10-17). The public `blinx2-recomp` tip 7f8c515 carries 27 lines with the Windows bench path:
  - 14 in `openspec/changes/{build-wizard,occ-reports,wizard-build-feedback,wizard-test-notes}`, archived since in cat as `archive/2026-10-17-*`;
  - 13 in `openspec/changes/{b3-public-release,b3-upstream-prs}`.

  cat's export script does not check that pattern (the D8 risk). The next round, through the CLI with the shared `audit-private`, rewrites or refuses them. The public history keeps them unless the user approves a rewrite. That is the user's call, and nothing was pushed or changed publicly.

  Done: the CLI export tree for this branch's tip holds none of those lines (the old script's tree for the same commit held 15). The user approved rewriting the public history to drop all 27 (2026-10-18); the orchestrator does it in the next push round through the CLI export, as a fresh root rather than a fast-forward onto 7f8c515. `public export` cannot make a fresh root yet (it always parents on the fetched public tip) and the pre-push guard refuses a non-fast-forward, so that round needs a CLI flag first (the hand-back says which)

## 5. b3 (the Burnout 3 session, worktree off `b3` `main`)

- [ ] 5.1 `[public]`:
  - `mode = "export"` (Q1, decided by the user, 2026-10-17);
  - `url = "git@github.com:apexJCL/burnout3-recomp.git"`, `remote = "public"`;
  - `upstream = "origin/main"`, `upstream_files = ["docs/screenshots/*"]`;
  - `exclude = [".claude/**", "CLAUDE.md", "TESTING.md"]` (D7: no longer in the CLI's default refusals).

  Then run `burnout3 public init`. It leaves `origin` (upstream, push disabled) alone and sets `--no-tags` on `public`. The existing `v2026.10.0-rc.1` is the one tag name shared by the private and public repos
- [ ] 5.2 Replace `scripts/audit-public.sh` and `scripts/test_audit_public.py` with `burnout3 public audit`, once the CLI tests cover the same cases; move `.git/info/audit-private` to `notes/public/audit-private`
- [ ] 5.3 `[layout]`: `main = "src/game/main.c"`; `extra`: `regen.sh`, `Setup.cmd`, `tools`, `CONTRIBUTING.md`, `CONTRIBUTORS.md`, `ROADMAP.md`
- [ ] 5.4 The nested worktree `b3/wt/apulife/b3` (detached 56574b4):
  - check it read-only: a clean `git status`, and 56574b4 reachable from a branch (or kept on a new branch);
  - then hand its removal (or `git worktree move` to the workspace's `wt/`) to the user as a one-line `!` command. `notes/cleanup-derived.py` refuses paths inside a main checkout
- [ ] 5.5 Baseline:
  - `.gitignore` to the baseline under b3's own lines (`/wt/` included);
  - `scripts/test_gitignore.py`, with pytest `testpaths = ["scripts"]` in `pyproject.toml`;
  - `release-wizard.yml` to the template, and add `checks.yml`;
  - the `[cli]` pin to the 1.11 release;
  - `TESTING.md` moves to `_local/`
- [ ] 5.6 Gates: b3's usual set, `burnout3 public audit` over the next round; review

## 6. First push round (SSX 3 and Spartan)

- [ ] 6.1 The CLI round, if 1.11 has not pushed it yet, so the pins exist publicly
- [ ] 6.2 Per game: `<slug> public export` (root commit on the empty public repo; `--tag` when the round is a release), `<slug> public audit`, then the printed push; check `git log --format='%ae %ce'` on the public ref shows only the noreply address
- [ ] 6.3 Check that a public clone of each runs `./<slug> setup` far enough to fetch the pinned CLI and toolkit (no game data needed)
- [ ] 6.4 Hand the CLAUDE.md "Public repos and legal" rows for `apexJCL/ssx3-recomp` and `apexJCL/spartan-recomp` and b3's mode to the orchestrator or the user (agents never edit CLAUDE.md); retire `notes/untracked-projects.md`

## 7. Follow-ups outside this change

- [ ] 7.1 `wizard-incremental-builds` (is running on it; not edited here): its D15 and tasks 9.6 and 9.7 assume SSX 3 and Spartan stay private and build their wizards through `[wizard] private`. Once the tracker item merges, update them to the public `[wizard] repo` and keep `private` only for a game with no public repo
- [ ] 7.2 Commit messages a70e0ac and d8bd99f in `ssx3/recomp` cite the workspace's `runs/`. Export mode never publishes private messages, so there is nothing to rewrite
- [ ] 7.3 After each game's migration, its CLAUDE.md row names `<slug> public export` instead of `export-public.sh` or the direct push (orchestrator or user edit)
- [ ] 7.4 A game-specific data-extension key (`[public] data_ext`, design.md open questions), when SSX 3's or Spartan's survey finds a format the default list misses
