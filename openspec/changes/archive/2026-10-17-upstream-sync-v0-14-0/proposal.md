# Upstream v0.14.0 sync

## Why
The toolkit fork (`posix-host/portability`, 70c4371) last merged upstream at v0.13.1
(193e299). Upstream sp00nznet/xboxrecomp has since released v0.14.0 (eb0aa1d, 122
commits, 98 without merges). Many of them are our own PRs as upstream reviewed them,
so the fork and upstream now carry two copies of the same code with different wording
and small review fixes. Others are new: the lifter's lock xadd flags, FCMOVcc, MXCSR
rounding, x87/SSE edge cases and neg; the disassembler's callback and tail recovery;
the APU's GPRST gate and device-queue stall fallback; arm64 MMIO decoder hardening;
#162's render back-end interface, fixed-function T&L and DMA walk; #205's RECOMP_MKB.

## What changes
- Toolkit branch `merge/upstream-v0.14.0`: a real merge commit (subject
  `Merge upstream v0.14.0 (eb0aa1d) into posix-host/portability (70c4371)`), not a
  squash or a rebase, so public `blinx2/portability` stays fast-forward and later syncs
  keep the ancestry. Then one commit per separable decision.
- Policy (operator, 2026-10-09; upstream first on duplicates): where both sides fixed
  the same problem, upstream's fix wins unless ours is shown better or a game needs
  it. Fork-only features (Metal and D3D11 executor, recomp_env, enhancements, render
  scale, the g_eflags lifter, the keyboard-and-mouse layer) survive. Every kept-ours
  case is listed with its reason in design.md; they are upstream PR candidates.
- Upstream's raw `getenv` knobs go through `recomp_env`; the two whose fork key had no
  old name (`RECOMP_MISSING_FILES`, `RECOMP_MISSING_FILES_LIST`) become aliases.
- cat branch `merge/upstream-v0.14.0-cat`: gen regenerated with `blinx2 analyze` then
  `blinx2 recomp` on the merged lifter and disassembler; `docs/env.md` notes the two
  aliases.

Decisions and evidence: design.md. Steps and gates: tasks.md.

## Review
A merge record, not a feature: no spec pass (the user, 2026-10-15). The merge
gets the usual review.
