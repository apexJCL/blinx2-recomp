## Context

- **Worktrees:** `wt/game-reset-impl/{cat,xboxrecomp}`. The toolkit branch
  comes off `posix-host/portability`; the cat branch carries `main.c`, the
  game hook, the env rows and the automation reason.
- **Gates:** the CLAUDE.md gates, plus D8 of `design.md`.
- **Locks:** Mac runs take `lockf` with `SDL_AUDIODRIVER=dummy`, except
  the hand checks that need sound, which need the user's go. PC runs take
  `D:\bench\.bench-lock`. Deck runs go through `blinx2 bench`.
- **Data:** run logs and frame dumps go to `runs/game-reset/`; saves used
  in the hand checks stay on the hosts, never in a commit or on the
  tracker.
- **save-states** stays parked. Phase 1 here builds the unwind its phase
  3 plans; its tasks 3.1 and 3.2 then point at this layer.
- **Scope (the user, 2026-11-04): BLiNX 2 first.** Phases 1 to 5 build
  the toolkit layers game-agnostic but adopt and verify them for BLiNX 2
  only. Tasks 3.5 and 5.6 are follow-ups outside this scope.

## 0. Facts: a milestone of its own (go/no-go)

Phase 0 is a separate milestone (the user, 2026-11-03: start it now). It
merges on its own, ahead of any reset code, and is useful even on a
no-go: the statics list and the probe serve save-states too. Its own
branches: `wt/game-reset-p0/{xboxrecomp,cat}`, toolkit off
`posix-host/portability`. It merges as two squash commits (toolkit, then
cat), each with a review. Nothing in it changes stock behaviour.
The toolkit merge also runs `sh notes/build-all.sh` with its worktree
(BLiNX 2, BLiNX 1, KUF on macOS and Windows), as every toolkit merge
does.

- [x] 0.1 The state audit (toolkit, reading only), classified keep,
  reset or constant, each with the module hook that will reset it:
  - file-scope statics in `src/kernel`, `src/d3d`, `src/input`,
    `src/apu`, `src/audio` (DSound HLE, the WMA decoder), `src/video`,
    `src/usb`, `src/nv2a`, `src/enhance`, `src/platform` and the Metal
    and D3D11 backends;
  - function-local statics (about 440 to 580 at `11e099c2`);
  - thread-local state (`RECOMP_TLS`, `__thread`, about 75 to 90);
  - `INIT_ONCE` guards and their kin (about 55), each marked as one whose
    init must run again or not;
  - non-static globals that hold run state (`g_apu_state`) and statics
    named like globals (`g_nv2a_ack_stop`, `g_scanned_put`);
  - the host-half inits that write guest memory (the thunk patch,
    `kernel_data_init`, TIBs and worker stacks, the APU windows), each
    marked for the D5 band 9 split.
  Committed as `docs/reset-statics.md`.
- [x] 0.2 `tools/reset_statics.py` (toolkit): lists, for a tree or a
  diff, every kind 0.1 covers (file-scope and function-local statics,
  thread-locals, `INIT_ONCE` guards, non-static globals) and fails on one
  missing from `docs/reset-statics.md` (the toolkit's, or a game's own
  with `--doc`); its pytest. Gate: `pytest tools/...`.
- [x] 0.3 The thread inventory (toolkit, reading plus one
  `RECOMP_THREAD_DUMP` run of BLiNX 2 in attract and stage 1): every host
  thread, its creator, its loop head and how it will pause (D2 step 3);
  every host call a guest thread can block in outside a wait bridge (host
  reads, the host FMV path when `RECOMP_FMV_HOST` is on), each with its
  way out. It confirms whether any current game creates threads through
  `xbox_PsCreateSystemThreadEx` (`kernel_thread.c:119`, role
  `xbox-thread`) and not only `bridge_PsCreateSystemThreadEx`. Committed
  as `docs/reset-threads.md`.
- [x] 0.4 The wait bridges (toolkit, reading): every blocking bridge
  (`KeWait*`, `NtWait*`, `KeDelayExecutionThread`, critical sections,
  mutants, semaphores, the guest CPU lock, APC delivery, `Sleep`), each
  with the line where it changes guest state after its wait. A section of
  `docs/reset-threads.md`.
