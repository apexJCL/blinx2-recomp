# Upstream v0.13.1 sync (BLX-35)

## Why
The toolkit fork (`posix-host/portability`, 99b9798) last merged upstream at 1409a7d.
Upstream sp00nznet/xboxrecomp has since released v0.13.0 and v0.13.1 (193e299, 62
commits). Several of them fix problems the fork had already fixed its own way. Keeping
two fixes for one problem doubles the upstream PR work and leaves dead code behind.

## What changes
- Toolkit branch `sync/upstream-v0.13.1`: a real merge commit (36761e6), not a squash or a
  rebase, so public `blinx2/portability` stays fast-forward and later syncs keep the
  ancestry. Then one commit per decision that drops our now-dead code.
- Policy (operator, 2026-10-09): where both sides fixed the same problem, upstream's fix
  wins unless ours is shown better or BLiNX 2 needs it. Everything else is a union.
- cat: `src/main.c` turns on upstream's opt-in `RECOMP_TITLE_KEVENTS`; `docs/env.md`
  lists upstream's four new switches, which now go through the `recomp_env` table.

Decisions and evidence: design.md.

## Review
This is a small merge record, not a feature, so it gets no Fable spec review (no Fable
quota). The merge itself still gets the usual Fable merge review.

## Owed before merge
- Proton: `blinx2 bench tests` (the Windows-only ctests, among them upstream's new
  kernel_events, kernel_regressions, kernel_directory, kernel_object_paths), `bench golden`
  (D3D11), a pacing A/B, and the BLX-1 dark-water A/B (20 runs pinned) on the merged tree.
- Burnout 3 smoke under Proton.
- CLI: add upstream's new ctests (kernel_events, kernel_regressions, memory_regressions)
  to the `bench tests` list.
