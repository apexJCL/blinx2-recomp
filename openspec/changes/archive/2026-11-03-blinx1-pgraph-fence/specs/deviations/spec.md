## MODIFIED Requirements

### Requirement: Inferred register semantics
The ack tick SHALL set the five-bit fence field of PGRAPH `0x400B10` to the low five bits of the completed fence, where the completed fence is the first registered fence mirror's completed word, or, when no mirror is registered and the executor has released at least once, the executor's last released semaphore value. The field's shift SHALL be learned from adjacent pairs of a subchannel-nonzero method `0x0310` and `BACK_END_WRITE_SEMAPHORE_RELEASE` (the only shift in 0..7 at which the `0x0310` word holds the released value's low five bits): the first such pair sets it, and a different shift SHALL replace it only after three such pairs in a row. A release a stopped walk salvages SHALL NOT pair with a word before the stop. Until a pair has been learned the shift SHALL be 2 (bits 2..6). The register's other bits SHALL be left as they are, except that the previous field's bits SHALL be cleared when the shift moves.
- Reason: XDK D3D's wait-for-idle spins until the register's fence field equals the low five bits of its fence word, which reads as "the GPU's own copy of the last semaphore value has reached memory". D3D writes that copy itself, as the `0x0310` word it puts right before each release, and the field's place differs by XDK: bits 2..6 in 5849 (BLiNX 2, Burnout 3, Spartan, KUF), bits 0..4 in 5558 (BLiNX 1, SSX 3; change `blinx1-pgraph-fence`). JSRF's older D3D fences with the release alone and never reads the register. The fence word and the executor's last release are the same value from two sides once the executor writes the fence (change `spartan-semaphore-ctxdma`); a title that registers no mirror has only the executor's side. The register's name and the rest of the word (the pushbuffer position) are not modelled.
- Risk: a title that reads `0x400B10` differently, whose fences are not built as that pair, or whose fence word and semaphore object differ (the mirror's "NOT the semaphore target" case), waits on a value that is not its fence.
- Detect: the register's source is logged once (`NV2A fence mirror: ...` for a mirror, `NV2A PGRAPH fence: no fence mirror registered` for the executor), and the learned field once per change (`[GPU] fence field in PGRAPH 0x400B10 at bits a..b`). A wait-for-idle that spins with these lines present is a blocker, not noise.
- Exit: confirmed against a hardware reference (xemu's pgraph code or nv2a documentation), and the requirement rewritten as fact: the register latches the `0x0310` word.

#### Scenario: Contradicting log line
- **WHEN** a run logs a semaphore object whose base differs from the mirrored fence word (`NOT the semaphore target; mirror stays on`), or `surface_hits_image`
- **THEN** the run is treated as blocked until the assumption is fixed

#### Scenario: Register source
- **WHEN** a title boots with the executor on
- **THEN** exactly one of the two source lines appears before D3D's first wait-for-idle, and which one says whether the title registered a mirror

#### Scenario: XDK 5558 field
- **WHEN** a title's D3D writes `0x0310` with `(pb << 5) | (fence & 0x1F)` right before releasing `fence`
- **THEN** the executor logs `bits 0..4` and the tick writes the fence's low five bits there, so `((reg ^ fence) & 0x1F) == 0` holds once the fence completes

#### Scenario: XDK 5849 unchanged
- **WHEN** a title's D3D writes `0x0310` with `((pb << 3 | fence & 0x1F) << 2) | x` right before releasing `fence`
- **THEN** the field stays at bits 2..6, as before this change, and a pair that fits at two shifts changes nothing

#### Scenario: Stray pair
- **WHEN** the shift is set and one pair fits a different shift
- **THEN** the shift does not move, and the field stays where the title's wait reads it
