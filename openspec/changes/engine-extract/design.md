# Design: engine-extract

## Context

- Findings this builds on: `engine-bridge-assessment/design.md` (S1, S2), `notes/engine-bridge/s2-FINDINGS.md`, the S2 extractor in `runs/engine-bridge/s2/tools/` (about 980 lines, stdlib, throwaway) and the S1 scripts in `runs/engine-bridge/s1/scripts/`.
- The CLI already reads IPK1 archives and DDS (`enhance/ipk.py`, `enhance/dds.py`); textures reuse them.
- Godot 4.7.2 is pinned for the spikes in `xbox-recomp/toolchains/godot-4.7.2/` (SHA256SUMS); the CLI pin uses the same release.

## Layout

```
xbr extract [--stage NAME ...] [--out DIR] [--import] [--list]
  game.toml [extract] --> XBE sections + textures (dump) --> ninja parse
     --> glTF 2.0 (.gltf + .bin) per stage, textures as PNG
     --> Godot project: project.godot, one .tscn per stage instancing its glTF
     --> --import: godot --headless --import (pinned)
```

- Package `xboxrecomp_cli/extract/`: `image` (section bytes by name, VA to file offset), `ninja` (chunk model, node tree), `gltf` (writer), `godot` (project files), `cli` (verb).
- Output defaults to a gitignored directory of the game repo (follow the repo's convention for generated trees); `--out` overrides.
- Stdlib only, like the rest of the CLI; PNG writing with `zlib`.
- The Godot pin (version, URL, sha256 per host) lives in `extract/godot.py`, not in `pins.py`, so `pins refresh` does not move it; bump it there by hand.

## The `[extract]` table

```toml
[extract]
vertex_header = 16          # bytes before the vertex list: BLiNX 1 16, BLiNX 2 8
packed_normals = true
angles = "bams"             # BLiNX 1 "bams" (0x10000 per turn), BLiNX 2 "radians"
texname_size = 32           # texture-name entry: BLiNX 1 32, BLiNX 2 36
textures = "media/{name}.dds"   # loose files, or "ipk:media:dds/{name}.dds" (BLiNX 2)
[[extract.stage]]
name = "MAP11"
section = "MAP11"
root = 0x01DC6CAC           # a VA, or a list of VAs (BLiNX 2), found offline
texlist = 0x01C68620        # one per root
```

`docs/manifest.md` in the CLI lists every key; the rule is that no game constant lives in the CLI. Stage names match `--stage` in any case.

## Parser rules (from S1 and S2)

- Find tables by structure, never by another tool's fixed addresses (pyBlinx's offsets are for another build).
- The object node is 0x34 bytes: +0x00 flags, +0x04 model, +0x08 position, +0x14 rotation (Ninja integer angles, 0x10000 per turn), +0x20 scale, +0x2C child, +0x30 sibling. Apply the transforms in the game's order (check against `sub_000302E0` / BLiNX 1's walker).
- The vertex chunk `size` field is not the stride; normals are Xbox packed; UVs are not divided by 255.
- Axes: Y up, right-handed, 1:1, no conversion in either game (S2; for BLiNX 2 see the S4 check below). The `up = "-y"` key exists for a game whose floors face -Y in the data; neither BLiNX does.
- Materials: texture, tiling, clamp, flip, double-sided, cut-out alpha. Other blend modes, specular and material type 24 are reported as unsupported per stage, not guessed.
- Translucent textures: a texture whose alpha never reaches 0 and dips below 240 is glass, not a cut-out, so it blends even without the strip's use-alpha flag (an alpha test at 0.5 would punch holes in it). On both dumps this is one texture: BLiNX 2 M13's glass floor `h_b2_wall8a_0000_alpha` (alpha 119 to 255, strip flags 0x02, blend 0x25). BLiNX 1 has none.
- Environment maps: a strip with flag 0x40 carries no UVs (kind 64); the game looks its texture up from the view-space normal each frame. A static scene has no view, so the writer uses the model-space normal, `u = 0.5 + 0.5 nx`, `v = 0.5 - 0.5 ny` (a sphere map at the identity view). These are the lamp lenses (`renz`) in both games: 39 strips in M13, 24 in MAP11. Counted under "approximated", not unsupported.
- Godot wraps: Godot's glTF importer keeps one repeat flag per material and takes it from wrapT (checked headless: (repeat, clamp) imports as no repeat, (clamp, repeat) as repeat). A texture clamped in V and tiled in U, like M13's grass-rock fringe `h_b2_tunagi_1a0000` (U 0 to 3, V 0 to 0.996), therefore clamped U too and smeared along the rock sides. Only a texture whose two wraps differ is changed: an axis whose UVs stay inside [0, 1] takes the other axis's wrap, which tiles the same over that range (both axes inside: clamp). Wraps that agree are kept, since clamp and repeat do not look the same at [0, 1]: under bilinear filtering and mips, repeat bleeds the opposite edge into a sky's horizon, a sign's border or the `h_b2_yajirushi` arrow. A first cut wrote every in-range axis as repeat and turned about 800 BLiNX 1 and 57 M13 clamp samplers into repeat; the review caught it. What still differs per axis is counted as unsupported: 2 textures in M13, 14 over the 24 BLiNX 1 stages (0 to 2 per stage).
- Mirror: Godot's 3D materials have no mirrored repeat, so a mirrored axis whose UVs leave [0, 1] imports as repeat. It is counted under "approximated" (BLiNX 1: 3 textures each in MAP21 to MAP23, 1 in MAP61; none in M13).
- Report: each stage writes `stages/<name>/report.json` (trees, counts, missing textures, unsupported, approximated), and `<out>/report.txt` gathers every stage's lines as printed.

