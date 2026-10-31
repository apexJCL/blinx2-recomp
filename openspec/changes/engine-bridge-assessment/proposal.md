## Why

On 2026-10-30 the user asked how feasible it is, given the state of the game repos, to move a game into a modern engine through a pipeline that remaps Xbox games into engine projects. The goals are better visuals, bugfixes and QoL, and modding and level editing. BLiNX 2 comes first, with BLiNX 1 alongside. A full port (rewriting the game logic in the engine) is not a pipeline: the logic is 11,686 register-level generated functions, mostly unnamed. What is feasible is to keep the recompiled game as the simulation and make the game repo plus the CLI the glue between the owner's dump, the running game and a locally generated engine project. The user asked to take the path of least resistance first, so pitfalls show early.

## What Changes

This is an assessment. It changes no behaviour and has no spec deltas (`skip_specs: true`).

- **`design.md`** holds:
  - the three meanings of "move to an engine" (host, scene lift, full port) and why the glue architecture combines the feasible two;
  - the three data paths: read (dump to engine assets), runtime (live scene from the recompiled game), write (editor edits back to guest-format overrides);
  - the engine comparison (Godot, Unreal, our own runtime with an engine as the GUI) against the player-builds-from-own-dump model;
  - the staged delivery: Godot as an editor beside our exe, then as an optional renderer, then as the host;
  - what BLiNX 1 and BLiNX 2 share, as far as checked;
  - the risks and the spikes, ordered by least resistance.
- **`tasks.md`** holds spikes S1 to S4 and the decision point after them. Each spike is a tracker sub-item. Spike code is throwaway, under `xbox-recomp/runs/engine-bridge/`, and lands in no repo.

## Capabilities

### New Capabilities
- None. Each stage becomes its own change with requirements once the spikes have answered its questions.

### Modified Capabilities
- None.

## Impact

- **Code, builds, goldens:** none. No render backend (CPU, D3D11, Metal), host or golden is affected by this change.
- **Toolkit:** none now. A later stage would add a game-agnostic capture and live-link service to the enhancements layer (fork-only, under `XBOXRECOMP_ENHANCE`, not meant for upstream), and the CLI would gain the extract and project-generation verbs.
- **Tools:** a Godot release pinned by sha256 under `xbox-recomp/toolchains/` (user space) for the spikes' headless import.
- **Legal:** every engine project is generated on the owner's machine from their own dump and is never published, the same model as the HUD and texture packs.
