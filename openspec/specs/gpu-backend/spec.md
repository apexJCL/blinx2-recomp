# gpu-backend Specification

## Purpose
Defines how the pushbuffer executor's decoded state drives a host GPU API (D3D11 on Windows and Proton, Metal on macOS), how frames reach the window, and how the GPU paths are checked against the CPU reference path and the golden frames.

## Requirements

### Requirement: Pushbuffer methods drive a host GPU API
The executor SHALL hand transform, combiner, texture, depth and draw state to a GPU render backend selected with `RECOMP_PB_BACKEND`: D3D11 on Windows and under Proton (`d3d11`: a direct D3D11 backend, `nv2a_pb_d3d11.c`, with its own device and swap chain, that reuses the D3D8 layer's vertex-program (`d3d8_vsh.c`) and combiner translators; DXVK under Proton), Metal on macOS (`metal`). The backend SHALL present the title's colour surface once per FLIP_STALL. The CPU executor SHALL remain available on every host as the reference render path (`RECOMP_PB_BACKEND` unset or `cpu`).

#### Scenario: Same frame, two paths
- **WHEN** the same pushbuffer segment is rendered by the CPU path and by a GPU render backend
- **THEN** the dumps of the title-stage frame agree within that frame's golden limits (`analysis/golden/golden.json`), apart from differences recorded as CPU-path defects

#### Scenario: Fence unchanged
- **WHEN** a GPU render backend is on
- **THEN** the fence word is still written by the executor at each BACK_END_WRITE_SEMAPHORE_RELEASE, in stream order, as `pushbuffer-executor` requires

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

### Requirement: Metal writes guest memory only when it is read
The Metal backend SHALL NOT copy the present surface into guest memory at every flip. The executor SHALL call the backend's `sync_guest` hook, on the ack thread, before it reads a surface's guest bytes, and the backend SHALL then write that surface back with the code the per-flip write-back used: guest-sized, box-filtered at render scale > 1, 32-bit or R5G6B5 at the guest pitch. The executor reads a surface for `fb_dump_at`, `RECOMP_FB_DUMP_FLIPS`, the report dump and surface dumps. A surface that is clean (written back since it was last drawn into) SHALL NOT be written again. The backend SHALL also write a dirty render target back before it hashes or decodes overlapping guest memory as a texture, and before it evicts a dirty target that was presented. `RECOMP_DEBUG=metal_writeback=always`, and `metal_no_rtt`, SHALL restore the write-back at every flip. Backends without the hook (CPU, D3D11, null) SHALL behave as before.

#### Scenario: Goldens unchanged
- **WHEN** the attract, stage1 and story goldens run on Metal with the default write-back and with `metal_writeback=always`
- **THEN** every frame gets the same verdict as with `metal_writeback=always` (the write-back at every flip), the dumps are 640x480, and under the default the write-back count equals the number of distinct dumped flips

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

### Requirement: Every render path keeps one target per surface, clears its clear box and presents the frame

A GPU backend SHALL keep one render target per guest surface (colour offset
and pitch), as large as any clip the title drew it with, keeping its contents
when it grows; a backend that seeds targets from guest memory SHALL seed the
grown margin the same way. Every render path (CPU, D3D11, Metal) SHALL bound
a colour clear by the surface clip and, once the title has sent
SET_CLEAR_RECT, by the clear rect, and SHALL leave the rest of the target as
it was. A flip SHALL present only the walker's present extent of the target,
and the walker's pick SHALL NOT change: a surface is still the colour offset
at a clip size, fresh for PRESENT_STALE_FLIPS (120) FLIP_INCREMENT_WRITEs.

#### Scenario: One back buffer, several clips

- **WHEN** a title draws its 640x480 back buffer under a 160x120 clip at
  (100, 100) and clears it there
- **THEN** Metal keeps one 640x480 target for the surface, and only the clip
  changes colour, on Metal and on the CPU path alike

#### Scenario: Clear rect

- **WHEN** a clear is sent with a clear rect of (300, 300)-(339, 339) inside a
  640x480 clip
- **THEN** only that rect changes colour, on every path

#### Scenario: Grown target keeps its contents and seeds its margin

- **WHEN** a surface drawn under a 320x240 clip is then cleared under a
  640x480 clip with a clear rect covering only (320, 240)-(639, 479)
- **THEN** Metal grows the target to 640x480; the 320x240 drawn before the
  grow, the cleared rect, and the guest bytes elsewhere all read as the CPU
  path leaves them

#### Scenario: Grown target, smaller frame

- **WHEN** a target grown to 640x480 is presented after the title draws only
  320x240 for more than 120 flips counted at FLIP_INCREMENT_WRITE
- **THEN** the flip shows 320x240, and the target is still 640x480

#### Scenario: Whole-clip clears take the stock path

- **WHEN** a title clears a surface whose clip is the whole target and has
  sent no clear rect, or one covering the clip
- **THEN** Metal clears it with the pass's load action, as before this change

### Requirement: A visibility-test report is settled before the title can read it
The GPU backends SHALL complete every pending visibility-test report (NV097 `GET_REPORT`) before the title can read it: at the end of each walk, before GET is stored; before a `BACK_END_WRITE_SEMAPHORE_RELEASE` that follows the report; and at the flip. They SHALL do it through one shared routine in the tracker (`nv2a_occ_settle`, `nv2a_backend_common.c`; `nv2a_occ_flip` at the flip). The executor calls it through the backend's `on_poll` at the first two points. At the flip, the D3D11 backend calls it after its `Present` and the Metal backend after its flip wait.

The routine SHALL work in three steps:
1. Take every result that is in, with a flush.
2. Wait for the rest while the frame's budget lasts. The budget is `occ_settle_us` (debug tier), counted per frame across all of that frame's settles. The default is 8000 µs on both backends; 0 means no wait.
3. Write each report still pending as complete (status 0) with the last completed count for that report address. The count must be younger than 250 ms. When the address has no such count, write the visible fallback (`NV2A_OCC_VISIBLE`).

A settled report's late result SHALL update only the address's last count and SHALL never be written to the report. A late result SHALL never replace the count of a newer report at the same address.

Reports already settled SHALL be polled without a flush. An `on_poll` with nothing pending SHALL only poll those.

The settle SHALL change nothing for:
- a report whose result is in by then;
- the `sync` and `fixed` modes;
- the CPU and null paths;
- the supersede, overflow and 250 ms rules;
- the render-scale division of counts.

`occ_delay_us` (debug tier) SHALL hold every result back by that many microseconds on both backends, for tests. Both backends' flip lines under `RECOMP_TRACE=flip` SHALL report the settles (`settled N (stale M, first K)`).

#### Scenario: Pending at a settle, with history
- **WHEN** a report at address A is pending at a settle, and A has a completed count younger than 250 ms from an earlier report (`tests/occ_reports`, fake ops)
- **THEN** the settle writes that count with status 0
- **AND** when the GPU result arrives later, the report words are unchanged, and a status the title has since reset stays reset
- **AND** the next report at A pending at a settle reads the late result (one frame stale)

#### Scenario: Pending at a settle, no history
- **WHEN** the first report at an address is pending at a settle, or the address's last count is older than 250 ms
- **THEN** the settle writes `NV2A_OCC_VISIBLE` with status 0 and counts it as `first`

#### Scenario: Result in within the budget
- **WHEN** a report's result comes in within the frame's remaining `occ_settle_us`
- **THEN** the real count is written and nothing is settled

#### Scenario: A budget a frame
- **WHEN** one settle in a frame has spent the budget
- **THEN** the frame's later settles take what is in without waiting, and the flip starts a new budget

#### Scenario: Injected latency reproduces the fault and the fix
- **WHEN** BLiNX 2 idles on the Story Mode / LOAD GAME screen (`@story-idle`) with `RECOMP_DEBUG=occ_delay_us=16000` and `RECOMP_TRACE=flip`, on Metal (Mac) and on D3D11 (Deck)
- **THEN** on the executor before this change thousands of flips draw 157 batches (the characters skipped)
- **AND** with the change every flip after the first with the screen up draws at least 1400 batches (`scripts/occ_flips.py` exit 0), and the settled reports are all `stale` but the first few

#### Scenario: Stock goldens unchanged
- **WHEN** attract, stage1 and story run on Metal (Mac) and on D3D11 under Proton with `RECOMP_TRACE=flip`
- **THEN** the goldens pass with the same verdicts without a re-record, at flips/s within the 25% rule
- **AND** the per-scenario `settled` totals are recorded; with the default budget most reports get their exact count

#### Scenario: Burnout 3 race
- **WHEN** a Burnout 3 race runs on Metal and on D3D11 under Proton (15-20 visibility tests a flip)
- **THEN** the race gate passes on both and no report is left pending across a walk or a flip

### Requirement: Both GPU backends show the executor's present extent
The D3D11 and Metal backends SHALL take the extent of the frame a flip shows from the executor's present pick (`nv2a_pb_present_state()`, through each backend's `present_extent`) and place it with the shared `nv2a_present_rect`; neither SHALL hold a present size of its own. When the pick's extent exceeds the render target it names, the backend SHALL grow that target to the extent with its existing grow path before the present and show the whole extent, so that Metal, D3D11 and the CPU path show the same rows; when the extent is within the target, the backend SHALL show the extent and not the rest of the target or its grow margin, as before. A change to the pick's rule in the executor therefore reaches both backends and the CPU path alike, and the stock unscaled copy path SHALL be left as it is.

