# Design: benchdb-merged-worktrees

Code: `xboxrecomp-cli/src/xboxrecomp_cli/benchdb/clean.py` (`Planner.merged`,
`merged_checkout`, `live_tree`, `integration`, `history`, `remove_local`)
and `config.py` (`[clean.integration]`). Tests:
`tests/test_benchdb_merged.py`.

## D1. Merged, decided conservatively

A dir under the worktrees root is merged when the tracker states were read,
the process list was read, and every checkout in it passes all of the
rules below. The checkouts are the ones guard 4's walk finds (`scan`): each
`.git` under the dir, and each checkout nested in an untracked or ignored
dir of one (`!! scratch/`), so guard 4 and this rule judge the same list.

1. It is a linked worktree (its `.git` file names a
   `<main>/.git/worktrees/<id>` dir, absolute or relative as
   `worktree.useRelativePaths` writes it) whose main checkout is outside
   the dir. A clone, or a main checkout inside the dir, may hold the only
   copy of its commits: never merged.
2. Its tracked state is clean: `git status` shows no staged or unstaged
   change to a tracked file (guard 4's `repo_state`, which also refuses a
   detached HEAD that no ref holds).
3. Its HEAD is a commit the worktree made: its own HEAD reflog has an
   entry at this sha that creates a commit (`commit`, `commit (amend)`,
   `commit (merge)`, `commit (initial)`, `cherry-pick`, `revert`, `am`),
   or a `rebase (finish)` whose sha differs from its `rebase (start)` (the
   onto). A fresh worktree's HEAD is main's tip; a fast-forward merge,
   pull or rebase only catches up with main. Either is about to be worked
   in, and its new untracked files are work in progress. With no reflog,
   nothing is merged.
4. Its HEAD is on the repo's integration branch (D4), and the row names
   the form:
   - an ancestor (`git merge-base --is-ancestor`): a fast-forward or
     prepared merge (`demo: ff 1234abcd5678 is in main`);
   - a squash merge that names it: a commit body on the branch has
     `tip <sha>` (or `tip: <sha>`, the form CLAUDE.md's squash rule writes
     as `Branch <name>, tip <sha>`), HEAD's sha starts with it, and it is
     12 hex digits or more or names one object
     (`rev-parse --disambiguate`) (`demo: sq squash-merged, tip 1234abc in
     main 89ab...`).
5. A detached HEAD that fails rule 3 but is an ancestor of the branch (a
   test or review checkout of a merged commit) is merged only when the
   newest mtime in the dir is a day old or more (`demo: detached HEAD
   1234abcd5678 is in main, nothing written for 3 days`). Younger, it is
   refused as rule 3 does, with `, and the dir was written within a day`.
   Rules 1 and 2 and D2 still apply (D5).
6. No sha its HEAD reflog holds is reachable only from that reflog,
   which goes with it: a detached commit or merge left by a checkout, a
   switch back to the branch, or one a reset dropped. `git rev-list
   --stdin` over every reflog sha, minus every shared ref (not
   `refs/worktree/`, `refs/bisect/`, `refs/rewritten/`) and every sha in
   the `refs/heads/*` reflogs (they stay in the main repo, so a branch's
   commits from before its rebase are held), must be empty. A missing or
   empty HEAD reflog (deleted, expired, `core.logAllRefUpdates=false`)
   is unknown and refuses (review 4).
   Exempt are only an amend's predecessor, and the original tip, start
   and picks of a rebase whose `(start)` is followed by a `(finish)` with
   no abort or new start between; the amend and the finish are checked
   themselves (the agent reviews 2 and 3, 2026-11-06). Rule 3 counts `merge
   x: Merge made by ...` and `pull: Merge made by ...` as commits too.
