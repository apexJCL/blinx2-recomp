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

### Requirement: A batch keeps every index the title sends
The executor SHALL collect at least `0x80000` (524,288) indices per BEGIN/END batch from `ARRAY_ELEMENT16`, `ARRAY_ELEMENT32` and `DRAW_ARRAYS`, and every backend SHALL draw the whole list. The NV2A accepts batches of at least `0x0FFFFF` elements and retail titles are known to send at least `0x410FA` in one draw, so a smaller cap cuts real geometry. Indices SHALL stay 16-bit: the hardware faults on a `DRAW_ARRAYS` start above `0xFFFF`, so no title references more than 65536 vertices in one batch. When a batch would pass the executor's limit, the executor SHALL print one `[GPU] index batch over N indices` warning per run and SHALL count the batches that overflowed. Indices past `0xFFFF` from `ARRAY_ELEMENT32` SHALL be counted too. It SHALL NOT drop indices silently.

#### Scenario: The stage 1 water grid reaches the horizon
- **WHEN** BLiNX 2 draws its stage 1 water grid as one 4592-index quad list (the lighthouse warp, `runs/stage1-water/scripts/warp_lhp.txt`, flip 2490)
- **THEN** all 1148 quads are drawn on the CPU path, Metal and D3D11, and the cyan water reaches the horizon with no hard edge, as in xemu

#### Scenario: A quad past index 4096
- **WHEN** a backend smoke test sends an indexed quad list of more than 4096 indices as `ARRAY_ELEMENT16`, with a distinct colour on the quads from index 4096 on
- **THEN** a pixel inside a quad past index 4096 has that colour on the CPU path and on the GPU backend under test, and the two frames match

#### Scenario: Overflow is visible
- **WHEN** a batch sends more indices than the executor holds
- **THEN** the run log has one `[GPU] index batch over` line, and the overflow count on the periodic `[GPU]` summary line is non-zero

### Requirement: The odd index of an indexed draw is kept
The executor SHALL decode `NV097_ARRAY_ELEMENT32` (0x1808) as one index per word, appended to the open batch under the same limit and warning as `ARRAY_ELEMENT16`. The XDK sends the last index of an odd-count `DrawIndexedVertices` this way; dropping it loses the batch's last primitive.

#### Scenario: A triangle list whose last index is a 32-bit element
- **WHEN** a backend smoke test sends a triangle list as `ARRAY_ELEMENT16` words followed by one `ARRAY_ELEMENT32` word
- **THEN** a pixel inside the last triangle is drawn on the CPU path and on the GPU backend under test, and `0x1808` does not appear in the unhandled-method ranking

### Requirement: The summary says how big batches get
The executor's periodic `[GPU]` summary SHALL print the largest index count of any batch so far and the number of overflowed batches (`index batches: max M, N overflowed`), and SHALL print the count of `DRAW_ARRAYS` runs that reached past index `0xFFFF` when it is non-zero. A run log then shows whether a title ever needed more than an earlier cap, and whether the walker decoded a start the hardware would have rejected.

#### Scenario: Reading a title's largest batch from its log
- **WHEN** a golden or Burnout 3 run finishes with the NV2A trace on
- **THEN** its log's last `[GPU]` summary carries `index batches: max M, N overflowed`, with N = 0 for every scenario of BLiNX 2 and Burnout 3 at the new cap

### Requirement: A backend draws any batch the executor accepts
A GPU backend's index ring SHALL hold the expanded list of a batch of `NV_MAX_INDICES` indices (three list indices per input index, 32-bit each), and its per-index scratch SHALL grow with the batch rather than be sized statically to the cap. The CPU program path's transformed-vertex scratch SHALL do the same. A batch the executor collects whole is then never dropped for its size downstream.

#### Scenario: Scratch costs what the run uses
- **WHEN** BLiNX 2 runs its stage 1 golden
- **THEN** the per-index scratch on each backend is sized to the run's largest batch (4592 indices), not to the cap
