## Context

### What is fixed (from `spike/fps` 4abc2fb, measured 2026-10-05)
- **The main loop.** `sub_0005F960` stores, per frame:
  - the wait `[0x3FD344]`;
  - the step `[0x3FD33C]` = `[0x3FD340]` (2 in the 3D scenes 4, 0xA and 0xB; 1 in menus);
  - the pad divisor `[0x4AC760]`.

  It then polls input, runs update and draw (`sub_00062FB0`), spins on the vblank count at `0x60475` and swaps. Menus already run at 60 fps (wait 1). 3D runs at 30 (wait 2).
- **Gameplay ignores the step.** The player, the camera, animation, particles, AI and event timers advance a fixed 1/30 s per frame. At step 1 and wait 1, a stage plays at 2x.
- **Time control.** The 20 time-control rate stores (`0x65C65`…`0x66DA8`) drive the world clock `[0xEC4C14]` and the HUD timer `[0xAE7428]`. Halving them fixes the timer, and nothing else.
- **mod60.** A real 60 fps BLiNX 2 needs an estimated 300 to 800 patched sites (XL, months).

### What the vertex constants hold (merged as cat 0fa905a, `openspec/changes/free-camera/spike.md` §5)
- `c[100..103]`: **world×view** (W·V) of the model being drawn, a 4x4 whose last row is (0,0,0,1). `c[104..107]` is a copy.
- `c[0..47]`: per-batch bone and matrix palettes. Whether they also carry the view is open (free-camera M0a).
- `c[112]`: a view-space light or up vector.
- **`V_game`, the view matrix itself, is not yet located.** `0xAAF450` is a ring of per-model W·V matrices, not a view. Free-camera task M0a finds `V_game`. Route A shares that result instead of searching again.
- The roles differ per program. Any interpolator must classify rows per program, not hard-code row numbers (task 2.3).

### What the renderer gives us (toolkit `posix-host/portability` 3e69844a)
- **The draw path.** `draw_primitive()` (`nv2a_pb_exec.c:6125`) hands each backend a small `nv2a_pb_draw`: prim, 16 attribute descriptors, u16 indices, inline vertex data (`inline_data`/`inline_buf`) and a `program` flag (vertex program or fixed function). The rest is live global state, read inside `on_draw`: `s_vsh.c[192][4]`, the program, the textures, combiners and the render target.
- **Nothing is retained.** The executor copies nothing. D3D11 and Metal read guest vertex, index and texture memory inside `on_draw` into GPU rings. No per-frame draw list exists. A replay must keep frame N's uploaded data alive, because the guest is writing frame N+1 into the same memory by then. The rings do not guarantee that today:
  - Metal rings reset after each wait and also on a mid-frame overflow (`flush()`, `nv2a_pb_metal.m:372-395`);
  - D3D11 `ring_map` maps with DISCARD on wrap (`nv2a_pb_d3d11.c:1140-1143`);
  - a texture re-uploaded mid-frame holds its end-of-frame content, so an earlier draw that sampled the old content replays wrongly.
- **Constants.**
  - D3D11 maps a 3 KB cbuffer per draw behind a memcmp shadow (`nv2a_pb_d3d11.c` about line 3100). 3 KB is 192 constants, 16-aligned, so it suits `VSSetConstantBuffers1` offsets, and `s_ctx1` (`ID3D11DeviceContext1`) already exists (`nv2a_pb_d3d11.c:552`).
  - Metal calls `setVertexBytes` with 3 KB per draw (`nv2a_pb_metal.m:2148`).
  - Programs are identified by a 32-bit FNV hash (`nv2a_backend_common.c:301`). Textures have `nv2a_tex_hash`.
- **Present.** FLIP_STALL → `present_pick` → `on_flip`.
  - D3D11 presents through a 2-buffer FLIP_DISCARD swap chain (`nv2a_pb_d3d11.c:526-529`). A second Present per flip on that chain can block the walker inside `on_flip`.
  - Metal blits zero-copy into the CAMetalLayer and writes back to guest RAM only on demand.

  An extra frame can be presented from the backend without touching the walker's flip counters (`s_gpu.flips`, `xbox_PacingFlip`).
