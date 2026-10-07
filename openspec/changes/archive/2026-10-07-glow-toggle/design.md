## Context

From the bloom spike (`openspec/changes/bloom-spike/spike.md`, branch `spike/bloom` e2e937d), here is what happens each frame, after the 3D scene and before the HUD. `sub_0005B550`:
1. calls `sub_0005B330`, which downsamples the frame into `0x00811000` (320x240);
2. reads the post mode `MEM32(0xADC738)`;
   - mode 3: it calls `sub_0005B7D0`, the glow composite;
   - mode 4: it calls `sub_0005BC60`, a second post effect with its own shader;
   - any other mode: neither.

`sub_0005B7D0` takes no arguments, has one `ret` (the lifted body has a single `esp += 4; return;`, no early return) and one caller, the direct call at `0x0005B569` in `sub_0005B550`.
- It reads the glow weight `MEM32(0xADC744)` (`0x00RRGGBB`; `0x404040` by default, the areas set `0x383838`, `0x484848` or `0x505050`) once, and stores it as the vertex diffuse of the full-screen quad's vertices (`0x3FC3F8..0x3FC564`).
- It draws that quad with four taps of the 320x240 target.
- It then calls `sub_0005B330` again (the second downsample, C).

The combiner program, read from the CPU pixel trace of the spike (`runs/bloom/c1/log.txt`, flip 1141, batch 873795: `rc0..rc6`, blend `307/1`):

| Stage | Colour | Alpha |
|---|---|---|
| rc0 | `r0 = v0·t0` | `r0.a = v0.a·t0.a` |
| rc1..rc3 | `r0 = r0 + v0·t1`, `+ v0·t2`, `+ v0·t3` | same with alphas |
| rc4 | `r1 = dot(r0, c0)`, `c0 = 0xFF666666` (0.4 per channel), blue to alpha | — |
| rc5 | `r1 = r1·r1` | `r1.a = r1.a·r1.a` |
| rc6 | `r0 = r1·r0` | discarded |

