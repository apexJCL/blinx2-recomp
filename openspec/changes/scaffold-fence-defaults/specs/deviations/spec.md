## MODIFIED Requirements

### Requirement: Inferred register semantics
The ack tick SHALL set PGRAPH `0x400B10` bits 2..6 to `(completed fence << 2) & 0x7C`, where the completed fence is the first registered fence mirror's completed word, or, when no mirror is registered and the executor has released at least once, the executor's last released semaphore value.
- Reason: XDK D3D's wait-for-idle (reached from Swap after a PFB flush) spins until those bits equal the low five bits of its fence word, which reads as "the GPU's own copy of the last semaphore value has reached memory". The fence word and the executor's last release are the same value from two sides once the executor writes the fence (change `spartan-semaphore-ctxdma`); a title that registers no mirror has only the executor's side. The register's name and its other bits are not confirmed; the behaviour is what the wait needs. (The second half of the former entry, the DMA objects covering physical memory from base 0, was retired by `spartan-semaphore-ctxdma`: the semaphore and report objects' bases are read from instance memory at bind.)
- Risk: a title that reads `0x400B10` differently, or whose fence word and semaphore object differ (the mirror's "NOT the semaphore target" case), waits on a value that is not its fence.
- Detect: the register's source is logged once (`NV2A fence mirror: ...` for a mirror, `NV2A PGRAPH fence: no fence mirror registered` for the executor). A wait-for-idle that spins with either line present is a blocker, not noise.
- Exit: confirmed against a hardware reference (xemu's pgraph code or nv2a documentation), and the requirement rewritten as fact.

#### Scenario: Contradicting log line
- **WHEN** a run logs a semaphore object whose base differs from the mirrored fence word (`NOT the semaphore target; mirror stays on`), or `surface_hits_image`
- **THEN** the run is treated as blocked until the assumption is fixed

#### Scenario: Register source
- **WHEN** a title boots with the executor on
- **THEN** exactly one of the two source lines appears before D3D's first wait-for-idle, and which one says whether the title registered a mirror
