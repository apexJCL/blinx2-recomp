## ADDED Requirements

### Requirement: Library code sections are translated
The pipeline SHALL disassemble and translate every XBE section that contains code. That is `.text` plus the XDK library sections listed in the game configuration. It SHALL NOT disassemble sections that hold only data, even when the XBE flags them executable.

#### Scenario: Library static initializers are callable
- **WHEN** the CRT runs the initializer tables and calls a static initializer in XGRPH, DSOUND, SRCADV or XPP
- **THEN** the dispatcher resolves the target to a translated function, and no `[ICALL] Failed to resolve` line is logged for it

#### Scenario: Model data is not disassembled
- **WHEN** disasm runs
- **THEN** no functions are reported in the model/motion data sections (DOLBY and every section after it)

### Requirement: Measured indirect targets seed function detection
The pipeline SHALL pass a hand-maintained list of runtime-measured indirect-call targets to function detection. Each listed address SHALL become a function start in the next recompilation.

#### Scenario: Thread entry inside a merged function
- **WHEN** the game starts a thread at `0x002D702E`
- **THEN** the dispatcher resolves it to `sub_002D702E`, and the thread runs instead of exiting immediately

#### Scenario: Seed list kept separate from generated feedback
- **WHEN** the `icall_feedback` database is used as a second seed file
- **THEN** it is passed as its own `--seed-functions` argument, and the hand-maintained list is not rewritten
