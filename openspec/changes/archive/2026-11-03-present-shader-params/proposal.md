## Why

The user (2026-10-29), after the tracker item put CRT presets in BLiNX 2: "if the
filter has extra settings, let's expose them. Ideally on their own tab,
like a Filters/Shaders tab. Right now the one that simulates CRT curvature
has way too much and there's fringing." the tracker item.

Three things follow from that:
- every slang preset declares runtime parameters (`#pragma parameter`) with
  a name, a label, a range and a step, and librashader reads them; the menu
  shows none of them;
- crt-lottes ships `warpX = 0.031`, `warpY = 0.041` and crt-lottes-fast
  `CURVATURE = 0.02`, which bend a 4:3 game a lot on a small screen;
- on the Deck the picture fringes. The cause (design, "Fringing") is that
  under `present.surface = internal`, which the SteamOS launcher picks
  under gamescope, the chain draws into a surface of the frame's size
  (640x480 at 1x) and gamescope then scales that to 1280x800. The shadow
  mask and the scanlines, which the preset draws per output pixel and per
  source line, are resampled by a non-integer factor: colour fringes and
  moiré. That is a bug, not a taste.

## What changes

- Toolkit (only with `XBOXRECOMP_ENHANCE`):
  - `nv2a_present_chain` keeps the active preset's parameter table (read by
    the backend through `libra_preset_get_runtime_params` when it builds the
    chain) and the per-preset overrides, with a parameter generation that
    the backends follow with `libra_*_filter_chain_set_param`, live, on
    Metal and D3D11.
  - The overrides come from the config:
    `[present.shader_params.<preset>]` with `<param> = <number>`, read from
    every layer, and go back through the menu's Save as differences only.
  - Menu: a new **Shaders** page after Render. The Shader picker moves
    there from Render; under it the active preset's parameters as range
    rows (label, value at the step's decimals, min..max in the footer), and
    a *Reset to preset* row. The Save page's *Reset to defaults* clears the
    overrides too.
  - The descriptor dump (`RECOMP_MODS_DESCRIBE=json`) gains a top-level
    `"shaders"` field: every bundled preset's parameters with their range,
    the preset value and the value this run resolved, plus the config key
    of each. Schema stays 1 (a field added).
  - Fringing fix: while a shader runs under `present.surface = internal`,
    the surface is the output, not the frame. D3D11: under gamescope (or
    fullscreen) the window's client area and the swap chain take the
    monitor's size; otherwise the swap chain follows the client area as
    under `window`. Metal: the drawable follows the window as under
    `window`. With the shader off the internal surface comes back.
  - Calmer curvature by default, in our wrapper presets
    (`assets/shaders/<name>.slangp`), never in the vendored upstream files:
    crt-lottes `warpX = 0.01`, `warpY = 0.02`; crt-lottes-fast
    `CURVATURE = 0.01`. The README names the upstream values.
  - ctests: the parameter store and its config round trip
    (`tests/present_chain`), the Shaders page (`tests/enhance_menu`), and
    the picker's choices against `NV2A_PRESENT_CHAIN_NAMES`.
  - `docs/runtime/config.md`: the TOML shape, the page, the surface rule.
- BLiNX 2: this spec, a commented example in
  `packaging/config.default.toml`, and the page name in `README.md` and
  `docs/env.md`. No new environment variables (the parameters have no env
  tier).

## Out of scope

- Convergence controls: none of the four bundled presets has a convergence
  or chromatic offset parameter (design, "Parameters"); none is invented.
- Parameters of a preset other than the active one in the menu (the dump
  lists them all).
- `render.scale > 1` with a CRT preset at a smaller output (more source
  lines than output lines aliases the scanlines): documented, not changed.
- The CPU rasteriser and the SDL presenter, which run no shader.