- [x] 0.5 Generated code (reading, with 0.2's script): no host statics
  outside the dispatch table, in BLiNX 2 and Burnout 3.
- [x] 0.6 Games (reading, with 0.2's script): the state in cat's
  `recomp_manual.c`, `pad_input.c`, `pad_slots.c`, `save_seed.c` and the
  10 mods (cat has no `src/fixes`), and the guest half of cat's
  `host_main` (the save seed stays in the host half, D6); for each mod,
  whether its `needs` names every guest hook, poke and state read it
  makes (D6a); the same split for BLiNX 1's `main.c`. Committed in cat as
  `docs/reset-statics.md`.
- [x] 0.7 The stop probe (toolkit, merged, DEBUG-tier and off by
  default): a `reset_probe=<flip>` key with its own flag,
  `g_xbox_reset_probe`, checked at the top of `xbox_GuestCpuPreempt`
  **before** its three early returns (the deterministic path, `!t_held`,
  the lock on with no waiter; `kernel_guest_cpu.c:1314-1330`), and in
  `xbox_SpinWait`, `xbox_SpinWaitKick`, the CPU lock acquire and the
  bridge entries. At that flip it raises the flag and logs, for each
  guest thread, the time until it reaches its first stop point; a thread
  already blocked in a wait bridge or queued on the CPU lock at the flip
  counts as stopped at 0. Then the flag drops and the game runs on. No
  unwind. A ctest for the log. Runs, 20 samples each over attract and
  the stage or race: BLiNX 2 (lock on) on Metal and on D3D11, Burnout 3
  (lock off) on D3D11. It touches the runtime, so its merge runs the
  BLiNX 2 goldens (Metal, D3D11 native). Its cat commit adds the
  `reset_probe` row to `docs/env.md` (Debug tier, the count 136 to 137),
  or `scripts/test_env_doc.py`'s tier counts fail.
- [x] 0.7a The DSP JIT keying (toolkit, reading `apu_dsp_emu.c`,
  `apu_dsp_run.c`, `apu_dsp_warm.h`): whether its code cache is keyed by
  the program's contents or by address only, which decides D5 band 3's
  rule (keep or drop).
- [x] 0.7b The cold-vs-cold baseline (is open): two cold runs of
  BLiNX 2's `@stage1` in the deterministic mode on Metal and on D3D11,
  frames and audio hash compared.
- [x] 0.8 The report: the counts, the probe's numbers, the revised effort
  per phase, written into `design.md` Facts and Effort on a cat spec
  branch, and posted on the tracker item for the user.
- [ ] 0.9 **Go/no-go**, the user's call on the 0.8 report. Exit criteria:
  1. `tools/reset_statics.py` reports 0 unclassified statics over the
     whole toolkit tree and cat's `src/` outside `src/recomp/gen/`;
  2. every host call a guest thread can block in (0.3) has a named way
     out, and none of them needs a change outside its own module;
  3. every wait bridge (0.4) has its post-wait guest change located, so
     the unwind return can sit before it;
  4. the generated code of BLiNX 2 and Burnout 3 has no host statics
     outside the dispatch table (0.5), or the exceptions are listed with
     a hook;
  5. the probe (0.7): every guest thread is stopped (at a stop point, or
     already blocked in a wait bridge or the CPU lock queue) within
     100 ms in at least 19 of 20 samples per game and backend, and within
     500 ms in all of them;
  6. the baseline (0.7b): two cold deterministic runs give identical
     frames and audio on Metal and on D3D11, so D8's equivalence gate
     can rest on it; if not, the report says whether the tracker item lands first
     or the gate falls back to golden tolerance;
  7. the effort: the user accepts the revised figure for phases 1 to 5.
     The spec's own figure before phase 0 is already 41 to 60 agent days,
     above the 50 first set, so this is an explicit acceptance, not a
     threshold; otherwise the scope narrows (for example BLiNX 2 first).
  Go when all seven hold. Otherwise the report names the criterion missed
  and a redesign or a narrower scope (for example, BLiNX 2 only), and
  phase 1 waits for the user.

## 1. Guest unwind (toolkit)

- [x] 1.1 `recomp_guest_unwind`: `g_xbox_reset_pending` (checked where
  0.7's probe flag is, before `xbox_GuestCpuPreempt`'s early returns), a
  per-thread unwind handle, `jmp_buf`s in `bridge_thread_main`,
  `xbox_thread_wrapper` (if 0.3 finds it used; else a log and an abort on
  a reset with such a thread live) and the boot loop, the live guest
  thread count. Point save-states tasks 3.1 and 3.2 at it.
- [x] 1.2 Unwind points: `xbox_GuestCpuPreempt`, `xbox_SpinWait`,
  `xbox_SpinWaitKick`, the guest CPU lock's acquire, every bridge entry.
  Review each point for held bridge locks; a per-thread held-lock count
  with an assertion at each unwind.
- [x] 1.3 Every wait bridge from 0.4 also waits on the unwind handle and
  returns "unwind" before any post-wait guest change.
- [x] 1.4 Host threads that call into guest code (APCs, DPCs, DSound
  callbacks) get an unwind point at the call-in.
- [x] 1.5 Thread exit after the jump through the usual exit path (TIB and
  stack freed); the boot thread releases the guest-object locks it owns
  and waits at the loop. The lock rule (design D3): free locks destroyed,
  locks owned by an exiting thread abandoned (out of the tables, never
  destroyed or unlocked), `[RESET] abandoned <n> locks`. Also fix the
  stock exit gap that phase 0 found: outside the deterministic mode a
  worker that ends in `PsTerminateSystemThread` calls `ExitThread`
  without `xbox_GuestCpuPart`, so `sched_forget` and the `t_sched`
  cleanup never run. The reset's live thread count needs every exit to
  part.
- [x] 1.6 ctest `guest_unwind` (design D8).
- [x] 1.7 The join and snapshot race (from the phase 0 review). A guest
  thread that joins while the reset takes its snapshot of live threads
  must either be in the snapshot or see the stop flag at its first stop
  point. The probe tolerates the miss; the reset cannot.
- [x] 1.8 The deterministic-mode slot leak (from the phase 0 review).
  `xbox_GuestCpuPart`'s deterministic branch returns before
  `xbox_ResetProbePart`, so a thread that exits in that mode keeps its
  slot. The reset's thread tracking must part on every path, or repeated
  resets run out of slots.
- [x] 1.9 The guest CPU's per-thread stats records (`s_threads` in
  `kernel_guest_cpu.c`) are taken by thread id and never freed. Free them
  at thread exit, or the 50-reset soak (5.4) fills the table.
- [x] 1.10 Check that D7 rule 1's refusals (a DEBUG-tier key set) do not
  block D8's reset driver (`reset_at`, 5.1). The driver itself runs under
  DEBUG-tier keys, so it needs a stated exemption or its own rule.

Phase 1 notes (toolkit `feat/game-reset-p1` 72c10626 and its review fixes,
`docs/reset-threads.md` "The guest unwind"):

- 1.1: `src/kernel/kernel_guest_unwind.{c,h}`. The jmp_buf is in
  `xbox_GuestUnwindCallIn`. `bridge_thread_main` uses it now; the boot
  loop calls it in phase 3, with `xbox_GuestUnwindPark`. The
  `xbox_thread_wrapper` creator is dead (0.3), so its threads are counted
  (`xbox_GuestUnwindForeign`), and a request with one live logs and
  aborts. Everything is off until `xbox_GuestUnwindEnable`.
- 1.2: points at the back edge (before the early returns), both spin
  waits, the lock's entry, queue and grant, the thunk dispatch's entry
  and exit, a contended critical section, and the ring's turn and block.
  The held-region count is `xbox_GuestUnwindHold`: an ISR or a DPC drain
  run on a guest thread holds it. A point inside the region refuses
  (`[RESET] unwind refused`) and the next point past it unwinds.
- 1.3: `sync_wait_one`, `sync_wait_many` and the delay also wait on the
  unwind event. On Windows the event is appended to the wait, with 20 ms
  slices for wait-all and 64 handles; POSIX uses `w32_wait_abortable`.
  The thread unwinds before `bridge_user_apc_finish` and the guest clears.
- 1.4: the DPC, ISR, OHCI and APU call-ins wrap their guest call in
  `xbox_GuestUnwindHostBegin` and `xbox_GuestUnwindHostEnd`. One that
  starts while a reset is pending skips the guest code; one already running
  is counted, and `xbox_GuestUnwindWaitStopped` waits for it to end. Guest
  APCs run in thread context, inside a guest thread's call-in, so its
  points cover them. DSound callbacks are not covered yet. The jump skips
  the mods' `guest_call` TLS with the rest of the frames; phase 2's mods
  hook resets it.
- 1.5, D3 refinement: before the jump the thread leaves every guest
  critical section it owns, each recursion. This is defined, because the
  thread is the owner, and it wakes a waiter in a plain host
  `EnterCriticalSection`. Only mutants are left abandoned now, and
  `[RESET] abandoned <n> locks` moves to phase 2's table teardown. The
  `PsTerminateSystemThread` exit calls `xbox_GuestCpuPart` on every path.
  Each thread clears its critical-section owner records at its part, so a
  later thread given the same host id does not let go of its locks.
- 1.6: the `guest_unwind` ctest covers every point kind (the wait on one,
  any of two and all of two), the lock off and on, the hold, DISPATCH
  under the one-CPU gate, the join race, the park, the ring, the registry
  limit and the host call-ins.
- 1.7: `xbox_GuestUnwindSpawnBegin` counts a thread before its
  `CreateThread`. A thread that joins with the flag up runs no guest
  code.
- 1.8, 1.9: the ring's part is in the unwind's exit path whether or not
  the thread holds the token. Parted threads give back their `s_threads`
  record, only with the unwind on, so stock is unchanged.
- 1.10: D8 already exempts `reset_at` from the D7 rules. Task 5.1 must
  call the reset below the rule check, not through the menu action.
- For later phases: the main thread has no call-in until the phase 3
  boot loop, so its points return. The registry holds 64 threads. A 65th,
  or one whose event cannot be made, is counted as untracked, and
  `xbox_GuestUnwindRequest` refuses (returns 0) while one lives.

## 2. Reset hooks (toolkit)

- [ ] 2.1 `src/platform/recomp_reset_hook.{c,h}`: the registry, the bands,
  `RECOMP_TRACE=reset` with per-hook times; ctest `reset_hooks`.
- [ ] 2.2 `src/kernel/kernel_reset.c`: the reset thread, the D2 steps, the
  timeouts and the quit fallback, the `[RESET]` lines; refused once
  `HalReturnToFirmware` has started; a second request while one runs
  ignored with `[RESET] already running`.
- [ ] 2.3 Device pause flags at each loop head from 0.3: `nv2a-ack` stops
  walking and its `dsp_ack_tick` and `poke_tick` but keeps its loop (it
  owns the D3D11 window and device), `vblank-ack`, `nv2a-kick`, the
  raster workers, the APU thread and the DSP GP and EP workers,
  `kernel-timer`, `ohci`, `host_open`, `vp-pump`, the present thread;
  the watchdog paused.
- [ ] 2.4 Renderer band, Metal: drain the command buffers, drop the
  guest-derived caches, keep the device, the shader caches and the present
  chain, clear to black.
- [ ] 2.5 Renderer band, D3D11: the same on the ack thread, the device and
  swap chain kept. Mirror 2.4 (backends agree).
- [ ] 2.6 PGRAPH, the walker's carry-over, HLE D3D8.
- [ ] 2.7 APU: registers, voices, DSP cores, the JIT cache rule from
  0.7a, HLE DSound and the WMA decoder (`src/audio`), the host stream
  flushed.
- [ ] 2.8 Input: OHCI and the guest pad state; host pads reported again.
- [ ] 2.9 Video: a reset during an FMV is allowed and stops it (the user,
  2026-11-03). A stock movie is decoded by guest code on guest threads,
  so phase 1's unwind stops it. With `RECOMP_FMV_HOST` (opt-in, Windows
  only), the Media Foundation player is stopped and its own window and
  D3D8 device closed in D2 step 3. On macOS `video_player.c` is stubs:
  nothing to stop. The video pump reset.
