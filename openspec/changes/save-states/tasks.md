## Context

- **Worktrees:** per phase, `wt/save-states-<phase>/{cat,xboxrecomp,xboxrecomp-cli}`.
  Toolkit branches come off `posix-host/portability`.
- **Gates:** the CLAUDE.md gates, plus D7 of `design.md`.
- **Locks:** every Mac run takes `lockf` and `notes/mac-run-lock.sh`, with
  `SDL_AUDIODRIVER=dummy`. Proton runs go through `blinx2 bench`.
- **Data:**
  - Raw dumps go to `runs/save-states/`.
  - States go to the shared store `states/<slug>/` beside `bench-logs/`.
  - Neither is committed, published, attached to the tracker or put in a
    `bench-logs` export.

## 0. Facts

- [ ] 0.1 Dump the contiguous window, the NV2A and MCPX apertures and RAM at
  three points (attract, stage 1, story), in BLiNX 2 and Burnout 3.
  Record the non-zero pages and the zlib-1 and LZ4 sizes in `design.md`.
- [ ] 0.2 Add a `RECOMP_STATE_TRACE=sites` probe (throwaway, shadow-free).
  At each flip, use the thread-dump walker to log every guest thread's
  chain. Collect 5 minutes of `@stage1-enemies`, the story scene and a
  Burnout 3 race. Count parks by kind (call, tail, back edge, spin, host
  sleep) and the critical sections and mutants held at the flip, then
  draft `config/resume_sites.json` from the logs.
- [ ] 0.3 Lifter audit: list every C local besides `ebp` that is live
  across a call site or a back edge (flags such as `_cf`, temporaries,
  SEH), and confirm that flag temporaries are re-derived after calls.
  Count the functions with a guest `setjmp` or SEH frame on a parked
  chain, and the tail calls on parked chains.
- [ ] 0.4 List the kernel calls seen parked and classify each one as
  restartable or not, and as pending or returned. List every wait bridge
  that needs the save handle, and every wait that falls back to
  `XBOX_TO_NATIVE(object)`.
- [ ] 0.5 Measure the title's `UDATA` and `TDATA` sizes in both games
  with real progress saved.
- [ ] 0.6 Burnout 3 safe point: try `RECOMP_GUEST_LOCK=1` on Burnout 3
  (Metal goldens and a speed check). Record option (a), turning the lock
  on as its own gated change, against option (b), a lock-independent
  stop-the-world path, and the pick. (a) is recommended (D2).
