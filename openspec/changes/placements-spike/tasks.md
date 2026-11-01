## 1. Findings

- [x] 1.1 Find the per-stage placement tables, their loaders and the stage index (`stage_current` 0xB87168)
- [x] 1.2 Decode the record layout (class word, position, rotation) and the layer rule (`stage + 0/1/4`)
- [x] 1.3 Find what records point at: enemy variant tables (types 1–5, 8), gimmick 0x52, the ambient gull
- [x] 1.4 Classify models as skinned or rigid, with notes for the tracker item
- [x] 1.5 Find the placements' frame: the tree data turned a half turn about X, checked on M21's collision floors and in Godot

## 2. Prototype (xboxrecomp-cli, branch `spike/placements`)

- [x] 2.1 Manifest: `[extract] placement_world`, `[[extract.placement_set]]`, `[[extract.placement_model]]`, `[[extract.stage]] placements`, with checks
- [x] 2.2 `extract/placements.py`: read, resolve, draw rigid models, use markers otherwise, write `placements.json`
- [x] 2.3 `extract/gltf.py`: `add_nodes` and `marker`; `extract/godot.py` composes the stage scene's layers
- [x] 2.4 `xbr extract --placements` (opt-in); `--list` shows the stage index
- [x] 2.5 Tests (synthetic image) and docs (`docs/manifest.md`, `docs/commands.md`)
- [x] 2.6 cat `game.toml`: the six sets, the known models and `placements = 5` on M21
- [x] 2.7 Export M21 with `--collision --placements --import`; Godot imports with no errors
- [x] 2.8 Review fixes: non-finite records unreadable, per-layer read errors in `placements.json`, a `variants` bound, `pos_at`/`rot_at` required, more loader checks, the `placement_set` rename, set names that read as Godot import hints refused

## 3. Gates

- [x] 3.1 CLI: `uv run pytest tests`, ruff check and format, `scripts/audit-public.sh`
- [x] 3.2 cat: `uv run pytest scripts`, ruff check and format

## 4. Follow-ups (not in this spike)

- [ ] 4.1 Skinned model export: weighted vertices, cached polygon lists, unknown chunk types, glTF skins
- [x] 4.2 Verify the rotation sign and order: X first, right-handed, radians; the game's half turn sits outside the rotation, so the CLI mirrors the Y and Z angles (design: *The placements' frame*; fix in the CLI request)
- [x] 4.3 Resolve the remaining gimmick classes (doors: class 0x13), the item models and enemy type 0x10: 168 `placement_model` rows; markers 2854 → 1002, mostly emitters (design: *Models and tables*)
- [x] 4.4 Find the reader of table 0x491DF8: `stage_item_setup` spawns it as the collectibles (time stones, coins, medals, Tom Tom medals), now the `collectible` set; 0x491D08 is the two-player item set it loads when 0xB22E3C is 2 (design: *Models and tables*)
- [x] 4.5 Model the enemy index remap (`idx % 5 == 3` → `idx - 2`): `enemy = [-2]` in the boss stages' `placement_layers` (4.10); the tracker item checked all six `s % 5 == 3` stages (M14, M24, M34, M44, M54, M64) carry it
- [x] 4.6 Map every stage to its `stage_current` index and its layer rule; `placements` on the nine first stages, emitter2 gains layer 4; every stage exported with hand-set layers and imported with no errors (design: *Every stage*)
- [x] 4.10 CLI: `[[extract.stage]] placement_layers` per stage and the half-turn move (design: *Per-stage layers*), then `placements` on the twelve other stages; all 21 stages exported from `game.toml` with the counts of *Every stage* and imported with no errors
- [ ] 4.11 Known gaps of the all-stage export:
  - CLI: `godot.write_project` takes the first `game.toml` stage as the main scene even with `--stage` (`extract/godot.py:294`), so the M21 main scene of the export was set by hand;
  - CLI: `report.txt` is rebuilt from every stage under the output directory (`extract/cli.py:201`), not just the stages of the run;
  - M44's `[16]` and M64's `[26]` boss lists sit far off the exported geometry, and M64 has no `collision` key;
  - M61's 31 class-0x0E enemies sit at the origin.
- [x] 4.7 Name the loaders in `symbols.toml`; gen does not read the file, so it is unchanged
- [ ] 4.8 Decode per-class record fields from the raw bytes (spawn rules, paths, door links)
- [ ] 4.9 Make the class dword's byte positions (class, variant, flags) manifest keys when a game's records differ; today the CLI reads BLiNX 2's shape, documented in `docs/manifest.md`
