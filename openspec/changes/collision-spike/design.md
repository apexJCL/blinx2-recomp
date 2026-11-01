## Context

The tracker item asked three questions: where the stage collision is, how to show it in the Godot extract, and why the player goes through a wall in the user's recording. The bug also happens on original Xbox hardware (the user, 2026-10-31). The cause is therefore in the game's own engine, and the recompilation was not examined. Addresses are XBE VAs (`sub_XXXXXXXX` in `src/recomp/gen/`). The method was disassembly with capstone over the dump's XBE; Ghidra's headless decompiler does not run on this Mac.

## 1. The data

- **Where it is.** The stage map table at .data 0x40d180 has 12-byte rows `(collision tree, visual root, texlist)`. The extract already uses the second and third columns. sub_000E2180 and sub_000E21C0 copy an area's first column to `MEM32(0xB8B840 + area * 4)` and call sub_000320F0, which fills in each model's bounding sphere. The debug draw at about 0xE5D71 draws these trees when `MEM32(0xEC4CC8) != 0`.
- **Format.** Each collision tree is an ordinary Ninja chunk object tree. The root carries eval flags 0xF, so it is hidden and never drawn. Vertices are VNX with packed normals. Strips are untextured kind 64/65.
- **Surface class.** The material diffuse colour (`u32 & 0xFFFFFF`) is the triangle's surface class:

  | Class | Name | Tested | Flag set to 0 (class solid) | Stages |
  |---|---|---|---|---|
  | `0xBFBFBF` | `solid` | always | n/a | all 20 |
  | `0x00FFFF` | `enemy_wall` | unless `[0x65B1F0] != 0` | only around the enemy and object updates in `stage_update` (0x6739E to 0x67423) | M11, M14, M21, M31, M41, M43, M51, M53 |
  | `0x7F7F00` | `camera_floor` | unless `[0x65B1E0] != 0` | only for the camera's height probe in sub_000299F0, on stage indices 5 and 7 (M21, M23) | M21, M23 |
  | `0x0000FF` | `unused_blue` | unless `[0x65B1EC] != 0` | never: stage start sets it to 1 and nothing clears it | none |
  | `0xFF00FF` | `camera_pass` | unless `[0x65B1E8] != 0` | in the stage frame, always except while `stage_render` runs the camera follow | M11, M13, M33 |
  | `0xFFFFFF` | (skip) | never | n/a | M31, M33 |

  Other diffuse colours (`0x7F0000`, `0xB2B2B2`, `0x00007F`, `0xFFFF00` and more, from M31 on) are always tested, like `0xBFBFBF`. Code outside the collision test compares them (the player code at 0x17D09F and 0x183F50 tests 0x7F0000, 0xBF0000 and 0xFF0000; 0x3B915 tests 0xB2B2B2), so they look like surface types, not switches. The setters and the evidence for each name are in §8 (task 3.4). The names are inferred from the code, not observed in play.
- **Not collision.** Some hidden-looking roots are not collision: M13's 0x018F426C is a textured alpha wall. M13's collision tree is 0x017FB3F0.
- **Per-stage trees.** They are recorded in `game.toml` (`[[extract.stage]] collision`). M64 has none.

## 2. Load-time bake and octree: sub_001642A0

It is called from 0xE2FAE and returns early on stage 0x1C. It does three things.

1. **Clears the buffers.**

   | Buffer | Address | Entry size | Count at |
   |---|---|---|---|
   | octree nodes | 0xCAE8A8 | 0x38 bytes | 0xCC9E30 |
   | reference cells `(tri*, next)` | 0xBACB98 | 8 bytes | 0xCCA048 |
   | triangles | 0xC21EA8 | 0x48 bytes | 0xCC9E2C |

