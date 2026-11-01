Worktree `wt/shop-api/cat`, branch `feat/shop-api` off
cat main f2b9ef6. Runs under `xbox-recomp/runs/shop-api/` (frames never on
the tracker). PC jobs under `D:\bench\.bench-lock`, logged in
`notes/benches.md`.

## 1. Static map

- [x] 1.1 The catalogue's records and categories; the shop's state,
  lineup and buy paths; owned weapons in the status struct.
- [x] 1.2 The weapon stats: gun table, shot table, the fire function's
  speed and life, the fire gate's interval.
- [x] 1.3 Names into `config/symbols.toml`.

## 2. cat: the API and the mod

- [x] 2.1 `src/shop_api_logic.{c,h}`: pure C over a memory view: table
  checks, the game's values, effective values and their write-back,
  restore, shot scaling over a pool diff, the fire timer, owned weapons.
- [x] 2.2 `src/shop_api.{c,h}`: overrides (D1), off (D2), the fire hook
  (D3), threads and statuses (D4).
- [x] 2.3 `src/shop_mod.c`: settings, Status row, the proof driver (D7,
  D9); `src/main.c` mod table, `CMakeLists.txt`.
- [x] 2.4 `game.toml`: hook slot `0x001A0260`, `enhance_stock`
  `"mods.shop.enable" = "off"`; `./blinx2 analyze && ./blinx2 recomp`;
  `config/hook_functions.json`.
- [x] 2.5 Env rows (`recomp_env_game.h`, `docs/env.md`), commented keys in
  `packaging/config.default.toml`.
- [x] 2.6 `scripts/test_shop.py`.
- [x] 2.7 The story shop's price lists (D10, found by the first price
  run): read, override, `price_pct`, restore; symbols and tests.
- [x] 2.8 Review fixes: owned ammo above the gun table's capacity goes
  down to it when the tables are lowered or restored (`shopl_clamp_owned`,
  guest-thread `on_frame`, only after the mod wrote); values below -1 and
  an interval above 100 % are `SHOP_RANGE`; synthetic tables in the test.

## 3. Gates

- [x] 3.1 `uv run pytest scripts`, `uv run ruff check . && uv run ruff
  format --check .`.
- [x] 3.2 PC build; Windows golden with the mod off (`blinx2 bench golden`,
  `BENCH_HOST_OS=windows`).
- [x] 3.3 Live proof on PC D3D11 (D9): a price change in the shop, a
  weapon stat change taking effect. Price (b030561, run 20261031-180807,
  `price_pct=50`): the Arms page shows TS-2000 200 G and TS-2100 300 G
  (stock 400 and 600). Stat (runs 20261031-182803 on, 183221 stock):
  gun 16's shots at speed 16.0 against 8.0, its shot type's power 60
  against 30. The interval was not seen live: the driver fires with the
  timer long past the threshold, which D3 leaves alone (unit tested).

## 4. Follow-ups

- [ ] 4.1 The interval live: a shot pattern that fires before the timer
  passes the threshold, to see `interval_pct` in play.
- [ ] 4.2 Restore while the story shop is open: the visit keeps the
  lowered prices until it closes (by design; check the next visit is stock).
- [ ] 4.3 A save made with the mod on, loaded with it off: owned ammo
  clamps; check nothing else carries the changed stats.
- [ ] 4.4 The HUD live after the ammo clamp (an ammo_pct=500 buy, then
  off).

## 5. Hand-back

- [ ] 5.1 `pt review ITEM`; the orchestrator runs the review and
  the merge.