#### Scenario: Grow at present
- **WHEN** a 640x480 mode is set at a buffer only ever drawn with a 320x240 clip, and the title flips (`nv2a_backend_smoke`, Metal on the Mac)
- **THEN** `nv2a_pb_metal_shown` reports target 640x480 and shown 640x480, the 320x240 content at the top left, and the CPU path presents 640x480 of the same buffer

#### Scenario: Crop without a mode unchanged
- **WHEN** the smoke's crop case runs without a display mode (122 flips of a 320x240 clip on a 640x480 target)
- **THEN** `nv2a_pb_metal_shown` still reports target 640x480, shown 320x240, and the CPU state 320x240

#### Scenario: Stock copy untouched
- **WHEN** BLiNX 2's goldens run at stock on D3D11
- **THEN** the `[d3d11] first present` line reads `copy` and the frames match their references as on main; under `present.surface = internal` Burnout 3's swap chain keeps one size from the title screen to the race

#### Scenario: Fix lands in the executor only
- **WHEN** the present-size scan changes (present-scanout)
- **THEN** no file under `src/d3d/` changes, and the Burnout 3 race-start card is steady on Metal and on D3D11 from the same executor change

### Requirement: A render target never outlives the title's use of its memory
The Metal and D3D11 backends SHALL NOT bind a render target as a texture, SHALL NOT write a render target back into guest memory, and SHALL NOT draw into a cached render target, when the title has written that target's guest memory (its full pitch x height, through the low 27 bits of its address) since the backend last read or wrote those bytes. Such a target SHALL be dropped without a write-back; a dropped target that the title draws into again SHALL be recreated from the title's bytes. A newly created target SHALL retire every other target whose guest range overlaps it in whole or in part, written back first when its memory is unchanged. A target drawn in the current flip is always valid. Each target's bytes SHALL be rehashed at most once per flip.