2. **Bakes every area's tree into world triangles.** It pushes a half turn about X (`push 0x40490fd8; call 0x2D4E20`, RotX(π)), then calls sub_00164850 for each area `i < [0xB871A0]`.
   - **sub_00164850** walks the tree. It applies every node's translation (0x2D4CB0), rotations and scale (0x3FF50) whatever the eval flags say. The rotations are always RotZ (0x2D4DA0, angle +0x1C), RotY (0x2D4DE0, +0x18) and RotX (0x2D4E20, +0x14), each only when its angle is nonzero: X is applied first, and the ZXY flag (0x20), which the draw walker sub_000302E0 honours, is ignored. It recurses into the child at +0x2C and follows the sibling at +0x30. For each model it calls sub_00164A80.
   - **sub_00164B00** transforms the vertex list into 0x65EF00 (32 bytes per vertex).
   - **sub_00164ED0** reads strip chunks 0x40/0x41. It keeps the material diffuse, alternates the winding by strip parity and sign, writes 0x48-byte triangles and grows the world AABB (min 0xC21E98, max 0xCCA03C).
   - **sub_00165200** fills in each triangle's normal (`cross(v1 - v0, v2 - v0)`, normalised), centroid and bounding radius.
   - **Triangle record:** v0 +0x00, v1 +0x0C, v2 +0x18, class +0x24, query stamp +0x28, normal +0x2C, centroid +0x38, radius +0x44.

3. **Builds the octree.** The root node covers the AABB grown by 100 on each side. Its centre is at +0x28 and its half-size (largest extent + 1) at +0x34. Its 8 children are at +0x00..+0x1C, and its reference list head and count are at +0x20 and +0x24.
   - A node with more than 50 triangles splits into 8 (sub_001645A0, sub_001645D0, octant table 0x164798).
   - A triangle goes into a child when the triangle-box test passes: sub_001647C0 → sub_000120D0, with box half-size `h * 0.5 + 0.1`.

**Why the export leaves out the half turn.** The bake's half turn is the game's own collision space; the player's position is kept in it. The extract writes the stage in tree space. The collision trees' bounds match the visual roots' bounds there with no turn (M21: collision 0x022E1AFC spans (120, 0, 390)..(810, 400, 810), visual 0x023128EC (120, 0, 390)..(900, 380, 810)). So the collision layer uses the trees' own transforms and the stage's `up`, as the visuals do.

## 3. The per-frame query

### sub_00163550: the query

Its arguments are a sphere (in esi), the out point, out normal, out penetration, out class, and flags.

1. Unless `flags & 4`, it tests the static stage through sub_00165380. The face "best" starts at 99999.0 and the static penetration at -9999.0.
2. It tests dynamic objects through sub_00163160 (pots, platforms; walkers sub_0002E8E0 and sub_000318A0).
3. It returns **one** contact. The dynamic one replaces the static one when its priority byte is above 5, or equal to 5 with a larger penetration (0x16362C..0x163645).

### sub_00165380: the octree walk

It increments the stamp `[0xEC5000]` and walks the octree. It uses the cached node list at 0xCC9E38 (count `[0xCCA038]`) or the recursive sub_001654E0 from 0xCAE8A8, and rejects nodes against the sphere. It calls sub_00165630 for each referenced triangle not yet stamped this query.

### sub_00165630: the per-triangle test

It first applies the class mask (the globals in §1), a bounding-sphere reject, and the sub_000E8DB0 pre-check. Then:

