Spike code is throwaway and lives in a cat worktree on a spike branch; runs go under `xbox-recomp/runs/entity-spike/`. No goldens apply; nothing merges except, later, through its own change.

## 1. Symbol map (part A)

- [x] 1.1 Settle `config/symbols.toml` (fields, naming scheme) in a spike worktree.
- [x] 1.2 Backfill from `openspec/` and `analysis/research/`, each entry with a source; list conflicts found between specs.
- [x] 1.3 A Ghidra script that imports the map as labels and comments (`scripts/ghidra/ImportSymbolMap.java`). Part A merges to main as data only; analyze and gen are not wired to it (the later names change).

## 2. Entity spike (part B, BLiNX 2)

- [ ] 2.1 E1 entity list and life cycle.
- [ ] 2.2 E2 entity struct.
- [ ] 2.3 E3 type table.
- [ ] 2.4 E4 placements.
- [ ] 2.5 Proof: live entity list mod, then the extra spawn, then the stat change, each with a game frame.
- [ ] 2.6 E5 time-control records, E6 weapons and shop items.
- [ ] 2.7 BLiNX 1: same scheme or not.

## 3. Decision point

- [ ] 3.1 Fold the findings into `design.md`; every address found is in `symbols.toml`.
- [ ] 3.2 Review of the findings.
- [ ] 3.3 Recommend the follow-up changes (names in gen; an entity mod API) and ask the user for the go.
- [ ] 3.4 Notes to `xbox-recomp/notes/entity-spike/`; spike worktree removed through `benchdb`; branch kept.
