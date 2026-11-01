## Why

The user wants `xbr` organised around modding and expanding the games
(2026-10-31). Today the commands that touch game data and game
behaviour sit side by side at the top level with the player's and the
pipeline's: `extract`, `enhance hud`, `hud-map` and `hooks`. Nothing groups
them, and more are coming: texture packs, placements, characters, a write
path back into the game, mod scaffolding and a mod list for a launcher.

`extract` is also tied to one engine. Its glTF carries Godot workarounds
(the clamped axis cut into the mesh, the wrap choice, the `-col` collision
names), and only Godot can open the result. The glTF should be the
neutral product, with engines as adapters on top.

## What Changes

- **New namespace `assets`**: game data out of the owner's dump, and later
  back in.
  - `assets export [--engine godot|none]`, `assets check`, `assets open`,
    `assets list` and `assets scan` replace `extract`, `extract --import`,
    `extract --list` and `extract --scan`.
  - `assets hud-pack` replaces `enhance hud`.
  - Names are reserved for texture packs, placements, characters and the
    write path. None of them is built here.
- **Engine adapters.** A small interface: `project`, `check`, `open`, plus
  a profile that says what the engine's glTF importer cannot read. Godot
  ships and is the default. `none` writes plain glTF only. Others plug in
  through a module path in `game.toml` or an `xbr.engines` entry point.
- **The glTF writer becomes engine-neutral.** The Godot workarounds run only
  when the adapter's profile asks for them. With `--engine godot` the output
  is identical to today's `extract`, except the three lines that name the
  verb (the glTF generator, the `project.godot` and `.gitignore` comments).
- **New namespace `mod`**: anything that changes the game's behaviour.
  - `mod hooks` (still a stage of `analyze`) and `mod hud-map` move here.
  - New: `mod symbols` (check and look up `config/symbols.toml`), `mod new
    NAME` (scaffold a mod with its descriptor, a rebindable control and a
    menu setting), `mod list` (the mods and their settings as JSON, for a
    future launcher).
- **`game.toml`.** `[extract]` becomes `[assets]`, `[enhance.hud]` becomes
  `[assets.hud]`, `[mods]` becomes `[mod]`, `[hud]` becomes `[mod.hud]`.
  Key names inside the tables do not change.
- **Default output folder** moves from `dist/extract` to `dist/assets`.
- **Compatibility.** For one release round the old verbs stay as hidden
  aliases and the old tables stay readable, each with a one-line note.
- **Decided by the user (2026-10-31):** the default output folder above;
  `none` writes the original per-axis and mirrored wraps, with the cut
  Godot-only; `mod new` prints the build lines and edits nothing; `mod list`
  reads the built exe; adapters load through both routes, the `game.toml`
  module path first; aliases and old tables live one release round.
- Every other command stays where it is (the map in `design.md` says why).

## Capabilities

### New Capabilities
- `cli-assets`: the `assets` namespace, the engine adapter interface and
  the neutral glTF output.
- `cli-mod`: the `mod` namespace.

### Modified Capabilities
- `hud-pack`: the verb is `assets hud-pack` and the table `[assets.hud]`.
- `packaging`: the player help lists `assets hud-pack`, and the HUD pack
  bundle requirement names it as the pack's source.

`engine-extract` is an unarchived change, not a main spec, so it gets no
delta here. Its extract requirement is updated when the first of the two
changes is archived (task 6.4).

## Impact

- **CLI:** `main.py` and `helptext.py`, the manifest loader, `extract/`
  split into a neutral writer and an `engines/` package, new `mod/`
  commands and templates, tests, and every doc that names the old verbs or
  tables. A minor release; the aliases go one round later.
- **Wizard:** it calls `assets hud-pack` and accepts both stage labels in
  `package --plan --json`. It is built from the same CLI checkout, so it
  moves with the pin.
- **Game repos:** only the four tables in BLiNX 2 (and four of its script
  tests that read `["mods"]`), the `[extract]` table in BLiNX 1 and
  `[enhance.hud]` in KUF move. Burnout 3, SSX 3, Spartan and JSRF have none
  of these tables and only move the pin; Auto Modellista uses the new
  tables when it gets a `game.toml`. The tables move in the same commit as
  the `[cli]` pin, since an older CLI refuses unknown tables, and the pins
  move at a push round (`GAMES=all sh notes/build-all.sh`).
- **gen/:** unchanged. The gen key keeps its `"game.toml [mods]"` label.
- **Render, runtime, toolkit, goldens:** none. Tooling only; per the
  workspace rules no golden or Proton run applies. `mod new` writes C from
  a template, but nothing the game runs changes until a porter builds it.
- **Legal:** unchanged. Every `assets` output is made from the owner's dump
  and stays under the game's gitignored `dist/`. No adapter may export a
  packed build (`.pck`, a Unity bundle) from game data.