- [ ] 2.10 Kernel: every handle closed, the host sync objects behind guest
  objects destroyed or abandoned (1.5), KE shadow, APC rings, timers,
  DPCs; after the memory bands, clocks, the RAM cache seeded again, the
  config values the guest reads at boot read again.
- [ ] 2.11 Memory, in the D5 order: guest RAM and the contiguous window
  cleared in place (never unmapped; the MMIO trap pages and watch
  re-protects stay mapped and armed and are skipped), heap and arenas
  reset, the guest `setjmp` slots and guest-pointer caches cleared; then
  the XBE sections loaded again; then the guest-memory parts of the
  host-half inits run again (the thunk patch after its `VirtualProtect`,
  `kernel_data_init`, TIBs and worker stacks, the APU windows), each split
  out of its init into a function both call.
- [ ] 2.12 Mods: `on_reset` appended to `struct xbox_mod` (v5); the
  toolkit records each mod's guest hooks and removes them before
  `on_reset`; `needs` (STATE, POKE, HOOK) made binding, with
  `[MOD name] undeclared <kind>` on a use it does not cover (D6a); an
  enabled mod that declares or uses them without `on_reset` turns the
  reset off with its name.
- [ ] 2.13 The enhance layer's own statics from 0.1 (HUD anchors, the
  free camera, the stats strip's guest counters).
