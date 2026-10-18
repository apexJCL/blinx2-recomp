## ADDED Requirements

### Requirement: Present surface for a scaling compositor
`present.surface` (env `RECOMP_PRESENT_SURFACE`) SHALL take `auto` (default), `window` or `internal`; another value SHALL be reported once and read as `auto`. `window` SHALL keep the existing behaviour: the swap chain follows the window and the game scales the frame into it. `internal` SHALL size the D3D11 window's client area and swap chain to the frame (640x480 × `render.scale`), SHALL NOT consult the screen size `present.fullscreen` uses nor resize the swap chain on `WM_SIZE`, and SHALL copy the frame into the back buffer without a scaling blit under every `present.filter`, so that the compositor scales it. `auto` SHALL resolve to `internal` when `RECOMP_HOST_GAMESCOPE` is true and to `window` otherwise; the resolved value and its reason SHALL appear on the `[ENHANCE]` options line, and the resolution SHALL happen once at init (no live change). The Metal presenter SHALL honour `internal` by keeping its drawable at the frame size and letting the layer scale it with the present filter's geometry. The SDL presenter SHALL ignore the key with one log line. `RECOMP_HOST_GAMESCOPE` SHALL be a config-tier row of the enhancement keys that no configuration file key binds, and the runtime SHALL NOT read gamescope's own variables. The SteamOS launcher SHALL export `RECOMP_HOST_GAMESCOPE=1` when `XDG_CURRENT_DESKTOP` is `gamescope` or `GAMESCOPE_WAYLAND_DISPLAY` is set, unless the variable is already set, and SHALL do so before `launch.env.default` and `config/launch.env` are loaded, so a user line wins.

#### Scenario: FSR-ready surface under gamescope
- **WHEN** the D3D11 build runs under gamescope at 1280x800 through the SteamOS launcher with `present.fullscreen = true`, `render.scale = 1` and no `surface` key
- **THEN** the log reads `present.surface=internal(auto: gamescope)` and `first present: back buffer 640x480 ... copy (surface internal)`, and gamescope receives a 640x480 surface to scale

#### Scenario: Scaled frame reaches the compositor whole
- **WHEN** the same run uses `render.scale = 2`
- **THEN** the back buffer is 1280x960 and the frame is copied into it with no box-downscale

#### Scenario: Desktop unchanged
- **WHEN** the D3D11 build runs with no hint and no key, with `present.fullscreen = true`
- **THEN** the window covers the screen, the back buffer follows it and the frame is placed by the scaling blit, exactly as before this change

#### Scenario: User override of the hint
- **WHEN** `config/config.toml` sets `present.surface = "window"` and the hint is set, or `config/launch.env` sets `RECOMP_HOST_GAMESCOPE=0` under gamescope
- **THEN** the surface is `window` and the log says `present.surface=window` (with `(auto)` in the second case)

#### Scenario: Bare executable under gamescope
- **WHEN** the D3D11 build is started without the SteamOS launcher under gamescope, with no key
- **THEN** no hint is set, `auto` resolves to `window`, and `RECOMP_PRESENT_SURFACE=internal` gives the `internal` behaviour

#### Scenario: Metal parity
- **WHEN** the Metal build runs with `RECOMP_PRESENT_SURFACE=internal`, `present.fullscreen = true` and `render.scale = 1`
- **THEN** the drawable is 640x480, the layer shows it letterboxed in the fullscreen view, and the frame dump is the same as under `window`

### Requirement: Guest-rate sampling of unity rect textures under scale
When `render.scale = N > 1`, a texture stage that samples a linear (rect) format from guest memory with a linear MIN or MAG filter SHALL, where its texcoords map one texel to one guest pixel along the screen axes (no cross derivatives, and a derivative of 1/N texel per host pixel on each axis, both within 1/64), sample at the coordinate the 1× render uses for the guest pixel that contains the host pixel. Stages whose source is a scaled render target, point-filtered stages, swizzled and compressed formats, magnified, minified, rotated or perspective mappings, and every stage at `render.scale = 1` SHALL sample as before. D3D11 and Metal, fixed-function, combiner, debug and probe shaders, SHALL apply the same rule, and the combiner shader text at `render.scale = 1` SHALL be unchanged.

#### Scenario: No padding at the movie edge
- **WHEN** the attract FMV (a 1024x512 YUY2 texture whose picture fills 640x480, drawn 1:1) renders at `render.scale = 2`
- **THEN** both host pixels of guest column 639 sample u = 639.5 (the probe reports `uv0 0.624512`), and the dumped frame's last column and row match the interior within the golden limits on Metal and D3D11

#### Scenario: Render-target source keeps host-rate detail
- **WHEN** a stage at `render.scale = 2` samples a scaled render target through a linear format
- **THEN** its snap constant is 0 and it samples at host rate, as before this change

#### Scenario: Stock sampling unchanged
- **WHEN** any scene renders at `render.scale = 1`
- **THEN** every stage samples at the same coordinates as before this change, the generated combiner shaders are byte-identical, and the goldens pass with the same verdicts
