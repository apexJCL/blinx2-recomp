## Context

BLiNX 2 builds a stage from its static trees (the `[[extract.stage]]` tree lists) and then spawns what each per-stage list holds. The spike read the loaders in the recompiled code and the XBE data. It checked the result on M21 against the stage's collision floors and in Godot. All addresses are XBE VAs.

## Findings

### Where the placements are

`stage_current` (0xB87168) is the stage index; M21 is 5. Each set below is a table of pointers indexed by `stage + layer`. Each non-null entry points to `{u32 count, u32 records*}`.

| set | table | stride | layers | loader | draws |
|---|---|---|---|---|---|
| `enemy` | 0x4921E8 | 0x5C | 0 | `sub_4F970` → `4F5C0` → `4EE20` | the enemy's model (variant tables) |
| `item` | 0x491C18 | 0x28 | 0 | `783B0` → `794D0` | pickups (power-ups, ...; not time crystals) |
| `gimmick` | 0x491EE8 | 0x2C | 0, 1, 4 | `C1D20` from `606F0`; per-class init at 0x403A00[class] | props, blocks, doors, switches |
| `emitter` | 0x492788 | 0x28 | 0, 1, 4 | `322F0` → `327F0` | effect emitters, no model |
| `emitter2` | 0x492878 | 0x28 | 0, 1, 4 | same loader | same |
| `ambient` | 0x4922D8 | 0x30 | 0 | `E0760` | ambient creatures (the gull) |

**Layers:** some sets load more than one entry for a stage: `stage + 0`, `+1` and `+4`. These are the area's own list beside the stage's. The manifest's `layers` key lists them per set.

The rule depends on the stage and the mode. The table below is for Sweepers with one player, the mode the export assumes (`stage_team_mode` 0xB21CB4: 0 Sweepers, 1 Tom Tom, 3 VS; `menu_player_count` 0xB22E3C):

