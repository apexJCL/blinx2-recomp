## Why

The user asked on 2026-11-03 for a menu action that resets the
running game as if the Xbox were rebooted. Today the only way back to the
title screen is to quit and start the game again: from the window's close
button or from Steam. The menu itself has no quit. On the Steam Deck in
game mode that is several steps through Steam's own UI.

The user's answers of 2026-11-03 shape this change:

- Restart and Quit go on a new **System** tab, each behind a confirm that
  opens on Go Back.
- **No relaunch.** The user wants the reset that keeps the window, the GPU
  device and the audio device open and rebuilds the guest state in the
  same process. The relaunch of the first draft (`1824b638`) is recorded
  as rejected (design D10).
- `game.reset` has no default binding.
- The saves "Import and restart" is a separate follow-up, the tracker item.

A reset also helps:

- **Restart-only settings** that the guest reads at boot
  (`system.language`, the video flags behind `display.aspect`). Today the
  player has to quit and start again by hand.
- **Recovery.** A soft lock, or a mod toggled into a state the player does
  not want, is fixed without leaving the game.

How the toolkit handles a reboot today (toolkit `posix-host/portability`
`11e099c2`, read only):

- `HalReturnToFirmware` always ends the process (`kernel_bridge.c` →
  `kernel_hal.c` → `ExitProcess(0)`). `XLaunchNewImage` is lifted title
  code that ends in `HalReturnToFirmware(2)`. Nothing relaunches or
  re-initializes.
- No host or guest thread has a way to stop, and about 1,700 statics
  (file-scope and function-local) in the toolkit, plus thread-locals,
  `INIT_ONCE` guards and cat's own sources and mods, hold state from the
  running boot.
- The planned way to stop guest threads in place is save-states phase 3
  (a `longjmp` unwind to the thread trampolines, every host sync object
  re-created). save-states is **parked** since 2026-11-03, and nothing of
  it is implemented.

## What Changes

- **A System tab (D1)** with two rows, **Restart game** and **Quit game**.
  Each opens a modal dialog focused on Go Back. With unsaved menu
  settings, each offers "… without saving", "Save settings and …" and Go
  Back. Quit is new: the footer keeps Cancel and Save. A bindable host
  action, `game.reset`, opens the Restart dialog; it has no default
  binding and never resets on its own.
- **An in-process reset (D2).** A reset thread:
  1. waits for the saves to go quiet and freezes them (D4);
  2. stops every guest thread by unwinding it to its trampoline (D3);
  3. pauses the device threads at their loop heads;
  4. runs the reset hooks, which put every module back to its start state,
     clear guest memory in place, load the XBE's sections again and redo
     the guest-memory parts of the host-half inits (D5);
  5. resumes the devices and runs the guest half of the boot again (D6).
  The window, its mode, the GPU device, the swap chain, the host audio
  device, the config and the menu stay. A step that gets stuck ends the
  game as a quit does, with the saves already safe.
- **The guest unwind (D3)** is the save-states phase 3 unwind (its tasks
  3.1 and 3.2) plus the cooperative wait abort from its phase 2, without
  any state capture. It is built here as a layer of its own,
  `recomp_guest_unwind`, which save-states reuses when it is un-parked.
- **Reset hooks (D5).** `recomp_reset_hook_add(name, order, fn)`, run in
  bands: renderer, PGRAPH and HLE D3D8, APU, DSP, DSound and WMA, input,
  video, kernel objects, guest memory cleared in place, the XBE reload,
  the guest-memory inits again, clocks and saves, mods (`on_reset`), the
  game. A phase 0 audit classifies every piece of toolkit and cat state
  as keep, reset or constant.
- **Mods (D6a).** `struct xbox_mod` gets an `on_reset`. Its `needs` bits
  for guest state, pokes and hooks exist but nothing reads them; the
  reset makes them binding. An enabled mod that uses guest state without
  `on_reset` greys the Restart row. cat's 10 mods each get one.
- **The boot loop (D6).** `xbox_boot_run(entry, game_boot)` owns the guest
  half of the boot and runs it again after each reset. A game moves its
  guest-side setup into `game_boot` and registers one reset hook for its
  own statics.
- **Saves are safe (D4).** Wait up to 10 s for the title to have no save
  file open and no touch for 2 s; then freeze save opens under the guard's
  lock. An open during the freeze unwinds instead of opening. The new boot
  thaws them. Menu Quit uses the same wait.
