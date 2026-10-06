## ADDED Requirements

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
- **THEN** program-mode batches are skipped exactly as before this change

### Requirement: The CPU path is an oracle, not the product
The design SHALL state the stopping rule. Once one title-stage frame matches a reference (an xemu capture, or a golden frame checked against one), new per-pixel features SHALL go to the GPU render backends (`gpu-backend`) or to `render-fidelity`, and the CPU path SHALL be kept as the reference renderer (`RECOMP_PB_BACKEND` unset or `cpu`, the toolkit default).

#### Scenario: Reference frame matched
- **WHEN** a title-stage dump matches the xemu capture of the same scene
- **THEN** later rendering features are tracked against the GPU backends or `render-fidelity`, not added to the CPU path first
