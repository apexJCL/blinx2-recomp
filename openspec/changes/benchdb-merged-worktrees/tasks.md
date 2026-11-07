## 1. Spec

- [x] 1.1 Proposal, design and tasks (this change).

## 2. CLI (worktree off `xboxrecomp-cli` `main`, branch `feat/benchdb-merged-guards`)

- [x] 2.1 `[clean.integration]` in `config.py`, checked as branch names (D4).
- [x] 2.2 `Planner.merged` and `merged_checkout`: the three forms, the own-commit rule, the reason on the plan row (D1).
- [x] 2.3 `live_tree`: processes and started items for every worktree dir (D2).
- [x] 2.4 Guard 4 keeps only notes for a merged dir; guard 5 skips it; the age refusal names why a dir is not merged.
- [x] 2.5 `remove_local` removes and prunes nested worktrees in every repo (D3).
- [x] 2.6 `docs/commands.md`: the merged rule and `[clean.integration]`.
- [x] 2.7 Tests (`tests/test_benchdb_merged.py`): ancestor, squash tip line (short sha), equal tree, the configured branch, all checkouts named; refusals for a tracked edit, an unmerged branch, one unmerged checkout of several, a fresh worktree, uncopied notes, a started item, a running process, an unlisted process table; clean prunes every repo, nested worktrees too; the config check.
- [x] 2.7a review fixes (2026-11-06): linked worktrees only, own commits only (no fast-forward catch-up), one checkout list for guard 4 and merged, no tree form, unique tip prefixes, every open file, relative gitdirs, the row counts the files that go; a test per probe.
- [x] 2.7b The user's D5 answers (2026-11-06): notes and scripts copied to `notes/<name>/` by `clean`, the row lists what goes; a dir with no checkout and no `.git` anywhere is merged; an old detached ancestor checkout is merged; an unread dir refuses guard 4. Tests: the copy and the listed rest, a clash in notes, a copy failing at clean, a no-checkout dir, a started item, a clone under `build/`, a `.GIT` and an unread dir, old and young detached ancestors, an old detached checkout off main, a tracked edit.
- [x] 2.7c review 2 (2026-11-06): git data under any name (bare clone, separate git dir, `.GIT`, `gitdir:` file, bundle) keeps a dir; reflog-only commits keep a worktree; keepers over 8 MB refuse and the row gives the bytes copied; CMake dirs stop at a checkout root; build output beside the checkouts; `.patch`/`.diff` kept. A probe test each.
- [x] 2.7d review 3 (2026-11-06): every reflog sha checked against the shared refs, exempting only an amend's predecessor and a finished rebase; merge and pull merges are own commits; an operation under way or a lock keeps a checkout; `.ps1`, `.bat`, `.cmd` and `#!` files kept. The review's probes as tests.
- [x] 2.7e review 4 (2026-11-06): only regular files opened (FIFO); a missing or empty HEAD reflog refuses; the branches' reflogs count as held. Tests for each.
- [x] 2.8 Gates: `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`.

## 3. After the merge

- [ ] 3.1 Add `xboxrecomp = "posix-host/portability"` under `[clean.integration]` in the workspace `benchdb.toml`, once the CLI that reads it is the one benchdb runs.
- [ ] 3.2 Plan the `wt/` dirs and clean the merged ones, one plan per batch.
- [x] 3.3 Decide (the user) whether a dir with no checkout left, or a detached checkout at an ancestor of its integration branch, counts as merged: yes, with the copy and the day of quiet (D5, 2026-11-06).
