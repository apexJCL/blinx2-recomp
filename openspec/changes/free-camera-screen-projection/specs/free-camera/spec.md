## MODIFIED Requirements

### Requirement: Free camera toggle
With `camera.free = "on"` (env `RECOMP_CAMERA_FREE`), the key `camera.free_toggle` (default `F6`, env `RECOMP_CAMERA_FREE_TOGGLE`) SHALL start and stop a free camera in any state where the game camera `[0x4B271C]` exists. Starting SHALL seed the free camera from the game's: position from the eye at `+0x2C..+0x34`, pitch `+0x0C`, yaw `+0x10`, roll and the extra angles 0. While it is active, the wrappers on the view builders `sub_000292A0` and `sub_0021B1F0`, on the screen projection `sub_00042E50` (`c[116..119]`, also called between builds), and on the draws that read the camera outside the builds (the stage pass `sub_000E58D0`, `sub_001F73C0`, `sub_000DAEC0`, `sub_0004D740`, the radar `sub_001A6E00` and the effect draw pass `sub_0015BC40`), SHALL write the free camera's fields into the struct (shake offset 0, eye = position), call the generated function, and put back each field that still holds the value written in; they SHALL act only when the camera is `[0x4B271C]`, and only in the outermost of nested calls. Stopping SHALL return the next build to the game's camera with nothing else to restore. If the game frees its camera (`[0x4B271C] == 0`), the free camera SHALL stop.

#### Scenario: Fly away and come back
- **WHEN** stage 1 runs on Metal with `RECOMP_CAMERA_FREE=on`, the toggle is pressed, the camera turns and moves, and the toggle is pressed again
- **THEN** the log shows `on at (x y z)` equal to the game camera's eye, the frames show the stage from the moved camera, and after the second press the frames are the game's view and the game camera reacts to the right stick again

#### Scenario: Shadows stay on the ground
- **WHEN** the free camera moves or turns over the shadowed ground in stage 1
- **THEN** the shadows stay where they lie on the ground, moving on screen with the ground, not with the game camera

#### Scenario: Camera-relative draws follow the free camera
- **WHEN** the free camera turns or moves away from the game camera
- **THEN** the radar turns with the free camera, the billboards and particles face it, and in split screen, where the stage pass centres the sky dome on the eye, the dome stays around it. A world-fixed sky, such as stage 1's, stays where the level puts it.

#### Scenario: Off by default
- **WHEN** the key is unset
- **THEN** the toggle does nothing and the builders, the screen projection and the wrapped draws run as the generated code
