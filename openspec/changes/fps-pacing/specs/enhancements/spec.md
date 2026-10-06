## MODIFIED Requirements

### Requirement: Enhancements default to stock
Every enhancement key (`render.scale`, `present.filter`, `present.fullscreen`, `present.pacing`) SHALL default to the stock behaviour. With every key at its default and the layer built in (`XBOXRECOMP_ENHANCE` ON), the Metal, D3D11 and CPU paths SHALL execute the same rendering, present and dump code as they did before the layer existed: every new statement in a backend or presenter SHALL be reached only when `render.scale > 1`, `present.filter` is not `nearest`, `present.fullscreen` is set, or the frame and the output differ in size. A lowered spin-wait loop at `present.pacing = "spin"` SHALL busy-wait as the unlowered loop did. Where the pipeline is deterministic the output SHALL be byte-identical: the pure helpers at scale 1 return their inputs, and `RECOMP_PB_FAST_AB` reports zero mismatches. The golden configuration SHALL pin `RECOMP_ENHANCE_CONFIG=none`, `RECOMP_RENDER_SCALE=1` and `RECOMP_PRESENT_PACING=spin`. These pins SHALL stay even if the default of `present.pacing` changes. The golden harness SHALL fail a run whose log reports a non-stock `render.scale`, `display.aspect` or `present.pacing`, or an `fps.mode` other than `lock30`. The only exception is an evaluation run started with `--allow-enhance <key>=<value>`, which records the reason as a note and SHALL NOT be used to record references.

#### Scenario: Stock goldens unchanged
- **WHEN** the Metal goldens `@attract`, `@stage1` and `@story` run on the layer-ON build with no key set
- **THEN** each passes with the same verdict as a build without the layer and the log reads `[ENHANCE] render.scale=1 present.filter=nearest present.fullscreen=0 present.pacing=spin (display.aspect=4:3)`

#### Scenario: Deterministic paths byte-identical
- **WHEN** the CPU backend runs attract for 60 s with `RECOMP_PB_FAST_AB` on the layer-ON build, and `tests/render_scale` runs its scale-1 cases
- **THEN** FAST_AB reports zero mismatches and every helper (`nv2a_host_size`, `nv2a_present_rect` for an exact fit, the occlusion scaling) returns its input unchanged

#### Scenario: Golden harness rejects a scaled run
- **WHEN** `golden.py` evaluates a run whose log contains `[ENHANCE] render.scale=2`
- **THEN** the run is marked FAIL with a reason naming the enhancement, regardless of its frames

#### Scenario: Golden harness rejects a sleeping run
- **WHEN** `golden.py` evaluates a run whose log reports `present.pacing=sleep`, without `--allow-enhance present.pacing=sleep`
- **THEN** the run is marked FAIL with a reason naming `present.pacing`; with the flag the frames are judged and the reason is printed as a note

## ADDED Requirements

### Requirement: Frame pacing key
`present.pacing` (env `RECOMP_PRESENT_PACING`) SHALL select how lowered spin-wait loops wait: `"spin"` busy-waits as stock, `"sleep"` blocks in the runtime wait (`frame-pacing`). The layer SHALL read it once at startup, before the guest starts, and SHALL report it on the `[ENHANCE]` settings line. Without the layer the mode SHALL be `spin`. The default SHALL be `"spin"`. It SHALL change to `"sleep"` only through a separate commit that can be reverted on its own, and only after `sleep` has been shown to be frame-identical to `spin`:
- on the Metal goldens;
- on the D3D11 goldens under Proton;
- in flip-indexed dumps of `@stage1` and `@story-hub`;
- on Burnout 3 under Proton at the exact upstream PR head.

Frame-identical means: the same verdict for every golden frame; a frame exact in every `spin` run exact in every `sleep` run; and, in the flip-indexed dumps, no `sleep`-against-`spin` difference larger than the largest `spin`-against-`spin` difference of the same flip. The change that flips the default SHALL amend this capability's "Enhancements default to stock" requirement with a named exception for `present.pacing` and the evidence, and SHALL keep the golden pins.

#### Scenario: Sleep selected from the file
- **WHEN** `enhance.toml` beside the executable has `[present] pacing = "sleep"` and no `RECOMP_PRESENT_PACING` is set
- **THEN** the `[ENHANCE]` line reads `present.pacing=sleep`, and the `pacing` trace reports `mode sleep` with wakes counted at site `0x00060475`

#### Scenario: Default flip withheld
- **WHEN** any of the four frame-identity checks fails or a pacing A/B is flagged (`frame-pacing`)
- **THEN** the default stays `"spin"` and the failing evidence is recorded in TASKS.md

### Requirement: Frame-rate mode reports what is available
The title SHALL read `fps.mode` (env `RECOMP_FPS_MODE`, choices `lock30`, `lock60`, `free`, default `lock30`) before the layer reports unused keys. `lock30` SHALL run the game's own pacing and log `[ENHANCE] fps.mode=lock30`. `lock60` and `free` SHALL each log exactly one line saying the mode is not available for this title and why, and then run `lock30`, writing nothing to guest memory. A value outside the choices SHALL be reported once by the layer and treated as the default.

#### Scenario: lock60 asked for
- **WHEN** BLiNX 2 starts with `RECOMP_FPS_MODE=lock60`
- **THEN** the log has one line `[ENHANCE] fps.mode=lock60 not available for this title (...); using lock30`, the game runs at its stock 30 fps in 3D, and frames match a `lock30` run

#### Scenario: Key in the file is not reported unused
- **WHEN** `enhance.toml` sets `[fps] mode = "lock30"`
- **THEN** the unused-key report does not list `fps.mode`
