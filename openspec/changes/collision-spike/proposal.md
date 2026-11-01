## Why

The user recorded BLiNX 2 going through a wall: in a corner by a torch pillar, with a pot pressed against it, repeated wall jumps end with the player behind the wall, falling under the stage until the "Retry checkpoint?" screen. The same bug happens on original Xbox hardware (the user, 2026-10-31), so it is in the game's own collision data or code, not in the recompilation, the lifter, FPU precision or the runtime. A fix is a stock-game fix.

Nothing in the project described the game's collision. The spike finds the data and the code that tests the player, explains the bug with addresses, and shows the collision in the Godot extract so a stage's collision can be inspected beside its visuals.

## What Changes

- **Findings** (`design.md`): the collision data format, the load-time triangle bake and octree, the per-frame sphere query and push-out, the player's call sites, and the cause of the tunnelling.
- **CLI, opt-in `xbr extract --collision`**: for each `[[extract.stage]]` that names `collision` trees, writes `stages/<name>/<name>_col.gltf`. It holds one node per surface class, named `col_<rrggbb>-col`, so Godot's importer makes each a `StaticBody3D` with a concave shape. A see-through, unlit debug mesh in the class's colour is toggled with `C` (or the `show_meshes` property in the editor). It also writes `collision.json`, the triangles per class. Without the flag the output is byte-for-byte what it was.
- **Manifest**: `[[extract.stage]] collision` (a VA or a list of VAs) and `[extract] collision_skip` (classes the game never tests: drawn, but no shape).
- **cat `game.toml`**: the collision trees of all 20 stages that have them (M64 has none), and `collision_skip = [0xFFFFFF]`.
- **Follow-up, not in this change**: the stock fix in `src/fixes` (default on), shaped in `design.md`.

## Capabilities

### New Capabilities
- None (a spike; the extract option extends `engine-extract`).

### Modified Capabilities
- `engine-extract`: the opt-in collision layer and its two manifest keys.

## Impact

- `xboxrecomp-cli`: `extract/collision.py` (new), `extract/cli.py`, `extract/godot.py`, `manifest.py`, `docs/manifest.md`, `docs/commands.md`, tests. Game-agnostic: no BLiNX constant in the CLI.
- cat: `game.toml` `[extract]` keys only. No runtime, recompilation or generated-code change, so no goldens.
- Output stays local game data under the gitignored `dist/` or `--out`; nothing is published.
