The spikes of `design.md`, by least resistance. Each spike is a sub-item of the tracker item and runs as its own agent. Spike code is throwaway and lives under `xbox-recomp/runs/engine-bridge/<spike>/`, never in a repo; findings go on the tracker item and into `design.md` through the orchestrator. No spike changes stock behaviour, so no golden, Proton or Mac build gate applies; S3 and S4 build in their own worktrees and merge nothing.

## 1. Offline spikes (parallel)

- [x] 1.1 S2: extract one BLiNX 1 stage from the dump into glTF and open it with headless Godot pinned under `xbox-recomp/toolchains/`. Record what was lost: skinning, materials, UV and vertex quirks, scale and axes.
- [x] 1.2 S1: compare the BLiNX 1 and BLiNX 2 model, map and motion sections and the BLiNX 2 loaders. Verdict: shared format, revision or rewrite, with a BLiNX 2 model header layout.
- [x] 1.3 Fold S1 and S2 into `design.md` (BLiNX 1 and BLiNX 2, Risks).

## 2. Live spikes (after 1)

- [x] 2.1 S4: a throwaway mod in a BLiNX 2 worktree streams the camera and every Ninja model draw over a local socket to a Godot viewport. Measure that guest frame times do not move.
- [x] 2.2 S3: dropped. S4 answered the posed-character question, and slice 1c answers the static-versus-run-time one (`design.md`, Recommendation).

## 3. Decision point

- [x] 3.1 Review of the findings: sound with fixes, folded into `design.md`.
- [x] 3.2 Recommend the first stage's change (scope, effort, which game), and ask the user for the go. Go on 1a, BLiNX 1 then BLiNX 2 (the user, 2026-10-30).
- [x] 3.3 Copy the spikes' notes to `xbox-recomp/notes/engine-bridge/`, remove any spike worktree through `benchdb`, and keep the referenced runs under `runs/engine-bridge/`.
