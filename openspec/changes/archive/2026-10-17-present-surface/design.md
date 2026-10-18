## Context

The D3D11 present path today (toolkit `src/d3d/nv2a_pb_d3d11.c`, `posix-host/portability` e629c35):

- **`init`** (line 428 on): with `present.fullscreen` (`nv2a_host_opts()->fullscreen`) it creates a `WS_POPUP` at `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)` (line 461); otherwise a `WS_OVERLAPPEDWINDOW` with a 640x480 client. The swap chain is FLIP_DISCARD, BGRA8, 2 buffers, at the client size (`s_back_w/h`, `s_made_w/h`).
- **`WM_SIZE`** (line 301) records `s_client_w/h`; `present_resize` (line 3402), called from `d3d11_flip`, calls `ResizeBuffers` to that size.
- **`d3d11_flip`** (line 3513): `stock` is scale 1, filter `nearest`, not fullscreen, back buffer unresized; `same` is frame extent = target size = back buffer size. It copies (`CopyResource`) when `same` holds and the filter is not `linear`, and otherwise blits through `present_blit` (line 3448), which places the frame with `nv2a_present_rect` and a point or linear sampler. The first-present line names `scaling blit`, `copy` or `overlap copy`.

The present keys are read in `src/enhance/enhance.c` `xbox_enhance_init` (`enhance_cfg_choice`/`_bool`, bound to their variables in `enhance_cfg.c` `bind_builtins`), stored in `struct nv2a_host_opts` (`src/kernel/nv2a_backend_common.h:1011`: `render_scale`, `present_filter`, `fullscreen`, `pack_off`) and printed on one `[ENHANCE] render.scale=... present.filter=... present.fullscreen=... present.pacing=...` line. The environment goes through `recomp_env.h`, three tiers (config, trace, debug); the enhancement keys are the `RECOMP_ENV_ENHANCE_KEYS` block, which exists only with `XBOXRECOMP_ENHANCE`.

gamescope composites the focused X window. The surface is the window's size, and gamescope fits it to the output with its filter (`-F`, or Steam's per-game *Scaling filter*). FSR upscales only, so it runs only when the surface is smaller than the output. Game Mode's gamescope runs with `-w/-h` at the game resolution chosen in Steam (Default is 1280x800 on the Deck), and Wine's screen metrics report that size. gamescope does not decorate or resize the window: the `b-*` runs' 640x480 overlapped window was shown pillarboxed at 1066x800 with no title bar and no `window resized` line in the log.

The Sofdec movie batch (Deck pixel probe, `runs/present/deck/px4-s2/game.log`, flip 300, scale 2):

```
batch prim 8 n 4 prog B2913952 ... surface 0x00104000 640x480
 tex0 mode 1 on 1 fmt 24 1024x512 off 81443000 pitch 2048 addr 3/3 filter 02063ECE ... src cache
 inline verts: v0 (0,0) (640,0) (640,480) ..., v2 (texcoord) the same numbers
 px (639,300): T0 639.25 300.25, pos 1278.5 600.5, uv0 0.624268 0.586426
```

`uv0` is the normalised sample (T0 × `tex_scale`, 639.25/1024). The probe's `pos` is `SV_Position`: host pixel centres.

## Decisions

### D1. `present.surface`: who scales the frame

The key takes three values; `enhance_cfg_choice` rejects anything else with the usual `[ENHANCE] ... should be one of auto|window|internal` line and uses the default.

- **`window`** (today): the swap chain follows the window, and the game scales the frame into it.
- **`internal`**: the swap chain is the frame size, 640x480 × `render.scale` (1280x960 at scale 2), and the compositor scales it.
  - The window's client area is created at that size: a `WS_POPUP` at (0,0) when `present.fullscreen` is set (no decorations, so a compositor that scales sees the frame alone), a normal window otherwise.
  - `WM_SIZE` still records the client size, but `present_resize` does nothing under `internal`, so the swap chain never follows a resize.
  - Back buffer and frame have the same size, so `d3d11_flip`'s `same` condition holds. The copy test becomes `same && (filter != linear || surface == internal)`: under `internal` the frame is copied under every filter, since a filter has nothing to do when nothing is scaled. At scale > 1 the scaled target is copied as it is: no blit, no box-downscale.
  - The first-present line names the mode: `back buffer 1280x960, frame 640x480 (1280x960 host), copy (surface internal)`.
