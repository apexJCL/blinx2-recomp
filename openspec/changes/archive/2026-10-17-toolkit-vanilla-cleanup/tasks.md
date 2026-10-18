# Tasks

Worktrees: `wt/vanilla/{xboxrecomp,cat,b3}`, all on `chore/vanilla-cleanup`
(toolkit off `posix-host/portability`, cat and b3 off `main`). Runs under
`xbox-recomp/runs/vanilla/`. Mac builds with
`DEVELOPER_DIR=/Library/Developer/CommandLineTools`, runs through
`notes/mac-run-lock.sh`, `SDL_AUDIODRIVER=dummy`.

## 1. Text (one toolkit commit)

- [x] 1.1 A1: `docs/runtime/enhance-config.md` keeps the five keys and a
      neutral game-key example; the BLiNX 2 rows and paragraphs go.
- [x] 1.2 A2, A3: `recomp_env.h` header and the two help strings.
- [x] 1.3 A4: round example VA in `spin_waits.py` and `04-lifting.md`.
- [x] 1.4 cat `docs/env.md`: the "Enhancements file" paragraph (D9).

## 2. Fixtures (one toolkit commit)

- [x] 2.1 A5 `test_spin_waits.py`, A6 `tests/window_title`, A7
      `tests/enhance_cfg`, A8 `tests/rt_alias`, A9 `tests/kernel_missing_report`
      and `tests/kernel_file_status`, A10 `tests/proton_run.sh`.
- [x] 2.2 H2: oracle files `*_a374605.c` -> `*_frozen.c`, CMakeLists and
      header comments.

## 3. Comments (one toolkit commit)

- [x] 3.1 Kernel, APU, platform rows of audit 3.3 (D1). `kernel_hal.c`,
      `kernel_bridge.c`, `kernel_pacing.*`: comment lines only.
- [x] 3.2 Renderer rows, and H3 in `nv2a_pb_state.h`.
- [x] 3.3 Tools and tests rows (`functions.py`, `lifter.py`,
      `flag_fallbacks.py`, `test_test_as_cmp.py`, `kernel_guest_cpu`,
      `d3d11_backend_smoke`, `vblank_ack`).

## 4. Knobs (one toolkit commit)

- [x] 4.1 C1 `kernel_prof.c` code bounds (D2).
- [x] 4.2 C5 `present_stale` (D3), C7 `tex_cache` (D4), C8 `zbuf_slots`
      (D5): rows at the tail of `RECOMP_ENV_KEYS`, read once into statics.
- [x] 4.3 C9 detector kwargs and `tools.disasm` flags (D6).
- [x] 4.4 cat `docs/env.md` rows for the three keys.

## 5. Policy (toolkit, cat and b3 commits)

- [x] 5.1 C3 toolkit default `auto` (D7); cat and b3 drop their override.
- [x] 5.2 C2 `one` spelling (D8); cat and b3 `D(GUEST_CPUS, "one")`;
      `kernel_thread.c` comment reworded; `docs/env.md` rows.

## 6. Gates (Mac)

- [x] 6.1 cat Mac build; POSIX ctest dirs; `pytest tools/recomp tools/disasm`;
      cat `uv run pytest scripts`, ruff check and format.
- [x] 6.2 `./blinx2 recomp`: `gen/` unchanged.
- [x] 6.3 Metal story golden and stage1 golden via the CLI runner: both pass (`runs/vanilla/golden-metal/`).
- [x] 6.4 `git merge-tree` against `fix/mac-one-cpu`: one trivial conflict per repo (recomp_env.h adjacent rows; env.md counts and adjacent rows), see notes/vanilla/NOTES.md.

## 7. Hand-back

- [x] 7.1 `notes/vanilla/NOTES.md`; TASKS follow-ups H1, H4, the disasm
      flags in `game.toml`; Proton list: BLiNX 2 golden, Burnout 3 boot and
      audio.

## 8. Proton (orchestrator, the Linux/Proton host)

- [ ] 8.1 BLiNX 2 `blinx2 bench golden` (D3D11).
- [ ] 8.2 Burnout 3 boot and audio: `apu_dsp_ack=auto` now from the toolkit default, `guest_cpus=one` from the game default; both should read as today.
