## 1. Evidence
- [x] 1.1 Metal crt-lottes under `internal`, before the fix (frame-sized shot, upscaled to 1280x800)
- [x] 1.2 Deck D3D11 crt-lottes before the fix (`present_*.bmp` size)

## 2. Toolkit
- [x] 2.1 Parameter store, overrides and generation in `nv2a_present_chain`
- [x] 2.2 Metal: publish the table, apply `set_param`, drawable at the window size under `internal` while a chain runs
- [ ] 2.3 D3D11: the same, with a monitor-sized client under gamescope or fullscreen
- [x] 2.4 Enhancer: load `present.shader_params.*` from every layer
- [x] 2.5 Menu: Shaders page, picker moved, parameter rows, Reset to preset, Save and Reset to defaults
- [x] 2.6 Descriptor dump: the `shaders` field
- [x] 2.7 Wrapper curvature defaults and the shaders README
- [x] 2.8 `docs/runtime/config.md`
- [x] 2.9 ctests: `present_chain` store and config round trip, `enhance_menu` Shaders page
- [x] 2.10 Menu: the Shaders page is hidden where no shader can run (no chain presenter, or librashader missing or not loading), the reason said once; `enhance_menu` case (the user, 2026-10-29)

## 3. BLiNX 2
- [x] 3.1 Commented example in `packaging/config.default.toml`

## 4. Gates
- [ ] 4.1 Mac build, `tests/posix_ctest.sh`, `uv run pytest scripts`, ruff
- [ ] 4.2 Metal golden; Deck D3D11 golden with the exe built on the PC
- [ ] 4.3 Shader off equals stock; crt-lottes after the fix on Metal and the Deck
