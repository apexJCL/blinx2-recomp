## ADDED Requirements

### Requirement: The public table
A published game SHALL have a `[public]` table in `game.toml` with `url` and `author`, and optionally `remote`, `branch`, `mode` (`export` by default, or `history`), `exclude`, `allow`, `upstream`, `upstream_files` and `message`. The table SHALL hold nothing private. Repo URLs SHALL be compared after normalising them to `<owner>/<repo>`, ignoring case, the scheme (ssh or https) and a trailing `.git`.

#### Scenario: Defaults
- **WHEN** `[public]` sets only `url` and `author`
- **THEN** the remote is `public`, the branch is `main` and the mode is `export`

#### Scenario: Unknown key
- **WHEN** `[public]` contains a key the CLI does not know
- **THEN** loading the manifest fails and names the key

### Requirement: The private set is never published
`TASKS.md`, `RESUME*.md` at any depth, `OPEN_QUESTIONS.md`, `WORKTREES.md`, `.git-blame-ignore-revs` and `_local/` SHALL never appear in an exported tree. `[public] exclude` SHALL add to this set and SHALL NOT remove from it. In history mode these files SHALL NOT be tracked.

#### Scenario: Export drops private notes
- **WHEN** a game tracks `TASKS.md` and `openspec/changes/x/RESUME.md` and runs `public export`
- **THEN** neither file is in the exported tree

#### Scenario: History mode with a private file
- **WHEN** a game in history mode tracks `TASKS.md`
- **THEN** `public audit` fails and names it

### Requirement: Private inputs live outside the repo
The private patterns (`audit-private`) SHALL be read from `$XBR_PUBLIC_DIR/audit-private`, then `$XBR_AUDIT_PRIVATE`, then `<git dir>/info/audit-private`, and never from a tracked file. The rewrite rules (`rewrite`) SHALL be read from `$XBR_PUBLIC_DIR`, or `<git dir>/info/xbr-public/` when it is unset. The CLI SHALL refuse an `XBR_PUBLIC_DIR` inside the game's work tree. A missing `audit-private`, or one with no line other than comments and blanks, SHALL make `public export` and `public audit` refuse to run.

#### Scenario: No private pattern file
- **WHEN** no `audit-private` exists in the lookup order
- **THEN** `public audit` exits 2 and says where it looked

#### Scenario: An empty pattern file
- **WHEN** `$XBR_PUBLIC_DIR/audit-private` holds only comments
- **THEN** `public audit` and `public export` exit 2, as for a missing file

#### Scenario: Private dir inside the repo
- **WHEN** `XBR_PUBLIC_DIR` points at a directory inside the game's work tree
- **THEN** `public export` refuses to run and names the variable

### Requirement: Export builds one commit on the public tip
`<slug> public export [REF]` SHALL build REF's tree without the private set and the exclusions, apply the rewrite rules, and commit it with `commit-tree` in a clean environment into `refs/public/<branch>`. The first parent SHALL be `<remote>/<branch>` after a fetch that matches `ls-remote` (none for an empty public repo). With `[public] upstream` set, `U = git merge-base REF <upstream>` SHALL be a second parent when `U` is not already an ancestor of the public tip; an upstream commit that REF has not merged SHALL never be added. Author and committer SHALL be `[public] author`. The CLI SHALL NOT push; it SHALL print the push command.

#### Scenario: First round on an empty public repo
- **WHEN** the public repo has no `main` and `public export` runs
- **THEN** `refs/public/main` is a root commit by the noreply identity, and the printed command pushes it to `refs/heads/main`

#### Scenario: Stale remote-tracking ref
- **WHEN** `<remote>/main` differs from what `ls-remote` reports
- **THEN** export refuses, so the result is a fast-forward of the real public tip

#### Scenario: A fork merged upstream
- **WHEN** b3's REF contains `origin/main` commits that `public/main` does not
- **THEN** the export commit has `public/main` as first parent and `git merge-base REF origin/main` as second parent

#### Scenario: Upstream moved but the fork has not merged it
- **WHEN** `origin/main` has commits that REF does not contain, and REF contains none that `public/main` lacks
- **THEN** the export commit has no second parent

#### Scenario: Nothing changed
- **WHEN** the filtered tree equals the public tip's tree and no second parent is added
- **THEN** export prints "nothing to publish" and creates no commit

### Requirement: Rewrite semantics
A text blob SHALL be one with no NUL byte in its first 8000 bytes; other blobs SHALL NOT be rewritten. The `rewrite` rules (`regex<TAB>replacement`, Python `re`, groups written `\1`) SHALL apply in order to each line of a text blob that matches an `audit-private` pattern, keeping each line's ending. `!fail <regex>` lines SHALL be matched case-insensitively against the rewritten blobs.

#### Scenario: Line endings kept
- **WHEN** a CRLF file has a line that a rule rewrites
- **THEN** the rewritten line keeps its CRLF and no other line changes

#### Scenario: A fail rule
- **WHEN** a rewritten blob matches a `!fail` regex in another case than the rule's
- **THEN** export exits non-zero, names the path and line, and moves no ref

### Requirement: Export refuses data and leaks
Export SHALL refuse, not drop, any path on the CLI's refusal list: the data and bundle extensions (`xbe`, `iso`, `xiso`, `bmp`, `png`, `wav`, `sav`, `pack`, `xpr`, `xwb`, `adx`, `sfd`, `ipk`, `xsv`, `xmv`, `rws`, `awd`, `ppm`, `raw`, `dmg`, `exe`, `pdb`, `nsi`, `tar`, `ico`, `icns`, without case), `hud-pack.toml` at any depth, `[data] game_files`, gen and its `gen.*` siblings, `dist/`, `build*/`, `bin/`, `_local/`, `saves/`, `runs/`, `bench-logs/`, and gitlinks. The extension rule SHALL exempt `docs/images/*.png`, `[public] allow`, and `[public] upstream_files` while they equal upstream's blob. After the rewrite it SHALL refuse when any `audit-private` pattern still matches a blob or a tracked path name.