#### Scenario: Hub targets do not reach stage 1
- **WHEN** the title draws 512x512 targets in the hub, then loads stage 1 into the same memory, and a stage-1 texture starts at one of their addresses
- **THEN** the texture is decoded from guest memory (the CPU path's texels), and a guest memory dump of the block taken after the stage's first texture decodes equals one taken at stage start and the CPU path's dump at the same flip

#### Scenario: A smaller target inside an old one
- **WHEN** the title creates a 256x256 target whose memory lies inside a 512x512 target it has stopped drawing and has since overwritten
- **THEN** the old target is dropped without a write-back, and the new target is seeded from the title's bytes

#### Scenario: Render-to-texture still works
- **WHEN** the title draws a target in a flip and samples it in the same or a later flip without writing its memory
- **THEN** the target's rendered image is sampled, as before

#### Scenario: A CPU write before a draw
- **WHEN** the title writes a target's memory from the CPU between two draws into it
- **THEN** the next draw starts from the written bytes, not from the earlier rendered image

#### Scenario: A/B switch
- **WHEN** `RECOMP_DEBUG=rt_alias_check=0` is set
- **THEN** both backends behave as before this change

### Requirement: R8B8 textures decode on every texel path
The shared texel decode SHALL decode NV097 texture format 0x29 (`SZ_R8B8`, swizzled) and its linear twin 0x16 (`LIN_R8B8`) as two bytes per texel, unsigned. The low byte is B and the high byte is R. Expanded to A8R8G8B8, R and A SHALL take the high byte and G and B the low byte, matching xemu's `GL_RG8` (G, R, R, G) table entry (GL and Vulkan) and Cxbx-Reloaded's `____R8B8ToARGBRow_C` (B, G, R, A = byte 0, byte 0, byte 1, byte 1). The Metal and D3D11 backends and the CPU sampler SHALL all decode it through this one table, so the three paths produce the same texels. The `SET_TEXTURE_FILTER` SIGNED bits are not applied, as for every other format today.

#### Scenario: Known texels
- **WHEN** a linear R8B8 texel holds the bytes `AB 12`
- **THEN** it decodes to `0x1212ABAB`, while G8B8 on the same bytes decodes to `0x12AB12AB`

#### Scenario: Swizzled level
- **WHEN** a 2x2 swizzled R8B8 level holds `01 10 02 20 03 30 04 40`
- **THEN** it decodes, row-major, to `0x10100101, 0x20200202, 0x30300303, 0x40400404` and occupies 8 bytes

#### Scenario: Spartan's lookup table is no longer magenta
- **WHEN** Spartan: Total Warrior binds its 256x256 R8B8 texture at 0x80720E00 during boot, on Metal or D3D11
- **THEN** no `texture format 0x29 ... not decoded: drawn magenta` line is logged and the texture is uploaded from guest memory

#### Scenario: Titles without the format are unchanged
- **WHEN** BLiNX 2 or Burnout 3 runs with the change
- **THEN** no texel it samples differs from main's, because neither title binds 0x29 or 0x16 (their main runs log no `not decoded` format at all) and every other decode case is untouched

### Requirement: Bump-environment texture stages are sampled on both GPU backends
A texture stage in texture-shader mode 6 (`BUMPENVMAP`) or 7 (`BUMPENVMAP_LUMINANCE`) SHALL be sampled by the D3D11 and Metal backends at `(s, t) + M * (du, dv)`, where `(du, dv)` are the input stage's blue and green taken from unsigned bytes back to two's complement over 127 (xemu's `sign3`), `M` is the stage's bump matrix, and the offset is added in the coordinate's own units before the stage's `tex_scale`. Mode 7 SHALL further scale all four channels of the sampled texel by `input.red * BUMP_ENV_SCALE + BUMP_ENV_OFFSET`. The input stage SHALL be stage 0 for stage 1 and the stage named by bits 16-19 and 20-23 of `SET_SHADER_OTHER_STAGE_INPUT` for stages 2 and 3, clamped to an earlier stage, through one shared helper. The four matrix registers (`SET_TEXTURE_SET_BUMP_ENV_MAT`, 0x1B28..0x1B34 of the stage) SHALL be read as m00, m01, m11, m10, so `du' = m00*du + m10*dv` and `dv' = m01*du + m11*dv`; this order is one hardware fact held in the shared decode and generators, never in a per-title quirk. The HLSL and MSL generators SHALL emit the same arithmetic, and the stock text for every other mode SHALL be unchanged. The CPU rasteriser keeps sampling these modes as plain 2D, recorded as a gap.

#### Scenario: Decode and constants
- **WHEN** a stage's register block holds `(a, b, c, d)` at offsets 0x28..0x34, `e` at 0x38 and `f` at 0x3C
- **THEN** `nv2a_stage_decode` yields `bump = {a, b, c, d}`, `bump_scale = e`, `bump_offset = f`, and `nv2a_ps_consts_fill` places them in `bump[n]` and `bumpls[n].xy` for both backends

#### Scenario: Generated text, both languages
- **WHEN** stage 1 is in mode 6 fed by stage 0 and stage 2 in mode 7 fed by stage 1, with `bump_on` set
- **THEN** the HLSL and the MSL each contain the two dot products on `bump[n].xw` and `bump[n].yz`, the 127 divisor, the offset added before `tex_scale`, and for stage 2 the luminance scale on the whole texel; the MSL compiles with Metal on the Mac; the same state without `bump_on` emits the plain 2D sample

#### Scenario: Water on a second title
- **WHEN** BLiNX 2's stage-1 ocean (attract and stage1 scenarios) and Boss 3 ripple are drawn on Metal and on D3D11
- **THEN** the water regions change against main's references while nothing else in the frame moves beyond its run-to-run spread, the error against the xemu captures does not rise, and the two backends agree within the golden limits

#### Scenario: Slots a frame can confirm
- **WHEN** the `bump` trace logs the matrices BLiNX 2 and Burnout 3 write
- **THEN** a diagonal matrix counts as confirming slot 2 only; the transpose of slots 1 and 3 is counted as confirmed by frame only if a title writes a matrix with `m01 != m10` and that scene matches xemu under the m00, m01, m11, m10 reading, otherwise it stays open in TASKS

### Requirement: Anisotropic filtering follows one rule on both backends
With `render.aniso = N` (2..16) set, the D3D11 and Metal samplers SHALL use anisotropic filtering with `MaxAnisotropy = N` only for a stage whose texture has more than one mip level, whose minification filter is linear, whose mip filter is not none, that is not a cube map, and when point sampling is not forced; min, mag and mip filters SHALL be linear under it on both backends. Every other stage SHALL keep the stock sampler. The anisotropy SHALL be part of each backend's sampler key in the same bit position (35), and SHALL be read at start.

#### Scenario: World sharper, screen-aligned content unchanged
- **WHEN** the stage-1 fly-over runs with `RECOMP_RENDER_ANISO=16` on Metal and on D3D11
- **THEN** a window shot shows the ground sharper at grazing angles than at stock, and the HUD, render targets read back and movie frames are unchanged

#### Scenario: Off by default
- **WHEN** no key is set
- **THEN** no sampler on either backend is anisotropic and the `[ENHANCE]` line reads `render.aniso=0`

### Requirement: Clip-plane texture stages kill pixels on every render path
On a draw through the register combiners, a texture stage in mode 5 (CLIPPLANE) SHALL kill the pixel on the D3D11 and Metal backends exactly as on the CPU path (`stage_clip_kills`). On a draw without combiners, stage 0 in mode 5 SHALL kill the pixel on both backends by the same rule. Each of the four components of the stage's interpolated coordinate SHALL discard the pixel at `>= 0` or at `< 0`, as SET_SHADER_CLIP_PLANE_MODE (0x17F8) selects for that stage and component. The stage's register SHALL still read 0. A draw with no CLIPPLANE stage SHALL produce the same pixels as before.

#### Scenario: Smoke scene on Metal
- **WHEN** `nv2a_backend_smoke` draws a quad whose stage-0 coordinate crosses 0 along x, with stage 0 in CLIPPLANE mode, once for each sign setting
- **THEN** the Metal frame equals the CPU path's frame: the half of the quad on the killed side is not drawn

#### Scenario: Draw without combiners
- **WHEN** `nv2a_backend_smoke` (Metal) and `d3d11_backend_smoke` draw the same quads with COMBINER_CONTROL 0 and stage 0 in CLIPPLANE mode, once for each sign setting
- **THEN** the basic shader kills from `clip_mode.x` the way xemu does, and the four probes show the killed half missing on each quad
- **AND** the CPU path is not the reference here: its no-combiner rasteriser kills only a textured stage 0, a gap recorded as a follow-up in TASKS.md

#### Scenario: Goldens unchanged
- **WHEN** the attract, stage1 and story goldens run on Metal and, under Proton, on D3D11
- **THEN** every frame keeps its verdict, since no BLiNX 2 scene seen so far uses mode 5

### Requirement: A blit from a render target is copied on the GPU
On Metal and D3D11, a SRCCOPY blit whose source is a live render target of the blit's pixel size, whose destination pitch holds the source's width (`dst_pitch >= w * bpp`; a whole copy into another pitch included), and which does not overlap it, SHALL be copied texture to texture. The destination SHALL become a render target with the source's guest size, pads, host size, render scale and format and the blit's destination pitch, marked `copy` until a draw or clear uses it, with the flip of the blit that filled it; one already there with that geometry SHALL be refilled. A blit across the whole guest width from x 0 to x 0 SHALL take the Hor+ pads with it; a narrower one SHALL copy its guest columns at the render scale. Targets over the destination other than that one SHALL be written back and retired first; when every slot is taken (`RT_MAX`, 16 on both backends), the least recently used target other than the source SHALL be written back and evicted for the twin. A target the title has rewritten from the CPU SHALL be dropped instead of written back, as everywhere else (`rt_drop_if_stale`).

Any other blit SHALL run in guest memory: a guest source; a partial blit with no such target to land in; BLEND_AND. Both backends SHALL write a source target back first, so the guest copy holds the frame and not the bytes from before it was drawn, and SHALL write back and retire the targets over the destination, so a partial blit keeps the rest of what it lands in. Metal writes back through `rt_sync`, which it uses for every lazy write-back. D3D11, which writes nothing back anywhere else, SHALL do it in `blit_write_back`: one synchronous staging copy and Map per target, box-filtered down to guest pixels at a render scale above 1, packed to the target's format with its constant bits (`nv2a_surf_pack_row`: X 1 for O1R5G5B5, the fixed alpha of the X8R8G8B8 and X1A7R8G8B8 formats). Because D3D11 targets are not seeded from guest memory, D3D11 SHALL write back only bytes the target holds: the source's blit rectangle, and a target over the destination only when a clear covered the whole of it since it was made or grown (`full`); a target drawn in part SHALL be dropped with no write-back, as before. That stall SHALL happen only on this path, never on a twin copy. Metal's write-back SHALL pack the same constant bits. The texture cache SHALL rehash the destination before its next bind. Each backend SHALL count the two paths in its present summary (`2D blits N target copies, M in guest memory`), printed only once a blit has happened.

The retire SHALL NOT be gated by `render.rt_alias_check`: it writes the target back first, so nothing is lost, and a target left over the destination would shadow what the blit wrote.

#### Scenario: The frame copy stays on the GPU
- **WHEN** Quantum Redshift runs to flip 7500 on Metal, and on D3D11 natively on Windows
- **THEN** every blit is a target copy (`0 in guest memory`), the copy at 0x00A1C000 is bound as a render target by the raindrop draws, and the frame matches between the two backends

#### Scenario: BLiNX 2's display-buffer copies
- **WHEN** BLiNX 2 runs its golden scenarios, which blit the 640x480 A8R8G8B8 frame (fmt 0xA) from 0x03268000 or 0x0313C000 to 0x000E7040, the framebuffer AvSetDisplayMode set, at flips 764, 890, 892, 3959 and 3971 (runs/qrs-rain/b2-golden)
- **THEN** each blit is a target copy into a twin at 0x000E7040, the present summary counts them (`2D blits 1 target copies, 0 in guest memory`), and the goldens are unchanged on Metal and on D3D11

#### Scenario: Backend smoke cases
- **WHEN** `nv2a_backend_smoke` (Metal) and `d3d11_backend_smoke` (native Windows) run their blit cases
- **THEN** a whole blit makes a twin that samples the source's image and a second one refills it with no new target; the twin is a copy in its blit's flip only, and not once drawn into; with every slot taken the twin evicts the oldest target, written back; a target over the destination is written back and retired; a partial blit with no twin copies from the source written back, and over a target of another size keeps the rest of what it held; a target and a source drawn in part keep the guest bytes they never drew; an R5G6B5 twin is written back packed; a destination pitch wider than the source's stays on the GPU and is written back at its own pitch; and at render.scale 2 under 16:9 a whole blit copies the pads, a partial one its guest columns only

### Requirement: Dot-product texture stages and cube maps are sampled on both GPU backends
The D3D11 and Metal backends SHALL generate the NV2A texture shader's dot-product modes (8 to 0x12) with xemu's arithmetic, in the stages each mode may occupy (`nv2a_dot_mode_ok`). A mode outside those stages SHALL be sampled as 2D.

- Each dot stage i SHALL compute `dot(T_i.xyz, map(input texel))`. The input stage SHALL come from `nv2a_stage_input`. `map` SHALL be the stage's field of `SET_DOT_RGBMAPPING` (0x1E74), which the executor keeps: with x the byte value, 1 is xemu's sign1 `(x - 128)/127`, 2 is sign2 `x >= 128 ? (x - 255.5)/127.5 : (x + 0.5)/127.5`, 3 is sign3 (two's complement over 127), and the other values pass the texel through.
- DOTPRODUCT SHALL keep its mode when its stage is disabled, since it reads no texture. It, DOT_ZW, BRDF and DOT_RFLCT_SPEC_CONST SHALL read 0.
- DOT_ST, DOT_STR_3D and DPNDNT_AR/GB SHALL read 2D, under the stage's `tex_scale`.
- DOT_RFLCT_DIFF, DOT_RFLCT_SPEC (the eye vector from T1.w, T2.w, T3.w) and DOT_STR_CUBE SHALL read a cube.

A stage whose mode reads a cube (CUBEMAP included), that is bound, and whose texture is a square `CUBEMAP_ENABLE` texture SHALL be decoded as six faces. Face f SHALL be decoded at `offset + f * nv2a_stage_face_stride`. Each backend SHALL cache it as one entry keyed as a cube, and SHALL bind it as a cube texture, but only for the combiners' shader. A batch on the basic shader SHALL read face 0 as 2D. A cube whose six-face span overlaps a live render target SHALL NOT be bound as a cube: its key, shader and bind SHALL take the 2D read on both backends, from the target where one starts at its offset. A cube-reading mode over a 2D texture SHALL read it at `remapCubeTo2D`.

The key (`nv2a_ps_stage_key`) SHALL hold the modes, the input stages, the dot mappings and the cube bits in the same layout on both backends. The MSL and HLSL generators SHALL emit the same arithmetic. The text for every state without a dot mode or a bound cube SHALL be unchanged. The CPU rasteriser keeps sampling these modes as 2D, recorded as a gap.

#### Scenario: Quantum Redshift's water
- **WHEN** Quantum Redshift's track-2 water, stage program 0x64621 with `SET_DOT_RGBMAPPING` 0x111, is drawn on Metal
- **THEN** the water is a translucent surface with ripples and reflections over the riverbed and the submerged ship, not one flat brown plane

#### Scenario: Decode, key and text (ctest)
- **WHEN** `tests/nv2a_dot` decodes the water's registers, with stage 1 disabled
- **THEN** the shader modes are 1, 0x11, 0x11 and 0x0C, and only stage 3 binds a cube
- **AND** the face stride is the 128-aligned span of the six DXT5 levels
- **AND** the key holds mapping 1 for stages 1-3 and the stage-3 cube bit
- **AND** the MSL and HLSL declare `tex3` as a cube, declare no `tex1` or `tex2`, and contain the three dots and the reflection vector
- **AND** with no cube bound they read `tex3` through `nv2a_cube_2d`
- **AND** the same modes without `bump_on` give the plain 2D text
- **AND** with the cube's faces under a live render target, the key has no cube bit and CUBEMAP reads 2D
- **AND** a DOT_RFLCT_DIFF stage 2 packs stage 3's input and mapping, and `nv2a_bump_sources` counts the dot and DPNDNT inputs

#### Scenario: Dot states compile (ctest)
- **WHEN** `d3d8_hlsl_split`, `d3d8_msl_split` and `d3dcompile_smoke` run the shared dot cases (`dot_cases.h`)
- **THEN** the HLSL text declares cubes exactly where the state binds one and applies no `alpha_only` fix-up to a stage that reads no texture, the MSL compiles with Metal, and on Windows the HLSL compiles with D3DCompile

#### Scenario: Environment cubes on a second title
- **WHEN** BLiNX 2 runs its golden scenarios on Metal and on D3D11
- **THEN** the verdicts pass within the golden limits
