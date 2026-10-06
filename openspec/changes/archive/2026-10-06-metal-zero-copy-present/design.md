## Context

Code was read at toolkit `posix-host/portability` 6826246 and cat `main` b2de36b. The measurement probe is on toolkit `perf/metal-readback` 1d2079b. The runs are in `xbox-recomp/runs/metalrb/` and the table is in proposal.md.

### What exists

**Start-up order.** `xbox_HostWindowMain` creates the SDL window on the process main thread and only then starts the guest on a pthread. The Metal backend's `init()` runs lazily on the nv2a-ack thread, at the executor's first method (`nv2a_pb_metal_register_from_env`). So the window exists before the backend has a device, and the backend may never come up (no device: the CPU rasteriser takes over, and the window keeps showing guest bytes).

**The Metal flip** (`metal_on_flip`, on the ack thread):
1. `present_target` finds the RT the walker picked: `rt->offset == surface_offset` and, once the walker has picked, `rt->w, h == p->w, h`.
2. On managed storage (discrete GPU) a `synchronizeResource` blit is encoded first. `flush(1)` commits and waits. The wait also frees the vertex and index rings, and `occ_after_wait` retires visibility slots.
3. At scale > 1, `host_readback` does one `getBytes` of `hw x hh`.
4. `write_back` (1x: `getBytes` at the guest pitch, or row by row to R5G6B5) or `write_back_scaled` (box filter) fills guest memory.
5. The window gets a second `getBytes` at 1x, or the host buffer at 2x and above, through `xbox_FramebufferWindowPresentPixels`. That copies into the back slot.
6. The main thread runs `SDL_UpdateTexture` and `SDL_RenderCopy`.

RTs are `MTLStorageModeShared` on Apple silicon (managed on a discrete GPU). They are seeded from guest bytes when created, and LRU-evicted (`RT_MAX` 8) without a write-back. `writes_back = 1` tells the executor to dump Metal frames from guest memory.

**The executor's guest-memory readers.** Each one runs on the ack thread (the thread contract in `nv2a_pb_state.h`: `present_pick`, `on_flip` and `nv2a_pb_exec_report` all run there, the report from the ack loop in `xbox_memory_layout.c`):
- `dump_at_flip` (`fb_dump_at`: the Metal and CPU golden source), right after `on_flip` in the same `FLIP_STALL` case;
- `RECOMP_FB_DUMP_FLIPS`, through `dump_present_bmp`, in the same case;
- the `[PB]` report dump (`dump_present_bmp`, or `dump_surface_bmp` before the first pick);
- `dump_surface_bmp`, at clears and after the first drawn batches.

Both present dumps go through `write_present_bmp`, which reads `s_present` (offset, w, h, pitch). `dump_surface_bmp` reads the drawn or current surface at `s_gpu.pitch`, `clip_x + clip_w` by `clip_y + clip_h`. The mid-frame ones already read stale bytes under Metal, because only the present surface is ever written back.

