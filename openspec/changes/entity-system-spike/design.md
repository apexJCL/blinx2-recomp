# Design: entity-system spike

## What we have (2026-10-30)

- **Names:** `analysis/ghidra/ghidra_names.json`, 671 Ghidra entries, mostly library functions and switch labels. In gen: about 144 named functions; the remaining ~11,500 are `sub_XXXXXXXX`.
- **Documented game addresses:** about 360 across `openspec/changes/*`, `openspec/specs/*` and `analysis/research/`. Examples:
  - camera struct `[0x4B271C]` and its builders (`free-camera`);
  - the stage frame `sub_00064850`, its update `sub_000649B0`, the pause flag `0xAE73B4`, the world-stop flag `0xAF0EF4`, the event system `sub_000EEB40`, the stage end `sub_00062550`;
  - the Ninja model draw `sub_0003B8D0`, the bone palette `0xA001D0` (engine-bridge S4);
  - the stage map table `0x40D180` (engine-extract);
  - the HUD sprite queue (`hud-anchors`), the LOD table (`lod-scale`).
- **Tools:** Ghidra 12.2 headless with the toolkit's `tools/ghidra_naming` (export with `decompiled.json`); gen as a call graph; the mod layer (hooks, pokes, `on_frame`); the S4 live link, which logs every model draw with its matrix and model pointer.

## Part A: symbol map

- **File:** `config/symbols.toml` in the game repo, one table per entry:

  ```toml
  [[symbol]]
  addr = 0x0003B8D0
  name = "nj_draw_model"
  kind = "function"            # function | global | field
  note = "Ninja chunk model draw; current matrix in xmm4..7"
  source = "engine-bridge S4, the tracker item"
  ```

  Fields of a struct are `kind = "field"` with a `struct` name and offset. Names follow one scheme: a prefix by subsystem (`nj_` Ninja library, `cam_`, `stage_`, `ent_`, `hud_`, `evt_`, `tc_` time control), then what it does.
- **Backfill:** harvest the ~360 addresses from specs and research, with a source line each; drop any that a spec later corrected.
- **Use, later change:** the names stage merges `symbols.toml` over Ghidra's names into `functions.json`, so gen and the Ghidra project both show them; a Ghidra script imports the map as labels and plate comments. The symbol map wins over Ghidra on conflict.
- **Rule from then on:** every spike, fix or feature that learns what an address does adds it to the map in the same branch.

## Part B: entity questions (BLiNX 2)

| # | question | leads in |
|---|---|---|
| E1 | Where is the live entity list, and what are spawn, update, draw and free? | the stage update `sub_000649B0` (what runs under the world-stop flag); callers of the model draw `sub_0003B8D0`; S4's per-draw model pointers grouped per object |
| E2 | What is the entity struct: position, rotation, model or node, type id, state or behaviour pointer, health? | a memory watch on one enemy's position while it moves; the struct S4's draws come from |
| E3 | Is there a type table (behaviour function, model, stats per enemy type)? | indirect calls through a table indexed by a small integer in the update loop |
| E4 | Where do placements come from? | the stage map table `0x40D180` rows and the `M*`/`G*` sections next to the geometry; spawns at stage start |
| E5 | What does time control record per entity? | the record buffers (rewind, fast-forward, pause) list exactly the state the game needs to restore an entity |
| E6 | Weapons and items: how are the vacuum and the time controls typed, and where are shop items and prices? | the shop screen's text, the item counters on the HUD |

**Method:** static (Ghidra decompiles, gen call graph) against dynamic (Mac Metal runs with `SDL_AUDIODRIVER=dummy`, scratch mods logging candidate structs per frame, memory watches through guarded reads). Each answer is checked live, never only in the listing.

**Proof:** a throwaway mod that, in stage 1:
1. lists the live entities each frame (type, position, health) next to the game frame;
2. spawns one extra copy of an existing enemy at a chosen point: it moves, attacks, can be killed, and survives a rewind;
3. changes one enemy type's health or speed.

**BLiNX 1:** after E1-E4, check whether BLiNX 1 uses the same entity scheme (it is game code, not the shared Ninja library, so it may differ).

## Output

- Part A (`config/symbols.toml`, its test `scripts/test_symbols.py` and the Ghidra import `scripts/ghidra/ImportSymbolMap.java`) merges to main now as data only (orchestrator, the tracker item review). Wiring the names into analyze or gen stays the later names change. Every entity address Part B finds is added to the map on its own branch.
- Findings on the tracker items and in this design; a recommendation for the follow-up changes: names in gen, and an entity mod API (spawn, list, type override) in the mod layer.

## Effort

| part | estimate |
|---|---|
| A: symbol map format and backfill | 1-2 agent-days |
| B: E1-E4 and the list and spawn proof | 4-6 agent-days |
| B: E5-E6 and BLiNX 1 comparison | 2-3 agent-days |

A and B can run in parallel; B adds to the map as it goes.

## Risks

- **Spawning outside the stage start** may break invariants the game keeps (time-control buffers sized at load, collision lists, enemy counts the stage end checks). E5 exists for this. If a mid-stage spawn breaks them, the proof falls back to adding a placement before stage load.
- **Behaviour is code.** A new enemy type with new behaviour needs C written against the found structs, as a mod; the spike only proves that copies and stat changes work.
- **Names drift.** A wrong name is worse than `sub_`; every entry needs a source, and a name changes only with a new source.
