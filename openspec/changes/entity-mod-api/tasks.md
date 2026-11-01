Worktrees: cat `wt/entity-api/cat` (`feat/entity-api`
off cat main 5cdea83); toolkit `wt/entity-api/xboxrecomp` (new branch off
`posix-host/portability`, made at the go). Runs under
`xbox-recomp/runs/entity-mod-api/`. Mac jobs under
`lockf -t 3600 ~/.recomp-mac.lock`, `SDL_AUDIODRIVER=dummy`; PC jobs under
its lock. Material: `spike/entity` 9770730 (`src/ent_spike.c`),
`spike/enemy-respawn` 4da65a8, `runs/entity-spike/`, `runs/enemy-respawn/`.

## 1. Toolkit: mod API v6 (D1)

- [x] 1.1 Move the `IrqRegs` save and restore from `kernel_hal.c` into a
  shared `recomp_regs.h`; the DPC path uses it unchanged.
- [x] 1.2 `guest_call` and `guest_alloc` in `src/enhance/mod.{c,h}`,
  `XBOX_MOD_API_VERSION` 6; refusal off the guest thread.
- [x] 1.3 ctest: registers restored bit for bit, arguments placed, frame
  aligned, refusal off the guest thread, one block per mod.
- [x] 1.4 `docs/runtime/config.md`, "Mods": the two calls.
- [ ] 1.5 Gates: Mac build, `tests/posix_ctest.sh` 0 FAIL,
  `sh notes/build-all.sh` with `TOOLKIT=` (PC leg with
  `WIN_BUILD_HOST=bench host-win` when it is on Windows). Review; merge
  by the orchestrator before section 4.
  Gates passed on `feat/mod-api-v6` 48b6af35 (ctest 0 FAIL, build-all
  every game on macOS and Windows); the review and merge remain.

## 2. Static audits (open questions 4-6)

- [x] 2.1 Every caller of `sub_0004EE20`: does it check the count first?
  Set `reserve` (open question 5); names into `config/symbols.toml`.
- [x] 2.2 The class allowlist from every `0x4921E8` entry and the extra
  sets `0x4923C8`/`0x4925A8`; the spawner class's nested spawn checked
  (open question 6).
- [x] 2.3 Callers of `sub_0004F910`: does anything read `0xADA9B0` for
  enemies (open question 4)?
- [x] 2.4 Class 1's variant count at `0x4AFCD8`.

## 3. cat: the API and the mod

- [x] 3.1 `src/ent_api_logic.{c,h}`: pure C over a memory view: list walk,
  handle check, guard order (D4), record table and area-setup free (D5),
  placement copy and respawn nibble, override apply and restore (D6).
- [x] 3.2 `src/ent_api.{c,h}`: the public calls (D3), the request ring,
  the two hooks, the per-frame liveness and stale-record check, guest calls
  through `guest_call`, the record block through `guest_alloc`.
- [x] 3.3 `src/entities_mod.c`: descriptor (`enable`, `hp_scale`, controls
  `spawn`, `kill`), the three rows, `on_enable`, toasts (D8); the
  `entities_proof` debug driver.
- [x] 3.4 `src/main.c` mod table, `CMakeLists.txt`.
- [x] 3.5 Env rows `RECOMP_ENTITIES`, `RECOMP_ENTITIES_HP_SCALE`,
  `RECOMP_ENTITIES_SPAWN_KEY`, `RECOMP_ENTITIES_KILL_KEY` (CONFIG) and
  `entities_proof` (DEBUG) in `src/env/recomp_env_game.h` and
  `docs/env.md`; commented keys in `packaging/config.default.toml`;
  `game.toml` `enhance_stock` gains `"mods.entities.enable" = "off"`.
- [x] 3.6 `game.toml` `[mods] hook_functions` gains `0x0004E700` and
  `0x000606F0` (D9); `blinx2 analyze`, then `blinx2 recomp`; commit gen and
  `config/hook_functions.json`. Done as D9 now reads: `0x0004E700` only
  (with `no_st0`), `stage_area_setup` through the `recomp_manual.c`
  wrapper; gen is untracked, so only `config/hook_functions.json`.
- [x] 3.7 `scripts/test_entities.py` (design, Tests).

## 4. Live proof (needs section 1 merged and the cat pin moved)

- [ ] 4.1 Metal, `@stage1`, steps 1-7 of the design's proof; frames and the
  TSV in `runs/entity-mod-api/metal/`. Skipped: since 2026-10-30 Mac builds
  and Metal runs happen only before release rounds; the PC runs (4.2) stand.
- [x] 4.2 Native Windows on the PC (when it is up on Windows; never switch
  the boot): the same steps.
- [x] 4.3 Open question 1: a kill under PAUSE, SLOW, FF and REC; relax the
  guard only for those that hold after the control ends and after a REW.
