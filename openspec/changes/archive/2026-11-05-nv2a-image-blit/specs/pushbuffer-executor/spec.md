## ADDED Requirements

### Requirement: The 2D engine's image blits are executed
The executor SHALL decode the methods of the 2D objects on subchannels other than 0, following xemu's pgraph:
- `SET_OBJECT` (method 0) SHALL bind the class named by the first word of the object's instance (bits 7:0), found through RAMHT as a context DMA is. With no bind seen, the class SHALL be XDK D3D's fixed layout: Kelvin on 0, NV09F IMAGE_BLIT on 2, NV062 CONTEXT_SURFACES_2D on 3. A subchannel bound to an object whose class can't be read (not in RAMHT, or outside guest memory) SHALL be class 0, so its methods go unhandled. A RAMHT hit MAY be kept per handle, provided the entry is reread and still names the handle on each use.
- NV062 SHALL keep the source and destination context DMA objects (0x0184, 0x0188), the colour format (0x0300), the pitches (0x0304: source in bits 15:0, destination in bits 31:16) and the offsets (0x0308, 0x030C, 27 bits). NV09F SHALL keep the operation (0x02FC), the source and destination points (0x0300, 0x0304: x in bits 15:0, y in bits 31:16) and the size (0x0308); a size with a non-zero width and height SHALL run the blit. NV012 beta (0x0300) SHALL keep the BLEND_AND factor.
- A blit SHALL place each surface at its context DMA object's base plus its offset, SHALL be refused when it ends past an object's limit or outside guest memory, and SHALL write nothing then. SRCCOPY and BLEND_AND (32-bit pixels) SHALL be performed; any other operation or a colour format with no size SHALL be refused, with one log line.
- The executor SHALL hand each blit to the backend's `on_blit` hook. A backend without one (the CPU rasteriser) SHALL get the copy in guest memory, and the texture cache SHALL recheck the destination.
- Any other method off subchannel 0 SHALL stay counted as unhandled.

#### Scenario: Quantum Redshift's frame copy
- **WHEN** Quantum Redshift runs a race to flip 7500 on Metal
- **THEN** the log shows the binds `subchannel 2 ... class 0x9F` and `subchannel 3 ... class 0x62`, a 640x480 R5G6B5 blit from 0x007C4000 to 0x00A1C000 each frame, and the lens raindrops refract the frame instead of drawing black (runs/qrs-rain/blit-metal43-after)

#### Scenario: Decode and limits (ctest)
- **WHEN** `tests/pb_image_blit` binds the objects through RAMHT on subchannels 5 and 6 and runs a 64x16 blit between two context DMA objects
- **THEN** the rectangle lands at the destination's base plus offset with every byte around it untouched, a blit past the destination's limit writes nothing, and a stub backend's `on_blit` gets the blit resolved while the executor writes nothing

#### Scenario: Unread classes and the RAMHT cache (ctest)
- **WHEN** `tests/pb_image_blit` binds subchannel 2 to a handle that is not in RAMHT, rebinds a known handle, and moves an object's RAMHT entry
- **THEN** the unread bind is class 0 and launches no blit, subchannel 3 keeps the layout's class, the rebind is a kept-slot hit with no scan, and the moved entry is scanned for and still blits
