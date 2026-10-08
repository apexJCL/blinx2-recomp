## Context

Today the lifter maps the x87 trig ops straight onto libm (`tools/recomp/lifter.py`, "x87 transcendentals"):

| op | emitted |
|---|---|
| fsin | `fp_top() = sin(fp_top());` |
| fcos | `fp_top() = cos(fp_top());` |
| fsincos | `{ double _a = fp_top(); fp_top() = sin(_a); fp_push(cos(_a)); }` |
| fptan | `{ fp_top() = tan(fp_top()); fp_push(1.0); }` |

The stack is double. The rest of the x87 model follows one rule: put the hardware behaviour that matters in a small `static inline` helper in `recomp_types.h` (`recomp_frndint`, `recomp_fist`, `recomp_fp_round24`, `recomp_fxam`), and test that helper with a standalone ctest (`tests/fist`, `tests/fp_precision`). The status word's condition bits live in `g_fp_cc`, which `fnstsw` reads together with TOP. `fxam`, `ftst` and the compares write `g_fp_cc`. Nothing else writes C2 today.

The status word reaches a branch two ways. `fnstsw ax; test ah, mask; jcc` reads eax, which `fnstsw ax` fills from `g_fp_cc`, so it sees whatever is in `g_fp_cc`. `fnstsw ax; sahf; jcc` does not: the jcc map for `flag_setter == "sahf"` (lifter.py, next to the fcomi map) answers from `g_fp_cmp`, the -1/0/1/2 result of the last compare, because when it was written compares were the only thing that set the status. `sahf` itself emits a comment.

What BLiNX 2's gen/ does with all this (counting alias bodies): 4,198 `fsin`, 195 `fcos`, 10 `fsincos`, 8 `fptan`, 4,394 `fpatan`, 1 `fprem`, 0 `fprem1`. No trig op is followed by a status read; the game's `sin()` is the bare instruction. The one `fprem` is the CRT's x87 `fmod` (`sub_002E0144`: `fxch st(1); L: fprem; fnstsw ax; sahf; jp L; fstp st(1)`), reached only through the dispatch table. 14 branches derive from `sahf` (5 `jp`, 3 `jne`, 3 `jbe`, 2 `jae`, 1 `je`), 7 `lahf`. Upstream `origin/main` (b3700e1) has the same trig, fprem and sahf code as our branch, so everything here applies to both.

The Windows build of the game links llvm-mingw's CRT. The conformance harness's lifted side is compiled with 32-bit MSVC, so the fact that it produced a correctly rounded cos(1e10) says nothing about the game binary's `sin`. The ctest under Proton (`blinx2 bench tests`) is where that gets checked.

## Decisions

### D1. Model the reduction as evaluating at x·pi/pi66

The x87 computes r = x − k·(pi66/4) for the integer k that puts |r| ≤ pi/4, evaluates the function on r, and fixes the sign and octant from k. Here pi66 = `0xC90FDAA22168C234C × 2^-66`, and pi − pi66 = 4.04e-21. Since x − k·pi66/4 = x − k·pi/4 + k·(pi − pi66)/4 and the octant correction undoes the k·pi/4 term, the result is f(x + k·(pi − pi66)/4). With k·pi66/4 = x − r that is f(x·(1 + D) − r·D), where D = (pi − pi66)/pi66 = 1.2874146789751208e-21 (`0x1.8518e2da2e893p-70`). The r·D term is at most (pi/4)·D ≈ 1e-21 radians, far below one ulp of any result, so the model is f(x·(1 + D)).

The helper cannot form x·(1 + D) in double, because 1 + D rounds to 1. It computes e = x·D and evaluates f(x + e) by angle addition, as a correction to libm's s = sin x and c = cos x:
- sin(x + e) = s + (c·sin e − s·v), cos(x + e) = c − (s·sin e + c·v), with v = 1 − cos e = 2·sin²(e/2);
- tan(x + e) = sin(x + e) / cos(x + e);
- when |e| < 2^-26, sin e is e and v·s is below half an ulp of s, so the correction is `c·e` and `-s·e` with no extra libm call beyond cos x (or sin x). That holds for |x| below 2^-26/D ≈ 1.16e13; above it, up to 2^63 where |e| ≤ 0.012, sin e and sin(e/2) come from libm. The versine form keeps the correction small next to s, so the sum rounds once; forming s·cos e + c·sin e instead costs an extra rounding of a term of size 1, which is what makes a near-zero result lose ulps.
- For |x| ≤ pi/4 the hardware does no reduction (k = 0) and the helper returns libm unchanged. This is a shortcut, not an exactness boundary: there the correction is below 2e-5 ulp of the result, and the hardware is itself only accurate to about one 64-bit ulp.
- Inf and NaN go to libm (NaN back) with C2 clear, as on hardware with invalid masked. FSINCOS and FPTAN then push a NaN as well: FPTAN pushes the NaN result, not 1.0 (measured on the Ryzen, see notes.md "S1 result"). The NaN's sign bit may differ; nothing compares NaN payloads.

