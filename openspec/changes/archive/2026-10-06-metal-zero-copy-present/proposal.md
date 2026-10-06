## Why

The Metal backend still pays two CPU round trips per flip. D3D11 pays neither: it has its own swap chain and does no guest readback.

1. **Present by readback** (`render-gpu-backend` 4.5). The flip waits for the GPU, then `getBytes` reads the present texture. The window's slot gets a copy, and the main thread uploads it with `SDL_UpdateTexture`. That is about 1.2 MB each way at 1x, 4.9 MB at 2x and 11 MB at 3x.
2. **Write-back every flip.** The present surface is copied into guest RAM and box-filtered when render scale > 1. The only reader is the debug and golden dump code. The title never reads it (measured below).

Measured on the Mac with the probe (toolkit `perf/metal-readback` 1d2079b, `RECOMP_DEBUG=metal_prof`). The runs are windowed with vsync, `SDL_AUDIODRIVER=dummy` and scratch save and HDD dirs. Raw logs are in `xbox-recomp/runs/metalrb/`. "Frame" is the `[PB-PERF]` wall mean (p50); `on_flip` is the backend's flip. The readback, write-back and wait columns are parts of `on_flip`, on the walker's (ack) thread.

| scene | scale | flips/s | frame ms (p50) | on_flip ms | readback ms | write-back ms | GPU wait ms | main-thread upload ms |
|---|---|---|---|---|---|---|---|---|
| stage1 3D | 1 | 27.1 | 37.3 (32.7) | 1.71 | 0.45 (window) | 0.47 | 0.73 | 0.14 |
| stage1 3D | 2 | 26.8 | 37.4 (32.8) | 3.70 | 1.78 (host, shared) | 0.80 | 1.00 | 0.38 |
| stage1 3D | 3 | 26.0 | 38.5 (32.7) | 7.10 | 3.99 (host, shared) | 1.36 | 1.50 | 0.79 |
| menu (story) | 1 | 54.4 | 18.4 (8.8) | 1.29 | 0.36 | 0.39 | 0.66 | 0.12 |
| menu (story) | 2 | 52.0 | 19.3 (8.7) | 2.98 | 1.51 | 0.80 | 0.76 | 0.37 |
| menu (story) | 3 | 47.3 | 21.2 (9.8) | 5.94 | 3.23 | 1.35 | 1.44 | 0.79 |

With both consumers switched off (`metal_no_window,metal_no_writeback`):
- stage1 at 3x: `on_flip` drops from 7.10 to 1.56 ms, walk from 12.75 to 7.01 ms, and flips/s goes from 26.0 to 27.2.
- The menu at 3x goes from 47.3 to 53.6 flips/s, close to 1x's 54.4–55.5.
- At 1x, `on_flip` drops from 1.71 to 0.74 ms.

Dropping only one consumer saves only its own part. At scale > 1, one host readback serves both consumers, so it stays while either is on:
- no write-back: `on_flip` 5.86 ms;
- no window: 6.98 ms.

The 3D scenes are paced at 30 Hz, so their flips/s barely move. The cost shows as lost headroom: at 3x the walker spends 5.5 ms of a 33 ms frame copying pixels. The 60 Hz menu loses 13% of its flips/s at 3x. GPU time per flip is 2.1–4.1 ms (stage1) and 0.2–1.4 ms (menu). The wait is mostly commit and scheduling latency, not GPU work.

## What Changes

