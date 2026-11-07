## 1. Toolkit

- [x] 1.1 `mod.h`: `XBOX_SET_LINK`, `XBOX_MOD_DESC_VERSION` 2, the field rules (D1, D2).
- [x] 1.2 `enhance_menu`: look up a toolkit item by key; read and set its value as a number; the link row on the mod's page is the item's slot (D3).
- [x] 1.3 `mod.c`: validation, no resolution, `setting` and `setting_set` through the item, source `link` (D4). `mod_describe.c`: kind `link`.
- [x] 1.4 ctest: the link row and the Controls row share one value and one saved key; refusals; `api->setting` follows the item.
- [x] 1.5 `docs/runtime/config.md`: the kind.

## 2. Cat

- [x] 2.1 `src/fdm_mod.c`: the `square_left` row, the Status hint and the About text (D5).
- [x] 2.2 `scripts/test_fdm.py`: the row, the hint.

## 3. Gates

- [x] 3.1 Toolkit Mac build, `tests/posix_ctest.sh` 0 FAIL.
- [x] 3.2 Cat `uv run pytest scripts`, ruff.
- [x] 3.3 Cat Mac build against the toolkit branch; Metal golden with mods off.
- [x] 3.4 Screenshot: the FDM page with the row on, and Controls > Sticks agreeing.
