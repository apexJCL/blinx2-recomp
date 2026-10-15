## MODIFIED Requirements

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

## ADDED Requirements

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
