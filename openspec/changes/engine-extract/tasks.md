Implementation goes in an `xboxrecomp-cli` worktree off `main`, plus a cat and a blinx worktree for the `game.toml` tables. Spike code under `runs/engine-bridge/` is a reference, not a source to copy blindly.

## 1. CLI: parser and writer

- [x] 1.1 `extract/image.py`: section bytes by name, VA to offset (reuse an existing CLI XBE reader if one fits).
- [x] 1.2 `extract/ninja.py`: node tree and chunk model parse with the `[extract]` switches; unsupported chunks counted, not fatal.
- [x] 1.3 `extract/gltf.py`: glTF 2.0 writer (meshes, nodes, materials, samplers, PNG textures).
- [x] 1.4 `extract/godot.py`: `project.godot` and one `.tscn` per stage; `--import` through the pinned Godot.
- [x] 1.5 Godot pin (version, URL, sha256 per host) and download into user space, as the other CLI toolchains do.
- [x] 1.6 The verb, `--list`, a per-stage summary, and the `[extract]` table read from `game.toml`; README entry in the CLI's style.

## 2. BLiNX 1

- [x] 2.1 `[extract]` in `blinx/game.toml` (all MAP sections that are stages); output dir gitignored.
- [x] 2.2 Every listed stage imports headless with no Godot errors; MAP11 gives S2's 310 meshes and 51,146 triangles, and 62 materials (S2's 64 less two duplicate `h_wall_18a0000` materials the writer merges).

## 3. BLiNX 2

- [x] 3.1 Find the stage roots by structure; record the method and the roots in `design.md`.
- [x] 3.2 `[extract]` in `cat/game.toml`, textures from `media.ipk`; output dir gitignored.
- [x] 3.3 Every listed stage imports headless with no Godot errors, Y-up with no turn (the first cut's `up = "-y"` came from S4's view-matrix flip and turned every stage upside down; dropped after review).
- [x] 3.4 Floors face up: CLI test `test_floors_face_up`; on the dump, M11 is 100% up-facing (BLiNX 1 MAP11 29%, its inward sky dome outweighing floors that are all up-facing).

## 4. Verification and docs

- [x] 4.1 `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .` in `xboxrecomp-cli/`; `uv run pytest scripts` and ruff in cat if cat scripts change.
- [x] 4.2 No game bytes in any commit or test (grep the diff for section data, check fixture sizes).
- [ ] 4.3 Screenshots of one stage per game in Godot, on the tracker item only.
- [ ] 4.4 Review before merge; fixes go back to the implementing agent.
- [ ] 4.5 After merge: notes to `notes/engine-extract/`, worktrees removed through `benchdb`, branches kept; the `[cli]` pin move rides the next push round with `notes/build-all.sh`.
