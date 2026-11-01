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

## Findings, part B (2026-10-30)

Static reads come from Ghidra decompiles and gen. Live checks come from the throwaway mod `src/ent_spike.c` on this branch: headless Metal, `@stage1`. The runs are `runs/entity-spike/live-1` (the list) and `live-2` (the proof). New names are in `runs/entity-spike/symbols-new.toml` (67 entries) for the tracker item's map; this branch leaves `config/symbols.toml` alone.

### E1: the live list and life cycle (answered, live)

The enemies live on one list at `0xAF0E88`:
- `+0` holds the head of a node chain. Each node is {prev, next, obj}.
- `+8` holds a pool of 0x2C1-byte slots (a used byte, then a 0x2C0 object), with 0xD-byte node slots after them.
- `+0x10` is the capacity and `+0x14` the live count. A spawn is refused once the count is above 0x21, so 34 enemies at most.
- `+0x18` holds 16 aggro slots.

| step | function |
|---|---|
| spawn | `sub_0004EE20(placement*)`, eax = the list. It allocates through `sub_00050D40` and `sub_00050D80`, copies pos and rot, runs a per-class init chosen by `class & 0xFF` (for class 1, `sub_00279D20`), and appends at the tail. Its return value is not the object. |
| update | `sub_0004E700`, run each frame from `stage_update` `sub_000649B0`; it calls each object's `+0x98` function |
| draw | `sub_0004E950` |
| remove | `sub_0004ED30` (esi = node), only when `+0x98` returns nonzero, or at teardown (`sub_000606F0`, `sub_00061D60`) |
| find / count / nth | `sub_0004EBE0` / `sub_0004EC10` / `sub_0004EBC0` |

**Dead enemies are not freed.** A kill takes the state through 0x80000001 → 0x80000003 → 0xA, and the enemy stays on the list in state 0xA, so a rewind can bring it back.

Items and projectiles use a separate pool at `0xB22E68`: 256 slots of 0x6C bytes.
- spawn: `sub_000794D0`, with 85+ callers
- free: `sub_00079D30`
- update: `sub_0007A0F0` and `sub_0007A460`

### E2: the enemy struct (answered, live)

The enemy object is 0x2C0 bytes:

| offset | field |
|---|---|
| +0 | class dword |
| +4 | state |
| +0x10 | placement* |
| +0x18 | flags |
| +0x28 / +0x2A | hp / max hp (shorts) |
| +0x2C | id |
| +0x48 | pos |
| +0x54 | previous pos |
| +0x6C | rot |
| +0x88 | class data |
| +0x98 | update fn |
| +0xA4 | dtor fn |
| +0xF0 | home pos |

The player is a separate struct at `0xCD2440` (0x30C per player). Its hp short is at +0x6C.

### E3: type data (answered, static, with a live poke)

There is no single type table. Types are spread across three places:
- a per-class function table at `0x3F5020 + class*0x18`, with classes 0x80 and up at `0x3F5218`;
- per-variant data at `0x4AFCD8`, where the hp short sits at +0xC of each variant;
- the init switch inside the spawn function.

Behaviour is code: the init switch and the per-object `+0x98` function.

### E4: placements (answered, live)

- `0x4921E8[stage index]` points to {count, records*}. Each record is 0x5C bytes: class at +0, pos at +4, rot at +0x14, then AI parameters, with a link id at +0x30.
- `sub_0004F970` runs `sub_0004F5C0`, which spawns the whole table in one frame. Stage 1 is table `0x4530F8`: 30 records at `0x452630`, of classes 0x101, 0x102, 0x105, 0x110, 0x210 and 0x310.

### Proof (passes in run live-2; no fallback needed)

| step | result | frame (flip) |
|---|---|---|
| list | every frame logs each enemy's id, class, hp, pos and state | all |
| stat change | the poke `0x4AFD04 = 3` before load makes all 15 class-0x101 enemies spawn at 3/3 instead of 1/1 | log |
| spawn | the mod copies placement 1 into a scratch record and calls `sub_0004EE20` from the pre hook of `sub_0004E700`. It gets id 55, the count goes 30 → 31, and the new enemy appears beside the player. | 1500 |
| moves, attacks | it moves through states 1 → 7 → 8 → 4. At f1508 the player's hp drops 30 → 20 with id 55 5 units away. | 1530 |
| rewind | REW (request 0x1000) replays id 55's path backwards for 300 frames, and it stays on the list | 1760, 1830 |
| kill | `sub_00050800(obj, …, 3)` takes hp to 0, and the enemy enters the death states | 2060 |