- **Vertices** (`flags & 8`, sub_00030230, a vertex within `r`) and **edges** (`flags & 4`, sub_00030070, an edge within `r` whose closest point lies between its ends) are taken when their distance `dist` is below the best: they write normal `(c - p)/dist` from the closest point `p`, penetration `r - dist` and `best = dist`. Bit 1 is not read by the test (checked against the disassembly, 0x1657A7, 0x1658A4 and 0x1659A0).
- **Face** (`flags & 2`, 0x1659AF..0x165C57), tested after the vertices and edges. With centre `c`, unit normal `n` and `s = dot(c - v0, n)`:
  - it needs `|s| <= r`. This makes the test **double-sided**: a centre up to `r` behind the face passes;
  - it needs `s <= best_s`. The **smallest signed distance wins** across all the faces of the query;
  - it needs the projected point `c - n*s` inside the triangle (three cross-product sign tests).
  - On a hit it writes point `c - n*s`, normal `n` (always the face's front normal), penetration `(r - s) * 1.1` (0x3DEFFC), the class, and `best_s = s`.
- **The class** is written for any contact the test took, as the whole u32 at the triangle's +0x24 (0x165C6E), high byte included.
- **One best for everything** (corrected by task 1.6's disassembly, 2026-10-31). Vertices, edges and faces compare against and write the **same** best (the test's ninth argument), which the walk sub_00165380 sets to 99999.0 once per query. A vertex or edge's value is its distance (never negative), a face's its signed distance. So the query returns the contact with the **smallest value over the whole walk**, and the walk's order only breaks exact ties. A face the centre is behind (`s < 0`) beats every vertex, edge and front-side face, and of two such faces the deeper one wins. (The spike read the faces' best at +0xAC and the vertices' at +0xB0 as two slots, with the last accepted contact winning; both offsets are the one pointer at different stack depths.)

### sub_001636C0: the push-out wrapper

It calls sub_00163550 and stores the hit flag in `[0xB90B88]`. On a hit it moves the centre to `c + n * penetration`. sub_00163780 (called from 0x81B05) is a variant of it.

## 4. The player

- **Calls.** The player update sub_00176150 calls sub_001636C0 with return addresses 0x178F92, 0x184F26, 0x185063, 0x185239, 0x185503, 0x185959 and 0x185B65, each with flags 7: the face (2) and edges (4); vertices (8) are off, and bit 1 is not read by the triangle test.
- **Chained calls.** The call returning at 0x185063 runs only when the one returning at 0x184F26 found a contact (`je 0x1850E6` at 0x184F35 skips it otherwise), and it re-queries from the pushed centre. The call returning at 0x185239 runs on every path through that block.
- **Sphere.** The centre is the player position (+0xEC/+0xF0/+0xF4) plus an offset. Afterwards the position becomes the new centre minus that offset.
- **Radius.** sub_001A3160(player, 1) returns it per character and state. Values seen: 1.5, 2.95, 3.8, 4.0, 5.5 and 6.0.
- **Other callers.** Enemies and objects call the same functions: sub_001636C0 from 0x8xxxx, 0x9363B and 0x2xxxxx, and sub_00163550 directly from 0x810B0, 0x813BB, 0x8A55F, 0x8A8CF, 0xC376B, 0xC4527, 0x28B208, 0x28B81B and 0x28E6A5.
- **Previous position.** It is kept at +0xF8 and nothing in the collision path reads it. The test is discrete: there is no sweep from the previous position.

## 5. Why the player goes through the wall

**The selection rule.** Take every face whose plane is within `r` of the centre, on either side, with the centre's projection inside it. The game resolves only the one with the smallest signed distance `s`. When the centre is behind a face (`s < 0`), the push `c + n * (r - s) * 1.1` moves the centre to about `1.1 r` in front of that face. For a face whose front looks away from the player, "in front" is the far side of the geometry.

**A worked case.** Take a wall `w` thick, front face F towards the player and back face B facing away. The centre is `d` into F (`d < 0` in front of F).
- F gives `s_F = -d` and B gives `s_B = d - w`.
- B passes the face test once `|s_B| <= r`, that is `d >= w - r`, and beats F once `s_B < s_F`, that is `d < w/2`.
- So B wins while `w - r <= d < w/2`. That window exists only when **`w < 2r`**: up to 12 units at the largest radius, 6.0.
- If `w < r`, the window starts before the centre reaches F: a sphere touching F from the front can already pick B.
- The push from B moves the centre to `1.1 r - 0.1 s_B` beyond B, out of reach of both faces. The chained re-query at 0x185063 (§4) then sees no wall and cannot undo it. But that is one query: in the one in-game case (§6), the player update ran its collision block again from the previous position (the loop from 0x185AB1 back to 0x1858BC) and that pass did undo it.
- A wall at least `2r` thick cannot be passed this way through its broad faces. It can be passed only at corners and side faces, where another face's back is within `r` of the centre while that face's projection still contains it (a pillar's corner, a wall's end).

**Why only sometimes.** Since the test keeps one best for every contact (§3), the walk's order only breaks exact ties, so the walk order does not explain it (the contact-order hypothesis is dropped). The bug needs the centre to be behind both faces of a thin wall with the far face the deeper one: `w - r <= d < w/2`. Ordinary movement rarely gets there. The player moves less than `r` per frame and the near face pushes it back out while `d < w - r`. Only a step that lands in the window in one frame does it.

**Task 1.6: the trace** (`walls_trace`, PC D3D11, the `st2` pad script on Stage 2 (M21), random moves, about 5600 frames on the stage). Runs: `runs/wall-tunneling/T1off-*`, `T1on-*`.
- **Player queries.** Sites 0x184F26, 0x185239 and 0x185959 run every frame, and 0x185B65 on some. The radius was 4.0 throughout, and the flags were always 7, as §4 says (so the walk tests faces and edges only).
- **Contacts.** The walk took 1745 faces and 468 edges. **None was a back face** (`s < 0`), so random play never reached the window above.
- **Dynamic objects.** sub_00163160 never answered, so the override at 0x163647 never happened. No pot was on this route, so the trace cannot show the pot's priority.
- **Previous position.** From the stage's first frame (767), player +0xF8 is the last frame's position on 4142 of 4143 moving frames; the other is the spawn itself. The game copies the position there before it moves the player, so `pos - prev` at query time is the frame's move. That makes it a usable "previous centre" for the fix. Before the stage (the title and the load, frames 221 to 766), +0xF8 holds a placeholder about 1340 units from the position; counting those frames gave the 88% first reported. The fix ignores any step longer than `2r` (a respawn or warp), so neither the spawn nor a warp acts as a previous centre.
- **Class switches**. On Stage 2 from the stage's first frame: `[0x65B1E0] = 1`, `[0x65B1E8] = 0`, `[0x65B1EC] = 1`, `[0x65B1F0] = 1`. So classes 0x7F7F00, 0x0000FF and 0x00FFFF are off and 0xFF00FF is solid. They did not flip during play.

**Verdict on the triggers.**
- **The single step is enough for one query.** Through the game's own triangle test (the task 1.7 probe), a centre inside the window is pushed out of the far side with no pot. In game, the one injected step did take the far face on its wall query, but the player did not pass through: the update's second collision pass (§6) undid it. A full pass-through in play is not reproduced.
- **The pot is not shown to be needed for one query,** and the trace never saw a dynamic contact replace a static one. Whether the pot (or the wall-jump state) is what lets a real pass-through skip the second pass is open (§6 follow-up).

**What makes it worse.**
- The test is discrete per frame, with no sweep.
- Each call resolves one contact.
- The 1.1 overshoot carries the centre past the far face rather than onto it.

**Thin geometry scan.** A scan of every stage's collision for back-to-back face pairs (normals opposed, dot < -0.9; the far face behind the near one, with overlapping projections on the near face's plane). Counts are near faces, so a wall's two sides count twice. "Walls" have a mostly horizontal normal (|n.y| < 0.7); the rest are floors and ceilings.

