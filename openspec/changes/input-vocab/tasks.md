## 1. Toolkit
- [x] 1.1 `input_names.{c,h}` on upstream's `InputControl` and `input_map.c`; extras `numpadenter`, `wheelup`, `wheeldown`; host buttons via `SourceName`.
- [x] 1.2 `enhance_input.c`, `enhance_actions.c`, `keyboard.c`, `kbm_script.c`, `mouse_sdl.c` on the new names; controls buffer 512 bytes for the longer list.
- [x] 1.3 `keyboard_sdl.c`: `SDLK_PAUSE`, `SDLK_CAPSLOCK`.
- [x] 1.4 `pad_map.c` host column and README Control column; README table regenerated (`PAD_MAP_README_OUT`).
- [x] 1.5 Tests: `input_bindings` (round trip, upstream names, old names refused), `enhance_cfg`, `input_actions`, `input_keyboard_sdl`, `pad_map` (every host token an upstream source).
- [x] 1.6 Docs: `src/input/README.md`, `docs/runtime/config.md`.

## 2. Games
- [x] 2.1 cat `packaging/config.default.toml`, `docs/input.md` (Old names table), `docs/env.md`, `scripts/test_config_default.py` (upstream names only).
- [x] 2.2 CHANGELOG breaking-change entries in cat, b3 and skates.
- [x] 2.3 This change's delta to `openspec/specs/input/spec.md`.

## 3. Gates
- [x] 3.1 Mac build, `tests/posix_ctest.sh` 0 FAIL apart from guest_cpu "spin: the macro saw the waiter" (flake, load-dependent, passes on rerun).
- [x] 3.2 cat `uv run pytest scripts`, ruff.
- [x] 3.3 Game builds: cat, b3, skates (b3 and skates `--system-tools`; b3 `--stale-gen-ok`, its gen was stale before this change).
- [x] 3.4 Metal goldens: cat attract/stage1/story; skates title, garage, dogenzaka (pad-scripted). b3 has no goldens. garage-load is a wall-time flake (one FAIL, pass on rerun).
- [x] 3.5 Deck goldens via `bench golden` (borderless): cat attract/stage1/story pass; skates title and garage pass, dogenzaka passed all EXACT in one of three runs, the others hit the Deck flip-timing flake also seen on main.

## 4. On merge
- [ ] 4.1 Bump cat's `game.toml` toolkit pin (and b3, skates pins) to the toolkit squash.
- [ ] 4.2 Sync the delta into `openspec/specs/input/spec.md` and archive.
