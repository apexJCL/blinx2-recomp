# The RAM cache drops unseen seeds when an over-cap seed starves a write

## Why

`storage.ram_cache` (on by default since the tracker item) seeds the in-memory Z:
partition from `<hdd>/Cache`, up to the stock 750 MB cap. The dev default
`<hdd>` (`~/.local/share/xboxrecomp`) is shared by every game. In the tracker item
spike that Cache dir held 1 GB: 360 stale `blinx2_*.rec` pages and 300 BLiNX 1
`pelon*.rec` pages. The seed took 747 MB, then:

- `blinx2_000.rec` could not grow: `STATUS_DISK_FULL`;
- the seed for `blinx2_026.rec` could not be read in; it started empty.

BLiNX 2 could not page its time record out, so REW looped its 10-frame ring
(`runs/enemy-respawn/r4-rew-cache` against `r5-rew-nocache`). Any Cache dir
over the cap breaks rewind, and any title that writes its own cache files
there is starved the same way.

## What changes

- When the seed did not fit under the cap (a file or directory was left out),
  and growing a file or creating a directory would pass the cap, the store
  drops seeds the title has neither opened nor been shown this run (by a
  listing or a query). It drops the oldest write time first, until the
  request fits. The host copies stay.
- Seeds the title opened or saw, and files it made, are never dropped. If
  dropping every droppable seed would still not make room, nothing is dropped
  and the request gets `STATUS_DISK_FULL` as before.
- While dropping is possible, the free space answer counts the droppable
  seeds as free, so titles that check before writing see the room.
- A seeded directory past the cap is left out like a file, so the seed never
  charges more than the cap.
- A Cache dir that fit under the cap changes nothing: no seed is ever
  dropped, and the free space answer is the same. That Cache dir may be the
  title's own state, and dropping part of it would lose data silently.

## Out of scope

- A per-game `<hdd>` default. The toolkit default `xboxrecomp` dir also
  holds UDATA, TDATA and the partition images, so moving it changes where
  saves go; games choose their own `RECOMP_HDD_DIR` in installs already.
  Filed as a follow-up.