- [x] 4.4 Open question 3: REW right after an area change; no stale-record
  line. Failed (run E4): a death retry's area setup frees a record the copy
  still uses; needs a D5 decision. Passed with D5 option (a) (runs E6 at
  cat 4db1e19, E7 at 1af329f, exe d6a31506392f): the copy goes off the
  list one frame after the retry (n 31 to 30), the REW 30 frames later
  restores it every frame it holds the ring's oldest frame and the sweep
  takes it off each time (n stays 30 in every sample, through play 7995),
  no stale-record line. E6 logged 270 rewind lines; 1af329f rate-limits
  them to one per 300 (E7: one line).
- [x] 4.4a D5 decided (a retry removes the API's copies; records freed only
  on a full walk and never while referenced) and implemented, with unit
  tests for both rules. A kill the game ignores answers `ENT_IGNORED` (D7).
  Rerun on the PC (cat f1ac875, exe c189d5432991): the retry sweep works
  (run E5), but a REW right after the retry brings the swept copy back
  (design, open question 3 and Risks); 4.4 stays open. Smoke (run A6):
  spawn, attack, kill to 0xA as before. Dormant kill (run A7) answers
  `ENT_IGNORED`.
- [x] 4.4b D5 option (a): the sweep runs every frame, unlinks any listed
  copy of a marked or retired record, and retired records are not reused
  until the next area setup; it reads only the used bytes when none is
  marked or retired. Running out of records answers `ENT_RECORDS` with
  nothing written (unit test `test_record_overflow`). Smoke (run A8, cat
  4db1e19): spawn, attack, kill to 0xA, the same as A6.
- [x] 4.5 Open question 7: one spawn on a Tom Tom stage.
- [x] 4.6 `fill` on 5-1: the time-record frame size with a full list;
  drop any class that pushes it past the budget.
- [x] 4.7 Mod off: `[ENHANCE] mods=none`, no `[MOD entities]` writes, no
  allocation. Descriptor dump lists the mod, its settings and controls.
- [x] 4.8 Post the proof on the tracker item (as text; frames stay in `runs/`) and update the
  design's open questions with what the runs settled.

## 5. Gates

- [x] 5.1 Mac build; `uv run pytest scripts`; `uv run ruff check . &&
  uv run ruff format --check .`.
- [ ] 5.2 Metal goldens, mod off, `RECOMP_MENU=0`: attract, stage1, story.
  Skipped: Metal goldens run before release rounds only (2026-10-30).
- [x] 5.3 Native Windows golden on the PC (`BENCH_HOST_OS=windows`) when it
  is on Windows; otherwise at its next Windows boot. Mod off, exe
  c189d5432991 (cat f1ac875): attract pass-with-known, stage1
  pass, story pass-with-known. Again at 4db1e19 (exe 2fff3d14d608) and
  1af329f (exe d6a31506392f): the same verdicts; 35.6, 33.5 and 49.5
  flips/s at 1af329f.
- [ ] 5.4 Proton on the Deck (`blinx2 bench golden`): non-blocking.
  Not run: the Deck did not answer over ssh (2026-10-31 morning). At
  f1ac875 its lock was free, but 4.4 still needs a change, so the Deck
  golden waits for the tip that merges. Skipped at 1af329f: PC gates
  suffice (the coordinator, 2026-10-31).
- [ ] 5.5 Review; its fixes back on this branch.
  - [x] 5.5a HIGH 1: a second retry from the same checkpoint. The sweep
    unlinks a listed copy of a free record too; retired records are freed
    only at a stage start (the setup's 0x6324D call). Logic test with two
    ages and a re-listed copy; D5 and D10 corrected.
  - [x] 5.5b MEDIUM 2: switched off after a spawn, the marking and the
    sweep keep running (no requests); sessions that never spawned stay
    stock. API test.
  - [x] 5.5c MEDIUM 3: kills in flight checked for room before the damage
    call (`ENT_BUSY`); the queue holds 64. API test.
  - [x] 5.5d LOW: kills wait 4 enemy updates; hp clamped to 1..9999; NULL
    pointers answered; CONTIG values asserted against `kernel.h`; cycle and
    early-out tests.
  - [x] 5.5e PC (cat ce63aae, exe 45f9a3f6723f, native llvm-mingw on the
    PC): the double retry (E8b, `stage1-2-retry2.txt`,
    `spawn:1+rewarea:30+setuponly:2`) passes, see the design's open
    question 3. E8 (first try) never died a second time: after the retry
    Stick stands out of the monsters' reach, so the script walks him back
    in. E7b: the copy off one frame after the retry, n 30 through the REW
    and to the end, one rewind line. A8b: spawn and kill done as in A8.
    Windows golden, mod off: attract pass-with-known, stage1
    pass, story pass-with-known; 35.8, 33.4 and 49.6 flips/s.
- [ ] 5.6 After the merge: the PC-built Windows exe through
  `blinx2 bench integrate --golden`; `TASKS.md`; follow-ups filed
  (placement respawn overrides, BLiNX 1 layouts, a save-state hook to drop
  queued requests once `save-states` lands).