### E5: time control (answered, live)

The player's control is `sub_0008C530`; the enemies' version is `sub_0008C9A0`. Both write the request word `0xADE76C` from the control id, and set the timer `0xAEB818` to 0x12C:

| control | id | request |
|---|---|---|
| PAUSE | 2 | 0x100 |
| SLOW | 3 | 0x200 |
| FF | 4 | 0x400 |
| REW | 5 | 0x1000 |
| REC | 6 | 0x2000 |

- `0x800` comes from a stage effect (`sub_0008CB10`), and `-1` means no request.
- While a control runs, `0xAE46EC` holds it. The map's name for that address, `sys_game_mode`, needs reconciling.

**What gets recorded.** The record is region-based, not per-entity:
- `sub_001A9830(0, ptr, size, flag)` registers raw memory in a table at `0xDD9BB8` (0x266 entries of 0x14 bytes), and it has 100+ callers.
- Spawn registers class 0x110's whole object, and each class's init registers the rest.
- Snapshots page to `z:\blinx2_%03d.rec`.
- Playback runs `sub_001A9720` → `sub_001A9010` → `sub_001A8D80`.
- The player is not recorded.

### E6: weapons, items and the shop (answered, static)

The shop is `sub_00210660`, over a catalogue at `0x4AACE0`: 53 records of 0x14 bytes, {name msg ptr, ?, price, category, id}. The categories are:
- 0 HP+10
- 1 max HP
- 2 barrier
- 3 jetpack
- 4 tank repair
- 5 time controls (FF 200, SLOW 250, PAUSE 300, REW 400, REC 500)
- 6 space controls and items
- 7 weapons

**Weapons.** The TS vacuums are ids 6-14 and the guns ids 16-41, in one id space.

**Names and gold.**
- Names come from the message table `0x3FC8B0`: 5 languages, 20 bytes per message.
- Gold is at `[0x4B2718] + p*0x140 + 0x78`, drawn by `sub_00092370`.

### BLiNX 1: same scheme, different layout

| | BLiNX 2 | BLiNX 1 |
|---|---|---|
| enemy list | `0xAF0E88`, objects 0x2C0, limit 34 | `0x63FAC0` (header 0xB4), pool `0x3F5BE0` of 0x1B30 bytes = 40 slots, objects 0xA0, nodes 0xD |
| list code | `sub_00050D40` / `sub_00050D80` | init `sub_00075CC0`, node alloc `sub_00075EE0`, spawn `sub_00076060`, setup `sub_000761A0` (called from `sub_000A9FF0`) |
| placements | `0x4921E8[stage]` → {count, recs}, 0x5C records | `0x3807B8[stage]` → {count, recs}, 0x2C records (class, pos, scale, rot); loader `sub_00076150` |
| time record | `sub_001A9830`, 0x14 entries, `blinx2_%03d.rec` | `sub_000DDE60` (64 callers), table `0x4F4300` with 0x18 entries, `pelon%03d.rec` (`sub_000DDA30` / `sub_000DE050`); list and pool registered whole through `sub_000DD650` |

The design is the same: a pooled list fed by a per-stage placement table, rewound through registered memory regions. The structs differ, so an entity mod API needs per-game layouts behind one interface. BLiNX 1 was checked statically only.

### Recommendation

- **Names in gen:** fold `symbols-new.toml` into the map.
- **Entity mod API in the mod layer:**
  - `ent_list` (walk `0xAF0E88`);
  - `ent_spawn(placement)` (scratch record plus `sub_0004EE20` on the guest thread, inside the enemy update);
  - `ent_kill` (`sub_00050800`);
  - type overrides as pokes into `0x4AFCD8` before stage load.

  Mid-stage spawns are safe up to 34 enemies. A spawned enemy is rewound like a placed one.
- **Risks:**
  - The scratch placement reuses the last record of stage 10's table. A real API needs its own static record memory that stays live while the object does, since the object keeps a pointer to it at +0x10.
  - A spawn made during a rewind is untested.
  - The 34 cap is hard.

## Findings, part C: respawn, the cap and rewind (2026-10-30)

