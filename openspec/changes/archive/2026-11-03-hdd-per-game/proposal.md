# Each title gets its own default `<hdd>`

## Why

A game that does not set `RECOMP_HDD_DIR` gets the toolkit default `<hdd>`:
`$XDG_DATA_HOME/xboxrecomp` or `~/.local/share/xboxrecomp` (POSIX), and
`%LOCALAPPDATA%\xboxrecomp` (Windows). BLiNX 1, BLiNX 2, JSRF, SSX 3 and
Spartan all pass NULL to `xbox_path_init` when the key is unset, so their
dev runs share one disk: one `Cache/` (the utility-drive caches behind Z:,
X: and Y:), one `TitleCache/`, one set of partition images, one D3D11 shader
cache. On the Mac that `Cache/` held 1 GB of `blinx2_*.rec` and `pelon*.rec`
pages. The RAM cache seeds from it, and the tracker item now drops seeds it never
opened when a seed overflows. That stops the starved writes, but the seed
still reads another game's files, and with the cache off a game writes into
the shared dir.

Player builds do not use the default. The Windows launcher, the SteamOS
`launch.sh` and every macOS app script set `RECOMP_HDD_DIR` to `<data>/hdd`,
and Burnout 3 always passes its own save dir. So the change reaches dev runs
and an exe started by hand, which is where the sharing happens.

## What changes

- With no hdd dir from the game, the default root is
  `<base>/xboxrecomp/<title id>`: `<base>` as before, and the title id comes
  from the XBE certificate (8 lower-case hex digits, as in `UDATA/<tid>`).
  `xbox_MemoryLayoutInit` records the id, so no game needs a change.
- When the title id is not known yet (the path layer used before the XBE is
  loaded, or a zero id), the root stays the shared `<base>/xboxrecomp`.
- The first time a per-title root is used, this title's saves are copied
  from the shared root: `UDATA/<tid>` and `TDATA/<tid>`, each only when the
  per-title root has no copy of its own. The shared root is only read. It is
  never moved or deleted. A marker file in the new root records the copy, so
  it runs once, and the log names both paths.
- Caches, partition images and the shader cache start empty in the new
  root. They are scratch that the title and the runtime rebuild.
- An explicit `RECOMP_HDD_DIR` (or a game's own save dir) is unchanged, and
  `RECOMP_SAVE_DIR` still moves the saves. With either set, nothing is
  copied.

## Impact

- Toolkit: `kernel_path.c` (both backends), `xbox_memory_layout.c`,
  `kernel.h`, `src/kernel/README.md`, `tests/kernel_path`.
- cat: `docs/env.md` rows for `RECOMP_HDD_DIR`, and the env header
  description.
- No new env key. The shared root stays on disk with every game's old files
  in it; deleting it is left to the user.
