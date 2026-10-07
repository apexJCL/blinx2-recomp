Worktrees: `wt/<name>/cat` off `main` and `wt/<name>/xboxrecomp` off `posix-host/portability`, both on `fix/recomp-test-flag-join`. Raw runs go to `xbox-recomp/runs/recomp-test-flag-join/`. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`, and Mac runs are headless with `SDL_AUDIODRIVER=dummy`. In the cat worktree `blinx2` needs `XBOXRECOMP_CLI_DIR=<xbox-recomp>/xboxrecomp-cli` (the pinned CLI sha is not pushed yet) and picks the toolkit worktree up from `../xboxrecomp`.

## 0. Spec review

- [x] 0.1 This spec was not written by Fable, so Fable reads it and improves it, then commits the revision on the spec branch.
- [x] 0.2 Implementation starts only from Fable's revised commit.

## 1. Toolkit: the fallback report (D3), first

- [x] 1.1 `tools/recomp/translator.py` and `lifter.py`: record every `_flags` site emitted (function, guest address, condition, reason) and dedupe by guest address across alias bodies. `__main__.py` writes `analysis/recomp/flag_fallbacks.json` (`-o` dir), adds the totals to `summary.json`, prints one summary line and lists the functions in the observed seed set.
- [x] 1.2 Tests: a known-unknown join (`popfd`, or a `call` before the jcc) is counted once; an alias body does not double it; the stage 1 shape (`cmp eax, 0` + `test esi, 0x100` + `je`) is counted with reason "join: cmp32z + test32" before D1.
- [x] 1.3 Run `blinx2 recomp` in the cat worktree with the report alone, keep `flag_fallbacks.json` as the **before** file in `runs/recomp-test-flag-join/before/`, and note the unique and reachable counts.

## 2. Toolkit: the lifter (D1)

- [x] 2.1 `tools/recomp/disasm.py`: `Operand` type `"expr"` (C text + `mem_size`). `lifter.py`: `_fmt_operand_read` and `_operand_width` handle it; `normalise_zero_test` turns every `test a, b` into `cmp <expr (a & b) at width>, 0`; the snapshot writes `_fa = (a & b) & MASK`, `_fb = 0`, `_cf = 0` and keeps `test a, b` in the comment. The emitted C for `test X, X` does not change.
- [x] 2.2 `_make_condition`'s `cmp` arm answers `jo`/`jno` with the exact OF of the wrapped difference at the operand width (unsigned arithmetic, like `_sf_of_difference`).
- [x] 2.3 `translator.py` `_merge_flag_states`: two cmp states of different widths merge into `cmp_mixed`; `_make_condition` answers it as cmp except for js/jns/jo/jno, which return None (D1b).
- [x] 2.4 Unit tests next to `test_flag_join.py` and `test_lifter_zero_test_merge.py` (design.md Validation), and the rewrites of the tests whose meaning changes (design.md D1 and D1b).
- [x] 2.5 `pytest tools/recomp tools/disasm`.

## 3. Verify the wading fix (D2)

- [x] 3.1 `blinx2 analyze` then `blinx2 recomp` in the cat worktree; keep `flag_fallbacks.json` as the **after** file. Diff before/after: the resurrected list, which must include 0x000F7F7C and 0x0017F7E7, 0x0017F97E, 0x0018095B in `sub_00176150`.
- [x] 3.2 Mac build. `runs/stage1-water/scripts/warp7p.txt` on Metal with `RECOMP_DEBUG=pad_peek=0xCD24C4:1:x,0xCD24A0:1:x`: the hit-stun byte stays 0 while wading and `[+0x84]` climbs without resets. Same at 2x render scale on Metal. If it fails, stop here and reopen the spike.
- [ ] 3.3 Zone check: find the zone object, stand in it, press A. The message appears once per press and `[0xB8BD70]` follows 2→3→4→1.
  - Archive note (2026-10-07): half done. `[0xB8BD70]` waits in state 3 and no longer cycles through 1 (notes.md, Zone). The "once per press" half is open: the zone tests bit 0x100 of the game-mode word `0xAE46EC`, not a button, and which event sets it is unknown. Moved to TASKS.md.

## 4. Attribute the regeneration (D4)

- [x] 4.1 Mechanical check of the gen/ diff: filter the expected rewrites; what remains must be exactly the resurrected branches.
- [x] 4.2 Read every resurrected branch (about 20) against the disassembly; record the list and verdicts in the change's notes.
- [x] 4.3 `uv run pytest scripts`, the ruff checks, and the POSIX ctest dirs.

## 5. Gates

- [x] 5.1 BLiNX 2 goldens on Metal (`blinx2 golden check`) and on D3D11 via `blinx2 bench golden` under Proton. Compare every moved golden with xemu (`scripts/xemu_compare.py`) before asking to re-bless it.
- [x] 5.2 Burnout 3: `b3/regen.sh` against the toolkit worktree, build, boot and a race under Proton on the Linux/Proton host (run lock, BLiNX first, user's go). Gate for the toolkit squash.
- [ ] 5.3 Bench: flips/s and raster ms on Metal and D3D11 within the CLAUDE.md thresholds.
  - Archive note (2026-10-07): the golden pace is unchanged (29.5 to 30.0 fps on D3D11), but flips/s and raster ms were not measured. Moved to TASKS.md (the bench pass for today's merges).

## 6. Merge

- [x] 6.1 Fable review. Fixes go back to the branch agent. Done: `notes/fable-reviews/2026-10-06-runtime.md` §4, no blocker. Its should-fix, `tools.conformance`, ran on the Linux/Proton host at toolkit 4773a01 (cat a72db5b): 5739/5741 pass, every test/cmp/jcc vector included; the two x87 failures predate the change.
- [x] 6.2 Squash-merge the toolkit change (`recomp: lift test as cmp of the AND so cmp/test joins keep their branch`, body naming the report and jo/jno), then the cat regeneration with the new `game.toml` toolkit pin. Done 2026-10-06: toolkit b0eb653 (from daddeab), cat 9c8bf09 (from edfb30c).
- [x] 6.3 Close the stage 1 water stutter in `TASKS.md`; add the fallback counts (before/after, unique and reachable) and the D5 follow-up entries (cmp + result-setter joins; whether entry-block alias bodies are ever entered). Done 2026-10-07: the stutter is closed (the user verified it on the Steam Deck), the counts are 1,987 unique (21,008 emitted, 43 at joins) before and 1,967 (20,617, 23) after, and the D5 entries are in TASKS.md.
