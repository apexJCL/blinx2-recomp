## MODIFIED Requirements

### Requirement: Both GPU backends show the executor's present extent
The D3D11 and Metal backends SHALL take the extent of the frame a flip shows from the executor's present pick (`nv2a_pb_present_state()`, through each backend's `present_extent`) and place it with the shared `nv2a_present_rect`; neither SHALL hold a present size of its own. When the pick's extent exceeds the render target it names, the backend SHALL grow that target to the extent with its existing grow path before the present and show the whole extent, so that Metal, D3D11 and the CPU path show the same rows; when the extent is within the target, the backend SHALL show the extent and not the rest of the target or its grow margin, as before. A change to the pick's rule in the executor therefore reaches both backends and the CPU path alike, and the stock unscaled copy path SHALL be left as it is.

#### Scenario: Grow at present
- **WHEN** a 640x480 mode is set at a buffer only ever drawn with a 320x240 clip, and the title flips (`nv2a_backend_smoke`, Metal on the Mac)
- **THEN** `nv2a_pb_metal_shown` reports target 640x480 and shown 640x480, the 320x240 content at the top left, and the CPU path presents 640x480 of the same buffer

#### Scenario: Crop without a mode unchanged
- **WHEN** the smoke's crop case runs without a display mode (122 flips of a 320x240 clip on a 640x480 target)
- **THEN** `nv2a_pb_metal_shown` still reports target 640x480, shown 320x240, and the CPU state 320x240

#### Scenario: Stock copy untouched
- **WHEN** BLiNX 2's goldens run at stock on D3D11
- **THEN** the `[d3d11] first present` line reads `copy` and the frames match their references as on main; under `present.surface = internal` Burnout 3's swap chain keeps one size from the title screen to the race

#### Scenario: Fix lands in the executor only
- **WHEN** the present-size scan changes (present-scanout)
- **THEN** no file under `src/d3d/` changes, and the Burnout 3 race-start card is steady on Metal and on D3D11 from the same executor change
