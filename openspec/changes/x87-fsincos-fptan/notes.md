# x87-fsincos-fptan: implementation notes

Branches `fix/x87-fsincos-fptan`. The final tips are in "Final rebase" and "Review fixes" below. Before the rebase they were:
- toolkit 905f08f, based on `posix-host/portability` cb43f7b;
- CLI 552bc45, based on `main` 023c77e;
- cat, from the Fable spec pass 548b8c1.

Raw runs are in `xbox-recomp/runs/x87-fsincos-fptan/`.

## Root cause

The x87 reduces trig operands with a 66-bit pi, so it returns f(x·(1 + D)) with D = (pi − pi66)/pi66 = 1.2874146789751208e-21. libm returns f(x). At 200 bits the model gives cos(1e10) = 0.8731196226831323 and tan(1e10) = -0.5583496377943541, which are the Linux/Proton native values. It also gives fsin(double(pi)) = 1.2246063538223773e-16, Dawson's hardware value.

## What landed

- **Runtime helpers.** `recomp_types.h` has `recomp_x87_fsin`, `_fcos`, `_fsincos` and `_fptan`, which take st0 and the C2 word by pointer and return whether the op completed. They share `recomp_x87_shift`, the versine form, and `recomp_x87_trig_oor`. The constants are decimal, not hex floats, so the 32-bit MSVC that builds the conformance side accepts them.
- **Lifter.**
  - fsin and fcos call the helpers. fsincos and fptan push only when the helper returns 1.
  - fprem and fprem1 write `g_fp_cc &= ~0x0400`.
  - sahf emits `_fa = (eax >> 8) & 0xFFu;`, plus `_cf = _fa & 1` when the function tracks CF. jcc and setcc after sahf read `_fa`'s CF, PF, ZF and SF bits.
  - The translator declares `_fa` in any function that contains a sahf.
- **Deviations from the spec:**
  1. The fast-path threshold is |x| < 2^-26/D ≈ 1.16e13, not about 5e13 as the design said. Both 5e13 and 6e13 were on the general branch, so the straddling vectors are 1.1e13 and 1.2e13. design.md is corrected.
  2. The libm self-check compares within the 1e-15 rule, not bit for bit. Apple's libm returns tan(1e10) = -0.55834963781124192, one ulp off the correctly rounded value. A bad reduction would be about 1e-11 off.
  3. setp and setnp are added to the setcc lifts. They were unimplemented (they emitted RECOMP_UNIMPL), and the sahf-path conformance case `setp al` needs them. A conformance snippet is one basic block, so a jcc around a mov cannot be used. No BLiNX 2 gen site uses setp or setnp.
  4. A `sahf; lahf` pair now rebuilds AH with SF as well. lahf probes the sahf map, which now answers js. This affects 6 sites in gen/, and the old version dropped SF.

## Tests (Mac)

- **`tests/x87_trig`** passes. With `-DX87_TRIG_PLAIN_LIBM` (the old lifting) it fails on the two hardware values, Dawson's value and the first model vector. Both outputs are in `ctest-before-after-mac.txt`. The micro-benchmark on Apple M-series:
  - sin over [0, 2pi): libm 2.2 ns, helper 4.5 ns;
  - near 1e10: libm 3.7 ns, helper 8.3 ns.
- **`model.py --sweep`:** the worst case uses 0.17 of the tolerance for sin, 0.15 for cos and 0.34 for tan on the fast branch, and 0.13, 0.12 and 0.34 on the general branch.
- **Lifter and conformance tests.** `pytest tools/recomp tools/disasm tools/conformance`: 610 passed, 2 skipped. The skips are the conformance native cases, which need MSVC. The new `test_lifter_x87_trig` compiles the lifted `fsin; fnstsw ax; sahf; jp`, `fprem; …; jp` and `fcompp; …; jb` blocks and runs them. The negative control, the old `(g_fp_cmp == 2)` condition, fails.
- **POSIX ctest dirs:** 33 of the 51 dirs pass, `x87_trig`, `fist` and `fp_precision` among them. The other 18 do not build on macOS for reasons unrelated to this change: Windows-only sources, no `cmake_minimum_required`, `-mmmx` on arm64.
- **CLI:** `uv run pytest tests` passes 292, and the ruff checks are clean. The parity fixtures' step text gains `x87_trig`.
- **cat:** `uv run pytest scripts` passes 25, and the ruff checks are clean.

