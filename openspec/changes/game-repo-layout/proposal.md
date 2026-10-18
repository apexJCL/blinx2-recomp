## Why

The user (2026-10-17) wants every supported game to end up with the same
repo structure: BLiNX 2 (`cat`), Burnout 3 (`b3`), SSX 3 (`ssx3/recomp`)
and Spartan: Total Warrior (`spartan/tca`). SSX 3 and Spartan now have
public, empty repos (`apexJCL/ssx3-recomp`, `apexJCL/spartan-recomp`). The
user chose to publish them as `blinx2-recomp` is published: the private
history stays local, and each push round is one export commit (scrubbed,
private notes left out) on the public `main`, with the noreply identity,
after an audit. The first push comes only after this layout lands.

Today the four repos have drifted apart (design.md, Survey):
- **Two publish mechanisms, both copied per game.** cat has
  `scripts/export-public.sh`: its exclusions and its host-name rewrite
  rules are in the script, so the script itself must stay private. b3
  pushes `main` straight to `apexJCL/burnout3-recomp` and checks the push
  with `scripts/audit-public.sh`, a copy of the CLI's audit. SSX 3 and
  Spartan have neither, and their `origin` remote is the public repo, so a
  plain `git push` would have published the private history. That window
  is closed: both now have `pushurl = DISABLED-no-push` (2026-10-17,
  tasks.md 0.1).
