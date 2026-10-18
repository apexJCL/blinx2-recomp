# Tasks: upstream v0.14.0 sync

## 1. Toolkit merge
- [x] 1.1 `git merge --no-ff v0.14.0` on `merge/upstream-v0.14.0` (off 70c4371), every
  conflict resolved per hunk (no -X ours/theirs), decisions in design.md: b87b386.
- [x] 1.2 Semantic pass: duplicate symbols, doubled blocks, raw getenv, env knobs.
- [x] 1.3 `RECOMP_MISSING_FILES[_LIST]` as recomp_env old names: 36c4aa4.

## 2. cat
- [x] 2.1 docs/env.md: the two old names on the `missing` and `missing_list` rows.
- [x] 2.2 Regenerate gen (`blinx2 analyze`, `blinx2 recomp`) on the merged lifter and
  disassembler; build macos.

## 3. Gates
- [x] 3.1 Mac build OK; POSIX ctests 70 pass, 0 fail, 15 n/a, 1 skip; pytest tools/recomp
  tools/disasm 1015 pass, 1 skip; cat pytest 60 pass, 1 skip, 1 fail (test_gitignore's
  symlink check, which fails the same way on base in a worktree), ruff clean.
- [x] 3.1b Re-run on b6589fb (after merging portability 06e87d1): build OK; ctests 72 pass,
  0 fail, 15 n/a, 1 skip (runs/up14sync/ctest-merge164/); pytest 1015 pass, 1 skip. Gen
  regenerated with the decode cache is identical to the pre-cache gen.
- [x] 3.2 Metal goldens (attract, stage1, story): all pass on merged, as on base.
  Flips/s on b6589fb / first merge / base: story 53.5/53.7/52.9, attract 46.2/46.4/44.6,
  stage1 34.1/34.1/34.4 (runs/up14sync/golden-metal-{merged,merged1,base}-*).
  With the six entry-proof seeds (cat 6d7ff1d) all three pass with 0 ICALL failures:
  story 53.1, attract 46.1, stage1 33.9 (runs/up14sync/golden-metal-seeds-*).
  Windows cross-build OK; cat_recomp.exe 37 MB, against 190 MB on base (gen 138 MB in 52
  files against 900 MB in 109 files, from the fewer data-table aliases).
- [x] 3.3 Proton D3D11 goldens (`blinx2 bench golden`) on the Deck, exe cross-built on
  the Mac. Base: attract, stage1 and story pass (flips/s 30.7, 30.6, 46.8;
  runs/up14sync/deck-golden-base.out). Merged with the seeds (cat a85c83c, exe sha256
  2ea74095, the same on the Deck): attract, stage1 and story pass, flips/s 31.1, 30.4, 46.7;
  0 ICALL failures, no faults or crashes (runs/up14sync/deck-golden-merged.log,
  bench-logs/20261016-22{1920,2041,2231}).
- [x] 3.4 Speed A/B against 70c4371 + cat 0860f81, Metal and D3D11: from the gate runs on the
  same hosts and harness, no drop of 25% or more. Metal story 53.1/52.9, attract 46.1/44.6,
  stage1 33.9/34.4; Deck D3D11 attract 31.1/30.7, stage1 30.4/30.6, story 46.7/46.8.
- [x] 3.5 Burnout 3 on the Mac (Metal), base burnout3-recomp f7baab9: pipeline OK; boot
  exits 0 with 0 faults and reaches the title (`D:\tracks\_FEMain.xmv`, 23 frames), the same
  point as on 70c4371 (21 frames) (runs/up14sync/b3mac-boot-{merged,base}-*).
- [x] 3.6 Mac CPU check (`blinx2 golden run --backend cpu`, b6589fb): attract, stage1 and
  story pass (wall-time checks SKIP on cpu per golden.json; attract-cliff CLOSE mae 0.25).
  Flips/s attract 17.3, stage1 7.8, story 27.3 (on 2026-10-11: 17.2, 8.0, 23.1)
  (runs/up14sync/golden-cpu-merged-*).

## 4. Follow-ups (TASKS.md)
- [x] 4.1 Upstream PR candidates: always-on Windows placeholder, always-on contiguous
  reuse, the keyboard-and-mouse layer in place of `RECOMP_MKB`.
- [x] 4.2 Assess upstream's FFP T&L, AA surfaces and DMA walk against the fork executor.
  Both are in TASKS.md under "v0.14.0 sync follow-ups".
