Worktrees:
- `wt/metalrb/xboxrecomp`: toolkit, branch `perf/metal-readback` off `posix-host/portability` 6826246. The probe commit 1d2079b is on it.
- `wt/metalrb/cat`: cat, branch `perf/metal-readback` off `main` b2de36b.

Raw runs go in `xbox-recomp/runs/metalrb/`. The run and summary scripts are `runs/metalrb/run.py` and `summarise.py`: windowed or headless, `SDL_AUDIODRIVER=dummy`, scratch save and HDD dirs. Mac builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Run one heavy job at a time on the Mac, which is shared with another agent. Never play sound on the Mac without asking.

## 0. Measure (done)

- [x] 0.1 Probe (toolkit 1d2079b): `metal_prof`, `metal_no_writeback`, `metal_no_window`, `metal_fb_watch`, with env.md rows.
- [x] 0.2 stage1 and the story menu at scale 1, 2 and 3, windowed: baseline, plus both consumers off. stage1 at 3x was also run with each consumer off on its own. The table is in proposal.md.
- [x] 0.3 Framebuffer readers: `fb_watch` on `@stage1` and `@story-hub`. Only `write_present_bmp` (dumps) read the surface, plus one `bzero` at re-allocation (design, Context).
- [x] 0.4 Spec review (Fable): design D1–D4 corrected, the four open questions decided (design, "Decided").

## 1. Executor hook (toolkit)

- [x] 1.1 `nv2a_pb_state.h`: `sync_guest(offset, pitch, w, h)` appended after `writes_back` in `struct nv2a_pb_backend`, with a comment saying when the executor calls it and that it runs on the ack thread only. Rewrite the `writes_back` comment: the backend's frames are dumped from guest memory, after `sync_guest` when it has one. Update every existing initialiser: CPU, null, D3D11 and Metal (positional: the field goes last).
  Done: toolkit eba4c8b. Positional initialisers needed no change (the field is last; zero-initialised NULL on CPU, null and D3D11), Metal's sets it.
- [x] 1.2 `nv2a_pb_exec.c`: call it when non-NULL in `write_present_bmp`, after the format check, with `s_present`'s offset, pitch, w, h; and in `dump_surface_bmp`, after its early-outs, with the drawn or current offset, `s_gpu.pitch`, `clip_x + clip_w`, `clip_y + clip_h`. Nothing else changes for the CPU path and D3D11.
  Done: toolkit eba4c8b.

## 2. Metal write-back on demand (toolkit)

- [x] 2.1 `RenderTarget`:
  - `dirty`, set in `begin_pass` (clear, draw, self-copy destination), cleared by the write-back. Being a copy source does not set it;
  - `pitch` at creation (`g->pitch`);
  - `presented`, set by `present_target`.
  Done: toolkit 5437712.
- [x] 2.2 `metal_sync_guest`, as in design D2: select the RT as `present_target` does (offset and w, h), else the most recent RT at the same `addr`; return if clean; on managed storage `synchronizeResource` then `flush(1)`, on unified `flush(1)` only if `s_cmd` is open; `host_readback` at scale > 1; `write_back` or `write_back_scaled`; clear `dirty`.
  Done: toolkit 5437712. Two details: `metal_sync_guest` restores the vertex and index ring positions after its `flush(1)`, because the decode-time sync runs inside `on_draw` after the draw's ring space is taken; with no open command buffer it waits on the last committed one if that is still running.
- [x] 2.3 `metal_on_flip`: no write-back unless `metal_writeback=always` or `metal_no_rtt`. In those modes, today's code runs as it is. Under `lazy` the flip does no `getBytes` at all when the window takes textures or is not running.
  Done: toolkit 5437712.
- [x] 2.4 Texture decode: at the top of `tex_bind`, after `rt_texture` declined, sync any dirty RT whose `[addr, addr + pitch*h)` overlaps the texture's extent, before `tex_hash_pal` runs. Count it (`decode syncs`) in the `present #` line. Eviction: `rt_free` syncs a dirty, `presented` RT.
  Done: toolkit 5437712. `decode syncs` stayed 0 in every golden and perf run.
