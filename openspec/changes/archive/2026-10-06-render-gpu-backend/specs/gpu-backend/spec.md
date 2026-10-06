## ADDED Requirements

### Requirement: Pushbuffer methods drive a host GPU API
The executor SHALL hand transform, combiner, texture, depth and draw state to a GPU render backend selected with `RECOMP_PB_BACKEND`: D3D11 on Windows and under Proton (`d3d11`, through the toolkit's D3D8->D3D11 layer; DXVK under Proton), Metal on macOS (`metal`). The backend SHALL present the title's colour surface once per FLIP_STALL. The CPU executor SHALL remain available on every host as the reference render path (`RECOMP_PB_BACKEND` unset or `cpu`).

#### Scenario: Same frame, two paths
- **WHEN** the same pushbuffer segment is rendered by the CPU path and by a GPU render backend
- **THEN** the dumps of the title-stage frame agree within that frame's golden limits (`analysis/golden/golden.json`), apart from differences recorded as CPU-path defects

#### Scenario: Fence unchanged
- **WHEN** a GPU render backend is on
- **THEN** the fence word is still written by the executor at each BACK_END_WRITE_SEMAPHORE_RELEASE, in stream order, as `pushbuffer-executor` requires

### Requirement: The CPU render path presents in the host window
With the CPU render path, the executor (pushbuffer walker, CPU vertex-program interpreter, CPU rasteriser) SHALL render every frame into the guest framebuffer. The finished frame SHALL be presented in the host window (on POSIX the SDL2 window, `fb_present_sdl.c`: an accelerated `SDL_Renderer` and one `SDL_UpdateTexture` blit per shown frame; on Windows the Win32 GDI window) and, with `RECOMP_FB_DUMP`, written as BMP dumps. The window's GPU use is Present only and SHALL NOT be described as GPU rendering or as an "SDL2 render backend".

#### Scenario: macOS CPU build
- **WHEN** the macOS arm64 build runs with `RECOMP_PB_BACKEND` unset and `RECOMP_FB_DUMP=...`
- **THEN** it produces the CPU path's dumps, and a `RECOMP_WINDOW_SHOT` taken at `RECOMP_WINDOW_SCALE=1` matches the dump of the flip it shows

### Requirement: Metal GPU render backend for macOS
With `RECOMP_PB_BACKEND=metal` on macOS, the executor SHALL hand the Metal backend the same decoded state it hands the D3D11 backend, and the backend SHALL draw the game's 3D on the GPU through Metal and present it in the SDL2 window. The CPU render path SHALL remain selectable as the reference.

#### Scenario: Same frame on Metal and on D3D11
- **WHEN** the attract or `@stage1` frames are rendered on macOS with `RECOMP_PB_BACKEND=metal`
- **THEN** they match the Proton D3D11 golden frames within the golden tolerance, at about 30 flips/s
