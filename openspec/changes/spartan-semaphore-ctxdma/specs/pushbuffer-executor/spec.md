## MODIFIED Requirements

### Requirement: The GPU fence advances when the executor consumes the release
The executor SHALL implement `NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_SEMAPHORE_OFFSET` and `NV097_BACK_END_WRITE_SEMAPHORE_RELEASE`. On a release it SHALL write the parameter, at the moment the method runs, to the semaphore context DMA object's base plus the semaphore offset.

When a bind method runs (`NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_CONTEXT_DMA_REPORT`) the executor SHALL read the object's base and limit from instance memory: the handle's RAMHT entry (RAMHT located through `PFIFO_RAMHT`; a valid entry whose handle matches) gives the PRAMIN instance; the base is the frame in word 2, bits 31:12, plus the adjust in word 0, bits 31:20; the limit is word 1. It SHALL keep that result until the next bind of the same purpose and SHALL NOT re-read instance memory per release or per report. When RAMHT does not hold the handle, or the aperture is not mapped, it SHALL use base 0 with no limit and log this once. `NV097_GET_REPORT` SHALL write at the report object's base plus the method's offset. A release or report that would end past the found object's limit SHALL be refused and logged once.

#### Scenario: D3D fence word written by the executor
- **WHEN** the executor runs and the title releases its fence
- **THEN** the first release is logged with its value, its resolved address and its DMA handle and offset, and the word at `*(device + 0x30)` equals the last value released

#### Scenario: A semaphore object that does not start at physical 0
- **WHEN** Spartan's D3D binds object 8 (`0x0002B03D, 0x20, 0x00002003`, base physical 0x2000, limit 0x20) and releases at offset 0
- **THEN** the bind is logged with base 0x00002000 and limit 0x20, the value lands at 0x80002000, D3D's fence word, and physical 0 is untouched

#### Scenario: The gate titles' fences move from the mirror to the executor
- **WHEN** BLiNX 2 or Burnout 3 runs with a fence mirror registered and the executor on
- **THEN** the bind line shows the object's base (BLiNX 2: 0x1000 or 0, by build; Burnout 3: its fence page), the first release lands on the mirrored fence word, and the mirror logs `now written by the executor; mirror off`

#### Scenario: A re-bind refreshes the cached object
- **WHEN** a title binds a handle, rewrites that object's words in PRAMIN, and binds the handle again
- **THEN** releases after the second bind use the new base, and releases between the rewrite and the second bind used the old one

#### Scenario: A write past the object's limit
- **WHEN** a release's offset puts its 4 bytes past `limit + 1` of a found object
- **THEN** nothing is written, and one log line names the handle, offset and limit

#### Scenario: A report object with a non-zero base
- **WHEN** a title binds a report object whose base is not 0 and issues `GET_REPORT` at offset o
- **THEN** the 16-byte report lands at base plus o on every backend

#### Scenario: A handle RAMHT does not hold
- **WHEN** a title binds a handle that no valid RAMHT entry names
- **THEN** one log line says so, and releases through it use the bare offset as before this change
