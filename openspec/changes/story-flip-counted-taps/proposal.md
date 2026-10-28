# Story golden: flip-counted taps and tmpfs dumps

## Why
The D3D11 `story` golden on the Linux/Proton host under Proton usually came back
INCOMPLETE for story-menu and story-hub. There were two causes, and both
come from the frame dumps:

- The D3D11 dumper writes each BMP synchronously in present. On
  the Linux/Proton host's data drive (a 5400 rpm HDD), once dirty pages pile up those
  writes block present for 0.4-3 s per frame. Every flip over 100 ms in
  the evidence runs fell inside an `fb_dump_at` window. The Deck writes
  to flash and does not stall.
- `@story-hub` timed its menu holds and taps in seconds (`wait 8`,
  `wait 7`, taps every 1.5 s). A stall in the tsedit dump window moved
  them up to ~165 flips away from the references, so the slot-list and
  hub anchors, and the frames counted from them, fell outside the dumped
  windows. The stalls also cost ~11 s of the 100 s run, so the hub
  frames were never reached.

## What changes
- `@story-hub` counts its menu holds and taps in pad polls: `wait polls
  476`, `wait polls 416` and `tap A every 90p`. Polls are one per flip
  in these menus, so the counts are about the old seconds at 60 Hz. The anchors
  then follow the game's frames, not wall time. `wait until 24` after the
  opening stays: the opening's skip moment varies, and the anchors are
  chained from tsedit anyway.
- The bench's Proton `run_game.sh` writes `d3d11_dump` frames to a
  `/dev/shm` directory while the game runs (when 4 GiB are free) and
  moves them into `bench-logs/<stamp>/frames/` when it ends (xboxrecomp-cli).

Unchanged: pixel limits, references, dump slack and the other scenarios.

## Follow-ups
- Make the D3D11 dumper write off the present path (a renderer task,
  the tracker item), so dumps cannot stall a run on any disk.