## BLiNX 2

- Same parser with `vertex_header = 8`, radians, `texname_size = 36`; textures from `media.ipk` (`dds\<name>.dds`).
- Stage roots, found by structure and checked against S4's draws (`runs/engine-bridge/s4/`, M11 only):
  1. **Stage map table** at `.data` `0x40d180`: 12-byte rows `(X, root, texlist)` indexed by area id (read by `sub_000E2180`/`sub_000E21C0`; the root lands in `0xB87180`, the texlist goes to `sub_37010`). `X` is never drawn (collision). A parallel table from `0x40d454` has `X = 0` rows for M14, M24 and M44.
  2. **Area part lists**: area records (`0x4b2798`, stride `0xe4`, from the stage table at `0x4ac358`) hold two list pointers side by side at `+0xdc` and `+0xe0`. Each list holds 7-dword part records `(0, root, float, texlist, kind, a, b)` and ends at a zero root. S4 draws every part of the first list with `C = diag(1, 1, -1)` (the model mirrored in Y, the float being twice the plane's height): it is the reflection, left out. The second list's parts draw like the table's roots.
  3. Part lists no area record points at (`.data` `0x404d..0x4087`, kind 0) are gimmicks placed at runtime (S4 draws them with their own translations): left out, as are enemies and other runtime objects.
- Each root draws with its own texlist, so `texlist` takes one VA per root.
- S4 check on M11: for every drawn model, `C = M_s4 * W^-1` (W from the tree) is the same `diag(1, -1, -1)` for all 9 kept trees (3 table rows, 6 parts). That C is constant across models, so it is the game's view convention, not the world's up axis: the world is already Y-up. A first cut applied it as `up = "-y"` and every stage imported upside down (M11's horizontal faces 0% up-facing; 100% without the turn); the CLI test `test_floors_face_up` covers it. The reflection and gimmick roots each give another C.
- Some strip chunks (strip flags 2 and 3, the M11 water and sky parts among them) have a size field that undercounts the strip, sized as if each point were 4 bytes. The game walks a strip by its counts, and the next chunk starts where they end, so the parser does the same.
- Code-drawn roots: the per-stage draw `sub_000E61A0` draws roots the tables do not hold, each with its own texlist (`MEM32(0xA723C8)`), and `sub_000E2CD0` bakes some more. M13's are in `game.toml`: the glass floor over the mirror pit (`0x018F4858`, texlist `0x018F42C4`; without it the start area is a black void), the lamp glows (`0x018F9450`), the sky (`0x018FEA0C`) and the grass `sub_000E6FA0` draws (`0x018F6128`). The black untextured material under that floor is the pit's own floor (y = -70), unlit black by design; the pit holds the mirrored lamps and pillars the glass floor shows. M11 already had its code-drawn roots. Left out in M13: the sky's second draw, mirrored in Y by `sub_0003FF50(1, -1, 1)` (the sky's lower half below the horizon), and the two 4,600-wide planes `0x01903248` and `0x019069E0` (`sub_0021A830`), which take a texlist set at runtime. Also left out: root `0x018F426C` (texlist `0x018E3528`), which `sub_000E2CD0` bakes and `sub_000E3C80` handles but no draw function draws (maybe collision). Other stages have code-drawn roots not yet listed (M23, M41, M43, M44, M51, M53, M54, M61, M64): a follow-up.
- Not covered: the second list in some area records is in BSS (filled at runtime: M34, M44, M111 and others); those stages have only their table rows. MSHIP has no rows. Areas of one section share world space, so a section is one stage.

## Verification

- pytest on synthetic chunk bytes and node trees built in the test (no game data in the repo or tests), covering both struct variants, the angle conversion and the glTF writer (valid accessors, buffer views, bounds).
- On the owner's dump (local, never committed): every listed stage of both games imports with `--import` and Godot logs no errors; per-stage mesh, triangle and material counts in the verb's summary; MAP11 gives 310 meshes, 51,146 triangles and 62 materials (S2 counted 64: the writer merges two duplicate `h_wall_18a0000` materials).
- Floors face up: in every stage most horizontal area faces +Y, with the triangle winding agreeing with the vertex normals. In BLiNX 1 MAP11 only 29% does, because the sky dome (`h_sora`, 1,240 wide and 735 high) faces inward and outweighs the floors; without it, the floors are all up-facing.
- One screenshot per game from the Godot project, posted on the tracker item only.

## Not in this change

Characters and skinning (scattered when exported per node, S2; live posing is slice 1c), motions, placements, collision, lighting, fog, view-dependent environment maps (the static approximation above stands in), additive blending (blend 0x21: the M13 glows import as alpha blend), the wizard, any Godot export.

## In-game comparison

The before and after shots come from a software renderer over the glTF (`runs/extract-fidelity/scripts/render.py`, with `GODOT=1` applying Godot's one-repeat-flag rule), since headless Godot cannot render and no visible window was allowed. No in-game M13 capture exists: the S4 dumps and goldens cover M11 only, and M13 needs a save at the Tom Tom gang stage. The comparison with the game is a follow-up.