- **Render-to-texture.** Both backends sample their own targets (`rt_texture`, self-copy) and track staleness (`nv2a_rt_own`, rt-stale-alias). There is no per-frame RT dependency graph, no depth readback, no motion vectors and no previous-frame state.
- **Cost today.**
  - Metal `@stage1`: 2.1-4.1 ms GPU and about 7 ms walk per flip at 3x (the Metal zero-copy present work). `lock60` sustained 58.5 fps on this Mac.
  - D3D11: the walker-perf review estimated 20-30 ms CPU per flip, of which VB/IB rings, state and DrawIndexed are about 10-14 ms. A replay re-runs neither the CPU vertex expansion (`s_vb_expanded`, `vb_begin`/`vb_end`) nor texture hashing, so it costs state, constants and DrawIndexed only. Task 4.1 measures that.
  - Native Windows paces at 38-42 ms once a frame exceeds about 6,000 draws (`win-kick-nap`). A replay doubles the submissions to about 9,600 per 33 ms.
- **Debug tool.** `RECOMP_DEBUG=vsh_const_dump` writes VCD1 records: flip, draw number, program hash and `c[192][4]` for every program draw. The record has no vertex-buffer, texture or render-target fields, and it skips inline and fixed-function draws.

### Offline numbers from an existing dump (no new run)
An existing local constants dump of `@stage1`, sampled every 120 flips (17 flips, 65,491 records, not published), was read with a scratch script. **Most of the sample is a held camera:** the dominant `c[100..103]` is identical from flip 1680 to 2520, and 7 of the 9 in-stage pairs are static. The numbers say little about pans and turns.

- **Draw count.** About **4,800 program draws per flip** in the stage (4,734-4,819 from flip 1440 on). There are 37 programs, and one (`F9BE5B67`) covers about 1,500 draws per flip.
- **What varies per draw.** Rows 100-106 vary the most, with about 420 distinct values per flip (`F9BE5B67`: 112). That matches the tracker item's W·V in `c[100..103]`. Rows 0-11 have 1-7 distinct values per program per flip (about 48 sets per flip), so they are per-batch palette data, not per-object transforms. Rows 138-151 have 1-20 distinct values, with no evidence of bones.
- **Order stability.** Matching the program-hash sequence between samples 120 flips apart (4 s) gives **91-99%** of draws. Hash-only matching is ambiguous (1,500 draws share one hash), and the camera is mostly held, so this is only a hint of order stability, not a match quality. Task 2 measures the real thing on consecutive flips and per scene class.

## Goals / Non-Goals

**Goals**
- Rate every route to 60 fps or more that does not retime the whole engine. For each: the visual result, feel and latency, artefacts, risks, effort, generic against title-only, and fit with the enhancements layer.
- Pick an order with cheap gates first, so that no L or XL work starts before a probe shows it can pass.

**Non-Goals**
- Building anything in this change. The probes in `tasks.md` are run later, each in its own worktree.
- Retiming the game logic (mod60). It is reassessed in route D and stays parked.
- The free-camera mod and the mod layer, which are the tracker item's subject. Route A only reuses `V_game` from free-camera M0a.
- Turbo or fast-forward. The user said no on 2026-10-05.
- FSR 3 and a DX12 or Vulkan backend (the user, 2026-10-17).

## Route inventory

### A. Renderer-side draw-replay interpolation (logic at 30, rendering at 60 or more)

The user's decisions (2026-10-17): route A is in scope, opt-in and default OFF, at 60 Hz first. It ships on Metal and D3D11; D3D11 covers native Windows and the Deck through DXVK. If the Deck cannot afford the replay, it ships without the Deck and the gap goes in TASKS.

**How it works**
1. Record frame N's draw list in the backend: the draw record (including inline and fixed-function draws), the constants and the bindings. Keep its VB, IB and texture uploads alive for one more frame.
2. Match each draw to one in frame N-1. The key:
   - program hash (or the fixed-function state);
   - attribute offsets and strides;
   - index count;
   - texture offsets;
   - render-target offset;
   - order within the run of draws with the same key (an LCS over the sequence).
