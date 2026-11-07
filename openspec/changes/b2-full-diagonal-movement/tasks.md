## 1. Research

- [x] 1.1 f(L) in the walk (design §1): max × (min(L, 1) - 0.4) / 0.6, the table at 0x450A84; f(sqrt 2) / f(1) unclamped = 1.690.
- [x] 1.2 Every user of the clamped length, with addresses, and which sees the unclamped value (design §2, D1).
- [x] 1.3 The mechanism (design §3, D2): pow pre filtered on 0x17C8FC, table restore in ent_player_update's pre and post.

## 2. Mod

- [x] 2.1 `src/fdm_mod.c`, `src/fdm_mod.h`, `src/fdm_logic.h`; registered in `src/main.c`, built in `CMakeLists.txt`.
- [x] 2.2 Hook slots `0x002D675C` (st0) and `0x00176150` (no_st0) in `game.toml`; `blinx2 analyze`, `blinx2 recomp`.
- [x] 2.3 `RECOMP_FDM` row in `src/env/recomp_env_game.h`, `docs/env.md` rows, `[golden] enhance_stock`, `docs/reset-statics.md`.
- [x] 2.4 Menu (D3): the switch's short help (the tooltip, at most 159 bytes), the About text (both plain and ASCII only, the user 2026-11-05), and the live Status row with the Square left stick hint.
- [x] 2.5 `scripts/test_fdm.py`.
- [x] 2.6 Speed readout (design §7, D4): `src/speed_mod.c`, `src/speed_mod.h`, `src/speed_logic.h`, `RECOMP_SPEED_READOUT`, `docs/env.md` and `docs/reset-statics.md` rows, `enhance_stock`, `scripts/test_speed.py`. Metal shots of the card on a keyboard W+A corner: 1.00 with fdm off, 1.69 with it on (`runs/b2-fdm/shots/speed-*`).

## 3. Gates

- [x] 3.1 Mod on, diagonal ratio on stage 1-1 (design §6): scripted corner 1.691 and keyboard W+A 1.691 (Mac, Metal); a vpad round pad on the Deck (Proton D3D11), 1.686 with Square left stick and 0.994 without it; mod off 1.004.
- [x] 3.2 Mod off: Metal goldens (`blinx2 golden`): attract, stage1 and story pass on 636b56df and on ce428851 with toolkit 23fccfda (`runs/b2-fdm/golden-metal.log`, `golden-metal2.log`).
- [x] 3.3 Mod off: D3D11 goldens on the Deck (`blinx2 bench golden`, exe built on the PC): attract, stage1 and story pass (`runs/b2-fdm/bench-golden.log`, `bench-golden2.log`). Proton runs with the mod on: sq-on2 and sq-off1 (3.1).
- [x] 3.4 `uv run pytest scripts` (353 passed, 24 skipped), `uv run ruff check .`, `uv run ruff format --check .`.
- [x] 3.5 Screenshots in `runs/b2-fdm/shots/`: the Mods list, the About and Enabled, the hint (square off), the ready line (square on), and the switch tooltip on the Mods list row and the Enabled row (toolkit 23fccfda).

## 4. Follow-up (not in this change)

- [ ] 4.1 A button on the mod's page that turns Square left stick on and saves it: needs a toolkit API to set another menu item by key.