- [ ] 0.7 Static inventory: every file-scope and TLS static in each
  subsystem file (kernel, HAL, memory layout, pushbuffer, backends, APU,
  USB, cat's manual overrides), classed as serialized, rebuilt or
  irrelevant. Check the host-derived thread IDs in guest thread objects
  and TIBs. Phase 2 is gated on this list.
- [ ] 0.8 **Go/no-go.** Simulate a save at every sampled flip and report
  the refusal rate and reasons per game. Go at 95 % or more of saves
  succeeding within `RECOMP_STATE_RETRY` flips; otherwise take the
  numbers to the user before phase 1.

## 1. Lifter and clocks (toolkit)

- [ ] 1.1 Shadow stack: one TLS struct with the depth and a fixed array of
  entries (`fn`, `site`, resolved `callee`, `ebp`, `esp`, `kind`), emitted
  by `lifter.py` for direct and indirect calls, tail calls
  (`RECOMP_ITAIL`, `RECOMP_FALLOFF_TAIL`), `RECOMP_BACK_EDGE` and
  `RECOMP_SPIN_WAIT`. Overflow refuses saves. Guest `setjmp` records and
  restores the depth. Measure the TLS layout on the Mac first. Add pytest
  cases in `tools/recomp`.
- [ ] 1.2 Resume entries for listed sites: a guarded prologue switch with
  `call`, `tail`, `edge` and `spin` cases and `recomp_resume_*` helpers in
  `recomp_types.h`. Re-issue through the stored callee; `PUSH32` only at
  the innermost pending kernel call. Store or refuse live locals and flag
  temporaries. A save-time chain check (`esp` decreasing,
  `MEM32(esp) == site`). Add pytests on fixture functions.
- [ ] 1.3 The `restartable` list in `config/resume_sites.json`: the lifter
  wraps each call to a listed manual override in the pending phase word.
  cat lists `0x002E0DB0` (data only, no override source change). A
  manual override mid-chain refuses the save.
- [ ] 1.4 Guest-clock base: QPC, tick count, interrupt and system time,
  `rdtsc`, vblank grid, timer due times. Add a ctest that moves the base
  and checks that every reader agrees.
- [ ] 1.5 `XBOXRECOMP_STATES` CMake option, default ON (the user,
  2026-10-22, subject to 1.6), part of the gen key and passed by
  `blinx2 analyze` and `recomp`. The OFF build stays buildable and is
  built by the gates.
- [ ] 1.6 **Default-ON gate.** ON against OFF on Metal (Mac) and D3D11
  (Deck, Proton), stock settings, the golden scenarios: frame CPU time
  median and p99, guest-CPU held time per frame, `.text` growth. Default
  ON only if frame CPU time rises 3 % or less on both backends and the
  goldens are frame-identical; otherwise ship OFF and report the numbers
  to the user. Also measure listed sites against all sites.

## 2. Fixtures (toolkit, cat, CLI)

- [ ] 2.1 `src/state/`: the container (header, chunks, CRC, sentinel), a
  field-by-field fixed-width encoding for every chunk (no raw host
  structs), a measure mode, and ctests on synthetic chunks, including a
  state written on one host and read on another.
- [ ] 2.2 Quiesce (D2), in its order:
  - refuse every state key with `RECOMP_GUEST_LOCK` off;
  - `on_flip` arms the request; the next kernel call on the CPU holder,
    after `xbox_IrqSafePoint()`, runs the save;
  - freeze CPU hand-outs (the 2 ms poll, the guest_sched 4 s valve);
  - drain the GPU with the device threads live;
  - stop the device threads at their edges;
  - classify through the per-thread save handle in every wait bridge,
    each thread writing its own TLS registers and chain;
  - refusals with reasons (raised IRQL, the dispatch gate held, a callback
    in a host frame, chain checks), and the retry.
- [ ] 2.3 Chunks, from the 0.7 inventory:
  - `MEM`, `APER` (with the ack thread's mirrors), `ALOC`;
  - `THRD`, `HAL`, `CLCK`;
  - `KOBJ`, with guest-view bookkeeping (type, flags, count, owner,
    recursion) in every create, release and wait bridge, critical-section
    shadows included;
  - `FILE`, with the open flags and an `OPEN_EXISTING` reopen;
  - `PGRA`, `SURF`, `APU`, `USB`;
  - `SAVE`: the title's `UDATA` and `TDATA` files, a staged swap on load,
    and the 16 MB cap.
  Each one gets a round-trip ctest.
- [ ] 2.4 Start-time load (D5) with `RECOMP_STATE_LOAD`: the lazy host
  init replayed (display mode, interrupts, APU threads, OHCI), each new
  thread writing its own TLS and re-acquiring its mutants and critical
  sections, a barrier before any thread resumes. Env rows with their tiers
  (`RECOMP_STATE_SAVE`, `_LOAD`, `_RETRY`, `_SAVE_MAX` CONFIG,
  `RECOMP_STATE_TRACE` TRACE) in the toolkit's table and cat's
  `docs/env.md`.
- [ ] 2.5 Surfaces (D4, cross-backend): Metal syncs every host-only RT and
  restores page protection, blits private depth and stencil to a shared
  buffer and back; D3D11 stages colour and uploads depth by
  `CopyResource`, checked on DXVK; the CPU backend's `SURF` no-op and its
  TASKS.md gap.
- [ ] 2.6 Toolkit: `xbox_StateRequest(path)` and `RECOMP_STATE_SAVE=<file>@flip N`.
  cat (data): `config/states.json` with `stage1-walk` and `attract`, and
  `config/resume_sites.json`. cat (the one piece of game code): the
  `savestate NAME` glue in `src/pad_input.c`, a call to
  `xbox_StateRequest`.
- [ ] 2.7 The shared fixture store `states/<slug>/<name>/<key>.xbrstate`
  beside `bench-logs/`, keyed by the XBE sha, the chunk versions and the
  resume-site coverage; resolved like golden frames; known to
  `notes/cleanup-derived.py`. Fixture runs point `RECOMP_SAVE_DIR` at an
  empty scratch directory and take the title's saves from the state's
  `SAVE` chunk (no separate `save/` copy). Full-prefix goldens stay the
  merge gate; `state make` again for changes to boot or load code. Add `*.xbrstate` and `*.xbrslot` to the public
  export and audit refusals.
- [ ] 2.8 CLI:
  - `xbr state make|list|check`;
  - `--from-state` on `golden run` and `bench run`;
  - synthetic tests;
  - a release, then cat's pin bump.
- [ ] 2.9 D7.1 round trip and D7.2 continuation on Metal, and on D3D11 via
  `blinx2 bench`, with Mac-made states; a cross-backend load each way.
- [ ] 2.10 Burnout 3: the 0.6 safe point, a resume-site list and one race
  fixture through 2.9.

## 3. In-session load

- [ ] 3.1 A `longjmp` unwind point in `bridge_thread_main` and on the boot
  thread. Check, per restartable call, that no bridge lock is held.
- [ ] 3.2 Host object teardown and re-creation: every host sync object,
  critical-section shadows included, destroyed and re-created, since the
  `longjmp` abandons ownership the reused threads still hold. Reuse threads, or create
  and exit them.
- [ ] 3.3 An undo state with the saves on disk, and rollback of both on a
  failed load.
- [ ] 3.4 D7.3 soak: 50 cycles with handle and texture counts flat.

## 4. Quick save (toolkit, behind `XBOXRECOMP_ENHANCE`)

- [ ] 4.0 Free F5 and F9 for the hotkeys (the user, 2026-10-22: "Save
  states keep F5/F9"). Both keys ship with other uses today: the
  toolkit's `input.mouse_release_key` defaults to `F9`, and cat's
  `camera.free_reset_key` defaults to `F5`. This task lands first in
  phase 4, ahead of 4.2, as its own small merge (toolkit, then cat).
  - Toolkit, the mouse release moves to `F8`:
    - `mouse.c`: the `release_key` default becomes `0x77`;
    - `enhance_input.c`: the knob default `"F8"`; in `reserved_use`,
      `0x77` frees the cursor, and `0x74`/`0x78` are the quick save and
      quick load (`[states]`). The "default is not a clash" exception
      moves to `0x77`;
    - docs: `docs/runtime/config.md` (the `input.mouse_release_key` row,
      the reserved-key paragraph and its sample warnings), the README
      input paragraph and `src/input/README.md`;
    - ctests in `tests/enhance_cfg`: `mo.release_key == 0x77`; binding
      `y = "F8"` warns about the release key; `y = "F9"` warns about the
      quick load; `walk_key = "F8"` warns that it is the release key.
      In `tests/input_keyboard`: F8 frees and grabs the cursor, and F9
      no longer does.
  - cat:
    - The free-camera reset moves to `Home`, and the freeze to `End`
      (orchestrator, 2026-10-22, follows from the user's F8 choice; the
      user may override). It acts only while flying,
      which `free_cam_action_reset` already ensures (`s_flying`), and
      Home is in no default key map, so the key does nothing outside
      free-cam. The freeze is gated on `s_flying` in
      `free_cam_action_freeze` the same way. The `free_camera.c`
      defaults become `"Home"` and `"End"`.
    - `packaging/config.default.toml`: `free_reset_key = "Home"`,
      `free_freeze_key = "End"` and `mouse_release_key = "F8"`.
    - Doc rows: `docs/env.md` (the `RECOMP_CAMERA_FREE_RESET_KEY` row,
      the `camera.free_*` key row and the `input.mouse_release_key`
      row) and `docs/input.md` (the F9 lines, now F8).
    - `scripts/test_free_camera.py`: the stock defaults `"Home"` and
      `"End"`, and a config-default check that `free_reset_key` is
      `Home` and `free_freeze_key` is `End`, neither on F5, F8 or F9.
- [ ] 4.1 The D9 slot store under `<save root>/states/<title_id>/`
  (`slots.json` order, one `.xbrslot` per slot, `undo.xbrslot`, atomic
  writes), with one slot, `quick`. ctests for the store with N slots.
- [ ] 4.2 A save hotkey and a load hotkey in the enhancements TOML
  (`[states]`; quick save `F5` and quick load `F9` by default, the user,
  2026-10-22; an optional pad chord). Blocked on: 4.0.
- [ ] 4.3 Vendored LZ4, a thumbnail, and compression off-thread.
- [ ] 4.4 A load notice that the title's saves roll back with the slot,
  and a "can't save here" toast after the retries.
- [ ] 4.5 A manual pass on the Mac, the Deck and native Windows (the
  user's OK for the boot switch), plus D7.2 on native Windows. Add a players
  CHANGELOG entry that says slots hold save data and stay private.

## 5. Slot manager (blocked on the mod overlay menu)

The menu half of this phase moved to `enhance-menu-preview` phase 3G,
the Save states page (the user, 2026-10-22). That change owns
the UI work. This phase keeps the store operations the page calls, the
CLI verbs and the manual pass.

- 5.1 *Moved to enhance-menu-preview 3G.1* (the slot list in the overlay
  menu: thumbnails, labels, times).
- [ ] 5.2 The store operations, with no UI: rearrange (`slots.json`
  order), delete, and export or import of one slot to a file. Import
  checks the header and refuses another XBE. Exports go to
  `<save root>/exports/<title_id>/` by default (`[states] export_dir`,
  the user, 2026-10-22). *The UI half (the rows, the confirm, the Open
  folder row and the SDL3 dialog) moved to enhance-menu-preview 3G.1
  and 3G.2.*
- [ ] 5.3 CLI: `xbr state slot export` and `xbr state slot import`, with
  synthetic tests. Blocked on: 5.2. It does not need the overlay.
- [ ] 5.4 A manual pass on the Mac, the Deck and Windows. Blocked on:
  enhance-menu-preview 3G merged, and 5.3.
