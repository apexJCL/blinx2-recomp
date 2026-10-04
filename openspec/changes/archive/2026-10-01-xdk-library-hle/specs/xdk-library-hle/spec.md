## ADDED Requirements

### Requirement: XDK libraries are translated, with hardware-bound entry points replaced by hand
The build SHALL translate the statically linked XDK library code along with the game. An XDK entry point that waits on or drives hardware the host doesn't model SHALL be replaced by a hand-written function in `src/recomp_manual.c` named for its guest address. The recompiler SHALL declare that function in `gen/` and not emit a body for it.

#### Scenario: Override excluded from generated code
- **WHEN** `scripts/pipeline.sh recomp` runs and `src/recomp_manual.c` defines `void sub_002E0DB0(void)`
- **THEN** recomp reports one function excluded, no file in `gen/` defines `sub_002E0DB0`, and the link uses the hand-written definition

#### Scenario: Vertical-blank wait returns
- **WHEN** guest code calls `D3DDevice_BlockUntilVerticalBlank` (`0x002E0DB0`), directly or through `sub_002A1870`
- **THEN** the call returns at the next 60 Hz boundary, with `eax = 0` and the guest stack popped, and no `KeWaitForSingleObject` is issued on the device's vblank event

### Requirement: A self-suspending guest thread blocks on POSIX hosts
On hosts without native thread suspension, a guest thread that suspends itself SHALL block until another thread resumes it.

#### Scenario: Idle worker parks
- **WHEN** a worker calls `NtSuspendThread` on its own handle
- **THEN** it does not return until `NtResumeThread` brings its suspend count to zero, and the NtSuspendThread call count stays in proportion to the NtResumeThread count
