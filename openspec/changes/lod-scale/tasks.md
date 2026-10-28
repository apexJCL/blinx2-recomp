Worktree `wt/lod-mod/cat` (`feat/lod-mod` off `main`). No toolkit change.
Runs under `xbox-recomp/runs/lod-mod/`. Mac jobs under
`lockf -t 3600 ~/.recomp-mac.lock`, `SDL_AUDIODRIVER=dummy`; the Deck through
`./blinx2 bench` (`BENCH_DIR=lod-mod-bench`).

## 1. Mod

- [x] 1.1 `src/lod_table.{c,h}`: the stock table, the threshold formula and
  the stock check, pure C.
- [x] 1.2 `src/lod_scale.{c,h}`: the descriptor (D1), `on_frame`,
  `on_enable`, the guards (D5) and the logs (D6); stock at
  shutdown.
- [x] 1.3 `src/main.c` mod table, `CMakeLists.txt`.
- [x] 1.4 Env rows `RECOMP_LOD`, `RECOMP_LOD_FOLLOW_SCALE`,
  `RECOMP_LOD_DISTANCE` (`recomp_env_game.h`, `docs/env.md`), commented keys
  in `packaging/config.default.toml`, `game.toml` `enhance_stock`.
- [x] 1.5 `scripts/test_lod_scale.py`: the formula (1x/2x/3x, distance,
  follow off, the floor of 1), the stock check, the env and doc rows, the
  golden key.

- [x] 1.6 Review fixes: the guards as pure C (`lod_step`) with
  tests on a simulated table; the shutdown comment, `s_on` left to the guest
  thread; the mod table skips a NULL entry; the scale caveat in D2.

## 2. Gates

- [x] 2.1 Mac build; `uv run pytest scripts`; ruff.
- [x] 2.2 Metal golden, mod off.
- [x] 2.3 Metal A/B, Sweepers hub (`runs/lod-spike/walk.txt` route), 2x and
  3x, mod off and on: batches per flip, flips/s, a crop.
- [x] 2.4a The descriptor in `RECOMP_MODS_DESCRIBE=json`; with
  `menu.enabled` on, the mod inits dormant and leaves the table stock.
- [ ] 2.4b Owed, hands-on by the user: on the Mods page, a live change of
  `render.scale` and of the switch (the headless runs cannot open the menu).
  Not done before the merge.
- [x] 2.5 Deck under Proton, 2x, mod off and on: batches and frame ms
  (25% rule).
- [x] 2.6 Deck D3D11 golden (`blinx2 bench golden`). Owed: the native Windows golden at
  the PC's next Windows boot.

Note (2.5): `@story-hub` ends on the Challenge intro, whose camera stops at a
different place from run to run (stock table too: a mod-on run at distance
0.5, which writes nothing, gave a third view), so the A/B compares the team
editor segment (flips ~2000-2620), which is the same in every run.
