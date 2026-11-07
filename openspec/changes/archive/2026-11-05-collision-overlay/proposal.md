## Why

The collision spike (`openspec/changes/collision-spike`) found BLiNX 2's collision data and shows it in the Godot extract. Checking it there means leaving the game: walking the spot of a bug while seeing the faces that hold the player needs the collision drawn in the game itself, over the live frame. Mods also have no way to draw anything in the game's 3D space: the overlay draws 2D panels only. The tracker item adds a game-agnostic 3D debug draw to the toolkit's mod API and a BLiNX 2 mod that draws the collision around the player with it.

## What Changes

- **Toolkit, mod API version 8 (`draw3d`)**: a mod submits world-space triangles and lines with RGBA colours and the view and projection they are seen through. The D3D11 and Metal backends draw them at the flip into the presented frame, alpha-blended and depth-tested against the game's own depth buffer, or with no depth test (x-ray). Nothing is drawn, and nothing costs more than one load per flip, until a mod publishes. The CPU rasteriser keeps building and draws nothing (a TASKS.md gap). A new ctest covers the batching, the transform and the hand-off.
- **cat, `debug.collision` mod (`src/collision_mod.c`)**: reads the stage's baked triangles and octree at run time and draws the faces in cells within a radius of the player. It has the Godot view's toggles (faces, opaque or translucent, crease and open edges, flatness colouring), visibility per surface class, a rebindable toggle key, and the stretch goal: the player's collision sphere and the face that pushed it this frame. Default off; the goldens run `RECOMP_MENU=0` with it off.
- **cat glue**: the game's view builds (`sub_000292A0` for the game camera and `sub_0021B1F0`, in `recomp_manual.c`) hand the mod the view and projection they just built.

## Capabilities

### New Capabilities
- `mod-debug-draw`: the toolkit's 3D debug draw for mods. (No spec delta was written; archived 2026-11-05 without one, so the capability has no main spec yet.)

### Modified Capabilities
- None (the mod is a new opt-in mod).

## Impact

- Toolkit: `src/enhance/mod.h`, `mod.c`, new `src/kernel/nv2a_dbg_draw.{c,h}`, `src/d3d/nv2a_pb_d3d11.c`, `src/d3d/nv2a_pb_metal.m`, a ctest, `docs/runtime/` notes.
- cat: `src/collision_mod.c`, `src/main.c` (mods table), `src/recomp_manual.c`, the env rows and `docs/env.md`, `TASKS.md`.
- With the mod off the runtime is stock: goldens byte-unchanged on Metal and D3D11.
