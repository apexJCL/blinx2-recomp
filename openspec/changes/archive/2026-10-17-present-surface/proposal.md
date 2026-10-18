## Why

Two present-path bugs reported from the Steam Deck (D3D11 under Proton, `[render] scale` 1 or 2, `present.filter = "linear"`, `present.fullscreen = true`). They share the present path and the render-scale geometry, so one change covers both.

**The tracker item: gamescope's FSR never engages.** gamescope composites the focused window's surface onto its output with its own filter (Steam's per-game *Scaling filter*: Linear, Nearest, FSR, ...). FSR is an upscaler: it applies only when the surface is smaller than the output. With `present.fullscreen = true` the D3D11 window is a `WS_POPUP` at `GetSystemMetrics(SM_CXSCREEN/SM_CYSCREEN)` (toolkit `src/d3d/nv2a_pb_d3d11.c:461`) and the swap chain follows `WM_SIZE` (`present_resize`). Under gamescope the screen metrics are gamescope's nested size, so the game makes a 1280x800 surface and scales 640x480 into it with its own blit. gamescope receives a full-size surface and has nothing to upscale. Today's workaround, a lower per-game resolution in Steam, is what the user should not need.

Reproduced on the Deck in a nested gamescope (`-W 1280 -H 800 -w 1280 -h 800`, scratch install, `@attract`). Evidence: `xbox-recomp/runs/present/deck/`.

| run | config | `[d3d11] first present` |
|---|---|---|
| `a-native-fs`, `a-nearest`, `a-fsr` | `fullscreen = true`, scale 1 | back buffer **1280x800**, frame 640x480, scaling blit |
| `b-native-window`, `b-nearest`, `b-linear`, `b-fsr` | `RECOMP_PRESENT_FULLSCREEN=0`, scale 1 | back buffer **640x480**; gamescope scales the undecorated window to 1066x800, pillarboxed (`shot1.png`) |
| `b2-fsr` | fullscreen 0, scale 2 | back buffer **640x480**, frame 640x480 from a **1280x960** host target |

- The user's own Game Mode logs show the same: `fullscreen=1`, back buffer 1280x800, and 1024x640 on the run where they lowered the game resolution in Steam.
- `b2-fsr` shows a second loss: in a window, the scale-2 frame is box-downscaled to the 640x480 back buffer, so gamescope never receives the 2x detail.
- The game process under Proton sees gamescope's environment (`env.txt`, read from the Wine process's `/proc/<pid>/environ`): `XDG_CURRENT_DESKTOP=gamescope`, `GAMESCOPE_WAYLAND_DISPLAY=gamescope-0`, `ENABLE_GAMESCOPE_WSI=1`. The launcher sees the same variables.
- gamescope's screenshots are not an FSR oracle: `gamescopectl screenshot` shots of different attract frames cannot be compared pixel for pixel. The mechanism (surface size against output size) is the evidence; the visual FSR check is the user's, in Game Mode (tasks.md section 6).

**The tracker item: a green line on the right and bottom edges at `render.scale = 2`, mostly during videos.** The user confirmed it is absent at scale 1 and returns at scale 2 (filter linear). The present filter is not the cause.

- The movie is Sofdec, decoded by the guest into a linear YUY2 (`0x24`) texture of **1024x512**. The picture occupies the top-left 640x480. The padding is zero YUV, which BT.601 maps to RGB (0,135,0): green. CPU texture dump: `runs/present/cpu-texdump/tex/01_811A8000_fmt24.bmp` and `03_81443000_fmt24.bmp`.
- The movie batch, from the D3D11 pixel probe on the Deck (`runs/present/deck/px4-s2/game.log`, flip 300):
  - `prim 8 n 4`: one inline quad, program `B2913952`, positions (0,0)..(640,480) and texcoords (0,0)..(640,480): one texel per guest pixel.
  - The stage is `mode 1 fmt 24 1024x512 addr 3/3 filter 02063ECE` (MIN and MAG linear), `src cache` (guest memory, not a render target).
  - At host pixel (1278,600) the probe reads `T0 639.25 300.25` and `uv0 0.624268 0.586426` (the normalised sample, 639.25/1024).
- Linear (rect) textures take unnormalised texel coordinates (`tex_scale = 1/size`, `nv2a_ps_consts_fill`). At scale N the host pixel centres fall between the guest sample points: at guest column 639 and scale 2 the two host pixels sample u = 639.25 and u = 639.75. Bilinear filtering at 639.75 takes 25% of texel 640, the green padding. At scale 1 every sample lands on a texel centre (639.5) and reads only the picture.
- Reproduced on Metal on the Mac: `runs/present/metal-attract-s1` and `-s2`. Frame 009 at s2, guest column 639 (box-averaged by the write-back) reads (142,167,155) against an interior of (162,171,177); back-solving the right host pixel gives (122,163,133), which is 0.75·content + 0.25·(0,135,0). At s1 the column matches the interior.
- Both GPU backends share the bug: the sampling rule lives in the shaders of both. The address mode (clamp at 1024) cannot help, since the padding lies inside the texture.

## What Changes

- **New enhancement key `present.surface`** (env `RECOMP_PRESENT_SURFACE`): `"auto"` (default), `"window"`, `"internal"`.
  - `window` is today's behaviour.
  - `internal` sizes the window's client area and the swap chain to the frame (640x480 × `render.scale`), ignores the screen size `present.fullscreen` would use, ignores `WM_SIZE`, and copies the frame into the back buffer with no scaling blit. The compositor scales the surface, so gamescope's FSR, linear or nearest filter applies.
  - `auto` is `internal` when the launcher's hint `RECOMP_HOST_GAMESCOPE` is true, `window` otherwise. Stock desktop behaviour is unchanged.
  - D3D11 implements it. Metal mirrors `internal` (drawable at frame size, the layer scales) so the key means the same on both backends; `auto` never resolves to `internal` on macOS. The SDL presenter and the CPU backend ignore the key with one log line (design.md D3).
