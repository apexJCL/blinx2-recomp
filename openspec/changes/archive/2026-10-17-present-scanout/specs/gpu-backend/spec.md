## ADDED Requirements

### Requirement: Both GPU backends show the executor's present extent
The D3D11 and Metal backends SHALL take the extent of the frame a flip shows from the executor's present pick (`nv2a_pb_present_state()`, through each backend's `present_extent`) and place it with the shared `nv2a_present_rect`; neither SHALL hold a present size of its own. A change to the pick's rule in the executor therefore reaches both backends and the CPU path alike, with no backend change, and the stock unscaled copy path SHALL be left as it is.

#### Scenario: Fix lands in the executor only
- **WHEN** the present-size scan changes (present-scanout)
- **THEN** no file under `src/d3d/` changes, and the Burnout 3 race-start card is steady on Metal and on D3D11 from the same executor change

#### Scenario: Stock copy untouched
- **WHEN** BLiNX 2's goldens run at stock on D3D11
- **THEN** the `[d3d11] first present` line reads `copy` and the frames match their references as on main
