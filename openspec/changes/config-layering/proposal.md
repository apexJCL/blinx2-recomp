# Change: Configuration layering, `config.default.toml` + `config.toml`

## Why

The enhancements file is a template today. `blinx2 package` stages
`enhance.toml.default`; the launcher copies it to `config/enhance.toml` on
the first launch, refreshes `config/enhance.toml.default` on every launch
"for comparison", and points the runtime at the copy with
`RECOMP_ENHANCE_CONFIG`. The runtime reads the copy, never the `.default`.
Three things follow from that, each seen on a real bundle:

- a new key never reaches an existing install. `--hud-pack` turns
  `textures.pack` on in the staged `.default`, and `packaging.md` §6 tells
  the owner to copy the `[textures]` table into `config/enhance.toml` by
  hand after an upgrade (BLX-29 review, 8.1a). The glow keys are not in the
  player's file at all ("add them as an `[fx]` table yourself", README);
- the player's file is a full copy of every key, so nothing says which
  values they chose. The in-game menu (`enhance-menu-preview`, phase 3)
  needs a file it can write a single changed key into and delete a key
  from on Reset, without rewriting the comments the player reads;
- the file is named after one layer (`enhance.toml`) when it is about to
  hold the mod and menu keys as well (`[textures]`, `[menu]`, later the
  mods list).

The user settled the shape on 2026-10-11 (`enhance-menu-preview`
design P1 and "Decided" 4): a shipped **`config.default.toml`** that the
runtime *reads*, a user **`config.toml`** that holds **differences only**,
the **environment on top** ("an environment variable can and will
override whatever's on config.toml"), the rename **automatic with no
notice** (no user base yet), **enhancement and mod keys only** (no
`launch.env` host setting moves), the per-title file kept, a developer
tree reading `config/config.toml` in the repository, and the rename
landed as **its own change before the menu**, so Save (phase 3) is built
against `config.toml` from the first line. This is that change
(`enhance-menu-preview` tasks 2.1 and 2.2, tracker BLX-74).

## What changes

- **Toolkit** (`posix-host/portability`; upstream-neutral, the layer is
  still off by default): `enhance_cfg_init` reads
  `<exe dir>/config.default.toml` first, then the user's
  `config.toml` (`<root>/<title>/config.toml`, then
  `<root>/config/config.toml`, or the one file `RECOMP_CONFIG` names),
  with the environment on top as today. `RECOMP_CONFIG` replaces
  `RECOMP_ENHANCE_CONFIG`, which stays as the row's `LEGACY` name;
  `none` keeps its golden meaning (no file at all). An `enhance.toml`
  found where a `config.toml` is missing is renamed once, with one log
  line. A missing `config.toml` is created as a comment header when its
  directory exists. The layer exposes what differences-only Save needs
  (the parsed defaults file and the path Save writes); the comment
  preserving patcher itself stays in phase 3 (task 3.5). A relative
  `textures.pack` keeps resolving against the executable's directory,
  the root the defaults file is read from. `tests/enhance_cfg` gains
  the layering, migration and differences cases.
  `docs/runtime/enhance-config.md` becomes `docs/runtime/config.md` with
  the layering table.
- **CLI** (`xboxrecomp-cli`, `main`): `package` stages the game's
  `packaging/config.default.toml` beside the executable (top-level bundle
  file on Windows and SteamOS, `Contents/Resources` on macOS), refuses a
  game that still ships only `enhance.toml.default` with a line naming
  the rename, and `--hud-pack` appends the `[textures]` table to the
  staged `config.default.toml`, which now applies on an upgrade too. The
  SteamOS `launch.sh` and the Windows `launcher.c` stop copying the
  template, remove the stale `config/enhance.toml.default` they made,
  and set `RECOMP_CONFIG`. The bundle `README.txt`, `docs/manifest.md`,
  the help text and the test fixtures (`golden.json`, `bench_parity.json`)
  follow. A tagged release, so cat re-pins a tag.
- **Game** (`cat`, `main`): `packaging/enhance.toml.default` becomes
  `packaging/config.default.toml` (header rewritten: it is read, not
  copied; `[fx]` present, commented, beside `[textures]`); CMake puts a
  copy beside the built executable so a developer build has its
  defaults; `main.c` passes the working directory as the user root so a
  developer run reads the repository's `config/config.toml`
  (gitignored); the macOS launcher `packaging/macos/BLiNX2.in` does what
  the CLI's launchers do; `analysis/golden/golden.json` pins
  `RECOMP_CONFIG=none`; `docs/env.md` renames the row (count unchanged),
  `docs/packaging.md` §6 and the README `Options` section describe the
  layering, `scripts/test_launchers.py` follows the launcher.
- **b3** (Burnout 3): nothing here. BLX-75 wires the layer into b3 after
  this merge and consumes it as written: `packaging/config.default.toml`,
  `xbox_enhance_init` in its `main.c`, `RECOMP_CONFIG` in its macOS
  launcher, the CLI tag re-pinned. Until then b3 keeps packaging with its
  pinned CLI and is unaffected by the toolkit change (it does not call
  the layer).

## Backends, hosts and goldens

- No backend or presenter code changes; Metal and D3D11 read the same
  `nv2a_host_opts` the layer hands them. The CPU rasteriser is untouched.
- Goldens are unaffected by construction: the golden configuration pins
  `RECOMP_CONFIG=none` (the legacy `RECOMP_ENHANCE_CONFIG=none` still
  works and prints the table's one deprecation line), `none` reads
  neither file, and the per-key pins (`RECOMP_RENDER_SCALE=1`,
  `RECOMP_PRESENT_PACING=spin`, `RECOMP_GLOW=on`, ...) stay. The stock
  Metal goldens run on the branch with the new pin and once with the
  legacy one; `blinx2 bench golden` on D3D11 under Proton on "go".
- Hosts: macOS (the app's `Resources` layout), Windows under Proton (the
  installer upgrade path: an install over a bundle whose
  `config/enhance.toml` exists is renamed once and the `--hud-pack` key
  takes effect), the Deck for the SteamOS tar when the user asks.

## Legal

No game data moves. `config.default.toml` carries key names, stock
values and comments; a `--hud-pack` bundle's copy names the owner's pack
path, as `enhance.toml.default` did, inside the owner's private bundle.
The public repositories receive code, the template and documentation.

## Non-goals

- Moving any `launch.env` host setting (`RECOMP_PB_BACKEND`,
  `RECOMP_WINDOW_SCALE`, `RECOMP_PRESENT_VSYNC`, `RECOMP_HEADLESS`,
  `RECOMP_HOST_PAD`, `RECOMP_RUMBLE`, `RECOMP_KEYBOARD`) into the file:
  they are how the host runs the game, not changes to it (P1).
- The comment-preserving line patcher `recomp_cfg_patch` and Save
  itself: `enhance-menu-preview` task 3.5, built on what this change
  exposes.
- The menu, the overlay, any new key, `[input]` or the mods list.
- A compatibility window for `enhance.toml`: the rename is automatic and
  the next release reads `config.toml` only. `RECOMP_ENHANCE_CONFIG`
  survives as a legacy env name because the table gives that for free.
- Changing b3 in this change (BLX-75).