## Regeneration (BLiNX 2)

`blinx2 analyze` then `blinx2 recomp`, against toolkit 905f08f. The gen/ diff against main's gen (toolkit a10f6d8, the same lifter as cb43f7b) is in `gen.diff`. After filtering out the expected rewrites, nothing is left except:
- the header copy;
- 5 `_cf = _fa & 1` lines;
- the `_fa` declarations.

Counts:
- 4,198 fsin, 195 fcos, 10 fsincos, 8 fptan and 1 fprem, as in design.md;
- 14 sahf-derived branches: 5 jp, 3 jne, 3 jbe, 2 jae and 1 je, as in design.md;
- 6 lahf-after-sahf sites.

## Goldens (Metal, Mac, headless)

| scenario | result |
|---|---|
| attract | pass, both frames CLOSE |
| stage1 | pass, 3 of 3 CLOSE |
| story | see below |

**Story.** It needs `dumpat --slack 800`. Without it the menu and hub frames are INCOMPLETE, because the slot-list anchor lands later than the default dump slack.
- The first slack run failed story-menu with "wrong screen at any pace". The anchor came 514 flips late, and the run paced 33.5 fps against the reference's 59.4.
- The rerun (`story2`) passes all three frames. Its story-menu numbers (mae 0.807/0.654/0.617) are identical to the base build's (`golden-metal-base`).
- Read as a host-pace hiccup, not the change.

## Performance (Metal, Mac)

