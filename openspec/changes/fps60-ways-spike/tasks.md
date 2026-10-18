Each experiment runs later in its own worktree, after the user's go for each run. Interpolation is in scope (the user, 2026-10-17), so tasks 2-5 go ahead, and the external-tool docs (task 1) are approved. Mac runs use Metal with `SDL_AUDIODRIVER=dummy`. Deck runs go through `blinx2 bench`, which takes the run lock. Frame dumps and footage stay local with the other private runs, never in a worktree or a public repo.

## 1. External frame-generation docs (route B3, S)

- [x] 1.1 (`docs/frame-generation.md`, the tracker item; the user approved the text on 2026-10-18.) Write a player-facing section in `docs/` on Lossless Scaling (Windows), lsfg-vk with `decky-lsfg-vk` (Linux and the Deck), AMD AFMF and NVIDIA Smooth Motion. For each: what it needs, the expected artefacts at a 30 fps base (HUD ghosting, particle smear, +1 base frame of latency, below the vendors' recommended base), and the settings that help (`present.pacing=sleep`, borderless window, vsync). Mark it unsupported. No code. **Done when** the user approves the text.
- [ ] 1.2 Only with the user's OK and their own Lossless Scaling copy: one lsfg-vk check on the Deck over `@stage1-hold`. **Pass:** the layer loads under our Proton build and presents at 60. The user's verdict on the footage is recorded in TASKS. No build changes.

## 2. Draw-matching probe (route A gate, S)

- [ ] 2.1 Extend `vsh_const_dump` to a VCD2 record (debug tier, toolkit branch). Add the attribute offsets and strides, the index count and first index, the bound texture offsets and formats, the render-target and zeta offsets, and a screen-space flag. Record inline draws (`inline_data`/`inline_buf`, with a hash and a vertex count) and fixed-function draws (`program` = 0) as well. Keep VCD1 readable. A ctest round-trips one record of each kind.
- [ ] 2.2 Dump **consecutive** flips (`vsh_const_dump_every=1` over a 300-flip window) on Metal for:
  - the golden scenarios `@stage1`, `@stage1-hold` and `@story`;
  - one boss or time-control scene;
  - **a pan and turn route** (a scripted camera rotation and a run with turns), because the existing sample is mostly a held camera.
- [ ] 2.3 Write `scripts/fps60_match.py` (stdlib, with `scripts/test_fps60_match.py`). It matches draws between flips N-1 and N by key plus order within the key. It **classifies each differing row per program** as a matrix (a 4x4 or 4x3 block whose last row is (0,0,0,1) or orthonormal), a vector (unit length) or a scalar, and checks the result against the tracker item's reading (`c[100..107]` W·V, `c[0..47]` palettes, `c[112]` a view-space vector). It also tags programs as particle or spawn (high unmatched rate, CPU-written vertices). Per flip and per scene class, it reports the matched fraction, the unmatched draws by program and tag, the row roles, and the largest per-draw transform delta.
- [ ] 2.4 Add cut detection to the script (V delta or a matched-fraction drop) and check it against the known cuts in `@story`.
- [ ] 2.5 Factor the camera. The generic fallback takes V as the most common W·V among a frame's draws. Once free-camera M0a lands, compare that with `V_game`. **Pass:** the two agree on at least 95% of 3D flips. Otherwise route A uses `V_game` on BLiNX 2 and records the fallback's failure rate for other titles.
- **Gate (stop rule for route A), per scene class, on 3D gameplay flips:**
  - at least **95% of draws matched**;
  - at least 80% of the unmatched draws are in programs that 2.3 tags as particle or spawn;
  - no false cut in `@stage1-hold`.

  Below 85% in any class, stop route A and record why in TASKS. Between 85% and 95%, report to the user before task 3.

## 3. Route A prototype on Metal (M)

- [ ] 3.1 Add the toolkit key and its rows before any code reads it:
  - `render.interp = "off" | "on"`, default off, 60 Hz output only (90/120 Hz is a later follow-up);
  - `RECOMP_RENDER_INTERP` in the `recomp_env.h` enhancements block, bound in `enhance_cfg.c`;
  - rows in the toolkit config docs and in `cat/docs/env.md`.

  Then record the frame's draw list in the Metal backend and keep its data alive for one extra frame. Size the rings for two frames and wrap them only at a frame start, or copy a draw's data when a mid-frame overflow (`flush()`) would reset them.
- [ ] 3.2 (Milestone, C3) Camera-only replay: re-render frame N with the camera at t = 0.5 from the factored V, presented on the half-way vblank through `presentDrawable:atTime:` with three drawables. **Pass:** on `@stage1-hold`, the present interval has p95 jitter under 2 ms around 16.7 ms; walker plus replay time per flip stays within 33 ms; no guest write-back from the replay.
- [ ] 3.3 Matched per-draw interpolation using the task 2 matcher and row roles: decompose and lerp W·V (`c[100..107]`), the same per matrix for the palette rows (`c[0..47]`), lerp and renormalise view-space vectors (`c[112]`), lerp or copy scalars, and use N's value for anything unmatched.
- [ ] 3.4 Post passes and render-to-texture: replay into host-only targets; a pass that samples an earlier frame's target gets the N-1 copy. A texture re-uploaded mid-frame keeps one version per upload, so earlier draws replay with the content they sampled. **Check** a time-control blur frame and an `fx.glow` frame: against the A/B mean of N-1 and N, the mid-frame shows no doubled glow or blur.
- [ ] 3.5 Cadence and cut rules: interpolate only at two vblanks per flip; repeat N on a cut, on a scene change and on FMV. **Check** that menus stay at 60 with no interpolated frames, and that a stop, slow and rewind sequence shows no pops.
- [ ] 3.6 Measure. **Gate,** on `@stage1-hold`, `@stage1` and the pan and turn route, at 1x and 2x render scale:
  - present-interval p95 jitter under 2 ms;
  - walker plus replay plus `on_flip` stall time per flip within 33 ms at p95;
  - under 1 pop per 10 s, counted by the script as a per-draw position jump against both neighbours;
  - added latency of at most one vblank, measured as the first present whose frame changes after a pad event, against stock;
  - stock goldens unchanged with the option off.

  Then side-by-side footage (stock 30 against interp) for **the user's review**, which decides whether route A continues.

## 4. D3D11 mirror, the native Windows gate and the Deck gate (M)

- [ ] 4.1 Before porting: one bulk constant buffer per frame, bound with 16-constant-aligned offsets through `s_ctx1->VSSetConstantBuffers1` (S-M). Then time a replay-only pass on the Deck: submit frame N's recorded draws twice, with no lerp. **Gate:** real frame plus one replay, including any `on_flip` stall, fits 33 ms at p95 at stock on `@stage1` and the pan and turn route.
- [ ] 4.2 Present scheduling: a third buffer plus a waitable swap chain, or a present thread under the context lock. Pick by measuring walker stall in `on_flip`.
- [ ] 4.3 Port tasks 3.1-3.5 to D3D11. **Pass:** the task 3.6 gate on the Deck under Proton; flips/s within the CLAUDE.md drop limit with the option off; and the Metal and D3D11 mid-frames agree on the A/B tool.
- [ ] 4.4 If 4.1 or 4.3 fails only on the Deck: ship on Metal and native Windows D3D11, disable the option under Proton with one log line, and record the Deck gap in TASKS (the user, 2026-10-17).
- [ ] 4.5 **Native Windows gate** (each run with the user's OK, since it needs a reboot): the 4.1 replay-only timing, then the task 3.6 gate, on the PC. The frame there already exceeds the draw count where native Windows paces at 38-42 ms. **Pass:** the same 33 ms gate. Native Windows is required: a failure stops D3D11 shipping and goes to the user.
- [ ] 4.6 Productise: pin the key off in `game.toml` `[golden] enhance_stock` and add a harness check that fails a golden run reporting it on; add a CPU-backend log line saying it ignores the option; `fps.mode` stays `lock30`, and the optional cat alias `fps.mode = "interp60"` → `render.interp = on` is added with its `cat/docs/env.md` row.

## 5. MetalFX frame interpolation (M-L, after task 3 passes)

- [ ] 5.1 Feed `MTLFXFrameInterpolator` colour, the previous colour, depth with `depthReversed = NO` (NV2A depth is not reversed), the HUD-class draws as the UI texture, and camera-only motion vectors. Select it with a toolkit CMake option `XBOXRECOMP_METALFX`, off by default: with it on, the build links MetalFX (no weak-linking) and sets the Mac deployment target to macOS 26; with it off, no MetalFX code is compiled and the stock Mac build keeps its current minimum. Check `+supportsDevice:` at run time and fall back to route A with one log line. The `render.interp` value that picks MetalFX exists only in that build. Record the D3D11 gap in TASKS.
- [ ] 5.2 Add per-draw motion vectors: a second clip-position output evaluated under the matched N-1 constants.
- [ ] 5.3 Compare with route A on the same footage. **Pass:** the user prefers it on at least one scene class (particles, glow), and it meets the task 3.6 cadence and time gates. Otherwise drop it and record why.

## 6. Store-tracing generator option (funded, S-M, about 1 pw)

Funded by the user on 2026-10-17. It serves the tracker item's free camera (M0a: who composes `V_game` into `0xAAD3A0` or the `0x885E20` stack, and who writes the `0xAAF450` ring) and the mods as much as mod60. mod60 itself stays parked unless the traces show a path.

**Scope:** a debug-only generator option in `tools/recomp`, the store-side twin of `--trace-functions`. Given address ranges, it emits a hook before each guest store whose target may fall in a range. The hook logs the store's guest va, the target address, the size and the value, plus the calling function, to a per-thread ring flushed to a file. The ranges come from `game.toml` or the env through `recomp_env`. Stock builds emit nothing, and the CLI exposes it as an `xbr` option, so Burnout 3 can use it too.

**Estimate:** about 1 pw: the generator emission and a range filter (2-3 days), the runtime ring and file format (1 day), a `tools/recomp` test and a small reader script (1 day). Not included: the regeneration (`blinx2 analyze` then `blinx2 recomp`) and the trace runs.

- [ ] 6.1 Implement the option with a `tools/recomp` unit test and a ctest of the ring. **Pass:** a stock build is byte-identical with the option off; an instrumented `@stage1` run lists every writer of the player position `0xAE7744` in one run.
- [ ] 6.2 Run it for free-camera M0a (the `0xAAD3A0`, `0x885E20` and `0xAAF450` ranges) and hand the writer list to that change.
- [ ] 6.3 Re-estimate mod60 from the `0xAE7744` and camera writer lists. Record the estimate in TASKS. mod60 stays parked unless the estimate falls well below XL.

## 7. Burnout 3 (after task 3 passes)

- [ ] 7.1 Run the task 2 probe on a Burnout 3 race. **Pass:** the same task 2 gate. Record its speed-blur post pass as the expected risk. Any upstream-bound part follows the Burnout 3 upstream gate.

## 8. Close the spike

- [ ] 8.1 Record each task's result, the 2026-10-17 decisions and the user's verdicts in TASKS. Open a follow-up change (for example `frame-interpolation`) for the route that passes, with requirements and scenarios.