Every input is signed identity, and each stage's output is clamped to [-1, 1]. So the source colour is `r0 = (v0·Σt) · dot(v0·Σt, c0)²`: the weight `v0` enters three times. The source alpha is `v0.a·t0.a`, and `v0.a` is 0 in every value the game writes. The blend is `ONE_MINUS_DST_COLOR, ONE` (screen), `frame' = d + s·(1−d)`.

Only `sub_0005B7D0` and `sub_000E4140` read `0xADC744`. The writers are `sub_0005B240` (the defaults), the area setup (`sub_000606F0`, `sub_00061790`) and `sub_000E4140`, a per-frame fade: it reads the low byte, steps it by ±1 toward a target, clamps it to `0x20..0x40` (or pulls it up to `0x40` by 1 per frame) and writes the byte back replicated to R, G and B. None of the writers is in `sub_0005B7D0`'s call tree, which reaches only the D3D wrappers (`sub_002E0D10`, `sub_002E1980`, `sub_002E25E0`, `sub_002E3830`, `sub_002E4C10`, `sub_002E5160`, `sub_002E5360`, `sub_002E5C80`), `sub_00033A20`, `sub_00033D00` and `sub_0005B330`.

## Goals / Non-Goals

**Goals:**
- `fx.glow = "off"` removes the mode-3 glow from the picture.
- `fx.glow_intensity = k` scales the glow layer by about k.
- The defaults are stock to the byte: the guest is never written.
- Mode 4, both downsamples and every other guest value stay as they are. The game's own fade keeps stepping from its own values.

**Non-Goals:**
- the guest-size glow target at render scale (follow-up F1);
- mode 4;
- any renderer change;
- a key for other titles.

## Decisions

### D1. Wrap `sub_0005B7D0`, game side
The wrapper goes in `src/recomp_manual.c` and uses the generator's wrap support (toolkit `tools/recomp/manual_scan.py`). The scanner recognises exactly one form, a line at column 0 of `src/recomp_manual.c` (the file `blinx2 recomp` passes as `--exclude-manual`):

```c
extern void sub_0005B7D0_gen(void);
```

With that line present and `sub_0005B7D0` defined by hand in the same file, `blinx2 recomp` emits the body under the `_gen` name and declares `sub_0005B7D0` only; the hand-written `sub_0005B7D0` then takes every call.

*Implementation finding (2026-10-06):* at toolkit b0eb653 that was not true. The wrap renamed the body in `func_db`, and every call site and the dispatch entry took their name from `func_db`, so the direct call at `0x0005B569` and the dispatch entry both named `sub_0005B7D0_gen`; the wrapper was never called (the first A/B: `off` frames equal stock). Toolkit 825fde2 (`docs/glow-toggle`) fixes it in `tools/recomp`: a call to a wrapped address names `sub_X`, the dispatch entry points at it and `recomp_funcs.h` declares it. cat is the only project with a wrap, so nothing else changes. Test: `tools/recomp/test_manual_call_dispatch.py`. The declaration cannot live in `src/glow.h`: the scanner does not read it.

Why game side:
- It hits exactly the mode-3 glow and nothing else.
- It needs no backend code, so CPU, D3D11 and Metal agree by construction (CLAUDE.md "Backends agree").
- A renderer-side draw-signature filter would put a BLiNX signature into the toolkit.
- Holding the mode global (`poke 0xADC738`) would change a value that `sub_0005B240` and `sub_0005B2D0` also read.

### D2. `off` is weight 0, not a skipped call
`off` calls `sub_0005B7D0_gen` with the weight set to 0. It does not return early.
- With `v0 = 0` every combiner stage gives 0 (signed identity of 0 is 0; `r0 = 0`, so `r1 = 0`), and the source alpha `v0.a·t0.a` is 0 as it is at stock. A screen blend of 0 is `d + 0·(1−d) = d`, exact in 8-bit unorm on every backend, in RGB and in alpha. So the frame bytes equal the bytes of a run that skips the pass.
- Because the frame is unchanged, downsample C writes the same bytes into `0x00811000` as downsample A did. A skipped call could not differ through that target either.
- What a skipped call would change is the D3D render state that `sub_0005B7D0` sets and `sub_0005B550` resets afterwards through the game's shadow words (`0xAD77F4`, `0xAD77F8`, `0xAD79D4`, ...). Weight 0 leaves those exactly as stock, so nothing drawn later (HUD, menus) can see a difference, and no proof about the shadow state is needed.
- The cost is one full-screen quad and one 320x240 downsample per frame. It is measured (task 5.4). If the D3D11 or Metal cost is visible, a later change can add the spike's early return (`esp += 4; return;`); that change must first show the shadow state is reset by the dispatcher on every path.

### D3. Intensity maps through a cube root
The source colour is `(v0·Σt) · dot(v0·Σt, c0)²`, so the layer `s` grows with the cube of the weight (the combiner program in Context). The wrapper writes `w' = lround(w · ∛k)` per colour byte, clamped to 0xFF, and keeps byte 3 (alpha, 0 in the game's values).
- The realised factors `(w'/w)³` for the game's weights: at `k = 0.5`, `0x38 → 0x2C` (0.485), `0x40 → 0x33` (0.506), `0x48 → 0x39` (0.504), `0x50 → 0x3F` (0.488); at `k = 2.0`, `0x38 → 0x47` (2.04), `0x40 → 0x51` (2.03), `0x48 → 0x5B` (2.02), `0x50 → 0x65` (2.01).
- The clamps bend this near white. Each stage output clamps to 1: `r1 = 0.4·(r+g+b)` of `r0` clips at stock already when `r0`'s channels sum past 2.5, and at `k = 2` `r0 = v0·Σt` clips when the four taps sum past 3.14 per channel. The 0.5 gate is tight (0.40..0.60); the 2.0 gate allows the clipping (1.5..2.2), and the task records the measured ratio.
- The game's values have R = G = B, so a per-channel scale and a uniform scale agree; per channel is kept because it costs nothing and covers any value the game might write.
- `fx.glow_intensity` is clamped to [0.0, 2.0] with one log line. A value that does not parse falls back to 1.0 through `enhance_cfg_float`'s own report (`[ENHANCE] ... is not ...; ignored`).
- The maths is a pure helper, `uint32_t glow_weight(uint32_t w, double k)` in `src/glow.c`, unit-tested by `scripts/test_glow.py` the way `scripts/test_unimpl_budget.py` tests `unimpl_budget.h`: a small C driver compiled with the host compiler (`clang`, `gcc` or `cc`; skip when none).

### D4. Exactly stock at the defaults
The wrapper computes one flag at startup: active = `glow == off || intensity != 1.0`. When the flag is clear, the wrapper is one predicted branch followed by the generated body: no guest read or write, and no logging.

The game-side `[ENHANCE] fx.glow=on fx.glow_intensity=1` line is printed in both cases. Without the layer (`RECOMP_ENV_HAVE_ENHANCE_KEYS` undefined) the flag is always clear; the env rows exist either way, as `RECOMP_FPS_MODE` does.

### D5. Restore that survives every return and never clobbers the game
The wrapper does the following:
- reads `orig = MEM32(0xADC744)`;
- writes `scaled = glow_weight(orig, k)`;
- calls the body through `RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0_gen)`;
- writes `orig` back only if the word still equals `scaled`.

The restore is what keeps the game's fade honest: `sub_000E4140` steps the weight from whatever the word holds, by one level a frame, and writes the low byte to all three channels. A scaled value left behind would move the fade's starting point every frame (the change would compound) and, with a per-channel scale, collapse G and B to R. With the restore, the fade only ever sees its own values, so the sequence it writes is the same as at stock.

Every path out of the generated body is its one `ret` to the wrapper. The lifted code has no longjmp or SEH unwind through this function. So the restore always runs.

The compare is insurance: on one thread nothing in the body's call tree writes the word (Context), so the word always still holds `scaled`. It matters only if a writer runs on another thread (D6); then it keeps that newer write instead of overwriting it with the stale `orig`. If `scaled == orig` (k rounds to ×1, or `orig` is 0), the wrapper skips both writes.

