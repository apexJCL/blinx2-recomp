# Design

## Where

`xboxrecomp:src/kernel/kernel_ramfs.c`: `make_room(extra, keep)`, called by
`set_size` (every write, `SetEndOfFile`, and the seed read-in on first open)
and by the directory create path, in place of the bare cap check.

## When dropping is allowed

Only when the seed scan itself overflowed the cap: `s_seed_overflow` is set
when `seed_file` or `seed_dir` leaves something out ("left out, past the
cap"), or if the charge after the scan is past the cap. A Cache dir that fit
is a state a console could hold, so it may be the title's own data from an
earlier run. There a title may hold an index of its files, open the index,
and expect the data files it names. Dropping one of those mid-run would lose
it silently. The cap answering `STATUS_DISK_FULL` lets the title clean up
itself, as on the console. With the flag clear, `make_room` is the old cap
check.

## The rule

A node is droppable when all of these hold:

- it still carries an unread seed (`seed != NULL`; `seed_fill` clears it on
  the first open);
- the title was never told its name: `seen` is set on an
  `NtQueryFullAttributesFile` hit and on every `NtQueryDirectoryFile` entry
  returned;
- it has no handle on it;
- it is a file with a non-zero size.

`keep`, the file being grown, is never droppable.

1. If the request fits, return.
2. If the flag is clear, or the request does not fit even with every
   droppable seed gone, return "full" and drop nothing. A request that fails
   anyway should not cost the title its seeds.
3. Otherwise drop the droppable node with the oldest `mtime` until the request
   fits. Ties go to the first seeded, by node order. Each drop logs one
   `[FILE] ram cache: <name> (<bytes>), a seed the title has not opened or
   listed, dropped to make room` line.

Why unseen seeds only: the console's cache partitions are scratch (the
dashboard and other titles clear them), so a title cannot count on a file it
has not met this run. A file it opened or listed may be in its state (an
index, a list it opens from later), so dropping it could change what it
reads.

The limit of the `seen` rule: a title that lists its whole Cache dir at boot
marks every seed seen, and nothing is droppable again. BLiNX 2 does not. With
the rule, the 5-1 REW run with the 1 GB dev Cache dir still drops 119 seeds
and matches the cache-off path (67/67 REW frames). A title that does list
everything gets `STATUS_DISK_FULL` as before; the per-game `<hdd>` default
 is the fix for that case.

Why oldest first: stale pages from old sessions, and another game's files,
are the oldest; the current game's recent pages are the newest.

## Directories in the seed

A seeded directory is charged a cluster like any other node. `seed_dir` caps
it as `seed_file` caps files: a directory past the cap is left out together
with its contents, and the flag is set. So the seed never charges more than
the cap. A seed's first open (`seed_fill`) re-charges exactly what the seed
already held, so it never needs room and never drops another seed.

## Free space

`FileFsSizeInformation` reports `cap - (used - droppable)`. With the flag
clear the droppable charge is zero, so a Cache dir under the cap gets the
stock answer. With the flag set, a title that checks free space before it
writes sees the room that `make_room` would make.

## Not changed

- The host Cache dir is never written or deleted.
- With the flag clear (any Cache dir that fit), nothing is ever dropped and
  every answer is the same as before.

## Test

The over-cap tests are three ctest variants, each its own process:

- `kernel_ram_cache_over_cap_test`: a 65-cluster file that never fits (so
  the flag is set in any listing order), two subdirectories and seven seeds
  (62 clusters) against a 64-cluster cap.
  - A listed seed and a queried seed, both older than the rest, are never
    dropped. An opened seed stays, and its first open drops nothing.
  - Free space counts the 40 droppable clusters.
  - A write up to the cap drops nothing. One cluster past drops the oldest
    unseen seed, which is in a subdirectory.
  - On a tie in write time, the first seeded goes.
  - A request past every droppable seed fails and drops nothing.
  - The rest of the cap drops the remaining unseen seeds.
  - The host files are untouched.
- `kernel_ram_cache_under_cap_test`: a Cache dir that fits. Free space is
  the stock answer; a write and a directory past the cap get
  `STATUS_DISK_FULL`; no seed is dropped.
- `kernel_ram_cache_dir_over_cap_test`: a file of the whole cap and a
  seeded directory. Whichever is listed second is left out, the charge stays
  within the cap, and the flag lets a write drop the seed that fit.

The tests read seed state through `xbox_RamCacheSeedState`, which does not
mark a seed seen.