Static reads come from Ghidra decompiles (`runs/enemy-respawn/ghidra/dec/`). Live checks use `src/ent_spike.c` on branch `spike/enemy-respawn`: headless Metal, debug stage select into stage 5-1 (index 20), with new options `killall`, `near`, `edge`, `far` and `spawnb`. The runs are in `runs/enemy-respawn/r1-respawn` … `r6-rew-past`. New names are in `runs/enemy-respawn/symbols-new.toml` (22 entries).

### C1: respawn without a rewind (answered, live)

The user saw it on 5-1: a dead enemy comes back about 15 s after the kill, but only while the player is away from its spawn point. The two enemies by the start are records 0 and 1 of the table at `0x47E140` (records from `0x47D730`), both class 0x201, group 1, respawn mode 1.

**The path.** A dead enemy stays on the list in state 0xA (E1). Each frame:
1. the class's state-0xA handler `sub_0027D3F0` calls the gate `sub_00050470`;
2. the gate adds 1 to the short at obj+0xAC (gen `recomp_0002.c`, `loc_0005052F`) once its early exits pass;
3. when the gate passes, `sub_00279D20` (EAX = 0) resets **the same object** in place.

The object keeps its slot, id and placement pointer, and its position goes back to the placement's. The list count does not change. `sub_002243A0` is class 9's nest spawner and plays no part. The timer is on the dead object (+0xAC), not on the placement.

**The gate (`sub_00050470`)**. The mode is the top nibble of placement+0x54. When that nibble is 0, the gate takes the mode from the group table: `0xADB5C8[placement+0x30]`, and it needs the short at `0xADB5CC[group]` to be above 0. So nibble 0 means "the group's default", not mode 0 itself.

| mode | delay | zone | other |
|---|---|---|---|
| 0 | 300 frames (0x12C) | default sphere, radius 150.0 | |
| 1 | 450 frames (0x1C2) | placement+0x34, or a default sphere of radius 50.0 when that is 0 | waits while the players hold the enemy's crystal colour (`sub_00050380`, colour nibbles in the low 24 bits of +0x54) |
| ≥ 2 | never | | |

- The zone descriptor is {type, +4, +8 radius}. The default is built on the stack as {1, 0, radius}.
- `sub_0004FEE0` tests each active player (count `0xD23904`, chars at `0xCD2440 + i*0x30C`). It uses the player position char+0xEC with y − 2.5, against the **placement** position (+4) and rotation (+0x14). It does not use the home position at +0xF0.
- Zone type 1 is a sphere (`sub_00049970`: it divides dist² by (param_4² + d[+8]²)·k, with param_4 = 0 here, so in effect dist² against the radius d[+8] squared). Types 2 and 3 are `sub_00049B10` and `sub_00049C50`. Any other type blocks the respawn.
- Early exits before the increment: while `0xAE46EC` (REW) is not 0, while `0xB21CB4` is not 1, and while the crystal block holds. The counter does not advance in any of these.
- Past those exits, the counter is not capped. It keeps counting while a player blocks the zone, so the respawn fires on the first frame the zone is clear. This holds only for the zone block.
- The 5-1 radii are set per placement: record 0 is 92.0, record 1 is 125.0, and record 7 is 100.0. Record 7's +0x54 top nibble is 0, so its mode comes from its group's default; that mode was not read live.

**Live**

| run | player | result |
|---|---|---|
| r1 | stays at the start, 179 from record 0 | killed at play 300, state 0xA at play 340, alive at play 790: exactly 450 frames |
| r2 | held at (600, −40, −1165), 46 from both | the counter passes 450 and reaches 860 with no respawn; the player is moved back at play 1200, and both respawn at play 1202 |
| r3 | held at (530, −37.5, −1200): 100 from record 0, 81 from record 1 | record 0 respawns at 450 frames, record 1 waits until the player moves away |

### C2: pool and capacity (answered, static)

- The pool is fixed in .bss at `0xADE790`: 0x5F5C bytes, or 34 × (0x2C1-byte slot + 0xD-byte node). `0xAE46EC` sits directly after it.
- Nothing allocates per stage. The pool's caller is `sub_000606F0` (gen `recomp_0003.c:43192`). It passes only the pool and its size, with no cap, so a bigger pool raises the count by itself.

### C3: raising the cap (answered, static plus one live measurement; not proved live)

