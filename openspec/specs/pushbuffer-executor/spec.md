# pushbuffer-executor Specification

## Purpose
Defines how the toolkit's pushbuffer executor consumes the NV2A command stream a translated title submits: decoding transform-unit state, running vertex programs on the CPU, keeping the GPU fence honest, and producing frames on the CPU reference path.

## Requirements

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
- **THEN** the mirror writes submitted -> completed on every ack tick, and the title passes its fence waits

### Requirement: Transform-unit state is decoded from the stream
The executor SHALL capture SET_TRANSFORM_PROGRAM into 136 instruction slots at the LOAD cursor, SET_TRANSFORM_CONSTANT into 192 vec4 constants at the CONSTANT_LOAD cursor, SET_TRANSFORM_EXECUTION_MODE, SET_TRANSFORM_PROGRAM_START, SET_VIEWPORT_OFFSET/SCALE and the SET_VERTEX_DATA* inline attribute values.

#### Scenario: Program upload at a cursor
- **WHEN** the stream sets the LOAD cursor and then sends N program words
- **THEN** the words land in consecutive slots starting at that cursor, and the cursor advances by one slot per four words

### Requirement: Program-mode batches are transformed on the CPU
When the execution mode is PROGRAM, the executor SHALL run the current program per vertex, take oPos as surface pixels with clip w (the XDK viewport epilogue), drop triangles with any w < 0, draw a vertex with w == 0 as w = 1 (as the D3D11 and Metal backends do; toolkit 9879d32, a Burnout 3 2D program), and rasterise with the existing surface model. Fixed-function mode SHALL keep the screen-space path. `RECOMP_PB_VSH=0` SHALL disable the program path, for A/B comparison.

#### Scenario: Title stage geometry
- **WHEN** BLiNX 2 reaches the title stage (after `title_movie_1a.sfd` opens)
- **THEN** the report shows 0 program-mode batches skipped as "not screen-space", and a `RECOMP_FB_DUMP` frame shows the stage, not black

#### Scenario: Path disabled
- **WHEN** the same run uses `RECOMP_PB_VSH=0`
- **THEN** program-mode batches are skipped, as on the screen-space-only executor

### Requirement: The CPU path is an oracle, not the product
The design SHALL state the stopping rule. Once one title-stage frame matches a reference (an xemu capture, or a golden frame checked against one), new per-pixel features SHALL go to the GPU render backends (`gpu-backend`) or to `render-fidelity`, and the CPU path SHALL be kept as the reference renderer (`RECOMP_PB_BACKEND` unset or `cpu`, the toolkit default).

#### Scenario: Reference frame matched
- **WHEN** a title-stage dump matches the xemu capture of the same scene
- **THEN** later rendering features are tracked against the GPU backends or `render-fidelity`, not added to the CPU path first
