## ADDED Requirements

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
