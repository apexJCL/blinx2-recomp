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
