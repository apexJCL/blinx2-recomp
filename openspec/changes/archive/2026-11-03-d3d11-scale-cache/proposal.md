## Why

A live `render.scale` change on D3D11 freezes the game for a moment. On the
Deck (GE-Proton11-7), the first flip at the new scale took 712, 196 and
151 ms for 1x to 2x, 2x to 3x and 3x to 1x on Jet Set Radio Future's title
(the tracker item's run, `bench-logs/20261027-170259`). Each of those flips uploaded
61-89 textures again, because D3D11's `scale_drop` frees the whole texture
cache. Its comment gives the reason as "a render-to-texture input is sized
by scale". This branch's own base run (`bench-logs/20261027-180628`, exe
2a2f38f1) measured 716, 213 and 158 ms; tasks.md 3.1 quotes that run and
the fix run beside it.

The tracker item removed the same drop from Metal (toolkit `f440873a`, merged in
`96263319`). There the flip after a change went from 175-235 ms to 6-12 ms.

## What changes

- D3D11 `scale_drop` (`src/d3d/nv2a_pb_d3d11.c`) keeps the texture cache and
  its hint table. It still releases the targets and depth buffers, clears
  `s_cur` and `s_stage_rt`, and resets the occlusion queries.
- The comment says why the cache is scale-independent. The log line becomes
  `render.scale=N from this flip: targets dropped`, as on Metal.

## Out of scope

- The CPU backend has no scale cache drop.
- Targets still lose their pixels at a change, as on any D3D11 eviction.
  The title redraws them in the next frame.
- The first change from 1x to any larger scale still costs about 575 ms on
  the Deck: the shader key carries a scale>1 bit (`key[36]`), so that flip
  compiles a new program set (draw 555 ms, 1 upload). Later changes reuse
  both sets. That is the tracker item.
