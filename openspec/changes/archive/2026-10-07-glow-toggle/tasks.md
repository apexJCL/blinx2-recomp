Worktree: `wt/bloom/cat` on `feat/glow-toggle` (off cat `main` a8ade89). The toolkit doc edit goes in `wt/bloom/xboxrecomp`, on a branch off `posix-host/portability`. Raw runs go to `xbox-recomp/runs/glow/`, never inside a worktree. Build on the Mac with `export DEVELOPER_DIR=/Library/Developer/CommandLineTools` and `blinx2 build`. Mac runs are headless with `SDL_AUDIODRIVER=dummy`. `pipeline.sh` and `bench.sh` are gone (main 70bf5c8): the pipeline is `blinx2 recomp`, the Proton host is `blinx2 bench <command>`, which takes the run lock itself (never wrap it in `flock`).

Order: 0, then 1 to 4 in order (each builds on the last), then the gates 5 and 6, then 7. Nothing in 5 or 6 starts before 4 is done, since the goldens need the harness rows.

## 0. Spec review (before any code)

- [x] 0.1 Fable reads this change (proposal, design, the spec delta) and improves it in place. Done 2026-10-06 on `feat/glow-toggle`: the combiner program verified from the spike's CPU trace (D3), the fade's dependence on the restore (D5), the wrap scanner's exact form (D1), `RECOMP_ABI_CALL` instead of a new esp check, the `blinx2` commands, the CMake and env.md counts, the thread evidence (D6).
- [x] 0.2 The implementing agent resumes only from Fable's revised commit.

## 1. Keys and environment

- [x] 1.1 Add two CONFIG rows to `src/env/recomp_env_game.h`, next to `FPS_MODE`: `GLOW` (`RECOMP_GLOW`, "enhancements: fx.glow, on|off") and `GLOW_INTENSITY` (`RECOMP_GLOW_INTENSITY`, "enhancements: fx.glow_intensity, 0.0..2.0").
- [x] 1.2 In `host_enhance_init` (`src/main.c`), inside `RECOMP_ENV_HAVE_ENHANCE_KEYS` and before `enhance_cfg_report_unused()`:
  - bind both keys and read them with `enhance_cfg_choice` (`{"on", "off"}`) and `enhance_cfg_float`;
  - clamp the intensity to [0, 2], with one log line when clamped;
  - set the wrapper's statics through `glow_configure(off, k)`;
  - print `[ENHANCE] fx.glow=<on|off> fx.glow_intensity=<%g>` on one line.
- [x] 1.3 Add both rows to `docs/env.md` (game rows, like `RECOMP_FPS_MODE`), saying what the keys do, that only mode 3 is affected and that goldens pin them. Raise the Config count in the intro bullet (34 → 36) and extend that bullet's last sentence to name the three game keys. `pytest scripts/test_env_doc.py` passes.

## 2. Weight helper

- [x] 2.1 `src/glow.c` and `src/glow.h`, added to `GAME_SOURCES` in `CMakeLists.txt`:
  - `uint32_t glow_weight(uint32_t w, double k)`: each of bytes 0-2 becomes `lround(byte · cbrt(k))`, clamped to 255; byte 3 is kept. `k <= 0` gives `w & 0xFF000000`.
  - `void glow_configure(int off, double k)` and `int glow_active(void)`; `glow_active` is 0 until configured, so a build without the layer never activates.
  - The comment says why the cube root (design D3) and why the restore matters (D5).
- [x] 2.2 `scripts/test_glow.py`, on the pattern of `scripts/test_unimpl_budget.py`: compile `src/glow.c` with a small driver using `clang`, `gcc` or `cc` (skip, exit 0, when none is found) and check:
  - k = 1 returns w;
  - k = 0 zeroes the colour bytes and keeps byte 3;
  - k = 0.5 and 2.0 on `0x383838`, `0x404040`, `0x484848` and `0x505050` give the bytes listed in design D3 (`0x2C`, `0x33`, `0x39`, `0x3F`; `0x47`, `0x51`, `0x5B`, `0x65`);
  - the 0xFF clamp (`0xF0F0F0` at k = 2), and alpha kept (`0x80404040`).

