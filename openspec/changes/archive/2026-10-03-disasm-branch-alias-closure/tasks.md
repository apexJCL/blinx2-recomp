## 1. Toolkit

- [x] 1.1 Add `FunctionDetector._pass_branch_alias_closure` (jmp and jcc, primary and alias sources, fixpoint), with tests in `test_branch_alias_closure.py`. Merged at toolkit `fd76080`.
- [x] 1.2 Upstream draft 11 (`analysis/upstream/`).

## 2. cat

- [x] 2.1 Regenerate: 985 new aliases, unresolved stubs 994 to 81.
- [x] 2.2 Verify with `RECOMP_PB_EXEC=1 RECOMP_STUB_LOG=1` for 240 s (`pres-23`): no stub hit, and the title reaches `stg0101_tex_us`. The old gen hits `0x00044C80` and dies with SIGSEGV (`pres-23old`).
