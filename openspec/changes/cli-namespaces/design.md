## Context

`xbr` (CLI `d43db28`) has about 40 top-level commands, registered in
`main.py`. Four of them work on game data or game behaviour and share
nothing but the top level: `extract`, `enhance hud`, `hud-map` and `hooks`.
`extract` (engine-extract, the tracker item and later) writes glTF shaped for
Godot's importer and a Godot project around it.

Facts that constrain the design:
- The bootstrap runs the CLI from its own locked venv (`uv run --project
  <cli> --locked xbr`). A third-party package installed somewhere else is
  not visible there, so entry points cannot be the only way to add an
  engine.
- The manifest loader refuses unknown tables. A game that moves its tables
  before its `[cli]` pin moves breaks its own build.
- `[mods]` reaches the generation key through `pipeline.gen_inputs()`,
  which stores `hooks.mods_digest()` (a hash of the content: hook
  functions, used signatures, st0 lists) under the literal key
  `"game.toml [mods]"`. That key is in every game's
  `src/recomp/gen.key.json` (cat: line 13). The digest does not depend on
  the table name, but the key's label does, so renaming the label would
  stale `gen/` in every game.
- The manifest loader decides a table is present with `_has_table`, and
  `OPTIONAL` is keyed on the first part of a table's name. TOML creates a
  parent table implicitly for a dotted child (`[assets.hud]` makes
  `assets`), so nesting needs loader changes (section 2a).
- The wizard (Go) calls `enhance hud` by name. The label `"enhance hud"`
  appears in three places: `TIMING_HUD` (`package/plan.py`) and
  `TIMING_LABEL` (`enhance/hud.py`) for `build-logs/timings.json`, and
  `resources.hud_need()` (`Need("enhance hud", ...)`), which feeds the disk
  stages of `package --plan --json` that the wizard reads as
  `PlanDisk.Stages` (`runner.go`).
- `wizard font` reads `[enhance.hud] font`, and the manifest checks the
  wizard's `font_hint` against it.

## Goals / Non-Goals

**Goals**
- Two namespaces, `assets` and `mod`, with room to grow.
- Engine-neutral glTF, with engine-specific output behind a small adapter.
- `--engine godot` output identical to today's `extract`, except the three
  lines that name the verb (section 9).
- One release round where the old verbs and tables still work.

**Non-Goals**
- Texture packs, placements, characters and the write path. Only their
  names are reserved.
- Moving player, pipeline or maintainer commands.
- Any change to what the parser reads or to what the game runs. The one
  parser edit is moving the `SUPPORTED_ADD` report label into the profile
  (section 3).
- Rewriting `game.toml` for the user. The CLI never writes it.

## Decisions

### 1. Command map

Moves:

| Today | New | Notes |
|---|---|---|
| `extract` | `assets export` | `--engine godot` (default) or `none`; `--stage`, `--out`, `--collision` and `--placements` unchanged |
| `extract --import` | `assets export` then `assets check` | `check` runs the adapter's check on an existing out dir |
| `extract --list` | `assets list` | |
| `extract --scan SECTION` | `assets scan SECTION` | maintainer tool, kept |
| (none) | `assets open [STAGE]` | Godot: `godot --editor --path OUT`; `none`: prints the paths |
| `enhance hud` | `assets hud-pack` | all options unchanged, `--list` included |
| `hud-map` | `mod hud-map` | sub-verbs unchanged (`emit --check` and the rest) |
| `hooks` | `mod hooks` | still run by `analyze` and `all` under `begin_stage("hooks")`; that name is the stage-extras key in the gen key and does not change; the stage-command passthrough (extra arguments for the tool) is kept |
| (none) | `mod symbols [check \| show ADDR\|NAME] [--json]` | reads `[pipeline] symbols`, uses `symbols.load()` |
| (none) | `mod new NAME` | scaffolds `src/NAME_mod.c` and `src/NAME_mod.h` from a template |
| (none) | `mod list [--json] [--exe PATH]` | runs the built exe with `RECOMP_MODS_DESCRIBE=json` |