- [x] 2.5 `metal_fb_guard` (design D3), built from the probe's handler: chained, installed at the first flip, one log line per event; a read switches to `always`, a write is logged once and ignored.
  Done: toolkit 5437712.
- [x] 2.6 `tests/nv2a_backend_smoke`:
  - the existing scenes call `be->sync_guest(...)` when non-NULL before comparing the GPU frame with the CPU frame (they compare guest bytes, which `lazy` leaves stale). The same bytes as before: the comparison stays exact;
  - a write-back-on-demand case, under the default `lazy`: draw, flip, and the guest bytes are untouched (still the seed) with zero write-backs; call `sync_guest` and the bytes equal the CPU rasteriser's frame, with one write-back; call it again and the count stays (clean RT);
  - draw at 2x (`recomp_env_set(RENV_RENDER_SCALE, "2")` with the layer built) and sync: the result equals `nv2a_downscale_box32` of the readback;
  - with `metal_writeback=always` (`recomp_env_set(RENV_METAL_WRITEBACK, "always")`, which overrides without a reload): the bytes are written at the flip, before any sync.
  Done: toolkit 5437712; the getters are `nv2a_pb_metal_writebacks()` and `nv2a_pb_metal_host_pixels()`. Also a guard case (`nv2a_backend_smoke guard`, its own ctest, since the guard is decided at the first flip): a read after a lazy flip proceeds, the next flip switches, the one after writes back.

  The write-back counter is static today; export a small getter for the test (`nv2a_pb_metal_writebacks()`), declared by the test as the backend getter is.

## 3. Keys and clean-up (toolkit + cat)

- [x] 3.1 `recomp_env.h`: add `metal_present`, `metal_writeback` and `metal_fb_guard` (debug tier). Move `metal_prof` to the trace tier and extend its line with the slot blit, the hand-off and `decode syncs`. Remove `metal_no_writeback`, `metal_no_window` and `metal_fb_watch`. `metal_no_rtt` implies `metal_writeback=always` in code, and its help says so.
  Done: toolkit 5437712.
- [x] 3.2 cat `docs/env.md`: matching rows (meaning, default, call site), remove the probe rows, and recount the tiers in the intro (trace +1, debug −1 net).
  Done: cat 79d194c (Trace 51, Debug 71).

## 4. Metal presenter (toolkit)

- [x] 4.1 New `src/video/fb_present_metal.m` (macOS, MRC, compiled only on Apple and with the Metal and QuartzCore frameworks; `src/video/CMakeLists.txt`):
  - device and queue creation (design D1), and the getter the backend adopts them through;
  - layer setup from an `SDL_Window` (pixel format, framebufferOnly, displaySync, maximumDrawableCount, drawableSize);
  - three slot textures, shared (managed on a discrete GPU), re-created on size change;
  - present pass: drawable-size check, `nextDrawable` with nil handled, clear, viewport from `nv2a_present_rect`, full-screen triangle, nearest or linear sampler (MSL compiled at runtime, fast math off as in the backend);
  - shot readback into a BMP;
  - `upload` of a byte frame into the back slot (BGRA8; R5G6B5 converted);
  - every entry point inside `@autoreleasepool`.
  Done: toolkit 5437712. Links CoreGraphics too (the sRGB colour space).
- [x] 4.2 `fb_present_sdl.c`:
  - at window creation, choose layer mode when `RECOMP_PB_BACKEND=metal` and not `metal_present=readback`, with the fallback to the renderer (destroy and re-create the window) on any failure;
  - in the slot hand-off, slots carry a texture handle in layer mode;
  - the main loop calls the layer present instead of the `SDL_Render*` calls in layer mode, and keeps every other line (events, title, quit, stats, shots);
  - resize, `EXPOSED` and fullscreen update `drawableSize`;
  - the `[PRESENT] window up:` line names the path, and the close path releases the layer resources after the `s_in_present` drain.
  Done: toolkit 5437712. The layer present checks the drawable size at every present, which covers resize, `EXPOSED`, fullscreen and a display change.
