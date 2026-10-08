Worktrees: `wt/x87/cat` off `main` and `wt/x87/xboxrecomp` off `posix-host/portability`, both on `fix/x87-fsincos-fptan`; `wt/x87/xboxrecomp-cli` off `main` on the same branch name for the one-line test registration (task 2.4). Raw runs go to `xbox-recomp/runs/x87-fsincos-fptan/`. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`, and Mac runs are headless with `SDL_AUDIODRIVER=dummy`.

## 0. Spec review

- [x] 0.1 This spec was not written by Fable, so Fable reads it and improves it, then commits the revision on the spec branch.
- [x] 0.2 Implementation starts only from Fable's revised commit.

## 1. Toolkit: runtime helpers (D1, D2)

- [x] 1.1 `templates/runtime/recomp_types.h`: the pi66 constant D, the finite-and-≥2^63 test, and the sin, cos, sincos and tan helpers in the versine form per D1, plus the C2 update per D2. Comments say why (the 66-bit pi, the CRT's C2 loop, no PC rounding per D3).
- [x] 1.2 `tests/x87_trig/model.py`: the mpmath generator for the vectors and the error-budget sweep from D1. Not part of the build; its output is pasted into the ctest with the command that made it.
- [x] 1.3 `tests/x87_trig/` ctest per design.md Validation, with the libm self-check first and the micro-benchmark last. Run it against plain libm (fails) and with the helpers (passes); keep both outputs in the branch notes.

## 2. Toolkit: lifter and tests

- [x] 2.1 `tools/recomp/lifter.py`: fsin, fcos, fsincos and fptan emit the helpers, with a conditional push and the C2 write. fprem and fprem1 clear C2. `sahf` snapshots AH, and the jcc/setcc map after `sahf` reads the snapshot's CF/PF/ZF/SF bits (D2). The fcomi map stays on `g_fp_cmp`.
- [x] 2.2 Update and add the lifter unit tests, including the compiled `fsin; fnstsw ax; sahf; jp` test with its negative control. Run `pytest tools/recomp tools/disasm`.
- [x] 2.3 `tools/conformance/cases.py`: `_FP_TRIG`, the `fsincos` case, and the two C2 cases (eax path and sahf path).
- [x] 2.4 `xboxrecomp-cli`: add `x87_trig` to the standalone list in `bench/host/tests.sh` and to the step text in `bench/__init__.py` `cmd_tests`, with `uv run pytest tests` and the ruff checks. The cat pin (`game.toml`) moves to that sha when it lands.

## 3. BLiNX 2

- [x] 3.1 `blinx2 analyze` then `blinx2 recomp` in the cat worktree against the toolkit worktree. Check that the gen/ diff is only the trig, fprem and sahf sites, and that the counts match design.md's Context (4,198 / 195 / 10 / 8 / 1 / 14).
- [x] 3.2 Mac build, the POSIX ctest dirs (`tests/x87_trig` included), `uv run pytest scripts`, the ruff checks.
- [x] 3.3 Metal goldens (`blinx2 golden check`). A moved golden is arbitrated per design.md Validation, not against xemu.
  - attract and stage1 pass. story-menu fails on a harness anchor flake under slow host pace, which the base build reproduces. In every failing run the menu frame is bit-identical to a passing run's (Fable review, notes.md).
- [x] 3.4 Metal flips/s and CPU time per frame, base vs branch, in `runs/x87-fsincos-fptan/`.

## 4. The Linux/Proton host (on the orchestrator's go)

- [x] 4.1 `blinx2 bench tests` (with `x87_trig` in the list, so the llvm-mingw libm is checked) and `blinx2 bench golden` from the cat worktree.
- [x] 4.2 `tools.conformance` snippets on the toolkit branch head: all vectors pass, the new ones included. Record `lscpu`'s model name in the run notes.
- [x] 4.3 D3D11 flips/s and raster ms, base vs branch, within the CLAUDE.md thresholds (25% flips/s, 1.5× raster ms). If tripped, the `recomp_sincos` shim from D4, then measure again.
- [x] 4.4 Burnout 3 under Proton before this joins the upstream set (not a gate for the cat merge). Count B3's trig, fprem and sahf sites from its regenerated gen/ for the PR text.
  - B3 d2c4335 regenerated with toolkit 53fc610: 72 fsin, 76 fcos, 3 fsincos, 6 fptan, 0 fprem, 18 sahf. The 900 s race smoke under Proton ran to the limit with no [FAULT] (notes.md "Final gates").

## 5. Review

- [ ] 5.1 Fable review, including the README-adherence check from D5. Fixes go back to the branch agent.