**Base build:** `wt/x87base/cat` (detached at 5dd464d, main's gen at a10f6d8), linked against the same toolkit tree. The base gen does not call the helpers, so it behaves exactly as base.

**Stock pacing (spin), stage1, interleaved:**

| run | base flips/s | branch flips/s |
|---|---|---|
| 1 | 33.64 | 33.45 |
| 2 | 33.43 | 33.68 |

**`present.pacing=sleep`, to see the CPU demand.** Process CPU at the third 600-flip window:

| run | base | branch |
|---|---|---|
| 1 | 57% | 57% |
| 2 | 57% | 56% |

There is no measurable change. The Metal log has no raster ms, and D3D11 raster ms is measured on the Linux/Proton host.

**A known crash in one run.** One branch sleep-pacing run crashed at 14 s: `sub_00332600+0x180` read APU MMIO 0xFE0001D8 from the kernel timer thread's DPC. This is the known crash in TASKS.md (stage 5-1 SIGSEGV, same PC). None of the four functions on its stack contains a trig or sahf site, and the rerun was clean.

## Final rebase (2026-10-07)

**Tips:**
- toolkit 0c319bb, on a0b9a55;
- CLI 25875e5, on f476bfa, with the noreply address as author and committer;
- cat, on 4dcdf52, with the CLI pin moved to 25875e5.

**Gates on the rebased tips:**
- toolkit: pytest 613 passed;
- CLI: pytest 351 passed, ruff clean;
- cat: pytest 27 passed, ruff clean;
- the x87_trig ctest passes;
- `blinx2 analyze`, then `recomp`, then the Mac build: the site counts are unchanged.

**Metal goldens (`golden-metal-final`):**
- attract and stage1 pass;
- story-menu fails again with "wrong screen".

**Story-menu on the Mac.** The anchor `slot-list` is bimodal. It lands at either ~3225 (pass) or ~3780 (fail, pace ~35 fps).

| run | base | branch |
|---|---|---|
| earlier pair | pass | pass (`story2`) |
| `story-ab` run 2 | pass | fail |
| `story-ab` run 3 | fail | fail |

The base build fails the same way, so this predates the change. Note that the `story-ab` runs were made before the Mac run lock existed, alongside another agent's pacing A/B. On D3D11 story-menu is CLOSE with the anchor at 3246.

## the Linux/Proton host

Raw logs are in `runs/x87-fsincos-fptan/bench host/`.

- **`blinx2 bench tests`** passes all 16 tests under Proton, including x87_trig. So the llvm-mingw libm reduces 1e10 correctly.
- **`blinx2 bench golden`** (D3D11): `golden: pass`, every frame CLOSE.
- **`tools.conformance` snippets** on the toolkit head (AMD Ryzen 7 3700X): 5835 vectors, 0 mismatches. The run used the podman image `xboxrecomp-gcc-i386` through a docker shim with `--security-opt label=disable`, and a temporary venv for capstone. The corpus phase was skipped (it needs MSVC).
- **D3D11 performance.** Stage1 with the golden env and `present.pacing=sleep`, base (cat 4dcdf52 + toolkit a0b9a55, gen regenerated) against the branch, interleaved:
  - flips per 105 s: 3252 / 3273 for base, 3271 / 3272 for branch;
  - process CPU over the 600-flip windows: 139–147% for base, 138–143% for branch;
  - frame interval p50 33.3 ms on both.

  There is no measurable change. The D3D11 log's raster column is 0, because the CPU rasterizer is not in use.

## Review fixes (Fable merge review, 2026-10-07)

Toolkit commit 9c288cd, on 0c319bb:
- **M1:** the `x87_trig_test.c` comment says "the x86 test host", not the host name.
- **S1:** inf, -inf and NaN join `_FP_TRIG`, so the hardware itself checks "NaN back, C2 clear". This needs one Linux/Proton conformance run.
- **S2:** tests for the lahf rebuild after sahf (with the SF 0x80 term), and for sahf writing `_cf` when the function tracks CF.
- **N4:** a translator test that a function whose only flag setter is sahf declares `_fa`. It fails without the translator change.
- **N2:** the plain-libm negative control is now a second ctest, `guest-x87-trig-plain-libm-fails`, with `WILL_FAIL`.
- **N7:** a header sentence on tan near a zero of cos.
- **N3:** the model.py docstrings name `recomp_x87_shift`.

The cat fixes are S3 (design.md: the self-check is within the 1e-15 rule), N1 (the helper names in proposal.md), N5 (this header) and N6 (the story-menu note at task 3.3).

Light gates: pytest over `tools/recomp`, `tools/disasm` and `tools/conformance` gives 616 passed and 2 skipped. The x87_trig ctest passes 2 of 2: the helper test, plus the plain-libm control failing as expected.

## Follow-ups for TASKS.md (from the review)

- **F1.** The Metal story `slot-list` anchor is bimodal when the host paces slow. When `tsedit` paces below about 58 fps, the anchor fires about 550 flips late and the checker compares the challenge hub. Yet the menu frame is bit-identical to a passing run's at the expected flip. The fix is the anchor itself, or letting the checker search the dump window when the pace check fails. Take Mac goldens under the run lock. This is not this branch's bug.
- **F2.** `recomp_0083.c:195632-195686` is a byte table lifted as code: `sahf; lahf; mov al, [0xA2A2A2A1]`, repeated. It is harmless, and a candidate for the data/code boundary pass.
- **F3.** The fprem/fprem1 quotient bits (C0, C3, C1), via `remquo`, if a title ever reads them.
- **F4.** Task 4.4: run Burnout 3 under Proton before this joins the upstream PR set. The fsin and sahf code is identical on `origin/main` b3700e1.

## Final gates (rebased onto the BLX-1 bases, 2026-10-07)

Tips: toolkit 53fc610 (on `posix-host/portability` 67471f5), CLI 161f48a (on `main` 7c0abae), cat on `main` da806fc with the CLI pin at 161f48a. The CLI rebase kept both `kernel_guest_cpu` and `x87_trig` in the Proton test list. Raw runs are in `runs/x87-fsincos-fptan/final/`.

**S1 result: the hardware disagreed on fptan.** The first conformance run with inf, -inf and NaN on the oracle (toolkit effce6b, AMD Ryzen 7 3700X) gave 5850 vectors and 3 mismatches, all `fpu_ptan`: st0 native NaN, lifted 1.0. fsin, fcos and fsincos agreed. A stack probe (`final/fptan-nan/probe.c` in the i386 gcc image: `fld; OP; fnstsw; fstp` x8) settles what FPTAN does with masked invalid:
- inf and -inf: depth 2, st0 and st1 both the default NaN (0xfff8000000000000), C2 clear, IE set;
- NaN: depth 2, st0 and st1 both the quiet NaN, C2 clear;
- FSINCOS the same; FSIN and FCOS leave one NaN;
- 3e19: depth 1, operand unchanged, C2 set, for all four (out of range, as modelled).

So FPTAN pushes its NaN result where it would push 1.0. Toolkit 53fc610 has `recomp_x87_fptan(&st0, &push, &cc)` hand back the value to push, as `recomp_x87_fsincos` does; the lifted fptan is `{ double _p; if (recomp_x87_fptan(&fp_top(), &_p, &g_fp_cc)) fp_push(_p); }`. The x87_trig ctest checks the NaN push and the 1.0 push; design.md D1 and the spec delta say it. BLiNX 2's gen/ changes at its 8 fptan sites and the header copy, nothing else. The rerun on 53fc610: **5850 vectors, 0 mismatches**.

**the Linux/Proton host (53fc610, gen regenerated):**
- `blinx2 bench tests`: pass, 17 suites, `x87_trig` and `kernel_guest_cpu` among them;
- `blinx2 bench golden` (D3D11 under Proton): pass, every frame CLOSE or EXACT, story-menu CLOSE (mae 0.78/0.63/0.61), present 0 mismatched flips in all three runs. The effce6b run before the fptan fix also passed.

**Burnout 3 under Proton.** b3 d2c4335 in a detached worktree, gen/ regenerated on the Mac with `burnout3 analyze` and `recomp` against toolkit 53fc610 (72 fsin, 76 fcos, 3 fsincos, 6 fptan, 0 fprem, 18 sahf), host tree `~/xbox-recomp-b3x87`. Built clean; the docs' race pad script with `BENCH_TIMEOUT=900` ran to the limit (exit 124, the normal end) with no `[FAULT]`, threads pinned to one core, vblank 53400, 224 CPU fb dumps; f223 is mid-race (lap 1/2, HUD and car correct). Run log: `final/b3-53fc610/`. One run, not an A/B against base.

**Mac (53fc610):**
- Mac build OK; gen/ regenerated (`blinx2 analyze`, `blinx2 recomp`);
- POSIX ctest dirs: 34 pass (x87_trig 2/2, kernel_guest_cpu included), the same 18 do not build on macOS as before;
- `pytest tools/recomp tools/disasm tools/conformance`: 616 passed, 2 skipped;
- cat `uv run pytest scripts` 27 passed, ruff clean; CLI `uv run pytest tests` 352 passed, ruff clean;
- Metal goldens: attract and stage1 pass (stage1 needs dump slack 100: its first-3d anchor can land 23 flips early, outside the default window); story-menu fails as F1 in every run here (three on effce6b and 53fc610): tsedit paces 56.5–56.8 fps, and either slot-list fires ~500 flips late (wrong screen) or the compared frame is 14 flips past the menu's settle. Each failing run has a frame matching the menu reference at mae 0.02 (flips 3387, 3402, 3494). tsedit and story-hub pass.
