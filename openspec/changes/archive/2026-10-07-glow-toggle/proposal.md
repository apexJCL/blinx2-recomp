## Why

BLiNX 2 draws a glow over every 3D frame. The bloom spike (`openspec/changes/bloom-spike/spike.md`, branch `spike/bloom` e2e937d; runs in `xbox-recomp/runs/bloom/`) found how:
- Each frame, `sub_0005B550` downsamples the frame to a 320x240 target.
- In post mode 3 (`0xADC738`), `sub_0005B7D0` then adds a 4-tap, luminance²-weighted blur over the frame with a screen blend. The weight `0xADC744` is the quad's vertex colour and enters the combiner program three times (design, Context).

The taps sit ±3 pixels apart, so edges get faint offset copies. The user saw these as a "doubled" image on cliff and box edges.

The glow is the game's intended look: our 1× frame matches xemu with it on (mean abs error 0.64) and is 14.8 levels darker without it. Some players still want it off or softer, especially at render scale 3, where the four taps separate into visible ghosts.

The user chose (2026-10-06) the spike's recommendation: a game-side toggle plus an intensity, in the enhancements layer. They did not choose the render-scale fidelity fix (keeping the 320x240 target at guest size). That fix is recorded as a follow-up only.

## What Changes

- **New game keys `fx.glow` and `fx.glow_intensity`** in `enhance.toml`, read only with the layer (`XBOXRECOMP_ENHANCE`, `RECOMP_ENV_HAVE_ENHANCE_KEYS`):
  - `fx.glow` is `"on"` (stock) or `"off"`; env `RECOMP_GLOW`.
  - `fx.glow_intensity` is a float from 0.0 to 2.0, default 1.0 (stock); env `RECOMP_GLOW_INTENSITY`. It scales the strength of the glow layer, whatever per-area weight the game picked.
  - Both are read once at startup in `host_enhance_init`, next to `fps.mode`, and reported on an `[ENHANCE] fx.glow=… fx.glow_intensity=…` line.
- **A wrapper for `sub_0005B7D0`** in `src/recomp_manual.c`, using the generator's existing `sub_X_gen` wrap (toolkit `tools/recomp/manual_scan.py`: the line `extern void sub_0005B7D0_gen(void);` at column 0 of `recomp_manual.c`).
  - At the defaults it calls `sub_0005B7D0_gen()` and touches nothing else.
  - Otherwise it scales the glow weight `0xADC744` for the duration of the call and puts the game's value back afterwards, so the game's own per-frame fade of that word (`sub_000E4140`) keeps stepping from its own values. `off` is weight 0. The game still issues the pass, but with a zero vertex colour the shader outputs zero and the screen blend leaves the frame unchanged.
- **Only post mode 3 is affected.** Mode 4 (`sub_0005BC60`), the first downsample (`sub_0005B330`) and the second downsample inside `sub_0005B7D0` all run as stock.
- **`gen/` is regenerated** with `blinx2 recomp`, which renames the body to `sub_0005B7D0_gen`. No generated code is hand-edited.
- **Goldens stay stock.** `golden.json` pins `RECOMP_GLOW=on` and `RECOMP_GLOW_INTENSITY=1`. `golden.py` fails a run whose `[ENHANCE]` line shows another value, unless `--allow-enhance` is given for an evaluation run.
- **Docs:** rows in `docs/env.md` and the `fx.*` keys in the toolkit's `docs/runtime/enhance-config.md` table of game keys. The toolkit doc is docs only; there is no toolkit code change.

Non-goals:
- the guest-size glow target at `render.scale > 1` (follow-up, recorded in TASKS.md);
- a toggle for mode 4;
- a renderer-side or game-agnostic post-pass filter.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `enhancements`: two game keys, `fx.glow` and `fx.glow_intensity`, which are stock by default, apply only to the game's mode-3 glow, and are kept out of goldens.

## Impact

- cat:
  - `src/recomp_manual.c` (the wrapper);
  - a pure helper `src/glow.c` and `src/glow.h` (the weight maths), added to `GAME_SOURCES` in `CMakeLists.txt`;
  - `src/main.c` (`host_enhance_init`);
  - `src/env/recomp_env_game.h` (two CONFIG rows);
  - `docs/env.md` (two rows and the Config count);
  - `analysis/golden/golden.json` (pins);
  - `scripts/golden.py` and `scripts/test_golden.py`;
  - a new `scripts/test_glow.py`;
  - regenerated `src/recomp/gen/`.
- toolkit: `docs/runtime/enhance-config.md` (docs only, on a toolkit branch off `posix-host/portability`).
- Runtime cost at the defaults: none (one predicted branch per frame). With the toggle active: two guest stores and one load per frame.