- [x] 4.3 Toolkit API for the backend, plain C declarations (`void *` handles) so `fb_present_sdl.c` stays C:
  - `int xbox_FramebufferWindowMetal(void **device, void **queue)`: 1 in layer mode, with the presenter's device and queue;
  - `void *xbox_FramebufferWindowBackTexture(uint32_t w, uint32_t h)`: the back slot's `id<MTLTexture>`, created or re-created at that size;
  - `void xbox_FramebufferWindowPublishTexture(void)`: publish the back slot with the walker's flip number.
  Done: toolkit 5437712.

  They sit in the same Dekker-style `s_running` / `s_in_present` handshake as `PresentPixels`: the ack thread is "in present" from `BackTexture` to `PublishTexture`.
- [x] 4.4 `metal_on_flip` and `init()`:
  - `init()` adopts the presenter's device and queue when `xbox_FramebufferWindowMetal` says yes, else creates its own as today;
  - in layer mode, before `flush(1)`, blit `rt->tex` into the back slot, then publish after the commit;
  - no `getBytes` and no `PresentPixels`;
  - guest-bytes frames still go through `xbox_FramebufferWindowPresent` (uploaded into a slot);
  - readback mode is today's code.
  Done with one deviation: the slot blit is encoded after the flip's `flush(1)` wait, in its own command buffer (`flush(0)`), then published. Same queue, so it runs after the frame; measured the same as encoding it before the wait (the menu's GPU wait stayed about 1.0 ms either way, against 0.66 ms at baseline). The blit itself is about 0.02 ms; the likely cause is that the main thread's present pass (clear plus a full-drawable triangle at 2560x1920) shares the backend's queue ahead of the next frame, so `flush(1)` absorbs it, where readback mode used SDL's own queue. A second queue for the present pass, ordered by an `MTLEvent`, belongs to the D6 flip-wait follow-up (TASKS).

## 5. Verify (Mac)

- [x] 5.1 Mac build. POSIX ctest dirs: `nv2a_backend_smoke`, `render_scale`, `enhance_cfg`, `nv2a_tex` and the rest of the POSIX set. No tools change, so no pytest.
  Done. Mac build clean. POSIX ctest: 26 standalone dirs pass (the same set as runs/batch, the rest Windows-only or x86-only), plus in-tree `nv2a_backend_smoke` (both tests), `input_map` and `d3d8_msl_split` (`runs/metalrb/ctest/summary.txt`).
- [x] 5.2 Goldens on Metal (`run.py ... --dump`, then `golden.py check`), attract, stage1 and story, at `lazy` and at `always`. The verdicts must match `main`'s. The known story-menu FAIL and story-hub INCOMPLETE are in TASKS. Under `lazy`, the `present #` line's write-backs equal the distinct dumped flips (`fb_dump_at` plus any report dump at another flip), and `decode syncs` is 0; a non-zero `decode syncs` with a changed verdict names the cause.
  Done (`runs/metalrb/g-*`, `gh-*`). Windowed, layer + lazy: attract pass (title CLOSE, mae 1.94; cliff 0.19), stage1 pass (stick 0.51, enemies 5.67 within its limits, hud 1.35), story: tsedit CLOSE, menu and hub INCOMPLETE (anchored flip not checkable windowed; with slack 70 a menu pace mismatch, 52 against 59.4 fps). Windowed, `always` + `readback`: the same verdicts (story menu pace 49.2 fps). Headless story at slack 70: pass in both modes with identical numbers (menu mae 1.255, hub CLOSE). The fallback run (5.8) is a third attract pass. Write-backs under lazy equal the dumped flips: attract 180 = 170 `fb_dump_at` + 10 report dumps; story 270 = 255 + 15; stage1 99 against 87 + 13 (one report dump shares a flip). `decode syncs` 0 everywhere.
- [x] 5.3 CPU-path golden on the Mac, attract: the hook is NULL there, as a regression check of 1.2.
  Done: CPU attract headless pass (title 0.006, cliff 0.185), no `[metal]` lines (`runs/metalrb/g-attract-cpu`).
