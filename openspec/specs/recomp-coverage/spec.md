# recomp-coverage Specification

## Purpose
Defines which XBE code the pipeline translates and how function detection is seeded, so that every call, jump and indirect target the title reaches at run time resolves to translated code.

## Requirements

### Requirement: Library code sections are translated
The pipeline SHALL disassemble and translate every XBE section that contains code. By default that is every executable section with raw data that is not a data section by name (`text_only = false`): `.text` and the XDK library sections the title links. A title whose XBE flags data sections executable (BLiNX 2's model and motion data) SHALL instead set `text_only = true` and list its code sections in `extra_sections`, so that sections holding only data are not disassembled.

#### Scenario: Library static initializers are callable
- **WHEN** the CRT runs the initializer tables and calls a static initializer in XGRPH, DSOUND, SRCADV or XPP
- **THEN** the dispatcher resolves the target to a translated function, and no `[ICALL] Failed to resolve` line is logged for it

#### Scenario: Model data is not disassembled
- **WHEN** disasm runs on BLiNX 2 with `cat/game.toml`'s settings
- **THEN** no functions are reported in the model/motion data sections (DOLBY and every section after it)

#### Scenario: A title without executable data sections sweeps everything
- **WHEN** disasm runs on Spartan or Burnout 3 with `text_only = false`
- **THEN** every section before `.rdata` is swept, and DOLBY yields at most one phantom function that nothing calls

### Requirement: Measured indirect targets seed function detection
The pipeline SHALL pass a hand-maintained list of runtime-measured indirect-call targets (`config/seed_functions.json`) to function detection. Each listed address SHALL become a function start in the next recompilation. The pipeline SHALL NOT pass the raw `icall_feedback` database to `--seed-functions`. When the database exists, the disasm stage SHALL regenerate `analysis/icall_seeds.json` from it with `tools.recomp.icall_feedback seeds --xbe` and pass that filtered file as a second seed file.

#### Scenario: Thread entry inside a merged function
- **WHEN** the game starts a thread at `0x002D702E`
- **THEN** the dispatcher resolves it to `sub_002D702E`, and the thread runs instead of exiting immediately

#### Scenario: Seed list kept separate from generated feedback
- **WHEN** `tools/recomp/output/icall_targets.json` (or `$ICALL_DB`) exists and the disasm stage runs
- **THEN** `analysis/icall_seeds.json` is rewritten from it, disasm is invoked with `--seed-functions config/seed_functions.json --seed-functions analysis/icall_seeds.json`, and the hand-maintained list is not rewritten

### Requirement: Every direct branch out of a lifted body lands on an entry
Function detection SHALL register an alias entry for every direct jmp/jcc whose target lies outside its primary or alias body and on a decoded instruction strictly inside another detected function. The alias SHALL end at the containing body's end. The pass SHALL iterate until no new alias is found. Targets in gaps between functions SHALL be left to the orphan pass.

#### Scenario: Function split at a lone int3
- **WHEN** a function is split at a single int3 and the halves branch into each other's interiors (BLiNX 2 `sub_00044900`, int3 at `0x00044CFA`)
- **THEN** each branch target becomes an alias entry ending at the containing body's end, and no `[STUB] unresolved` line is logged for it at run time

#### Scenario: Backward branch from inside an alias
- **WHEN** an alias body contains a jcc to an address before its own start but inside its primary function
- **THEN** the target is registered as an alias entry

### Requirement: Unresolved stubs are measured, not assumed
The recomp report SHALL state the count of unresolved call and jump targets. The runtime SHALL log the first hit of each unresolved stub when `RECOMP_STUB_LOG` is set.

#### Scenario: BLiNX 2 after the closure pass
- **WHEN** disasm runs on `default.xbe` with the coverage settings
- **THEN** the unresolved-stub count is at most 81 (down from 994), and a 240 s run with `RECOMP_STUB_LOG=1` logs no `[STUB]` hit

### Requirement: A TEST lifts as a compare of its AND against zero
The lifter SHALL lift every `test a, b` as `cmp (a & b), 0` at the operand width: the flag snapshot holds the masked AND in `_fa` and 0 in `_fb`, the recorded flag state is a `cmp` of that width, and `_cf` is 0. A join whose predecessors end in a `cmp` and a `test` of the same width SHALL inherit a flag state, so its jcc, setcc or cmovcc compiles to a real condition. The `cmp` arm of the condition builder SHALL answer `jo` and `jno` with the exact overflow of the wrapped difference at the operand width. The emitted C for `test X, X` SHALL NOT change.

#### Scenario: The stage 1 talk-zone join
- **WHEN** a block is reached by `cmp eax, 0` on one edge and `test esi, 0x100` on the other and starts with `je`
- **THEN** the `je` compiles to `CMP_EQ(_fa, _fb)` and not to `_flags`, and on the `test` edge `_fa` holds `esi & 0x100`

#### Scenario: Every condition after a test reads x86 semantics
- **WHEN** `test` is followed, directly or across a join, by any of je, jne, jb, jae, jbe, ja, jl, jge, jle, jg, js, jns, jp, jnp, jo, jno
- **THEN** the condition evaluates as the hardware would on 0, the sign bit of the width, the full mask and a negative immediate, at 8, 16 and 32 bits

### Requirement: Compare states of different widths merge for width-independent conditions
When the predecessors of a join carry `cmp` states of different operand widths, the join SHALL inherit a mixed-width compare state. A je, jne, jb, jae, jbe, ja, jl, jge, jle, jg, jp or jnp (and the matching setcc and cmovcc) after it SHALL read that edge's own snapshot, which is exact because `_fa/_fb` are masked and `_fas/_fbs` sign-extended at each edge's width. A js, jns, jo or jno after it SHALL keep the fallback, because the sign and overflow of the difference depend on the width.

#### Scenario: Mixed widths merge for the zero flag
- **WHEN** a block is reached by `cmp al, 0` on one edge and `test eax, eax` on the other and starts with `je`
- **THEN** the `je` compiles to `CMP_EQ(_fa, _fb)` and not to `_flags`

#### Scenario: Mixed widths refuse the sign flag
- **WHEN** a block is reached by `cmp al, 0x80` on one edge and `cmp eax, 0x80` on the other and starts with `js`
- **THEN** the `js` compiles to the fallback and is counted, since with al = 0x80 the hardware's SF is 0 at 8 bits and 1 at 32

### Requirement: Flag fallbacks are measured, not assumed
`recomp` SHALL record every `_flags` fallback it emits (function, guest address, condition, and why the state was lost) to `flag_fallbacks.json` in its output directory, counted once per guest address across alias bodies, SHALL put the totals in `summary.json`, SHALL print one summary line, and SHALL list the functions in the observed seed set that contain one. The report SHALL NOT fail the build.

#### Scenario: Before and after a lifter change
- **WHEN** `recomp` runs before and after a change to flag tracking
- **THEN** the difference between the two `flag_fallbacks.json` files is the list of branches whose behaviour can change, by guest address

#### Scenario: An alias body does not inflate the count
- **WHEN** a function body is emitted for its owner and for a tail-jump alias
- **THEN** each fallback site in it is counted once

### Requirement: Code is read as the loader maps it
Function detection and translation SHALL read a code section's bytes as the XBE loader maps them: the file's `raw_size` bytes followed by zeros up to `virtual_size`. An instruction that starts in the file bytes and ends in the zero fill SHALL decode and be translated whole. No instruction SHALL start in the zero fill, and data sections and sections whose `virtual_size` does not exceed `raw_size` SHALL be read as their file bytes only.

#### Scenario: Spartan's D3DXMatrixLookAtLH keeps its ret
- **WHEN** disasm runs on Spartan's XBE, whose D3DX section has raw size 0x258 and virtual size 0x260
- **THEN** `sub_00237EA5` ends at 0x00237F99, its last instruction is `ret 0x10`, and the generated function ends with `esp += 20; return;`

#### Scenario: The front end survives its first update
- **WHEN** Spartan, regenerated with the fixed toolkit, reaches its front end
- **THEN** `sub_0017F630` is called more than once, no `Couldn't find section` line is printed, and the title keeps presenting frames instead of sleeping in `sub_001ADCA0`

#### Scenario: The fill is not decoded as code
- **WHEN** a code section's virtual size exceeds its raw size by more than 14 bytes
- **THEN** no entry in `engine.instructions` starts at or after the section's raw end, and at most 14 zero bytes are appended to its data

#### Scenario: A gap alias keeps the straddling instruction
- **WHEN** a tail-jump target with no enclosing body lies in a function whose last instruction crosses the section's raw end
- **THEN** the alias entry's end is that instruction's end, not the raw end

#### Scenario: The lifter reads the fill as zeros
- **WHEN** the lifter reads a body that crosses a code section's raw end and the file holds non-zero bytes after that section's raw data
- **THEN** the bytes past the raw end are zeros, and a body whose end lies more than 14 bytes past the raw end is reported and skipped

#### Scenario: The shipped games move only where an instruction is cut
- **WHEN** disasm runs on Burnout 3 and BLiNX 2 with their own manifests
- **THEN** Burnout 3's function bounds are identical to the base toolkit's, and BLiNX 2's differ only in `sub_00330162` (end 0x0033131A → 0x0033131D)

### Requirement: A body that tears down its frame and falls off its end is reported
The lifter SHALL print one warning for a translated body whose last instruction is `leave` or `pop ebp`, is not followed by a terminator, and has no fallthrough target at its end. Bodies that end in any other instruction SHALL not be reported.

#### Scenario: The cut ret would have been named
- **WHEN** Spartan is translated with the base toolkit's function bounds
- **THEN** exactly one warning is printed, for `sub_00237EA5`

#### Scenario: Data decoded as code stays quiet
- **WHEN** BLiNX 2, Burnout 3 and Spartan are translated with the fixed toolkit
- **THEN** no warning is printed, although hundreds of phantom bodies over data end without a terminator

### Requirement: A new game sweeps every code section by default
`xbr new` SHALL write `[pipeline.disasm] text_only = false`, with a comment saying why, and the manifest SHALL default `text_only` to false when the key is absent. A game that sets `text_only` explicitly SHALL get the same disasm command as before the default changed.

#### Scenario: A fresh scaffold
- **WHEN** `xbr new DIR --offline` writes `game.toml`
- **THEN** `text_only` parses as false and the disasm stage command carries no `--text-only`

#### Scenario: A manifest without the key
- **WHEN** a `game.toml` has no `[pipeline.disasm] text_only`
- **THEN** the disasm stage command carries no `--text-only`

#### Scenario: The shipped games do not move
- **WHEN** the CLI builds the disasm command for BLiNX 2 (`text_only = true` plus `extra_sections`) and Burnout 3 (`text_only = false`)
- **THEN** each command is the one v0.6.7 built, and each game's `gen.key.json` `argv` hash is unchanged

### Requirement: Disasm reports calls into code sections it did not sweep
When a direct call from disassembled code targets an executable, non-data section with raw data that is not being swept, disasm SHALL print one warning per such section, with the target count, one example address and the `--extra-sections` name to add. The warning SHALL NOT change the detected functions.

#### Scenario: Spartan swept as `.text` only
- **WHEN** disasm runs on Spartan with `--text-only` and no `--extra-sections`
- **THEN** it warns about XGRPH (9 targets, e.g. 0x00255D64) among D3D, DSOUND, XPP, XMV and D3DX, and its functions.json is identical to a run without the warning code

#### Scenario: BLiNX 2 with its configured sections
- **WHEN** disasm runs on BLiNX 2 with `cat/game.toml`'s settings
- **THEN** no unswept-section warning is printed

### Requirement: Spartan sweeps every code section
Spartan's game configuration SHALL set `text_only = false`, so XMV, D3D, D3DX, DSOUND, XGRPH and XPP are translated.

#### Scenario: Static-init pixel shaders assemble
- **WHEN** Spartan boots and `sub_001B1590` calls XGAssembleShader (`sub_0025E96F`) on the four `xps.1.1` strings at 0x2AFF90, 0x2AFEA8, 0x2AFE48 and 0x2AFD50
- **THEN** each call returns 0 and writes a buffer of 240 bytes, no `[STUB] unresolved 0x0025E4B2` line is logged, and `sub_0025A92C` does not fault

#### Scenario: The twelve remaining stubs are not reached
- **WHEN** Spartan runs headless for 120 s with `RECOMP_STUB_LOG=1`
- **THEN** no `[STUB]` line and no `[CRASH]` line is logged

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
