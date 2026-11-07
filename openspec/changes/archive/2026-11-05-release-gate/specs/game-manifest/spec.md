## ADDED Requirements

### Requirement: The manifest names the reference release
`[xbe]` MAY set `region` and `version` (32-bit integers), `title` (string)
and `alt_title_ids` (integers in 1..0xFFFFFFFF) for the release the port was
made from. A key left unset SHALL take no part in any check. `fingerprint
--toml` SHALL print these keys for the dump it reads.

#### Scenario: Another release is named
- **WHEN** the manifest sets region 0x7, version 1 and a dump's certificate says PAL, version 2 with other code sections
- **THEN** the verdict stays `code`, and the note, doctor line, plan record and build stamp say another release and name both PAL, version 2 and region-free, version 1

#### Scenario: Another title ID
- **WHEN** a dump's certificate title ID is not `[xbe] title_id` and its sha256 is not listed
- **THEN** it is another release, `unknown` when the game lists no sha256 and no sections, and both releases are named with their title IDs

#### Scenario: Truncated beats the release
- **WHEN** the dump is truncated
- **THEN** the verdict is `unknown` with `why=truncated` and no release is claimed in the note, the plan record or the stamp

#### Scenario: Import of another region's title ID
- **WHEN** a dump's title ID differs but its alternate title IDs name the game's (same publisher), or its normalized title matches
- **THEN** import warns, naming both, and imports it; any other title ID is refused as before
