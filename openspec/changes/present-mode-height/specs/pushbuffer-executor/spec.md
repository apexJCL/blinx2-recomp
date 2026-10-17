## ADDED Requirements

### Requirement: The present extent is the display mode's size
The kernel SHALL resolve the mode word AvSetDisplayMode receives to the frame size of its timing (640x480, 720x480, 1280x720, 1920x1080, 640x576 or 720x576, by the word's timing byte) and record it beside the framebuffer address, pitch and format before the display-mode generation is bumped; a word with an unknown timing byte SHALL record no size and log once, and a pitch that is neither the size's width nor half of it (a field title) in the format's pixels SHALL log once and record no size. The executor's present pick SHALL choose the surface as before and then publish, as the extent a flip shows: the display's width and height when the surface is at the display pitch; the display's width and half its height when the surface is at twice the display pitch (field rendering, one field); and the surface's clip extent when there is no display mode, no recorded size, another pitch, or a surface chosen without one at the display address or in the scanout set. Phase 1's scanout set SHALL accordingly take only picks sized from the display address or the set; a pick made with neither (the largest fresh surface anywhere) SHALL not join it. The extent SHALL therefore not change between a title's screens drawn at different clip heights into buffers of one display mode, and SHALL never exceed the frame the mode defines.

#### Scenario: Menus and races at one size
- **WHEN** a title in a 640x480 mode draws twenty frames at clip 640x464, then twenty at clips 640x480, 640x464 and 640x463 a frame (`nv2a_backend_smoke`, CPU path), flipping between two buffers
- **THEN** every flip presents 640x480, with zero size changes across the transition; on the executor before this change the first twenty present 640x464

#### Scenario: Field buffers keep their height
- **WHEN** a 640x480 mode is set at pitch 2560 and every frame draws a 640x240 surface at pitch 5120 and flips
- **THEN** the pick's extent is 640x240 at pitch 5120 and the field warning prints once; after a surface at pitch 2560 is drawn and flipped the extent is 640x480

#### Scenario: Mode change and an HD mode
- **WHEN** the title sets mode 0x880B0A02 at pitch 5120 at a new address, draws 1280x720 and flips, then sets 0x0801010D at pitch 2560 again
- **THEN** the extents are 1280x720 and then 640x480, and no buffer of the previous mode is picked in between

#### Scenario: Unknown word falls back
- **WHEN** a mode word with a timing byte the table does not know is set
- **THEN** one `[AV]` line says so, no size is recorded, and the pick's extent is the surface's clip extent, as under present-scanout

#### Scenario: Burnout 3 from title to drive
- **WHEN** Burnout 3 runs on D3D11 under Proton with `present.fullscreen` and `RECOMP_FLIP_LOG=1`, from the title screen through the menus and a race
- **THEN** the flip log shows no change of present size from the `[AV] SetDisplayMode` line to the end of the drive, and the picture does not move at the menu-to-race transition on Metal or D3D11

#### Scenario: BLiNX 2 unchanged
- **WHEN** attract, stage1 and story run with `RECOMP_FLIP_LOG=1` on main and on the change
- **THEN** the per-flip `(offset, w, h)` sequences are identical (640x480 throughout, the mode's size), and the goldens pass with the same verdicts on Metal and D3D11 without a re-record