- **Zero-copy present.** When the Metal backend is selected, the SDL window is created with `SDL_WINDOW_METAL` and a `CAMetalLayer` view (`SDL_Metal_CreateView`) instead of an `SDL_Renderer`. The presenter owns the Metal device and command queue (the window comes up before the backend's lazy `init()`), and the backend adopts them. At the flip the backend blits the present texture into one of the presenter's three GPU slot textures, in the frame's own command buffer, and publishes the slot. The main thread draws the slot into the layer's drawable with one full-screen triangle and presents it. Nothing crosses to the CPU. The present filter (nearest, linear, integer), letterbox, resize, HiDPI, fullscreen, vsync, `RECOMP_WINDOW_SHOT`, the title-bar stats and the drop-not-wait hand-off all keep their current behaviour. A guest-bytes frame (a surface the backend never drew) is uploaded into a slot, as today.
- **Write-back on demand.** The flip no longer copies the present surface into guest RAM. A new executor hook, `sync_guest`, asks the backend to write a surface back just before the executor reads that surface's guest bytes, on the ack thread where every such reader already runs. This covers `fb_dump_at` (goldens), `RECOMP_FB_DUMP_FLIPS`, the `[PB]` report dump and the mid-frame surface dumps. The Metal backend also writes a dirty render target back before it hashes or decodes guest memory that overlaps it (a texture `rt_texture` did not bind), and before evicting a dirty target that was presented. Dumps come from the same `write_back` and `write_back_scaled` code at the same flip, so golden frames stay guest-sized and byte-identical.
- **A/B and fallbacks** (debug tier):
  - `metal_present=readback` restores the 4.5 present.
  - `metal_writeback=always` restores the per-flip write-back. `metal_no_rtt` implies it.
  - `metal_fb_guard` traps the first CPU access to the last present surface. A read logs the thread and pc and switches the run to `always`; a write (the host allocator's `bzero` is the one seen) is logged once and ignored.
  - If `SDL_Metal_CreateView` fails, the window uses the `SDL_Renderer` path and the backend uses the readback present.
- **Probe clean-up.** `metal_no_writeback`, `metal_no_window` and `metal_fb_watch` are removed. `metal_prof` stays as a trace key: one line every 300 flips.

Out of scope:
- Dropping the flip's GPU wait (0.7–1.5 ms). It needs per-frame rings and changes when visibility reports land, which the attract-cliff golden depends on.
- Private-storage render targets. That is optional task 6.1: only if a measurement shows GPU time drops.
- Making the D3D11 mid-frame and report dumps correct through the same hook (they read never-written guest memory today). Recorded as a follow-up, see Impact.

The agent's four open questions (defaults, stale guest reads, `sdl2-compat`, shot geometry) are decided in design.md, "Decided".

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `gpu-backend` (`render-gpu-backend`, not yet archived): adds requirements for the Metal present path and for on-demand guest write-back. These replace task 4.9's plan and 4.5's interim readback. Its "the SDL2 window SHALL remain the Present path" still holds: the window is SDL's, drawn through its `CAMetalLayer`.
- `enhancements` (`enhancements-render-scale`, not yet archived): the "Guest-size write-back" requirement's "so … the title sees guest-sized frames" becomes "so every reader of the written-back bytes sees guest-sized frames"; the write-back itself now runs on demand. The scenario holds through `sync_guest`. Adjust the sentence when either change is archived.

## Impact

- **Toolkit** (branch off `posix-host/portability`):
  - `src/d3d/nv2a_pb_metal.m`: device adoption, flip, `sync_guest`, overlap and eviction write-backs, the slot blit, keys.
  - `src/video/fb_present_sdl.c`: window creation picks the layer path, and the hand-off carries a texture.
  - New `src/video/fb_present_metal.m`: device and queue, layer, slots, present pass, shot, byte upload. Obj-C, MRC, macOS only.
  - `src/kernel/nv2a_pb_state.h` and `nv2a_pb_exec.c`: the `sync_guest` hook, the `writes_back` comment, and the calls before guest-memory dumps.
  - `src/platform/recomp_env.h`: keys.
  - `tests/nv2a_backend_smoke`: the existing scenes sync before comparing (they compare guest bytes after a flip, which `lazy` leaves stale), plus a write-back-on-demand case.
- **Backends agree.**
  - D3D11 already presents from its swap chain with no guest write-back, and `d3d11_dump` handles `fb_dump_at` from its own back buffer or RT. It leaves `sync_guest` NULL. Follow-up in TASKS: its `[PB]` report dump (`dump_present_bmp`) and mid-frame `dump_surface_bmp` read guest memory that D3D11 never writes; a D3D11 `sync_guest` (staging copy of the RT) would make them correct. Not needed for this change's parity, since those dumps are not golden material there.
  - The CPU path draws into guest memory, so it has nothing to sync. Its presenter (`SDL_Renderer` on macOS and Linux, GDI on Windows) is unchanged: the layer window is made only for `RECOMP_PB_BACKEND=metal`.
- **Goldens:** none change. Metal attract, stage1 and story must give the same verdicts as on `main`; story-menu already FAILs on `main` (TASKS). Because `nv2a_pb_exec.c` changes, the D3D11 golden runs under Proton (`bench.sh golden`) and the CPU golden runs on the Mac. One place can in principle differ: a texture decoded from guest memory over a dirty render target now sees that target's current contents rather than the previous flip's write-back (design D2); the probe trapped no such decode in either measured scene, and the golden runs are the check.
- **Hosts:** macOS only for the new paths. Linux SDL and Proton are unchanged. Managed storage (Intel Macs) is handled in code (design D2) but there is no such machine here to test it.
- **Upstream:** the Metal backend and the SDL presenter are fork-only today. The `sync_guest` hook is title-agnostic and NULL by default; it goes upstream with the Metal backend, if that ever goes. Nothing here is upstream-bound now, so the Burnout 3 gate does not apply; it does the day the hook is put in an upstream PR.