- **`auto`** (default): `internal` when `RECOMP_HOST_GAMESCOPE` is true (`recomp_env_on`), `window` otherwise.

The resolved value and its reason go on the existing `[ENHANCE] render.scale=...` line: `present.surface=internal(auto: gamescope)`, `present.surface=window(auto)`, `present.surface=internal`. `struct nv2a_host_opts` gains `int present_surface` holding the resolved `window` or `internal` (never `auto`). It is read at init only: the window is created once, so there is no `NV2A_OPT_*` bit and the in-game menu cannot change it.

Why the frame size and not 640x480 always: at scale 2 the user's case should hand gamescope the 1280x960 frame, which it downsamples into an 800-line output. Today that frame is box-downscaled to the window first (`b2-fsr`). With scale 1 the surface is 640x480 and gamescope's FSR upscales it to 1066x800: the "FSR out of the box" result the tracker item asks for. FSR does not apply at scale 2 on an 800-line output, because the surface is taller than the output; the docs say so.

On a plain desktop, `internal` shows the frame unscaled (a 640x480 window at scale 1), because nothing composites it. That is the documented meaning: the key is for a scaling compositor, which is why `auto` chooses it only under gamescope.

Rejected: keeping `window` and leaving it to Steam's per-game resolution. That is the current workaround the user wants gone, and it also sizes our blit target down, so the game's scaler runs before gamescope's.

### D2. The hint: a config-tier row, set by the launcher only

**Where the hint lives.** `RECOMP_HOST_GAMESCOPE` is a row of `RECOMP_ENV_ENHANCE_KEYS` in the config tier:

```
X(HOST_GAMESCOPE, CONFIG, "RECOMP_HOST_GAMESCOPE", NULL, "host: 1 when the launcher runs the game under gamescope (Steam Game Mode); present.surface=auto then means internal")
```

Reasons: the table has three tiers and the hint is neither a trace nor a debug switch; it exists only with the enhancements layer, like the key it steers; and `RECOMP_HOST_PAD` already shows a config-tier row that describes the host rather than a preference. It is not bound to a config file key (`enhance_cfg_bind_env` is not called for it): it has no file tier, a user does not set it in `config.toml`, and the key it steers is `present.surface`. `docs/env.md` lists it in the Config table with "set by the SteamOS launcher; a user line in `config/launch.env` overrides it", not in the launcher-variables table (the game reads it).

**Who sets it.** The SteamOS bundle's `launch.sh` (CLI template `src/xboxrecomp_cli/package/templates/steamos/launch.sh`), which already tests `XDG_CURRENT_DESKTOP = gamescope` for its first-launch notice (line 150). Before `load_env "$HERE/launch.env.default"` (line 47) it runs:

```
# Steam's Game Mode, or a nested gamescope on a desktop. The game then
# hands gamescope the frame to scale (present.surface=auto -> internal),
# so Steam's scaling filter (FSR) applies. A line in config/launch.env wins.
if [ -z "${RECOMP_HOST_GAMESCOPE:-}" ] \
    && { [ "${XDG_CURRENT_DESKTOP:-}" = gamescope ] || [ -n "${GAMESCOPE_WAYLAND_DISPLAY:-}" ]; }; then
    export RECOMP_HOST_GAMESCOPE=1
fi
```

Both `launch.env.default` and `config/launch.env` load after it, so a user line `RECOMP_HOST_GAMESCOPE=0` wins, as does one already in the environment. Precedence for the key itself is the usual one: `RECOMP_PRESENT_SURFACE` beats `config/config.toml`'s `present.surface`, which beats `config.default.toml`'s `"auto"`. The hint only decides what `auto` means. A user who wants the old behaviour under gamescope puts `surface = "window"` under `[present]` in `config/config.toml`.