3. For a matched draw, interpolate the constant rows that differ between N-1 and N, by the role task 2.3 assigns per program:
   - **W·V** (`c[100..107]` in BLiNX 2): decompose into rotation, translation and scale, slerp the rotation, lerp the rest. Plain lerp is the fallback for small deltas.
   - **palette matrices** (`c[0..47]`): the same, per 4x4 (or 4x3) matrix.
   - **view-space vectors** (`c[112]`): lerp and renormalise.
   - **scalars** (colours, UV scroll, fog): lerp, or copy N's value.
4. Present the mid-frame (t = 0.5) at the half-way vblank, then N. A later follow-up (not in the first version) presents t = 1/3 and 2/3 at 90 Hz, or 1/4, 2/4 and 3/4 at 120 Hz. Arbitrary display rates fall out of the same code, as in RT64.

**Camera factoring (improves rotation quality)**
- The constants hold W·V, not W·VP. Write each draw as `W = (W·V)·V⁻¹` and interpolate W and the camera V separately. The camera becomes a quaternion plus a position.
- **V sources:**
  1. `V_game`, once free-camera M0a finds it (BLiNX 2 only, shared with the tracker item);
  2. the generic fallback: the most common W·V among a frame's draws, on the assumption that static-world draws have W = I. This is weak: in the sample it covers only 387-433 of about 4,800 draws.
- Task 2.5 compares the two.

**Edge cases**
- **Unmatched draws**, such as a spawn, a despawn, a culling change or an LOD switch: draw them at N (t = 1). A spawn appears half a 60 Hz frame early, which matches what Zelda64Recomp does by default.
- **CPU-written vertices** (particles, trails, any pre-transformed or inline geometry):
  - with the same VB address, the same vertex count and a small per-vertex delta, lerp the positions on the CPU or in a compute pass;
  - otherwise draw them at N, so they step at 30.
- **HUD and 2D.** Screen-space draws have constant transforms. Interpolation leaves them as they are, and HUD digits change at 30, as on the console. Sliding 2D panels step at 30 unless their quad constants are matched and lerped.
- **Cuts.** Detect a cut when V's delta passes a threshold, or when the matched fraction falls below about 70%. Also detect scene changes (`[0xAE73F0]` changes, title-specific) and loading screens. On a cut, repeat N; never smear.
- **Pacing.** Interpolate only while the title paces at two vblanks per flip. BLiNX 2 menus already run at 60 (wait 1), and interpolating them would show stale frames. The executor knows the vblank count between flips, so this detection is generic.
- **Time control.**
  - Stop (rate 0): N-1 and N are equal, so the mid-frame is equal too, which is correct.
  - Slow, fast and rewind: objects move by whatever the game moved them between frames, and interpolation follows that. Rewind interpolates backwards, which is correct.
  - The risk is in the **post effects**. The time-control blur, the glow (`fx.glow`) and any pass that reads a target rendered in an earlier frame (feedback) would accumulate twice if the replay re-runs them on the same host target. Rules: replay into host-only targets; give a pass that samples an RT from frame N-1 the N-1 copy; on Metal, never write a replay back to guest RAM.
- **FMV.** The movie quad's texture changes each frame, so the draw is repeated, not lerped. That is correct.

**Present scheduling, per backend**
- **Metal.** Present the mid-frame with `presentDrawable:atTime:` (or `afterMinimumDuration:`) at the half-way vblank, then N one vblank later. The layer needs enough drawables (`maximumDrawableCount` 3) so that the walker never waits on one.
- **D3D11.** The 2-buffer FLIP_DISCARD chain cannot take two Presents per flip without blocking `on_flip`. Options, in order: a third buffer plus a waitable swap chain (`DXGI_SWAP_CHAIN_FLAG_FRAME_LATENCY_WAITABLE_OBJECT`) so the walker waits only on its own frame; or a present thread that issues the second Present under the context lock. Task 4 picks one by measurement.
- Both: the gates in tasks 3.6 and 4.1 count walker stall time inside `on_flip`.

