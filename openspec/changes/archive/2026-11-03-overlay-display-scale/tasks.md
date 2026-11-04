## 1. Toolkit (`fix/ovl-display-scale` off `posix-host/portability`)

- [x] 1.1 Kernel: display floor, Deck marking, lazy probe hook, fit rule in `nv2a_ovl_ui_scale`, bake lines
- [x] 1.2 `enhance_display.c`: the Win32 and SDL3 probe; `overlay.ui_fit` key, menu row, env rows for `ui_scale` and `ui_fit`
- [x] 1.3 Pad glyphs in small text at the body size; compact panel width floor
- [x] 1.4 ctests: `tests/overlay` `test_display_scale`, `tests/enhance_menu_layout` Deck case, `tests/enhance_menu` Deck shots and Render pin
- [x] 1.8 Review fixes: SDL probe waits for the presenter's video (`nv2a_overlay_display_ready`), Windows DPI note, docs
- [x] 1.7 Deck by SMBIOS names too (`nv2a_overlay_is_deck_board`): the first Deck run, Desktop Mode, had no `SteamDeck`
- [x] 1.5 `docs/runtime/config.md`: keys, Overlay scale section, restart table
- [x] 1.9 Rework: atlas bound at `OVL_UI_SCALE_MAX` with a `test_fit` case per largest bake; `SteamDeck=0` and primary-display notes in config.md
- [x] 1.6 Gates: Mac `tests/posix_ctest.sh` 0 FAIL; Windows build on the PC (plus its D3D11 golden)

## 2. cat (`fix/ovl-display-scale`)

- [x] 2.1 This spec; `docs/env.md` rows, counts and toolkit keys table

## 3. Verify

- [x] 3.1 Deck hand check: the menu at the new scale under Proton, screenshot on the tracker item
