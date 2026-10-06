## ADDED Requirements

### Requirement: The pushbuffer executor produces the title's frames
The toolkit executor SHALL be on by default (`RECOMP_PB_EXEC=0` turns it off) and SHALL consume each pushbuffer segment the title submits before `DMA_GET` reports it as consumed. It SHALL write clears and screen-space batches into the guest colour surface. With `RECOMP_FB_DUMP=<prefix>`, it SHALL write the drawn surface as BMP files.

#### Scenario: Intro movie frames on macOS
- **WHEN** BLiNX 2 boots on macOS with `RECOMP_FB_DUMP=<dir>/f`
- **THEN** within 60 s the dumps include 640x480 frames of the intro movie (studio logos, intro cuts), and the report shows 0 batches skipped as not screen-space

### Requirement: The GPU fence advances when the executor consumes the release
The executor SHALL implement `NV097_SET_CONTEXT_DMA_SEMAPHORE`, `NV097_SET_SEMAPHORE_OFFSET` and `NV097_BACK_END_WRITE_SEMAPHORE_RELEASE`. On a release it SHALL write the parameter to the resolved semaphore address at the moment the method is executed.

#### Scenario: D3D fence word written by the executor
- **WHEN** the executor runs and the title releases its fence
- **THEN** the first release is logged with its value, its resolved address (0x80000000 for BLiNX 2) and its DMA handle and offset, and the word at `*(device + 0x30)` equals the last value released

### Requirement: The submitted-to-completed fence mirror is only a fallback
A fence mirror registered with `xbox_Nv2aMirrorFence` SHALL stop writing once the executor has released a semaphore onto the same fence word. It SHALL keep mirroring when the executor is off, before the first release, or when the semaphore targets a different word, and it SHALL log once which case applies.

#### Scenario: Executor on
- **WHEN** the executor is on and the first release lands on the mirrored word
- **THEN** the log says `now written by the executor; mirror off`, and the mirror makes no further writes

#### Scenario: Executor off
- **WHEN** `RECOMP_PB_EXEC=0` turns the executor off
- **THEN** the mirror writes submitted -> completed on every ack tick, as before this change, and the title passes its fence waits