**Quality, latency and cost**
- **Visual result.** Camera motion, the player, enemies, platforms and rotating pickups get true 3D intermediate poses, with no image warping or ghosting. Ghosting is the main weakness of the image-space routes.
  - Artefacts: particles stepping at 30 (or, worse, mis-matched); rare pops on the frame where the match fails; "paper" shrink on large per-frame rotations if decomposition is skipped. Ship of Harkinian documents that last effect and mitigates it in model space.
  - At 30 → 60, the per-frame deltas are small, so plain lerp is mostly fine.
- **Feel and latency.** Input is still sampled at 30 Hz and the game still reacts at 30 Hz, so the controls feel like stock but look smoother.
  - Latency is counted in whole vblanks. If the replay finishes before the half-way vblank, N goes out **one vblank (+16.7 ms)** later than stock; if it misses, **two (+33 ms)**. `spike.md`'s +33 ms is the miss case; the design target is +1.
  - Extrapolation (presenting N+½ from N-1 and N) adds no latency, but overshoots on stops, turns and jumps. It is a later variant for the camera only, not the default.
- **Cost.**
  - **GPU.** Each mid-frame replays about 4,800 draws. Metal GPU time is 2-4 ms per frame, so 2x fits easily on this Mac.
  - **D3D11.** A replay costs state, constants and DrawIndexed, not vertex expansion or hashing. Mitigation: one big constant buffer per frame, bound with 16-constant-aligned offsets through `s_ctx1->VSSetConstantBuffers1`, so the replay maps once instead of per draw. That rework is **S-M**. The Deck budget is the risk, measured by task 4.1.
  - **Native Windows.** It already paces at 38-42 ms above about 6,000 draws. With a replay, about 9,600 submissions per 33 ms may not fit. Task 4.5 is a **gate** there (each run needs the user's OK, since Windows needs a reboot). Native Windows is a required platform, so a failure stops the D3D11 release, not just the Deck.
  - **CPU backend.** It cannot do it. It logs that it ignores the option.

**Size, split and enhancements fit**
- **Effort.** S probe; M for a Metal prototype to a gate; L to production on Metal; M for the D3D11 mirror, including the S-M constant-buffer rework. **L overall.**
- **Generic against BLiNX-2-only.**
  - Generic (toolkit): about 90%. That covers the recorder, the matcher, the row classifier, the interpolator, the cut and cadence detection, and the present scheduling.
  - BLiNX 2 only: `V_game` from free-camera M0a, a scene variable for cuts, per-hash hints (for example "this program is a particle system, never lerp") in config, and the post-effect rules if the generic ones are not enough.
  - Burnout 3 races at 30 with a chase camera, which is the ideal case. Its speed blur is the post-effect risk.
- **Enhancements fit.**
  - The key belongs to the **toolkit**, next to the other render and present keys in `enhance_cfg.c` and the `recomp_env.h` enhancements block: `render.interp = "off" | "on"` (env `RECOMP_RENDER_INTERP`). Decided (2026-10-17); 60 Hz output only in the first version.
  - `fps.mode` (`RECOMP_FPS_MODE`) is a cat game key and stays `lock30`. An optional alias `fps.mode = "interp60"` maps to `render.interp = on` with `fps.mode = lock30` underneath, and logs it.
  - Default OFF, so every replay branch is unreachable at off.
  - Goldens pin it off through `game.toml` `[golden] enhance_stock`, and the harness fails a run that reports it on.
  - Metal and D3D11 together; CPU ignores it and logs one line.
  - DEBUG keys `interp_off` and `interp_t=…`, and TRACE `interp` (match statistics per 600 flips).

**Verdict: the most promising route. Gate it on the probe (task 2), then on a Metal prototype (task 3), then on D3D11 (task 4) so it ships on both.**

### B. Image-space frame generation

**B1. MetalFX frame interpolation (`MTLFXFrameInterpolator`)**
- **The user's decision (2026-10-17):** allowed as an optional Metal-only path after route A. A MetalFX build requires macOS 26 (no weak-linking) and is selected by the toolkit build option `XBOXRECOMP_METALFX`, off by default. The D3D11 gap goes in TASKS.
- **Availability.** macOS 26+ and iOS/iPadOS 26+ (headers checked in the MacOSX 26.5 and 27.0 SDKs). Device support is checked at run time with `+supportsDevice:`.
- **Inputs:**
  - colour, and the previous colour (`prevColorTexture`, macOS 26; only `requiresPrevColorTexture` is new in 27);
  - **depth** and **motion vectors**;
  - `depthReversed`, which defaults to YES. NV2A depth is not reversed, so we set NO;
  - an optional **UI texture**, composited without warping;
  - deltaTime, near, far, FOV and aspect, plus worldToView and viewToClip (macOS 27);
  - `shouldResetHistory` for cuts.

  It interpolates between two rendered frames, so the latency is like A's (+1 vblank or more).
- **What we must supply:**
  - **Depth.** It is on the GPU already, per zeta surface.
  - **Motion vectors.** Three ways:
    1. camera-only, from depth and V of two frames. This needs V (`V_game` or the fallback). M effort; moving objects get camera MVs only, so they ghost.
    2. per-draw: compile each vertex program with a second position output evaluated under frame N-1's matched constants, and write `pos_N - pos_N-1` to an MV target. This needs A's matcher, but a failed match degrades to camera MVs instead of a pop.
    3. no MVs: not supported by MetalFX.
  - **UI.** The HUD must be split out: route screen-space (HUD-class) draws to the UI texture. The HUD pack and aspect work already classify HUD draws by texture and program, so reuse that.
- **Quality.** Good on camera pans and solid geometry. Artefacts on transparencies and particles, on post effects (glow, the time-control blur), on disocclusion at the screen edges and on thin geometry. The 30 → 60 base is low for any frame generator: vendors recommend a 60 base, and the errors grow with the per-frame motion.
- **Effort and split.** M to L, Metal only, macOS 26+. Under "backends agree" it is a Metal-only enhancement, recorded in TASKS as such.
- **Verdict: allowed, after A.** It is worth it only once A's matcher exists, because without per-draw MVs it ghosts every moving object.

**B2. AMD FSR 3 frame generation on D3D11**
- **Out of scope (the user, 2026-10-17).** FSR 3 frame interpolation (and the newer FSR Redstone ML frame generation) needs DX12 or Vulkan, and SM 6.x wave operations that D3D11 (SM 5) lacks. A D3D11on12 bridge costs about 10-15%, and OptiScaler's own frame generation is DX12 only.
- A future native Vulkan backend for the toolkit would be a separate strategic decision on its own merits (portability, the Deck without DXVK). FSR alone does not justify it.
- **Verdict: no.**

**B3. Driver and external tools (zero toolkit code)**

| Tool | Where | Notes |
|---|---|---|
| Lossless Scaling (LSFG) | Windows | paid; windowed or borderless capture |
| lsfg-vk (2.0 is out) | Linux and the **Steam Deck** | a Vulkan layer; works under Proton through DXVK, but compatibility varies per Proton build; Decky plugin `decky-lsfg-vk`; needs a Steam copy of Lossless Scaling |
| AMD AFMF / AFMF 2 | Windows, Radeon RX 6000+ and Radeon 700M | driver-level; DX11 and DX12 (AFMF 2 also Vulkan and OpenGL); AMD recommends a base of 55-60 fps or more, so a 30 base is below vendor guidance |
| NVIDIA Smooth Motion | Windows and Linux, RTX 40 and 50 | driver-level; DX11, DX12 and now Vulkan; on Linux `NVPRESENT_ENABLE_SMOOTH_MOTION=1` |
| gamescope | the Deck | has no frame generation; it only shapes the output |
| macOS | — | no system-level frame generation |

- **Quality.** Optical flow on the final image, with no depth or motion vectors. Expect HUD ghosting (the HUD is warped with the scene), particle and transparency smearing, and edge artefacts. All of it is worse at a 30 base. Latency is +1 base frame or more.
- **Our part (S).**
  - A short doc section for players.
  - A compatibility check: even 33.3 ms flips (already better with `present.pacing=sleep` and the ns vblank clock); borderless window; `present.vsync`.
  - Nothing in the build changes, and goldens are unaffected.
- **Verdict: do it now, as documentation** (decided 2026-10-17). It is the cheapest 60 fps look for Deck and Windows players who want it, and it costs us no engineering. It is not a substitute for A.

**B4. Our own optical flow or motion-vector frame generator**
- An own warp shader with our MVs, on both backends. It is the B1 algorithm without Apple's network.
- **Verdict: no.** L to XL, worse than B1 and riskier than A, which already has the information B4 would estimate.

### C. Hybrid or partial logic retiming

**C1. Camera logic at 60, everything else at 30 (a reduced mod60 on the camera only)**
- **What it needs.** Find the camera controller and halve its integrators, about 20-50 sites (mod60 §5, M). Then run it twice per 30 Hz tick, or at step 1 in a 60 Hz loop that runs the rest of the update every other frame. The second needs splitting `sub_00062FB0`'s update from its draw, which nobody has located yet.
- **Result.** The camera follows a player who moves in 30 Hz steps. Against a 60 Hz camera, the player and every moving object **judder visibly**, so the picture looks worse than a uniform 30. The camera's look-ahead and collision also read 30 Hz player state.
- **Verdict: no.**

**C2. The rate-store patch plus the camera**
- The mod60 data (`mod60.md` §1b, §1c) rules this out:
  - after the rate patch, about 1,170 linear floats still advance at 2x;
  - the player was measured at 2x;
  - fixing the camera too leaves the player, enemies and animation at 2x.
- **Verdict: no.** Still a 2x game.

**C3. A renderer-side partial: camera-only replay**
- This is route A with matching off: re-render N with the camera at t = 0.5, through the V factoring.
- **Result.** The static world (most of a BLiNX stage) pans smoothly. Moving objects judder, as in C1.
- **Verdict: as a product, no. As a milestone, yes.** It is A's first prototype step (task 3.2), because it tests replay, present scheduling and the V factoring without the matcher.

### D. The full mod60, revisited
**What changed since 2026-10-05:**
- **The recompiled C is ours to instrument.** mod60 §1b failed to find the player's authoritative state because a write watchpoint on 16 KB arm64 pages missed it. A generator option that instruments stores to an address range would find every writer of `0xAE7744` and its copies deterministically, with no paging. This is new and cheap (S to M). It is a store-side twin of `--trace-functions`.
- **Tooling that exists now:**
  - `--spin-waits` showed that a per-site generator emission (`RECOMP_SPIN_WAIT(va)`) works cleanly; the "patchable immediates" idea (`MOD_IMM(site, stock)`) is the same shape;
  - `vsh_const_dump`, `mem_dump`, `pad_peek` and `poke`;
  - The tracker item's matrix-ring findings, and `V_game` once M0a lands.
- **`--hook-functions`** is still only proposed (enhancements-layer D6); it is not in `tools/recomp` today.

**Effect on the estimate.** None of this changes the 300 to 800 sites or the data-driven timing (event scripts, camera paths and motion data in frames), and none of it touches the validation matrix across about 30 stages, the bosses and the time-control puzzles. It cuts the discovery cost per site, perhaps by a fifth to a third. It does not cut the semantics work or the validation.

**Verdict: still XL and BLiNX-2-only. It stays parked** unless the funded store tracing (task 6) shows a path. It is the only route to real 60 Hz input and logic.

### E. Guest-side render-twice (the Ship of Harkinian approach)
- Split the guest's update from its draw pass. Snapshot the object state at N-1 and N, write lerped positions and rotations into RAM, call the draw pass, then restore.
- Ship of Harkinian tried interpolating inputs this way and found rotations looked wrong. It then moved to recording and interpolating final matrices in a tree keyed by hand-inserted `FrameInterpolation_RecordOpenChild` calls, on a fully decompiled game.
- Here we have no decompilation, the draw pass may mutate state, and every object class needs its layout known.
- **Verdict: no.** XL and BLiNX-2-only, and route A gets the same result at the matrix level without knowing any object.

### What others did, and what transfers

| Project | Approach | What transfers |
|---|---|---|
| Zelda64Recomp / RT64 | Deferred matrix interpolation in the renderer. The game is tagged with matrix-group IDs through `gEXMatrixGroupDecomposed` (per-component interpolate or skip, decomposed order). The tagging patches run to about 8,000 lines (actor, camera, terrain, UI, particle, billboard, effect, sky and sword-trail tagging) on a fully decompiled game, with camera-cut heuristics and per-scene overrides | Route A's design: decomposition, per-component skip, explicit cut handling. The warning: a good result needed identity tags. Our matcher replaces tags with draw signatures, which is the approximation `enhancements-layer` D5 already named |
| Ship of Harkinian (OoT PC) | Records the matrix-stack tree per frame, keyed by call-site nodes, and replays it at t; mitigates the "paper effect" on about 180° rotations by interpolating in model space | Decomposition matters for spinning objects (BLiNX pickups and enemies); per-draw identity is the hard part |
| sm64 PC ports (60 fps patch) | Interpolation in the game's graph-node renderer, keeping previous transforms per object | Decomp-only; nothing transfers directly |
| UnleashedRecomp (Xbox 360) | The engine is dt-based, so high fps is native, after fixing many glitches that assume 30 fps; its community still points players at Lossless Scaling for above 60 | A dt engine still needs fixes, so a fixed-step one is far worse (it confirms D). External frame generation is an accepted player-side answer (B3) |
| Emulator 60 fps patches (PCSX2, Dolphin) | Per-game cheats that change a frame-time constant or unlock a variable-dt engine | Works only for dt engines. BLiNX 2 is not one (its step is ignored) |

## Comparison

| Route | Look | Feel and latency | Main artefacts | Effort | Generic / title | Enhancements fit | Verdict |
|---|---|---|---|---|---|---|---|
| A draw-replay interp | 60+ true 3D in-betweens | 30 Hz input; +1 vblank (+2 on a miss) | particles at 30; rare pops; cuts need detection | L (D3D11 rework S-M inside it) | ~90% generic (helps B3) | toolkit key, Metal + D3D11, CPU logs | **go, gated** |
| A extrapolation variant | 60, no added latency | 30 Hz input; +0 ms | overshoot on stops, turns, jumps | +S on A | generic | same | later, camera only |
| B1 MetalFX FI | 60, good on solids | +1 vblank or more | ghosting on objects without per-draw MVs; particles, glow, blur | M-L (+A's matcher) | generic, Metal-only | Metal-only option, TASKS gap | allowed, after A |
| B2 FSR 3 FG on D3D11 | — | — | — | XL or bridge | — | — | out of scope |
| B3 external tools (LSFG, lsfg-vk, AFMF, Smooth Motion) | 60-120, HUD ghosting | +1 base frame or more | HUD and particle smear at a 30 base | S (docs) | user-side | outside the build | **do now (docs)** |
| B4 own optical flow | worse than B1 | +1 vblank or more | everything B has | L-XL | generic | — | no |
| C1 camera logic at 60 | judder on every moving object | 30 Hz input | looks worse than 30 | M + update/draw split | title | — | no |
| C2 rate stores + camera | 2x game | — | — | M | title | — | no |
| C3 camera-only replay | static world smooth, objects judder | +1 vblank | judder | S-M | generic + V | — | milestone of A |
| D full mod60 | real 60 | real 60 Hz input | 2x-speed regressions | XL (months) | title-only | separate build or MOD_IMM | parked |
| E guest render-twice | like A | +1 vblank | state mutation | XL | title-only | — | no |

## Recommendation and order

1. **B3 docs (S)**, decided 2026-10-17. A player-facing section on external frame generation (Lossless Scaling, lsfg-vk with its Decky plugin on the Deck, AFMF, Smooth Motion): what to expect at a 30 base, HUD ghosting, and the recommended settings (`present.pacing=sleep`, borderless window). It ships nothing and is unsupported, but honest.
2. **Task 2: the draw-matching probe (S, offline plus Metal dump runs).** It decides whether route A is worth a prototype. It includes a pan and turn route, because the existing sample is mostly a held camera.
3. **Task 3: route A on Metal (M).**
   - 3.2: camera-only replay (C3) for the plumbing;
   - 3.3: matched per-draw interpolation.

   Gate: the pop rate, the present cadence, walker plus replay time, and the user's own look at side-by-side footage. Stop here if the gate fails.
4. **Task 4: the D3D11 mirror, with the constant-buffer rework, a native Windows gate and a Deck gate (M).** Native Windows is required. If only the Deck fails, route A ships on Metal and native Windows and the Deck gap goes in TASKS.
5. **Task 5: MetalFX frame interpolation (M-L), only after A passes on Metal.** It reuses A's matcher for per-draw motion vectors. It is a quality comparison against A: A's in-betweens are exact for matched draws, and MetalFX may handle particles and unmatched draws better.
6. **Task 6: the store-tracing generator option (S-M, about 1 pw; funded).** It serves free-camera M0a and the mods as much as mod60. mod60 (D) stays parked unless the traces show a path.

Burnout 3: once A passes on BLiNX 2, the same probe (task 2) runs on a B3 race. B3's 30 Hz races with a chase camera are the best case for A. This follows the Burnout 3 upstream gate if any of it goes upstream.

## Risks
- **[The user's 2026-10-05 "no interpolation"]** → superseded: on 2026-10-17 the user put interpolation back in scope, opt-in and default OFF.
- **[Matching fails on many draws in busy scenes or during pans]** → task 2 measures it per scene class, with a pan and turn route. A matched fraction below the gate stops A before any backend code exists.
- **[Row roles differ per program]** → task 2.3 classifies rows per program from the data; nothing hard-codes BLiNX 2's rows into the toolkit.
- **[Replay data overwritten before replay]** → task 3.1 sizes the rings for two frames and wraps them only at a frame start, or copies; mid-frame texture re-uploads are versioned (task 3.4).
- **[D3D11 cannot fit the replay on the Deck]** → task 4.1's gate after the bulk constant buffer. If it still fails, route A ships on Metal and native Windows without the Deck, and the Deck gap goes in TASKS.
- **[Native Windows draw-count pacing]** → task 4.5 is a gate (runs need the user's OK for the reboot). A failure there stops D3D11 shipping and goes to the user.
- **[A second Present blocks the walker]** → per-backend present mechanism above; walker stall time is part of the gates.
- **[Post effects double-accumulate or read stale targets]** → replay only into host-only targets. Task 3.4 has an explicit check on the time-control blur and on `fx.glow` frames.
- **[Latency complaints]** → +1 vblank is the target and +2 the miss case. The toggle stays default OFF; extrapolation for the camera is a later variant.
- **[Goldens contaminated]** → goldens pin `render.interp` off, and the harness fails a run that logs it on, as it does for `render.scale`.

## Decisions (2026-10-17)
1. **Interpolation is back in scope.** Tasks 2-5 go ahead. Route A stays opt-in and defaults OFF.
2. **60 Hz first.** 90, 120 and display-rate output are a later follow-up. The key is the toolkit key `render.interp = "off" | "on"` (env `RECOMP_RENDER_INTERP`). Cat's `fps.mode` stays `lock30`; an optional cat alias `fps.mode = "interp60"` may map to `render.interp = on`.
3. **Platforms, not "both or not at all".** Route A ships on Metal and D3D11. If D3D11 on the Deck cannot afford the replay, it ships on Metal and native Windows D3D11 without the Deck, and the Deck gap goes in TASKS. That makes the native Windows check (task 4.5) a real gate; each run there still needs the user's OK.
4. **MetalFX is allowed** as an optional path after route A, and it **requires macOS 26**: no weak-linking. It is selected by a toolkit build option, `XBOXRECOMP_METALFX`, off by default. With it on, the build links MetalFX and raises the Mac deployment target to macOS 26; the stock Mac build keeps its current minimum. The D3D11 gap goes in TASKS.
5. **Store tracing is funded** (task 6). It also serves the tracker item's free camera (M0a) and the mods. mod60 itself stays parked unless the tracing shows a path.
6. FSR 3 and a DX12 or Vulkan backend are out of scope.
7. **External frame-generation docs: yes.** Task 1 writes a short player-docs section on Lossless Scaling, lsfg-vk, AFMF and Smooth Motion, marked unsupported but known to work: what each needs, and that a 30 fps base is below vendor guidance. No code.

No open questions remain.
