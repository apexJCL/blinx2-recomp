## Why

The user (2026-10-28): "If you're able, add the CRT shader to Blinx 2".
The spike (notes/shader-spike/report.md) picked RetroArch slang
presets run by librashader, and the umbrella the tracker item fixed the shape: the
prebuilt upstream library pinned by sha256, only PD/MIT/BSD presets bundled,
no catalogue download, and the shader reads the render-scale frame. This is
phase 1: CRT presets in BLiNX 2 on Metal and D3D11.

## What changes

- Toolkit (game-agnostic, only with `XBOXRECOMP_ENHANCE`):
  - `src/kernel/nv2a_present_chain.{c,h}`: loads librashader with
    dlopen/LoadLibrary (never linked), checks its ABI and API, resolves the
    preset, and gives the backends the symbols. A missing library turns the
    feature off with one log line; a Windows load that fails for a missing
    VC++ runtime says so.
  - Keys `present.shader` (default `none`: stock present) and
    `present.shader_lib` (library override), with env rows
    `RECOMP_PRESENT_SHADER` and `RECOMP_PRESENT_SHADER_LIB`.
  - Metal (`fb_present_metal.m`) and D3D11 (`nv2a_pb_d3d11.c`): with a
    shader on, the final present draw becomes the librashader filter chain
    into the present rect; the menu and stats overlay draw after it.
  - A "Shader" choice on the menu's Render page switches presets live.
  - The header `librashader.h` (MIT) vendored in `third_party/librashader/`;
    four presets (crt-lottes, crt-lottes-fast, crt-hyllian (the fast,
    single-pass Hyllian), fsr) vendored in `assets/shaders/` at a pinned
    libretro/slang-shaders commit, with their licence headers; the build
    copies them to `shaders/` beside the exe.
  - ctests `tests/present_chain`: library missing, ABI check, preset paths.
- BLiNX 2: a commented `[present] shader` row in
  `packaging/config.default.toml`, `docs/env.md` rows, the golden's stock
  key list learns `present.shader = "none"`.
- Library delivery: the toolkit's build pins the release zips by sha256 and
  stages the library, the presets and the MPL-2.0 text beside the exe; the
  CLI's package step carries them into the bundles.

## Out of scope

The wizard's preset-link fetch, a shader parameters page, other games, the
CPU rasteriser (logs one line and presents stock), `present.surface =
internal` with a shader (falls back to the window surface).
