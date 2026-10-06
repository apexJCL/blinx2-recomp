## Context

The executor decodes the stream and owns surfaces, the fence and the flip on both hosts. `render-vertex-programs` proves decode correctness on the CPU. This change moves rendering to the host GPU on Windows. The bench host is the Linux/Proton host with GE-Proton, so D3D11 means Wine to DXVK/Vulkan.

**Terms.** *Render* is who draws the game's 3D into the frame: the CPU rasteriser (walker + `nv2a_vsh_cpu.c` + the raster in `nv2a_pb_exec.c`), the D3D11 GPU render backend (`src/d3d/nv2a_pb_d3d11.c`; not `src/nv2a/nv2a_pgraph_d3d11.c`, the older MMIO-era translator), or the planned Metal GPU render backend. `RECOMP_PB_BACKEND` selects it: unset is the CPU rasteriser, `d3d11` the GPU backend, `null` the walker alone with nothing drawn. *Present* is how a finished frame reaches the screen: the D3D11 swap chain (d3d11 backend), the Win32 GDI window (`fb_present.c`, CPU path on Windows), or the SDL2 window (`fb_present_sdl.c`, macOS: an accelerated `SDL_Renderer`, Metal by SDL's default on macOS, nothing pins it; the `[PRESENT] window up: SDL <driver> renderer` line records the choice; one `SDL_UpdateTexture` blit per shown frame). On macOS today the GPU only presents; it draws no 3D. SDL2 is never Render: on POSIX it handles Present and controller input (`xinput_device.c`). "SDL2 backend" and "SDL renderer" are not render paths and are not used for them.

## Goals / Non-Goals

**Goals:**
- The title stage at a stable 60 (or 30) fps on Proton, with the CPU path as the oracle.
- The fence, flip and vblank model unchanged from `present-frames`.

**Non-Goals:**
- A macOS GPU render path in the D3D11 rounds. macOS renders on the CPU and presents in the SDL2 window (plus BMP dumps). The Metal GPU render backend is tasks §4, after Proton is playable (spike: `analysis/spikes/metal-backend-feasibility-2026-10-02.md`, local).
- Upscaling, widescreen, or any enhancement beyond hardware.

## Decisions

### pgraph to D3D11, via DXVK on Proton
Alternatives considered:
- **D3D11 via DXVK (chosen).** The toolkit's D3D8->D3D11 layer and HLSL emitters already exist, and Proton runs D3D11 well.
- **Vulkan direct.** Portable, and it would also serve macOS through MoltenVK, but it is much more work, and nothing in the toolkit targets it.
- **GL via `d3d8_gl.c`.** macOS only, and later if at all.
- **Metal on macOS (planned second render backend, tasks §4).** It consumes the same decoded state as D3D11 through the shared NV2A layer (P0/P1, toolkit d050739) and keeps the SDL2 window (P2) as the Present path: it draws into a Metal texture the window blits, or into the window's `CAMetalLayer` drawable directly. Either needs a new handoff: today's `present_copy` only copies finished bytes out of guest memory (task 4.5).
- **Entry-point HLE onto `src/d3d`.** Rejected: it is title-specific, and it loses the fence and flip model that the executor has already proven. It also contradicts the pair-review decision to keep translating XDK D3D.

### The CPU executor stays as the reference
With `RECOMP_PB_BACKEND` unset the executor renders through the CPU path. The acceptance check renders the same pushbuffer segment both ways and compares the dumps.

## Risks / Trade-offs

- [`nv2a_pgraph_d3d11.c` is written for another title] → Resolved by not reusing it: the backend is `src/d3d/nv2a_pb_d3d11.c`, gated on decoded state, not on title IDs.
- [Signed texture filtering (ocean) is not in the toolkit] → Tracked in `render-fidelity`, so this change does not grow without bound.
- [Rendering moves off the ack thread] → The fence write must stay at the release point in stream order. Keep that in the executor, and give the backend draw state only.
