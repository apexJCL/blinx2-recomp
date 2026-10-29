## 1. Toolkit (`feat/present-shaders` off `posix-host/portability` 375deac4)

- [x] 1.1 Vendor `third_party/librashader/librashader.h` (v0.12.0, MIT) and the four presets in `assets/shaders/` with a README naming the commit and licences
- [x] 1.2 `src/kernel/nv2a_present_chain.{c,h}`: load, ABI/API check, symbols, preset resolve, request generation, VC++ runtime line
- [x] 1.3 Keys `present.shader`, `present.shader_lib`; env rows; `[ENHANCE]` log line; `docs/runtime/config.md`
- [x] 1.4 Metal glue in `fbm_present` (chain into the cleared drawable, overscan ignored with one line, overlay after)
- [x] 1.5 D3D11 glue in `d3d11_flip` (chain in place of `present_blit`, scratch copy of a grown target, `s_sc_init`, back-buffer dump)
- [x] 1.6 Menu: "Shader" choice on the Render page
- [x] 1.7 Build: copy `assets/shaders` to `shaders/` beside the exe; optional `XBOXRECOMP_LIBRASHADER` path copied beside it
- [x] 1.8 `tests/present_chain` ctest; Mac build; `tests/posix_ctest.sh` 0 FAIL

## 2. BLiNX 2 (`feat/present-shaders` off cat main)

- [x] 2.1 This spec
- [x] 2.2 `packaging/config.default.toml` commented `shader` row; `docs/env.md` rows; golden stock keys learn `present.shader = "none"`
- [ ] 2.3 Toolkit pin for the test build

## 3. Library delivery

- [x] 3.1 CLI package step: `shaders/` and the library from the exe dir into the bundle, in the stage inputs (the pins live in the toolkit build, 1.7)
- [ ] 3.2 Follow-up: `bench` ships `shaders/` with the exe

## 4. Verify

- [x] 4.1 Metal golden with `present.shader = none` (stock)
- [x] 4.2 Metal run with crt-lottes, window shot in `runs/present-shaders/`
- [x] 4.3 Windows exe built on the PC; Deck golden with `none`
- [x] 4.4 Deck Proton run with a CRT preset and a back-buffer dump (vkd3d-shader HLSL compile)
- [x] 4.5 Deck patch installed for the user
- [ ] 4.6 Review before merge