Error budget, checked with mpmath at 200 bits over 18,000 log-uniform operands in [0.5, 2^63) against the harness's own rule (`|d| ≤ tol·max(|a|, |b|, 1)`, tol = 1e-15), with the pole band |cos| < 1e-2 excluded for tan: the plain angle-addition form uses at most 0.20 of the tolerance for sin and cos and 0.44 for tan; the versine form 0.17 and 0.36. The angle itself carries x·D's rounding (≤ 2^-53·0.012 ≈ 1.3e-18 rad), D's own rounding (the same), and the dropped r·D (1e-21), all invisible. The native oracle is the x87's 64-bit result (within one 64-bit ulp of f(x·(1 + D))) stored as a double, so it is within 0.51 ulp of the model. The script that produces these numbers goes in `tests/x87_trig/` as `model.py` (stdlib plus mpmath; it is not part of the build), so the vectors and the budget can be regenerated.

What the model relies on: the host libm reduces large arguments correctly. glibc, Apple libm and the UCRT do; the ctest's libm self-check (Validation) proves it for whichever libm the test links, including llvm-mingw's under Proton.

Every trig site calls the helper. The lifter cannot tell which sites see large operands, so there is nothing to select per site; the range check is a `fabs` and a compare inside an inline function, and the text change at 4,411 sites is the whole of the generated-code impact.

Rejected:
- **Reduce with pi66 in extended or double-double arithmetic, then call the polynomial.** More literal, but on the Mac `long double` is double (arm64). We would need double-double Cody-Waite reduction with k up to 2^61, which is more code and more risk for no observable gain over D1.
- **Emit the helper only where the site is followed by a status read.** The value divergence has nothing to do with the C2 check, and BLiNX 2 has no such site anyway.
- **A larger fast-path threshold.** Any |x| above pi/4 can land near a zero of the function, where the result is tiny and even a 1e-19 correction is many ulps (x = 355 gives sin ≈ -3.0e-5, which the hardware shifts by 134 ulps: libm -3.014435335948845e-05, hardware -3.0144353359488906e-05; x = double(pi) gives Dawson's value, 3.3e-5 relative). Hardware changes those, so the helper must.
- **Widen the conformance tolerance.** That hides a real, deterministic divergence from the hardware, which is the thing `Case.tol`'s docstring says not to do.

Accuracy target: the native result to `tol=1e-15` relative, which is what `fpu_sincos_pair` and `fpu_ptan` already use. That is a few ulps. libm's own last-place difference from the x87 polynomial stays as it is.

Assumption: the reference CPUs share pi66. Intel documents it for P6 and later, and the Xbox CPU is a Pentium III. The Linux/Proton host's CPU (the conformance native side) matched pi66 to the last digit on vector 16, where any other constant beyond bit 66 would show at the 1e-11 level, and Dawson's `fsin(pi)` is a third machine. The new conformance vectors check it on more operands; the run notes record the Linux/Proton host's CPU model (`lscpu`), so the vendor the oracle stands for is on file.

### D2. Out-of-range operands, C2, and the sahf branch

For finite |x| ≥ 2^63 (SDM: `IF |ST(0)| < 2^63 ... ELSE C2 := 1`), FSIN, FCOS, FSINCOS and FPTAN set C2 and leave st0 unchanged, and FSINCOS and FPTAN push nothing. In range they clear C2. C1 (round-up) is not modelled, like everywhere else in this stack model. C0 and C3 are undefined, so they are left alone. QEMU's `helper_fsin` (and xemu's) does exactly this with `MAXTAN = 2^63`, which is a useful cross-check of the boundary, though QEMU's values come from the host libm and do not model pi66.