- [ ] 2.14 Module ctests where a hook can run standalone (handle table,
  ramfs seed, APU registers).

## 3. Boot loop and games

- [ ] 3.1 `src/kernel/kernel_boot.c` `xbox_boot_run(entry, game_boot)`;
  the host half stays in the game's `main`.
- [ ] 3.2 The new-game template: `xbox_boot_run` and an empty game hook.
- [ ] 3.3 cat `src/main.c`: boot through `xbox_boot_run`, the pad init in
  `game_boot`; `cat_save_seed` stays in the host half (run once, never
  at a reset); a game reset hook for the 0.6 statics; the automation
  reason passed to the toolkit, with `RECOMP_SAVE_SEED` among its keys.
- [ ] 3.4 cat `docs/env.md`: the `reset_at` row and the `reset` trace
  channel.
- [ ] 3.5 (Follow-up, outside the BLiNX 2 scope.) BLiNX 1 and the other
  active games: adopt `xbox_boot_run` as each is next touched; until then
  their row is greyed out (D7 rule 5).
- [ ] 3.6 cat's 10 mods (collision, crystals, debug menu, entities, free
  camera, glow, HUD, LOD scale, shop, walls): `needs` corrected from 0.6,
  and an `on_reset` for each that drops its guest pointers and cached
  addresses and installs again what its init installs.

