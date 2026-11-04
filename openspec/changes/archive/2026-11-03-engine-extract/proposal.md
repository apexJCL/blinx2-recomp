## Why

The engine-bridge assessment (`engine-bridge-assessment`) chose Godot, staged, with the owner's locally generated project as the glue. On 2026-10-30 the user gave the go on stage 1's first slice, 1a: turn each game's stages into a Godot project from the owner's own dump, BLiNX 1 first and BLiNX 2 in the same change. S1 showed both games use the same Sega Ninja chunk format with two struct differences; S2 took a BLiNX 1 stage (MAP11) to glTF and into a headless Godot import with no errors. Every later slice (the live link, live meshes, the write path) needs this parser and its asset keys.

## What Changes

- **New CLI verb `xbr extract`** (game repos run it as `blinx1 extract`, `blinx2 extract`): reads the dump's XBE sections and textures, parses Ninja chunk models into meshes, writes glTF 2.0 per stage plus textures, and generates a Godot project with one scene per stage. `--import` runs the pinned Godot headless to import it.
- **One game-agnostic Ninja chunk parser** in the CLI. The per-game differences (vertex-list header 16 or 8 bytes, texture-name entry 32 or 36 bytes, section names, stage roots, where textures come from) are data in each game's `game.toml` under a new `[extract]` table.
- **Godot pinned** like the other CLI toolchains (version, URL, sha256 per host), downloaded into user space on demand.
- **Scope:** static textured stages. Characters, motions, skinning, placements, collision, lighting and fog are out of scope (slices 1b and 1c, or later).

## Capabilities

### New Capabilities
- `engine-extract`: the extract verb, the `[extract]` table, the generated project layout, and what the output never contains or does.

### Modified Capabilities
- None.

## Impact

- **Render backends, hosts, goldens:** none. The verb runs offline and changes nothing the game executes; no golden, Proton or Windows run applies (workspace rule: tooling skips goldens).
- **Toolkit:** none.
- **CLI:** a new `extract` package and verb, a Godot pin, pytest cases on synthetic chunk data (no game bytes in tests), ruff. Game repos reach the verb at their next `[cli]` pin move; until then, `XBOXRECOMP_CLI_DIR`.
- **Game repos:** `[extract]` in `cat/game.toml` and `blinx/game.toml`; the output directory is gitignored.
- **Wizard:** unchanged in this change. Offering the project from the wizard (Godot in `wizard/pins.json`) is a follow-up.
- **Legal:** the project is generated on the owner's machine from their dump and never published. The verb never runs a Godot export (`.pck`); the output, including `.godot/imported`, stays under a gitignored directory.