Reserved, not built here: `assets textures`, `assets characters`,
`assets import` (the write path). `assets` and `mod` print "not yet" for
them, so no third party takes the name. Placements export through
`assets export --placements` (the placements spike), not a verb of their
own; `assets placements` is reserved only for a later inspection verb
(listing a stage's records without exporting), should one be wanted.

Stays at the top level:

| Command | Why it stays |
|---|---|
| bare `xbr`, `xbr PATH`, `import`, `package`, `doctor`, `fingerprint`, `clean`, `setup` | player commands; the wizard and the READMEs call them |
| `analyze`, `recomp`, `all`, `build`, the stage verbs (`parse`, `disasm`, `funcid`, `abi`, `ghidra`, `names`, `recomp`) | the pipeline; each stage's `begin_stage` name is part of the gen key |
| `pins`, `public`, `new`, `workflow`, `wrapper` | maintainer tools, unrelated to modding |
| `wizard` (`wizard font` reads `[assets.hud]`) | builds the player wizard, not a mod tool |
| `bench`, `bench db` / `benchdb`, `golden`, `pacing-stats`, `bench-matrix`, `audio-check` | test and bench tools; scripts, notes and TASKS call them by name |
| `enhance` | left empty after `hud` moves; kept as a hidden alias group for one round, then removed |

`hooks` as a bare top-level verb becomes a hidden alias like the others.
Inside the pipeline it keeps the stage name `hooks`.

### 2. `game.toml` key map

Only tables move. Key names inside them do not change.

| Today | New | Notes |
|---|---|---|
| `[extract]` | `[assets]` | adds `engine = "godot"` (default; `none` or an adapter name) |
| `[[extract.stage]]` | `[[assets.stage]]` | |
| `[extract.stage.transform]` | `[assets.stage.transform]` | |
| `[[extract.stage]] placements` | `[[assets.stage]] placements` | key unchanged; the stage's index into the placement sets |
| `[extract] placement_world` | `[assets] placement_world` | key unchanged |
| `[[extract.placement_set]]` | `[[assets.placement_set]]` | read by `assets export --placements` |
| `[[extract.placement_model]]` | `[[assets.placement_model]]` | likewise |
| `[enhance.hud]` | `[assets.hud]` | the empty `[enhance]` goes |
| (none) | `[assets.engines.NAME]` | `module = "tools/engine_x.py"`, relative to the game root |
| `[mods]` | `[mod]` | `hook_functions`, `st0`, `no_st0` |
| `[mods.signatures]` | `[mod.signatures]` | |
| `[hud]` | `[mod.hud]` | `table`, `scenarios`, `mod` |
| `[pipeline] symbols` | unchanged | an `analyze` input; `mod symbols` reads it |

Two tables are both called `hud`: `[assets.hud]` is the redrawn texture
pack, `[mod.hud]` is the HUD layer table that `mod hud-map` checks. The
manifest doc says so next to each.

What does not move, because it is not a `game.toml` table or is consumed
outside the CLI:
- the pack output `dist/enhance/hud/` and the bundle field
  `enhance.hud_pack`;
- `package --hud-pack/--keep-hud-pack/--clear-hud-pack`;
- the package capability `enhance` and `golden.enhance_stock`;
- the player's `[mods]` table in `config.toml`, which the runtime reads.

The label `"game.toml [mods]"` in `gen_inputs()` stays verbatim, with a
comment saying it names the old table on purpose: changing it would
stale `gen/` in every game for no change in content. The
`config/hook_functions.json` field `"mods"` stays too.

The default out moves from `dist/extract` to `dist/assets` (the user,
2026-10-31), for `assets export` and the `extract` alias alike. A game
that sets `out` keeps its value. An old `dist/extract` is left alone;
`assets export` mentions it once so the owner can delete it. The pack
output `dist/enhance/hud/` does not move.

### 2a. How the loader nests tables

- `OPTIONAL` is keyed on the full dotted table name (`assets`,
  `assets.hud`, `mod.hud`, ...), not its first part.
- `[assets]` counts as present, and `textures` as required, only when it
  has keys of its own besides `hud` and `engines`. A game with only
  `[assets.hud]` (KUF) does not have an `[assets]` table. The same rule
  replaces the `"extract" in m` checks in `_derive` and
  `extract/cli.config()`, through one helper (`has_assets(m)`).
- `engines` is a map key of `[assets]` (kind `STRMAPS`, like
  `[mods.signatures]`), so `[assets.engines.NAME]` is not an unknown table
  to `walk()`.
- `[mod]` is filled with defaults as `[mods]` is today. `[mod.hud]` is
  optional on its own: no `[mod.hud]` means no HUD table, as no `[hud]`
  does today.
- The old tables are mapped before these checks run, so `[enhance.hud]`
  alone behaves like `[assets.hud]` alone.

### 3. Neutral glTF and the engine profile

Today's output, sorted:

| Part | Where | Neutral or Godot | After |
|---|---|---|---|
| geometry, transform, `UP_ROTATION`, backdrop box | `gltf.py` | neutral | writer |
| env-map UVs from model-space normals | `gltf.py` | neutral | writer |
| glass alpha (< 240), `texture_alpha` | `gltf.py`, `textures.py` | neutral | writer |
| `KHR_materials_unlit` | `gltf.py` | neutral (a glTF extension) | writer |
| `xbr_blend` extra on additive materials | `gltf.py` | neutral data, engine reads it | writer; each adapter decides how to apply it |
| one wrap per material (`_samplers_by_range`: an in-range axis takes the other's wrap) | `gltf.py` | Godot (its importer keeps one repeat flag, from wrapT) | `profile.wrap_per_axis = False` |
| clamped axis cut into the mesh (`_bake`, `_clip`, `_settle_bakes`, `CUT_SNAP`) | `gltf.py` | Godot | runs only when `wrap_per_axis` is False |
| mirrored repeat (already written as `MIRRORED_REPEAT`, 33648) | `gltf.py` | neutral; only the report counts it as approximated for Godot | writer; the count's label is wording |
| report labels naming Godot ("Godot keeps one wrap", "Godot repeats it", `SUPPORTED_ADD` "set by the Godot scene") | `gltf.py`, `ninja.py:78` | Godot wording | `profile.wording`; `ninja.py` reports a label key |
| collision node names `col_<rrggbb>-col` | `collision.py` | Godot importer hint | `profile.collision_suffix = "-col"` |
| `collision.json`, debug mesh alpha 0.35 | `collision.py` | neutral | writer |
| PNG textures from DDS | `textures.py` | neutral | writer |
| `report.json`, `report.txt` | `cli.py` | neutral shape, Godot wording | writer, wording from the profile |
| `.gitignore` (`*`) | `godot.py` | neutral | writer, for every engine |
| `project.godot`, `view.gd`, `stage.gd` (applies `xbr_blend`), `collision.gd`, `*.tscn` | `godot.py` | Godot | `engines/godot.py` `project()` |
| `--headless --import` and its log check | `godot.py` | Godot | `engines/godot.py` `check()` |
| Godot pin, sha256, `XBR_GODOT`, `third_party/godot-4.7.2` | `godot.py` | Godot | `engines/godot.py` |

`none` and `godot` differ only in three things:
1. the wrap choice and the cut: with `wrap_per_axis = True` each sampler
   keeps its per-axis wraps and no mesh is cut;
2. collision naming: no suffix; the collision nodes carry an
   `xbr_collision` extra with the class instead;
3. the report wording: neutral, and mirrored repeat counts as supported.

Mirrored repeat is `MIRRORED_REPEAT` for both, as today. The clamped-axis
cut stays Godot-only (the user, 2026-10-31).

### 4. Adapter interface

```python
@dataclass(frozen=True)
class Profile:
    wrap_per_axis: bool
    collision_suffix: str
    wording: Mapping[str, str]  # label key -> text for the reports


class Engine(Protocol):
    name: str
    api: int  # 1
    profile: Profile

    def project(self, ctx, out: Path, stages: list[Stage], collision: bool) -> None: ...
    def check(self, ctx, out: Path) -> list[str]: ...  # problems; empty = ok
    def open(self, ctx, out: Path, stage: str | None) -> int: ...
```

- `assets export` writes the neutral parts with the adapter's profile, then
  calls `project()`. `none.project()` writes nothing.
- `check()` for Godot is today's `--headless --import` run. For `none` it is
  a stdlib structural check of each `.gltf` (buffers, accessors, indices in
  range, images present).
- `none` refuses an out dir that already holds `project.godot`, so a stale
  Godot project is not left beside a neutral export. The message names
  the dir, says it holds a Godot export, and gives the command that clears
  it (`rm -r DIR`, with the dir filled in) and `--out DIR` for another
  dir. It deletes nothing itself. Godot keeps removing a
  stale `collision.gd` as today.
- `ctx` gives the game root, the `[assets]` table, the host and a logger.
  It is the only thing an adapter gets from the CLI; adapters do not import
  CLI internals. `api` lets the CLI refuse an adapter built for another
  interface.

### 5. Loading third-party adapters

Both routes (the user, 2026-10-31), in this order: built-ins (`godot`, `none`; reserved), then
`[assets.engines.NAME] module` in `game.toml`, then the `xbr.engines` entry
point group. The module must define `ENGINE`. A name found twice is an
error that names both sources.

- The module path is the primary route. It works with the bootstrap's
  locked venv, needs no packaging, and lives in the game repo next to the
  stages it serves.
- Entry points serve someone who installs `xbr` as a tool
  (`uv tool install xboxrecomp-cli --with xbr-engine-unity`), where the
  package is in the same environment. The bootstrap never sees them; the
  docs say so.

A module path in a third-party `game.toml` runs code, but so does the game
repo's own build, so it opens no new trust boundary.

### 6. The `mod` commands

- `mod hooks` and `mod hud-map`: moved as they are.
- `mod symbols check`: loads `[pipeline] symbols` and prints the
  problems. `symbols.load()` raises one combined `CliError`, so it gets a
  variant (`symbols.problems(path)`) that returns them as a list; `load()`
  calls it and raises as today. It prints the problems (reserved names, C keywords, `sub_`/`loc_` shapes,
  duplicates, unknown kinds). `show ADDR|NAME` prints the entry. `--json`
  for both. Exit 1 on problems.
- `mod new NAME`: writes `src/NAME_mod.c` and `src/NAME_mod.h` from a
  template shaped like `cat/src/hud_mod.c`: an `xbox_mod_desc` (title,
  summary, author, version), one menu setting, one rebindable control,
  `init`/`shutdown` stubs, the `XBOX_MOD_API_VERSION >= 5` guard, and
  `const struct xbox_mod *NAME_mod(void)`. The template holds nothing
  game-specific (no `hud_table.h`, no `CAT_*` guards; the header guard is
  `NAME_MOD_H`). It refuses an existing file and a NAME that is not a C
  identifier. It edits nothing else (the user, 2026-10-31) and prints:
  1. the `CMakeLists.txt` source line and the `#include "NAME_mod.h"` for
     `src/main.c`;
  2. the registration, `if (NAME_mod()) mods[nm++] = NAME_mod();`;
  3. a note to grow the fixed mods array first (cat's `mods[8]` is full,
     BLiNX 1's is `mods[2]`).
- `mod list`: runs the built exe (or `--exe PATH`) with
  `RECOMP_MODS_DESCRIBE=json` and `RECOMP_MODS_DESCRIBE_OUT` set to a temp
  file, under `SDL_AUDIODRIVER=dummy`. The toolkit writes every descriptor
  and resolved value and exits before the game starts, running no mod code.
  `--json` prints it as is; without it, a table. No exe found: it says to
  build first. Needing a build is accepted (the user, 2026-10-31).

### 7. Compatibility

- **Verbs:** `main()` rewrites `extract`, `enhance hud`, `hud-map` and a
  bare `hooks` to the new form before parsing and prints one line on
  stderr: `xbr: 'extract' is now 'assets export'`. `extract --import`
  becomes `assets export` followed by `assets check`; `--list` and
  `--scan` map to `assets list` and `assets scan`. Aliases are hidden from
  `--help` and `helptext.py`.
- **Tables:** the loader maps each old table to the new one, warns once per
  table, and errors when a game has both forms of the same table. Every
  reader (`hooks`, `hudmap/runs.py`, `wizard font`, the manifest checks)
  reads the new name only.
- **Labels:** the label becomes `"assets hud-pack"` at all three sites
  (`TIMING_LABEL`, `TIMING_HUD`, `resources.hud_need()`). Readers of
  `timings.json` accept both labels, and the wizard maps both in
  `PlanDisk.Stages` and the timings, so files from the older CLI still
  estimate.
- **Lifetime:** the aliases and old tables ship in the release round that
  adds the namespaces and go in the round after (the user, 2026-10-31).

### 8. Effect on the games

The tables move in the same commit as the game's `[cli]` pin.

| Game | Tables | Other edits |
|---|---|---|
| BLiNX 2 (`cat`) | `[mods]`, `[hud]`, `[enhance.hud]`, `[extract]` | `README.md` (`enhance hud`), `docs/packaging.md`, `docs/env.md`, `config/hud.toml` comment; four script tests read `["mods"]` from `game.toml` and move to `["mod"]`: `scripts/test_hud_table.py:65` (also `hud-map emit --check` to `mod hud-map emit --check`), `test_crystals.py:331`, `test_entities.py:1320`, `test_shop.py:871` |
| BLiNX 1 (`blinx`) | `[extract]` | the comment above it (`dist/extract/` to `dist/assets/`) |
| KUF | `[enhance.hud]` | `README.md` (`enhance hud`), the comment above the table |
| Burnout 3, SSX 3, Spartan, JSRF | none | pin only |
| Auto Modellista | no `game.toml` yet | uses the new tables when it gets one |

The pin moves land at a push round, so the check is
`GAMES=all sh notes/build-all.sh`.

CLI docs: `README.md`, `docs/commands.md`, `docs/manifest.md`,
`docs/bundle.md`, `docs/wizard.md`, `docs/symbols.md`, `CHANGELOG`,
`helptext.py`. A new `docs/engines.md` describes the adapter interface.

### 9. Tests

- **Godot identity, defined:** every file `assets export --engine godot`
  writes, relative to its out dir, is byte-identical to today's `extract`
  output except three lines, which say `xbr assets export` instead of
  `xbr extract`:
  1. the glTF `asset.generator` string (`gltf.py:88`), in every `.gltf`;
  2. the `Made by` comment in `project.godot` (`godot.py:103`);
  3. the comment line of `.gitignore` (`godot.py:259`).

  The test normalises those three lines and compares sha256s; any other
  difference fails. The `extract` alias gives the same files.
- **Fixtures** (synthetic, recorded from today's `extract` before the
  split): a wrap cut, the in-range wrap choice, a mirrored repeat, an
  additive material, `texture_alpha`, env-map UVs, collision on and off
  with a `collision_skip` class (no `-col`), a transform, a backdrop,
  `up = "-y"` and `textured_colour = "white"`.
- **On the owner's dump** (local, never published): `diff -r` of the old
  CLI's `extract` and the new `assets export` for every BLiNX 1 and 2
  stage, with only the three lines above differing. Run once before merge;
  nothing is committed.
- **`--engine none`:** no `project.godot`, `*.tscn`, `*.gd`, `.godot/` or
  `import.log`; `.gitignore` present; per-axis samplers; no cut vertices;
  no `-col` names; `assets check --engine none` passes. Refuses a dir with
  `project.godot`, and the message names the clearing command and
  `--out`.
- **Adapters:** a module path adapter loads; a duplicate name errors; a
  wrong `api` is refused; an entry point adapter loads (with a fake
  distribution).
- **Aliases:** each old verb gives the same result as the new one plus the
  stderr note; old tables load with a warning; both forms error.
- **Loader nesting:** a KUF-shaped manifest with only `[assets.hud]`, and
  one with only the old `[enhance.hud]`, both load with no
  `assets.textures: required` error and `has_assets(m)` false;
  `[assets.engines.NAME]` loads; a manifest without `[mod.hud]` has no HUD
  table.
- **Gen key:** for the same content under `[mods]` and under `[mod]`,
  `gen_inputs()` and `gen_key()` are equal and `gen_stale_reasons()` is
  `[]` against a key written with `[mods]`.
- **`mod`:** `symbols check` on good and bad files, with `--json` giving
  the list; `new` refuses an existing file and a bad name; `list` against
  a stub exe that writes a fixed JSON.
- **`mod new` compiles for real:** the test finds the toolkit through
  `XBOXRECOMP_DIR` and skips when it is unset. It compiles the generated
  `.c` with `XBOX_MOD_API_VERSION` at the toolkit's value and
  `RECOMP_ENV_HAVE_ENHANCE_KEYS` defined, so the guarded body is built,
  links a small driver, and checks that `NAME_mod()` exists and returns
  non-NULL.
- **Wizard:** `go test` for the label mapping.

No game data enters the tests; fixtures are synthetic, as in
`tests/test_extract.py` today.

## Risks / Trade-offs

- **Identity is fragile.** Splitting `gltf.py` can reorder dict keys
  or floats. Mitigation: record the sha256s first, split second, and keep
  the Godot path calling the same functions in the same order.
- **Two `hud` tables** may confuse readers. Mitigation: the doc notes, and
  the error for an unknown key in one names the other.
- **A pin that skips the alias round** (a game jumping two rounds) loses
  the old tables at once. The loader error names the new table, so the fix
  is mechanical.
- **`mod list` needs a build.** It reads the truth from the exe rather
  than parsing C, at the cost of a build first.

## Migration Plan

1. CLI: the split, the namespaces, the aliases, the docs, tests. Minor
   release.
2. Wizard: the new verb and both labels, built from the same checkout.
3. Each game: move its tables and the pin in one commit, at the next push
   round. BLiNX 2, BLiNX 1 and KUF have edits; the rest move the pin only.
4. The round after: remove the aliases and the old-table mapping.

Rollback: revert the game's pin commit; the old CLI reads the old tables.

## Decisions by the user (2026-10-31)

The user took the proposed picks:

| Question | Decision |
|---|---|
| Default output folder | `dist/assets` (section 2) |
| `none` wraps | the original per-axis and mirrored wraps; the cut is Godot-only (section 3) |
| `mod new` | prints the `CMakeLists.txt` and `src/main.c` lines, edits nothing (section 6) |
| `mod list` | reads the built exe; a build first is fine (section 6) |
| Adapter loading | both routes, the `game.toml` module path first (section 5) |
| Alias lifetime | one release round (section 7) |
