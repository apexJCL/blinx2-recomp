## ADDED Requirements

### Requirement: The present size scan covers every buffer the title scans out
The executor SHALL keep a scanout set: the offsets of the surfaces the last `present_stale` flips presented (compared as physical addresses, as the display address is), cleared when the display-mode generation changes. When a display mode is set, the size scan of the present pick SHALL take the largest fresh surface at the display address or at any scanout offset, at the display pitch (or the field pitch when that rule is in force); with none fresh, the largest stale one there still sets the size and leaves no candidate, as before. Of that size, the newest draw since the last flip SHALL still win, else the newest clear, else the screen stays. When the surface table is full, eviction SHALL take the least recently used entry that is not at a scanout offset or the display address at that pitch, and only when every entry is such an entry the least recently used of all. The table SHALL hold at least 32 entries. Without a display mode, the pick SHALL be as before (the largest fresh surface anywhere). A pick's size SHALL therefore not change between two flips of a double-buffered title whose frames draw the same clip extents into each buffer, however many offscreen surfaces a frame touches.

#### Scenario: Double-buffered title with three clip extents a frame
- **WHEN** the display is at A and each frame draws into A or B in turn at clip extents 640x480, 640x464 and 640x463, and also into 19 offscreen surfaces, then flips (`nv2a_backend_smoke`, CPU path)
- **THEN** from the third flip, eight consecutive flips present the buffer drawn that frame at 640x480; on the executor before this change the size alternates 640x480 and 640x464

#### Scenario: Single-buffered title with many offscreen surfaces
- **WHEN** the display is at A and each frame draws into A at 640x480, into 19 offscreen surfaces, then into A at 640x464, and flips
- **THEN** eight consecutive flips present A at 640x480, because A's entries are spared eviction

#### Scenario: Display-mode change clears the set
- **WHEN** after presenting from A and B the title sets a display mode at C, a frame draws into A at 1280x720 and into C at 640x480, and flips
- **THEN** the pick is C at 640x480: A's larger entry no longer sets the size

#### Scenario: A table of protected entries still evicts
- **WHEN** the display is at A and a frame draws into A at 40 distinct clip extents, then at 640x480, and flips
- **THEN** the pick is A at 640x480 and the executor neither stalls nor asserts; plain LRU applied once every entry was protected

#### Scenario: Burnout 3 race-start card
- **WHEN** a Burnout 3 race starts on Metal (Mac) or D3D11 under Proton with a scaling present (`present.fullscreen`, `present.surface = internal`, a filter or `render.scale > 1`)
- **THEN** every flip across the race-start card presents 640x480 and the picture does not move on screen; after the race loads the flip log shows no change of present size to the end of the drive

#### Scenario: BLiNX 2 unchanged
- **WHEN** attract, stage1 and story run with `RECOMP_FLIP_LOG=1` and `RECOMP_PRESENT_TRACE=1` on main and on the change
- **THEN** the per-flip `(offset, w, h)` sequences are identical, the protected-eviction count is 0, and the goldens pass with the same verdicts on Metal and D3D11 without a re-record