Software reads C2 like this. MSVC's CRT `_CIsin`/`_CIcos` and code compiled from `sin()` at /Oi do `fsin; fnstsw ax; sahf; jp reduce`, and the `reduce` path loops `fprem1; fnstsw ax; sahf; jp loop` until C2 clears; the CRT's `fmod` is the same loop on `fprem`. So three things change together:
- the trig ops write `g_fp_cc = (g_fp_cc & ~0x0400) | (out_of_range ? 0x0400 : 0)`;
- `fprem`/`fprem1` clear C2 (`g_fp_cc &= ~0x0400`). They already compute the full remainder with `fmod` or `remainder`, which is the hardware's end state after the loop runs to completion, and "complete" is C2 = 0. Their comment says so, but the code never writes it. The quotient bits the hardware leaves in C0, C3 and C1 are not modelled; `remquo()` is the route if a title ever reads them, and that is a follow-up, not this change;
- `sahf` snapshots AH (`_fa = HI8(eax)` or a dedicated local, the implementer picks whichever reads cleanest next to `_snapshot_flags`), and the jcc/setcc map for `flag_setter == "sahf"` reads the snapshot's bits: CF 0x01, PF 0x04, ZF 0x40, SF 0x80. So `jp` is `(_fa & 0x04)`, `je` `(_fa & 0x40)`, `jb` `(_fa & 0x01)`, `jbe` `(_fa & 0x41)`, `ja` `!(_fa & 0x41)`, `jae` `!(_fa & 0x01)`, `js` `(_fa & 0x80)`, and their negations. For a status that came from a compare this is the same answer as today, because `RECOMP_FCMP_CC` already encodes unordered as C3|C2|C0 and less as C0. For a status from `fxam`, `ftst`, a trig op or `fprem` it is the first correct answer, and it also stops the CRT `fmod` loop spinning on a stale `g_fp_cmp == 2`. The snapshot, not eax, is what the branch reads, so an instruction between `sahf` and the jcc that touches eax cannot break it. The fcomi family keeps its `g_fp_cmp` map; those set EFLAGS from the compare directly.

Without the `fprem` half, setting C2 on a trig op would turn the CRT fallback into an endless loop; without the `sahf` half, nothing the CRT does could see it. Inf and NaN operands: see D1.

Emitted shape, so the push stays conditional at run time:

```c
{ double _a = fp_top(); int _oor = recomp_x87_trig_oor(_a);
  if (!_oor) fp_top() = recomp_x87_tan(_a);
  g_fp_cc = (uint16_t)((g_fp_cc & ~0x0400u) | (_oor ? 0x0400u : 0u));
  if (!_oor) fp_push(1.0); } /* fptan */
```

fsin and fcos fold the check into a helper, `recomp_x87_fsin(&st0, &cc)` or similar, whichever reads cleanest next to `recomp_frndint`. fsincos takes the pair from one helper, since it needs both s and c anyway. The implementer picks one shape and keeps all four ops consistent.

### D3. No precision-control rounding on the results

Per the SDM, PC affects only FADD, FSUB, FMUL, FDIV and FSQRT (and their variants). The transcendentals deliver 64-bit significands whatever PC is. The current lifts are right not to wrap them in `RECOMP_FP_PC`, and this change keeps that. A comment says so, because the next person to read the fsqrt arm next door will wonder.

### D4. Cost

fsin is on hot paths (camera, animation), and game angles mostly lie in [0, 2pi), seven eighths of which is above pi/4. So the usual added cost is not the compare but one extra libm call: cos x next to sin x (or the reverse), plus a multiply-add. fsincos already needs both and pays nothing extra. The general branch (two more libm calls) only runs above |x| ≈ 1.16e13.

Two measurements. A micro-benchmark in `tests/x87_trig` (ns per call, plain libm vs helper, for operands in [0, 2pi) and at 1e10, printed, not asserted) says what the helper costs in isolation on the Mac and under Proton. Then flips/s and CPU time per frame on Metal and on D3D11 under Proton, base vs branch, in the bench's own numbers. A drop of 25% or more in flips/s, or a 1.5× rise in raster ms, blocks the merge and gets reported.

If the frame numbers trip the flag, the fallback is a `recomp_sincos` shim that takes both values from one call (`sincos` on glibc and mingw-w64, `__sincos` on Apple, two calls elsewhere), not a weaker model. Without `-ffast-math` (the gen/ build does not use it) compilers do not fuse sin and cos into sincos on Linux or Windows, so the shim is a real saving there.

### D5. Upstream shape

