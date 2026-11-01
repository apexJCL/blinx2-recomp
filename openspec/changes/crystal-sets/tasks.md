Worktree: cat `wt/crystal-sets/cat` (`feat/crystal-sets`
off cat main f2b9ef6). Runs under `xbox-recomp/runs/crystal-sets/`. PC jobs
under `D:\bench\.bench-lock`, logged in `notes/benches.md`. Material:
`spike/crystals` f696490 (symbols) and d709fe6 (`src/crystal_spike.c`).

## 1. Spec and symbols

- [x] 1.1 This change: proposal, design, tasks, spec.
- [x] 1.2 The f696490 symbols into `config/symbols.toml`.

## 2. Hook slot

- [x] 2.1 `0x0008BFD0` in `game.toml` `[mods] hook_functions`; regenerate
  with `./blinx2 analyze && ./blinx2 recomp`.

## 3. The mod

- [x] 3.1 `src/crystals_logic.{c,h}`: the row, prepare, detect, push.
- [x] 3.2 `src/crystals_mod.{c,h}`: hooks (D1), HUD (D3), modes (D4),
  settings and Status row (D5), proof driver (D6).
- [x] 3.3 Registration in `src/main.c` before the HUD mod; `CMakeLists.txt`.
- [x] 3.4 Env rows `RECOMP_CRYSTALS`, `RECOMP_CRYSTALS_PROOF`;
  `docs/env.md`; `packaging/config.default.toml` if the mods are listed
  there; `game.toml` `[golden] enhance_stock`.
- [x] 3.5 `scripts/test_crystals.py`.

## 4. Gates

- [x] 4.1 `uv run pytest scripts`, `uv run ruff check . && uv run ruff
  format --check .`.
- [x] 4.2 Windows build on the PC; Windows golden with the mod off
  (attract, stage1, story).
- [x] 4.3 Live proof on PC D3D11 with the mod on (D6), runs under
  `runs/crystal-sets/`.
