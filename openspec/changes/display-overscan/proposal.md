## Why

Some titles leave a border at the left and right edges of their 4:3 frame, because the CRT televisions they were made for hid the outer few percent of the picture (overscan). SSX 3's title screen is one: its art spans guest columns 9..629 of the 640x480 frame, and columns 0..8 and 630..639 are black, or dim navy where the bottom gradient reaches them. That is 9 guest pixels a side, the same at render scale 1 and 2 and in a 2560x1920 window shot. Race and menu frames are full width. The user saw it on the Deck: "probably overscan leftover… most noticeable on the home screen before pressing Start", "on the left and right sides. It's horizontal only" (2026-10-18).

A modern display shows the whole frame, so the border shows up as a dark seam. Masking it black would not help, since it already is dark. The remedy is what a TV did: crop the edges and zoom the rest uniformly.

## What Changes

- **`display.overscan`** (env `RECOMP_DISPLAY_OVERSCAN`, default `0` = stock). It is a whole number of guest pixels, 0..64, cut from each of the left and right edges of the presented 4:3 frame. Top and bottom are cut in proportion (`n * h / w`), so the picture keeps the 4:3 shape and is zoomed uniformly. Out-of-range values (above 64 or below 0) are clamped with one warning, and a non-number is reported and ignored, so the next source answers (the config file, then 0). Under `present.filter = integer` the vertical cut is rounded to whole host rows.
- **Present only.** The crop is a source rectangle on the flip's present blit, on Metal and D3D11. The guest frame, the host render targets, the write-back to guest memory, `fb_dump`, `metal_host_dump` and the D3D11 dump are unchanged. `window_shot` shows the crop, since it reads the window.
- **Hor+: refused.** With a `display.aspect` other than 4:3, a non-zero `display.overscan` is reported once and 0 is used (design D2).
- **A pure helper, `nv2a_present_crop`,** in `nv2a_backend_common`, gives both backends the source rectangle, its UV scale and offset, and the size to fit to the window. A new standalone ctest, `tests/present_crop`, covers it, and a crop case in `tests/d3d11_backend_smoke` reads the back buffer under Proton.
- **CPU rasteriser**: ignores the key and logs one line. A TASKS.md line records the gap.
- **Goldens**: unchanged and stock-only. The CLI's golden check fails a run whose log reports a non-zero `display.overscan`, like the other toolkit keys.
- **Games**: SSX 3's `packaging/config.default.toml` gets a commented row (`# overscan = 0`, suggesting 9 for the title screen's border). That's a separate change in the SSX 3 repo, after this one lands in a pin.
- **Not in this change:**
  - an asymmetric or vertical-only crop. No title on record needs one;
  - a per-screen crop. SSX 3's race frames are full width and lose 9 columns at 9: the player trades that for a clean title screen, as on a TV;
  - the SDL renderer's readback present on Metal (`metal_present=readback`), a debug mode. It ignores the key (design D5).

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `enhancements`: new requirement "Display overscan crop". "Enhancements default to stock" is amended to name `display.overscan`, its stock value and the golden check.

## Impact

- **Toolkit (`xboxrecomp`, off `posix-host/portability`):**
  - `src/kernel/nv2a_backend_common.{h,c}`: the `overscan` field of `nv2a_host_opts` and `nv2a_present_crop`;
  - `src/enhance/enhance.c`: parsing, the Hor+ refusal and the log;
  - `src/enhance/enhance_cfg.c`: the env binding;
  - `src/platform/recomp_env.h`: the `DISPLAY_OVERSCAN` row;
  - `src/d3d/nv2a_pb_d3d11.c`: blit shader offset, `present_blit`, the `stock` and blit decisions in `d3d11_flip`;
  - `src/video/fb_present_metal.m`: a crop pipeline (`vs_crop`) used only above 0, and `fbm_present`;
  - `src/video/fb_present_sdl.c` and `src/d3d/nv2a_pb_metal.m`: the render scale and pad on the hand-off slot;
  - `src/kernel/nv2a_pb_exec.c`: the CPU rasteriser's one line;
  - `tests/present_crop/` (new), `tests/enhance_cfg` and `tests/d3d11_backend_smoke`;
  - `docs/runtime/config.md`.
- **CLI (`xboxrecomp-cli`):** `display.overscan` in `golden.ENHANCE_STOCK` and `manifest.TOOLKIT_ENHANCE_KEYS`, with a test.
- **cat:** a `docs/env.md` row, the "Config" line's counts (50 → 51, twelve → thirteen), and a TASKS.md line for the CPU rasteriser. BLiNX 2 needs no crop, so its `config.default.toml` is not changed.
- **Performance:** at 0, nothing. Above 0, one extra full-frame blit on paths that skipped it (D3D11 at scale 1 with `nearest`, or the internal surface): one textured quad per flip.