| Stage | Faces | Walls `w < r` | Walls `w < 2r` | Floors `w < 2r` | Thinnest |
|---|---|---|---|---|---|
| M11 | 5213 | 315 | 535 | 17 | 0.20 |
| M13 | 2392 | 193 | 524 | 273 | 1.50 |
| M14 | 2775 | 273 | 463 | 0 | 0.10 |
| M111 | 702 | 99 | 99 | 0 | 0.29 |
| M121 | 768 | 44 | 49 | 35 | 1.50 |
| M21 | 2863 | 49 | 110 | 0 | 0.04 |
| M23 | 2376 | 49 | 120 | 124 | 3.51 |
| M24 | 1010 | 0 | 0 | 0 | none |
| M31 | 6484 | 167 | 295 | 65 | 0.22 |
| M33 | 4697 | 154 | 222 | 184 | 0.11 |
| M34 | 3694 | 23 | 68 | 23 | 0.17 |
| M41 | 3670 | 114 | 653 | 199 | 0.23 |
| M43 | 3158 | 194 | 230 | 64 | 0.01 |
| M44 | 934 | 165 | 213 | 9 | 0.22 |
| M51 | 4588 | 58 | 179 | 16 | 1.17 |
| M53 | 2921 | 49 | 200 | 25 | 0.11 |
| M54 | 1845 | 0 | 0 | 0 | none |
| M61 | 1900 | 0 | 0 | 0 | none |
| M91 | 2247 | 5 | 79 | 11 | 2.85 |
| M93 | 1852 | 45 | 157 | 30 | 0.04 |

