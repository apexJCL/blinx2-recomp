## ADDED Requirements

### Requirement: Pushbuffer methods drive a host GPU API
On Windows (Proton), the executor SHALL hand transform, combiner, texture, depth and draw state to a pgraph translator that renders through the toolkit's D3D8->D3D11 layer, and SHALL present the title's colour surface once per FLIP_STALL. The CPU executor SHALL remain available as the reference render path (`RECOMP_PB_BACKEND` unset).

#### Scenario: Same frame, two paths
- **WHEN** the same pushbuffer segment is rendered by the CPU oracle and by the GPU render backend
- **THEN** the dumps of the title-stage frame agree within a tolerance stated in design.md

#### Scenario: Fence unchanged
- **WHEN** the GPU render backend is on
- **THEN** the fence word is still written by the executor at each BACK_END_WRITE_SEMAPHORE_RELEASE, in stream order, as `present-frames` requires

### Requirement: macOS renders on the CPU and presents in the SDL2 window
On macOS the build SHALL NOT require a GPU render backend. The CPU executor (pushbuffer walker, CPU vertex-program interpreter, CPU rasteriser) SHALL render every frame into the guest framebuffer. The finished frame SHALL be presented in the SDL2 window (`fb_present_sdl.c`: an accelerated `SDL_Renderer`, Metal by SDL's default on macOS, one `SDL_UpdateTexture` blit per shown frame) and, with `RECOMP_FB_DUMP`, written as BMP dumps. The window's GPU use is Present only and SHALL NOT be described as GPU rendering or as an "SDL2 render backend".

#### Scenario: macOS build
- **WHEN** the macOS arm64 build runs with `RECOMP_PB_EXEC=1 RECOMP_FB_DUMP=...`
- **THEN** it produces the same dumps as before this change, and a `RECOMP_WINDOW_SHOT` taken at `RECOMP_WINDOW_SCALE=1` matches the dump of the flip it shows

### Requirement: Metal GPU render backend for macOS (planned, tasks §4)
When the Metal render backend exists and `RECOMP_PB_BACKEND=metal` is set on macOS, the executor SHALL hand it the same decoded state it hands the D3D11 backend, the backend SHALL draw the game's 3D on the GPU through Metal, and the SDL2 window SHALL remain the Present path. The CPU render path SHALL remain selectable as the oracle.

#### Scenario: Same frame on Metal and on D3D11
- **WHEN** the attract or `@stage1` frames are rendered on macOS with `RECOMP_PB_BACKEND=metal`
- **THEN** they match the Proton D3D11 golden frames within the golden tolerance, at about 30 flips/s
