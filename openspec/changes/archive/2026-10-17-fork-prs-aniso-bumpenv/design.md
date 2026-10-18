## Context

Both GPU backends get their per-stage state from `nv2a_stage_decode` and their combiner shaders from one API-free parser (`d3d8_combiners_parse.c`) feeding the HLSL and MSL generators. Each backend's `setup_pixel` folds the four stage modes into a `modes` word (anything but NONE, PASSTHRU and CLIPPLANE becomes 2D) and keys its shader memo on the combiner registers plus that word. Each backend builds its samplers from the stage's filter word, keyed on address modes, filters and LOD range. `nv2a_ps_consts_fill` fills the shared constant block that both backends upload; Metal appends its own `tex_bias`.

The CPU rasteriser's `stage_sample` (`nv2a_pb_exec.c`) treats modes above 5 as 2D at `(s, t)`.

## D1. The bump matrix registers hold 00, 01, 11, 10

Two documentary references and one frame agree. The references settle all four slots; the frames confirm only the slots their matrices exercise (see below), and the transpose question stays open as a title confirmation until a scene with a non-diagonal matrix is found.

1. **The XDK's API.** The Xbox `D3DTEXTURESTAGESTATETYPE` orders the matrix 00, 01, 11, 10: Cxbx-Reloaded's mirror of the XDK enum (`src/core/hle/D3D8/XbD3D8Types.h`) has `X_D3DTSS_BUMPENVMAT00 = 22`, `01 = 23`, `11 = 24`, `10 = 25`, then `BUMPENVLSCALE = 26` and `BUMPENVLOFFSET = 27`, marked as the first states after the deferred ones. These six are written straight to the stage's register block: `0x1B28 + 0x40 * stage + 4 * (state - 22)`, so 00 lands at 0x1B28, 01 at 0x1B2C, **11 at 0x1B30, 10 at 0x1B34**, the scale at 0x1B38 and the offset at 0x1B3C. The PC D3D8 enum orders them 00, 01, 10, 11, and that is the order our HLE header `d3d8_xbox.h` carries (`D3DTSS_BUMPENVMAT10 = 9`, `11 = 10`, upstream code); it is wrong for the XDK and joins the tracker item's follow-up on that header's values.
2. **xemu's method handler** (`hw/xbox/nv2a/pgraph/pgraph.c`, `DEF_METHOD(NV097, SET_TEXTURE_SET_BUMP_ENV_MAT)`) writes the four method slots through `swizzle[4] = { NV_PGRAPH_BUMPMAT00, NV_PGRAPH_BUMPMAT01, NV_PGRAPH_BUMPMAT11, NV_PGRAPH_BUMPMAT10 }`. Its shader then reads the PGRAPH registers in their own order (00, 01, 10, 11; `nv2a_regs.h` 0x181C, 0x1828, 0x1834, 0x1840, the same values as our `nv2a_regs.h`) into a column-major `mat2`, so `dsdt' = (00*ds + 10*dt, 01*ds + 11*dt)`, which is the D3D formula `u' = u + du*M00 + dv*M10`, `v' = v + du*M01 + dv*M11`. The PR's claim that xemu reads the stream as 00, 01, 10, 11 looked at the shader and missed the handler's swizzle.
3. **Spartan's colour grade** writes `0.5 0 0.5 0` and samples a two-curve lookup table, which only works as the diagonal 0.5: slot 2 holds m11. Being diagonal, it says nothing about slots 1 and 3.

The PR's HLSL is consistent with all three: with the registers as `bump.xyzw = (00, 01, 11, 10)`, `du' = dot(ds, bump.xw) = 00*du + 10*dv` and `dv' = dot(ds, bump.yz) = 01*du + 11*dv`. The code stays; the comments in `nv2a_stage`, `nv2a_ps_consts` and the generator that say xemu reads 00, 01, 10, 11 are corrected in our commit, and the PR close comment says so with the two citations.

**What a title's frame can and cannot confirm.** The two references settle all four slots on paper. A frame confirms only what its matrix exercises:
- A diagonal matrix, stored `(s, 0, s, 0)`, tells slot 2 from slot 3: read as 00, 01, 10, 11 it gives `du' = s*(du + dv)`, `dv' = 0`, a one-axis shear instead of a scaled ripple. That is all Spartan's `0.5 0 0.5 0` shows: slot 2 is m11, not m10. Slots 1 and 3 are both zero there, so it cannot tell whether slot 1 is m01 and slot 3 m10 or the transpose.
- Telling the transpose needs a matrix with `m01 != m10`, both non-zero: a rotation or a skew. Only a title that writes one can confirm slots 1 and 3 by frame.

So the experiment is: (a) the `bump` trace key (D4) logs every bump matrix BLiNX 2 and Burnout 3 write, with the stage and the values, over attract, stage 1, Boss 3 and a race; (b) if one of them is non-diagonal with `m01 != m10`, that scene is drawn with the settled order and compared with its xemu capture (`cat/analysis/reference/xemu/`, stage1 and attract, 2026-10-02, or a new capture for Boss 3 or Burnout 3) and with the transposed reading; the one that matches xemu and the hardware's expected look settles the transpose by frame. If no title writes such a matrix, the note says so and the transpose stays settled by reference only; TASKS records it as open until a title with a rotation or skew turns up. It is not counted as confirmed. Either way BLiNX 2's ocean and ripple against xemu confirm slot 2 on a second title, and the ocean's mean error against xemu must not rise. If a frame only matches xemu under the other reading, that is a finding to take to hgeorgilas and xemu, not a reason to flip the code quietly. Optional, if cheap: find in BLiNX 2's disasm the XDK routine that emits method 0x1B28 and read its state-to-offset mapping; it should write states 22..27 in index order, which would confirm the transpose from the API side without a frame.

**One fact, one place.** The register order is a property of the NV2A and the XDK that every title shares. It lives in the shared decode and generators (`nv2a_backend_common`, `d3d8_combiners_*`) and nowhere else: never a per-game quirk, a game key or a backend-local table.

## D2. What the bump-env PR does and what we check in review

The PR is small and follows xemu's `psh.c`. Review items, each against the reference:

- **Input stage.** Stage 1 reads stage 0; stages 2 and 3 read bits 16-19 and 20-23 of `SET_SHADER_OTHER_STAGE_INPUT`, as xemu's `input_tex[]` does (its `SHADERCTL` mask is 0xFFFF000). The PR clamps an input at or past the stage to `n - 1`; xemu asserts instead. Keep the clamp (a title bug must not kill the shader) and move the selection into a shared `nv2a_stage_input(n, other_stage_input)` in `nv2a_backend_common.h`, so both backends and the ctest use one function.
- **Signed-byte decode.** The input's `.bg` arrive as unsigned BGRA8 and go back to two's complement. xemu's `sign3` divides by 127 (`x >= 128 ? (x - 256) / 127 : x / 127`); the PR divides by 128. Use 127 as xemu does, unless hgeorgilas has hardware evidence; the difference is under 1% of the offset and invisible in a golden, so this is correctness by reference, not by frame.
- **Offset units.** The offset is added to `(s, t)` in the coordinate's own units, before `tex_scale`: normalised for a swizzled texture, texels for a linear one, as xemu adds `dsdt` to `pT.xy` before its rect `norm` remap. Correct; the ctest pins it in the text.
- **Luminance (mode 7).** xemu scales the whole texel (`t = t * (scale * l + offset)`, alpha included); the PR scales `.rgb`. Follow xemu. No title we run uses mode 7 (no `[VSH]` report shows `7=`), so this is untested by frame on every path; the split tests and the ctest cover the text.
- **Decode and constants.** `nv2a_stage_decode` reads `r[0x28/4 .. 0x34/4]`, `0x38` and `0x3C` of the stage's 0x40-byte block, the method offsets of `SET_TEXTURE_SET_BUMP_ENV_MAT`, `SCALE` and `OFFSET`; `nv2a_ps_consts_fill` copies them per stage. Both backends' `setup_pixel` fill `tex_input[]`, set `bump_on`, and grow the memo key by one word (`inputs`) so a change of input stage recompiles.
- **Input stage texel.** The `.bg` read is of the input stage's sampled value, after our decode. Spartan reads its downsampled frame back as `LIN_R8G8B8A8` (0x41) to get the channels the bump stage expects; if the colour grade is wrong on the branch, check that the render-target-as-texture fast path honours a 0x41 re-read of a target drawn as A8R8G8B8 before suspecting the generator.
- **Stock paths unchanged.** With `bump_on` unset (the legacy D3D8 path, the split tests' random cases) the text changes only by the constants line, which his re-recorded `expected.h` tables show; the expected hashes are checked, not trusted (task 2.4).

## D3. Metal twins

- **Anisotropy.** `sampler()` in `nv2a_pb_metal.m` computes the same `an = !point && mip && mn && !t->cube ? nv2a_host_opts()->aniso : 0`, adds `(uint64_t)an << 35` to its key (bits 35-39 are free on both backends: D3D11 uses 12-24 for the filter word and 25-32 for the LOD range, Metal 25-32), and sets `maxAnisotropy = an`. D3D11's `D3D11_FILTER_ANISOTROPIC` forces linear min, mag and mip; Metal sets the three filters linear when `an` is set, so the two backends apply the same filter. The `Stage` typedef is `struct nv2a_stage` on both, so `cube` is there.
- **Bump-env.** `d3d8_combiners_generate_msl` gets the same branch as the HLSL: for a stage in mode 6 or 7 with `bump_on`, decode the input's `.bg`, apply the matrix, sample at `(i.t.xy + ds) * pc.tex_scale.xy` with the stage's `bias(pc.tex_bias)`, and for mode 7 scale by the luminance term. The Metal `setup_pixel` fills `tex_input` from the shared helper, sets `bump_on`, and keys on `inputs` (37 words to 38). Nothing changes when no stage is in mode 6 or 7: the MSL text is the stock text, so `d3d8_msl_split`'s hashed cases stay as his re-record left them, and the Metal goldens for story are unchanged.
- **No aniso on a bump source.** A stage that a later BUMPENVMAP(_LUMINANCE) stage reads through `nv2a_stage_input` holds offsets, not colour. At stock its mips average a ripple map to ~0 at a distance, so a far sea is calm. Anisotropic filtering keeps the sharp ripple at grazing angles and scatters the dependent lookups into noise (the far stage 1-1 sea at `render.aniso = 16`). `nv2a_bump_sources()` names those stages for a combiner draw. `nv2a_stage_aniso()` holds the shared rule (mipmapped, min-linear, not a cube map, not a bump source). Both `sampler()`s call it, and the result is in the key, so a stage that is a source in one draw and plain in the next gets the right sampler. The perturbed stage keeps aniso: skipping it too made no measurable difference to the far sea (task 4.8).
- **Both twins are read at start.** `aniso` is not in the live-change mask (`nv2a_host_opts_request`), as the PR says; the in-game menu entry is a follow-up on both backends.

## D4. Tests and the trace key

- **`tests/nv2a_bump`, a standalone ctest** on the `tests/nv2a_tex` pattern (links `nv2a_backend_common.c`, `nv2a_tex_pack.c` and the three API-free combiner files). Cases: a stage register block with `(a, b, c, d)` at 0x28..0x34, `e` at 0x38 and `f` at 0x3C decodes to `bump = {a, b, c, d}`, `bump_scale = e`, `bump_offset = f`, and `nv2a_ps_consts_fill` copies them to `bump[n]` and `bumpls[n].xy`; `nv2a_stage_input` gives 0 for stage 1, the register's nibbles for 2 and 3, and clamps a late input; the HLSL and MSL for stage 1 in mode 6 fed by stage 0 contain the two dot products on `.xw` and `.yz`, the 127 divisor and the offset added before `tex_scale`; mode 7 adds the luminance line; the same state without `bump_on` emits the plain 2D sample. The test fails on the base (no `bump` field) and passes with the change.
- **Split tests.** A `bump_check` beside `texmode_check` in `d3d8_hlsl_split` and its MSL counterpart: stage 1 mode 6 from stage 0, stage 2 mode 7 from stage 1. On the Mac `d3d8_msl_split` compiles every case with Metal, which is the compile gate for the MSL twin; on Windows the PR author compiled a generated shader with fxc, and the Deck's `d3d11_backend_smoke` run compiles ours under DXVK. The hashed random cases do not change with the twin (D3).
- **`RECOMP_TRACE=bump`** (trace tier, X-macro row, `docs/env.md`): the first time each distinct `(stage, input stage, matrix, scale, offset, texture format and size)` appears in a batch, one line with the flip number. Printing only. It is how task 3.1 finds the BLiNX 2 and Burnout 3 scenes and records their matrices.

## D5. Goldens that move are judged, then re-recorded

The attract and stage1 scenarios contain mode-6 batches (520 and 3540); story has none. So `attract-cliff` and the three stage1 frames may change in their water regions on both backends, on main's references. The rule "goldens run at stock" holds (bump-env is stock behaviour, not an enhancement), so a verdict change is expected and is handled as follows:

1. Run the three scenarios on the branch, Metal on the Mac and D3D11 on the Deck. A frame whose verdict changes is diffed against its reference: the changed pixels must lie in the water (the ocean, the ripple), and nothing else in the frame may move beyond its usual run-to-run spread (the `note` fields in `golden.json` record it per frame).
2. Compare the moved frames with the xemu captures (`cat/analysis/reference/xemu/xemu-stage1-20261002-144723`, `xemu-attract-20261002-143300`): the error against xemu must not rise, and the water should look like xemu's. Keep the crops in `runs/hgpr/`.
3. The user playtests BLiNX 2 (stage 1, Boss 3) and Burnout 3 (a race) on the branch and signs off; the playtest is the acceptance for scenes no golden covers (Boss 3).
4. Re-record the moved frames with `blinx2 bench golden` in record mode from a clean D3D11 run. The references were taken on the Linux/Proton host's RTX 2060 and the Deck stands in today; the user chooses the host, and `golden.json`'s notes name it. Then the Metal goldens must pass against the new references, as they do today.
5. The old references stay in `analysis/golden/frames/` under a dated directory, as `pre-pacer-20261004` does.

Frames with no water (`attract-title`, story) must keep their verdicts; a change there is a regression.

## D6. Authorship, commits and the public round

The toolkit branch `feat/fork-prs-aniso-bumpenv` off `posix-host/portability` carries exactly four commits, in this order, and lands with `--ff-only` (a prepared merge, so each commit is first-parent and becomes one public commit):

1. `git cherry-pick -x e5a857a` (Harry, `d3d11: render.aniso, ...`), unchanged.
2. Ours: the Metal aniso twin, the aniso key in the golden harness's non-stock list (CLI, separate repo), `docs/env.md` row (cat, separate repo).
3. `git cherry-pick -x a061141` (Harry, `d3d11: BUMPENVMAP and BUMPENVMAP_LUMINANCE ...`), unchanged.
4. Ours: the Metal bump twin, the shared input helper, the review fixes (127, luminance on all channels, comments on the order), `tests/nv2a_bump`, the split-test cases, the `bump` trace key.

`notes/public-toolkit-map/round.py` sets author and committer to the noreply identity for every commit. For this round it must keep a commit's author when it is not ours (Harry's two), rewriting only the committer. That is a main-session change in `notes/`, made and checked (`git log --format='%an <%ae>'` on the built public commits) before the round. The PR close comments cite the public shas of commits 1 and 3.

## D7. Upstream

Bump-env is title-neutral and belongs to the GPU series of `cat/analysis/upstream/pr-stack-plan.md`: the decode and constants with G3 (one vsh/combiner decoder), the generator branches with G6 (D3D11) and G7 (Metal). When those branches are cut, Harry's commit is cherry-picked with its authorship. `render.aniso` is an enhancements-layer key, which the plan keeps fork-only; it is offered only if upstream asks for plain opt-in keys. The HLE header's enum order (D1) goes with the tracker item's upstream candidate on `d3d8_xbox.h`.

## Validation

- Mac build (`DEVELOPER_DIR=/Library/Developer/CommandLineTools`) and `tests/posix_ctest.sh`: 0 FAIL, with `nv2a_bump` and the split tests in the list; `tests/enhance_cfg` and `host_opts_live` pass with the new field.
- BLiNX 2 Metal goldens on the Mac; D3D11 goldens on the Deck from a Mac-built exe under the run lock; verdicts per D5; flips/s and mean frame ms recorded, flagged at a 25% drop or 1.5x rise.
- `RECOMP_RENDER_ANISO=16` on both backends: the stage-1 ground sharper at grazing angles in a window shot, no change to render targets, movie frames or the HUD; off by default, so the goldens' `[ENHANCE]` line reads `render.aniso=0`.
- Burnout 3 race gate (`b3/scripts/race_gate.py`) on the Mac and on the Deck, built against the branch, and a look at the race scene that uses mode 6.
- Spartan on Metal (Mac) and D3D11 (Deck), from a `tca` clone built against the branch: the colour grade and glow if the post chain presents by then; otherwise the `bump` trace shows stage 1 in mode 6 reading the R8B8 table with the matrix stored as `0.5 0 0.5 0` and input stage 0.
- The CPU rasteriser builds; no CPU golden (the rule since 2026-10-10).
- The user's playtest of BLiNX 2 and Burnout 3 before the merge.