Raising the cap would take:
1. a larger pool in free guest memory, passed at the `sub_000606F0` call (the capacity follows from the size);
2. four inline limits patched:
   - the `0x21 < count` refusal in `sub_0004EE20`, which allocates the slot before the test, so a refused spawn leaks it;
   - class 9's `< 0x22` checks, at `00221270.c:47` (gen `recomp_0019.c:102127`) and in fragment `0022239B.c:14`;
   - the `< 0x22` loop at `00182C26.c:882`, the player push-back against class 0x310;
3. room in the time record.

The time record is the real limit. Its ring at `[0xDDD198]` holds 10 frames of 0x16B0C bytes. Each frame's budget is under 0x16801 bytes and at most 0x20 regions, and a region that does not fit is **silently dropped**. On 5-1 the steady value is 89,650 bytes in 9 regions (the same in all six runs) against a budget of 92,160. That leaves about 2.5 KB. If the record grows by 0x2CE per extra slot, that is fewer than 4 more slots before later regions stop being recorded and their state stops rewinding. The 0x2CE growth is an assumption: no run showed that the whole pool is recorded as one region. Raising the frame budget means patching the ring's frame size and the paging (`z:\blinx2_NNN.rec`, 929,792 bytes per page).

**Verdict:** a raised cap is not a cheap hook. It needs a pool move, four code patches and probably a time-record redesign. Keep 34 for the entity API. Mods can spawn into free slots (`count < 34`) and reuse dead slots through the respawn path.

### C4: rewind (answered, live)

**The five-position loop seen in `live-2` comes from the RAM cache, not the game.** `live-2` and `r4` ran with `storage.ram_cache` on. It seeded 747 MB from `~/.local/share/xboxrecomp/Cache`: 360 old `blinx2_*.rec` pages and BLiNX 1's `pelon*.rec` pages, against the 750 MB cap. The run logged:
- `blinx2_000.rec not grown: STATUS_DISK_FULL`;
- `could not read the seed for blinx2_026.rec; it starts empty`.

The game cannot page its record out, so REW replays the 10-frame ring over and over. With the same inputs, the A/B shows:
- **r4, cache on:** the spawned enemy repeats 5 positions with a period of about 10 frames during REW;
- **r5, `RECOMP_STORAGE_RAM_CACHE=0`:** it retraces one smooth path.

The `stop` option is a no-op: `stage_update` resets `0xADE76C` to −1 every frame, and REW ends through the counter `0xADE1C8` or the timer.

**Rewinding past a mod spawn (r6, cache off).**
- id 32 was spawned at play 402 and REW requested at play 422.
- At play 441, after 19 rewind frames, the list count went 29 → 28 and id 32 was gone.
- No `sub_0004ED30` call happened: the recorded list header and pool used-bytes were written back.
- A spawned enemy is therefore undone like any other state. `pre_remove` hooks do not see it, so an API that owns per-spawn memory (C5 risk) must also check liveness each frame.

**Spawning during a rewind (r6).** At play 462, inside REW, `sub_0004EE20` returned id 33 in the same slot, and the count read 29. The next rewind frame put the count back to 28 and the enemy never appeared. A spawn during REW is silently undone, with no leak. The entity API should refuse or defer spawns while `0xAE46EC` shows REW.

How long REW runs varies: about 68 frames from play 450 in r4 and r5, and the full 300-frame timer from play 420 in r6. The cause was not pinned.

### C5: the `0xADA9B0` registry and checkpoints (answered, static)

- The registry's dedupe plausibly never runs: the loader appears to always pass 1. Its argument was not fully traced.
- Placements load only at stage start:
  - `sub_0004F970` loads `0x4921E8[idx]`; idx % 5 == 3 uses idx − 2;
  - `sub_00160E70`, called only from `sub_000606F0`, loads the extra set (1P `0x4923C8`, 2P `0x4925A8`).
- The checkpoint snapshot (`0xADCA58` → `0xAE4780`, 0x5DC dwords) holds no enemy state, and a checkpoint reload does not re-run the loader. Dead enemies come back only through C1 or a rewind.

### Recommendation, part C

- **Entity API additions:**
  - `ent_respawn` settings per placement: mode, zone and radius;
  - a "dead" query (state 0xA plus counter +0xAC).

  Spawns need their own static placement record. They must be refused while REW runs, and the API must check each frame that spawned objects are still on the list.
- **The cap stays at 34** (C3).
- **Toolkit follow-up:** the RAM cache seeds stale game scratch pages (`*.rec`) up to its cap, and BLiNX 2 rewind then breaks.
