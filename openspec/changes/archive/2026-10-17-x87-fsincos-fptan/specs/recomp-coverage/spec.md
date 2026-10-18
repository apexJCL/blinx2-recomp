## ADDED Requirements

### Requirement: x87 trig ops reduce their argument like the hardware
The lifted FSIN, FCOS, FSINCOS and FPTAN SHALL return the value the x87 returns. The x87 reduces its argument with a 66-bit pi (`0xC90FDAA22168C234C × 2^-66`), so the lifted result SHALL match f(x·pi/pi66) to 1e-15 relative (absolute below 1) for finite |x| < 2^63, not libm's f(x). For |x| ≤ pi/4 the result SHALL equal libm's. Precision control SHALL NOT be applied to these results.

#### Scenario: A large angle drifts as on the Pentium III
- **WHEN** `fld qword [1e10]; fcos` runs lifted
- **THEN** st0 is 0.87311962268313226 (the hardware value), not 0.87311962267685606 (the true cosine)

#### Scenario: fptan of a large angle
- **WHEN** `fld qword [1e10]; fptan` runs lifted
- **THEN** st1 is -0.55834963779435409 (the hardware value) and st0 is 1.0

#### Scenario: A result near zero keeps the hardware's relative error
- **WHEN** `fld qword [double(pi)]; fsin` runs lifted
- **THEN** st0 is 1.2246063538223773e-16 to 1e-15 relative (the value measured on hardware), not the true 1.2246467991473532e-16

### Requirement: Out-of-range trig operands set C2 and leave the stack alone
For finite |x| ≥ 2^63, FSIN, FCOS, FSINCOS and FPTAN SHALL leave st0 unchanged, push nothing, and set C2 in the status word. In range they SHALL clear C2. Infinite and NaN operands SHALL produce NaN with C2 clear, and FSINCOS and FPTAN SHALL push NaN (FPTAN pushes no 1.0 then). FPREM and FPREM1 SHALL clear C2, since they compute the complete remainder.

#### Scenario: fptan out of range pushes nothing
- **WHEN** `fld qword [2^64]; fptan; fnstsw ax` runs lifted
- **THEN** the stack depth is 1, st0 is 2^64, and AH bit 2 (C2) is set

#### Scenario: fptan of infinity pushes NaN
- **WHEN** `fld qword [inf]; fptan` runs lifted
- **THEN** the stack depth is 2, st0 and st1 are both NaN, and C2 is clear

#### Scenario: The CRT reduction fallback terminates
- **WHEN** `fsin` runs on 2^64, then `fnstsw ax; sahf; jp` branches to an `fprem1; fnstsw ax; sahf; jp` loop
- **THEN** the first `jp` is taken, st0 still holds 2^64, and the loop exits after its first `fprem1`

### Requirement: Branches after `fnstsw ax; sahf` read the stored status word
A jcc or setcc whose flags come from `sahf` SHALL test the CF, PF, ZF and SF bits of the AH value `sahf` loaded, so a status word from FXAM, FTST, a trig op or FPREM reaches the branch, not only one from a compare. For a status word from a compare the outcome SHALL be unchanged.

#### Scenario: The CRT fmod loop after an unordered compare
- **WHEN** a NaN compare leaves the last compare unordered, then `fld 7.0; fld 2.5; fxch st(1); fprem; fnstsw ax; sahf; jp loop; fstp st(1)` runs lifted
- **THEN** the loop runs once and st0 is 2.0

#### Scenario: A compare still branches the same way
- **WHEN** `fld 1.0; fld 2.0; fcompp; fnstsw ax; sahf; jb` runs lifted
- **THEN** the branch is not taken, as before (st0 = 2.0 was not below 1.0)