`RECOMP_ABI_CALL` is the generated code's own call form. Under `RECOMP_ABI_CHECK` (`gen/recomp_types.h`) it logs, never aborts, when the callee returns with `esp` below entry + 4 or with ebx, esi or edi changed. The dispatcher's call into the wrapper is already checked the same way. No new check is needed.

### D6. Thread safety
The key values are read once in `host_enhance_init`, before any guest thread starts, and are read-only afterwards. Plain statics are enough: the same pattern as `fps.mode`.

The guest word is the only shared state. Its readers and writers are the game's frame code:
- `sub_0005B550` is called once, from `sub_00067E60` (return `0x0006891B`);
- `sub_000E4140` from the frame routines `sub_000649B0..` (one shared call site, return `0x00067054`);
- the area setup from the stage loader (`sub_00062FB0`, `sub_00075210`).

The spike's runs show the threads this title has: `guest-main` (tid 1001, the game's main routine) and the XDK worker threads (`PsCreateSystemThreadEx` #2..#4, routine `0x002980E7`, context `0x002D702E`, created at boot), plus the host's own `nv2a-kick`, `nv2a-ack`, `kernel-timer` and `vblank-ack`, which never run game code. The frame code is expected on `guest-main`.

Task 3.3 confirms this on our host with the toolkit's write watchpoint, `RECOMP_DEBUG=watch=0xADC744,watch_len=4`, whose lines (`[WATCH] write to 00ADC744 (+0x0) esp=...`) carry the writer's `esp`. The stack identifies the thread: `guest-main`'s stack against the workers' stacks, whose tops the boot log prints (`spawned worker ... stack top 0x03EE9FF0`). The wrapper's one-shot debug line prints its own `g_esp` so it can be placed the same way. If every writer and the wrapper share one stack, the read, modify, call and restore sequence is race-free.

If they do not, D5's compare-and-restore still never loses a game write made after the wrapper's store. The only lost-update window is a foreign write between the wrapper's load and its store, a few instructions long. In that case the task records it and the store and the restore switch to `__atomic_compare_exchange_n` on the guest word.

### D7. Goldens and the harness
- `golden.json` pins `RECOMP_GLOW=on` and `RECOMP_GLOW_INTENSITY=1`. `RECOMP_ENHANCE_CONFIG=none` already keeps `enhance.toml` out; the pins keep a stray shell variable out.
- `golden.py`'s enhancement table (`ENHANCE_STOCK`) gains `fx.glow` (stock `on`) and `fx.glow_intensity` (stock `1`, compared as a float). A non-stock value FAILs, unless the run passes `--allow-enhance fx.glow=off` or `--allow-enhance fx.glow_intensity=0.5`. Those runs are for evaluation and are refused for `--record`, as today.
- The goldens themselves do not change.

### D8. Where the keys sit
The keys go in a `[fx]` table in `enhance.toml` (`glow = "off"`, a TOML string; `glow_intensity = 0.5`), read through `enhance_cfg_choice` and `enhance_cfg_float` after `enhance_cfg_bind_env("fx.glow", RENV_GLOW)` and `("fx.glow_intensity", RENV_GLOW_INTENSITY)`. This happens in `host_enhance_init` before `enhance_cfg_report_unused()`, so the keys are never reported as unused. The env rows are CONFIG tier in `src/env/recomp_env_game.h`, with rows in `docs/env.md` (whose Config count `test_env_doc.py` checks).

## Risks / Trade-offs

- **The `enhancements` spec has a pending delta from fps-pacing** (merged on cat main at 89bbe77, its change not yet archived). This change only ADDs requirements, so the two deltas apply in either order.
- **The game's own weight animation** (`sub_000E4140`) is scaled at draw time and never stored back, so it keeps animating from its own values. With `k > 1`, its peak may clip to 0xFF less often than it would saturate the frame; this is accepted.
- **`off` keeps the GPU cost of the pass** (D2). This is cheap on Metal and D3D11. On the CPU rasteriser it is one 640x480 four-tap quad per frame, about the size of the spike's measured post draws; CPU speed is low priority (CLAUDE.md).
- **The dispatch table.** The generator renames the function everywhere it names it, so `gen/recomp_dispatch.c`'s entry for `0x0005B7D0` may point at `sub_0005B7D0_gen`. The only call is direct, so the wrapper still takes every call; task 3.2 records what the entry says.

## Follow-ups

- **F1, guest-size glow target at render scale.** Keep `0x00811000` at 1× when `render.scale > 1`, so the pass looks like retail at 3×. This needs a per-target hint in the toolkit, honoured by Metal and D3D11, with a box reduction. Effort M. The user did not choose it on 2026-10-06; it is recorded in TASKS.md only.
- **F2, mode 4.** Find which areas use `sub_0005BC60` (`peek=0xADC738` on `@stage1` and `@story`) and whether players want a key for it.