`r` here is 6.0, the largest radius. With `w < 2r`, 4196 of 56089 faces sit in a wall thin enough for the back face to win, in every stage but M24, M54 and M61; M21 (Stage 2) has 110. The earlier scan (centroids within 10 units, gap under `r`) missed most of them. So thin walls are common, not rare. Penetration (a pot or a wall-jump step) is not needed for the selection bug: in a thin wall, a deep enough step is enough, and in a wall under `r`, contact can be. What keeps most of them solid in play is that ordinary moves are shorter than `r` and the near face pushes the centre back out before it reaches the window (task 1.6).

## 6. The fix: the entry face (opt-in mod)

**Shape.** The fix is the `walls` mod (`src/walls_mod.c`, rule in `src/wall_logic.c`). It is off by default (`RECOMP_WALLS`, `mods."walls.enable"`), so stock behaviour does not change. It is a mod rather than a default-on `src/fixes` entry because the bug happens on original hardware and changes how the game plays, so it stays opt-in (the user, 2026-10-31). It hooks:
- sub_001636C0, pre and post, to tell the player's seven sites apart by return address;
- sub_00165630, pre and post, never a skip;
- sub_00163160 (the dynamic objects), post only, for the trace's override check.

**The rule.** When the test takes a face X with the centre behind it (`s_X < 0`), and the previous centre `c - (pos - prev)` was behind X too (a step longer than `2r` gives none), the mod looks for the face Y the sphere entered by. Y must:
- face the other way (`n_X . n_Y < -0.5`);
- be within `r` (`|s_Y| <= r`);
- hold the centre's projection;
- have the previous centre on its front (`>= -0.01`).

Of several such faces, the smallest `s_Y` wins. Without X's face, the test would have left the walk's earlier best, or taken X's own edge (or vertex) if that beat it. If that value is at most `s_Y` (the game's strict comparison: a tie keeps the earlier contact), it stands: the earlier outputs are put back, or X's edge is written. Otherwise Y's point, normal, push `(r - s_Y) * 1.1`, class and best are written. A triangle whose normal is not unit length (zero, NaN) is never X nor Y. The whole decision is `wall_decide` in `src/wall_logic.c`, tested without the game (`scripts/test_walls.py`). With no such Y the game's contact stands: a one-sided platform entered from below, or a centre that was already inside. The rule is symmetric, so a wall entered from its far side gets its far face. Enemies, items and the dynamic objects stay stock.

**Rejected.**
- **Option 2 as first written** (back-side faces rank below every front contact). A centre that entered by F is behind F too, so F is a back-side face as well. With no front contact, the ranking falls back to the smallest `|s|`, which picks B whenever the centre is past the middle, and in the window.
- **The smallest `|s|` alone.** It picks the nearer plane, not the entered one: B in the second half of the wall.
- **Taking a face only from its front** (option 1). It drops the face the centre is behind, and when no other contact is found the sphere stays in the wall.

**Task 1.7: the A/B** (PC D3D11, Stage 2). Runs `runs/wall-tunneling/P1-*` and `TP2*-*`.
- **Thin pairs through the game's own test** (`probe`; `guest_call` of sub_00165630 over the stage's triangles, r 2.95, 44 pairs under `2r`, the centre at 8 depths from the near face):

  | | Ends behind the near face |
  |---|---|
  | stock | 186 of 352 |
  | fix | 55 of 352 |

  Of the 55, 47 are deeper than `r`, where the near face is out of reach for both. The other 8 are on a 0.29-wide pair that neither walk hits.
