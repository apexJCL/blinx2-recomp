## Context

Reference design: `enhancements-layer` on `spike/enhancements` (design.md D1 render scale, D2 present, D6 layer, D11 E1; § User Decisions is binding). Code read at toolkit `posix-host/portability` c1fa5a4 and cat `main` 730cfa6; this revision re-read every pixel-addressed site named below.

What exists:
- `src/enhance/` (opt-in `XBOXRECOMP_ENHANCE`, default OFF in the toolkit): `recomp_cfg.c` (TOML subset), `enhance_cfg.c` (env > `<root>/<title>/enhance.toml` > `<root>/enhance.toml` > default; `RECOMP_ENHANCE_CONFIG=<path>|none`). Env keys `RECOMP_ENHANCE_CONFIG`, `RECOMP_RENDER_SCALE`, `RECOMP_DISPLAY_ASPECT` (config tier, only with `RECOMP_ENV_HAVE_ENHANCE_KEYS`, which the toolkit defines PUBLIC on `recomp_env` when the layer is on). `xbox_enhance` links only `recomp_env`. No caller yet; cat builds without it. The toolkit has no "directory of the executable" helper.
- Metal (`nv2a_pb_metal.m`): `surface()` makes one BGRA8 texture per `(color_offset, w, h)` with `w = clip_x + clip_w`, rejects `> 4096`, and uploads the guest bytes into it when `pitch >= w*4` (creation only); `depth_target(w, h)` keyed `(zeta, w, h)`; viewport `{0,0,rt->w,rt->h}`; `rt_texture()` binds an RT by address (low 27 bits) with `tex_scale = 1/src->w` for linear formats, and a target sampled while drawn into goes through the `s_self` copy (`copyFromTexture:toTexture:`, whole texture, same size required); `present_target()` matches the walker's pick by offset and guest `w, h`; `metal_on_flip` runs `write_back` (`bpp = pitch / rt->w`; 32-bit `getBytes` at the guest pitch, 16-bit row by row to R5G6B5; `writes_back = 1`) and then a second `getBytes` for `xbox_FramebufferWindowPresentPixels(px, w, h, w*4, 4)`. The walker calls `on_flip` before `dump_at_flip`/`dump_present_bmp`, so `RECOMP_FB_DUMP*` on Metal read the written-back guest bytes.
- D3D11 (`nv2a_pb_d3d11.c`): same target shape (created empty, no size cap; `rt_self_copy` via `GetDesc` + `CopyResource`); fixed 640x480 `FLIP_DISCARD` swap chain in a resizable `WS_OVERLAPPEDWINDOW` created by `init()` on the ack thread, `wnd_proc` handles `WM_CLOSE` only and `pump()` runs on the ack thread at each flip; `d3d11_on_flip` `CopyResource`s the present RT into the back buffer when sizes match, else `CopySubresourceRegion` of the overlap; `dump_frame` (`RECOMP_DEBUG=d3d11_dump`, the golden source) reads the **back buffer** after that copy; `read_pixel` (1x1 staging copy at guest coordinates, bounds `rt->w/h`) and `px_probe` (eight R32G32B32A32 MRTs sized `rt->w x rt->h`, bound with the draw's DSV) are debug reads. No scissor, no clear rect, polygon offset decoded but not applied, no 2D-class blit.
- SDL presenter (`fb_present_sdl.c`): resizable `SDL_WINDOW_ALLOW_HIGHDPI` window of `640*RECOMP_WINDOW_SCALE` points, a streaming texture re-created whenever the frame's `w, h, bpp` change, `SDL_RenderSetLogicalSize(frame)` (SDL letterboxes with its own float scale) and `SDL_RenderCopy(ren, tex, NULL, NULL)`, `SDL_HINT_RENDER_SCALE_QUALITY "nearest"` set before `SDL_Init`; `RECOMP_WINDOW_SHOT` reads the renderer's output (device pixels) between copy and present. Frames arrive either as a GPU backend's host pixels (`PresentPixels`) or as guest bytes at the walker's pick size (`present_copy`, 640x480 before the first pick).
- Visibility tests: each backend counts samples (D3D11 occlusion query, Metal visibility result buffer) and hands them to the shared tracker (`nv2a_occ`, `nv2a_backend_common.c`): `occ_ready` sums a report's queries into a `uint32_t`, `occ_finish` writes it with `nv2a_report_write` and counts `vis += count != 0`; a late or oversized report completes as `NV2A_OCC_VISIBLE` (0x10000, synthetic).
- Bench: `golden.json` references are all `size [640,480]`; frames are not bit-exact between two runs of the same binary (wall-time content: cloud movie, idle animation, timer phase), so the compare is an exact hash **or** a tolerant compare; `check_present_mismatch` (bench.sh) compares the `[D3D11] flip ... present X walker Y` log fields, not pixels. `RECOMP_PB_FAST_AB` compares the CPU fast and slow rasterisers per batch and is deterministic.
- cat `main.c`: `recomp_env_init()` first on both entry paths; `xbox_path_init(BLINX2_GAME_DIR = "game_files", NULL)`; the macOS path ends in `xbox_HostWindowMain(host_main)`.

## User Decisions (render-scale slice, 2026-10-04)

These answer the three questions the first draft left open and are binding here.

1. **Config location**: `enhance.toml` is runtime configuration (scale, filter, fullscreen, aspect are all read at startup; nothing is compile-time), so it lives **alongside the main executable** and is the initial config load, not in `game_files/`. Precedence stays env > title file > root file > default, with the executable's directory as `<root>` (resolved portably: `_NSGetExecutablePath` on macOS, `GetModuleFileName` on Windows, `/proc/self/exe` on Linux; fall back to the working directory). `RECOMP_ENHANCE_CONFIG` still overrides the path. Principle for later slices: anything needed at compile time is passed as an argument to the build step and may live anywhere; nothing in this slice is.
2. **D3D11 dumps under scale**: no downsample. Defaults are native resolution and 1:1 scaling, upscaling is purely user configuration and goldens run at stock, so a scaled run dumps at host size; golden comparison applies to stock runs only.
3. **`XBOXRECOMP_ENHANCE`**: ON in cat by default, every key at stock.

## Goals / Non-Goals

**Goals**
- `render.scale = N` (1..4) on Metal and D3D11 with no per-title knowledge, identity at N = 1.
- E1 on the SDL presenter and the D3D11 window: nearest/linear/integer filters, resize, borderless fullscreen.
- The enhancements layer gets its first caller, with every value at stock by default, and the stock guarantee (R4) that every later slice inherits.

**Non-Goals**
- Scaling the CPU rasteriser (spike D1 non-goal; memory rule "CPU render low priority").
- Hor+ aspect, FPS modes, the module table/hooks, pokes (later slices of `enhancements-layer`).
- A fullscreen or screenshot hotkey (keyboard handling is parked with `input-selection`).
- The Win32 GDI window (`fb_present.c`, CPU backend on Windows): recorded as a follow-up.
- Scaled goldens: goldens stay stock (decision 7); scaled output is checked by dumps and tests.
- A lazy Metal write-back and a zero-copy Metal present (`render-gpu-backend` 4.9): follow-ups, with the cost measured here.

## Decisions

### R1. Host options live in `nv2a_backend_common`, the layer only fills them
`struct nv2a_host_opts { unsigned render_scale; int present_filter; int fullscreen; }` with `nv2a_host_opts_set(const struct nv2a_host_opts *)` and `const struct nv2a_host_opts *nv2a_host_opts(void)` in `nv2a_backend_common.{c,h}` (library `xbox_kernel`, which the D3D11/Metal backends and `xbox_video` already reach: `fb_present_sdl.c` calls `nv2a_pb_present_state()` today). Zero-initialised = stock (scale 0 reads as 1, filter 0 is `nearest`). The layer (`src/enhance/enhance.c`, `xbox_enhance_init(root, title)`) calls `enhance_cfg_init`, binds and reads `render.scale`, `present.filter`, `present.fullscreen`, validates (scale clamped to 1..4 with a log line; an unknown filter is reported by `enhance_cfg_choice` and falls back to `nearest`), calls `nv2a_host_opts_set`, calls `enhance_cfg_report_unused` and logs once:

`[ENHANCE] render.scale=2 present.filter=linear present.fullscreen=0 (display.aspect=4:3)`

Why not read the keys in the backends: the backends must build and behave identically with the layer off (`XBOXRECOMP_ENHANCE=OFF` is the toolkit default and upstream's shape), and `xbox_enhance` would otherwise become a dependency of `xbox_d3d8`. `xbox_enhance` gains a link to `xbox_kernel` (for the setter); nothing links the other way, so the layer stays a separable extension (decision 5): with it off, the struct is all zeros and every consumer takes its identity branch. Why not the spike's module table now: one consumer, three values; the table comes with the hook slices (aspect, fps). The setter is the seam the table will call later; the per-target mapping struct of spike D6/D9 (`hw, hh, vp_scale_x, ...`) arrives with the aspect slice and will be derived from these options plus the target's shape, so nothing here is thrown away.

The options are set once, on the main thread, before `xbox_HostWindowMain` starts the guest, so the backends (ack thread) and the presenter (main thread) read constants; no locking.

`display.aspect`: read and logged; anything but `4:3` logs `display.aspect=<v> not implemented yet (hor+ is a later slice); using 4:3`. The key exists in the reader already, so a user file that sets it must not be silently ignored.

### R2. Render scale in the GPU backends: host size beside guest size
`RenderTarget` and `DepthTarget` gain `hw, hh`. The cache keys stay `(offset, w, h)` in guest units, and `w, h` keep meaning guest size everywhere they are used today (`nv2a_vp_consts_fill`, `tex_scale`, `present_target`'s match against the walker's `nv2a_pb_present` size, the write-back's `bpp = pitch / w`, `read_pixel`'s bounds after scaling). Host size comes from one pure helper:

`nv2a_host_size(w, h, scale, max_dim, &hw, &hh)`: `hw = w*N`, `hh = h*N`, with N lowered for that surface (to the largest that fits) if `w*N` or `h*N` would exceed `max_dim` (16384 on both APIs for the hardware in use; Metal's own `> 4096` guest-size rejection stays). Per-surface N may then differ (only for a > 4096/N guest surface, which BLiNX 2 does not have); every per-target consumer derives its numbers from the target's own `hw/w`, never from the global N. The one global consumer is the visibility tracker (below).

Sites, Metal and D3D11 alike:

| Site | Change |
|---|---|
| colour/depth allocation | `hw x hh`; a depth target is always requested with its colour target's guest `w, h`, so the two get the same host size |
| viewport | `{0, 0, hw, hh}` (D3D11 `RSSetViewports`, Metal `setViewport`) |
| `nv2a_vp_consts_fill` | unchanged: guest `w, h` (this is what makes scale free for every program, pass-through HUD programs included) |
| RTT `tex_scale` | unchanged `1/w` for linear formats (guest texel units → normalised); swizzled formats are normalised already; the scaled SRV is sampled (supersampled RTT, as xemu) |
| self-copy (`s_self`, `rt_self_copy`) | sized `hw x hh` (Metal: from the source's host size, since `copyFromTexture:toTexture:` needs equal sizes; D3D11: `GetDesc` already copies the source's size); match on `hw, hh` |
| clears | whole target, nothing to do |
| Metal: new RT from guest bytes | guest bytes expanded nearest N× on the CPU (`nv2a_upscale_nearest32`) into a temp buffer, then `replaceRegion` at host size. Creation only, not per frame. At N = 1 the existing direct `replaceRegion` runs |
| Metal: write-back at the flip | host pixels read once (`getBytes` of `hw x hh`), box-filtered to `w x h` (`nv2a_downscale_box32`), then written at the guest pitch (32-bit) or converted to R5G6B5 as today. At N = 1 the existing direct `getBytes` path runs unchanged. The walker's `dump_at_flip`/`dump_present_bmp` run after `on_flip`, so `RECOMP_FB_DUMP*` on Metal stay 640x480 at every scale |
| Metal: window present | `xbox_FramebufferWindowPresentPixels(px, hw, hh, hw*4, 4)` from the same host readback (one `getBytes` per flip serves both). The presenter already re-creates its texture on a size change, so a flip that presents a surface the backend never drew (guest bytes, `w x h`) still shows, at the same destination rectangle |
| Metal: texture cache | unchanged: guest textures are decoded from guest memory at their declared size; the written-back frame is guest-sized as before |
| D3D11: present | see R3 |
| D3D11: `dump_frame` (`d3d11_dump`) | see R3 and R8: the back buffer when the direct copy ran (today's code), the present RT otherwise |
| D3D11: `read_pixel` | guest coordinates multiplied by the target's `hw/w` before the bounds check and the 1x1 copy (debug only) |
| D3D11: `px_probe` | its eight MRTs are allocated at the target's `hw x hh` (they are bound with the draw's DSV, which is host-sized, and D3D11 requires equal dimensions); the probe coordinates are multiplied like `read_pixel`'s (debug only) |
| `trace_stream_out`, `[D3D11-WHITE]` | vertex-stage reads, no pixels, nothing to do |
| visibility tests | `nv2a_occ_set_scale(o, N)` from the backend at init with the global N; `occ_ready`'s summed count is divided by N² (rounded, a non-zero count kept ≥ 1 so "visible" never becomes "hidden"); the synthetic `NV2A_OCC_VISIBLE` fallback is not divided (it is a flag, not a sample count). One place, shared by both backends; lens flares and other tests that compare a count to a threshold keep their meaning |
| lines and points | 1 host pixel wide (thinner relative to the frame); accepted, as xemu partly does |
| scissor, clear rect, polygon offset | not applied by either backend today; if added later they multiply by `hw/w` |
| texture address matching, present pick, `nv2a_pb_present` | guest addresses and guest sizes, unchanged |

Fidelity caveat (spike D1, from xemu): post passes that sample with guest-texel offsets (the time-control blur) cover N× fewer effective pixels and look sharper than retail. It is an enhancement, documented, off by default.

CPU backend: `nv2a_host_opts()->render_scale > 1` with `RECOMP_PB_BACKEND` cpu (or null) logs once `[ENHANCE] render.scale=N ignored: the CPU rasteriser draws into guest memory at the guest size` and renders at 1×. E1 still applies to its window (SDL presenter).

### R3. E1: present filter, resize, fullscreen
One pure helper decides where a frame goes in an output: `nv2a_present_rect(src_w, src_h, dst_w, dst_h, filter, &rect)`:
- `nearest`, `linear`: the largest rectangle of the frame's aspect that fits, centred (a letterbox).
- `integer`: the largest whole multiple `k ≥ 1` of the frame that fits, centred; if even `k = 1` does not fit (a 2× frame in a smaller window), it falls back to the fitted rectangle, scaled down with linear filtering, rather than cropping.

The frame's aspect is its own (`w:h`); for BLiNX 2 that is 4:3 at every scale, so present aspect stays correct. Sizes are device pixels: the SDL renderer's output size (2× the window's points on a Retina display, because of `SDL_WINDOW_ALLOW_HIGHDPI`) and the D3D11 client size.

**SDL presenter** (`fb_present_sdl.c`, macOS/Linux, every backend). The stock path is today's code, call for call: `SDL_RenderSetLogicalSize(frame)` and `SDL_RenderCopy(ren, tex, NULL, NULL)` with the `nearest` hint. The branches are:
- `linear`: the same logical-size path plus `SDL_SetTextureScaleMode(tex, SDL_ScaleModeLinear)` when the texture is created (SDL ≥ 2.0.12, which the build uses).
- `integer`: no logical size (`SDL_RenderSetLogicalSize(ren, 0, 0)` once, at start); the destination rectangle from `nv2a_present_rect` with `SDL_GetRendererOutputSize`, recomputed when the output size or the frame size changes; the texture's scale mode is `nearest`, switched to linear only while the fallback applies. `SDL_RenderSetIntegerScale` is not used because it crops when the frame does not fit.
- `present.fullscreen = true`: the window is created `SDL_WINDOW_FULLSCREEN_DESKTOP` (borderless, no mode change). Window size at start otherwise stays `640*RECOMP_WINDOW_SCALE` points.
Why not route every filter through `nv2a_present_rect`: SDL's logical-size letterbox rasterises a float-scaled quad, so an integer destination rectangle could differ from it by an edge row or column, and "the stock window is unchanged" would rest on a rounding argument instead of on unchanged code. The window shot reads what is shown, as today.

**D3D11 window** (`nv2a_pb_d3d11.c`): `wnd_proc` handles `WM_SIZE` by recording the new client size (the window belongs to the ack thread, which created it in `init()` and pumps it in `pump()` at each flip, so no cross-thread hand-off is needed); the flip calls `ResizeBuffers` before its next present when the recorded size differs from `s_back_w x s_back_h`, releasing `s_back` first and re-acquiring it after. The flip then:
- if the present RT is `s_back_w x s_back_h` (host size) and the filter is `nearest` or `integer` with k = 1: today's `CopyResource`, and `dump_frame` reads the back buffer, as today (the stock path, unchanged code);
- otherwise: clear the back buffer to black and draw a full-screen triangle sampling the RT's SRV (created on demand, as `rt_texture` does) into `nv2a_present_rect`'s viewport, with a point or linear sampler; one small VS/PS pair compiled at init with the existing `D3DCompile` path; `dump_frame` reads the present RT (R8).
`present.fullscreen = true`: the window is created `WS_POPUP` at the primary monitor's size (`GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)`; there is no `HWND` yet to ask `MonitorFromWindow`), and the swap chain is sized to it. No exclusive fullscreen (Proton and `FLIP_DISCARD` handle borderless best). Window title and `FrameStats` are untouched.

The swap chain at stock stays 640x480: under scale it is created at the window's client size, and the window's initial client size stays 640x480 (a later key may size it; out of scope), so a 2× frame in an unresized window is shown downscaled until the user resizes or sets fullscreen. A window manager that resizes the window at creation (seen under some compositors) moves a stock run onto the blit path; that is harmless for the goldens because the dump then reads the RT (R8), whose bytes are what the back buffer would have received. `check_present_mismatch` compares log fields and is unaffected; it is re-run on Proton (task 4.5).

### R4. The stock guarantee: what changes at scale 1, and how it is proven
With every key at its default and `XBOXRECOMP_ENHANCE` built in, the code that runs differs from `main` only in these places:
- cat `main.c` calls `xbox_enhance_init`, which reads `<exe dir>/enhance.toml` if present (the bench pins `RECOMP_ENHANCE_CONFIG=none`, so no file is read in a golden run), prints the `[ENHANCE]` line and stores three constants.
- The env table has two more config keys (docs count).
- Metal `surface()`, `depth_target()`, `write_back()`, the window readback and the presenter take their `N == 1` / default branches, which are the existing code; the new helpers are not called at N = 1 except `nv2a_host_size`, which returns its inputs.
- D3D11 `d3d11_on_flip` takes the `CopyResource` branch under the same condition as today (sizes equal) with `dump_frame` reading the back buffer; `wnd_proc` additionally records `WM_SIZE`, which only matters if the window is resized.
- The visibility tracker divides by 1.
- The CPU rasteriser and `RECOMP_PB_FAST_AB` run code that this change does not touch.

Why "byte-identical goldens" is not the gate as literally worded: `golden.json` records that two runs of the same binary are not bit-exact (wall-time content), so no frame comparison between `main` and this branch can be required to be exact. Byte identity is required where the pipeline is deterministic, and the frame gate is the golden verdicts:
1. `tests/render_scale` asserts the identity of every helper at N = 1 and of `nv2a_present_rect` for a frame that fits exactly (`rect == {0, 0, dst_w, dst_h}`), and `nv2a_occ` at scale 1 returns counts unchanged.
2. `RECOMP_PB_FAST_AB` on the CPU backend (attract, 60 s) reports zero mismatches on this branch, as on `main`: the deterministic path is byte-identical.
3. Metal goldens `@attract`, `@stage1`, `@story` pass with the same verdicts as `main` (exact or within the same limits), on the layer-ON build, with the pins in `golden.json`; the reported mae/bad-fraction numbers are recorded beside `main`'s in the task.
4. `golden.py` reads the run log and marks the run FAIL when an `[ENHANCE] render.scale=` value other than 1 appears (or `display.aspect` other than 4:3), so a stray user environment or file can never pass as a golden.
5. The review (task 9.1) checks the diff for the identity branches listed above: every new statement in the backends and the presenter is behind `scale > 1`, a non-default filter, `fullscreen`, or a size mismatch.
6. D3D11 on Proton (task 4.5): the same goldens and `check_present_mismatch`, same verdicts as `main`.

### R5. How CPU, D3D11 and Metal stay in agreement
- Render scale: Metal and D3D11 implement the same table (R2) with the same pure helpers (`nv2a_host_size`, `nv2a_present_rect`, `nv2a_occ` scaling) from `nv2a_backend_common`, so the numbers cannot drift; both read the same `nv2a_host_opts`. The CPU path is excluded by design (it rasterises into guest memory at the guest pitch; an N× CPU path is N² slower and nobody asked for it) and says so in its one log line and in docs: a user on the CPU backend gets 640x480 frames with the key set, not an error, so a shared `enhance.toml` works on every backend. Metal is verified on the Mac in this change; D3D11 is built (llvm-mingw) and its Proton verification is an open task that blocks the "verified" claim for the D3D11 half, not the merge of the Metal half.
- E1: the SDL presenter serves every backend on macOS/Linux; the D3D11 window serves D3D11 on Windows/Proton; both use `nv2a_present_rect`, so integer mode places the frame identically. The Win32 GDI window (`fb_present.c`, CPU backend on Windows: `StretchDIBits` of a fixed `640x480`) gets neither filters nor resize here; it is a TASKS.md follow-up ("E1 for the GDI window: `nv2a_present_rect` in `WM_PAINT`, `WM_SIZE`, `HALFTONE` for linear"), low priority with the CPU path.

### R6. Settings
New config-tier keys in `recomp_env.h` (under `RECOMP_ENV_HAVE_ENHANCE_KEYS`, like the existing three), following the layer's naming rule (`RECOMP_` + dotted key):
- `RECOMP_PRESENT_FILTER` → `present.filter` (`nearest` default, `linear`, `integer`)
- `RECOMP_PRESENT_FULLSCREEN` → `present.fullscreen` (bool, default off)
`RECOMP_RENDER_SCALE` exists. Each gets a `docs/env.md` row in cat (with the three existing layer keys, which have none yet) and a row in `docs/runtime/enhance-config.md`. All default to stock. `RECOMP_WINDOW_SCALE` keeps its meaning (initial SDL window size in points).

### R7. cat wiring and the config root
- `CMakeLists.txt`: `set(XBOXRECOMP_ENHANCE ON CACHE BOOL "build the enhancements layer (enhance.toml, RECOMP_RENDER_SCALE, ...)")` before `add_subdirectory` of the toolkit: ON by default (user decision 3; the title opts in, as the toolkit's docs say), not `FORCE`, so `-DXBOXRECOMP_ENHANCE=OFF` on the configure line still builds a layer-free binary for A/B.
- `main.c`: under `#ifdef RECOMP_ENV_HAVE_ENHANCE_KEYS` (the toolkit defines it PUBLIC on `recomp_env` when the layer is on), `xbox_enhance_init(recomp_exe_dir(), NULL)` right after `recomp_env_init()` on both entry paths. The title argument is NULL: one title per executable, so `<exe dir>/enhance.toml` is the file (user decision 1); `RECOMP_ENHANCE_CONFIG=<path>|none` overrides as before.
- `recomp_exe_dir()` is a toolkit helper (`src/platform/recomp_exe_dir.c`, library `platform`): `_NSGetExecutablePath` + `realpath` on macOS, `GetModuleFileNameA` on Windows (a Wine path such as `Z:\...` is what `fopen` wants there), `readlink("/proc/self/exe")` on Linux; the directory part, cached; the working directory when none works. The layer's `[ENHANCE] config:` line already names the files it read, so the resolved root is visible in every log.
- `golden.json` global env adds `RECOMP_ENHANCE_CONFIG=none` and `RECOMP_RENDER_SCALE=1`; `scripts/bench.sh integrate` runs through golden.py and inherits them. The present keys need no pin: the dump source is independent of the window on every backend (Metal/CPU dump guest bytes; D3D11 dumps the back buffer or the RT before any filter).

### R8. Dumps under scale (user decision 2)
A scaled run dumps at host size: D3D11 `d3d11_dump` frames are `hw x hh` BMPs with unchanged names (the BMP header carries the size, `run-info.txt` carries `RECOMP_RENDER_SCALE`); the window shot is the output size as always. Metal and CPU `RECOMP_FB_DUMP*` are guest bytes and stay 640x480 (the written-back frame). Golden comparison applies to stock runs only (`golden.py` fails a scaled run by size and by the `[ENHANCE]` check); scaled output is checked by eye and by the 2× comparison pair in `runs/enh-scale/`. A `golden.py` downsample option for A/B of a scaled run is a later nicety, not needed now.

## Verification plan

- Stock identity (R4): `tests/render_scale` identity cases; `RECOMP_PB_FAST_AB` attract 60 s on the CPU backend, zero mismatches; Metal goldens `@attract`, `@stage1`, `@story` with the same verdicts as `main` and the numbers recorded; `golden.py` `[ENHANCE]` check exercised once with `RECOMP_RENDER_SCALE=2` (must FAIL) and once at stock (must not); a stock `RECOMP_WINDOW_SHOT` whose letterbox rectangle (black border geometry) matches `main`'s.
- 2× on Metal: `RECOMP_RENDER_SCALE=2` attract and stage1, 120 s each, no crash; window shots at 1× and 2× of the same flip saved as a comparison pair under `xbox-recomp/runs/enh-scale/`; `fb_dump_at` frames at 2× are 640x480 and compare with the golden references within their limits (`golden.py` on that dump dir); flips/s and the `[PRESENT]` ack-copy and upload ms at 1× and 2× (and 4× for the readback cost) from `RECOMP_PRESENT_STATS=1`, plus the `[PB-PERF]` flip time.
- E1 on the SDL presenter: window shots with each filter in a resized window (one each), fullscreen once; `integer` at a 1920x1080 output shows a 640x480 frame at 1280x960 centred.
- Unit: `tests/render_scale` (ctest, standalone like `tests/nv2a_tex`, which already compiles `nv2a_backend_common.c` alone) for `nv2a_host_size`, `nv2a_present_rect`, `nv2a_downscale_box32`, `nv2a_upscale_nearest32`, the occlusion count scaling; `tests/enhance_cfg` gains cases for the new keys and for `recomp_exe_dir()` (non-empty, is a directory).
- D3D11 (Proton, later): the same goldens at stock plus `check_present_mismatch`; 2× attract dump is 1280x960 and sharper; each filter in a resized window; fullscreen; flips/s 1× vs 2×; Burnout 3 menu at stock and 2× (upstream gate for the common and D3D11 parts).

## Risks / Trade-offs

- [Write-back downsample and window readback cost CPU per flip at N > 1] → one `getBytes` of `hw x hh` (4.9 MB at 2×, 19.7 MB at 4×) serves window and write-back; the box filter is a tight loop (~1.2 M pixels at 2×); the presenter's slot copy and `SDL_UpdateTexture` scale with N² too. Measured in the perf task; a lazy write-back and the zero-copy `CAMetalLayer` present are the follow-ups if the numbers warrant.
- [Visibility counts at N²] → divided in the shared tracker; a test whose count is near its threshold may flip by rounding; acceptable for an opt-in mode.
- [D3D11 code unverified this round] → built with llvm-mingw; Proton verification is task 4.5 and blocks the D3D11 half's "verified" claim, not the Metal half.
- [A compositor resizes the D3D11 window at start] → the blit path runs at stock; the dump reads the RT (same bytes), so the goldens hold; the log's `[D3D11]` first-flip line names the back-buffer size so a run shows it happened.
- [`integer` mode on SDL uses its own rectangle] → only that mode leaves SDL's logical-size path; the default path is unchanged code (R3).
- [The exe directory is the build directory during development] → a developer's `enhance.toml` sits in `build/`; `RECOMP_ENHANCE_CONFIG=<path>` points elsewhere, and the `[ENHANCE] config:` line shows which file was read.
- [Upstream declines the extension] → the core-side seam is one zero-default struct and pure helpers; with the layer absent nothing calls the setter and the backends are identity.

## Open Questions

None. The three questions of the first draft are answered under § User Decisions (render-scale slice).
