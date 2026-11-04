## 1. Baseline

- [ ] 1.1 Add the synthetic fixtures (wrap cut, in-range wrap choice, mirrored repeat, additive, `texture_alpha`, env-map UVs, collision on and off with a `collision_skip` class, transform, backdrop, `up = "-y"`, `textured_colour = "white"`) and record the sha256 of every file today's `extract` writes for them
- [ ] 1.2 On the owner's dump, keep today's `extract` output for every BLiNX 1 and 2 stage under `runs/cli-namespaces/` (local only)

## 2. Neutral writer and engines

- [ ] 2.1 Add `Profile` and the `Engine` protocol (`api = 1`) in `assets/engines/`
- [ ] 2.2 Make the wrap choice, the mesh cut, the collision suffix and the report wording read the profile; move the `SUPPORTED_ADD` text out of `ninja.py` into the wording
- [ ] 2.3 Move the Godot pin, project texts, `write_project` and `import_project` into `engines/godot.py` behind `project`, `check` and `open`
- [ ] 2.4 Add `engines/none.py`: per-axis wraps and no cut, `xbr_collision` extras, neutral wording, structural glTF check, refuse a dir holding `project.godot` (the message gives `rm -r DIR` and `--out`)
- [ ] 2.5 Load adapters: built-ins, then `[assets.engines.NAME] module`, then the `xbr.engines` entry points; error on a duplicate name or a wrong `api`
- [ ] 2.6 Check the fixtures match the 1.1 sha256s with `--engine godot`, after normalising only the three verb lines (glTF generator, `project.godot` comment, `.gitignore` comment)

## 3. Namespaces

- [ ] 3.1 `assets export`, `check`, `open`, `list`, `scan`, with the default out `dist/assets` (a one-time note when an old `dist/extract` exists); reserve `textures`, `placements`, `characters`, `import`
- [ ] 3.2 `assets hud-pack` (from `enhance hud`); label `assets hud-pack` at `TIMING_LABEL`, `TIMING_HUD` and `resources.hud_need()`, with `timings.json` readers taking both labels
- [ ] 3.3 `mod hooks` (keeps `begin_stage("hooks")` and the stage passthrough) and `mod hud-map`
- [ ] 3.4 `symbols.problems()` returning a list (`load()` raises from it); `mod symbols check|show [--json]`
- [ ] 3.5 `mod new NAME` writes `src/NAME_mod.c` and `.h` from a game-neutral template; prints the include and source lines, the registration, and the note to grow the mods array
- [ ] 3.6 `mod list [--json] [--exe PATH]` through `RECOMP_MODS_DESCRIBE`
- [ ] 3.7 `helptext.py` lists the new verbs only

## 4. Manifest and compatibility

- [ ] 4.1 New tables `[assets]` (+ `engine`, `engines` as a `STRMAPS` key), `[assets.hud]`, `[mod]`, `[mod.hud]`; readers use the new names
- [ ] 4.1a `OPTIONAL` keyed on the full table name; `has_assets(m)` (own keys besides `hud` and `engines`) replaces the presence checks in `validate()`, `_derive` and `extract/cli.config()`; `[mod.hud]` optional on its own
- [ ] 4.2 Map the old tables with one warning each; error when both forms exist
- [ ] 4.3 Hidden verb aliases in `main()` with a one-line stderr note
- [ ] 4.4 Keep the `"game.toml [mods]"` label in `gen_inputs()` verbatim, with a comment saying why; test `gen_key()` equal and `gen_stale_reasons() == []` across `[mods]` and `[mod]`

## 5. Wizard

- [ ] 5.1 Call `assets hud-pack`; map both stage labels; `go test` and `wizard/check.sh`

## 6. Tests and docs

- [ ] 6.1 Tests from design section 9 (KUF-shaped manifests included; the `mod new` compile test through `XBOXRECOMP_DIR`); `uv run pytest tests`, ruff
- [ ] 6.2 `diff -r` against 1.2 on the owner's dump for every stage; only the three verb lines differ
- [ ] 6.3 Update `README.md`, `docs/commands.md`, `manifest.md`, `bundle.md`, `wizard.md`, `symbols.md`, `CHANGELOG`; add `docs/engines.md`
- [ ] 6.4 Before archiving: if `engine-extract` is archived by then, add a MODIFIED delta for its extract requirement (verb `assets export`, table `[assets]`, out `dist/assets`); otherwise edit that change's spec in place
  - Note (tidy, 2026-11-03): `engine-extract` is archived, so this is due as a MODIFIED delta against `openspec/specs/engine-extract/spec.md`.

## 7. Games (with each game's pin move)

- [ ] 7.1 BLiNX 2: the four tables, README, `docs/packaging.md`, `docs/env.md`, `config/hud.toml`; `scripts/test_hud_table.py:65` (and its `mod hud-map` call), `test_crystals.py:331`, `test_entities.py:1320`, `test_shop.py:871` read `["mod"]`; `uv run pytest scripts`
- [ ] 7.2 BLiNX 1: `[extract]` to `[assets]`, and its comment's `dist/extract/` to `dist/assets/`
- [ ] 7.3 KUF: `[enhance.hud]` to `[assets.hud]`, README
- [ ] 7.4 Burnout 3, SSX 3, Spartan, JSRF: pin only; Auto Modellista uses the new tables when it gets a `game.toml`
- [ ] 7.5 At the push round: `GAMES=all sh notes/build-all.sh` shows every game building

## 8. Next round

- [ ] 8.1 Remove the verb aliases and the old-table mapping
