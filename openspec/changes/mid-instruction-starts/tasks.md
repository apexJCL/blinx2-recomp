Worktrees: `wt/tomtom-hang/xboxrecomp` (`tomtom-hang/mgtu-tg-hang` off posix-host/portability c8a8214f) and `wt/tomtom-hang/cat` (`tomtom-hang/mgtu-tg-hang` off main a359dd8). BLX-188.

## 1. Toolkit

- [x] 1.1 `functions.py`: refuse weak starts that the body before them crosses in code (D1); keep them out of later candidate and alias passes.
- [x] 1.2 `disasm.py`: print the refused starts and any detected body that still reaches one.
- [x] 1.3 `translator.py` / `__main__.py`: a fall-off into unclaimed code tail-dispatches through RECOMP_FALLOFF_TAIL (miss logged once per site), and a WARN reports the count (D3).
- [x] 1.5 Review: weigh both starts before refusing (D1); suspect branches add no targets; tests for the table and terminator cases, seeds, two refusals in a row, the candidate guard and a called FPO start.
- [x] 1.4 Tests: `tools/disasm/test_mid_instruction_start.py` and `tools/recomp/test_falloff_dispatch.py`; `pytest tools/recomp tools/disasm`.

## 2. Cat

- [x] 2.1 `blinx2 analyze` then `blinx2 recomp`; report the gen diff.
- [x] 2.2 Mac build; `tests/posix_ctest.sh` 0 FAIL; `uv run pytest scripts` and ruff.
- [x] 2.3 Metal goldens: attract, stage1 and story, with flips/s.
- [x] 2.4 Windows ABI-check build staged for run 6 on the user's PC.
- [x] 2.5 TASKS.md follow-ups: short index-fed tables (D2); Burnout 3 check.

## 3. Check

- [ ] 3.1 Run 6 on the user's PC passes the second Tom Tom Gang exam.
