## Why

On 2026-10-30 the user asked whether the engine-bridge work makes it possible to create maps, fix bugs and add characters, weapons and enemies. Bugfixes already work through the mod layer. Reskins and map edits follow from the engine bridge's write path. Anything with new behaviour (a new enemy, a new weapon) needs the game's entity system: how an enemy is spawned, updated, drawn and freed, and where its type, stats and placements live. Nobody has mapped it. The user also noted that the constant reverse-engineering effort should already have produced named, documented functions; it has not. About 360 game addresses are documented, but they are scattered across specs and research notes, and the generated code names only about 144 functions, library ones from Ghidra.

## What Changes

An assessment with two parts. It changes no behaviour (`skip_specs: true`).

- **Symbol map (foundation).** A curated, per-game file of what we know: address, name, kind (function, global, struct field), one-line note and source (spec, commit, run). It is backfilled from the existing specs and research, fed to `analyze`'s names stage so the generated code and Ghidra show the names, and grown by every later spike and fix.
- **Entity spike (BLiNX 2).** Find the entity list and its life cycle, the entity struct, the type table and the stage placements, then prove it with a throwaway mod that spawns one extra enemy in stage 1 and changes one enemy's stats. BLiNX 1 is compared at the end.

## Capabilities

### New Capabilities
- None. The symbol map's format and the names-stage input become a change with requirements once the spike has used them.

### Modified Capabilities
- None.

## Impact

- **Code, builds, goldens:** none in this change. Spike mods are throwaway, in a worktree, never merged.
- **Later:** names in gen change only identifiers, but they still regenerate gen, so that change takes the goldens like any gen change. Hooks key on addresses and are unaffected.
- **Toolkit:** none. **CLI:** none now; a later change reads the symbol map in the names stage.
- **Legal:** names, offsets and notes are facts about the code, like the existing specs; no game bytes are committed.