## 4. Menu and saves (toolkit)

- [ ] 4.1 `kernel_file.c`: `xbox_saves_freeze()` and `xbox_saves_thaw()`;
  an open under the freeze unwinds. ctest `reset_saves`.
- [ ] 4.2 The System page (last tab, its intro and icon) with Restart game
  and Quit game.
- [ ] 4.3 The two dialogs on the `s_dlg` machinery: focus on Go Back, the
  unsaved-settings variants, the failed-save rule, "Restarting…",
  "Quitting…" and the saves wait line.
- [ ] 4.4 Quit: the saves wait and freeze, then `recomp_quit_post("menu")`,
  or the exit hooks and `ExitProcess(0)` on a thread of its own with no
  poster.
- [ ] 4.5 `game.reset` registered with no default binding; it opens the
  Restart dialog.
- [ ] 4.6 The D7 rules and the greyed row's help line; the shared
  automation helper if pre-launch-screen has not landed. ctest
  `reset_rules`.
- [ ] 4.7 The "applies at restart" status: "applies at Restart game" or
  "applies after quitting" per setting.
- [ ] 4.8 Menu ctests (design D8).

## 5. Verification

- [ ] 5.1 The `reset_at=<flip>` DEBUG row and its trigger.
- [ ] 5.2 Equivalence on Metal (Mac): deterministic mode, `@stage1` after
  a reset at flip N against a cold run; frames and audio hash equal.
- [ ] 5.3 Equivalence on D3D11 (native Windows, PC).
- [ ] 5.4 The 50-reset soak on the Mac and the PC: handles, heap,
  textures, GPU memory and RSS flat within 2 % with the abandoned locks'
  bytes subtracted; the abandoned count per reset no larger than the
  locks held at its stop and not growing; no `[RESET] stuck`.
- [ ] 5.5 Hand checks (design D8) on the Mac, the PC from Steam and the
  Deck in game mode.
- [ ] 5.6 (Follow-up, outside the BLiNX 2 scope.) Burnout 3: adopt
  `xbox_boot_run`. It runs with the guest CPU
  lock off, so it has no deterministic mode and no frame equivalence:
  after a reset at a fixed flip, one race's golden within its normal
  tolerance, plus a 20-reset soak on D3D11. Or record it as a follow-up
  in TASKS.md.

## 6. Gates

- [ ] 6.1 Toolkit: the Mac build, `tests/posix_ctest.sh` (0 FAIL),
  `pytest tools/recomp tools/disasm`, and the Windows ctests on the PC.
- [ ] 6.2 cat: `uv run pytest scripts`, `uv run ruff check .` and
  `uv run ruff format --check .`.
- [ ] 6.3 Goldens: Metal on the Mac and D3D11 on native Windows; the Deck
  later, non-blocking. Flips/s within the 25 % rule.
- [ ] 6.4 `sh notes/build-all.sh` with the toolkit worktree (BLiNX 2,
  BLiNX 1, KUF on macOS and Windows).
- [ ] 6.5 Review; fixes back to the branch's agent.