This is title-agnostic toolkit work on code identical upstream. The upstream README's rules for lifter work apply: unit tests that compile the lifter's own output, each paired with a negative control that feeds the pre-fix expression and must fail; a conformance case so the CPU is the oracle; no new dependency in the pipeline (mpmath is only used by the vector generator, which is not run by the build or the tests). No deviation is planned. The Burnout 3 Proton run is the gate for the PR, not for the cat merge.

## Validation

- **ctest `tests/x87_trig`** (standalone, links `recomp_types.h` only, like `tests/fist`; `CMakeLists.txt` in the same shape so `bench/host/tests.sh` can build it with llvm-mingw). The comparison rule is the harness's: relative at 1e-15 above 1, absolute below, except where noted.
  - libm self-check: `sin(1e10)`, `cos(1e10)` and `tan(1e10)` from the host libm equal the correctly rounded values (from `model.py`) within the 1e-15 rule. Apple's tan(1e10) is one ulp off, and a bad reduction is about 1e-11 off. A host whose libm reduces badly fails here, with a message that names libm, before the helper is blamed.
  - the hardware values from the Linux/Proton log, as the vec-16 expectations: cos(1e10) = 0.87311962268313226 and tan(1e10) = -0.55834963779435409;
  - Dawson's `fsin(double(pi))` = 1.2246063538223773e-16, relative at 1e-15: this one is tiny, so the absolute rule would pass the old lifting too, and the relative rule is what makes it a real test;
  - model vectors from `model.py` at 200 bits: 355, 1e5, 1e10, 1e15, 1e18, 1.1e13, 1.2e13 (both sides of the 2^-26 branch), 2^62, 2^63 − 2^10, and their negatives, for sin, cos and tan. Vectors stay out of the tan pole band (|cos(x·(1 + D))| > 1e-2), and `model.py` asserts that;
  - |x| ≤ pi/4 (0.5, -0.7, 0.0, -0.0), 7 and 100: bit-identical to libm for the first group; for 7 and 100 within the rule (the correction is below an ulp there and may or may not flip the last bit);
  - x = 2^63, -2^63, 2^64, 1e300: operand unchanged, C2 set, and FPTAN and FSINCOS push nothing; inf and NaN: NaN back, C2 clear, and FPTAN and FSINCOS push NaN;
  - fprem after an out-of-range fsin clears C2; the status word built as `fnstsw` builds it has bit 10 set after the fsin and clear after the fprem;
  - the micro-benchmark from D4, printed.

  The test fails on the old lifting (plain sin/cos/tan) and passes after. Show both runs in the branch's notes.
- **Lifter unit tests** (`tools/recomp/test_lifter_fpu_reverse.py` and neighbours): update the `sin(fp_top())` and `cos(fp_top())` expectations. Assert the fptan push is conditional on the out-of-range test, that fsincos replaces then pushes in that order, that fprem/fprem1 clear C2, that `sahf` emits the snapshot, and that `jp`/`je`/`jb`/`ja` after `sahf` read the snapshot's bits and not `g_fp_cmp`. One compiled test in the README's pattern: lift `fsin; fnstsw ax; sahf; jp`, run it on 2^64 and on 1.0, and the negative control with the old `(g_fp_cmp == 2)` condition must fail. Run `pytest tools/recomp tools/disasm`.
- **Conformance** (`tools/conformance/cases.py`): a `_FP_TRIG` input list (1e10, 1e15, 1e18, 2^62, 355, double(pi), 100, 0.5, their negatives where it matters, and 2^63, 2^64, 1e300) for `fpu_sincos_pair`, `fpu_ptan` and a new `fpu_sincos_pushes` (`fsincos`). Two C2 cases: `fsin; fnstsw ax; and eax, 0x0400` (the eax path), and `fsin; fnstsw ax; sahf; setp al; movzx eax, al` (the sahf path, the one the CRT uses; confirm setcc after sahf goes through the same map, otherwise use a jcc around a mov). Both run on the in-range and the out-of-range inputs. Run on the Linux/Proton host (x86 host, the native oracle) after the Mac gates. The whole suite must pass, and the run notes record `lscpu`'s model name.
- **Goldens:** BLiNX 2 on Metal (`blinx2 golden check`) and on D3D11 (`blinx2 bench golden`). None should move. If one does, xemu cannot arbitrate (its fsin is the host libm). Find the trig site behind the differing pixels with the usual probe tooling, log its operand, and confirm with `model.py` that the hardware value differs from libm's there; only then re-bless, with the operand and the model value in golden.json's note.
- **Performance:** the D4 numbers, base vs branch, in `runs/x87-fsincos-fptan/`.