- **Four different `.gitignore` files.** None of them ignores a nested
  worktree. One sits in `b3/wt/apulife/` (`?? wt/` in b3's status). Spartan
  tracks `game.toml.bak-20261016`.
- **Gates differ.** cat has 12 `scripts/test_*.py` and a ruff
  configuration. b3 has 2 tests and ruff. SSX 3 and Spartan have neither.
- **`[wizard]` assumes SSX 3 and Spartan are private.** SSX 3's table is
  commented out with "this repo is not published". Spartan sets
  `private = true`, a key its pinned CLI (v0.7.6) does not know yet.
  Spartan's toolkit pin is a commit on `posix-host/portability`, which the
  public toolkit fork does not carry, so a public clone could not run
  `setup`.
- **Docs and the release workflow differ.** Spartan has no `CHANGELOG.md`,
  no release workflow and no `openspec/`. cat's and b3's
  `release-wizard.yml` are older than the CLI's template.

## What Changes

- **A standard game repo layout**, written down once (design.md D1-D4):
  - which files and directories are required, which are optional, and
    how they are named;
  - which deviations a game may declare in `game.toml` (`[layout]`, for
    files inherited from an upstream such as b3's `regen.sh`);
  - one `.gitignore` baseline;
  - no worktree or embedded repo ever inside a game repo.
- **One private set.** A fixed list of private working-note files
  (`TASKS.md`, `RESUME*.md`, `OPEN_QUESTIONS.md`, `WORKTREES.md`,
  `.git-blame-ignore-revs`) and the untracked `_local/`. None of them is
  ever published (D5).
- **One shared publish mechanism in the CLI**, driven by a new
  `[public]` table in `game.toml`, replacing the copied scripts (D6-D9):
  - `<slug> public init` sets up the `public` remote and a push guard
    that matches the public repo in any URL form and lets through only
    the export commit and its tags, as fast-forwards;
  - `<slug> public export` builds the scrubbed tree and commits it as one
    squash commit on the public tip, into a local ref, with upstream's
    merge base as a second parent when a fork has merged upstream;
  - `<slug> public audit` checks what the push would publish: the export
    commit's diff against the public tip (so a merge is audited too), its
    message, identity and tags, the layout and the public pins.
  The private patterns and the rewrite rules live outside every repo.
  The push itself stays a printed, manual `git push`.
- **b3 moves to export mode** (D10; Q1, decided by the user, 2026-10-17). Its
  already-public history stays as it is. Each new round goes on top of it,
  with upstream's tip as a second parent when b3 has merged upstream. A
  `history` mode remains for a game that keeps pushing its commits as
  they are.
- **`[wizard] repo` names the public repo** for SSX 3 and Spartan,
  replacing `private = true` (D6, D12, D13).
- **The CI and release shape** (D11): the release workflow stays the
  CLI's template, byte for byte, checked by doctor. A `checks` workflow,
  required for every public game (Q3, decided), runs the game's pytest
  and ruff gates. Release tags are
  made on the export commit in the public repo.
- **The scaffold writes the layout and `doctor` checks it** (D12):
  - `xbr new` writes the whole required set;
  - `doctor` gains a separate layout block (required files, `.gitignore`
    coverage, tracked game data, nested worktrees, the wrapper and the
    workflow against their templates, the push guard). It never changes
    doctor's problems, `next:` or exit status;
  - `public audit` and `public export` refuse to pass on any layout
    problem.
- **Spartan's slug becomes `spartan`** before its first push (Q2, decided).
  `openspec/` stays public in every game, scrubbed by the export (Q4,
  decided).
- **A phased migration** (D13, tasks.md). The CLI goes first, after
  the tracker item merges. Then each
  game's owning session conforms its own repo: the orchestrator for cat,
  xb-upstream for b3, ssx3-ec for SSX 3, xb-windows for Spartan. The
  first-push round for SSX 3 and Spartan comes last.

## Capabilities

### New Capabilities

- `game-repo-layout`: the standard tree of a game repo; the private set;
  the `.gitignore` baseline; no nested worktrees; the scaffold writes it
  and `doctor` checks it.
- `public-export`: publishing a game repo through `[public]`:
  - `public init`, `public export` and `public audit`;
  - the export and history modes;
  - private patterns and rewrite rules kept outside the repo;
  - the noreply identity;
  - the push guard.

### Modified Capabilities

None in `openspec/specs/`. The manifest schema (`cli-extraction`'s
`game-manifest`, not yet archived) gains `[public]` and `[layout]`. The
CLI's `docs/manifest.md` documents them.

## Impact

- **xboxrecomp-cli** (public, noreply identity):
  - new `public.py` and `layout.py`;
  - `manifest.py` gains `[public]` and `[layout]`;
  - `doctor.py` gains the layout section;
  - `scaffold.py` and `templates/new-game/` write the baseline and the
    `checks.yml`;
  - docs: `docs/manifest.md`, `docs/commands.md`, `docs/maintainers.md`,
    and a new `docs/layout.md`.
  - A release, so the games can pin it.
- **cat**: `[public]` and `[layout]`. `scripts/export-public.sh` and
  `scripts/test_export_public.py` are removed once one round through the
  CLI gives the same tree. The REWRITE rules move to the private rules
  file. The `.gitignore` and the workflow are brought up to the baseline.
- **b3**: `[public]` in export mode (Q1, decided). `scripts/audit-public.sh`
  and its test are replaced. `[layout] extra` covers upstream's files. The
  `b3/wt/apulife` worktree moves out of the repo.
- **SSX 3, Spartan**: the full baseline, `checks.yml` included; `[public]`
  and `[wizard] repo`; the remote made safe; the audit findings fixed;
  Spartan's toolkit pin moved to a public tag, and its slug renamed, which
  testers see as a new wizard name, settings folder and default root
  (tasks.md 3.2).
- **Not touched by this change**: `wizard-incremental-builds` (is
  running on it). Its D15 and tasks 9.6 and 9.7 assume private games, so
  they are a follow-up (tasks.md 7.1).
- **No game data, ISOs, frames, captures or saves** go anywhere. The
  export and the audit refuse them by path and by extension.
- **Hosts and backends**: this change is repo structure, CLI tooling and
  publishing, with no runtime, renderer, audio or kernel code. The one
  exception is Spartan's toolkit pin move (tasks.md 3.5): it changes the
  toolkit the game builds against, so it runs the game's Windows gates
  plus a Proton run on the Deck. Otherwise there are no Proton runs or
  goldens beyond each game's normal gates.
