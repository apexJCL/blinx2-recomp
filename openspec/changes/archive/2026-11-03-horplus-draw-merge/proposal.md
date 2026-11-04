## Why

GitHub #6: on v2026.10.3 (Windows 11, Ryzen 5 2600, GTX 1060,
render scale 3, aniso 2, fullscreen, display.aspect 16:9) the last part of
level 2 (Sweepers, TomToms) is "extremely laggy".

Stage 2's wide views are about 8.4k batches a flip. Draw merging
turns them into about 3.1k draws. `merge_on()` turns merging off whenever
`display.aspect` is not stock or `render.snap_2d` is on above scale 1,
because Hor+ and the snap place each batch from its own vertices. So at
16:9 every one of the 8.4k batches is its own draw. The walker's time
adds to the guest's, since the guest spins at KickOff while it waits.

Measured on the stage 2 objectives flyover (flips with more than 7000
batches, `RECOMP_TRACE=flip`):

| run | draws | walk ms | draw ms |
|---|---|---|---|
| Mac Metal 4:3 | 3125 | 7.4 | 2.9 |
| Mac Metal 4:3, `pb_merge=0` | 8430 | 11.2 | 5.8 |
| Mac Metal 16:9 | 8663 | 12.0 | 6.1 |
| PC D3D11 4:3, scale 1 | 3125 | 11.4 | 5.1 |

At 4:3, `pb_merge=0` reproduces the 16:9 cost, so the cause is the lost
merging, not the Hor+ scan. On a Ryzen 2600 at scale 3 the extra walk
pushes the frame past 33 ms.

## What changes

- New backend hook `merge_placed(int program)` in `struct nv2a_pb_backend`
  (last field; NULL keeps today's behaviour). Under Hor+ or snap_2d,
  `merge_on()` holds a batch only when the hook accepts it.
- `nv2a_merge_placed()` in `nv2a_backend_common.h` is the shared rule. A
  batch may merge when all of these hold:
  - it is a program batch;
  - its program's aspect gate has settled as 3D (`two_d == 0` after 16
    batches);
  - the depth test is on;
  - it samples no render target.

  Hor+ centres such a batch and the snap never touches it, whatever its
  vertices. Every other batch is placed from its own vertices and is still
  drawn alone: pass-through batches, flat near layers, bands, screen quads,
  and programs not yet settled or seen 2D.
- D3D11 and Metal both implement the hook with the same rule.
- Stock (4:3, snap off) is unchanged, so the goldens do not move.
