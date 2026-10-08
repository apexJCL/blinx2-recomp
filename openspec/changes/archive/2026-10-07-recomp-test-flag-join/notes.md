# recomp-test-flag-join: implementation notes

Toolkit `fix/recomp-test-flag-join`:
- 3b62cc2: the report (D3);
- 638a2bb: D1, D1b, and the cmp jo/jno.

Cat `fix/recomp-test-flag-join`. Raw runs are in `xbox-recomp/runs/recomp-test-flag-join/`.

## Fallback report, before and after

| | emitted | unique | joins |
|---|---|---|---|
| before (3b62cc2) | 21,008 | 1,987 | 43 |
| after (638a2bb) | 20,617 | 1,967 | 23 |

20 unique sites came back to life, in 391 emitted bodies; no new fallback appeared. The emitted difference (391) equals the sum of their body counts, so nothing else in gen/ gained or lost a fallback. All four required sites are in the list: 0x000F7F7C, 0x0017F7E7, 0x0017F97E and 0x0018095B.

| guest | cond | kinds at the join | function | bodies |
|---|---|---|---|---|
| 0x00019682 | je | cmp32 + cmp8z | sub_00019490 | 1 |
| 0x0001B1A4 | jg | cmp16z + cmp8z | sub_0001B050 | 1 |
| 0x0001B4D8 | jne | cmp32z + cmp8 | sub_0001B050 | 1 |
| 0x0005B143 | je | cmp32z + test8 | sub_0005B050 | 1 |
| 0x0006778D | jne | cmp32 + cmp8z | sub_000649B0 | 12 |
| 0x00071A4A | je | cmp32z + cmp8z | sub_00071680 | 1 |
| 0x000C2698 | jne | cmp16 + cmp32 | sub_000C2570 | 1 |
| 0x000E0CE2 | jne | cmp32 + test32 | sub_000E0CA0 | 1 |
| 0x000F7F7C | je | cmp32z + test32 | sub_000F7C50 | 2 |
| 0x0014B9BA | jge | cmp16 + cmp8 | sub_0014B6D0 | 1 |
| 0x0017F7E7 | je | cmp32 + test8 | sub_00176150 | 29 |
| 0x0017F97E | je | cmp8z + test8 | sub_00176150 | 34 |
| 0x0018095B | je | cmp32z + test8 | sub_00176150 | 298 |
| 0x001CDAF5 | jne | cmp32 + cmp8 | sub_001CDA90 | 1 |
| 0x001FC347 | je | cmp32 + test8 | sub_001FC2B0 | 1 |
| 0x001FCC89 | je | cmp32 + cmp8z | sub_001FCA10 | 1 |
| 0x002FEC91 | je | cmp32 + test8 | sub_002FEB7F | 1 |
| 0x0035137B | jne | cmp32 + cmp8 | sub_00351110 | 2 |
| 0x0035410D | je | cmp8z + test32 | sub_00353F10 | 1 |
| 0x0036A74A | jne | test32 + test8 | sub_0036A6B5 | 1 |

The remaining 23 joins are cmp + arithmetic setters (20) and arithmetic-only joins (3), as the design's D5 expects.

## Wading repro (D2), Metal, headless

Script: `warp7p.txt`, with `pad_peek=0xCD24C4:1:x,0xCD24A0:1:x,0xB8BD70:1:x`.