- **Never during automation (D7).** The Restart row is greyed out with the
  reason, and the action does nothing, under a DEBUG-tier key,
  `RECOMP_WINDOW_QUIT_AFTER`, a headless run, the game's automation
  reason, a game that turned it off or does not boot through
  `xbox_boot_run`, an enabled mod that uses guest state without
  `on_reset`, or a `HalReturnToFirmware` already under way. A second
  request while a reset runs is ignored.
  Goldens pin `RECOMP_MENU=0`, so the tab never exists there.
- **Verification (D8).** A DEBUG-tier test trigger, `reset_at=<flip>`. In
  the deterministic mode, the boot after a reset must give the same
  frames and audio as a cold boot, on Metal and D3D11, once phase 0 has
  shown two cold boots agree (is open). A 50-reset soak keeps
  handles, memory and textures flat; locks a stopped thread still held
  are abandoned, never destroyed, and counted on their own.

## Capabilities

### New Capabilities
- `game-reset`: the System tab's Restart game and Quit game, their
  confirms, the saves guard, the automation rule, the in-process reset
  and its equivalence with a cold boot.

### Modified Capabilities
- `host-boot`: "Boot order" and "Clean exit" are modified: the guest half
  of the boot runs in a loop owned by the toolkit, and a reset runs it
  again with the `[RESET]` lines instead of exiting.

## Impact

- **Toolkit** (`posix-host/portability`; game-agnostic, upstreamable):
  - new `src/kernel/kernel_reset.c` (the reset thread),
    `src/kernel/kernel_boot.c` (`xbox_boot_run`),
    `src/platform/recomp_reset_hook.{c,h}`, and the
    `recomp_guest_unwind` layer in the kernel bridge and the guest CPU
    lock;
  - every wait bridge waits on the thread's unwind handle; every bridge
    entry checks the reset flag;
  - a reset hook in each module (kernel, memory, APU and DSP, PGRAPH and
    both renderers, input and USB, video and FMV, the enhance layer);
  - a pause flag in each device thread;
  - `src/enhance/enhance_menu.c` and `enhance_actions.c`: the System page,
    the dialogs, `game.reset`, Quit;
  - `src/kernel/kernel_file.c`: the saves freeze and thaw;
  - the mod API: an optional `on_reset` (v5) and `needs` made binding;
  - the template: `xbox_boot_run` and an empty game hook;
  - one DEBUG-tier env row, `reset_at`, and one trace channel,
    `RECOMP_TRACE=reset`;
  - `docs/reset-statics.md` and the script that flags new statics.
- **Game** (`cat`): `src/main.c` boots through `xbox_boot_run`, with the
  save seed kept in the host half; a game reset hook for the statics in
  `recomp_manual.c` and `pad_*`; an `on_reset` in each of the 10 mods;
  the automation reason (with `RECOMP_SAVE_SEED`); the `docs/env.md`
  rows (`reset_probe` in phase 0, `reset_at` later).
- **Backends:** D3D11 and Metal each get the drain and cache drop of band
  1, and must agree. The CPU path keeps building; its reset is a TASKS
  follow-up.
- **Hosts:** macOS (Metal), native Windows (D3D11), the Deck under Proton.
  One process throughout, so no launcher behaviour changes.
- **Goldens:** stock behaviour does not change: the tab only exists in the
  open menu, which goldens turn off. The runtime is touched throughout, so
  the Metal and native Windows goldens run before the merge, and the
  equivalence gate of D8 runs on both.
- **Dependency:** save-states stays parked. The unwind it would need is
  built here (the user, 2026-11-03).
- **Effort: about 46 to 68 agent days, above the 50 first set.**
  Phases 1 to 5 (with the mods) are 41 to 60 agent days, against the 50
  in the earlier exit criterion; the review of `8d7d34f7` put the
  total at 45 to 65. Phase 0 (5 to 8 days) is a milestone of its own that
  merges alone and ends in a go/no-go with written exit criteria (task
  0.9); the effort criterion is now the user's acceptance of the revised
  figure, or a narrower scope (for example BLiNX 2 first). Phases 1 to 5
  wait for the go. A restart during an FMV is allowed and stops it: a
  stock movie is guest code and unwinds with its threads.
- **Scope: BLiNX 2 first** (the user, 2026-11-04). After phase 0 the user
  gave the go for phases 1 to 5 at 43 to 62 agent days, scoped to BLiNX 2.
  The toolkit layers stay game-agnostic. BLiNX 1, Burnout 3 and the other
  games adopt `xbox_boot_run`, add their game hook and run their own
  verification later, each as a follow-up; until then their Restart row is
  greyed out (D7 rule 5).

## Status

Phase 0 is done (2026-11-04). Its results are under "Phase 0
results" in `design.md`. The user gave the go on 2026-11-04 for phases 1
to 5, BLiNX 2 first ("Settled" in `design.md`). Phases 1 to 5 are not
started.
