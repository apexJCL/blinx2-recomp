## ADDED Requirements

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
