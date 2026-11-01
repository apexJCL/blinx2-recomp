## 1. Findings

- [x] 1.1 Find the collision data: the stage map table's first column, by area (`design.md` §1).
- [x] 1.2 The load-time bake and octree, sub_001642A0 (§2).
- [x] 1.3 The per-frame query and push-out, sub_00163550 / sub_00165380 / sub_00165630 / sub_001636C0 (§3).
- [x] 1.4 The player's call sites and radius (§4).
- [x] 1.5 The tunnelling's cause, with addresses (§5). The bug reproduces on original hardware, so the recompilation was not examined.
- [x] 1.6 The trace (`walls_trace`, §5): on Stage 2, flags are always 7, +0xF8 holds the last frame's position, no back-face contact and no dynamic override in ordinary play. Contact order dropped (one shared best); one step into the window is enough for one query and needs no pot, but a pass-through in play is not reproduced (§5 verdict).
- [x] 1.7 The A/B through the `walls` mod's hooked face test (§6, the entry-face rule): thin pairs through the far side 186 → 55 of 352 (the rest out of reach for both), 36 of 2000 random spheres changed, all of them stock pushes through the entry face; in game, an injected step makes the stock wall query push the player out of the far side and the fix push it back in front, but the player update's second collision pass (0x185AB1 → 0x1858BC) undid the stock push at that spot (follow-up).
- [x] 1.8 Thin-wall scan of every stage (§5 table): back-to-back faces under `2r` matched by overlapping projections.

## 2. CLI prototype

- [x] 2.1 `extract/collision.py`: walk the trees as the game does (every transform, hidden nodes kept), world triangles by class.
- [x] 2.2 glTF with `-col` class nodes (StaticBody3D + ConcavePolygonShape3D on import) and a see-through debug mesh per class; `collision.gd` toggles it.
- [x] 2.3 `--collision` flag, `collision` and `collision_skip` manifest keys, docs; stock output unchanged without the flag.
- [x] 2.4 pytest on synthetic bytes: the bake, flags ignored (including ZXY: the bake always rotates X first), glTF names and materials, skip, opt-in, manifest errors.
- [x] 2.5 cat `game.toml`: the collision trees of every stage.
- [x] 2.6 M13, M21, M23 and M24 exported with `--collision --import` into a local scratch directory: no Godot errors; a headless load counts the expected static bodies and concave faces.

## 3. Follow-ups (each its own tracker item)

- [x] 3.1 The fix as the opt-in `walls` mod (`RECOMP_WALLS`, default off): the entry face replaces a back face the centre was already behind (§6). Option 2 as first written and the smallest `|s|` were rejected. Experimental: shown by the probe only. Review fixes (2026-11-01): the decision is the pure `wall_decide` (X's own edge, the strict tie, zero or NaN normals), steps over `2r` ignored, the triangle copy only on a back-face contact, the query state cleared every frame.
- [ ] 3.2 Optional: sub-step the player's move when it is longer than half the sphere's radius.
- [ ] 3.3 Name the functions in `config/symbols.toml` (sub_001642A0, sub_00163550, sub_00165380, sub_00165630, sub_001636C0, sub_001A3160).
- [x] 3.4 The surface classes' meaning (the four globals at 0x65B1E0..0x65B1F0 that switch classes off): `enemy_wall`, `camera_floor`, `unused_blue`, `camera_pass`, with their setters (§1, §8). The names are inferred from the code, not observed in play. The CLI side, `[[extract.collision_class]]` rows feeding `collision.json` and the Godot node names, is proposed in §8 and waits for a CLI change (cat cannot carry the rows before its pin understands them).
- [ ] 3.5 Optional: the extract's collision layer for BLiNX 1, if its engine keeps collision the same way.
