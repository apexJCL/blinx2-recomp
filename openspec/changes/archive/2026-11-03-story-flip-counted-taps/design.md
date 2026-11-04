# Design

## Polls, not seconds
The pad script already counts polls (`wait polls N`, `tap B every Np`).
Metal run 20261026-135613 logs poll 1908 at flip 1908 in the menus, so
one poll is one flip there. A count in polls moves with the game's own
frame count: when present stalls, the taps wait for it. A seconds count
keeps running, so the taps land earlier in flips.

The holds are 476 polls (about 8 s at 60 polls a second) and 416 polls
(about 7 s), and taps come every 90 polls (1.5 s). These are the old
holds counted in flips. On Metal, run 20261026-135613 put the anchors
at slot-list 3269 and hub 3972, inside the old runs' spread.

## Dumps to tmpfs
Writing the BMPs to `/dev/shm` takes the disk out of present without
any runtime change. The files are moved, not copied, after the
survivor sweep and on any exit (an EXIT trap), so the pull and prune
steps still find them in `frames/`. If `/dev/shm` has less than 4 GiB
free, or is not there, the dumps go to `frames/` as before. A story run
dumps ~0.7-0.85 GB.

Rejected:
- A longer story time limit with a higher flip floor. The stall would
  still cost time and still vary per run.
- Making the bench stop once the last needed frame is dumped. That only
  helps after the stalls have already moved the taps.
- Wider dump windows. The task ruled these out unless the structural fix
  was too big.