- **Elsewhere** (2000 spheres near random solid triangles, random previous centres): 1758 hit. Stock and fix differ on 36, and on all 36 stock pushed the centre through the face the fix took. Nothing else changed.
- **In game** (`tp`: player 0 placed in front of a 5.0-wide wall, then one step 30% into it, r 4.0): on the step's wall query (0x185959) the walk took B in both runs.
  - **Stock** pushed the centre 9.75 behind F, out of the far side.
  - **The fix** (`W`: F written in B's place) pushed it 4.55 in front of F.

  In stock, the player update then ran its collision block again in the same frame. The code has a loop back from 0x185AB1 to 0x1858BC. The pass started 3.5 in front of the previous position, so the player ended in front of the wall in both runs. So the injected step does not reproduce a full pass-through at this spot: something in the player update can undo a far-side push. A follow-up should find what sends the update back, and whether the pot or the wall-jump state skips it.

  In about 5600 frames of ordinary play on the stage (`T1on`) the fix never acted. Neither did the golden: it ran with the mod off and passed.

**Optional extras, not done:**
- sub-step the player's move when it is longer than `r / 2`;
- clamp the back-side push to `r - s`, without the 1.1 overshoot.

## 7. The extract's collision layer

**Writer.** `xbr extract --collision` (CLI `extract/collision.py`) does the same walk as sub_00164850. It applies every transform, in the bake's fixed X, Y, Z order whatever the ZXY flag says, and keeps hidden models. It writes world triangles grouped by class into `<name>_col.gltf`, one node per class:
- `col_<rrggbb>-col` for a class the game tests. Godot's importer gives that node a `StaticBody3D` with a `ConcavePolygonShape3D` and keeps the mesh.
- `col_<rrggbb>` for a class in `[extract] collision_skip` (`0xFFFFFF` for BLiNX 2). It is drawn, with no shape.

The debug material is the class colour at 35% alpha, unlit and double-sided. `collision.gd` toggles the meshes with `C` (`show_meshes` in the editor) and leaves the shapes alone. The `-col` route was chosen over building shapes in a script so that the shapes exist in the imported scene, where the editor and a later physics probe can use them.

**Check.** M13, M21, M23 and M24 imported headless with no errors. A headless load of each scene found the expected bodies and faces:

| Stage | Static bodies | Concave faces |
|---|---|---|
| M13 | 2 | 2392 |
| M21 | 3 | 2863 |
| M23 | 2 | 2376 |
| M24 | 1 | 1010 |

## 8. Surface classes

The four class flags are BSS (zero at boot). Every write to them, from the XBE's absolute references, is listed below; nothing writes them through a computed address. Three functions apply the mask with the same skip-while-set rule: the sphere face test sub_00165630, its sibling sub_00166160, and the model test `nj_model_collide` (sub_0002EC20, also sub_000305F0). Names are from `config/symbols.toml`. The class names below are inferred from these writers and from the geometry, not observed in play.

**Stage start.** `stage_area_setup` (sub_000606F0) at 0x61AFF..0x61B11 stores `[0x65B1EC] = 1`, `[0x65B1F0] = 1`, `[0x65B1E8] = 0`, `[0x65B1E0] = 1`. In the stage frame (`stage_update`, then `stage_render`), outside the windows below, the player, the camera and every other query therefore treat cyan, olive and blue as air, and fuchsia as solid. The claims below hold for the stage frame only. Other scenes run from `sys_frame_update` (sub_00062FB0) with whatever the flags hold then; before the first stage loads that is 0 for all four (every class solid). Whether those scenes query stage collision was not checked.

### `0x00FFFF` `enemy_wall` (`[0x65B1F0]`)

- **Writers.** `stage_update` (sub_000649B0) stores 0 at 0x6739E, just before `ent_enemy_update_all(ent_enemy_list 0xAF0E88)`. Then, only when `[0xB2A740] == 4` (the `jne` at 0x673B4 skips to 0x67419 otherwise), come a second enemy call, the countdown at 0xB2A7C0 and, when it runs out, the sound calls sub_0029F960 / sub_0029FED0 and the resets of 0xAE73E0 and 0xB2A740. Always, at 0x67419, comes sub_000E0520 (the object list at 0xB22E20, whose pool includes `ent_item_pool` 0xB22E68). It stores 1 at 0x67423, before the effect pool sub_0022BE40. The generated copies sub_000664F2, sub_000664F4 and sub_00066A4A are the same instructions.
- **Also 1.** Eight handlers in 0x22C800..0x230458 store 1 before their 60-unit probe through sub_00164100 (0x22CB26, 0x22D87E, 0x22E3F9, 0x22EB22, 0x22F345, 0x22FADE, 0x22FF2A, 0x2303C3). Six of the eight are in the handler list that follows the descriptor at 0x4AD5B0, which sub_000E2CD0 registers at 0xE33C7 next to M14's models; by those model addresses they are M14's stage objects. Run from the object list inside the window, one of them turns the class off for the objects after it until the frame's 0x67423 store.
- **Player.** In the stage frame, `ent_player_update` (0x176150) runs from sub_00067CF0 (called at 0x670F6 and 0x670FD), before the window, so the player does not collide with the class there. The camera runs from `stage_render`, also outside it. `ent_player_update` has other callers outside `stage_update` (sub_001C2610, sub_001DF1E0, sub_001E0DF0, sub_00348590, sub_00348F10, sub_0035C210, sub_00055AE0, sub_00056010); what the flag holds for them is not covered here.
- **Geometry.** Vertical strips 20 to 50 units high along platform edges and pit rims (`|n.y|` 0). M14's 69 triangles are the exception: one horizontal sheet, 807 by 950, at y -35..2: by the rule above, a floor that enemies and items stand on and the player falls through (not checked in play).
- **Name.** A wall or floor for enemies and items that the player passes through: it keeps enemies on their platforms.

### `0x7F7F00` `camera_floor` (`[0x65B1E0]`)

- **Writer.** sub_000299F0, called from `cam_follow_a` (0x2E398). When `stage_current` (0xB87168) is 5 or 7 (round 2 stages 1 and 3: M21 and M23), it stores 0 at 0x29A5B, queries a 50-unit vertical probe (sub_00164100) that starts 30 below the camera target, and stores 1 at 0x29AC6. On an `0x7F7F00` hit it stores the hit height - 10 in `[0x65B1B4 + view * 4]`; otherwise the stage's default from the float table at 0x3F2618 (indices 2, 3 and 18, M13, M14 and M44, are -40, 50 and -570; the rest 0).
- **Use.** The camera functions sub_00029B40, sub_0002BF40 and sub_0002D0D0 read `[0x65B1B4 + view * 4]` and raise the camera target's y to at least that height plus a constant (0x29DCB).
- **Geometry.** Horizontal quads only (`|n.y|` 1), 40 to 500 units across, at several heights in M21 and M23, the two stages whose index the probe checks.
- **Name.** The camera's floor: no character or object collides with it, and the camera keeps its target above it.

### `0x0000FF` `unused_blue` (`[0x65B1EC]`)

- **Writer.** Only `stage_area_setup`, which stores 1. No stage holds the class. Before the first stage loads the flag is 0 (BSS), so a query then would treat blue as solid; whether any runs was not checked, and no stage holds the class anyway.
- **Name.** Unused: never solid in play. Kept in the table because the face test still checks it.

### `0xFF00FF` `camera_pass` (`[0x65B1E8]`)

- **Writers.** `stage_render` (sub_00067E60) stores 1 at 0x67E89 and 0 at 0x67EB5. Between them it runs `cam_follow_a` (skipped when `stage_play_mode` is 0x800) and `cam_follow_b`, both skipped while `stage_pause_flag` is set. `cam_follow_b` has a second caller: sub_001BD2F0 at 0x1BD3BE, reached from the scene sub_001C2610 that `sys_frame_update` calls at 0x63654. Nothing sets the flag around that call, so with the stage-start value 0 the class is solid for that camera.
- **Geometry.** M11: four posts, 7 by 18 by 7, at the corners of a 50 by 128 rectangle. M13: one column, 5 by 99 by 10. M33: two small slanted pieces, 30 by 10.
- **Name.** Solid for the player, enemies and objects, ignored by the stage camera: thin props that would otherwise push the camera in front of the player.

### Runtime check

Skipped, so the names are inferred, not observed. Each writer is an unconditional store that brackets a fixed set of calls: no state, mode or event decides the value inside its window. The class test's polarity is in the code: after the flag loads at 0x16566F, 0x16567F and 0x16568F a `je` goes to the face test (0x1656BD) when the flag is 0; after the load at 0x1656B4 a `jne` at 0x1656BB goes to the skip (0x1656AD) when it is non-zero.

A later one-shot check would confirm the cyan name cheaply: on M14 and M21, log the caller (return address) of every sub_00165630 call that hits a `0x00FFFF` triangle while `[0x65B1F0]` is 0. The names hold if every caller is an enemy, item or stage-object update and none is the player or the camera.

### Showing the names in the extract (proposal, CLI follow-up)

- **Manifest.** The CLI manifest is strict: unknown keys are errors, and its field types are STR, INT, INTS and TABLES, so a table keyed by hex strings does not fit. A new optional array of tables does, with integer colours like `collision_skip`:

  ```toml
  [[extract.collision_class]]
  colour = 0xBFBFBF
  name = "solid"

  [[extract.collision_class]]
  colour = 0x00FFFF
  name = "enemy_wall"

  [[extract.collision_class]]
  colour = 0x7F7F00
  name = "camera_floor"

  [[extract.collision_class]]
  colour = 0x0000FF
  name = "unused_blue"

  [[extract.collision_class]]
  colour = 0xFF00FF
  name = "camera_pass"

  [[extract.collision_class]]
  colour = 0xFFFFFF
  name = "skip"
  ```

  The CLI would reject a duplicate colour or a name that is not `[a-z0-9_]+`. cat's `game.toml` cannot carry these rows until its `[cli]` pin reaches a CLI that knows the key; until then the names live only here.
- **`collision.json`.** Each class entry gains `"name"` when the manifest gives one. The class stays the key, so readers keyed on colour keep working.
- **Godot nodes.** `col_<name>_<rrggbb>-col` (or `col_<name>_<rrggbb>` for a skipped class); with no name, the node keeps `col_<rrggbb>`. The colour stays in the name, so two classes can share a name and the debug colour still matches the node.
- **Shapes.** The `-col` shape suits a player-centred probe only for classes the player hits. `enemy_wall` and `camera_floor` are air to the player. A second list, `[extract] collision_player_skip = [0x00FFFF, 0x7F7F00, 0x0000FF]`, would draw them with no shape, like `collision_skip`; that is a choice for the CLI change, since an enemy-side probe would want them.
- **Supersedes** the old Risks note that the classes' meanings were unknown. Naming the always-tested surface types (`0x7F0000`, `0xB2B2B2`, `0x00007F`, `0xFFFF00` and others) is separate work: they change what a contact does, not whether it happens.

## Risks

- **Double-sided shapes.** Godot's concave shapes are double-sided by default and the game's face test is too. The debug view does not show which side is the front. A later pass could tint back faces to show where §5 bites.
- **Which player a query belongs to.** The walls mod gives a sphere query to the nearest player whose position is within 12 units of its centre; the query's arguments carry no player pointer. In co-op, two players closer than that can swap, and the fix then reads the other player's step. The worst case is a wrong previous centre: the rule then finds no entry face (the game's contact stands) or, with both players moving the same way, the right one. The step bound (`2r`) caps how far off it can be. Reading the player from the caller's frame would remove the guess; it was not needed for one player.
- **Unproven in play.** The fix is opt-in and labelled experimental: the probe shows the rule on the game's own triangle test, but no pass-through in play has been reproduced (§6), so it has not been seen to fix one there.
- **Class names are inferred.** §8 reads them from the code; none was confirmed in play (§8, runtime check).