**The SDL presenter** (`fb_present_sdl.c`):
- The window is resizable and HiDPI.
- One accelerated `SDL_Renderer` (SDL's Metal renderer, as the log says).
- Three byte slots with a lock-free hand-off: the ack thread never waits for the window, and an unshown frame is dropped.
- Letterbox through `SDL_RenderSetLogicalSize`; `integer` through `nv2a_present_rect`; `linear` through the texture's scale mode.
- `SDL_WINDOW_FULLSCREEN_DESKTOP` for fullscreen.
- `RECOMP_WINDOW_SHOT` uses `SDL_RenderReadPixels` between copy and present.
- The close path clears `s_running` and spins on `s_in_present` before destroying the window, so no present is mid-publish when SDL goes.

SDL on this Mac is Homebrew `sdl2-compat` 2.32.72 over SDL3 3.4.16, and it has `SDL_WINDOW_METAL`, `SDL_Metal_CreateView`, `SDL_Metal_GetLayer` and `SDL_Metal_GetDrawableSize`.

**D3D11** (`nv2a_pb_d3d11.c`):
- The backend owns the window and the swap chain.
- `CopyResource` at stock, or the scaling blit (`s_blit_*`: full-screen triangle, point or linear sampler, `nv2a_present_rect`).
- No guest write-back.
- `d3d11_dump` reads the back buffer, or the RT after a blit, and handles `fb_dump_at` itself.

### Who reads the written-back guest framebuffer (measured)

The probe's `metal_fb_watch` made the present surface's pages `PROT_NONE` after every write-back. It logged the first access per flip (thread, pc, read or write), and a hash compared the bytes between write-backs. Two runs, headless, at 1x, with `fb_dump_at`:

| run | flips watched | reads | writes | other |
|---|---|---|---|---|
| `@stage1` (3D, HUD, enemies) | 4200 | 99, all `write_present_bmp` on `nv2a-ack` (the `fb_dump_at` dumps) | 1: `__bzero` in `xbox_ContiguousAllocEx`, a guest thread re-allocating that memory | the hash changed once, at the same allocation |
| `@story-hub` (TS-edit, menus, hub) | 6600 | 270, all `write_present_bmp` | 1: the same `bzero` | |

So:
- BLiNX 2's own code never read its framebuffer in either run. No title code touched it at all apart from re-allocating it.
- The Metal texture path never decoded the present surface from guest memory: no read from a decode or hash function was trapped.
- The window does not read guest memory while the backend draws, because it is fed from the texture.
- `metal_no_rtt` (decode RTs from guest memory) and the RT seed at creation are readers by construction, but neither showed up in these runs.

Limits of the probe:
- It catches the first access per flip only.
- It cannot see an access through another mapping of the same physical pages: there are 28 mirror views, and the title uses the contiguous window that `dma_resolve` returns.
- A kernel-side access, such as `read()` into the pages, would fail with EFAULT rather than trap. That is why the guard below is not the default.
- Off-screen RTs were never written back, so the probe says nothing about guest reads of those; they would have read seed or garbage before this change too.

D3D11 is the backend every Proton golden runs on, and it has never written back. A title that read its framebuffer with the CPU would already be wrong there.

## Goals / Non-Goals

**Goals**
- No GPU→CPU→GPU copy per flip on the Metal backend with a window, at any render scale.
- No per-flip guest write-back. Guest bytes are written exactly when the executor or the backend is about to read them.
- Goldens unchanged: `fb_dump_at` frames are guest-sized and come from the same write-back code at the same flip.
- Present parity with today's SDL path: filters, letterbox, integer, resize, HiDPI, fullscreen, vsync, window shot, title stats, drop-not-wait.
- A one-key A/B back to each old behaviour.

**Non-Goals**
- Dropping the flip's GPU wait (a follow-up; see D6).
- Changing the CPU path, the D3D11 backend or the Linux or Windows presenters.
- Present latency work, such as presenting from the ack thread (D1 says why not).

## Decisions

### D1. Present on the main thread from GPU slot textures, through a CAMetalLayer

The hand-off keeps its shape: three slots (back, ready, front), a pointer swap under `s_lock`, and drop-not-wait. A slot now holds an `MTLTexture` (`BGRA8Unorm`, frame-sized: `hw x hh`) instead of bytes. Slot storage is `Shared` on unified memory and `Managed` on a discrete GPU, the same choice `surface()` makes for RTs: the guest-bytes upload below needs `replaceRegion`, which a private texture refuses, and a blit destination gains nothing from private storage.

**Device and queue.** The presenter creates them (`MTLCreateSystemDefaultDevice`, `newCommandQueue`) when it sets the layer up, at window creation on the main thread, before the guest exists. The backend's `init()` asks `xbox_FramebufferWindowMetal(&device, &queue)`; when the window is in layer mode it adopts both, otherwise (headless, fallback, the smoke test) it creates its own as today. One device, so textures are shared; one queue, so the ordering argument below holds. The old direction, backend hands device to presenter, cannot work: the window is up long before `init()`, and must present guest-bytes frames even if `init()` never succeeds.

**Ack thread** (`metal_on_flip`, before `flush(1)`):
1. Ask the presenter for the back slot's texture at the frame's size. It is created, or re-created on a size change, on the shared device; creating textures from a background thread is allowed. Releasing the old texture while a present pass still reads it is safe: a committed command buffer retains its resources until it completes.
2. Encode `copyFromTexture:rt->tex toTexture:slot` in the frame's command buffer.
3. After the commit, publish the slot with the walker's flip number.

The copy is GPU-only: 1.2–11 MB at hundreds of GB/s.

**Main thread:** on a new frame or `dirty`, inside an `@autoreleasepool`:
1. Compare `SDL_Metal_GetDrawableSize` with `layer.drawableSize` and set it when they differ. Cheaper than trusting events alone: a move between displays of different scale may arrive as something other than `SIZE_CHANGED` through `sdl2-compat`.
2. Take `[layer nextDrawable]`. On nil (timeout, display asleep, window hidden) skip the present, leave the slot as front and keep `dirty` set, so the frame is drawn at the next pass.
3. Encode one pass: clear to black, viewport = `nv2a_present_rect(frame w, h, drawable w, h, filter)`, a full-screen triangle sampling the slot. The sampler is nearest for `nearest` and for a whole `integer` multiple, and linear for `linear` and the integer fallback, as D3D11's `s_blit_smp`.
4. `presentDrawable`, commit. No wait.

Main and ack threads share one `MTLCommandQueue`. Command buffers on one queue start in commit order, and texture hazard tracking is on by default. So:
- the present pass that samples a slot runs after the blit that filled it: the slot is published only after the frame's command buffer is committed, so the main thread cannot commit a pass that reads it any earlier;
- a later blit into a slot waits for the earlier pass that read it. The ack thread's next back slot is the one the main thread drew from two swaps ago, whose pass can still be in flight; tracking covers it.

No fence or event is needed.

**Guest-bytes frames** (`xbox_FramebufferWindowPresent`, a surface the backend never drew): the ack thread copies the bytes into the back slot with `replaceRegion`, converting R5G6B5 to BGRA8 as today's 16-bit texture did. This is today's CPU cost (slot memcpy plus `SDL_UpdateTexture`), now all on the ack thread. It happens only before the first Metal frame, or for the whole run when Metal `init()` failed and the CPU rasteriser draws into a layer window; the CPU path proper (`RECOMP_PB_BACKEND` unset) never gets a layer window.

Why the main thread, not the ack thread:
- `nextDrawable` blocks when every drawable is queued (vsync, three drawables). On the ack thread that would push the display's cadence back into the walker and the guest. Today's contract is "the walker never waits for the window", and the bench's flip timing depends on it.
- The main thread already owns resize, fullscreen, events and shots. A `nextDrawable` wait there is at most a display period, and the event pump (which also updates the game controllers) tolerates that as it tolerates `SDL_RenderPresent` with vsync today.
- The cost is at most one frame of latency in the worst case, the same as today's slot hand-off.

**Window creation.** When `RECOMP_PB_BACKEND=metal` and `metal_present` is not `readback`:
- `SDL_CreateWindow` gets `SDL_WINDOW_METAL`, plus the existing `RESIZABLE`, `ALLOW_HIGHDPI` and optional `FULLSCREEN_DESKTOP`. No `SDL_Renderer` is made.
- `SDL_Metal_CreateView` and `SDL_Metal_GetLayer`.
- On the layer:
  - `device` = the presenter's device;
  - `pixelFormat` = `BGRA8Unorm`;
  - `framebufferOnly` = YES, or NO when `RECOMP_WINDOW_SHOT` is set;
  - `displaySyncEnabled` = the existing vsync flag (`RECOMP_PRESENT_VSYNC`);
  - `maximumDrawableCount` = 3;
  - `drawableSize` from `SDL_Metal_GetDrawableSize` at start, on every `SDL_WINDOWEVENT_SIZE_CHANGED` and `EXPOSED`, and checked before each present (above), on the main thread.

If `SDL_CreateWindow` with the Metal flag, either Metal view call, or the device creation fails, the window is destroyed and re-created the old way, and the presenter reports `[PRESENT] window up: CAMetalLayer unavailable (<err>); SDL renderer, readback present`. The backend asks `xbox_FramebufferWindowMetal()` at `init()` and uses today's readback present when it returns 0. `SDL_VIDEODRIVER=dummy` makes the Metal window creation fail on this stack, which is how the fallback branch is exercised without a second machine (tasks 5.8).

The startup line says which path is in use: `[PRESENT] window up: CAMetalLayer (zero-copy), vsync on`.

**Letterbox geometry.** Every filter uses `nv2a_present_rect`, as D3D11 does. SDL's logical-size letterbox rounds its float scale its own way, so the stock rectangle can differ from today's by up to 1 px on an odd output size. That is invisible, and window shots are not goldens. 4.2-style shots verify it (tasks).

**Window shot.** `shot_due` and `shot_save` keep their flip logic. In layer mode the shot encodes, after the present pass and in the same command buffer, a blit of the drawable texture (hence `framebufferOnly = NO` only when shots are requested) into a shared `MTLBuffer`, then presents, commits, waits for that one command buffer on the main thread and writes the same BGR24 BMP at drawable size. It reads device pixels of the whole drawable, so the fullscreen-`nearest` "left-aligned" quirk of `SDL_RenderReadPixels` (TASKS) goes away on this path.

**Close.** The Dekker handshake is unchanged: `s_running` off, spin on `s_in_present`, then release the slots, the layer's view and the window on the main thread. The ack thread's blit encode counts as "in present" from slot acquisition to publish.

**Stats.** `upload ms/frame` becomes the encode time of the present pass. `ack copy ms/flip` becomes the time from slot acquisition to publish (the blit encode). The `[PRESENT]` line names the path.

### D2. Write-back on demand: an executor hook, `sync_guest`

`struct nv2a_pb_backend` gains `void (*sync_guest)(uint32_t offset, uint32_t pitch, uint32_t w, uint32_t h)`, appended after `writes_back` (the initialisers are positional). It means: "the executor is about to read the guest bytes of the surface at colour offset `offset`, `w x h` at `pitch`; make them current". It is called on the ack thread only, like `on_flip`; every executor reader listed in Context runs there. The executor calls it, when it is non-NULL:
- in `write_present_bmp` (`fb_dump_at`, `FB_DUMP_FLIPS`, the `[PB]` report dump), after the format check that makes it return 0, with `s_present`'s offset, pitch, w and h;
- in `dump_surface_bmp`, after its own early-outs, with the drawn or current offset, `s_gpu.pitch`, `clip_x + clip_w` and `clip_y + clip_h`.

It is NULL for the CPU path (it draws into guest memory), for D3D11 (it dumps itself) and for null. `writes_back` keeps its meaning, "dump this backend from guest memory", so Metal keeps `writes_back = 1` and `FB_DUMP_FLIPS` keeps counting its batches. Its comment in `nv2a_pb_state.h` changes from "on_flip leaves the finished frame in the guest present surface" to "the backend's frames are dumped from guest memory, after `sync_guest` when it has one".

**Metal's `sync_guest`:**
1. Find the RT as `present_target` would: `rt->offset == offset` and `rt->w, h == w, h`. That is the RT today's flip wrote back, so the identity argument below is exact. If none matches, take the most recently used RT whose `addr` matches `nv2a_pb_dma_resolve(offset)` in the low 27 bits (a surface dump of a target drawn at another clip). If still none, there is nothing to do: the guest bytes are the only copy.
2. If the RT is not dirty, return.
3. Otherwise:
   - on managed storage, encode `synchronizeResource` as the flip does today, then `flush(1)` whatever the state of `s_cmd`; on unified memory `flush(1)` only if `s_cmd` is open (the RT has work in an uncommitted command buffer). At a flip, `on_flip` has already waited, so this is free there;
   - `host_readback` at scale > 1;
   - `write_back` or `write_back_scaled`, the exact functions used today, with the guest `pitch`;
   - clear the dirty flag.

`rt->dirty` is set in `begin_pass`: every clear, draw or self-copy *destination* use of that RT opens a pass on it. Being the source of the `s_self` copy, or of the slot blit, does not dirty an RT.

The frame `fb_dump_at` writes is therefore made by the same code, from the same texture contents, at the same point: `dump_at_flip` runs right after `on_flip` on the same thread, nothing draws in between (`xbox_FramebufferWindowFrameStats` is the only call between them), and in layer mode the slot blit is encoded before the flip's wait, so the texture is settled either way. So it is byte-identical to today's dump of that flip. A pitch or size the walker reports differently from the RT's guest size is handled as today: `write_back` derives `bpp` from `pitch / w`.

**Write-back count.** A dumped flip syncs once per dirty RT: `fb_dump_at`, `FB_DUMP_FLIPS` and the report dump of the same flip share one write-back, since the second finds the RT clean. So with `fb_dump` set, write-backs equal the number of distinct (flip, surface) dump events; with no `fb_dump` prefix, zero. The smoke test and the golden check use that.

**Metal-internal readers:**
- **Texture decode over a dirty RT.** `tex_bind` hashes guest memory (`tex_hash_pal`) before it decides to upload, so the check goes at the top of `tex_bind`, after `rt_texture` has declined: if the texture's byte range (`nv2a_tex_extent`) overlaps a dirty RT's `[addr, addr + pitch*h)`, sync that RT first, then hash. This covers 16-bit or other-format views of a 32-bit target, `metal_no_rtt`, and an RT read as a texture after eviction. It is a check of 8 entries per stage bind, and a mid-frame `flush(1)` only when it fires (never, in the measured runs). The pitch an RT was drawn with is stored on the RT at creation. Note the semantics: the decode sees the RT's *current* contents, where today it saw the previous flip's write-back (present surface) or nothing (off-screen). That is what the hardware does, and nothing in the measured scenes reaches it; a counter in the `present #` line (`decode syncs`) attributes any golden difference to it.
- **Eviction.** `rt_free` of a dirty RT that has ever been a present target (`rt->presented`, set by `present_target`) syncs it first. Then a re-created RT seeds from the bytes today's code would have left, since today only the present surface is written back. Off-screen RTs keep today's behaviour: they are never written back at eviction. `rt_free` runs from `surface()` mid-frame; its `flush(1)` ends the open pass, which `surface()`'s caller reopens on the new target anyway.

**`metal_writeback=always`** (and `metal_no_rtt`, whose decode wants the bytes every flip) runs today's flip write-back unchanged. It is the A/B and the escape hatch.

### D3. Guest CPU access: parity with D3D11, plus a debug guard

The default trusts the measurement and D3D11's precedent: no write-back for the title's sake.

`metal_fb_guard` (debug tier) is the probe made permanent:
- after each flip, the last present surface's pages are `PROT_NONE`;
- the SIGSEGV/SIGBUS handler, chained like `RECOMP_WATCH`'s (`watch_posix_handler` in `xbox_memory_layout.c`) and installed lazily at the first flip, so after the title's own MMIO handler, checks whether the fault is inside the span. If it is, it opens the pages, records thread, pc and the ESR write bit, and lets the access proceed;
- the next flip logs the event once. A **read** (`[metal] fb_guard: guest READ of present surface 0x%08X by '<thread>' pc <sym>+0x..; switching to metal_writeback=always`) switches the run to `always` from then on. A **write** is logged once and ignored: the title overwriting its framebuffer needs nothing from the GPU, and the one write the probe saw is the host allocator's `bzero` in `xbox_ContiguousAllocEx`, which would otherwise flip every run to `always` at the first re-allocation.

The read that tripped it sees the bytes of the last write-back (possibly several frames old).

It is not the default for three reasons:
- the measured runs show nothing to guard;
- `PROT_NONE` on guest pages turns a kernel-side access (`read()` into memory the title re-allocated, which the `bzero` shows it does) into EFAULT, which is a real I/O failure;
- the page span is per-flip mprotect churn on the guest's memory.

### D4. Keys

Debug tier, in the `recomp_env` table with rows in `cat/docs/env.md`:
- `metal_present=layer|readback`: default `layer`. With `readback`, the window and backend are today's.
- `metal_writeback=lazy|always`: default `lazy`. `metal_no_rtt` implies `always`.
- `metal_fb_guard`: D3.

`metal_prof` moves to the trace tier: a `[metal] prof` line every 300 flips with wait, readbacks, write-back, slot blit, hand-off and GPU time. It is cheap, prints only, and the bench can read it. `metal_no_writeback`, `metal_no_window` and `metal_fb_watch` go away.

**Stock behaviour.** The Metal backend itself is opt-in (`RECOMP_PB_BACKEND=metal`). Within it, the new paths are the default because they produce the same frames, the same dumps and the same window behaviour; they are not an enhancement under `XBOXRECOMP_ENHANCE`. The old paths stay one key away. Decided below (1).

### D5. Render scale

At scale > 1:
- the slot is `hw x hh`, and the blit copies the whole host texture;
- the present pass scales it into the letterbox, so 2x looks as it does today;
- `sync_guest` box-filters to guest size as `write_back_scaled` does, so dumps stay 640x480 and golden.py's non-stock check still fires on the `[ENHANCE]` line.

### D6. What stays

- **The flip's `flush(1)` wait.** It resets the rings and retires visibility slots, and `nv2a_occ` timing depends on it. Removing it means rings sized for 2–3 frames in flight, plus a completed-handler counter or a `MTLSharedEvent` for slot retirement. It would save 0.66–1.50 ms per flip. It is recorded in TASKS as a follow-up, not done here.
- **`MTLStorageModeShared` RTs.** With no `getBytes` on the common path they could be private (lossless compression on Apple GPUs), with `sync_guest` blitting into a shared staging buffer. Optional task 6.1 decides on measured GPU time.

## Decided

The four questions the proposal left open, decided by Fable at the spec review (the user had delegated unattended decisions):

1. **New present and lazy write-back are the Metal backend's defaults; the old paths sit behind `metal_present=readback` and `metal_writeback=always`.** The opt-in rule guards stock *behaviour*; this change produces the same frames, dumps and window output and only removes copies, so it is a fix, and the backend itself is already opt-in. The condition is the golden gate: if any Metal golden verdict moves, the defaults flip back until the cause is found.
2. **A title's CPU reads of its framebuffer see stale bytes under the default, and the guard is debug-only.** Every Proton golden already runs this way on D3D11, the probe saw zero reads in the two scenes that cover 3D and menus, the guard's `PROT_NONE` breaks kernel-side I/O into those pages, and `always` is one key away. The guard switches on reads only, so the allocator's `bzero` does not defeat the default.
3. **Relying on `SDL_Metal_CreateView` through `sdl2-compat` is acceptable.** The calls exist on this stack, the fallback is detected at window creation and re-creates the old window, and the fallback branch is exercised with `SDL_VIDEODRIVER=dummy` (tasks 5.8). The per-stack checks of fullscreen, HiDPI and resize are tasks 5.4 and 5.6.
4. **A window shot whose frame rectangle moves by up to 1 px is acceptable.** Shots are not goldens; the golden source is the guest-sized `fb_dump_at` dump, which this change keeps byte-identical. The 1 px comes from `nv2a_present_rect` versus SDL's own rounding, and it removes the fullscreen-`nearest` left-alignment quirk. Task 5.4 compares within that tolerance.

No genuine dispute was found; nothing here needs the user before implementation.

## Risks / Trade-offs

- **`sdl2-compat` and `SDL_WINDOW_METAL`.** Homebrew's SDL2 is `sdl2-compat` 2.32 over SDL3. `SDL_Metal_CreateView` on a window without a renderer is supported there, but fullscreen, HiDPI and resize must be checked on this stack (tasks 5.4, 5.6). Fallback: the readback path, detected at window creation and exercised in 5.8.
- **Present from two threads on one queue.** The ordering argument in D1 relies on tracked hazards. Slot textures must not be created with `MTLHazardTrackingModeUntracked`. A ctest cannot show a missing hazard reliably, so the window shots at the anchored flips are the check (tasks 5.4). The presenter as a whole has no standalone test: it needs a display. The hook and the lazy write-back do (tasks 2.6).
- **A title that reads its framebuffer** gets stale bytes under `lazy`, as it would under D3D11. `metal_fb_guard` finds it, and `always` fixes it.
- **Golden identity relies on nothing drawing between `on_flip` and `dump_at_flip`.** True today (same function, same thread). The smoke test asserts the write-back count: one per dumped flip, zero otherwise.
- **Decode over a dirty RT sees fresher bytes than today** (D2). Never reached in the measured scenes; the `decode syncs` counter and the golden runs tell if a scene reaches it.
- **Managed storage** (discrete GPU) is handled by the same `synchronizeResource` the flip does today, but no such Mac is available to run it.
- **Lost diagnostic.** `RECOMP_FB_DUMP` mid-frame surface dumps become correct under Metal (they sync). The cost is a mid-frame GPU wait per dump, which is fine for a debug key.
- **The existing smoke scenes** compare guest bytes after a flip and would fail under `lazy` without a sync; they call the hook (tasks 2.6), which is also the first exercise of it.

## Migration

Nothing persistent changes. Saves, configs and golden.json are untouched. Bench scripts on the Mac gain nothing mandatory; `metal_prof` is optional.