- **The hint `RECOMP_HOST_GAMESCOPE`** is a config-tier row of the toolkit's enhancement keys, read by the runtime and set only by launchers (design.md D2). The CLI's SteamOS `launch.sh` exports `RECOMP_HOST_GAMESCOPE=1` when `XDG_CURRENT_DESKTOP=gamescope` or `GAMESCOPE_WAYLAND_DISPLAY` is set, unless the user's `config/launch.env` sets it. This is Steam's Game Mode, and a nested gamescope on a desktop. With scale 1 and Steam's Default or Native resolution, FSR works out of the box; no per-game setting is needed. The runtime itself does not read the gamescope variables (D2).
- **Guest-rate sampling of unity rect-texture stages under scale** (design.md D4). When `render.scale = N > 1`, a stage that samples a linear (rect) texture from guest memory with a linear filter, and whose texcoords map one texel to one guest pixel along the screen axes (a 1:1 blit, the movie), samples at the point the 1x render samples for the guest pixel that contains the host pixel. The test and the correction run in the pixel shader from screen-space derivatives, switched per stage through the unused `tex_scale[n].z`. Render-target sources, point-filtered stages, swizzled and compressed formats, magnified or minified stretches, rotated or perspective mappings, and every stage at scale 1 sample as today.
- **Docs:** rows in `cat/docs/env.md` (`RECOMP_PRESENT_SURFACE`, `RECOMP_HOST_GAMESCOPE`), the toolkit's `docs/runtime/config.md`, `packaging/config.default.toml` (`surface = "auto"` with a comment), and the enhancements spec delta.

## Impact

- **Toolkit** (`wt/present/xboxrecomp`, off `posix-host/portability` e629c35):
  - `src/platform/recomp_env.h`: two rows in `RECOMP_ENV_ENHANCE_KEYS` (`PRESENT_SURFACE`, `HOST_GAMESCOPE`).
  - `src/enhance/enhance_cfg.c`: `bind_builtins` binds `present.surface`. `src/enhance/enhance.c` `xbox_enhance_init` reads the key, resolves `auto` from the hint, stores the result in `struct nv2a_host_opts` (new field `present_surface`, `src/kernel/nv2a_backend_common.h`) and prints it on the `[ENHANCE] render.scale=...` line.
  - `src/d3d/nv2a_pb_d3d11.c`: `init` (window and swap-chain size), `WM_SIZE`, `d3d11_flip` (direct copy under `internal`, the first-present log), the render-target override in `setup_pixel` (line 2208), the fixed-function shader `s_ps_src` (line 384), the debug shader `d3d11_debug_ps` (line 2158) and the px probe's pass B `uvof` (line 2687).
  - `src/video/fb_present_metal.m`: drawable sizing under `internal`. `src/video/fb_present_sdl.c`: the ignore line.
  - `src/kernel/nv2a_backend_common.c` `nv2a_ps_consts_fill`: the per-stage snap constant. `src/d3d/nv2a_pb_metal.m`: `fs_basic` (line 203) and the render-target override (line 2026).
  - `src/d3d/d3d8_combiners_parse.h` (a `rect_snap` flag beside `fog_input`), `d3d8_combiners_hlsl.c:147` and `d3d8_combiners_msl.c:133`.
  - ctests: the resolver (`tests/enhance_cfg` or a new `tests/present_surface`) and the snap eligibility plus the helper's arithmetic (`tests/render_scale`).
- **CLI (`xboxrecomp-cli`):** `src/xboxrecomp_cli/package/templates/steamos/launch.sh` and `tests/test_steamos_install.py`. A CLI worktree, a release tag, and a new cat `game.toml` `[cli]` pin.
- **cat:** `packaging/config.default.toml`, `docs/env.md` (rows and the tier counts `scripts/test_env_doc.py` checks), `analysis/golden/golden.json` `env` gains `RECOMP_PRESENT_SURFACE=window` (a no-op today, made explicit), `TASKS.md` follow-ups.
- **Stock:** with no key and no hint, both paths execute today's code. Goldens run at stock resolution with `surface = window` pinned. The snap constant is non-zero only at `render.scale > 1`, which goldens reject, and the combiner generators emit the helper only then, so the stock shader text (the `d3d8_hlsl_split` and `d3d8_msl_split` expected outputs) is unchanged.
- **Performance:** `internal` at scale 1 presents a 640x480 swap chain instead of 1280x800, which is cheaper. The snap adds two derivatives and a few compares per rect-texture stage at scale > 1 only.
- **Related, not in scope:** TASKS follow-up (a) from the tracker item (scale > 1 misses host column and row 0) wants to move the guest-to-host mapping by half a host pixel. D4 uses today's mapping (host = guest·N, measured by the probe), where each guest pixel owns an N×N block of host pixels. Under the moved mapping the last host column's centre falls on the guest edge (640.0) and belongs to no 1x sample, so that follow-up must revisit the snap's block rule; recorded in TASKS.md with this change.
- **Upstream:** both fixes are title-agnostic. The snap is a candidate once tested on Burnout 3 under Proton. `present.surface` lives in the fork's enhancements layer.