#### Scenario: A host name survives the rewrite
- **WHEN** a blob still matches an `audit-private` pattern after the rules run
- **THEN** export exits non-zero, names the path and line, and moves no ref

#### Scenario: An exempt image
- **WHEN** the tree has `docs/images/compare.png` and `docs/screenshots/a.png` listed in `upstream_files` and equal to upstream's blob
- **THEN** export does not refuse either file

#### Scenario: Agent files are a game's own exclusion
- **WHEN** b3 tracks `CLAUDE.md` and `.claude/` and lists them in `[public] exclude`
- **THEN** export drops them, and a game that does not list `.claude/` publishes it

### Requirement: Public tags
`public export --tag TAG` SHALL create the annotated tag `refs/public-tags/TAG` on the export commit, in the same clean environment, with `[public] author` as the tagger and the tag's `CHANGELOG.md` section as its message.

#### Scenario: A release round
- **WHEN** `public export --tag v2026.11.0` runs
- **THEN** `refs/public-tags/v2026.11.0` is an annotated tag by `[public] author` on `refs/public/main`, and the printed push command includes it

### Requirement: Audit checks what would be published
`<slug> public audit [RANGE | --all]` SHALL check the default range `<remote>/<branch>..<tip>`, where the tip is `refs/public/<branch>` in export mode and `<branch>` in history mode:
- the content of `git diff <remote>/<branch> <tip>` (the empty tree when the remote branch does not exist), so a merge commit is checked against its first parent; in history mode each commit of `<range> ^<upstream>` against its first parent too. Added lines SHALL be checked for home-directory paths, links into the assistant's web app and the private patterns; added and changed paths for private patterns in their names, binaries and the refusal list, with the export's exemptions and `docs/images/*.png` free of text or Exif chunks;
- the messages and the authors and committers of `<range> ^<upstream>` (the whole range without `upstream`), which must be `[public] author`;
- the tagger (`[public] author`) and the message of each `refs/public-tags/*` tag the push would add;
- the tip's tree for the refusal list and the private set, the layout, and that the `[cli]` and `[toolkit]` tags exist on their public URLs and name the pinned commits.

`--all` SHALL mean, in export mode, a dry-run export of HEAD (the tree, the rewrites, the refusals, the layout and the pins, with no ref moved and no private-history identity or message read), and in history mode every tracked file at HEAD with every message and identity of `HEAD ^<upstream>`. It SHALL exit 1 on a hit and 2 when it cannot check.

#### Scenario: A leak in the export merge
- **WHEN** the export commit has a second parent and adds a line matching an `audit-private` pattern
- **THEN** the audit fails and names the path and line, although `git log -p` shows no diff for the merge

#### Scenario: A pin that is not public
- **WHEN** `[toolkit]` pins a commit on a branch the public toolkit fork does not carry, with no public tag
- **THEN** the audit fails and says a public clone could not run `setup`

#### Scenario: Wrong identity
- **WHEN** a commit in the range has the local identity as author
- **THEN** the audit fails and names the commit

#### Scenario: Wrong tagger
- **WHEN** a `refs/public-tags/*` tag not yet on the remote has the local identity as tagger
- **THEN** the audit fails and names the tag

#### Scenario: Export mode, all
- **WHEN** `public audit --all` runs in an export-mode game whose private history uses the local identity
- **THEN** the audit checks a dry-run export of HEAD and reports no identity hit

### Requirement: The push guard
`<slug> public init` SHALL find every remote whose fetch or push URL normalises to the same `<owner>/<repo>` as `[public] url`, rename the first to `[public] remote` (or add it), and remove the others. It SHALL set the URL, replace any `pushurl` (including `DISABLED-no-push`), and set `tagOpt = --no-tags`. In export mode it SHALL set the push refspec to `refs/public/<branch>:refs/heads/<branch>` and install a chained `pre-push` hook. For a push to any URL form of the public repo, the hook SHALL allow only `refs/heads/<branch>` with the sha of `refs/public/<branch>` as a fast-forward of the remote sha, and `refs/tags/*` with a `refs/public-tags/*` tag that peels to a commit reachable from `refs/public/<branch>`; it SHALL refuse every other ref, raw shas, deletes and non-fast-forwards. Doctor SHALL report a missing guard where a remote with `[public] url` exists.

#### Scenario: A plain push of main
- **WHEN** a user runs `git push public main` in an export-mode game
- **THEN** the hook refuses the push

#### Scenario: A push over the https URL
- **WHEN** a user runs `git push https://github.com/<owner>/<repo> main` naming the public repo
- **THEN** the hook refuses the push, as for the ssh remote

#### Scenario: A raw sha
- **WHEN** a user pushes a commit sha other than `refs/public/main`'s to `refs/heads/main` of the public repo
- **THEN** the hook refuses the push

#### Scenario: A delete
- **WHEN** a user runs `git push public :main`
- **THEN** the hook refuses the push

#### Scenario: Origin is the public repo
- **WHEN** `origin` points at the public URL with `pushurl = DISABLED-no-push` before `public init`
- **THEN** after `public init` only the `public` remote has that URL, its push URL is the public URL, and fetches from it bring no tags
