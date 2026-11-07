## Why

With `camera.free` on, the ground's shadows stay where the game camera puts them on screen while the free camera moves (reported 2026-11-05 on every renderer). The cause is in the swap of decision D1 of `free-camera`. The view builders `sub_000292A0` and `sub_0021B1F0` see the free camera. But `sub_00042E50` also reads the camera struct: it writes the screen projection `c[116..119]` from the camera's angles and eye. It runs again between builds, from `stage_render` (0x685C7), `sub_000348A0`, the HUD queue drain and other passes. By then the swap has put the game's fields back. So the shadows' screen-space buffer is drawn with the free view, but it is laid on the ground with the game's view.

This is not a regression. The swap has not changed since the free camera merged (0b3bee18), and `RECOMP_DEBUG=cam_fix`, which uses the same swap, shows the same thing.

The tracker item follows up on D2. It covers the render-path readers of the struct that run outside the builds: the stage pass `gfx_stage_pass_e58d0`, `sub_001F73C0`, `sub_001D72E0`, `sub_000DAEC0`, `sub_001A6E00` (the radar), `sub_0004D740` and the effect draw pass `sub_0015BC40`. It also covers the sky that is lost on a long flight. Those draws stayed on the game camera, as the shadows did. The radar's view cone already followed the free camera; its dots read the struct's yaw and did not.

## What Changes

- cat `src/recomp_manual.c`: a wrapper on `sub_00042E50` gives it the same swap as the builds. It is not counted or logged as a build, and inside a build the depth counter leaves the build's swap in place. The generated body is regenerated as `sub_00042E50_gen` (`blinx2 analyze`, then `recomp`).
- The tracker item: wrappers in the same form go on the readers that draw relative to the camera. They are `sub_000E58D0` (the stage pass, with its eye-centred sky dome and its eye-relative callees), `sub_001F73C0`, `sub_000DAEC0`, `sub_0004D740`, `sub_001A6E00` and `sub_0015BC40`. `sub_001D72E0` is reached only under a swap. The effect step under the stage pass keeps the game's random sequence (D3). Design D3 gives each verdict, and D4 explains why the stage 1 sky still disappears on a long flight.
- With the free camera off and no `cam_fix` or `cam_log`, the wrapper calls the generated body directly, as the builders' wrappers do: stock is unchanged.

## Capabilities

### Modified Capabilities
- `free-camera`: the "Free camera toggle" requirement now names the camera readers that get the swap, not only the two builders.

## Impact

- cat only: `src/recomp_manual.c`, the regenerated `src/recomp/gen/`, and the `free-camera` spec, and the `RECOMP_CAMERA_FREE` row of `docs/env.md`. No toolkit change, no new env key.
