Worktrees:
- `wt/hgpr/xboxrecomp`: toolkit, branch `feat/fork-prs-aniso-bumpenv` off `posix-host/portability` 6c06ae4. The PR heads are local refs `pr/hgeorgilas-aniso` (e5a857a) and `pr/hgeorgilas-bumpenv` (a061141).
- `wt/hgpr/cat`: this spec and the cat-side docs, branch `spec/fork-prs-aniso-bumpenv` off `main`.
- `wt/hgpr/xboxrecomp-cli`: the golden harness's non-stock list, a branch off `main`.
- `wt/hgpr/tca`: a `cp -c` clone of `spartan/tca` without its build dirs, configured with `XBOXRECOMP_DIR` at the toolkit worktree.

Raw runs go in `xbox-recomp/runs/hgpr/`. Mac runs are headless (`SDL_AUDIODRIVER=dummy`), builds use `export DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Proton runs are on the Deck with a Mac-built exe copied over, under `flock -w 3600 ~/.recomp-run.lock` (memory note *deck-proton-bench*; `blinx2 bench` takes the lock itself). No tools under `tools/` change, so every game build against the branch may use `--stale-gen-ok`, recorded in its provenance note. BLiNX 2 first on the Deck; one agent there at a time.

## 0. Spec review

- [x] 0.1 Fable wrote this spec, so no second read is needed before implementation; the Opus review (6.2) covers the code.

## 1. Bring the PRs in

- [x] 1.1 `git cherry-pick -x e5a857a` onto the branch. Author stays `Harry <harrygeorgilas@gmail.com>`; the message is his. Check `git log --format='%an <%ae>'`.
- [x] 1.2 Review the aniso commit against design D2 and the PR text: the rule `!point && mip && mn && !t->cube`, the key bit 35 clear of the LOD and filter bits, the 0..16 clamp with 1 as off, the `RENDER_ANISO` row in the `RECOMP_ENV_ENHANCE_KEYS` X-macro (CONFIG tier), `config.md`. Findings go in the review note, fixes in 2.x.
- [x] 1.3 `git cherry-pick -x a061141` onto the branch, after 2.x, so the four commits land in design D6's order. Author stays Harry's.
- [x] 1.4 Review the bump-env commit against design D2: the input-stage nibbles, the clamp, `sign3`'s divisor, the offset before `tex_scale`, mode 7 on all four channels, the decode offsets 0x28..0x3C, the constants copy, the memo key growth, the Metal layout asserts (544, 560). Verify the re-recorded `expected.h` tables: build the base and the PR with `HLSL_DUMP` and `MSL_DUMP`, diff the dumps, and confirm only the constants line differs (his claim), keeping the diff summary in the notes.

## 2. Aniso: Metal twin and plumbing (our commit 2)

- [x] 2.1 `nv2a_pb_metal.m` `sampler()`: the same rule and key bit as D3D11, `maxAnisotropy = an`, and linear min, mag and mip filters when `an` is set (design D3).
- [x] 2.2 Window shots on the Mac at `RECOMP_RENDER_ANISO=16` and at stock on the stage-1 fly-over: the ground sharper at a grazing angle, the HUD, render targets and movie frames unchanged. Same on the Deck in D3D11. Shots in `runs/hgpr/aniso/`.
- [x] 2.3 CLI: `golden.py`'s `ENHANCE_STOCK` gains `("render.aniso", <re>, "0")` with a test in `tests/`; `uv run pytest tests`, `uv run ruff check . && uv run ruff format --check .`. It rides the next CLI round and is not a merge blocker for the toolkit. Done: CLI `feat/golden-render-aniso-stock` 6d2d23e (633 pass, ruff clean); cat's pinned CLI lacks it until the next round, so a Deck aniso16 golden ran without the stock refusal.
- [x] 2.4 cat: `docs/env.md` row for `RECOMP_RENDER_ANISO` (enhancements layer, default 0, Metal and D3D11, CPU ignores it) and the count in the Config line; `uv run ruff check . && uv run ruff format --check .` and `uv run pytest scripts` unaffected but run.

## 3. Bump-env: scenes, Metal twin, tests (our commit 4)

- [x] 3.1 The `bump` trace key (design D4): X-macro row (TRACE tier), one line per distinct configuration with the flip, a `docs/env.md` row. Run BLiNX 2 attract and stage 1 and a Burnout 3 race on the Mac with it and record, in the notes, each title's mode-6 stages, input stages, matrices, scale and offset, texture formats and the flips. For each matrix say which slots a frame of it can confirm: a diagonal one confirms slot 2 only; one with `m01 != m10`, both non-zero, can confirm the transpose (design D1). If one exists, compare that scene with its xemu capture under the settled order and the transposed reading, and record which matches. If none exists, say so, and the transpose goes to TASKS as open (6.4).
- [x] 3.2 `nv2a_stage_input(n, other_stage_input)` in `nv2a_backend_common.h`; both backends call it. Correct the comments that say xemu reads 00, 01, 10, 11 (design D1), citing the method handler's swizzle.
- [x] 3.3 Review fixes from 1.4: the 127 divisor and the mode-7 scale on all four channels, in the HLSL, with the reason in the commit body.
- [x] 3.4 The MSL branch for modes 6 and 7 in `d3d8_combiners_generate_msl`, with `bias(pc.tex_bias)` kept; the Metal `setup_pixel` fills `tex_input`, sets `bump_on`, keys on `inputs`. The hashed `d3d8_msl_split` cases must not change.
- [x] 3.5 `tests/nv2a_bump` (design D4), registered in the toolkit's CMake test list and standalone-buildable. Show it fails on the base and passes on the branch; keep both outputs in the notes.
- [x] 3.6 `bump_check` in `d3d8_hlsl_split` and `d3d8_msl_split`; on the Mac the MSL case compiles with Metal.
- [x] 3.7 CPU rasteriser: builds; `stage_sample` still samples modes 6 and 7 as 2D. TASKS entry for the gap (6.4).

- [x] 3.8 `render.aniso` skips a bump source stage (design D3), on both backends through `nv2a_bump_sources()` and `nv2a_stage_aniso()`, with the result in the sampler key. `tests/nv2a_bump` checks a source stage at 0, a plain mipmapped stage at 16, the basic shader, no mips, point, a cube map and stock, plus a stage-3 source and a plain stage that names another (review, 1e2d72b). Toolkit 9e5f53b.

## 4. Gates

- [x] 4.1 Mac build and `tests/posix_ctest.sh <dir>`: 0 FAIL; `nv2a_bump`, both split tests, `enhance_cfg`, `host_opts_live`, `nv2a_backend_smoke` in the list. Summary in `runs/hgpr/`.
- [x] 4.2 BLiNX 2 Metal goldens on the Mac (attract, stage1, story) from a cat build against the branch (`--stale-gen-ok`, provenance note): verdicts per design D5; flips/s and mean frame ms against main's last runs (45.8 / 33.4 / 54.0 flips/s), flagged at a 25% drop or 1.5x rise.
- [x] 4.3 BLiNX 2 D3D11 goldens on the Deck: `blinx2 build windows` on the Mac with a provenance file, copy to `~/blx-bench/cat/build-win/`, `blinx2 bench golden`. Verdicts per D5; flips and frame ms against bench-logs 20261015-074306/-074426/-074617. The `[ENHANCE]` line reads `render.aniso=0`.
- [x] 4.4 Golden judgement (design D5 steps 1-2): per moved frame, a diff against the reference and a crop against the xemu capture in `runs/hgpr/golden/`; the error against xemu must not rise. Frames without water keep their verdicts. The findings go to the user with the playtest builds. No golden frame moved on Metal or D3D11 (water is off screen in every golden frame), so there was nothing to judge or re-record; the stage-1 sea comparison against xemu (error 6.39 -> 5.61) is in `wt/hgpr/notes/bump-order-evidence.md`.
- [x] 4.5 Burnout 3 race gate, built against the branch: `python3 scripts/race_gate.py --fixture ... --out .../runs/hgpr/b3-mac` on the Mac and the Deck D3D11 variant (`--pad-script`, `BENCH_TIMEOUT=490`), both pass; a frame of the race scene from 3.1's flip, before and after, in `runs/hgpr/b3/`.
- [x] 4.6 Spartan on Metal (Mac) and D3D11 (Deck, own dir `~/spartan-bench-hgpr`, under the run lock), from `wt/hgpr/tca` (`tca build macos|windows --stale-gen-ok`): the colour grade and glow by eye if the post chain presents, else the `bump` trace line for stage 1 (mode 6, R8B8 table, matrix `0.5 0 0.5 0`, input 0). Not a blocker; a wrong colour grade is first checked against the 0x41 re-read (design D2) and goes to TASKS if unresolved. Dumps in `runs/hgpr/spartan/` only.
- [x] 4.7 Aniso spot check at `RECOMP_RENDER_ANISO=16` on both backends during 4.2 and 4.3's scenarios: no crash, no visible change to screen-aligned content (2.2's shots).

- [x] 4.8 The far stage 1-1 sea at aniso 0, at 16 before 3.8 and at 16 after, on the held view of `runs/hgpr/aniso-bump/scripts/seafar.txt` (@stage1, then six camera steps), flips 1900-2100. The far-sea and mid-distance beach high-frequency energy (`runs/hgpr/aniso-bump/scripts/aniso_bump.py`):

  | Backend | Measure | Aniso 0 | 16 before | 16 after |
  |---|---|---|---|---|
  | Metal (Mac) | far sea | 7.46 | 32.15 | 7.82 |
  | Metal (Mac) | beach | 23.09 | 26.52 | 26.89 |
  | D3D11 (Deck) | far sea | 7.31 | 46.96 | 7.39 |
  | D3D11 (Deck) | beach | 23.34 | 27.07 | 27.05 |

  - The D3D11 runs were Mac-built exes: cfcec254 before, 150a03be after.
  - The far sea at 16 now matches aniso 0, and the ground keeps its sharpening.
  - Also skipping the perturbed stage gave 7.58 on Metal. The three low values sit inside one run's frame-to-frame spread (sd 1.4-2.1), so the perturbed stage keeps aniso.
  - Frames and crops are in `runs/hgpr/aniso-bump/`. The Metal goldens still pass (stock).

## 5. The user's playtest and the re-record

- [ ] 5.1 Builds for the user: the Mac app (Metal) and a Windows exe (Deck under Proton, or native Windows if the user prefers), from the same toolkit sha, with 4.4's crops. The user plays BLiNX 2 stage 1 and Boss 3 and a Burnout 3 race and signs off, or names what is wrong.
- [x] 5.2 After the sign-off, re-record the moved frames (design D5 step 4) from a clean D3D11 run on the host the user names; old references kept under a dated directory (step 5); `golden.json` notes name the host, the toolkit sha and this change. Metal goldens re-run against the new references: pass. **Not applicable:** no golden frame shows the bump water (attract, stage1 and story pass unchanged on Metal and on the Deck, D3D11), so no frame moved and nothing is re-recorded. The bump change is judged on the Metal stage-1 A/B instead (crates sea, error against xemu 6.39 -> 5.61; `wt/hgpr/notes/bump-order-evidence.md`), with a D3D11 crop of the same scene from the Deck beside it (bench-logs 20261015-122729, frames in `runs/hgpr/deck-sea/`: D3D11 error min 1.97, median 5.78 against Metal 2.25 and 5.85, high-frequency energy 13.49 against Metal 13.56 and xemu 13.26; crop `runs/hgpr/crops/s1-sea-metal-d3d11-xemu.png`; the D3D11 mean, 7.37, takes in a few frames before the dialogue cut, since the run is not phase-aligned).

## 6. Review, merge, follow-ups

- [ ] 6.1 Main session: `notes/public-toolkit-map/round.py` keeps a non-ours author (Harry's two commits) and rewrites only the committer; checked on the built public commits before the round (design D6). The PR close comments (public shas of commits 1 and 3, the comment correction with the two citations, the 127 and mode-7 fixes) are drafted for the user's approval; nothing is posted without it.
- [ ] 6.2 Opus review of the toolkit branch (and the CLI and cat branches) before the merge; fixes go back to the branch's agent, into commits 2 and 4 only.
- [ ] 6.3 Merge: toolkit with `--ff-only` (four commits, design D6); cat and CLI with `git merge --squash`. Then the post-merge steps: notes to `notes/hgpr/`, referenced runs to `runs/` with `cp -c`, worktrees removed and branches kept, the Deck `bench golden` on the merged tree.
- [ ] 6.4 TASKS.md: close the BUMPENVMAP follow-up (line 783 and BLX-136's item); add the CPU-rasteriser gap, the in-game menu entry for `render.aniso` on both backends, the `d3d8_xbox.h` enum order to BLX-136's header follow-up, mode 7 untested by any title, the matrix transpose (slots 1 and 3) as open unless 3.1 found a non-diagonal matrix, and MSAA/FXAA as the next PRs from hgeorgilas; record the gate numbers and the golden re-record. Also from the Opus review (N2): the bump sample skips `nv2a_snap_uv` when `rect_snap` is on (render.scale > 1), in Harry's HLSL branch and our MSL alike (`d3d8_combiners_hlsl.c:154`, `d3d8_combiners_msl.c:140`); snapping the base coordinate before the offset is the likely fix, on both backends, with a scaled-run check of the stage-1 sea.
