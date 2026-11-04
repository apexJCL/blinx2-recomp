## Context

Hor+ (`nv2a_aspect_place`) has these per-batch outcomes:

- centre: 3D, the projection widened;
- stretch or cover: 2D, from `two_d` and `full_w`;
- the HUD lift;
- the flat near layer (depth off);
- the screen quad (6 vertices or fewer, sampling a padded target);
- the band (depth off, bars).

Only centre is the same for every vertex set. A merged list is placed as
one draw, so merging is safe only for batches whose placement is centre.

## Decisions

- **D1. The rule reads only state set before the batch.** That state is
  the program flag, the depth enable, the program's aspect gate and the
  bound stages' texture addresses against the render targets. A chain's
  batches share every state but their vertices (that is what the walker
  merges), so each batch's answer is the same. The walker still asks at
  every batch's END; a batch answering no draws the chain held so far,
  then itself alone.
- **D2. The gate must have settled.** A program's first 16 batches are
  scanned. `two_d == 0` after that means all 16 were 3D. Programs still
  being scanned, or seen 2D, keep drawing alone. A program that turns 2D
  is still caught by the gate's recheck, which flips `two_d` so its next
  batch stops merging, but later than before. The gate's `n` counts
  draws, not batches, so with merging the every-256th recheck comes
  about 2.7 times later in guest batches (8.4k batches as 3.1k draws in
  stage 2). That recheck scans the merged list: up to 33 vertices across
  all of its batches. When those vertices span several depths, the scan
  sets `vary_z`, and the snap leaves that one draw alone. Hor+ ignores
  `vary_z`. Accepted: the late catch was already the gate's design
  ("caught then, late"), and a settled 3D program turning orthographic is
  rare.
- **D2a. Fixed-function batches do not merge under Hor+ or snap_2d.** The
  hook is asked at END with `vsh_batch_active()`. `ff_begin` runs at the
  draw, after END, so a fixed-function batch asks with `program` 0 even
  when it draws through its synthesised program. BLiNX 2's stage 2 world
  is program batches, so the fix covers it. Letting fixed-function
  batches merge would need END to know whether `ff_begin` will take the
  batch: a follow-up (tasks 4.1).
- **D3. A backend hook, not a core check.** The gate lives in each
  backend's vertex-shader cache (`vs->hp`), and the render-target test
  uses its own stage table. The core sees only an int. NULL means no
  merging under Hor+ or snap, which matches today's behaviour and the CPU
  rasteriser.
- **D4. No new key.** This is a performance fix to an existing path.
  `pb_merge=0` (debug tier) still turns all merging off.

## Risks

- A 3D program whose placement depends on its vertices in a way the gate
  does not see would draw differently when merged. The six outcomes
  above are the whole of `nv2a_aspect_place`, and centre has no input
  from the vertices.