## 3. Wrapper

- [x] 3.1 In `src/recomp_manual.c`, add the line `extern void sub_0005B7D0_gen(void);` at column 0 (the form `manual_scan.py` recognises; not in `glow.h`), then `void sub_0005B7D0(void)` with the comment block from design D1/D2/D5:
  - when `!glow_active()`: `RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0_gen); return;`
  - when active: `orig = MEM32(0xADC744)`; `scaled = glow_weight(orig, k)`; if `scaled != orig` store it; call the body through `RECOMP_ABI_CALL` as above; then `if (MEM32(0xADC744) == scaled) MEM32(0xADC744) = orig;` (skipped when nothing was stored).
  - `RECOMP_ABI_CALL` gives the `RECOMP_ABI_CHECK` build's esp and callee-saved checks for free (design D5); no new check.
- [x] 3.2 Regenerate with `blinx2 recomp`. The log says "1 wrapped as sub_X_gen". `git diff --stat src/recomp/gen/` shows only the rename (`recomp_0010.c`, `recomp_funcs.h`, possibly `recomp_dispatch.c`) and `gen.key.json`. Record whether the dispatch entry for `0x0005B7D0` names `sub_0005B7D0` or `sub_0005B7D0_gen` (design, Risks). Never hand-edit `gen/`.
- [x] 3.3 Threads (design D6), one Metal `@attract` run, 60 s, `RECOMP_DEBUG=watch=0xADC744,watch_len=4` plus `RECOMP_GLOW_INTENSITY=0.5`, with a one-shot `[GLOW]` debug line from the wrapper that prints its `g_esp`:
  - place each `[WATCH] ... esp=` line and the wrapper's `esp` on a stack: `guest-main`'s, or a worker's (their `stack top` lines at boot). Record whether all writers share the wrapper's stack.
  - if they do not, switch the store and the restore to `__atomic_compare_exchange_n` on the guest word, and say so in design D6.
  - from the same log, the sequence of values the game writes (every `[WATCH]` line that is not the wrapper's own pair per frame) equals the sequence from a stock run of the same length, timing aside: the fade never saw the scaled value.
- [ ] 3.4 Removed: the esp check is `RECOMP_ABI_CALL` (3.1).
  - Archive note: removed by the spec review, nothing to do.

## 4. Goldens and harness

- [x] 4.1 `analysis/golden/golden.json` env pins `RECOMP_GLOW=on` and `RECOMP_GLOW_INTENSITY=1`.
- [x] 4.2 `scripts/golden.py`: add the `fx.glow` and `fx.glow_intensity` rows to `ENHANCE_STOCK` (the intensity compared as a float against 1), and accept them in `--allow-enhance`. The `--record` refusal is unchanged.
- [x] 4.3 `scripts/test_golden.py` cases:
  - stock line passes;
  - `fx.glow=off` fails;
  - `fx.glow_intensity=0.5` fails;
  - both pass as notes with `--allow-enhance`;
  - a log without the `fx` line, from an older build, is not failed for it.

## 5. Gates (Mac)

- [x] 5.1 `blinx2 build`, then `pytest scripts`. The toolkit changes only in a doc here, so its ctest dirs need not run; run them if that changes.
- [x] 5.2 Metal goldens `@attract`, `@stage1` and `@story` with no key set (`scripts/golden.py`): same verdicts as `main`, and the log shows the stock `fx` line.
- [x] 5.3 Metal frame A/B at `@attract`, flip 1141 (`RECOMP_DEBUG=fb_dump_at=1141`), each in its own run in `runs/glow/`:
  - stock;
  - `RECOMP_GLOW=off`;
  - `RECOMP_DEBUG=poke=0xADC738:0,fb_dump_at=1141`;
  - `RECOMP_GLOW_INTENSITY=0.5`;
  - `RECOMP_GLOW_INTENSITY=2.0`.

  Pass:
  - off ≈ poke within the golden limits (channel mae ≤ 0.5, ≤ 0.5% bad at tol 8); design D2 predicts identical bytes, so record the measured mae;
  - stock − off mean is 12 to 18 levels;
  - the glow layer (frame − off) at 0.5 is 0.40 to 0.60 times stock's layer;
  - at 2.0 it is 1.5 to 2.2 times (the stage clamps near white pull it under 2; design D3); record the measured ratio;
  - edge crops (the spike's `ears` and `fern` regions) are saved for the review.

  If flip 1141 differs between runs in camera or animation (mae > 2 between two stock runs), pick another flip from the spike's runs where two stock runs agree, and say which.
- [x] 5.4 Cost: `RECOMP_TRACE=flip` flips/s and Metal GPU time, stock against `off`, over 60 s of `@stage1`. The rule from CLAUDE.md applies: flag a 25% drop in flips/s.
- [x] 5.5 CPU backend mirror check: one `RECOMP_PB_BACKEND=cpu` run with `RECOMP_GLOW=off` and one with the poke, flip 1141. They agree within the golden limits.

## 6. Gates (Proton)

- [x] 6.1 From this worktree: `blinx2 bench sync`, `blinx2 bench build`, then `blinx2 bench golden` (the D3D11 goldens): same verdicts as `main`. (`blinx2 bench integrate` is for the main checkouts after the merge; it is not this gate.)
- [x] 6.2 D3D11 mirror check: two `blinx2 bench run` runs with `RECOMP_DEBUG=d3d11_dump` (flip 1141 is present 60·19+1, `frame_19`), one with `RECOMP_GLOW=off` and one with `RECOMP_DEBUG=d3d11_dump,poke=0xADC738:0`. They agree within the golden limits. Record the run stamps in this task.

## 7. Docs and follow-ups

- [x] 7.1 Toolkit `docs/runtime/enhance-config.md`: add the `fx.glow` and `fx.glow_intensity` rows to the game-keys table (where `fps.mode` sits), as BLiNX 2 keys. This is docs only, on a toolkit branch.
- [x] 7.2 `TASKS.md`: add F1 (guest-size glow target at render scale, effort M, not chosen by the user on 2026-10-06) and F2 (mode 4). Done 2026-10-07.
- [ ] 7.4 Follow-up (the 4.2/4.3 deviation, accepted by the coordinator 2026-10-06): xboxrecomp-cli reads the game's enhancement keys and stock values from a game.toml table (e.g. `[golden] enhance_stock = { "fps.mode" = "lock30", "fx.glow" = "on", "fx.glow_intensity" = "1" }`, with the log pattern per key) instead of hardcoding `fps.mode` in `ENHANCE_STOCK`; then `--allow-enhance fx.glow=off` works and cat's `fx.*` rows move there.
  - Archive note (2026-10-07): open, moved to TASKS.md (a CLI change).
- [ ] 7.3 A Fable review of the merge; fixes go back to this branch's agent.
  - Archive note (2026-10-07): not done yet; the Fable merge reviews are batched (Fable quota). Listed in TASKS.md.

## Results (2026-10-06, Mac)

Runs are in `xbox-recomp/runs/bloom/glow-toggle/` (crops in `crops/`; the three directories whose names contain spaces are a broken first batch, ignore them).

- 3.2: `blinx2 analyze` + `blinx2 recomp` log "1 wrapped as sub_X_gen". At toolkit b0eb653 the call site and the dispatch entry both named `sub_0005B7D0_gen`, so the wrapper never ran (design D1, finding). With toolkit 825fde2 the call at 0x0005B569 is `RECOMP_ABI_CALL(0x0005B7D0u, sub_0005B7D0)`, the dispatch entry is `sub_0005B7D0`, and `recomp_funcs.h` declares both names.
- 3.3: every write to 0xADC744 (`watch`, `ab-k05watch`, `ab-stockwatch`, 60 s each) is on guest-main's stack (esp 0x038BFC98/0x038BFC9C for the game, 0x038BFD00/0x038BFD04 for the wrapper's store and restore; the worker stacks are at 0x03EE9FF0 and up). No atomics needed. The game-written values, without the wrapper's pairs, are the same in both runs (0x404040, 0x3F3F3F, 0x404040); the fade's step-down (seen at flip 1658 in an earlier stock run) did not occur in either 60 s run, so the stepping case was not exercised.
- 4.2/4.3: deviation, see 7.4 (the harness is in the CLI).
- 5.1: `blinx2 build` clean (no warnings in the changed files). `uv run pytest scripts` 30 passed; ruff check and format clean. Toolkit `pytest tools/recomp tools/disasm` 594 passed (2 new wrap cases). The toolkit change is Python only, so the POSIX ctests were not run.
- 5.2: Metal goldens with no key set, `[ENHANCE] fx.glow=on fx.glow_intensity=1`: attract, stage1 and story pass (all CLOSE, as on main). One story run was INCOMPLETE (story-hub anchor not checkable) while another agent was building; the rerun passed.
- 5.3: `@attract` flip 1141 (stock3, off, poke, k05, k20, one batch). off vs poke: identical bytes (mae 0.000). stock - off: mean 14.77 levels. Layer ratio: 0.506 at 0.5, 2.008 at 2.0. Flip 1021 agrees (16.85 levels, 0.531, 2.012). Two stock runs: mae 0.06. Flips under load drift to a different camera (an earlier batch); a quiet batch did not. Stage 1 (golden flips, `s1-*`): at 841 off -13.75 levels, 0.5 gives ratio 0.505, 2.0 gives 2.00.
- 5.4: `@stage1` 60 s, metal_prof: stock 35.31 flips/s, GPU 3.080 ms/flip; off 35.40 flips/s, 3.098 ms. No cost.
- 5.5: CPU `@stage1` flip 841, off vs poke: mean difference -0.06 levels (the glow layer is about 14), mae 2.0-3.3 with 8% of pixels off. The CPU runs do not hold the scripted timeline (same as the Metal run's frame, mae 50-65), so this is timing noise, not glow; it is outside the golden limits only for that reason.
- Backends: the wrapper changes only the guest word that becomes the quad's vertex diffuse; it has no backend code, so CPU, Metal and D3D11 get the same draw. Metal shows off == poke byte for byte. 6.x: see below.

## Proton results (2026-10-07, cat f6f05ef + toolkit ae24c58 = main f587514 / portability 4bfee1c merged in)

- the Linux/Proton host tree `~/xbox-recomp-glow` (shared llvm-mingw and prefix), synced from wt/bloom with the gen regenerated against toolkit 825fde2 (unchanged in tools/recomp since). `blinx2 bench golden`: every Proton ctest passes; D3D11 golden passes (attract-title CLOSE, attract-cliff EXACT, the stage1 and story frames CLOSE) with `[ENHANCE] fx.glow=on fx.glow_intensity=1`; runs 20261006-234909, -235029, -235220.
- 6.2: D3D11 `@attract` with `RECOMP_GLOW=off`, flip 1141 (run 20261006-235614): the log shows `[GLOW] weight 003F3F3F -> 00000000`; stock - off is 14.73 levels (Metal 14.77). The D3D11 off frame vs Metal off and Metal poke: mae 0.20/0.20/0.16, 0.27% of pixels off by more than 8. Frames in `runs/bloom/glow-toggle/d3d11/`. No separate D3D11 poke run: Metal showed off == poke byte for byte, and D3D11 off matches it.
- Mac rerun after the merges: build clean, `pytest scripts` 25 passed, ruff clean, Metal goldens attract/stage1/story pass (`final-metal-*`), Metal off at 1141 unchanged (`final-off`).
