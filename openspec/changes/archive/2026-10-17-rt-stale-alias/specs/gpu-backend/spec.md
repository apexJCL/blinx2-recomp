## ADDED Requirements

### Requirement: A render target never outlives the title's use of its memory
The Metal and D3D11 backends SHALL NOT bind a render target as a texture, SHALL NOT write a render target back into guest memory, and SHALL NOT draw into a cached render target, when the title has written that target's guest memory (its full pitch x height, through the low 27 bits of its address) since the backend last read or wrote those bytes. Such a target SHALL be dropped without a write-back; a dropped target that the title draws into again SHALL be recreated from the title's bytes. A newly created target SHALL retire every other target whose guest range overlaps it in whole or in part, written back first when its memory is unchanged. A target drawn in the current flip is always valid. Each target's bytes SHALL be rehashed at most once per flip.

#### Scenario: Hub targets do not reach stage 1
- **WHEN** the title draws 512x512 targets in the hub, then loads stage 1 into the same memory, and a stage-1 texture starts at one of their addresses
- **THEN** the texture is decoded from guest memory (the CPU path's texels), and a guest memory dump of the block taken after the stage's first texture decodes equals one taken at stage start and the CPU path's dump at the same flip

#### Scenario: A smaller target inside an old one
- **WHEN** the title creates a 256x256 target whose memory lies inside a 512x512 target it has stopped drawing and has since overwritten
- **THEN** the old target is dropped without a write-back, and the new target is seeded from the title's bytes

#### Scenario: Render-to-texture still works
- **WHEN** the title draws a target in a flip and samples it in the same or a later flip without writing its memory
- **THEN** the target's rendered image is sampled, as before

#### Scenario: A CPU write before a draw
- **WHEN** the title writes a target's memory from the CPU between two draws into it
- **THEN** the next draw starts from the written bytes, not from the earlier rendered image

#### Scenario: A/B switch
- **WHEN** `RECOMP_DEBUG=rt_alias_check=0` is set
- **THEN** both backends behave as before this change
