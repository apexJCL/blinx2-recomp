## ADDED Requirements

### Requirement: A wrap with no generated body fails recomp
When the manual file declares a `sub_X_gen` wrap for an address that is not
a function start in the analysis, recomp SHALL fail before writing gen,
leading with a sentence for the player that the dump is probably another
release, then naming each address and its reason. A use of an unknown
`sub_` name in code (a call, or the name as a value) SHALL fail the same
way; a declaration alone SHALL only warn.

#### Scenario: Wrap of a non-function address
- **WHEN** the manual file wraps an address inside another function
- **THEN** recomp exits non-zero with "inside NAME (0x…), not a function start of its own" for that address
