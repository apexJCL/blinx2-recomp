## 1. Spec

- [x] 1.1 Proposal, design and the `crystal-sets` delta (name, heart icon)

## 2. Code

- [x] 2.1 `cry_pickup` begin, end and undo and `cry_quad` in `crystals_logic.{c,h}` (D2, D3)
- [x] 2.2 `crystals_mod.c` rewritten over them; name, label and summary (D1)
- [x] 2.3 Heart icon from the gauge's texture `0x418848` frame 3 (D3)
- [x] 2.4 Proof moved to `crystals_proof.c`, `crystals_internal.h`; `kill:f`, `hp`, `hearts` (D4)
- [x] 2.5 `docs/env.md`, `recomp_env_game.h`, `packaging/config.default.toml`, CHANGELOG

## 3. Tests

- [x] 3.1 `scripts/test_crystals.py` over the new API (Tests)
- [x] 3.2 `uv run pytest scripts`, `ruff check`, `ruff format --check`

## 4. Live

- [x] 4.1 PC build and the golden with the mod off (D3D11)
- [x] 4.2 Heart crystal in the row, captured under `runs/crystals-rewrite/` (D5)
- [x] 4.3 Death and retry with a partial row (D5)
- [x] 4.4 Stage-end clear (D5)

## 5. Review fixes

- [x] 5.1 Delta spec: a death and retry keep the row as at the death; the checkpoint load untested
- [x] 5.2 The heart check reads frame 3's handle, not the static descriptor
- [x] 5.3 docs/env.md: the `entities_proof` row back as it was
- [x] 5.4 The row's hearts, at most two, in the RETRY count byte: the stock lit hearts show them (D3)
- [x] 5.5 `on_enable` settles before its repeat check (`cry_settle`)
- [x] 5.6 Tests: the icon choice with its fallback, the settle, the hearts byte
- [x] 5.7 The proof's header: it runs with the mod on or off
- [x] 5.8 PC build, the golden with the mod off, the heart proof with the lit hearts
