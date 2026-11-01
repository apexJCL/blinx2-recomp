## ADDED Requirements

### Requirement: The assets namespace
`xbr assets` SHALL group the commands that read game data out of the owner's dump: `export [--engine NAME] [--stage NAME]... [--out DIR] [--collision] [--placements]`, `check [--engine NAME] [--out DIR]`, `open [STAGE] [--engine NAME]`, `list`, `scan SECTION` and `hud-pack` (the HUD pack command, as the `hud-pack` spec describes). They SHALL read the `game.toml` table `[assets]` (stages in `[[assets.stage]]`, the pack in `[assets.hud]`). The default output folder SHALL be `dist/assets`, unless `[assets] out` sets one. The names `textures`, `placements`, `characters` and `import` SHALL be reserved: each prints that it is not available yet and exits non-zero.

#### Scenario: Export with the default engine
- **WHEN** `blinx1 assets export --stage map11` runs on the owner's dump with no `engine` key
- **THEN** `dist/assets/` holds the stage's glTF, textures, report and the Godot project, as `extract` wrote them

#### Scenario: Reserved name
- **WHEN** a user runs `xbr assets placements`
- **THEN** the command says it is not available yet and writes nothing

### Requirement: Engine adapters
`assets export` SHALL write the engine-neutral parts (glTF, textures, `collision.json`, `report.json`, `report.txt`, `.gitignore`) shaped by the adapter's profile, then call the adapter's `project`. `assets check` SHALL call the adapter's `check` and fail when it returns problems; `assets open` SHALL call its `open`. The engine SHALL come from `--engine`, else `[assets] engine`, else `godot`. The built-in adapters are `godot` and `none`. Other adapters SHALL load from `[assets.engines.NAME] module` (a Python file relative to the game root that defines `ENGINE`), then from the `xbr.engines` entry point group. A name found in two sources, or an adapter whose `api` differs from the CLI's, SHALL be refused with a message naming the sources or the versions.

#### Scenario: Godot output unchanged
- **WHEN** `assets export --engine godot` and the previous CLI's `extract` run on the same stages
- **THEN** every file is byte-identical except three lines that name the verb: the glTF `asset.generator`, the `Made by` comment of `project.godot` and the comment of `.gitignore`

#### Scenario: Plain glTF
- **WHEN** `assets export --engine none` runs
- **THEN** no `project.godot`, `*.tscn`, `*.gd`, `.godot/` or `import.log` is written, each sampler keeps its per-axis wraps, no mesh is cut, collision nodes carry an `xbr_collision` extra and no `-col` suffix, and `assets check --engine none` passes

#### Scenario: Godot export in the way
- **WHEN** `assets export --engine none` targets a folder holding `project.godot`
- **THEN** it refuses, deletes nothing, and gives the `rm -r` command for the folder and the `--out` option

#### Scenario: Adapter from the game repo
- **WHEN** `game.toml` has `[assets.engines.mine] module = "tools/engine_mine.py"` and the user runs `assets export --engine mine`
- **THEN** the module's `ENGINE` writes its project after the neutral parts

### Requirement: Old extract verb and tables for one round
For one release round after the namespaces ship, `xbr extract` (with `--import`, `--list` and `--scan`), `xbr enhance hud`, `xbr hud-map` and the bare `xbr hooks` SHALL run their new forms and print one line on stderr naming the new form; they SHALL not appear in `--help`. The tables `[extract]`, `[enhance.hud]`, `[mods]` and `[hud]` SHALL load as `[assets]`, `[assets.hud]`, `[mod]` and `[mod.hud]` with one warning each, and a manifest holding both forms of one table SHALL be refused. A manifest whose only `assets` content is `[assets.hud]` (or the old `[enhance.hud]`) SHALL not count as having an `[assets]` table. The generation key SHALL keep its `"game.toml [mods]"` input label, so moving the table does not stale `gen/`.

#### Scenario: Old verb
- **WHEN** a user runs `xbr extract --import`
- **THEN** it runs `assets export` then `assets check` and prints `xbr: 'extract' is now 'assets export'` on stderr

#### Scenario: HUD pack only
- **WHEN** a manifest has `[enhance.hud]` and no `[extract]`, as KUF's does
- **THEN** it loads with a warning, with no `assets.textures: required` error

#### Scenario: gen/ stays fresh
- **WHEN** a game moves the same content from `[mods]` to `[mod]`
- **THEN** `gen_stale_reasons()` is empty
