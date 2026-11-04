## Context

Change `ram-cache-partition` built the store and its key:
`RECOMP_STORAGE_RAM_CACHE`, a CONFIG row of the main `recomp_env` table, and
`storage.ram_cache` bound to it under the enhance layer. `xbox_enhance_init`
calls `xbox_RamCacheEnable` before the guest starts; without the layer the
kernel resolves the key itself at the first file call. Both defaulted OFF.

## Decisions

### D1. The default lives in the toolkit and in each game's file

The toolkit's fallback moves to ON, so every build path agrees: a packaged
game, a `<game> build` tree run from the repo, a bench run, a build without
the enhance layer. Each game's `config.default.toml` also says
`ram_cache = true`, because that file is the player's reference for every
key and the CLI's `doctor` compares it with the template.

The default is not a `RECOMP_ENV_GAME_DEFAULTS` row: a value from that table
counts as the environment and would beat `ram_cache = false` in
`config/config.toml` (BLiNX 1's `docs/env.md` records the same choice). So
the precedence stays: environment, then `config/config.toml`, then
`config.default.toml`, then the toolkit default.

### D2. Off words without the enhance layer

The kernel's own read used `recomp_env_on` (set, non-empty, not starting
with `0`), right for a default-off key. Default-on needs the reverse: on
when unset or empty, off for `0`, `false`, `no` or `off` (any case), the
same words `enhance_cfg_bool` takes, so a value means the same with and
without the layer. Any other value gets the layer's warning
(`... is not a bool ...; ignored`) and is ignored. The layer then falls back
to `config/config.toml` and `config.default.toml`; without the layer there is
no file, so the toolkit default (on) holds. A bad value with a file that says
`ram_cache = false` is therefore off with the layer and on without it; only a
build without the layer (a toolkit ctest) can see the difference.

### D3. The charge in the `[MEM] exit` line

`mem_stats_ramcache_note` takes the store's charge each time it changes
(two relaxed atomic stores, as the GPU notes). The line prints
`ramcache_mib` and `ramcache_peak_mib` after the GPU fields only when the
store was used, so a run with the store off prints the line it printed
before. The figure is the store's FATX charge: each entry's size rounded up
to 16 KB clusters, which is what the 750 MB cap counts. It is not the host
memory the store holds, and is no bound on it either way. It can be higher:
seed files are charged from the first file call, but their bytes are read
only when a file is first opened, so an unread seed costs nothing. It can be
lower: a file's buffer grows by half again, so an open file can hold up to
about half its size again in slack until its last close trims it. Use
`ram_mib` for the host's view.

### D4. Saves

The design's risk from the tracker item still holds: a title that keeps something it
needs on `Z:` loses it at exit. None of the six titles keeps saves there
(they go to `UDATA` on `E:`). The cache is not throwaway on the console:
the dashboard hands cache slots out least recently used, so a title
usually finds its own cache from the last session. With the store, every
session starts from the seed in `<hdd>/Cache` (empty on a fresh install),
so a title that builds a cache on first run rebuilds it each run; see the
load time below. Each game's smoke run checks
the cache is active and that the host's `hdd/Cache` gets no new writes. A
title that breaks gets `ram_cache = false` in its own `config.default.toml`
with the reason beside it, and a follow-up item.

### D5. Load time

BLiNX 2 is the title the `fatx_overwrite` comment describes: at boot it
copies `plcom_tex`/`tank_tex` `.ipk` texture packs to `Z:` when they are
missing, then reads them from there. With the store that copy runs every
session; with the cache on disk it runs once. Measured on the PC (native
Windows, D3D11, `golden --only attract`), to the attract golden's first-3d
anchor (the first flip with 1000 batches or more, the demo's stg0101 scene),
on toolkit b5027073:

| arm | first-3d (s) | stall into it (ms) | `Z:` creates before it |
|---|---|---|---|
| store, empty seed (x3) | 22.69, 23.39, 21.30 | 594, 625, 562 | 15 |
| store, warm seed | 23.89 | 563 | 1 |
| disk, cold | 19.94 | 735 | 15 |
| disk, warm (x3) | 25.09, 20.45, 24.89 | 687, 579, 703 | 1 |

The warm arms did skip the copy (1 create, not 15). The empty-seed store,
at 22.5 s mean, lands inside the warm disk spread (20.5-25.1 s, 23.5 s
mean), and the cold disk run, which made the same copies, was the fastest.
So the rebuild has no cost that shows above run-to-run noise. The PC was
busy during these runs (CPU load 96-100% from other build jobs; the
golden marked each arm INCONCLUSIVE for that), so read this as a few
seconds of noise each way, not as a precise figure.
