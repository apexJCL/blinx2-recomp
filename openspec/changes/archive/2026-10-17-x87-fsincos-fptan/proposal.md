## Why

The `tools.conformance` run for recomp-test-flag-join (toolkit 4773a01, cat a72db5b, the Linux/Proton host) passed 5739 of 5741 vectors. The two failures are x87 vectors older than that change (the same on 37201d8). Logs: `xbox-recomp/runs/recomp-test-flag-join/conformance/`.

```
FAIL fpu_sincos_pair  (fsin and fcos)
       vec 16  st(0)  native=0.87311962268313226  lifted=0.87311962267685606
FAIL fpu_ptan  (fptan replaces st0 and pushes 1.0 -- depth grows by one)
       vec 16  st(1)  native=-0.55834963779435409  lifted=-0.55834963781124181
```

Vector 16 is `(1e10, 3.0)`, so the operand is 1e10. The lifted value is the true cos(1e10) and tan(1e10), correctly rounded. The hardware value is not. It is wrong in the 11th digit, and it is wrong in a known, exact way.

**Root cause: the x87 reduces its argument with a 66-bit pi.** FSIN, FCOS, FSINCOS and FPTAN reduce the operand modulo pi/4 with an internal constant of 66 significant bits, `0xC90FDAA22168C234C × 2^-66` (Intel SDM, "Transcendental Instruction Accuracy"; also Bruce Dawson, "Intel Underestimates Error Bounds by 1.3 quintillion", 2014). libm reduces with as many bits of pi as the argument needs. The reduced argument therefore differs by k·(pi − pi66)/4, where k is the number of eighth-turns removed. For |x| = 1e10 that is about 1.3e-11 radians, which is exactly the error seen. Evaluated at 200 bits with mpmath, `cos(1e10 · pi/pi66)` = 0.87311962268313223 and `tan(1e10 · pi/pi66)` = -0.55834963779435413, and both round to the native doubles in the log. The same model gives `fsin(double(pi))` = 1.2246063538223773e-16, the value Dawson measured on hardware (the true sine is 1.2246467991473532e-16), so the model is confirmed by two independent machines. The candidates the task listed do not explain it:
- **80-bit vs double.** Not the cause. An 80-bit result rounded to double differs from correct rounding by at most one ulp, about 1e-16, not 1e-11.
- **fptan pushing 1.0.** Already modelled (`fp_push(1.0)`). The stack depth matches, and the failing slot is the tangent in st(1).
- **RECOMP_FP_PC.** Not involved. Precision control affects only FADD, FSUB, FMUL, FDIV and FSQRT (and their variants). The transcendentals always round to 64 bits, and the lifter correctly leaves them unwrapped.
- **C2 for |x| ≥ 2^63.** Not what the vectors hit (1e10 < 2^63), but it is a real gap next to this one, and the fix closes it too (design.md D2).

Reading the C2 path turned up a second, older gap. A branch after `fnstsw ax; sahf` is lifted from `g_fp_cmp`, the last compare's result, not from the status word that `fnstsw` just stored. So C2 from anything but a compare (FXAM, an out-of-range trig op, an incomplete FPREM) never reaches the branch, and the CRT's `fprem; fnstsw ax; sahf; jp` loop, which is in BLiNX 2 as the x87 `fmod` (`sub_002E0144`, reached through the dispatch table), spins forever if the last compare before it was unordered. Setting C2 on the trig ops without fixing this would change nothing that the CRT idiom can see (design.md D2).

The bug is small. It matters for three reasons. The conformance suite is the oracle for the lifter, and two permanent known failures hide a third. Xbox titles call `fsin`/`fcos` on accumulated angles (time × speed, never wrapped), where the Pentium III's answer drifts from libm's as the angle grows, and a recompiled title should drift the same way. And the `sahf` lift is a latent hang in every title whose CRT `fmod` runs after a NaN compare.

## What Changes

- **The trig lifts go through runtime helpers that model the 66-bit reduction.** `recomp_x87_fsin/fcos/fsincos/fptan` in `templates/runtime/recomp_types.h` evaluate the function at `x · pi/pi66` without forming that product in double (design.md D1). For |x| ≤ pi/4 the hardware does no reduction, so the helper returns libm's value unchanged. Every trig site in the generated code calls the helper; the range check lives inside it, because the lifter cannot know an operand's range.
- **Out-of-range operands behave as on hardware.** For finite |x| ≥ 2^63, FSIN, FCOS, FSINCOS and FPTAN leave st0 unchanged, push nothing and set C2. In range they clear C2. FPREM and FPREM1 clear C2 as their comment already claims (design.md D2).
- **Branches after `fnstsw ax; sahf` read the stored status word.** `sahf` snapshots AH and the following jcc/setcc tests the CF, PF, ZF and SF bits of that snapshot. For a compare-sourced status this is the same answer as today, since `RECOMP_FCMP_CC` already encodes C3/C2/C0 as the hardware does, and for every other source it is the first correct one (design.md D2). 14 branches in BLiNX 2's gen/ take this form.
- **Tests.** A new standalone ctest `tests/x87_trig` with the two hardware values from the Linux/Proton log, Dawson's published `fsin(pi)`, model vectors computed at 200 bits, a libm self-check, and the C2, `sahf` and `fprem` interplay. Lifter unit tests for the new emitted text, with the negative control the upstream README asks for. New conformance vectors with large and out-of-range operands and a `sahf`-shaped C2 case, so the hardware itself checks the model.
- **Regenerate BLiNX 2** (`blinx2 analyze`, then `blinx2 recomp`). The emitted text changes at every `fsin`, `fcos`, `fsincos`, `fptan`, `fprem` and `sahf` site.

## Impact

- Toolkit: `tools/recomp/lifter.py` (the fsin, fcos, fsincos, fptan, fprem, fprem1 and sahf arms, and the jcc map after sahf), `templates/runtime/recomp_types.h` (helpers), `tests/x87_trig/` (new ctest), `tools/recomp/test_lifter_fpu_reverse.py` and neighbours (updated assertions), `tools/conformance/cases.py` (new vectors).
- CLI: `tests/x87_trig` joins the standalone list that `blinx2 bench tests` builds with llvm-mingw and runs under Proton (`bench/host/tests.sh` and the step text in `bench/__init__.py`), because that is the only place the Windows build's libm is exercised.
- Generated code: 4,198 `fsin`, 195 `fcos`, 10 `fsincos`, 8 `fptan`, 1 `fprem` and 14 `sahf`-derived branches in BLiNX 2's gen/ (counting alias bodies) change text. The trig value changes only for |x| > pi/4, by at most |x|·1.3e-21 radians: the double result differs from libm's in about 1% of calls at |x| ≈ 100, 6% at 1e3, 43% at 1e4 and almost always above 1e5, always in the last place or in a result near zero. The game stores most results as float, which absorbs a last-place double change except on a float rounding boundary. Goldens should not move; design.md says how a moved one is arbitrated (xemu is not the arbiter, since QEMU's `fsin` is the host libm).
- Hot path: `fsin` is common, and game angles mostly lie above pi/4, so the usual cost is one extra libm call (`cos x` next to `sin x`), not one compare. Measure flips/s and CPU time on Metal and D3D11, and flag a 25% drop (design.md D4).
- No env key, no renderer or kernel change. All backends share the generated code, so they agree by construction.
- Upstream: a title-agnostic lifter and runtime fix with tests, on code that is identical on `origin/main` (b3700e1). It is a candidate for the PR set once it has run on Burnout 3 under Proton.