- [x] 5.4 Window shots (`RECOMP_WINDOW_SHOT` at anchored flips) in layer mode against readback mode, attract flip 300 and stage1-stick:
  - stock window: same frame rect within 1 px, and pixels within the golden's limits, since the content is the same frame;
  - each filter (nearest, linear, integer) in a resized window;
  - fullscreen;
  - render scale 2;
  - HiDPI at `RECOMP_WINDOW_SCALE=1` and 2.
  Done (`runs/metalrb/shots/`, `summary.txt`; `shots.py`). Every shot is also checked against its own run's `fb_dump_at` frame of the same flip: layer and readback agree on every case. Stock (2560x1920 px, HiDPI at `RECOMP_WINDOW_SCALE=2`) and `RECOMP_WINDOW_SCALE=1` (1280x960 px): exact against the dump in both modes. Scale 3 (the window clamps to 3840x2436 px, so a non-4:3 window) with linear and integer, and fullscreen with nearest, linear and integer: frame size identical in both modes (3248x2436 letterboxed; integer 3200x2400 at 320,18), the layer frame centred within 0 px, nearest and integer exact, linear mae 0.22. Render scale 2: identical stats in both modes (the window shows host pixels, the dump is box-filtered). stage1-stick (flip 843) stock and render scale 2: the same. A readback-mode shot of a letterboxed window starts at the frame's corner: `SDL_RenderReadPixels` reads the logical-size viewport, a property of the old path. The first run found the layer shot's red and blue swapped (the BMP writer, not the window); fixed before the runs above. No non-Retina display was available.

  Save them under `runs/metalrb/shots/`.
- [x] 5.5 Perf: re-run the proposal's matrix (stage1 and the menu at 1, 2 and 3; baseline only) with `metal_prof`. Expected `on_flip` is close to the "both off" rows: about 0.75 / 1.6 ms at 1x / 3x on stage1, and menu flips/s within 3% of 1x at every scale. The prof line reports zero readback bytes. Flag a flips/s drop of 25% or more, a 1.5x rise in raster ms, or any rise in walk time, against the baseline (workspace rule).
  Done (`runs/metalrb/p-*`, `f-*`, `p2-st-x1`; windowed, before -> after). stage1: flips/s 27.08/26.75/25.98 -> 27.51/27.42/27.04 at 1x/2x/3x; walk 7.77/9.20/12.75 -> 6.30/6.62/7.13 ms; on_flip 1.71/3.70/7.10 -> 0.77/1.07/1.59 ms. Menu: flips/s 54.37/51.96/47.31 -> 54.00/54.87/54.50 (within 1% of 1x at every scale); walk 1.66/3.39/6.37 -> 1.42/1.65/2.23; on_flip 1.29/2.98/5.94 -> 1.07/1.28/1.85. Readback and write-back bytes are 0; the slot blit is about 0.02 ms. Raster ms is 0 on Metal; its GPU-path counterpart, draw, did not rise (stage1 4.4 against 4.9 ms). No flag. The window thread: 0.3% of a core; stage1 `upload` 0.03 ms/frame (was 0.14-0.79); the menu's `upload` (1.3-1.5 ms/frame) is the `nextDrawable` vsync wait, not CPU work. The menu's GPU wait in `on_flip` is about 1.0 ms against 0.66 at baseline: the present pass on the shared queue (see 4.4).
