## MODIFIED Requirements

### Requirement: The CPU render path presents in the host window
With the CPU render path, the executor (pushbuffer walker, CPU vertex-program interpreter, CPU rasteriser) SHALL render every frame into the guest framebuffer. The finished frame SHALL be presented in the host window (on POSIX the SDL3 window, `fb_present_sdl.c`: an `SDL_Renderer` with vsync per `RECOMP_PRESENT_VSYNC`, a streaming texture whose scale mode is set to nearest explicitly because SDL3's default is linear, letterboxed by `SDL_SetRenderLogicalPresentation`, and one `SDL_UpdateTexture` blit per shown frame; on Windows the Win32 GDI window) and, with `RECOMP_FB_DUMP`, written as BMP dumps. The window's GPU use is Present only and SHALL NOT be described as GPU rendering or as an "SDL render backend". `RECOMP_WINDOW_SHOT` SHALL read the renderer back through `SDL_RenderReadPixels` and write the same BMP bytes as before the SDL3 move. The same renderer block serves Metal's readback present, which is how it is verified while the CPU backend stays out of the routine gates.

#### Scenario: macOS CPU build
- **WHEN** the macOS arm64 build runs with `RECOMP_PB_BACKEND` unset and `RECOMP_FB_DUMP=...`
- **THEN** it produces the CPU path's dumps, and a `RECOMP_WINDOW_SHOT` taken at `RECOMP_WINDOW_SCALE=1` matches the dump of the flip it shows

#### Scenario: Stock filter is nearest
- **WHEN** a window shot is taken at `RECOMP_WINDOW_SCALE=2` in Metal readback mode with no enhancement filter set
- **THEN** every 2x2 block of the shot is one dump pixel (no interpolated values), and with `present.filter=linear` it is not

### Requirement: Metal GPU render backend for macOS
With `RECOMP_PB_BACKEND=metal` on macOS, the executor SHALL hand the Metal backend the same decoded state it hands the D3D11 backend, and the backend SHALL draw the game's 3D on the GPU through Metal and present it in the SDL3 window. The CPU render path SHALL remain selectable as the reference.

#### Scenario: Same frame on Metal and on D3D11
- **WHEN** the attract or `@stage1` frames are rendered on macOS with `RECOMP_PB_BACKEND=metal`
- **THEN** they match the Proton D3D11 golden frames within the golden tolerance, at about 30 flips/s

### Requirement: Metal frames reach the window without a CPU round trip
When `RECOMP_PB_BACKEND=metal` runs with a window on macOS, the window SHALL show each published frame by drawing it from GPU memory: a blit of the present render target into a presenter slot texture, then a draw into a `CAMetalLayer` drawable on the window obtained through `SDL_Metal_CreateView` and `SDL_Metal_GetLayer`, sized from `SDL_GetWindowSizeInPixels`. No CPU readback or upload of the frame SHALL occur. The presenter SHALL own the Metal device and command queue and the backend SHALL adopt them, so the slot textures and the ordering of the blit and the draw are on one queue. The window SHALL keep the stock and enhancement present behaviour of the SDL presenter:
- the nearest, linear and integer filters, with geometry from `nv2a_present_rect`;
- letterboxing on resize, HiDPI (`SDL_WINDOW_HIGH_PIXEL_DENSITY`, with `SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED` resizing the drawable) and borderless fullscreen;
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
- **WHEN** the CAMetalLayer view cannot be created (for instance under `SDL_VIDEO_DRIVER=dummy`)
- **THEN** the run continues with the SDL renderer window and the readback present, the `[PRESENT] window up:` line says so, and its `fb_dump_at` frames match the golden
