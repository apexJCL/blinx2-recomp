## Why

The user decided (spike `enhancements-layer`, branch `spike/enhancements`, design.md § User Decisions, 2026-10-04) to start the enhancements layer once the build is stable, with the extras taken easiest first: E1, E2, E4, E6, E7, then E3/E5. This change is the first slice: **internal render scale** (spike D1) plus **E1, window resize, fullscreen and present filtering** (spike D2 / D11), because render scale needs a presenter that can show a frame larger than 640x480 and E1 is the rest of that presenter work.

The broader layer design (module table, hor+ aspect, FPS modes, pokes, Lua assessment) stays in the spike's `enhancements-layer` change as the reference; this change does not re-derive it and does not implement it. The config reader it builds on has landed in the toolkit (`enhance/config`, merged at toolkit 409a8e8 and 042715f: `XBOXRECOMP_ENHANCE`, `src/enhance/`, `enhance.toml`, `RECOMP_ENHANCE_CONFIG`, `RECOMP_RENDER_SCALE`, `RECOMP_DISPLAY_ASPECT`), but nothing calls it yet, and cat does not build it.

Today every Metal and D3D11 render target, depth target and viewport is guest-sized; the SDL window letterboxes a 640x480 frame with nearest filtering only; the D3D11 window is a fixed 640x480 swap chain that does not follow a resize.

## What Changes

- **Render scale** (`render.scale`, env `RECOMP_RENDER_SCALE`, 1..4, default 1). The Metal and D3D11 backends allocate colour and depth targets at N× the guest clip size, set the viewport to that size and keep the pixel-to-NDC constants (`nv2a_vp_consts_fill`) on the guest size, so every program lands where it did, at N× the pixels. Every pixel-addressed path follows (design R2 lists each site): render-target creation from guest bytes (upscaled), the Metal write-back to guest memory (box-downsampled to guest size, so `RECOMP_FB_DUMP`, `fb_dump_at` and the title see 640x480), the window present (host size), self-copies, the D3D11 pixel probes (coordinates and their own targets), and visibility-test counts (divided by N², so the title's thresholds hold). The CPU rasteriser ignores the key and logs once (it draws into guest memory at the guest pitch).
- **E1: present filter, resize, fullscreen** (`present.filter = nearest | linear | integer`, `present.fullscreen = true|false`, env `RECOMP_PRESENT_FILTER`, `RECOMP_PRESENT_FULLSCREEN`; defaults `nearest`, `false`). SDL presenter (macOS and Linux, every backend including CPU): per-texture scale mode for `linear`, an integer-multiple destination rectangle for `integer`, borderless desktop fullscreen at start; the default path is today's code, call for call. D3D11 window: `WM_SIZE` → `ResizeBuffers`, a scaling present blit when the frame and the swap chain differ in size or the filter is `linear`, borderless fullscreen. At stock (scale 1, window not resized) D3D11 keeps today's `CopyResource` into a 640x480 back buffer and today's back-buffer dump.
- **The layer's first caller**: a toolkit `xbox_enhance_init(root, title)` (`src/enhance/enhance.c`) that loads the config, reads the render and present keys and hands them to the backends through a small host-options setter in `nv2a_backend_common` (so `xbox_d3d8`, `xbox_kernel` and `xbox_video` never link `xbox_enhance`). cat turns `XBOXRECOMP_ENHANCE` on and calls it from `main.c` before the guest starts, with the executable's directory as the config root (user decision, design § User Decisions (render-scale slice)).
- **Bench**: `golden.json` pins `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_RENDER_SCALE=1`, and `golden.py` fails a run whose log shows a non-stock `[ENHANCE] render.scale` (goldens always run at stock, decision 7).

Not in this change: hor+ aspect (`display.aspect` stays 4:3; a non-4:3 value is logged as not implemented), FPS modes, the module table and hooks, pokes, a fullscreen hotkey (keyboard is parked with `input-selection`), the Win32 GDI window (`fb_present.c`, CPU backend on Windows), a lazy Metal write-back, a zero-copy Metal present.

## Capabilities

### New Capabilities
- `enhancements`: render scale and present scaling/window handling (the first two requirements of the spike's `enhancements` capability, narrowed to what this slice builds), plus the stock-behaviour guarantee every later slice inherits.

### Modified Capabilities
- (none) The `deviations-register` rows for render scale are added when that change lands; this change notes the deviation in docs.

## Impact

- **Render backends**: Metal (implemented and verified on macOS in this change), D3D11 (implemented and cross-built; Proton verification is a task left open, the Linux/Proton host is in use by another agent), CPU (key ignored, documented; E1 applies through the SDL presenter).
- **Hosts**: macOS (Metal, SDL presenter), Proton (D3D11 window). Linux native SDL gets E1 for free. Windows CPU backend (GDI window) gets nothing yet (follow-up).
- **Goldens**: none change. attract, stage1 and story must pass with the same verdicts at stock on Metal (and on D3D11 once Proton runs); golden.json gains the two stock pins; the dump source is independent of the window on every backend, so the present keys need no pin.
- **Toolkit** (`posix-host/portability` via `enhance/render-scale`): `src/enhance/enhance.{c,h}` (new), `src/platform/recomp_exe_dir.c` (new: the executable's directory, for the config root), `src/kernel/nv2a_backend_common.{c,h}` (host options, scale and present-rect helpers, occlusion count scaling), `src/d3d/nv2a_pb_metal.m`, `src/d3d/nv2a_pb_d3d11.c`, `src/video/fb_present_sdl.c`, `src/platform/recomp_env.h` (two keys), `docs/runtime/enhance-config.md`, new ctest `tests/render_scale`, cases in `tests/enhance_cfg`. Upstream: per the user's decision, the layer is offered upstream later as a separate opt-in extension, not core; the only core-side seam is the identity-default `nv2a_host_opts` struct and the pure helpers in `nv2a_backend_common` (title-agnostic, identity when unset), which go in that extension's PR set with the D3D11 changes (Burnout 3 gate then). The SDL presenter and Metal parts are fork-only until those are upstreamed.
- **cat**: `CMakeLists.txt` (`XBOXRECOMP_ENHANCE` defaults ON, still overridable), `src/main.c` (one guarded call), `docs/env.md` rows, `analysis/golden/golden.json` pins, `scripts/golden.py` (the `[ENHANCE]` log check), `TASKS.md` follow-ups.
