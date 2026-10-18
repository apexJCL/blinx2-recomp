## Why

The GPU backends keep a render target for every surface the title draws into, and never ask whether the title still uses that memory as a surface. On the Mac (log `runs/stage1-issues/user/game-20261006-101123.log`), the Sweepers hub creates two 512x512 targets at 0x0169D000 and 0x0119B000 (1 MB each at pitch 2048). Stage 1 then reuses that memory: textures, its own 256x256 water targets (0x011A5000, 0x01225000, both inside the 0x0119B000 MB) and dense float and short data (vertex or collision tables, `runs/stage1-issues/m1-layout/mem/`). Seven of the eight target slots are in use, so nothing evicts the hub's two, and Metal does two wrong things with them:

- **Stale binding.** `rt_texture` binds any live target whose address equals a texture's offset (low 27 bits). A stage texture loaded at the start of either block samples the hub's old image instead of its texels. D3D11's `rt_texture` does the same.
- **Write-back over live data.** Before hashing and decoding a texture whose bytes overlap a dirty target, `tex_bind` writes that target back into guest memory (`rt_sync`, counted as "decode syncs"). The hub target's old pixels then overwrite 1 MB of whatever stage 1 keeps there. The session log ends with "2 decode syncs". Eviction (`rt_free`) writes back too, but only a target that was presented, so it does not reach the hub's off-screen targets. D3D11 never writes guest memory, so there only the stale binding applies.

This fits the play-test reports. Metal-looking surfaces (barrels, door, switch buttons, the floating plates in `water-metal.mov`, red there and cyan glass in the reference) showed odd textures, and changing the render scale, which rebuilds every target, cleared them. If the overwritten block holds game state (water-plate or collision data), it may also explain the water-walking jitter that activating the switches fixes. Proving or refuting that is part of this change (task 1.3): the jitter may have another cause, and the fix stands on the texture evidence alone.

## What Changes

- A target is valid as a texture source, a write-back source or a reusable surface only while the title still owns its memory as a surface. The backend records a hash of the guest bytes under each target when it last knew them: at creation (the bytes the seed reads) and after each write-back. Before it binds, writes back or reuses a target that was not drawn in the current flip, it rehashes once per flip. A mismatch means the title rewrote that memory, so the target is dropped without a write-back.
- Creating a target retires every other target whose guest range overlaps the new one, in whole or in part: written back first if its memory is unchanged, dropped if it is not.
- Both GPU backends (Metal and D3D11) get the same rule through a shared helper in `nv2a_backend_common.h`. The CPU path draws into guest memory and decodes from it with no target cache, so it is unaffected.
- A headless repro: the hub, then stage 1, then frame dumps on the plates or barrels, plus a guest memory compare before and after the first decode sync.

## Capabilities

### Modified Capabilities
- `gpu-backend`: render-to-texture, surface reuse and lazy write-back honour guest rewrites of a target's memory.

## Impact

- toolkit: `src/d3d/nv2a_pb_metal.m` (`surface`, `rt_texture`, the `tex_bind` decode sync, `rt_free`, `metal_sync_guest`, the flip summary), `src/d3d/nv2a_pb_d3d11.c` (`surface`, `rt_texture`), `src/kernel/nv2a_backend_common.h` and `.c` (helper), new ctest `tests/rt_alias`, `tests/nv2a_backend_smoke` and `tests/d3d11_backend_smoke` cases.
- cat: input preset `@hub-stage1` in `src/pad_input.c`, a golden frame candidate, a `docs/env.md` row for the A/B key.
- Cost: one hash of a target's bytes (up to 1 MB) per target per flip, only for a target not drawn this flip that is about to be bound, written back or reused. Bounded by the slot count (8) and measured in the tasks; a row-sampled hash is the fallback if the full one shows in `metal_prof`.
