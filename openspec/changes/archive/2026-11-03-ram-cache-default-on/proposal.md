## Why

The user, 2026-10-30: "For the most part, seems like all games use
the HDD cache space for quick asset access. Can we also make the RAM HDD cache
ON by default?"

`storage.ram_cache` (change `ram-cache-partition`) keeps the title's
cache partition (`Z:`, `Partition3`-`5`) in memory: capped at the stock
750 MB, seeded read-only from `<hdd>/Cache`, never written back. Today only
BLiNX 1 turns it on, in its `packaging/config.default.toml`, because it
rewrites a 570 MB ring of cache files at about 7 GB of host writes an hour.
The other titles also stream assets through the cache partition. Saves
live on `E:`, not there. The cost is that a cache a title builds is not
kept between sessions (the console keeps it until the dashboard reuses the
slot), so each session rebuilds it; the design measures what that costs at
boot.

This is an exception to the workspace rule that opt-in features default OFF
and never change stock behaviour (CLAUDE.md, "Opt-in features"), granted by
the user on 2026-10-30. The precedents are the in-game menu (2026-10-27),
BLiNX 1's own RAM cache default (2026-10-28) and the DSP JIT (
2026-10-30). The title sees the same files and the same FATX behaviour; only
where the bytes live changes.

## What changes

- **Toolkit default ON.** `enhance_cfg_bool("storage.ram_cache", 1)`, and
  without the enhance layer the kernel reads `RECOMP_STORAGE_RAM_CACHE` as on
  when it is unset or empty. A build or a run without the packaged config
  behaves like one with it.
- **The opt-outs still win:** `ram_cache = false` in `config/config.toml`,
  and `RECOMP_STORAGE_RAM_CACHE=0` (or `false`, `no`, `off`) over any file.
- **The `[MEM] exit` line** gains `ramcache_mib` and `ramcache_peak_mib`
  when the store was used, so a bench or smoke log shows what it cost.
- **Every game's `packaging/config.default.toml`** gets the `[storage]`
  block BLiNX 1 has, with `ram_cache = true` and its own comment: BLiNX 2,
  JSRF, SSX 3, Burnout 3, KUF, and Spartan (parked; only its build-all check
  runs). BLiNX 1 keeps its block; its env doc drops the "config default
  instead of a game-defaults row" note to say the toolkit default is now on.
- **New games:** the CLI's new-game template carries the same block, and
  its `config_defaults` test expects `storage.ram_cache = true`.
- Each game's CHANGELOG and docs say so; the toolkit's CHANGELOG too.

## Out of scope

- The 750 MB cap and the seeding behaviour.
- A menu item for the key (the menu shows it only if a page already does).
