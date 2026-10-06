## ADDED Requirements

### Requirement: Metal frames reach the window without a CPU round trip
When `RECOMP_PB_BACKEND=metal` runs with a window on macOS, the window SHALL show each published frame by drawing it from GPU memory: a blit of the present render target into a presenter slot texture, then a draw into a `CAMetalLayer` drawable on the window. No CPU readback or upload of the frame SHALL occur. The presenter SHALL own the Metal device and command queue and the backend SHALL adopt them, so the slot textures and the ordering of the blit and the draw are on one queue. The window SHALL keep the stock and enhancement present behaviour of the SDL presenter:
- the nearest, linear and integer filters, with geometry from `nv2a_present_rect`;
- letterboxing on resize, HiDPI and borderless fullscreen;
- vsync per `RECOMP_PRESENT_VSYNC`;
- `RECOMP_WINDOW_SHOT`;
- the title bar;
- dropping an unshown frame instead of making the walker wait: the walker SHALL never block on drawable acquisition, and a drawable the window cannot get SHALL leave the frame to the next pass.

`RECOMP_DEBUG=metal_present=readback` SHALL restore the readback present. If the layer cannot be created, the presenter SHALL fall back to the `SDL_Renderer` window and the backend to the readback present, and log which path is in use. A surface the backend never drew SHALL still reach the window, uploaded from guest bytes.

#### Scenario: No per-frame readback
- **WHEN** `@stage1` runs windowed on Metal at render scale 1, 2 or 3 with `RECOMP_TRACE=metal_prof`
- **THEN** the prof line reports zero readback and zero hand-off copy time, and no `getBytes` runs on the flip path

#### Scenario: Present parity
- **WHEN** window shots are taken at the same flip in layer mode and in readback mode, for the stock window and for each filter in a resized window, in fullscreen and at render scale 2
- **THEN** the frame rectangle matches within 1 pixel and the pixels match within the golden limits of that frame

#### Scenario: Fallback
- **WHEN** the CAMetalLayer view cannot be created (for instance under `SDL_VIDEODRIVER=dummy`)
- **THEN** the run continues with the SDL renderer window and the readback present, the `[PRESENT] window up:` line says so, and its `fb_dump_at` frames match the golden

### Requirement: Metal writes guest memory only when it is read
The Metal backend SHALL NOT copy the present surface into guest memory at every flip. The executor SHALL call the backend's `sync_guest` hook, on the ack thread, before it reads a surface's guest bytes, and the backend SHALL then write that surface back with the per-flip code used before this change: guest-sized, box-filtered at render scale > 1, 32-bit or R5G6B5 at the guest pitch. The executor reads a surface for `fb_dump_at`, `RECOMP_FB_DUMP_FLIPS`, the report dump and surface dumps. A surface that is clean (written back since it was last drawn into) SHALL NOT be written again. The backend SHALL also write a dirty render target back before it hashes or decodes overlapping guest memory as a texture, and before it evicts a dirty target that was presented. `RECOMP_DEBUG=metal_writeback=always`, and `metal_no_rtt`, SHALL restore the write-back at every flip. Backends without the hook (CPU, D3D11, null) SHALL behave as before.

#### Scenario: Goldens unchanged
- **WHEN** the attract, stage1 and story goldens run on Metal with the default write-back and with `metal_writeback=always`
- **THEN** every frame gets the same verdict as on `main`, the dumps are 640x480, and under the default the write-back count equals the number of distinct dumped flips

#### Scenario: No write-back without a reader
- **WHEN** Metal runs with no `fb_dump` prefix set
- **THEN** the backend performs no guest write-back of the present surface during the run

#### Scenario: Sync on demand in the smoke test
- **WHEN** `nv2a_backend_smoke` draws a scene and flips under the default write-back
- **THEN** the guest bytes still hold the seed and the write-back count is 0; after `sync_guest` they equal the CPU rasteriser's frame and the count is 1; a second `sync_guest` leaves the count at 1

### Requirement: CPU reads of the framebuffer follow D3D11
Under the default write-back, a title's own CPU reads of its present surface SHALL see the bytes of the last write-back, if there was one, as under the D3D11 backend, which never writes back. `RECOMP_DEBUG=metal_fb_guard` SHALL detect the first title access to the last present surface and log the accessing thread and code address once; a read SHALL switch the run to `metal_writeback=always`, a write SHALL be logged and ignored.

#### Scenario: Guard on BLiNX 2
- **WHEN** `@stage1` and `@story-hub` run with `metal_fb_guard`
- **THEN** no title read is reported, the one write (the host allocator clearing re-allocated memory) is logged without a mode switch, matching the probe's measurement in design.md
