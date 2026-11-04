## Context

Both GPU backends present the flip through one shared rule, `nv2a_present_rect` (`nv2a_backend_common.c`). It turns the frame's host size, the window size and `present.filter` into a destination rectangle (letterboxed, stretched or whole multiples), and the backend samples the whole frame into it:

- **D3D11** (`nv2a_pb_d3d11.c`):
  - `present_blit` samples UV `0..uv_scale.xy` through the blit shader's `cbuffer C { float4 uv_scale; }`. `uv_scale.zw` is unused.
  - `d3d11_flip` skips the blit for a stock frame (scale 1, `nearest`, windowed, no pad, back buffer the frame's size) and for a same-size frame unless `linear`. Under `present.surface = internal` it copies the frame with `CopyResource`.
- **Metal** (`fb_present_metal.m`):
  - `fbm_present` draws the presenter slot (a texture exactly `fw x fh`) over UV 0..1 with no uniform.
  - Under `internal` it forces the whole drawable and `nearest`.
  - It knows only `fw`, `fh` and the filter (`fb_present_sdl.c` hands them over from the slot); not the render scale the frame was drawn at.

The guest's pixels are untouched by present: `fb_dump` reads guest memory, `metal_host_dump` and the D3D11 dump read the host render target, and `window_shot` reads the window.

## Goals / Non-Goals

**Goals:**
- Hide a title's overscan border with a TV-style crop: cut the edges, then zoom the rest uniformly, on Metal and D3D11.
- At 0, run exactly the code that runs today.
- Keep the source-rectangle math in one pure, tested helper.

**Non-Goals:**
- Changing what the game draws, the render targets or any capture of guest memory.
- Per-edge, per-screen or vertical-only crops.
- The CPU rasteriser (TASKS.md line) and the Metal readback debug present.

## Decisions

### D1. The unit is guest pixels a side; the vertical cut follows

`display.overscan = n` cuts `n` guest columns from each of the left and right edges. It also cuts `n * h / w` guest rows from each of the top and bottom, so the remaining picture keeps the frame's shape and is zoomed by `w / (w - 2n)` in both axes. For 640x480 at n = 9 that is 622 x 466.5 guest pixels, starting at (9, 6.75).

- **Why guest pixels:** the border is measured in guest pixels (9 for SSX 3 at every render scale), so the setting reads the same at scale 1 and 4. The helper multiplies by the render scale the frame was drawn at.
- **Why proportional:** a horizontal-only cut would stretch the picture sideways by 3%. A TV's overscan is a uniform zoom.
- **Why not percent:** a percent hides the exact value a player measured. 9 px is 1.4%, which no one would type.
- **Range 0..64.** 64 is 10% of a 640-wide frame a side, beyond any TV's overscan. A larger value is clamped to 64, and a negative one to 0, each with one `[ENHANCE]` warning: the same pattern as `render.scale` and `render.aniso`. The cut is applied to whatever size the flipped frame has. A frame no wider than `2n` guest pixels is presented whole, so the helper never returns an empty or negative rectangle.
- **Fractional rows are fine** for `nearest` and `linear`: both backends sample by UV, so 6.75 needs no rounding. `integer` is the exception (D3).

### D2. Hor+: the key is refused, with a warning

When `display.aspect` parses to a wide ratio, a non-zero `display.overscan` is reported once and 0 is used:

`[ENHANCE] display.overscan=9 ignored with display.aspect=16:9: the 4:3 edges are inside the padded frame; using 0`

The test is on the parsed ratio (`o.aspect_w`), after the aspect parse. An invalid aspect that falls back to 4:3 therefore still crops.

The orchestrator asked to pick between two options: cropping only the 4:3 guest columns, or refusing. Refusing is the right one:

- **A crop is a cut at the picture's outer edge.** Under Hor+ the 4:3 frame's edge columns sit inside the padded frame, between the centre and the pads (`nv2a_host_pad` columns a side). A source rectangle can only take a contiguous range, so "the 4:3 columns only, pads untouched" would mean cutting a band out of the middle of the picture and splicing the two sides together. 3D that runs across the old 4:3 edge, which is what Hor+ draws, would then tear.
- **The other reading doesn't hide the border.** Cropping the padded frame's own outer edge would leave the 9 columns visible.
- **Hor+ absorbs the problem.** In Hor+ the full-screen 2D art is centred and pillarboxed (black, `display.movie`), so a dark 9-column border inside it merges with the black side bars.

This last point is an expectation, not a measurement: Hor+ is not in SSX 3's toolkit pin yet. A `window_shot` of the title at 16:9 is a task for when it is (tasks 5.2). If the border shows there, the follow-up is a guest-side mask at the 4:3 edge, not this present crop.

### D3. One pure helper, `nv2a_present_crop`

```c
struct nv2a_crop {
    float x, y, w, h;                   /* the shown part, host px */
    float u_scale, v_scale, u_off, v_off; /* its UV in the tw x th texture */
    uint32_t fit_w, fit_h;              /* the size to give nv2a_present_rect */
};
/* The part of a frame of host size fw x fh (render scale n, hor+ pad
 * pad guest px) that a display.overscan of ov guest px shows under
 * present filter `filter`, in a texture of tw x th. ov 0, a pad or a
 * frame too narrow for the cut returns the whole frame. */
void nv2a_present_crop(uint32_t fw, uint32_t fh, uint32_t tw, uint32_t th,
                       unsigned n, unsigned pad, unsigned ov, int filter,
                       struct nv2a_crop *c);
```

- **Inputs:** `tw x th` is the texture the frame lives in. D3D11's render target can be larger than the frame (`rt->hw`), which is why `present_blit` already scales UV by `hcw / rt->hw`. Metal's slot is exactly the frame (`tw = fw`).
- **Outputs:** the helper returns both the rectangle and the UV mapping. The backends then never repeat the arithmetic, and the test covers what they sample.
- **The size for `nv2a_present_rect` (`fit_w x fit_h`):**
  - **`nearest` and `linear`: the uncropped `fw x fh`.** The crop keeps the frame's aspect exactly, so the destination rectangle is the one the whole frame would get. Rounding the cropped size instead would bring the seam back: 622 x 466.5 rounded to 467 rows fits 639 columns into a 640x480 back buffer, which is a one-column bar.
  - **`integer`: the cropped size in whole host pixels.** Whole multiples of 466.5 rows don't exist for odd multiples, so under `integer` the vertical cut is rounded to whole host rows (6.75 → 7, giving 622 x 466 at scale 1). The rectangle and UVs use the rounded cut. The aspect then drifts by 0.1% (622/466 against 4/3), which is accepted: `integer` already trades exact size for sharp pixels.
- **Under `present.surface = internal`** the destination is the whole surface on both backends (the surface is the frame's size). The crop is zoomed into it with the `present.filter` sampler, except that `integer` samples `nearest`: Metal already forces whole=1 there, and D3D11 matches it.

### D4. Backends: force the blit, offset the UV

- **D3D11:**
  - The blit shader becomes `o.t = o.t * uv_scale.xy + uv_scale.zw`, and the comment over the cbuffer names `zw` as the crop offset.
  - `present_blit` fills the cbuffer from `nv2a_present_crop` and passes `fit_w x fit_h` to `nv2a_present_rect`. At 0 the helper returns the current scale and a zero offset, so a blit that runs today samples identical UVs. The blit path isn't reached by a stock run (scale 1, `nearest`, window the frame's size), so the shader change doesn't alter stock.
  - `stock` in `d3d11_flip` gains `&& !overscan`, and the `same` shortcut and the `internal` `CopyResource` are skipped when `overscan > 0`, so a crop always blits.
  - With a crop, the forced blit sets `s_dump_rt`. The D3D11 dump then reads the render target: uncropped, at the render target's size (`hw x hh`, which can be larger than the frame).
- **Metal:**
  - The hand-off slot (`struct fb_slot`, `fb_present_sdl.c`) gains `n` and `pad`. `metal_flip` passes them from the drawn target through `xbox_FramebufferWindowBackTexture(w, h, n, pad)`. `fbm_upload` (guest-bytes frames, already guest size) sets `n = 1`, `pad = 0`. So `fbm_present` never guesses the scale from `nv2a_host_render_scale()`, which is wrong when `nv2a_host_size` clamped the scale, on the flip of a live scale change, and for uploaded frames.
  - `fbm_present` takes `n` and `pad` and reads `overscan` from `nv2a_host_opts()`. At 0 it draws exactly as today: the same pipeline, vertex function and bindings. With a crop it uses a second pipeline whose vertex function `vs_crop` reads `float4 crop` (scale.xy, offset.zw) set with `setVertexBytes`. So no new statement runs at 0 (the stock requirement), and the pipeline is built once at `fbm_create`.
  - Under `internal`, the forced whole drawable stays. The forced `nearest` stays at 0 and under `integer`. With a crop and `linear`, the sampler is `linear`.
- **Filter note:** with `nearest`, zooming 622 columns to a window draws uneven columns, as any non-integer window size does today. `docs/runtime/config.md` suggests `linear` with a crop. The default stays `nearest`.

### D5. What ignores the key

- **CPU rasteriser** (`cpu_on_flip` → `fb_present_sdl.c`): logs one `[ENHANCE] display.overscan=N ignored by the CPU rasteriser` line, like `display.aspect`. A TASKS.md line records the gap (an SDL `srcrect` would do it).
- **Metal `metal_present=readback`:** a debug present through the SDL renderer. It ignores the key silently: it is not a player path, and the main log line already names the backend.
- **The Windows GDI window:** ignores every enhancement key today.

### D6. Live changes: not in v1

`nv2a_host_opts_request` changes `render.scale`, `present.filter`, fullscreen and the pack while the game runs. Overscan is read once at start, like `display.aspect`. A live toggle would need a new `NV2A_OPT_*` bit and an input binding, and no one has asked for one.

### D7. Logging and the golden check

- At 0, the `[ENHANCE]` summary line is byte-for-byte unchanged.
- A non-zero value (after the clamp and the Hor+ refusal) adds ` display.overscan=N` inside the summary's parentheses, after `display.aspect`.
- The CLI defines `ENHANCE_OVERSCAN_RE = r"\[ENHANCE\] render\.scale=.*\(display\.aspect=\S+ display\.overscan=(\d+)\)"`. It is anchored to the summary line, so the clamp warning, the Hor+ refusal and the CPU line, which carry the raw value, never match (as for `ENHANCE_ANISO_RE`).
- `golden.ENHANCE_STOCK` gains `("display.overscan", ENHANCE_OVERSCAN_RE, "0")`. A missing match counts as stock, as for every key, so older toolkits and a run at 0 pass.
- `manifest.TOOLKIT_ENHANCE_KEYS` lists the key, so a game's table can't redefine it.

## Risks / Trade-offs

- **Race frames lose columns too.** At 9, SSX 3's full-width race frames lose 9 columns a side and about 7 rows top and bottom (1.4%). A TV did the same, and the player chooses it. The SSX 3 config row says so.
- **The extra blit.** On D3D11 at scale 1 with `nearest` (the stock-like player setting), a crop adds one full-frame draw per flip. That's negligible next to the frame, but it is a new cost on the cheapest path. The perf check in tasks 5.3 measures flips/s at 0 and 9.
- **`integer` drift.** Under `integer` the crop's aspect is off by up to one host row (0.1% at scale 1). It's accepted and tested (D3).
- **The Hor+ expectation in D2 is unmeasured** until Hor+ reaches SSX 3's pin (tasks 5.2).

## Open Questions

- (none)