| run | polls while wading | frames with stun | walk-ramp max | ramp drops |
|---|---|---|---|---|
| spike build, 1x | (every 4th frame stunned, ramp 0,1,2,0) | 1 in 4 | 2 | every 4 frames |
| this build, 1x (`wade1`) | 966 | 0 | 0x4B | 5 (the script's 5 direction changes) |
| this build, 2x (`wade2x`) | 1000 | 0 | 0x4B | 5 |

**Zone (3.3), corrected.** `0xAE46EC` is not a pad mask. It is a game-mode word. Code around 0x60F47-0x6593C writes it with whole values (0, 2, 3, 4, 0x200, 0x1100), and it reads 0 while wading. The zone's "press" test (`test esi, 0x100`) therefore waits for a mode that carries bit 0x100, such as 0x1100, and not for a button. Which event sets that mode is still open: the next step is a `watch_delay` watch on `0xAE46EC` in the talk zone. Earlier notes on this zone: `[0xB8BD70]` now waits in state 3. It drops to 2 and comes back to 3 as the cat leaves and re-enters the zone; in this script that happens when the cat jumps on A. It no longer cycles through 1. On this zone, the A button is jump, not the 0x100 bit, so the "message once per press" half of task 3.3 is still open: which button sets 0x100 is not known.

## Mac gates

- `pytest tools/recomp tools/disasm`: 592 passed.
- Toolkit standalone ctests on the Mac: 30 pass. 18 don't build on macOS (Windows or D3D only), and `d3dcompile_smoke` has no tests on macOS. This change touches no C.
- `uv run pytest scripts`: 26 passed. ruff check and format: clean.
- Metal goldens (`runs/recomp-test-flag-join/golden-metal`): `golden: pass`. All 8 frames are CLOSE; none moved toward or away from xemu enough to fail.

## Mechanical check of gen/ (4.1)

- `before/gen` (3b62cc2) and the regenerated gen have the same 109 files, with identical line counts in each, so the comparison can go line by line (`runs/recomp-test-flag-join/gen_pairs.json`). 480,593 lines changed:
  - **480,192 are the expected rewrite.** The test snapshot becomes `_fa = ((A) & (B))`, `_fb = 0`. `TEST_Z`/`TEST_NZ` become `CMP_EQ`/`CMP_NE`. The parity of `_fa & _fb` becomes the parity of `_fa - _fb`, which is the same value because `_fb` is 0.
  - **391 are the revived `_flags` consumers.** That is exactly the 20 sites times their bodies.
  - **10 are an equivalent jns rewrite** after an 8-bit test: `(int8_t)(_fa & _fb) >= 0` becomes the top bit of `(uint8_t)(_fa - 0)`.
- Nothing else changed.

## The 20 revived sites against the disassembly (4.2)

Every site is a compiler-made join: a `jmp` from one arm, or a jump-table arm, lands on a jcc that the fall-through arm also reaches with its own cmp or test. On the hardware the jcc reads whichever arm's flags were set last. Each condition is je, jne, jg or jge, and D1/D1b answer all four exactly; the mixed-width joins use jg/jge, which compare per-edge sign-extended values. **Verdict: all 20 revived branches are correct.**

Before the fix, every one of them was never taken, so each arm fell through regardless. Sites worth a note:
- **0x00019682** `je`: `test al, al` on `[0xCD24A0]`, the hit-stun byte, against `cmp [0xB8BBAC], ebx`.
- **0x000F7F7C**: the talk-zone wait (the stutter).
- **0x0017F7E7, 0x0017F97E, 0x0018095B** in the player update: jump-table arms `test byte [edi+0x48], 0x40` joined with a `cmp eax, esi` or a `test al, al`.
- **0x0006778D** `jne` in `sub_000649B0`, the per-player loop: `cmp edx, ecx` against `cmp byte [eax], 0`.
- **0x0001B1A4** `jg`: `cmp word [eax+0x6c], 0` against the `cmp word`/`cmp byte` arms of a jump table (signed per edge).
- **0x0014B9BA** `jge`: `cmp word [edx+0x6c], 0x1e` against a byte-compare arm.
- The others are each a cmp-or-test pair at a jmp-join:
  - in game code: 0x0001B4D8, 0x0005B143, 0x00071A4A, 0x000C2698, 0x000E0CE2, 0x001CDAF5, 0x001FC347, 0x001FCC89;
  - in D3DX: 0x002FEC91;
  - in SRCADV: 0x0035137B, 0x0035410D;
  - in XPP: 0x0036A74A, where the `mov` between the test and the jne does not touch the flags.

## Gates on the merged base (toolkit daddeab, cat 4f8d95f)

Both branches were merged with the irq-safe-points fix (toolkit 37201d8, cat 9330eef) and regenerated with `blinx2 analyze` + `blinx2 recomp`.
- Fallback report: unchanged, at 1,967 unique sites (20,617 emitted) and 23 at joins.
- Toolkit pytest: 592 passed.
- Wading repro (Metal, 1x, `merged/wade1`): 978 polls, 0 stun frames, walk ramp up to 0x4B.
- Metal goldens (`merged/golden-metal`): pass, all 8 CLOSE.
- The Linux/Proton host, Proton (`bench host/`): build OK; all 13 Proton ctests pass; `blinx2 bench golden` (D3D11) passes. attract-cliff is EXACT and the other 7 are CLOSE. Pace is 29.5 to 30.0 fps against the reference.
- No golden moved, so none was re-recorded.

Burnout 3 (`b3/`, `b3gate.sh`):
- Setup: b3/fork-glue 4788d52, regenerated by each toolkit (`regen.sh`). Base is toolkit 37201d8, gen e7039cee. New is daddeab, gen 90d7b729.
- The gen differs in about 16,000 lines. The new report has 54 unique sites (61 emitted), 15 of them at joins.
- Both builds ran the r3 race route for 900 s. Both reach the race and render it with the HUD. Neither has a [CRASH].
- Vblank pacing is identical: 600 vblanks every 10,000 ms, max 10,000.
- Sink audio: median RMS is 4612 base vs 4492 new; the quiet seconds after 60 s are 106 vs 97.
- Frames diverge from dump 25 on (148 frames each). The irq-safe-points base/new pair diverged at dump 26, so this is ordinary Proton run-to-run drift.
- 5.3 is still open: the golden pace is unchanged, but raster ms was not measured.
