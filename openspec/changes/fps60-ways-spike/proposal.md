## Why

The user asked on 2026-10-17 for another look at 60 fps or more in BLiNX 2 gameplay. This time the question is which routes avoid retiming the whole engine, and how good each result would be.

The earlier fps spike (cat `spike/fps` 4abc2fb: `openspec/changes/fps-modes-spike/spike.md`, `mod60.md`, `v1-pacing-proposal.md`) settled the engine side:

- Stage logic, the player, the camera, animation, particles, AI and event timers all advance a fixed 1/30 s per rendered frame.
- Every engine-side lever plays the game at 2x speed. That covers the step variable, the wait count, the vblank rate and the swap interval.
- Halving the 20 time-control rate stores fixes the HUD timer and the time-controlled objects. The player and the camera still run at 2x.
- A real 60 fps mod (`mod60`) needs 300 to 800 patched sites. That is XL, months of single-agent work.

The enhancements-layer design (cat `spike/enhancements`, D4) had assumed the engine's vblank count was multiplied into movement. The spike measured that it is not. So D4's "drive the engine's own count" route is closed, and D5 (frame interpolation) is the only generic route left. The `fps-pacing` change listed interpolation as a separate spike in its non-goals. This change is that spike's plan, widened to every non-retiming route.

**A decision to revisit.** On 2026-10-05 the user decided "Interpolation: not acceptable. Skip it." (`spike.md`, User decisions 2). That answer was given against a +33 ms latency estimate and a single XL option. This change brings interpolation back with better numbers: a latency target of one vblank (+16.7 ms, +33 ms only when a replay misses), a cheap probe that gates it, and image-space options that cost us almost nothing. On 2026-10-17 the user put interpolation back in scope: opt-in, default OFF, 60 Hz first. The decisions are listed at the end of `design.md`; no open questions remain.

## What Changes

This is a spike plan. It does not change behaviour, it has no spec deltas (`skip_specs: true`), and it is post-v1.

- **`design.md` lists every route** with a rating: the visual result, gameplay feel and input latency, artefacts and risks, effort (S/M/L/XL), the toolkit-generic part against the BLiNX-2-only part, and how it fits the enhancements layer. The routes are:
  - A: renderer-side draw-replay interpolation;
  - B: image-space frame generation, through MetalFX, FSR 3, external tools, or our own motion vectors;
  - C: hybrid or partial logic retiming;
  - D: the full mod60, revisited;
  - E: guest-side render-twice;
  - plus what other recomp, decomp and emulator projects did.
- **`design.md` recommends an order:**
  1. document the external frame-generation tools (S, user-side);
  2. an offline draw-matching probe (S);
  3. a Metal prototype of route A, with a pop-rate and frame-time gate;
  4. the D3D11 mirror with a native Windows gate and a Deck gate; if only the Deck fails, route A ships on Metal and native Windows and the Deck gap goes in TASKS (the user, 2026-10-17);
  5. MetalFX frame interpolation as an optional Metal-only path after A, in a build that requires macOS 26 (build option `XBOXRECOMP_METALFX`, off by default), reusing A's matching (the user, 2026-10-17).
- **Funded:** a store-tracing generator option (task 6, about 1 pw), which serves the tracker item's free camera and the mods as well as a mod60 re-estimate. mod60 itself stays parked.
- **Out of scope:** FSR 3 and a DX12 or Vulkan backend (the user, 2026-10-17).
- **`tasks.md` lists the experiments,** each with a measurable success criterion and a stop rule.
- **Data gathered for this spike.** No new runs were made. The offline numbers come from an existing local constants dump of `@stage1` (not published, read only). Most of that sample is a held camera, so it says little about pans:
  - about 4,800 program draws per flip, across 37 programs;
  - per-object world×view in `c[100..103]`, which agrees with the tracker item (merged, cat 0fa905a); rows 0-47 hold per-batch palettes;
  - 91-99% of draws matched by program-hash order between samples 120 flips apart.

## Capabilities

### New Capabilities
- None. A route that passes its gate gets its own change with requirements, for example `frame-interpolation` under the enhancements layer.

### Modified Capabilities
- None.

## Impact

- Docs only: `openspec/changes/fps60-ways-spike/`.
- The follow-up experiments run on the Mac (Metal, `SDL_AUDIODRIVER=dummy`) and on the Deck (D3D11 under Proton, under the run lock). Each needs its own worktree and the user's go.
- Rules for any route that ships:
  - opt-in, default OFF, behind `XBOXRECOMP_ENHANCE`;
  - goldens pinned to stock;
  - Metal and D3D11 agree (route A on both), or the gap is recorded in TASKS (MetalFX);
  - the CPU backend logs that it ignores the option.
- The toolkit-generic parts (route A in full, and B's motion vectors) would also serve Burnout 3, which also runs its races at 30 fps.
- Related: the tracker item (merged as cat 0fa905a, `openspec/changes/free-camera/`) read the constant layout and found that the view matrix `V_game` is not yet located; its task M0a finds it. Route A's camera factoring and B's camera-only motion vectors would share that result, with a generic heuristic as the fallback. This spike does not repeat that work.
- Route A's key belongs to the toolkit enhancements layer (`render.interp`), not to cat's `fps.mode`.
