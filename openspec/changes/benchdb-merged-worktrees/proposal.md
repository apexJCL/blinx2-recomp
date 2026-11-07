# benchdb-merged-worktrees: a merged worktree passes the dirty and age guards

## Why

The user, 2026-11-06: "let's update benchdb to also allow dirty
and young if their work has been merged".

Removing a finished worktree after its merge needs `--force-dirty` (guard
4: untracked build outputs and saves) and `--force-young --older-than`
(guard 5: written within 7 days), and each flag needs the user's word. On
2026-11-06 `wt/apu-sfx`, `wt/blx-crackle-fix` and `wt/blx-crackle` waited
on both. A plan of the 68 `wt/` folders that day refused 32 for their age
and 15 for untracked files, most of them build trees and logs of merged
branches.

## What changes

- `benchdb plan wt/<name>` decides whether a worktree dir is merged
  (design D1). A merged dir skips guard 4's untracked-file check and
  guard 5. Its notes and scripts are copied to `notes/<name>/` before it
  goes; the rest goes. The plan row says so: `a merged worktree, its notes
  kept (<checkout>: <form>; ...); keeps N notes or scripts in
  notes/<name>/; M untracked files go (size): names`.
- A dir with no checkout left, and no `.git` anywhere in it, is merged;
  so is a detached checkout of a merged commit once its dir is a day old
  (the user, 2026-11-06; D5).
- A worktree dir is refused while it is live (D2): a process has a file
  open in it (its cwd and executables included), or a started tracker item carries its
  name. This holds for every worktree dir, merged or not.
- A guard 4 or 5 refusal names why the dir is not merged
  (`written within 7 days; not merged: tool: x 1234abcd is not in dev`).
- `clean` removes each linked worktree in the dir, nested ones included,
  then prunes every repo they belong to (D3).
- `[clean.integration]` in `benchdb.toml` names a repo's integration
  branch by its main checkout (D4).

## What does not change

Tracked edits still refuse a worktree, with or without a merge. The pins,
the roots and their patterns, the `[never]` paths and the floor are
unchanged. `--force-dirty` and `--force-young` keep their meaning and
their need for the user's word. The orchestrator keeps copying untracked
notes to `notes/<name>/` after a merge (CLAUDE.md step 5); `clean` copies
what is still missing. Without
tracker states, or when the processes cannot be listed, nothing is merged
and the guards apply as before.
