# recomp-coverage Specification

## Purpose
Defines which XBE code the pipeline translates and how function detection is seeded, so that every call, jump and indirect target the title reaches at run time resolves to translated code.

## Requirements

### Requirement: Library code sections are translated
The pipeline SHALL disassemble and translate every XBE section that contains code. That is `.text` plus the XDK library sections listed in the game configuration. It SHALL NOT disassemble sections that hold only data, even when the XBE flags them executable.

#### Scenario: Library static initializers are callable
- **WHEN** the CRT runs the initializer tables and calls a static initializer in XGRPH, DSOUND, SRCADV or XPP
- **THEN** the dispatcher resolves the target to a translated function, and no `[ICALL] Failed to resolve` line is logged for it

#### Scenario: Model data is not disassembled
- **WHEN** disasm runs
- **THEN** no functions are reported in the model/motion data sections (DOLBY and every section after it)

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
