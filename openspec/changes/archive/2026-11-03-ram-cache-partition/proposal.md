## Why

BLiNX 1 creates 300 cache files on its utility drive, `z:\pelonNNN.rec`
(1.9 MB each, about 570 MB in all). Z: links to
`\Device\Harddisk0\Partition5`, which the path layer maps to `hdd/Cache`.
While the player plays, the title rewrites these files in a ring, at about
one file per second. That is about 7 GB of host writes per hour on the
Deck's SSD. All three Deck crashes in the tracker item happened during these
rewrites.

The console treats its cache partitions (X:, Y: and Z:, 750 MB each on the
stock 8 GB drive) as scratch that a title cannot rely on keeping. The
dashboard and other titles clear them. A title therefore cannot depend on
the data surviving, and holding the partition in host memory is faithful
to the console.

## What changes

- A new toolkit module, `src/kernel/kernel_ramfs.{c,h}`. It is a
  memory-backed store for the cache partition. It serves create, open,
  read, write, seek, end of file, allocation, delete, rename, directory
  listing, and the file and volume queries.
- The public `xbox_Nt*File` functions in `kernel_file.c` become one
  dispatcher for both backends. When the key is on, a path or handle on
  the cache partition goes to the store. Everything else goes to the
  backend as before.
- A new config-tier key, `RECOMP_STORAGE_RAM_CACHE`, with the config file
  key `storage.ram_cache` (bool, default off). It is off by default, and
  with it off nothing changes.
- The store is capped at the stock partition size of 750 MB. A write
  or size change that would go past the cap fails with
  `STATUS_DISK_FULL`. This is what a full FATX partition does, so it is
  closer to the console than spilling to disk.
- When the store starts, it is seeded read-only from `hdd/Cache`. Titles
  that look for the last session's files still see them. The store never
  writes back to disk.

## Out of scope

- X: and Y: as separate volumes. Partitions 3, 4 and 5 already share
  `hdd/Cache` on disk, and they share one store too.
- The raw partition devices (`PartitionN.img`), which stay on disk.
- Formatting a utility drive does not clear the store. The path layer
  does not clear `hdd/Cache` either.
- BLiNX 1's `config.default.toml` sets the key to true after the review (the user's call): there the cache ring is about 7 GB of host writes an hour.
