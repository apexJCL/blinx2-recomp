## Why

The CPU executor cannot carry a 3D stage. It runs on the NV2A ack thread, it already rasterised 1.14 G pixels with 3D off (run `20261001-213616`), and `render-vertex-programs` adds per-vertex and per-pixel work on top. The title needs real-time vertex programs, register combiners, four texture stages and depth at 640x480 and 60 fps.

Status: the **D3D11 GPU render backend is merged** and is the Proton render path (toolkit rounds ba392b2 to 7b44ad8 and later). The task list in tasks.md was written before that work and has not been re-checked against it. The **Metal GPU render backend for macOS (tasks §4) is merged** too and is the macOS render path (`RECOMP_PB_BACKEND=metal`; toolkit M1 66c173e through the M3 merge dce9962), on top of the shared NV2A state layer (P0/P1) and the SDL2 window (P2, toolkit d050739).

Terms used here and in the other changes: **Render** is who draws the game's 3D into the frame (CPU rasteriser, D3D11 GPU, Metal GPU). **Present** is how a finished frame reaches the screen (SDL2 window with an SDL-accelerated blit on macOS, Metal by SDL's default; the D3D11 swap chain or the Win32 GDI window on Windows/Proton). SDL2 is never Render; on POSIX it handles Present and controller input.

## What Changes

- Render on the GPU: the pushbuffer's pgraph state (transform, combiners, textures, depth, draws) is translated into D3D11 by `src/d3d/nv2a_pb_d3d11.c` (`RECOMP_PB_BACKEND=d3d11`), written for this change on the toolkit's D3D8->D3D11 layer (`d3d8_vsh.c` HLSL emitter, `d3d8_combiners.c`). The plan had been to start from `src/nv2a/nv2a_pgraph_d3d11.c`; that older MMIO-era translator was not reused. Under Proton, D3D11 goes through Wine to DXVK/Vulkan.
- Present the title's colour surface once per FLIP_STALL through the D3D11 swap chain. The executor keeps owning the fence, DMA and flip (`present-frames`).
- Keep the CPU executor as the reference renderer (the CPU render path: `RECOMP_PB_BACKEND` unset).
- macOS: Render stays on the CPU rasteriser; Present is the SDL2 window (`fb_present_sdl.c`, P2) plus BMP dumps. The window's accelerated `SDL_Renderer` (Metal by SDL's default on macOS) only blits the finished frame; the GPU draws no 3D there. A **Metal GPU render backend** is an explicit future task of this change (tasks §4), gated on a playable Proton build.

## Capabilities

### New Capabilities
- `gpu-backend`: how pushbuffer methods drive a host GPU API, and how the result is checked against the CPU reference.

### Modified Capabilities
<!-- none -->

## Impact

- Toolkit: `src/d3d/nv2a_pb_d3d11.c` (the render backend), `src/d3d/d3d8_vsh.c` (HLSL emitter), `src/d3d/d3d8_combiners.c`, `src/kernel/nv2a_pb_exec.c`, and since P0/P1 the shared `src/kernel/nv2a_backend_common.c`. `src/nv2a/nv2a_pgraph_d3d11.c` (written for a Burnout 3 menu profile, `GAME_HAS_FONT_ATLAS`) is untouched; only `nv2a_core.c` and `nv2a_pb_replay.c` use it.
- The D3D11 render backend is Windows/Proton only. The macOS render path (CPU) and present path (SDL2 window) are unchanged until the Metal render backend (tasks §4) starts.
- The vblank and pacer deviations (`deviations-register`) can retire once the backend presents and raises vblank from its own present.