| set | at an area's first stage (`s % 5 == 0`) | other stages | loader |
|---|---|---|---|
| `gimmick` | `[s]`, `[s + 1]`, `[s + 4]` | `[s]` | `C1D20`; with `team_mode >= 2` or 0xB21C9C set it reads the per-area table 0x4921B8 `[s / 5]` instead (stage 50: 0x491FB0) |
| `emitter`, `emitter2` | `[s]`, `[s + 1]`, `[s + 4]` | `[s]`; M44 (18) in Sweepers: none | `322F0` (emitter2's `+4` at 0x492888) |
| `enemy` | `[s]` | `[s]`; the boss stages (`s % 5 == 3`) in Sweepers: `[s - 2]` | `4F970` |
| `item` | `[s]` | `[s]` | `98E30`: 0x491C18, or 0x491D08 with two players in Sweepers or Tom Tom |
| `ambient` | `[s]` | `[s]` | `E0760` |

`enemy[s]` is empty at every boss stage; the `[s - 2]` lists hold the boss classes (0x81 M14, 0x82 M24, 0x84 M44, 0x85 M54, 0x86 M64; M34's 0x83 comes from elsewhere, its `[11]` is null). The first stages' layers match the sets' `layers` keys, so those stages carry `placements` in `game.toml`. The other stages carry `placements` with a per-stage `placement_layers` (see *Per-stage layers* below).

**Resolved in the tracker item:** 0x491DF8 is the collectible set, spawned by `stage_item_setup` after the item set (see *Models and tables*).

### Record layout

Every set shares the head of the record:

| offset | field |
|---|---|
| +0x00 | class dword: low byte the class, byte 1 the variant, top byte flags |
| +0x04 | position, 3 × f32 |
| +0x10 | 1.0 (w) |
| +0x14 | rotation, 3 × f32 radians, X applied first (as Ninja objects turn) |
| +0x20 | 1.0 |
| +0x24.. | per-class fields (kept raw in `placements.json`) |

Spinning props store an accumulated angle, which can run many turns. The export folds it with `math.remainder`.

### M21 (stage 5)

| set | records | by layer | classes |
|---|---|---|---|
| `enemy` | 28 | 0: 28 | 0x108 ×6, 0x204 ×5, 0x205 ×4, 0x105 ×5, 0x310 ×2, 0x102 ×6 |
| `item` | 105 | 0: 105 | 0x1E ×34, 0x18 ×27, 0x23 ×20, 0x19 ×7, 0x16 ×7, 0x17 ×4, 0x1D ×3, 0x5C, 0x0C, 0x1C |
| `gimmick` | 119 | 0: 3, 1: 25, 4: 91 | 24 drawn (class 0x52, blocks); the rest are markers |
| `emitter` | 17 | 0: 7, 1: 8, 4: 2 | 0x34 |
| `emitter2` | 7 | 0: 7 | 0x39 |
| `ambient` | 42 | 0: 42 | 0x102 (class 0x02, no model known) |

An enemy class word is `type | variant << 8`. Type 0x08, variant 1 is written 0x108.

### Every stage

The stage index comes from the section switch in `sub_00169D10` (byte table 0x169F78, jump table 0x169F1C). Area `a` owns indexes `5a` to `5a + 4`; `5a + 1` and `5a + 4` load no section of their own (the `[s + 4]` layer is another sectionless index's list) and `5a + 3` is the boss stage. Each list was also matched against the stage's geometry by nearest vertex.

| stage | s | enemy | item | gimmick | emitter | emitter2 | ambient | drawn | markers (skinned) |
|---|---|---|---|---|---|---|---|---|---|
| M11 | 0 | 30 | 93 | 42 | 176 | 8 | 18 | 18 | 328 (21) |
| M13 | 2 | – | 22 | – | 51 | 13 | 16 | 16 | 86 |
| M14 | 3 | 1 | 107 | 30 | 77 | – | 16 | 16 | 215 |
| M21 | 5 | 28 | 105 | 119 | 17 | 7 | 42 | 24 | 268 (26) |
| M23 | 7 | 4 | 28 | 84 | 9 | 19 | 22 | 10 | 152 (4) |
| M24 | 8 | 28 | – | 22 | 31 | – | – | 0 | 81 |
| M31 | 10 | 16 | 94 | 77 | 16 | 11 | – | 0 | 214 |
| M33 | 12 | 16 | 46 | 65 | 10 | 7 | – | 1 | 134 (9) |
| M34 | 13 | – | – | 15 | – | – | – | 0 | 15 |
| M41 | 15 | 24 | 92 | 125 | 1 | 7 | – | 0 | 229 (20) |
| M43 | 17 | 21 | 41 | 55 | – | – | – | 0 | 108 (9) |
| M44 | 18 | 7 | 35 | 4 | – | – | – | 0 | 40 (6) |
| M51 | 20 | 28 | 102 | 113 | 209 | 2 | – | 0 | 441 (13) |
| M53 | 22 | 19 | 52 | 70 | 117 | – | – | 0 | 251 (7) |
| M54 | 23 | 4 | – | 43 | – | – | – | 0 | 47 |
| M61 | 25 | 32 | 3 | 31 | – | – | – | 0 | 66 |
| M64 | 28 | 28 | 25 | 37 | – | – | – | 0 | 63 (27) |
| M91 | 40 | – | 7 | 6 | 43 | – | – | 0 | 56 |
| M93 | 42 | – | 13 | 16 | 6 | – | – | 0 | 35 |
| M111 | 50 | – | – | 11 | – | – | – | 0 | 11 |
| M121 | 55 | – | – | 14 | – | – | – | 0 | 14 |

M63 (27) has no section. Every export imports into Godot with no errors, and no layer read failed. Before the tracker item the drawn props were the gulls (ambient 0x01) and class 0x52 gimmicks; the enemies with models are skinned.

The non-first stages were exported with the layers above set by hand, since the CLI has no per-stage list yet. Two lists do not sit on the exported geometry:
- M44's `[16]` and M64's `[26]` boss lists (median 120 and over 1000 from the nearest vertex). The boss arenas may be placed at runtime; M64 also has no collision trees in `game.toml`.
- M61's 31 enemies of class 0x0E are all at the origin, so the game must position them at runtime.

### Models and tables

**The two item tables.** `stage_item_setup` (`sub_000783B0`) picks the item set and then spawns the collectibles:
1. It loads 0x491C18[s], the item set the export already read.
2. When 0xB22E3C is 2 and the team mode 0xB21CB4 is 0 or 1, it loads 0x491D08[s] instead: the two-player item set (`sub_00098E30` reads the same pair).
3. Two other modes load 0x492968[(0xEC4CE8 or 0xEC4CE4) << 4].
4. Outside the hub drills (0xEC4CF8 set, or 0xEC4CE0 set with `stage_current` 0xB87168 == 0xB871AC: the same condition that selects 0x492968), it spawns every record of 0x491DF8[s] through `ent_item_spawn`.

Both loops filter records: outside M64 (0x1C) a record is skipped when team mode 0xB21CB4 >= 2 or 0xB21C9C != 0, so Sweepers is unaffected. On M14 in Sweepers the item loop (0x784C4–0x784F7) spawns only records whose class dword is 0x23: the export draws 106 items there and the game spawns 11. This is a gap of the export like those of task 4.11.

0x491DF8 is the **collectible** set: time stones (item types 0x2A–0x35, the six crystal colours twice), coins (0x36–0x41, `d_b2_coin1`–`3` in turn), medals (0x42–0x47, `h_medal_01a`–`06a`) and Tom Tom medals (0x48–0x4D, `h_b2_medal_01tom`–`06tom`). Its records are 0x28 bytes like the item set's, and it is now the `collectible` placement set. 0x491D08 is not exported, since the export assumes one player.

**Models.** The branch's `game.toml` has 168 `placement_model` rows, held for the release round: 83 gimmick, 40 item, 30 collectible, 14 enemy and 1 ambient. No CLI change was needed. The census of the all-stage export (`--collision --placements --import`, every stage imported with no errors):

| stage | records before → after (collectible) | drawn | skinned | markers |
|---|---|---|---|---|
| M11 | 367 → 410 (43) | 18 → 194 | 21 → 21 | 328 → 195 |
| M13 | 102 → 149 (47) | 16 → 85 | 0 → 0 | 86 → 64 |
| M14 | 231 → 282 (51) | 16 → 203 | 0 → 0 | 215 → 79 |
| M21 | 318 → 411 (93) | 24 → 309 | 26 → 26 | 268 → 76 |
| M23 | 166 → 228 (62) | 10 → 166 | 4 → 4 | 152 → 58 |
| M24 | 81 → 81 (0) | 0 → 21 | 0 → 24 | 81 → 36 |
| M31 | 214 → 308 (94) | 0 → 261 | 0 → 18 | 214 → 29 |
| M33 | 144 → 200 (56) | 1 → 163 | 9 → 9 | 134 → 28 |
| M34 | 15 → 15 (0) | 0 → 15 | 0 → 0 | 15 → 0 |
| M41 | 249 → 305 (56) | 0 → 245 | 20 → 36 | 229 → 24 |
| M43 | 117 → 273 (156) | 0 → 253 | 9 → 10 | 108 → 10 |
| M44 | 46 → 46 (0) | 0 → 37 | 6 → 7 | 40 → 2 |
| M51 | 454 → 515 (61) | 0 → 280 | 13 → 20 | 441 → 215 |
| M53 | 258 → 383 (125) | 0 → 250 | 7 → 9 | 251 → 124 |
| M54 | 47 → 47 (0) | 0 → 43 | 0 → 1 | 47 → 3 |
| M61 | 66 → 66 (0) | 0 → 34 | 0 → 31 | 66 → 1 |
| M64 | 90 → 100 (10) | 0 → 72 | 27 → 27 | 63 → 1 |
| M91 | 56 → 82 (26) | 0 → 39 | 0 → 0 | 56 → 43 |
| M93 | 35 → 92 (57) | 0 → 83 | 0 → 0 | 35 → 9 |
| M111 | 11 → 11 (0) | 0 → 11 | 0 → 0 | 11 → 0 |
| M121 | 14 → 14 (0) | 0 → 9 | 0 → 0 | 14 → 5 |
| **total** | 3081 → 4018 (937) | 85 → 2773 | 142 → 243 | 2854 → 1002 |

Drawn means a rigid model; skinned models stay markers until the tracker item. The new enemy rows and 18 item models are skinned, so the skinned count rises. The counts follow the review's item framing (`export-v2`). The 1002 markers left:

| set | markers | why |
|---|---|---|
| emitter, emitter2 | 837 | effects, no model by design |
| gimmick | 79 | classes 0x00, 0x04, 0x17 (gates), 0x26, 0x2E are controllers or pick their model from more than the variant; 0x3C and 0x70 are light sprites; 0x32, 0x44, 0x4F, 0x51, 0x59, 0x74 have no model found |
| ambient | 64 | class 0x02 light sprites |
| enemy | 22 | type 0x14 (11) and the boss types 0x81–0x86 (11), no model found |

### What each record points at

- **Enemies:** the type selects a pair of variant tables. Each table entry is 0x20 bytes, `{obj*, texlist*}` at +0 and +4, indexed by the variant. The flagged table is used when the top byte is non-zero.

  | type | table | flagged table |
  |---|---|---|
  | 1 | 0x4AFCD8 | 0x4AFD18 |
  | 2 | 0x4AED40 | 0x4AEDA0 |
  | 3 | 0x4AEE00 | 0x4AEE40 |
  | 4 | 0x4B0138 | 0x4B0178 |
  | 5 | 0x4AF3D0 | 0x4AF410 |
  | 8 | 0x4AEAF0 | — |
  | 6 | 0x4AFA48 | 0x4AFA88 |
  | 7 | 0x4AF808 | 0x4AF848 |
  | 9 | 0x4ACBB8 | — |
  | 0x0A | 0x4AF220 | — |
  | 0x0D | 0x4AE968 | — |
  | 0x0E | 0x4AF0EC | — |
  | 0x12 | 0x4AC968 | — |
  | 0x10 | fixed: obj 0x2BE0690, texlist 0x2BD4A68 | |

  Type 0x10 (init `sub_00276580`) shares type 1's state tables; unless its id is 0x310 it draws through `sub_00277CF0` with the fixed rigid `p_hod_asi01_cp` object. The loader remaps one index (`idx % 5 == 3` → `idx - 2`); `enemy = [-2]` on the six boss stages (M14, M24, M34, M44, M54, M64) covers it, and no other exported stage has `s % 5 == 3`.
- **Gimmicks:** each class has an init function in 0x403A00. 83 classes are resolved (see *Models and tables*): most index a per-class table by variant (`{obj, ?, texlist}` at stride 0x14, or stride 0x20), some use a fixed object and texlist. Class 0x13 is the big door (table 0x4050D8, stride 0x20).
- **Items:** the record's class byte is the item type, and the model entry is 0x400528 + type × 0x38: object at +0, texlist at +4, scale at +0x28, count at +0x2C, and the debris object and texlist at +0x30/+0x34. The item draw `sub_00086A80` builds the entry at 0x87156 and reads +0 and +4; `sub_0008F750` draws the debris piece from +0x30/+0x34. The rows set `variants = 1`, so a non-zero variant cannot read the next type's entry. Time crystals dropped by enemies (types 0x2A–0x2F) are not placed records, but the collectible set 0x491DF8 places time stones of the same type range.
- **Ambient:** class 0x01 (gull) uses obj 0x1BBF5C8 and texlist 0x1BBEFB0, fixed. Class 0x02 (`sub_002835A0`, draw `sub_002836E0`) is a `d_hikari_blue` light sprite with no model, so it stays a marker.
- **Emitters:** effects only, no model.
- **Shops:** no shop record was found in M21's lists. They are likely a stage-script object or a menu, not a placement.

### Skinned and rigid (for the tracker item)

| model | kind | evidence |
|---|---|---|
| every enemy read (types 1–5, 8) | weighted (skinned) | `VN_NF` vertex chunks, cached polygon lists (chunks 4/5) |
| `noct` 0x2BFC94C, `btama` 0x2BBAE70 | weighted | reader derails on unknown chunk types (ImageError) after reading NF chunks |
| gimmick 0x52 blocks (0x21C2F5C, 0x21C3AB4) | rigid | plain vertex chunks |
| gull 0x1BBF5C8 | rigid | plain vertex chunks |

A skinned export needs the following:
- the chunk types the reader does not know yet;
- the weighted vertices (`*_NF`: the vertex's offset, weight and node index), rebuilt into joint and weight attributes;
- the cached polygon lists, which are stored at one node and drawn at another, resolved per mesh;
- glTF skins built from the node tree.

Animation (motion files) is a separate step. Until then the export draws a skinned model's placement as a marker, and the node's extras give the model and texlist VAs.

### The placements' frame

BLiNX 2's manifest has `up = "y"`: the stage and collision glTFs are in the tree data's axes. The placement positions are not. They are the data turned a half turn about X, `(x, -y, -z)`.

With that turn the item positions sit on M21's collision floors: the median height above the nearest floor below is 0.0. Enemies sit a median 5 above the floor and gimmicks 2.5 above it, which looks like model origins above the feet (not checked). Without the turn the placements do not line up.

The Godot view confirms it: `runs/placements-spike/m21_placements.png`, kept local.

`[extract] placement_world = "-y"` says this:
- each set's top node carries the half turn, combined with the stage's own up turn (two half turns cancel);
- a model under a placement is authored in the data's axes, so with `-y` the placement node carries the half turn back, outside the record's rotation (`Rx(pi) · R`, below).

**Rotation.** The draws give the order and the signs. Class 0x52's draw (`sub_000C7360`) builds its matrix in xmm4–xmm7, one row per axis plus the translation, with row vectors (`v' = v M`):
1. `2D4CB0`: translate to the entity's position (+0x10);
2. `2D4E20(pi)`: the half turn about X;
3. `2D4DA0(+0x34)`, `2D4DE0(+0x30)`, `2D4E20(+0x2C)`: Z, then Y, then X, each pushed onto the matrix, so X is applied to the vertices first.

`2D4C20`, `2D4C50` and `2D4C80` rotate rows (X, Y), (X, Z) and (Y, Z): about Z, Y and X, right-handed with positive angles. The angle becomes an index into a 4096-entry sine table (0x3E7BD0) by `* 651.9` (4096 / 2pi, set by `sub_002D4E60`), so the record's angles are radians. Spawn (`C1B90`) copies the record's rotation to +0x2C unchanged. Most entity draws share the pattern. Of the 180 functions that apply the Z, Y, X turns, 161 push pi shortly before them (a scan of the generated code), the enemy draws `4C300` and `4C4A0` among them.

So the game draws `T(pos) · Rx(pi) · Rz(rz) · Ry(ry) · Rx(rx)` (column vectors). The order (X first) and the signs match the CLI's `ninja.quat`, but the half turn was not where the CLI put it:

| | transform | in data axes |
|---|---|---|
| game | `T · Rx(pi) · R(rx, ry, rz)` | `T · R(rx, -ry, -rz) · Rx(pi)` |
| CLI before the fix | `T · R(rx, ry, rz) · Rx(pi)` (the model node's turn) | same |

`Rx(pi)` negates Y and Z, so it flips the Y and Z angles it passes through. The old export mirrored every heading (the Y angle) and every Z tilt. No drawn prop showed it: every drawn placement has a zero rotation. The headings are on markers (boxes) and in `placements.json`, which keeps the record's raw angles. It shows once skinned enemies are drawn: 234 enemy records carry a Y angle, 132 of them with a model. The CLI now gives the placement node `Rx(pi) · R` and the model node no turn under `placement_world = "-y"` (xboxrecomp-cli `feat/placement-layers`), with a test that pins this order for non-zero angles on all three axes. This derivation reads the draw code itself, so a screenshot would add no evidence, and no drawn prop has a heading to compare.

## Decisions

- **Generic CLI, data in `game.toml`.** The CLI knows a placement set: a table, a stride, layers and field offsets. It reads one record shape: the class dword (byte 0 class, byte 1 variant, byte 3 flags, non-zero flags picking `table_flagged`) and f32 radians. `docs/manifest.md` says so; making the byte positions keys is a follow-up for the first game that differs (`tasks.md` 4.9). It also knows two ways to find a model: a variant table or a fixed object. Every address is in cat's `game.toml`.
- **One glTF beside the stage.** `<name>_placements.gltf` stays separate from `<name>.gltf` and the collision glTF:
  - the scene instances it as a `placements` node;
  - a viewer can hide it;
  - an engine importer can map the node names and extras to its own spawners.
- **Markers, not guesses.** A record with no known or rigid model gets an unlit box in its set's colour, sized per set. The record is never dropped.
- **Raw bytes are kept.** `placements.json` keeps each record's raw bytes. The per-class fields can be decoded later without another extract.
- **Opt-in.** With no `--placements`, or no `placements` key on the stage, the output is unchanged.

## Proposed `game.toml` shape

```toml
[extract]
# Placement positions are the tree data turned a half turn about X.
placement_world = "-y"

[[extract.stage]]
name = "M21"
# ... trees, collision ...
placements = 5           # the stage's index into every placement table

[[extract.placement_set]]
name = "enemy"           # set name: node names, extras, placement_model.set
table = 0x4921E8         # u32 per stage + layer -> {u32 count, u32 records*}
stride = 0x5C
layers = [0]             # default [0]
pos_at = 4               # required: the game's offsets
rot_at = 0x14
# class_at = 0 (default)
size = 6.0               # marker half-size; default 4.0
# colour = 0xE04040      # marker colour; default from a palette

[[extract.placement_set]]
name = "gimmick"
table = 0x491EE8
stride = 0x2C
layers = [0, 1, 4]
size = 8.0

[[extract.placement_model]]
set = "enemy"
class = 0x01             # the class byte (low byte of the class word)
table = 0x4AFCD8         # indexed by the variant byte
table_flagged = 0x4AFD18 # used when the flags byte is non-zero
stride = 0x20
# variants = N          # optional: the table's record count; past it, a marker
# object_at = 0, texlist_at = 4 (defaults)

[[extract.placement_model]]
set = "gimmick"
class = 0x52
table = 0x407278
stride = 0x14
texlist_at = 8

[[extract.placement_model]]
set = "ambient"
class = 0x01
object = 0x1BBF5C8       # a fixed model, no variants
texlist = 0x1BBEFB0
```

The manifest checks are as follows:
- set names are unique and do not end in a Godot import hint (`-col`, `_rigid`, ...);
- the stage index is 0 or more and `layers` lists each offset once;
- offsets fit in the stride;
- every model names a known set and a class byte, with no duplicate (set, class);
- a model has either a table or an object; an object needs a texlist and takes no `table_flagged` or `variants`; a table's `object_at` and `texlist_at` fit its stride; VAs are 0 or more;
- `stage.placements` needs at least one set.

## Per-stage layers

A set's `layers` hold for every stage unless the stage overrides them. The CLI (`feat/placement-layers`) adds that optional per-stage override, and `game.toml` uses it on the twelve stages that are not an area's first:

```toml
[[extract.stage]]
name = "M14"
placements = 3
placement_layers = {gimmick = [0], emitter = [0], emitter2 = [0], enemy = [-2]}

[[extract.stage]]
name = "M44"
placements = 18
placement_layers = {gimmick = [0], emitter = [], emitter2 = [], enemy = [-2]}
```

- Each key names a `[[extract.placement_set]]`; a set not named keeps its own `layers`.
- An offset may be negative as long as `placements + offset >= 0`; each offset appears once.
- `[]` means the set loads nothing on that stage.
- It needs `placements` on the same stage.
- `placements.json` and `--list` show the layers used.

The same CLI change moves the half turn (see *The placements' frame*): with `placement_world = "-y"`, the placement node gets `Rx(pi) · R` and the model node no turn.

## Risks and open points

- The half-turn fix is checked against the draw code and a unit test, not on screen: no drawn prop has a heading until skinned enemies are drawn.
- Gimmick classes 0x00, 0x04, 0x17, 0x26, 0x2E, 0x32, 0x44, 0x4F, 0x51, 0x59, 0x74, enemy types 0x14 and 0x81–0x86, and shops are unresolved.
- The export assumes Sweepers with one player. Tom Tom and VS swap the gimmick table and load M44's emitters; two players use the 0x491D08 items.
- M44's and M64's boss lists and M61's enemies do not sit on the exported geometry (see *Every stage*).
- The loaders are named in `config/symbols.toml` (`stage_item_setup`, `stage_gimmick_placements_load`, `stage_emitter_placements_load`, `stage_ambient_placements_load` and others). The recompiler does not read that file for this game, so `src/recomp/gen` is unchanged.
