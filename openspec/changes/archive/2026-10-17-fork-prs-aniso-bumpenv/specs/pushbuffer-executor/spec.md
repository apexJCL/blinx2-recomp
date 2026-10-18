## ADDED Requirements

### Requirement: Bump-environment state is decoded from the stream
The executor SHALL keep `SET_SHADER_OTHER_STAGE_INPUT` (0x1E78) in the transform-unit state it hands the backends, and `nv2a_stage_decode` SHALL carry each stage's `SET_TEXTURE_SET_BUMP_ENV_MAT` (four registers, in stream order), `BUMP_ENV_SCALE` and `BUMP_ENV_OFFSET`. With `RECOMP_TRACE=bump` (trace tier; printing only) the executor SHALL log, once per distinct combination of stage, input stage, matrix, scale, offset and texture format and size, one line naming the flip it first appeared in, so the scenes a title bump-maps and the matrices it writes can be found from a run.

#### Scenario: BLiNX 2 and Burnout 3 scenes found
- **WHEN** attract, stage 1 and a Burnout 3 race run with `RECOMP_TRACE=bump`
- **THEN** the log names each mode-6 stage, its input stage and matrix with the first flip, matching the end-of-run `[VSH]` mode counts (mode 6 on stages 1 and 2 for BLiNX 2, stage 1 for Burnout 3), and no line appears for a title that uses no bump stage

#### Scenario: No behaviour change
- **WHEN** the trace key is unset
- **THEN** no bump line is printed and the frames are those of a run without the key