7. No operation is under way and it is not locked: its git dir holds none
   of `rebase-merge/`, `rebase-apply/`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`,
   `REVERT_HEAD`, `BISECT_LOG`, `sequencer/`, `locked`. A stopped
   `rebase -i` keeps the original commits only there.

Git data that no judged checkout accounts for keeps any dir (`git_data`):
a `.git` in any case (APFS is case-insensitive, so the checkout walks
match it in any case too), a dir with HEAD, `objects/` and `refs/` (a
bare clone, a `--separate-git-dir` target), a small regular file
starting with `gitdir:` (only regular files are ever opened: a FIFO
would block the plan, and clean under its lock), a `*.bundle`, or a dir the walk cannot read.

One checkout that fails keeps the whole dir, and the guard 4 or 5
refusal says which (`not merged: tool: half 1234abcd5678 is not in dev`).
Without tracker states the refusals read as before this change.

A dir with no checkout left (scan finds none) is merged when nothing in it
is named `.git`, in any case, at any depth, nested or under any dir, and
the walk read every dir (`any_git`). Pins, the floor and D2 still apply.
A `.git` anywhere puts the dir under rules 1 to 5 (a clone under `build/`
is "no linked worktree"); a `.git` no walk judged refuses it (D5).

A merged dir skips guard 5 (no age) and guard 4's untracked check. Its
untracked notes and scripts (`.md`, `.markdown`, `.txt`, `.rst`, `.sh`,
`.py`, `.ps1`, `.bat`, `.cmd`, extension-less files starting with `#!`,
and `.patch`/`.diff`, which may be some work's only copy; in any case; in a checkout or beside them, but not in a CMake build dir holding
`CMakeCache.txt` below a checkout root or the dir (neither counts),
whose CMake and fetched-dep files go
with it: the 2026-11-06 plan found 2,700 such files in four `qrs-*`
dirs) that have no copy by
sha under `notes/<name>/` are listed on the plan item (`copy`) and
copied by `clean` to `notes/<name>/<path in the dir>` before anything is
deleted. The plan refuses the dir when a destination already holds other
bytes, or a keeper is over 8 MB (`MAX_REF_FILE`: notes/ is a ref source,
and every later plan would refuse it); the row gives the bytes copied.
Build output (`.venv`, `node_modules`, ...) beside the checkouts is
regenerable as inside one; `clean` checks every destination again, copies, compares each
copy's sha256, and raises with nothing deleted on any failure. Build
trees, logs, results, saves and dumps go with the dir. The row says both
(`; keeps 3 notes or scripts in notes/x/; 12 untracked files go (3.1 GB):
demo/build/a.o, ...`, the first five names). Every commit stays on its
branch, which `git worktree remove` keeps. Guard 4's walk also refuses a
dir it cannot read now, merged or not: its files are unknown.

Rejected: trusting the branch name alone (a branch can be reused); the
tip line's sha in any repo (each checkout reads its own repo's branch);
an equal tree (true of a revert, an empty commit and every fresh
worktree, and squash bodies here always name the tip; review,
2026-11-06); fast-forward entries as own work (a caught-up worktree).

## D2. Live

`live_tree` runs for every worktree dir before guard 4:

- one `lsof -n -w -F pcn` per plan, every open file (else
  `/proc/<pid>/cwd`, `exe` and `fd/*` on Linux): a process with any file
  open under the dir, its cwd and executables included, refuses it
  (`live: pid 123 (zsh) has cat open`). A dir in use is
  never deleted, merged or not; a failed listing only turns D1 off.
- with tracker states, `Pending.live_topic` on the dir's name: an item
  Ready, In Progress, Blocked or In Review that carries `agent:<name>` or
  whose number the name holds (`blxNNN`). In Review counts because the
  merge review's fixes go back to the branch's agent in that worktree.

## D3. Removal and prune

`remove_local` finds every checkout under the dir, nested ones too, and
runs `git worktree remove --force` from each one's main checkout, the
deepest first, then the rmtree, then `git worktree prune` in every main
checkout it met. Before this change only the top checkouts were found,
so a nested worktree's repo kept a stale record.

## D4. The integration branch

Nothing in benchdb knew one: the build lineage reads a game's `[bench]
main_branch`, and the toolkit's `posix-host/portability` lived only in
CLAUDE.md. The branch of a checkout's repo is, in order:

1. `[clean.integration]` in `benchdb.toml`, keyed by the main checkout's
   path (relative to the file, as every local path there):

   ```toml
   [clean.integration]
   xboxrecomp = "posix-host/portability"
   ```

2. the `[bench] main_branch` of a `game.toml` in the main checkout;
3. `main`.

A branch missing from the repo makes nothing merged. The workspace's
`benchdb.toml` gains the `xboxrecomp` line at the merge; an older benchdb
refuses the unknown key, so the line goes in with the CLI pin move.

## D5. The workspace on 2026-11-06

A plan of every `wt/` dir with this change (and the `xboxrecomp` line in
memory) adds none to the two that already went. Of the refusals that a
merge could lift: 32 dirs hold no checkout (empty, or build trees and logs
left after their worktrees went), 6 checkouts are detached at a commit
they did not make (test and review checkouts; 5 of them ancestors of their
integration branch), 4 branches are spikes or tests not merged, and one toolkit checkout belongs to a repo other than `xboxrecomp` with no `main`. Rule 3
keeps the detached ones: they look like a fresh worktree.

Settled by the user, 2026-11-06:

1. "Finding 5: keep notes plus scripts. Before a merged dir goes, copy
   its untracked .md/.txt (any case, also .markdown/.rst) and .sh/.py
   files to notes/<name>/ (or require them there, as you do for notes
   now). Build trees, logs, results and saves go. The plan row lists what
   goes, with count and size."
2. "A dir with no git checkout left counts as merged once its notes and
   scripts are copied, it isn't pinned and nothing live uses it. Make sure
   it really has no checkout anywhere inside, nested or ignored (no .git
   file or dir at all). Anything with a .git stays under the normal
   rules."
3. "A checkout detached at a commit that is an ancestor of the
   integration branch but wasn't committed there counts as merged only if
   nothing in the dir was written in the last day (newest mtime ≥ 24 h
   old). Otherwise it is refused as now. All the other rules still apply
   (linked worktree, no tracked edits, live check)."

D1 implements them: the copy and the row, the no-checkout rule, rule 5.
