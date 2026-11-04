## Why

The Godot extract shows a stage's static trees and, since the collision spike, its collision. What the game spawns into a stage at load is missing: enemies, items, props, doors, blocks and effect emitters. (Time crystals are dropped at run time, not placed.) Without them a stage in Godot is an empty shell, and the port work that moves BLiNX 1 enemies and maps into BLiNX 2 has nothing to compare against.

The spike finds where BLiNX 2 keeps its per-stage placements, what each record points at, which models are skinned, and prototypes an opt-in export of one stage (M21).

## What Changes

- **Findings** (`design.md`):
  - the six per-stage placement tables, their record layouts and loaders;
  - the layer rule, which loads more than one table entry for a stage;
  - the model each class is drawn with, where it is known;
  - skinned and rigid models, and what a skinned export needs;
  - the frame the placements live in.
- **CLI, opt-in `xbr extract --placements`**: for each `[[extract.stage]]` with a `placements` index, writes:
  - `stages/<name>/<name>_placements.gltf`, with one top node per set and one named node per record (position, rotation and glTF `extras` with class, variant, flags and model VAs);
  - the record's rigid model where `[[extract.placement_model]]` names one, and an unlit marker box otherwise (skinned models, unknown classes, emitters);
  - `placements.json`, which holds every record with its raw bytes, the counts per set, and the classes with no model.

  The stage scene instances the placements as a `placements` node. Without the flag the output is byte-for-byte what it was. The glTF is engine-neutral; Godot only views it.
- **Manifest**:
  - `[extract] placement_world`;
  - `[[extract.placement_set]]`: set name, table, stride, layers, field offsets (`pos_at` and `rot_at` required) and marker size and colour;
  - `[[extract.placement_model]]`: a variant table (with an optional `variants` count) or a fixed object;
  - `[[extract.stage]] placements`: the stage's index.

  No game constant is in the CLI.
- **cat `game.toml`**: `placement_world = "-y"`, the six sets, the known models (enemy types 1–5 and 8, gimmick 0x52, ambient 0x01), and `placements = 5` on M21.

## Capabilities

### New Capabilities
- None (a spike; the option extends `engine-extract`).

### Modified Capabilities
- `engine-extract`: the opt-in placements layer and its manifest keys.

## Impact

- `xboxrecomp-cli`:
  - new `extract/placements.py`;
  - `extract/gltf.py` (`add_nodes`, `marker`), `extract/cli.py`, `extract/godot.py` (`scene()` composes the layers) and `manifest.py`;
  - `docs/manifest.md`, `docs/commands.md` and tests.
- cat: `game.toml` `[extract]` keys only. There is no runtime, recompilation or generated-code change, so no goldens are needed.
- The output stays local game data under the gitignored `dist/` or `--out`. Nothing is published.
