## ADDED Requirements

### Requirement: Free camera toggle
With `camera.free = "on"` (env `RECOMP_CAMERA_FREE`), the key `camera.free_toggle` (default `F6`, env `RECOMP_CAMERA_FREE_TOGGLE`) SHALL start and stop a free camera in any state where the game camera `[0x4B271C]` exists. Starting SHALL seed the free camera from the game's: position from the eye at `+0x2C..+0x34`, pitch `+0x0C`, yaw `+0x10`, roll and the extra angles 0. While it is active, the wrappers on the view builders `sub_000292A0` and `sub_0021B1F0` SHALL write the free camera's fields into the struct (shake offset 0, eye = position), call the generated builder, and put back each field that still holds the value written in; they SHALL act only when the builder's camera is `[0x4B271C]`, and only in the outermost of nested builds. Stopping SHALL return the next build to the game's camera with nothing else to restore. If the game frees its camera (`[0x4B271C] == 0`), the free camera SHALL stop.

#### Scenario: Fly away and come back
- **WHEN** stage 1 runs on Metal with `RECOMP_CAMERA_FREE=on`, the toggle is pressed, the camera turns and moves, and the toggle is pressed again
- **THEN** the log shows `on at (x y z)` equal to the game camera's eye, the frames show the stage from the moved camera, and after the second press the frames are the game's view and the game camera reacts to the right stick again

#### Scenario: Off by default
- **WHEN** the key is unset
- **THEN** the toggle does nothing and the builders run as the generated code

### Requirement: Fly controls and input capture
While the free camera is active, player 1's pad SHALL drive it and the game SHALL see a neutral pad on port 0 (after the once-per-frame poll `sub_0005C930`): the left stick moves in camera space, the right stick and mouse motion look, RT or X rises and LT or Y sinks (the world is Y-down), White multiplies the speed by 4 and Black by 0.25. The base speed is 80 world units a second times `camera.free_speed` (0.05 to 20); the look rate is 1.8 rad a second at full stick, 0.0025 rad a mouse count, times `camera.free_look_sens` (0.05 to 10); a value out of range SHALL be replaced by 1 with one line. Pitch SHALL be clamped to ±1.5 rad and a frame's time step to 0.1 s. `camera.free_reset_key` (default `F5`) SHALL re-seed the free camera from the game's.

#### Scenario: Character stands still
- **WHEN** the free camera flies with the left stick held
- **THEN** the character does not move, and moves again with the stick once the camera is off

### Requirement: HUD hide
`camera.free_hud` (`keep` or `hide`, default `keep`) SHALL set whether the HUD shows when the free camera starts, and `camera.free_hud_key` (default `F7`) SHALL flip it while flying. Hiding SHALL skip, through the mod API's `batch_filter` on both GPU backends, the whole blended, no-depth 2D pass drawn to the back buffer: the batches drawn with program `5474DB2A` or `B2913952`, no depth test, blending on. Dialogue boxes and fades drawn in that pass are hidden too while the HUD is hidden. Each distinct matched batch shape SHALL be logged once. The CPU renderer MAY keep drawing the HUD (a recorded follow-up).

#### Scenario: HUD gone on Metal
- **WHEN** the HUD is hidden in stage 1 on Metal
- **THEN** the timer, the radar and the counters are not drawn, the stage is, and the log lists the matched batch shapes

### Requirement: Freeze
`camera.free_freeze_key` (default `F8`) SHALL, while flying, stop and restart the world through the event world-stop flag `0xAF0EF4`. A freeze SHALL start only while `0x449F40 == 1`, `0xAE73B4 == 0` and `0xAF0EF4 == 0`. While frozen the flag SHALL be set to 1 again after `sub_00161120` each frame; a game write of another value SHALL be counted, logged and kept as the value to put back. Unfreezing, stopping the camera, the pause menu or retry (`0xAE73B4 != 0`), leaving the stage (`0x449F40 != 1`) or a stage start (`sub_000606F0`) SHALL end the freeze and put the kept value back.

#### Scenario: Freeze and resume
- **WHEN** stage 1 is frozen for several seconds and unfrozen
- **THEN** the timer and the enemies stand still while the camera keeps flying, the log shows `freeze off: 0xAF0EF4=0 (0 game writes while frozen)`, and the stage runs on afterwards