**No runtime fallback.** The runtime does not read `XDG_CURRENT_DESKTOP` or `GAMESCOPE_WAYLAND_DISPLAY`, although Proton passes both through (`env.txt`). Reasons:

- Every supported Linux install goes through the bundle, whose launcher is the one place that knows the host. The Windows and macOS launchers have no gamescope. The bench runs the bare `.exe` under Proton, but it pins `RECOMP_PRESENT_SURFACE=window` (D5), so a hint would not matter there.
- Fork code reads the environment only through the `recomp_env` table, whose names are `RECOMP_*`; its non-`RECOMP_` names are deprecation aliases that print a line. A row for a foreign variable would be a fourth kind of row for one case.
- A developer running a bare `.exe` under gamescope has `RECOMP_PRESENT_SURFACE=internal` (or `surface = "internal"` in the file), documented beside the key.

Revisit only if a non-bundle Linux install path appears (a Flatpak, a Lutris script); then the launcher of that path sets the same hint.

### D3. Backend parity

- **D3D11:** D1 as written.
- **Metal (macOS):** `fb_present_metal.m` sizes `drawableSize` to the view at init (line 151) and on every present (line 309). Under `internal` the drawable stays at the frame size and the layer scales it to the view: `contentsGravity = kCAGravityResizeAspect` (letterboxed, like `nv2a_present_rect`'s fit) and `magnificationFilter`/`minificationFilter` `kCAFilterLinear` for `linear` and `integer`, `kCAFilterNearest` for `nearest`. The frame is then drawn 1:1 into the drawable with no blit geometry. This keeps the key's meaning identical for a small change. `auto` never resolves to `internal` on macOS: there is no gamescope and the macOS launcher sets no hint. It is reachable with `RECOMP_PRESENT_SURFACE=internal` for the parity check (tasks 4.2).
- **SDL presenter (CPU backend) and the Win32 GDI window:** the key is ignored with one log line (`[present] present.surface=internal ignored (SDL presenter)`), per the CLAUDE.md rule that the CPU path only has to keep building. Recorded in TASKS.md.

### D4. Guest-rate sampling of unity rect-texture stages at scale > 1

**What the 1x render does.** At scale 1 the movie quad maps guest pixel g's centre (g + 0.5) to texel coordinate g + 0.5: every sample is a texel centre, and bilinear filtering reads that texel alone. At scale N the N host pixels inside guest pixel g sample at g + (k + 0.5)/N, between texel centres, and the ones nearest the picture edge blend in the padding texel. The fix makes those host pixels sample where the 1x render sampled their guest pixel. For a 1:1 blit there is nothing else to gain from host-rate sampling: the source has one texel per guest pixel, and the extra samples only interpolate between neighbours (a bilinear upscale of the video, which also reads the padding). The snapped result is the 1x movie, as the console shows it, scaled by the present path.

**Shader rule.** For each enabled stage n, with `uv` the stage's texcoord in texels (after the `/w` of a true 2D stage, before `* tex_scale[n].xy`), `pos` the host pixel centre (`SV_Position.xy`, `[[position]].xy`) and `N = tex_scale[n].z`:

```
float2 dx = ddx(uv), dy = ddy(uv);          // before any branch: derivatives
                                             // need uniform control flow
bool snap = N > 1.0
    && abs(dx.y) <= EPS && abs(dy.x) <= EPS           // screen-aligned
    && abs(abs(dx.x) * N - 1.0) <= EPS                // one texel per guest
    && abs(abs(dy.y) * N - 1.0) <= EPS;               //   pixel, both axes
if (snap) {
    float2 d = (floor(pos / N) + 0.5) * N - pos;      // to the block centre
    uv += dx * d.x + dy * d.y;                        // the 1x sample point
}
```

- `EPS = 1.0 / 64.0` texel per host pixel. fp32 derivatives of coordinates in 512..1024 carry an ulp of 6e-5, so a tolerance of 1e-4 would sit inside the noise; 1/64 is 250× above it, and a mapping that passes the test while tilted or stretched by 1/64 moves the corrected sample by at most N/128 texel (|d| ≤ N/2), which is invisible.
- The correction is the affine extrapolation of the texcoord from the host pixel to its guest pixel's centre, so it is exact for any affine mapping; the unity and alignment tests only limit where it is used.
- The movie at scale 2: at host x 1279.5, `d.x = −0.5`, `dx.x = 0.5`, so u = 639.75 − 0.25 = 639.5; at 1278.5, `d.x = +0.5`, u = 639.25 + 0.25 = 639.5. Rows the same. The probe reports `uv0 0.624512` (639.5/1024) for both host pixels.
- The rule uses screen-space derivatives, so it does not care how the texcoords were made (vertex program, inline or array) and costs no CPU work.

**Eligibility** (CPU side, `nv2a_ps_consts_fill`, shared by both backends). `tex_scale[n].z = N` when all of these hold, else 0:

- `nv2a_host_render_scale() = N > 1`;
- the stage is on (`mode` not 0 and not 4);
- the format is linear (`nv2a_tex_size_from_format(color)` false), so the coordinates are texels;
- MIN or MAG is linear (`nv2a_tex_filter_linear(filter, 0)` or `(filter, 1)`); a point-filtered stage reads one texel and never bleeds.

`tex_scale[n].zw` exist in both constant layouts (`PsConsts` in HLSL and MSL) and are zero today (`memset` in the fill). The two render-target overrides (D3D11 `setup_pixel` line 2208, Metal line 2026) reset `.z` to 0: a scaled target holds host-rate detail that the 1x rule would throw away. `.w` stays unused.

**Where it is applied.** Every place that turns an interpolated stage texcoord into a sample:

- D3D11 `nv2a_pb_d3d11.c`: `s_ps_src` (fixed function, line 384), `d3d11_debug_ps` (line 2158, `RECOMP_TRACE=d3d11_debug_ps=t0`) and the px probe's pass B `uvof` (line 2687), so the probe and the debug view report what the real draw samples;
- Metal `nv2a_pb_metal.m` `fs_basic` (line 203);
- the combiner generators `d3d8_combiners_hlsl.c:147` and `d3d8_combiners_msl.c:133`.

One helper per language, `nv2a_snap_uv(uv, pos, tex_scale[n])`, keeps them identical. The static shaders (`s_ps_src`, `fs_basic`, the debug and probe shaders) always contain it and branch on the constant. The combiner generators emit the helper and its call only when `NV2ACombinerState.rect_snap` is set (a backend flag beside `fog_input`, set from `nv2a_host_render_scale() > 1` when the backend parses the state), so the stock shader text, and the `d3d8_hlsl_split`/`d3d8_msl_split` expected outputs, do not change. The flag is part of the shader cache key (`rc_hash` on D3D11 and Metal's equivalent): `render.scale` can change at run time from the menu (`host_opts_live`), so the same combiner state needs both shaders. Dependent reads (bump env-map stages) are left alone: their coordinates do not come from an interpolated texcoord.

**Why not the alternatives:**

- Clamping `uv` to the quad's texcoord range inset half a texel, or to the picture rectangle. The range is not known in the shader; on the CPU it needs the vertex program's outputs (the interpreter or stream output), and a rectangle computed from the texture alone does not exist (a rect texture's padding is just bytes). For a 1:1 blit any clamp that keeps the bilinear footprint inside the picture degenerates to the snap anyway: the 1x sample at 639.5 reads texel 639 alone, and every host-rate sample between 639.5 and 640 reads the padding.
- Per-triangle bounds from a geometry shader. D3D11 only; Metal has no geometry stage.
- Uploading padded textures with edge replication. It changes what the title's bytes mean, and the padding size is not known from the texture.
- Point sampling at scale > 1. It changes interiors, not just edges.
- Snapping every screen-aligned rect stage, magnified ones included (the first draft). A magnified picture reads its padding on the console too: its last row's 1x sample lands between the last picture row and the padding, so the enhanced render shows at most a little more of what the hardware shows. Snapping those stages would replace the enhancement's bilinear magnification with a nearest-upscaled 1x image on every 2D linear-format element. The unity rule touches only stages that have nothing to lose. If a magnified or minified stretch is seen bleeding beyond its 1x look, widening the test is a follow-up (TASKS.md), with its own evidence.

**Dependency.** `floor(pos / N)` is today's guest-to-host mapping (host = guest·N, each guest pixel an N×N block of host pixels; the probe's `pos 1278.5` ↔ `T0 639.25`). TASKS follow-up (a) from the tracker item proposes host = (guest − 0.5)·N + 0.5, under which host blocks straddle guest pixels and the last host column's centre maps to guest 640.0, a point no 1x sample covers. That follow-up must redefine the snap's block rule when it changes the mapping; this change notes it there and does not pre-empt it.

### D5. What stays stock

- With no key and no hint, `present.surface` resolves to `window` and `tex_scale[n].z` is 0 at scale 1.
- The D3D11 and Metal present paths execute today's statements; the new statements are reached only under `internal`. The combiner shader text at scale 1 is byte-identical to today's. The static shaders gain the helper, whose branch is not taken at `.z = 0`; the goldens confirm the output.
- The golden configuration (`analysis/golden/golden.json` `env`) additionally pins `RECOMP_PRESENT_SURFACE=window` and leaves `RECOMP_HOST_GAMESCOPE` unset. `blinx2 golden check` needs no new rule: `internal` at scale 1 presents the same 640x480 bytes (the dump reads the back buffer after a copy, or the target after a blit, never the window), and scale > 1 is already refused.

## Validation

- **ctest:**
  - the resolver (`tests/enhance_cfg`, or a new `tests/present_surface`): every combination of key (`auto`, `window`, `internal`, unset, invalid) and hint (unset, `0`, `1`), with the expected log fragment;
  - the snap constant (`tests/render_scale`): linear and swizzled formats, point and linear filters, scale 1 and 2, mode 0 and 4 stages, and the render-target override;
  - the helper's arithmetic in C, as the ctest's reference for the shader expression: 639.75 → 639.5 and 639.25 → 639.5 at scale 2; 300.25 → 300.5; at scale 3 the three host pixels of guest column 639 (639.1667, 639.5, 639.8333) → 639.5; a stretched mapping (`dx.x·N = 0.933`) or a cross term of 1/32 is not snapped; at `.z = 0` the input is returned.
- **Mac Metal:** goldens at stock. Then `@attract` at scale 2 with `fb_dump` every 30 flips, through `runs/present/tools/edges.py`: the right column and bottom row of frame 009 match the interior within the golden limits, where today they read (142,167,155) against (162,171,177). Repeat at scale 3. Menus and the HUD at scale 2 compared with `runs/present/metal-attract-s2` by eye: no element changed except the movie edges.
- **Deck nested gamescope** (`~/Games/BLiNX2-scratch/tools/run-gs.sh`, desktop mode):
  - with the hint, `fullscreen = true` and scale 1: `present.surface=internal(auto: gamescope)` and `first present: back buffer 640x480 ... copy (surface internal)`;
  - at scale 2: back buffer 1280x960;
  - without the hint (`RECOMP_HOST_GAMESCOPE=0` in `launch.env`): 1280x800 as today;
  - the px probe at (639,300) at scale 2 reports `uv0 0.624512` for stage 0.
- **the Linux/Proton host:** `blinx2 bench golden` (D3D11 at stock), plus one scale-2 attract run with a D3D11 host-size dump (`RECOMP_DEBUG=d3d11_dump`) checked for the edge with `edges.py`. D3D11 flips/s against main.
- **Game Mode on the Deck:** the user's check, tasks.md section 6.
