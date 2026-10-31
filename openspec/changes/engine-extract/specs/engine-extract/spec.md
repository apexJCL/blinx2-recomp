## ADDED Requirements

### Requirement: Extract stages to a Godot project
`xbr extract` SHALL read the stages listed in the game's `[extract]` table from the owner's dump and write, per stage, a glTF 2.0 file with its textures and a Godot scene that instances it, under a `project.godot` in the output directory. It SHALL print per stage the meshes, triangles, materials, unsupported chunks and approximations, and SHALL write the same per stage to `stages/<name>/report.json` and for every stage to `report.txt` in the output directory. With `--import` it SHALL run the pinned Godot headless to import the project and fail when Godot logs an error.

#### Scenario: BLiNX 1 MAP11
- **WHEN** `blinx1 extract --stage map11 --import` runs on the owner's dump
- **THEN** the summary shows 310 meshes, 51,146 triangles and 62 materials (S2 counted 64; the writer merges two duplicate `h_wall_18a0000` materials), and the import logs no errors

#### Scenario: BLiNX 2 stage
- **WHEN** `blinx2 extract --import` runs on the owner's dump
- **THEN** every listed stage is written and imported with no Godot errors, Y-up with no turn (the S4 `diag(1, -1, -1)` is the game's view convention, not its world's up axis)

#### Scenario: Report beside the project
- **WHEN** `extract` writes a stage
- **THEN** `stages/<name>/report.json` holds its trees, counts, missing textures, unsupported and approximated items, and `report.txt` holds the lines the run printed for every stage in the output directory

#### Scenario: Code-drawn stage geometry
- **WHEN** `blinx2 extract --stage M13` runs on the owner's dump
- **THEN** the glass floor over the start area's mirror pit is present, drawn with alpha blending

#### Scenario: Godot sees the wraps the game meant
- **WHEN** a texture's two wraps differ and the UVs on one axis stay inside [0, 1]
- **THEN** that axis is written with the other axis's wrap (clamp when both stay inside), so Godot's single repeat flag matches the axis that tiles, a texture whose wraps agree keeps them (clamp stays clamp: repeat would bleed the opposite edge in), and a texture whose wraps still differ per axis is counted as unsupported

#### Scenario: Environment-mapped strips
- **WHEN** a strip has the environment-map flag and no UVs
- **THEN** it keeps its texture, with UVs from its model-space normals, and is counted as approximated

#### Scenario: Floors face up
- **WHEN** a stage whose floors have +Y normals in the data is extracted with the default `up`
- **THEN** its horizontal faces, by triangle winding in world space, face +Y in the glTF

### Requirement: Game constants live in game.toml
The parser SHALL take every per-game value (vertex-list header size, texture-name entry size, texture source, section names, stage roots) from `[extract]`; the CLI SHALL hold no game constant. A missing `[extract]` table SHALL make the verb exit with a message naming it.

#### Scenario: Two games, one parser
- **WHEN** the same parser runs with `vertex_header = 16, texname_size = 32` and with `vertex_header = 8, texname_size = 36` on synthetic test data
- **THEN** both produce the expected meshes

### Requirement: Output stays local
The verb SHALL write only under its output directory, which defaults to a gitignored directory of the game repo, and SHALL never run a Godot export. No test or fixture SHALL contain bytes from a game.

#### Scenario: No export
- **WHEN** `extract --import` finishes
- **THEN** the output holds no `.pck` or exported binary, and `git status` in the game repo shows no new tracked or untracked files outside ignored paths