- [ ] 5.6 Resize and fullscreen by hand on the Mac (the user's window, no sound): drag-resize, enter and leave fullscreen, and move between a Retina and a non-Retina display if one is available. No stretched frame, no black frame that persists, and no `nextDrawable` stall in `[PRESENT]` stats.
  - Archive note (2026-10-06): left for the user; listed in TASKS.md.
  Pending: needs the user at the Mac (drag-resize, fullscreen toggle, display move). The scripted cases in 5.4 cover the sizes.
- [x] 5.7 `metal_fb_guard` on a short stage1 run: zero reads, the `bzero` write logged once without a mode switch, and the log line arms. A forced read (a test-only poke that reads the surface) switches to `always`.
  Done. `@stage1` 60 s windowed with `metal_fb_guard` (`runs/metalrb/v-guard-s1`): the arm line once, then no read and no write over 1800 lazy flips (the probe's `bzero` came at a surface re-allocation this run did not reach), 0 write-backs, no crash. The forced read is the smoke test's guard case: the read proceeds, the next flip logs `guest READ ... switching to metal_writeback=always`, and the flip after that writes back.
- [x] 5.8 Fallback: a run with `SDL_VIDEODRIVER=dummy` and `RECOMP_PB_BACKEND=metal` prints the `CAMetalLayer unavailable` line, comes up on the renderer path, and its `fb_dump_at` frames match the golden. If the dummy driver does not fail the Metal window on this stack, force the failure with a build-time test hook instead; the branch must run once.
  Done (`runs/metalrb/v-fallback`): `SDL_VIDEODRIVER=dummy` fails the Metal view, the run logs `CAMetalLayer unavailable (...dummy...); SDL renderer, readback present`, comes up on the software renderer, and the attract golden passes (title CLOSE 1.96, cliff 0.19).

## 6. Optional

- [ ] 6.1 Private RTs: `MTLStorageModePrivate` colour targets, with `sync_guest` and the readback path blitting into a shared staging buffer first. Keep it only if `metal_prof` GPU ms drops on stage1 at 3x.
  - Archive note: optional, not attempted; listed in TASKS.md.
  Not attempted: optional, and the GPU time per flip (stage1 2.16/2.75/4.09 ms at 1x/2x/3x) leaves it for a later measured pass.

## 7. Gates, docs, merge

- [x] 7.1 Proton: `bench.sh golden` (D3D11) and the CPU golden on the Linux/Proton host, under the run lock, because `nv2a_pb_exec.c` and `nv2a_pb_state.h` change. Expected identical, since the hook is NULL there. Burnout 3 is not gated: nothing here is upstream-bound (proposal, Impact).
  Done on the Linux/Proton host from the branch heads (`BENCH_DIR=~/xbox-recomp-metalrb`, `runs/metalrb/benv.sh`; logs `runs/metalrb/bz-*.log`, runs in `bench-logs/`). `bench.sh golden` (D3D11): the 8 Proton tests pass and all 7 frames are CLOSE (stick 0.109, enemies 6.89, hud 1.22, title 1.94, tsedit 0, menu 1.23, hub overlay 0%), golden: pass (runs 20261006-011310, -011429, -011619). CPU attract 200 s (20261006-011822): 6.9 flips/s, raster 139.1 ms on 3D flips, no crash, against the batch baseline 20261005-205810 at 6.7/s and 142.4 ms.
- [x] 7.2 Docs:
  - the `nv2a_pb_metal.m` header (on_flip, "Only the present surface is written back" → "on demand");
  - the `fb_present_sdl.c` header (layer mode, device ownership);
  - `render-gpu-backend` tasks 4.9 ticked, pointing here;
  - cat `TASKS.md`: replace the "Metal CPU round trips" item with the result; add the flip-wait follow-up (design D6) and the D3D11 `sync_guest` follow-up for its report and mid-frame dumps (proposal, Impact).
  Done: both toolkit headers in 5437712; `render-gpu-backend` 4.9 ticked; TASKS.md item replaced, with the D6 flip-wait and D3D11 `sync_guest` follow-ups and optional 6.1.
- [x] 7.3 Fable review of the branch; fixes go back to this branch's agent, never to the main session. Then the orchestrating session merges: toolkit `--no-ff` into `posix-host/portability`, cat `--no-ff` into `main`.
  - Archive note: done. Fable reviewed the branch; its fixes are toolkit ad1a241 and cat 873be3e. Merged as toolkit 81be009 and cat b607417.
- [x] 7.4 After the merge (orchestrating session): copy untracked notes to `notes/metalrb/`; the runs are already in `runs/metalrb/` (copy any new shots there with `cp -c` if they were made elsewhere); `git worktree remove --force` both worktrees and `rm -rf wt/metalrb`, keeping the branches; `scripts/bench.sh integrate` and golden on the Linux/Proton host; update `cat/TASKS.md`.
  - Archive note: done. The Linux/Proton host `integrate` plus golden ran after b607417 (rc=0; attract-cliff EXACT, the other 7 frames CLOSE), `wt/metalrb` is removed, the notes live in `runs/metalrb/`, and TASKS.md is updated (cat 97f95f6).
