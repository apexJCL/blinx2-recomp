## Why

Jet Set Radio Future hung on stage entry. A minidump of the hang shows
the DJ record at `0x0228E000` 0x28000 bytes inside a live heap block that holds
`se_pple.dat`: the word the title polls is that file's bytes at offset 0x28000.
The record was freed (or carved from a freed parent buffer) by a path the probe
did not watch, the heap handed the block to the sound bank load, and the title
kept reading through its stale pointer. Nothing overlapped; the reuse was
legitimate, the title's pointer was not.

The tracker item fixes the title path, and the tracker item is the fidelity work. A runtime
safety net that makes such a stale pointer read its old contents, instead of
whatever reused the block, lets a tester tell this class of hang from others
and keeps playing in the meantime.

## What changes

- New CONFIG key `RECOMP_HEAP_QUARANTINE=<KiB>` (toolkit `recomp_env` row,
  `docs/env.md` row). Off by default; 0 or empty is off.
- When on, `heap_free` puts the block in a bounded FIFO (1024 slots and the
  KiB limit) instead of freeing it. The oldest block goes back to the heap
  first. A block freed twice is held once. A request that would run out of
  heap drains the queue and retries before reporting exhaustion. A block
  larger than the limit is freed at once. 8192 KiB is the suggested value.
- A `memory_regressions_heap_quarantine` ctest.

## Out of scope

- Turning it on for any game. BLiNX 2 and JSRF ship with it off.
- Finding the unwatched free path (territory; the
  `RECOMP_TRACE=heap=0x0228E000` arm is staged for the next hang).
