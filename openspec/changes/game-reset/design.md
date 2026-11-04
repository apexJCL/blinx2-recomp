# Design: reset the game from the menu

## Context

On the console, a reset (the power button, or a title's own quick reboot)
throws away everything the title had in memory. The kernel boots again,
the XBE loads fresh and its entry point runs. The hard disk keeps what was
written to it, and that includes the saves.

This design comes from reading, not from runs: the toolkit at
`posix-host/portability` `11e099c2`, cat at `main` `63d80cf0`, and the open
changes save-states (parked since 2026-11-03), pre-launch-screen (not
implemented: cat's `main.c` has no pre-launch screen yet) and
overlay-saves (archived 2026-11-03). The review of `8d7d34f7`
checked the facts below against the same trees; its corrections are in.

**Revision, 2026-11-03 (the user's answers).** The first draft
(`1824b638`) relaunched the executable. The user chose to wait for the
in-window reset instead: the window, the GPU device and the audio device
stay open and the guest state is rebuilt in the same process. The
relaunch is kept under "Alternatives considered" (D10) as rejected. The
user also put Restart and Quit on a new System tab, kept `game.reset`
without a default binding, and filed the saves "Import and restart" as
The tracker item.

### Facts the design rests on

**Reboot handling today.** `HalReturnToFirmware` always ends the process
(`kernel_bridge.c` `bridge_HalReturnToFirmware` → `kernel_hal.c`
`xbox_HalReturnToFirmware` → `ExitProcess(0)`). Before that it:

- logs the launch data page and the guest call chain;
- dumps the indirect-call feedback;
- runs the missing-file and kernel summaries;
- waits for a host FMV, at most 60 s.

`XLaunchNewImage` is lifted XAPI code. It fills the launch data page and
calls `HalReturnToFirmware(2)`, so a self-reboot, a launch and a quit look
the same and all of them exit. `HalRegisterShutdownNotification` only logs.
`HalIsResetOrShutdownPending` is `FALSE`.

**The menu has no Quit today.** The footer holds Cancel and Save. The
leave dialog's "Exit without saving" and "Exit and Save" close the menu,
not the game. The game ends by the window's close button, by the
launcher, by `HalReturnToFirmware`, or by "Import and quit" on the Saves
page (`recomp_quit_post("saves_import")`). The menu's pages are Render,
Shaders, Pack, Game, Mods, Stats, Controls, Debug, Saves and Files
(`enum page` in `enhance_menu.c`).

**Boot is owned by the game's `main.c`.** cat's `host_main` runs:

1. crash diagnostics;
2. load the XBE;
3. `xbox_MemoryLayoutInit`;
4. the APU;
5. `xbox_kernel_init`;
6. `xbox_path_init`;
7. `xbox_kernel_bridge_init`;
8. `g_esp`;
9. the XBE init-flag patch in guest memory;
10. `recomp_dispatch_init`;
11. `xbox_WatchdogStart`;
12. cat's save seed and pad init;
13. `xbe_entry_point()`.

The entry point runs the title's main routine inline on the boot thread
(save-states facts). The first `PsCreateSystemThreadEx` does not return
while the title runs. On POSIX the main thread belongs to the window
(`xbox_HostWindowMain`) and `host_main` runs on a `guest-main` pthread. On
Windows the D3D11 window is created on the `nv2a-ack` thread at the first
flip.

**Threads.** About 15 to 20 host threads run in a BLiNX 2 session (their
roles from `xbox_log_thread_role`):

- **guest code:** `guest-main` (the boot thread) and one `guest-worker`
  per title thread, started by `bridge_thread_main` (`kernel_bridge.c`)
  from `bridge_PsCreateSystemThreadEx`. A second creator,
  `xbox_PsCreateSystemThreadEx` (`kernel_thread.c:119`, role
  `xbox-thread`, through `xbox_thread_wrapper`), serves the thunk-table
  path for native-call titles; no current game is known to use it, and
  phase 0 confirms it (task 0.3);
- **`nv2a-ack`:** the pushbuffer walker itself. Its loop also runs
  `dsp_ack_tick` and `poke_tick`, and on Windows it owns the D3D11 window
  and device, created at the first flip;
- **`vblank-ack`:** delivers the vblank DPCs into guest code;
- **`nv2a-kick`**, the raster workers (`nv2a_pb_exec.c` `raster_worker`);
- **APU:** `mcpx.apu_thread` and the DSP GP and EP workers
  (`apu_dsp_run.c` `worker_main`);
- **`kernel-timer`**, **`ohci`**, the `host_open` thread
  (`src/input/host_open.c`), **`vp-pump`**, **`fb-present`** or the SDL
  guest thread, **`watchdog`** (`xbox_memory_layout.c:3796`), the watch
  re-protect and resolver threads, the profilers and samplers;
- the window thread (`sdl-main` on POSIX).

None of them has a way to stop: there is no unwind path today.

**Movies.** Stock movies are decoded by the title's own code on guest
threads. The host FMV path is opt-in (`RECOMP_FMV_HOST`, CONFIG), Windows
only (Media Foundation in `video_player.c`, with its own window and D3D8
device); on macOS `video_player.c` is stubs. So a stock reset during a
movie is a reset of guest threads like any other.

**Where a guest thread can be stopped.** Every lifted loop back edge has
`RECOMP_BACK_EDGE`, a relaxed load of `g_xbox_guest_cpu_preempt` that
calls `xbox_GuestCpuPreempt` when it is set. The CLI lifts every game with
`--back-edge-yield` when the toolkit has it, so every current game has
these checks. With `RECOMP_GUEST_LOCK` off the flag is never set today,
but the check is in the code. `xbox_GuestCpuPreempt`
(`kernel_guest_cpu.c:1314-1330`) returns early in three cases before it
does anything: the deterministic path (`xbox_GuestDetOn`), a thread that
does not hold the CPU (`!t_held`, which is every thread with the lock
off), and the lock on with no waiter. A stop check must sit before all
three. Spin waits (`RECOMP_SPIN_WAIT`) call
`xbox_SpinWait` under a similar test. A thread blocked in a kernel wait
sits in a bridge (`KeWaitForSingleObject`, `NtWaitForMultipleObjects`,
`KeDelayExecutionThread`, critical sections, the guest CPU lock) in a host
wait, and only a signal reaches it.

**Host objects that guest objects own.** Mutants are `CreateMutexW`
objects, owned by a host thread. Guest critical sections are host
`CRITICAL_SECTION` shadows (`kernel_rtl.c` `xbox_cs_shadow`) with an owner
and a depth. On POSIX a `CRITICAL_SECTION` is a recursive pthread mutex
(`win32_compat.c`): destroying one that is locked, or unlocking it from a
thread that does not own it, is undefined. Guest `setjmp` uses a native
`jmp_buf` slot (`recomp_setjmp_slot` in `xbox_memory_layout.c`). A
`longjmp` out of a thread abandons every host lock that thread holds.

**State a reset has to put back.** Most of it is listed in save-states
D3:

- guest RAM, the contiguous window and the apertures;
- the heap and arena bookkeeping;
- the handle table, the KE shadow, mutants, semaphores, APC rings and
  files;
- timers and the DPC queue;
- the PGRAPH structs and the walker carry-over;
- the APU register files, the voices and the DSP cores with the JIT;
- the OHCI and pad state;
- the HLE D3D8 and DSound state;
- the clocks.

On top of that come the statics and guards. Rough counts at `11e099c2`:

- file-scope statics: `src/kernel` 652, `src/d3d` 215, `src/input` 102,
  `src/apu` 91, `src/video` 54, `src/usb` 43, `src/nv2a` 28, `src/audio`
  (DSound HLE, the WMA decoder) a few: about 1,190, without `src/enhance`,
  `src/platform` and the backends;
- function-local statics: about 440 to 580, many of them const tables;
- thread-local state (`RECOMP_TLS`, `__thread`): about 75 to 90;
- `INIT_ONCE` guards and their kin: about 55;
- non-static globals that hold run state (`g_apu_state`), and statics
  named like globals (`g_nv2a_ack_stop`, `g_scanned_put`), which a name
  rule would miss;
- in cat: `recomp_manual.c`, `pad_input.c`, `pad_slots.c`, `save_seed.c`
  and the 10 mods (collision, crystals, debug menu, entities, free
  camera, glow, HUD, LOD scale, shop, walls). cat has no `src/fixes`.

Each one is either host state to keep (the window, the device, the
config, the menu), state derived from the guest that must go back to its
start value, or a table filled once that is the same on every boot.

**Boot-time work in guest memory.** Some of the host half of the boot
writes guest memory: the kernel bridge patches the thunk table after a
`VirtualProtect` and runs `kernel_data_init` (the kernel's exported data);
the bridge builds TIBs and worker stacks; the APU init maps its guest
windows. The memory layout keeps MMIO trap pages and watch re-protects
mapped over parts of the guest range.

**Save seed.** `cat_save_seed` (`save_seed.c:138-171`) copies
`RECOMP_SAVE_SEED` over `RECOMP_SAVE_DIR` before the boot, when the key
is set. Run again at a reset, it would wipe the player's saves since the
start.

**Mods.** `struct xbox_mod` (`mod.h:106-133`) has `init`, `shutdown`,
`desc`, `needs` and `follows`. `needs` already names `XBOX_MOD_NEED_STATE`,
`_POKE` and `_HOOK`, but it is "a declaration only for now": nothing reads
it, so nothing checks that a mod which hooks or pokes guest state says
so. There is no reset callback.

**save-states and its phase 3.** save-states is parked since
2026-11-03 (the openspec cleanup, cat `bd544b8c`). Nothing of it
is implemented. Its phase 3, "in-session load", plans the unwind this
reset needs:

- 3.1: a `longjmp` unwind point in `bridge_thread_main` and on the boot
  thread, and a check per restartable call that no bridge lock is held;
- 3.2: every host sync object, critical-section shadows included,
  destroyed and re-created, since the `longjmp` abandons ownership the
  reused threads still hold;
- 3.4: a soak of 50 cycles with handle and texture counts flat.

Phase 3 as written sits on phase 2's quiesce and its cooperative wait
abort (every bridge wait also waits on a per-thread handle, save-states
D1). Phase 3 is sized at 5 to 8 agent days, phase 2 at 17 to 25. A reset
needs only part of that: it throws the threads' state away, so it needs
no shadow stack, no resume sites, no state encoding and no re-acquire of
owned objects (phases 1 and most of 2).

**Saves.** `kernel_file.c` keeps the handles the title holds under
`UDATA`/`TDATA` and a stamp of its last touch. `xbox_saves_busy()` is 1
while a handle is open or for 2 s after the last touch, and
`xbox_saves_gen()` moves with each touch (overlay-saves D4). Host I/O is
synchronous: `NtWriteFile` is a `write`/`WriteFile` on the host fd.
`NtFlushBuffersFile` calls `fsync`/`FlushFileBuffers`. Once the guard is
quiet, nothing the title wrote is still held in the process.

**RAM cache.** `kernel_ramfs.c` (on by default) holds the Z: partition in
memory and never writes it back. It starts empty, apart from its seed, on
every run.

**Menu patterns.** The menu has:

- one-row confirms: `s_confirm` for Files' "Reset to defaults", and
  `confirm_row` for Remove and Delete;
- one modal dialog, the leave dialog (`s_dlg`) with "Exit without saving",
  "Exit and Save" and "Go Back". It opens focused on Go Back, refuses a
  Save it cannot write, and lists the unsaved settings.

Host actions register through `enhance_action_register` (`menu.open`,
`overlay.stats`, mods' actions). They are bindable on the Controls page,
and a scripted pad never fires one.

### Phase 0 results (2026-11-04)

Measured on toolkit `feat/game-reset-p0` (`ca2ddf11`) and cat `feat/game-reset-p0`
(`2c746d67` for the audits). The audits are in the toolkit's `docs/reset-statics.md` and
`docs/reset-threads.md` and in cat's `docs/reset-statics.md`; the probe is
`RECOMP_DEBUG=reset_probe` (`kernel_reset_probe.c`, off by default).

**Statics (0.1, 0.2).** `tools/reset_statics.py check` lists every mutable
static, thread-local, once-guard and run-state global and checks it
against the doc tables:

| Tree | Objects | Unclassified | keep | reset | constant | Files with a reset row |
|---|---|---|---|---|---|---|
| toolkit (whole tree) | 2559 | 0 | 2023 | 416 | 120 | 44 |
| cat `src/` outside `src/recomp/gen/` | 313 | 0 | 190 | 118 | 5 | 12 |

The toolkit's reset rows by module: kernel 287 (`xbox_memory_layout.c` 68,
`nv2a_pb_exec.c` 65, `kernel_bridge.c` 34, `kernel_guest_cpu.c` 33,
`kernel_hal.c` 16, `kernel_guest_det.c` 13, `kernel_ramfs.c` 12), d3d 63
(Metal 20, D3D11 19, HLE D3D8 11), enhance 19, apu 13, video 12, usb 11,
nv2a 8, input 3. In cat, 110 of the 118 reset rows are in the mods (walls
22, entity API 17, collision 17, entities 14, crystals 14, shop API 11,
free camera 8, shop 4) and 8 in the game. The spec's rough count (about
1,700 to 1,900 objects) was close; the reset share is smaller than feared
(16% in the toolkit), but the mods carry more than phase 3m assumed.

The scanner first missed four objects (a local named `id`, a pointer to a
function returning a typedef, and the function after one that returns a
pointer to an array). It now warns on any function body it cannot name,
so a miss is reported instead of hidden.

**Threads and waits (0.3, 0.4).** 23 host-thread rows (about 28 creator
sites); 2 of them run guest code on a host thread (`kernel-timer`: DPCs,
the vblank ISR, timers; `ohci`: the USB ISR). 2 guest-thread roles;
`xbox-thread` (`kernel_thread.c`) is dead in every current game. 13
blocking sites outside the wait bridges; 12 wait-bridge rows. Every way
out stays in its own module (criterion 2), with three risks to design
for: guest critical sections (`kernel_rtl.c`, the biggest deadlock risk),
the order (guests stop at their back edges before the walker and APU
pause, since KickOff's flush spin and MakeSpace's wait need the walker),
and the guest call-ins on `kernel-timer` and `ohci`. Every bridge has one
host wait followed by `bridge_user_apc_finish`, and its guest clears come
after the wait, so one check after the wait covers each (criterion 3); 8
of the 12 consume the signal in the host primitive, which is acceptable
only because the reset reinitialises every guest object.

The probe found one more stock gap. Outside the deterministic mode, a
worker that ends in `PsTerminateSystemThread` calls `ExitThread` without
calling `xbox_GuestCpuPart`. This skips `sched_forget` and the `t_sched`
cleanup, so the scheduler never forgets the thread. Phase 0's change is
on the probe side only: `xbox_ResetProbePart()` before `ExitThread`,
which does nothing with the probe off. The stock gap is a phase 1 item
(task 1.5), and the reset's live thread count cannot rely on Part until
it is fixed.

Phase 0 changes one other line outside the probe. `kernel_thunk_dispatch`
now reads the slot's ordinal once, at entry, and passes it to
`xbox_GuestDetTraceCall`. Before, the deterministic trace read
`g_kernel_dispatch_slot` again after the body, and a nested dispatch
could change it, so the trace could name the wrong ordinal.

**Generated code (0.5).** BLiNX 2's generated code has 3 host statics:
`g_flat_table` (the dispatch table), `s_hook_slots_gen` (the mods' hook
slots, keep) and the `on` guard of `recomp_stub_log` (a log guard, keep).
Burnout 3's has 2: `g_flat_table` and the same `on`. No guest state lives
in a host static there.

**The boot split (0.6).** cat's `host_main` (`src/main.c` 1102-1346) splits cleanly. The guest
half is three steps: `g_esp = XBOX_STACK_TOP`, the init-flag patch at
guest 0x00010124 (it writes the XBE header in guest RAM, so it re-runs
after band 8), and the entry; on a reset it also calls a new
`cat_pad_reset()` in place of `cat_pad_early_init()`. Everything else
runs once in the host half, and `xbe_data` stays alive for band 8:
- the mapping;
- the APU object;
- `xbox_kernel_init` and the bridge table;
- `recomp_dispatch_init`;
- the watchdog;
- `cat_save_seed()`.
BLiNX 1's (`blinx/src/main.c` 703-925) is smaller still: `g_esp`, the
entry and a pad reset, with no init-flag patch and no save seed.
`xbox_Nv2aMirrorFence` stays registered in both games, so the NV2A reset
must reset the fence word's value and leave the registration alone.

The mods' `needs` (D6a) do not cover what the mods do:
- no cat mod declares STATE, yet eight of them read guest RAM outside
  hook arguments;
- `lod` declares nothing, yet it pokes and reads;
- no flag covers `guest_alloc` or `guest_call`.
The recorder also cannot see raw `api->mem` access, so STATE and POKE
stay declarations. The tables recommend this: the reset is off for any
declared mod that has no `on_reset`, `guest_alloc` counts as POKE and
`guest_call` counts as HOOK. All ten mods hold reset-class state, so all
ten need an `on_reset`.

**DSP JIT keying (0.7a).** dsp56300's translation cache is keyed by
address and verified by content (`translations`, a word-by-word compare
of P), and it survives P writes, but `dsp56300_reset` calls
`invalidate_cache`, which drops it, and the guest resets the core on every
boot (GPRST, then the bootstrap; `apu_dsp_emu.c` 599-624). So no JIT code
survives a reset even inside one run. D5 band 3: drop the cache (keeping
it would need a library change, for no gain the probe can see).

**The stop probe (0.7).** At each listed flip the probe raises the stop
flag (and the preempt flag) and records, per guest thread, the first stop
point it reaches; a thread already blocked in a kernel wait or queued on
the CPU lock counts as stopped at 0.

| Game, backend | Run | Samples | All stopped | Stop ≤ 100 ms | Median ms | Max ms |
|---|---|---|---|---|---|---|
| BLiNX 2 (guest lock on), Metal | stage1 | 26 | 26 | 26 | 8.8 | 11.9 |
| BLiNX 2, Metal | attract | 22 | 22 | 22 | 14.8 | 18.1 |
| BLiNX 2, D3D11 (native Windows) | attract | 40 | 40 | 40 | 4.4 | 19.7 |
| BLiNX 2, D3D11 (native Windows) | stage1 | 40 | 40 | 40 | 3.0 | 17.5 |
| Burnout 3 (guest lock off), D3D11 (native Windows) | boot, menus, race start | 40 | 40 | 40 | 0.0 | 1.0 |

Every sample stopped every live guest thread, far under the 500 ms bound
(criterion 5). Two limits apply to these numbers:
- **Guest code on host threads is not measured.** The probe covers only
  guest threads. It does not measure the guest code that the
  `kernel-timer` thread runs (the DPCs, the vblank ISR, the timer DPCs)
  or that `ohci` runs (the USB ISR). Their call-ins get their own unwind
  points in task 1.4.
- **The lock-off times are optimistic.** A thread in `IN_BLOCK`, blocked
  in a short kernel call such as a contended critical section, counts as
  stopped at 0. A real reset still has to wake it through the unwind
  handle (task 1.3). With the guest lock off, more threads sit there, so
  Burnout 3's figures are lower than a real reset would see. The stop points seen: `back_edge`, `cpu_acquire`,
`waiting` (a kernel wait), `spin` (`xbox_SpinWait`, a guest spin-wait loop),
`queued` (on the CPU lock) and `bridge` (inside a wait bridge). Burnout 3
has 3 guest threads and runs without the guest lock, so they stop at back
edges, spin waits or kernel waits at once. BLiNX 2 waits for the lock holder to reach its
next back edge.

Before one fix, every BLiNX 2 sample showed two threads as NOT STOPPED.
Both were dead workers that had left through `PsTerminateSystemThread`
without parting (above). A thread dump of the attract run found the
other idle states the reset must handle:
- guest threads in `xbox_HostSleepNs` inside guest subs (they stop at the next back edge after the sleep);
- one worker that had suspended itself through `NtSuspendThread`.
Both are in `docs/reset-threads.md`. The goldens pass with the probe on.

**The cold-vs-cold baseline (0.7b).** It passes on both backends (criterion 6), and D8's equivalence gate can
rest on it without waiting. Each pair is two cold stage1 runs
of BLiNX 2 under `RECOMP_DEBUG=deterministic`, recording audio with
`audio_wav`:

| Backend | Frames compared | Identical | Audio compared | Audio |
|---|---|---|---|---|
| Metal (Mac) | 331 (every dumped flip) | 331 | 76.35 s | identical |
| D3D11 (native Windows) | 31 (the scenario's kept checkpoints) | 31 | 130.73 s | identical |

The only files that differ on Metal are four `fb_dump` captures
(000-003). These are taken on host time, not keyed to a flip, so the
gate must ignore them. Audio is compared over the length both runs
share; the runs stop at slightly different host times. Every golden
verdict passed in both pairs.

**Effort, revised (0.8).** The counts confirm phase 2's 20 to 28 days:
416 toolkit reset rows in 44 files, mostly in the kernel, and the
backends' 39. Phase 3m rises from 3-5 to **5-7**, because the mods hold
110 reset statics, all ten need an `on_reset`, and the `needs` gaps
above must be fixed, including the `guest_alloc` arena reset in band 7.
Phase 1 gains the stock `PsTerminateSystemThread` part and the four
items the review found (tasks 1.5 and 1.7 to 1.10); they fit in its
7 to 10 days. Phases 1 to 5 now total **43 to 62 agent days** (45 to 70
with phase 0), still above the 50 set before phase 0. Criterion 7 is the
user's call. Starting with BLiNX 2 alone would save phase 3's other games
and Burnout 3's half of phase 5, about 3 to 4 days.

## Goals / Non-goals

**Goals**

- One menu action resets the game to a fresh boot inside the same
  window, on macOS (Metal), native Windows (D3D11) and the Deck (D3D11
  under Proton). The window, its size and fullscreen state, the GPU
  device, the host audio device, the config and the menu stay.
- After a reset the game runs as it does after a cold start. A reset in
  the deterministic mode gives the same frames as a cold boot (D8).
- No save is ever torn or lost. Unsaved menu settings are asked about.
- Automation, goldens, pad recordings and the deterministic mode are
  never affected.
- The menu gets a Quit with the same confirm and the same saves wait.
- The machinery is game-agnostic. A game adds a reset hook for its own
  statics and nothing else.

**Non-goals**

- Changing how the title's own `HalReturnToFirmware` and `XLaunchNewImage`
  behave. Both still exit. Routing a title's quick reboot to itself
  through the reset is a follow-up (D9).
- Resetting with no window (headless) or from a script, apart from the
  DEBUG test trigger of D8.
- Quick save and load. They stay in save-states. This change builds the
  unwind save-states phase 3 would reuse, but none of the state capture.
- The saves "Import and restart".

## Decisions

### D1. The System tab: Restart game and Quit game

- **A new page, System**, the last tab after Files, with the intro "Restart
  or quit the game." It has two rows:
  - **Restart game**: "Start the game again from its boot, as a console
    reset does. The window stays open."
  - **Quit game**: "Close the game."
  The toolkit adds the page for every game. The rows are not called
  "Reset": Files already has "Reset to defaults" for the settings.
- **Quit is new.** The menu has no quit today (Facts); nothing moves out of
  the footer, which keeps Cancel and Save. The window's close button and
  the launcher keep working as before.
- **Both open a modal dialog.** A one-row confirm (`s_confirm`) is too easy
  to accept by accident for something that throws away progress. The
  dialogs reuse the leave dialog's machinery (`s_dlg`) with their own body
  and buttons:
  - Restart: "Restart the game? Progress since your last in-game save is
    lost, as on a console reset." Buttons **Restart** and **Go Back**.
  - Quit: "Quit the game? Progress since your last in-game save is lost."
    Buttons **Quit** and **Go Back**.
  - Both open focused on Go Back, as the leave dialog does, so a second A
    press does nothing.
  - With unsaved menu settings, the body adds the leave dialog's count and
    names line, and the buttons become **Restart without saving** (or
    **Quit without saving**), **Save settings and restart** (or **Save
    settings and quit**) and **Go Back**. A failed save keeps the dialog
    open with the reason, as in D9a of the leave dialog.
- **Binding.** The host action `game.reset` ("Restart game") is
  registered by the toolkit with no default binding. It only opens the
  menu on the Restart dialog. The menu opens if it was closed, and Go Back
  returns to the game. A pad chord can therefore never reset the game on
  its own. There is no `game.quit` action.
- **While waiting.** Between the confirm and the reset (or the quit), the
  dialog shows "Restarting…" (or "Quitting…") and takes no input. If the
  saves wait (D4) runs past 500 ms, it shows "Waiting for the game to
  finish saving…". The menu closes when the new boot starts.

### D2. The mechanism: an in-process reset

`xbox_reset_request(reason)` (new, `src/kernel/kernel_reset.c`) runs the
reset on a host thread of its own, the reset thread. The steps:

1. **Saves** (D4): wait for quiet, then freeze.
2. **Stop the guest** (D3): every guest thread unwinds to its trampoline.
   Created threads exit. The boot thread stops at its boot loop.
3. **Pause the devices** at their own loop heads, by a per-device pause
   flag, after their queues drain:
   - `nv2a-ack` stops walking the pushbuffer, and stops `dsp_ack_tick`
     and `poke_tick`, but the thread keeps running its message loop: it
     owns the D3D11 window and device on Windows;
   - `vblank-ack` stops delivering DPCs; `nv2a-kick` and the raster
     workers idle;
   - the APU thread and the DSP GP and EP workers idle;
   - `kernel-timer`, `ohci`, `host_open`, `vp-pump` and the present
     thread idle;
   - the **watchdog** is paused, or it would report the stopped guest as
     a hang;
   - with `RECOMP_FMV_HOST` on Windows, the host player is stopped and its
     own window and D3D8 device closed.
   The window thread and the host audio thread keep running and are told
   to drop what came from the guest.
4. **Rebuild** (D5): the reset hooks run in a fixed order and put every
   module back to its start state; guest memory is cleared and the XBE's
   sections are loaded again.
5. **Resume the devices** and release the boot thread. It runs the guest
   half of the boot (D6) and calls the entry point again.

The window shows its last frame, then black, through the reset. No guest
frame is presented between steps 2 and 5. The log has
`[RESET] begin (<reason>)`, `[RESET] guest stopped (<n> threads, <ms>)`,
`[RESET] rebuilt (<ms>)` and `[RESET] boot <n>`.

**Refusals at request time.** A reset is refused once
`HalReturnToFirmware` has started (the process is already on its way
out; a flag set at the bridge's entry). A second request while one runs
is ignored with `[RESET] already running`; the dialog is input-locked
from the confirm on, so only `game.reset` can ask twice.

**Failure.** A step that does not finish in its time (2 s for the guest
stop, 2 s for the devices) logs `[RESET] stuck at <step>: <who>` and the
process ends as a quit does, after the exit hooks. The saves are already
safe (D4), so nothing is lost but the session. This is the safety net for
a missed unwind point; the soak (D8) has to keep it from happening.

### D3. Stopping the guest: the shared unwind

This is save-states phase 3's unwind (tasks 3.1 and 3.2) and the part of
phase 2's cooperative wait abort it stands on, built here as a layer of
its own, `recomp_guest_unwind`. save-states reuses it later (D7).

- **The request.** The reset thread sets `g_xbox_reset_pending`, raises
  `g_xbox_guest_cpu_preempt`, and signals a per-thread **unwind handle**
  for each guest thread.
- **Unwind points.** A guest thread unwinds only where it holds no bridge
  lock:
  - `xbox_GuestCpuPreempt` (every back edge), with the reset check placed
    before its three early returns (Facts), so it works with the lock on
    or off and in the deterministic path;
  - `xbox_SpinWait` and `xbox_SpinWaitKick`;
  - the guest CPU lock's acquire;
  - every bridge wait, which also waits on the thread's unwind handle
    (save-states D1's cooperative abort, without the state record). The
    wait returns "unwind" before it changes any guest state;
  - the entry of every kernel bridge call (a check of the flag).
- **The jump.** `bridge_thread_main`, `xbox_thread_wrapper` (the
  `kernel_thread.c` creator, if phase 0 finds it used) and the boot loop
  set a `jmp_buf` before they call guest code. At an unwind point the thread
  `longjmp`s there. Lifted frames own no host resources (save-states
  facts). The guest `setjmp` slots belong to the guest memory being thrown
  away and are cleared in D5.
- **Locks a thread still holds: never destroyed.** At the stop, each
  guest-object host lock (a mutant, a critical-section shadow) is in one
  of three states:
  1. *free*: destroyed, as any other object;
  2. *held by the boot thread*: the boot thread is reused, so it releases
     what it holds itself (it is the owner, and the shadow records the
     depth) before it waits at the boot loop; then the lock is destroyed;
  3. *held by a thread that exits*: **abandoned**. It is removed from the
     kernel's tables and never destroyed or unlocked, since on POSIX that
     is undefined for a locked recursive mutex. Its memory is leaked. On
     Windows a mutex is closed (its owner's exit marks it abandoned, which
     is defined); a `CRITICAL_SECTION` is leaked there too.
  The new boot creates its own objects, so nothing reaches an abandoned
  one. Each reset logs `[RESET] abandoned <n> locks`. The count is small
  (the locks held at a flip; phase 0 measures it) and each costs well
  under a kilobyte, so the soak (D8) measures memory with the abandoned
  bytes subtracted and checks the count per reset separately: at most the
  number held at the stop, never growing across resets.
  Toolkit-internal host locks are never held at an unwind point; task
  1.2 checks it per point, and a debug assertion checks a per-thread count
  of held bridge locks at each unwind.
  *Refined in phase 1:* every unwinding thread, not only the boot thread,
  leaves the critical-section shadows it owns, each recursion, before the
  jump. It is the owner, so this is defined on both hosts, and it wakes a
  waiter blocked in a plain host `EnterCriticalSection`, which no unwind
  event reaches. Rule 3 now covers mutants only; the abandoned count is
  logged at phase 2's table teardown. The held-lock count is
  `xbox_GuestUnwindHold`. It is held over an ISR or DPC run on a guest
  thread, and a point inside it refuses and lets the next point unwind.
  On Windows the waits gain the unwind event as one more handle (20 ms
  polls for wait-all and full 64-handle waits) instead of an APC.
- **Exit.** A created thread returns from `bridge_thread_main` after the
  jump, through its usual exit path (its TIB and stack freed). The boot
  thread waits in the boot loop. The reset thread waits until the number
  of live guest threads is zero, plus the boot thread at the loop.
- **With the lock off (Burnout 3).** Guest threads run in parallel; each
  stops at its own next point. This is save-states D2 option (b), which
  save-states rejected for its *save* (it needs one exact moment for the
  whole state). A reset needs no such moment: it throws the state away,
  so stopping the threads one by one is enough.
- **Threads outside the guest.** A host thread that calls into guest code
  (an APC or DPC delivered on a device thread, a DSound callback) gets
  the same unwind point at its call-in and is treated as a device thread.

### D4. Saves first, then freeze

The order, before D3:

1. **Wait for quiet.** Poll `xbox_saves_busy()` every 50 ms for up to 10 s
   (`SAVES_QUIET_MS` is 2 s, and a BLiNX 2 save writes three files over a
   few frames). Past 10 s, give up: the dialog says "The game is saving.
   Try again in a moment." Nothing changes.
2. **Freeze the saves.** `xbox_saves_freeze()` (new, `kernel_file.c`)
   takes the guard's lock, checks again that no file handle is open under the save trees, and
   sets the frozen flag. A later `NtCreateFile`/`NtOpenFile` on a save
   path (`xbox_path_is_save`), and a relative open under a tracked handle,
   waits on the thread's unwind handle and unwinds (D3) instead of
   opening. If the second check finds a handle open (a save began between
   1 and 2), the freeze returns 0 and step 1 runs again with the time
   left. This closes the race with the guest CPU lock on or off, so it
   works for Burnout 3 (lock off) as well as cat (lock forced on).
3. After the rebuild, the new boot clears the flag before the entry point
   runs (`xbox_saves_thaw()` in the kernel's reset hook).

Nothing has to be flushed: host writes are synchronous, and
`NtFlushBuffersFile` calls are already `fsync`. The RAM cache is dropped
and seeded again, as at a cold start. The cost to stock runs is one atomic
load of the frozen flag on each save-path open.

**Quit** (D1) uses steps 1 and 2 too, then `recomp_quit_post("menu")`.
With no window to take the quit (GDI), it runs the exit hooks and
`ExitProcess(0)` on a thread of its own, as `pad_quit` does. The window's
close button and a launcher's kill are unchanged.

### D5. Rebuild: reset hooks

- **The registry.** `recomp_reset_hook_add(name, order, fn)` (new,
  `src/platform/recomp_reset_hook.{c,h}`, beside the exit hooks). The
  hooks run on the reset thread, in order, with every guest thread gone
  and every device paused. Each hook logs its name and time under
  `RECOMP_TRACE=reset`.
- **Order** (bands, so a game or a mod can slot in). The devices are
  paused first (D2 step 3); then:
  1. renderer: drain in-flight command buffers (Metal) and the immediate
     context (D3D11, on `nv2a-ack`); drop the texture, surface,
     render-target and vertex caches that came from guest memory; keep
     the device, the swap chain, the shader caches keyed by content and
     the present chain; clear the backbuffer to black;
  2. PGRAPH, the walker's carry-over, the HLE D3D8 state;
  3. APU: the register files, the voices, the DSP cores, the HLE DSound
     state and the WMA decoder (`src/audio`); the DSP JIT's code cache is
     kept only if phase 0 shows it is keyed by the program's contents
     (task 0.10), else dropped; the host audio stream is flushed and keeps
     playing silence;
  4. input: OHCI, the guest-side pad state, the `host_open` thread's
     queue; the host pads stay connected and are reported again as at
     boot;
  5. video: the video pump reset; with `RECOMP_FMV_HOST` (Windows), the
     host player was stopped in D2 step 3. A stock movie is guest code
     and needs nothing here;
  6. kernel objects: every handle closed (files, events, mutants,
     semaphores, threads), the host sync objects behind guest objects
     destroyed or abandoned (D3), the KE shadow, the APC rings, timers and
     the DPC queue cleared;
  7. guest memory, cleared **in place**: guest RAM and the contiguous
     window zeroed through the existing mappings, never unmapped; the MMIO
     trap pages and the watch re-protects stay mapped and armed, and the
     clear skips them; the heap and arena bookkeeping reset; the guest
     `setjmp` slots and the caches that hold guest pointers cleared;
  8. the XBE's sections loaded again from the image (a fresh read, so a
     section the title patched in RAM comes back as shipped);
  9. the guest-memory parts of the host-half inits, run again in their
     boot order over the fresh image: the thunk table patch (after its
     `VirtualProtect`) and `kernel_data_init`; the TIBs and worker stacks;
     the APU's guest windows. Each is split out of its init into a
     function both the init and this band call;
  10. clocks and storage: the clocks put back so `KeTickCount` and the
      guest time start again as at boot; the RAM cache seeded again; the
      saves thawed;
  11. mods: each enabled mod's `on_reset` (D6a);
  12. the game's own hook (D6).
- **What stays.** The window and its mode, the GPU device and swap chain,
  the host audio device, the config and the env table, the menu and its
  unsaved state, the bindings and the action table, the mods' settings,
  the logs, the profilers' totals, the crash handlers, the dispatch
  table (constant after `recomp_dispatch_init`).
- **The audit.** Phase 0 classifies every piece of state listed in Facts
  (file-scope and function-local statics, thread-locals, `INIT_ONCE`
  guards, run-state globals, in the toolkit including `src/audio`,
  `src/enhance`, `src/platform` and the backends, and in cat's sources
  and mods) as *keep*, *reset* or *constant*, and every init-once guard as
  one whose init must run again or not. The list is committed as
  `docs/reset-statics.md` in the toolkit, and a script (task 0.2) flags
  new statics in a toolkit diff so the list stays current. Each *reset*
  static is reset by its module's hook. This is the bulk of the work and
  the main risk (Risks).

### D6. The boot loop; what a game declares

- **The toolkit owns the guest half of the boot.**
  `xbox_boot_run(entry, game_boot)` (new, `src/kernel/kernel_boot.c`)
  sets the boot thread's unwind point and loops:
  1. the guest half of the boot: the XBE init-flag patch, `g_esp`, the
     game's `game_boot` callback (cat's pad init);
  2. `entry()`;
  3. on an unwind: wait for the reset thread's rebuild, log
     `[RESET] boot <n>`, go to 1.
  A return from `entry()` without a reset ends the process as today.
- **The host half runs once**: crash diagnostics, the XBE load,
  `xbox_MemoryLayoutInit`, the APU, `xbox_kernel_init`, `xbox_path_init`,
  `xbox_kernel_bridge_init`, `recomp_dispatch_init`, the watchdog, cat's
  save seed (it must never run again: it would copy the seed over the
  saves made since the start), and the pre-launch screen once
  pre-launch-screen lands. The memory, kernel and APU inits stay as they are;
  their reset hooks put them back to the state these inits left.
- **A game declares:**
  - its boot through `xbox_boot_run`, with its guest-side setup moved into
    `game_boot` (cat: `src/main.c`, the save seed and pad init). A game
    that still calls `xbe_entry_point()` itself gets the Restart row
    greyed out with "this game does not support restart yet". cat's
    save seed stays in the host half; `RECOMP_SAVE_SEED` is also part of
    cat's automation reason, since only scripted runs set it;
  - one reset hook for its own statics (`recomp_reset_hook_add("game",
    RECOMP_RESET_GAME, fn)`): cat's `recomp_manual.c` and `pad_*` hold
    statics that cache guest pointers or one-shot flags, and the phase 0
    audit lists them;
  - its automation reason (the pre-launch gate's string; BLiNX 2's
    `RECOMP_INPUT_SCRIPT` and its `*_PROOF` keys);
  - optionally `xbox_reset_disable(reason)`, for a game whose boot cannot
    be repeated.
- The new-game template uses `xbox_boot_run` and an empty game hook, so
  new games carry both.
- **Generated code** keeps its globals in guest memory, which D5 clears.
  Phase 0 checks the generated code for host statics (none are expected:
  the lifter emits none outside the dispatch table).
- **Pre-launch screen** (future work: pre-launch-screen is not
  implemented). Once it lands it sits in the host half, so a reset does
  not show it again: the player asked to go back into the game.
- **Restart-class settings.** Settings the guest reads through the kernel
  at boot (`system.language` through `XGetLanguage`, the video flags
  behind `display.aspect`) take effect after a reset, since the kernel's
  reset hook reads them again. Host-side ones (`present.surface`,
  `overlay.ui_scale`) still need a quit. The "applies at restart" status
  says which: "applies at Restart game" or "applies after quitting".

### D6a. Mods: declaring guest state and `on_reset`

- **The declaration exists but is not read.** `needs` (`mod.h`) has
  `XBOX_MOD_NEED_STATE`, `_POKE` and `_HOOK`. This change makes it
  binding for the reset: the toolkit records, per mod, every guest hook it
  installs and every guest poke or state read it registers through the
  API (`api->hook`, the poke and state helpers), and logs
  `[MOD name] undeclared <kind>` at the first use not covered by `needs`.
  A debug build fails the mod's init on it; a release build counts the
  mod as declaring it.
- **`on_reset`**, appended to `struct xbox_mod` (v5, zeroed in older
  tables like v4's fields): called in band 11 with the guest gone and the
  fresh image loaded. The toolkit has already removed the mod's guest
  hooks (it recorded them); the mod drops its guest pointers and cached
  addresses and re-installs what it needs, as at init.
- **The rule.** An *enabled* mod (its init ran and returned 0, and
  `api->active()` or its `follows` key says it is on) that declares or
  was seen using STATE, POKE or HOOK and has no `on_reset` turns the
  restart off with "mod <name> does not support restart". A disabled mod
  never does.
- **cat's 10 mods** each get an `on_reset` (tasks 3.6): collision,
  crystals, debug menu, entities, free camera, glow, HUD, LOD scale, shop
  and walls. Most hook or poke guest state.

### D7. Never during automation; who else can turn it off

The Restart row is greyed out with its reason (shown as its help line),
and the action does nothing (`[RESET] refused (<reason>)`), when any of
these holds:

1. a DEBUG-tier key is set: one walk of the `recomp_env` table, the
   pre-launch gate's rule 4. That covers `deterministic`, `det_trace`,
   `pad_script`, `pad_record`, `pad_quit`, the frame and audio dumps,
   and every other harness key;
2. `RECOMP_WINDOW_QUIT_AFTER` is set (benches);
3. the run is headless (`RECOMP_HEADLESS`), or there is no window
   presenter;
4. the game gave an automation reason;
5. the game turned the action off (`xbox_reset_disable(reason)`), or does
   not boot through `xbox_boot_run` (D6);
6. an enabled mod that declares or uses guest state, pokes or hooks has
   no `on_reset` (D6a);
7. `HalReturnToFirmware` has started (D2).

Goldens pin `RECOMP_MENU=0`, so the System page and its rows never exist
in them. A reset therefore never cuts a pad record in two, never replays a
script into a second boot, and never splits a deterministic trace. If
pre-launch-screen has not landed when this is built, this change adds
the shared helper (`xbox_enhance_automation_reason(game_reason)`) and
the pre-launch gate reuses it.

Quit is not refused by rules 1 to 4: it ends the run as the close button
does, and a pad record ends cleanly at a quit. With no window the menu
does not exist, so rule 3 holds for it trivially.

### D8. Verification

The reset's risk is a static left behind. The gate is therefore that a
reset boot behaves as a cold boot, measured.

- **The test trigger.** A DEBUG-tier row, `reset_at=<flip>`, resets once at
  that flip without the menu and without the D7 rules. It is test-only, never documented for
  players, and refused with a message when the enhancements layer is off.
- **Baseline first.** The equivalence below assumes two cold runs in the
  deterministic mode already give identical frames and audio. That is
  not yet shown (is open). Phase 0 runs it (task 0.9, exit
  criterion 6); without it, a reset mismatch could not be told from
  ordinary non-determinism.
- **Equivalence.** In the deterministic mode, a run with
  `reset_at=<N>` must give, from the reset boot's first flip, the same
  frames and the same audio hash as a cold run from its first flip, for
  the length of the stage-1 golden scenario (`@stage1` replayed after the
  reset). Run on Metal and on D3D11. This is the merge gate. A mismatch
  is a static left behind, and the frame where it diverges points at it.
- **Soak.** 50 resets in a row at random flips through attract, stage 1
  and a story scene: host handle count, guest heap, texture count, GPU
  memory and RSS flat within 2 % after the first reset, with the
  abandoned locks' bytes subtracted (D3); the abandoned count per reset
  no larger than the locks held at its stop and not growing; no
  `[RESET] stuck`.
- **ctests** (toolkit, `tests/`, run by `tests/posix_ctest.sh`):
  - `guest_unwind`: threads parked at each unwind point kind (back edge,
    spin, CPU lock, each wait bridge, a bridge entry) unwind; a thread
    owning a critical-section shadow and a mutant unwinds and the objects
    are re-created; the held-lock count assertion fires on purpose;
  - `reset_hooks`: order, bands, a hook that fails;
  - `reset_rules`: the D7 table, driven through `recomp_env_set`, gives
    each reason and the row's grey state;
  - `reset_saves`: with a fake clock, the D4 wait and give-up, the second
    check inside the freeze, an open under the freeze that unwinds, the
    thaw;
  - one module test per reset hook where it can run standalone (the
    kernel's handle table, the ramfs seed, the APU registers);
  - menu: through `enhance_menu_event`, the System page and its two rows,
    each dialog's focus on Go Back, the unsaved-settings variants, Go
    Back on any other event, the greyed row's help line, and `game.reset`
    opening the dialog and never resetting.
- **cat:** `uv run pytest scripts` and the ruff checks.
  `scripts/test_config_default.py` already checks `RECOMP_MENU=0` in
  `golden.json`. The env-doc check covers the new rows.
- **Hand checks** (the implementation's gates):
  - Mac, Metal: start, save in-game, Restart, load the save; restart 5
    times in a row; Restart while the game saves; Restart during an FMV;
    windowed and fullscreen; Quit with and without unsaved settings.
  - Native Windows, D3D11, from a Steam shortcut: the same, plus the
    overlay and the window mode unchanged after a restart.
  - Deck game mode (Steam + Proton): the same, plus gamescope focus and
    Steam Input unchanged (one process, so nothing should change).
- **Goldens:** the runtime is touched throughout, so Metal on the Mac and
  D3D11 on native Windows run before the merge; the Deck goldens run
  later and do not block. The stock path changes by the unwind checks at
  bridge entries and waits; the performance rule (25 % flips/s) applies.

### D9. Follow-ups (not in this change)

- **Saves "Import and restart"**: the tracker item. With this reset, the import can
  restart in the window instead of quitting.
- **A title's quick reboot to itself.** `HalReturnToFirmware(2)` with a
  launch data page naming the running XBE could become a reset, with the
  page carried over. Only if a title needs it.
- **save-states phase 3.** Its unwind is D3. What it adds on top is the
  capture and restore of the state.

### D10. Alternatives considered

**Relaunch the executable: rejected by the user (2026-11-03).** The first
draft (`1824b638`) restarted by starting the same executable again with a
hand-off key, `RECOMP_RESET_GEN`: exec in place on macOS and Linux
(`posix_spawn` with `POSIX_SPAWN_SETEXEC`, `execve`), and on Windows and
Proton a supervisor (the first instance closes its window, audio and
handles, then starts and waits for each child, which ends with a reset
exit code). It was about 1 to 2 days of probes and 5 to 7 of work, and
reset everything by construction. The user chose to wait for the reset
that keeps the window. That draft's costs were the window closing and
opening again (1 to 2 s, a new window under gamescope), a second process
on Windows, and the launcher probes it needed. None of it is in this
design: no supervisor, no `RECOMP_RESET_GEN`, no exec. Its saves wait
and freeze (D4) and its automation rules (D7) carry over.

**Restore a boot-time save state.** With save-states built, a reset could
load a state taken at the entry point. It needs all of save-states
(about 40 to 61 agent days, parked), and the boot state would have to be
taken on every start. The reset needs a strict subset (D3), so it comes
first and save-states builds on it.

**Reset without stopping the devices.** Pausing only the guest threads
and resetting device state under each device's lock would avoid the pause
flags, but every device would need a lock covering its whole state and a
reset that races its own loop. Pausing at the loop head is simpler and
each device has one already.

## Effort

Sized from the counts above. The unwind is save-states' estimate for its
phase 3 (5 to 8) plus the cooperative wait abort from its phase 2, without
the state record.

| Phase | Agent days | What |
|---|---|---|
| 0. Facts (own milestone) | 5-8 | the state audit (file-scope and function-local statics, thread-locals, `INIT_ONCE` guards, run-state globals; the toolkit with `src/audio`, the enhance layer and the backends; cat's sources and 10 mods) and its script, the thread and device inventory, the wait bridges, generated code checked, the boot split, the DSP JIT keying, the stop probe and its runs, the cold-vs-cold baseline, the mods' `needs` checked; then **go/no-go** (task 0.9) |
| 1. Unwind | 7-10 | the unwind handle in every wait bridge, the unwind points (the probe flag before `xbox_GuestCpuPreempt`'s early returns), the `jmp_buf`s in both thread creators, thread exit, the lock rule (free, owned by the boot thread, abandoned), the held-lock assertion, the ctests |
| 2. Reset hooks | 20-28 | the registry, then a hook per module: kernel 6-8, renderer and PGRAPH on Metal and D3D11 5-7, APU, DSP, DSound and WMA 4-5, input and USB 1-2, video and the host FMV path 1, guest memory in place, the XBE reload and the guest-memory init split 3-5 |
| 3. Boot loop and games | 3-5 | `xbox_boot_run`, the template, cat's `main.c` (save seed kept in the host half) and game hook; BLiNX 1 and the other active games one day each where they adopt it |
| 3m. Mods | 5-7 (was 3-5; phase 0 counts) | the `on_reset` field (v5), the `needs` check made binding, the hook record, and an `on_reset` for each of cat's 10 mods |
| 4. Menu | 2-3 | the System page, both dialogs, Quit, `game.reset`, the rules (with the firmware and second-request refusals), the saves wait and freeze |
| 5. Verification | 6-9 | equivalence on Metal and D3D11, the soak, Burnout 3's non-deterministic check, the hand checks on three hosts, the goldens, fixing what they find |

The total is about **46 to 68 agent days**, of which phases 1 to 5
(with the mods) are **41 to 60**. That is above the 50 agent days set
for phases 1 to 5 before phase 0 (task 0.9, criterion 7), already at the
spec stage. The review of `8d7d34f7` put it at 45 to 65; the rise
from the earlier 34 to 51 is the wider audit, the in-place memory clear
with the guest-memory init split, the lock rule, the mods' `on_reset`,
and the baseline. Phase 0 re-estimates from its counts; if the figure
stays above 50, the go needs the user to accept it or to narrow the
scope (for example BLiNX 2 only first, other games after). The
relaunch was 6 to 9.

After phase 0 (Facts, "Phase 0 results"), phase 3m is 5 to 7, so
phases 1 to 5 are **43 to 62** agent days and the whole change 45 to 70.

## Risks

- **A static left behind.** About 1,700 statics, plus the thread-locals and
  guards, are audited by reading.
  One missed gives a second boot that differs from the first: a cached
  guest pointer into cleared memory (a crash), a one-shot flag that never
  fires again (a missing effect), a counter that does not start at zero
  (a timing change). These look like game bugs. The equivalence gate (D8)
  catches what the tested scenes reach; it cannot catch a static only a
  later scene uses. The static-diff script keeps new ones from slipping
  in.
- **A thread that never reaches an unwind point.** A guest thread in a
  host call that never returns (an FMV decoder call, a blocking host read)
  is not at a back edge. Phase 0 lists the host calls guest threads make
  and gives each a way out. The 2 s timeout and the quit fallback (D2)
  keep a failure from hanging the game.
- **Host locks.** A toolkit-internal lock held at an unwind point
  deadlocks the next boot. The held-lock count assertion and the
  per-point review (task 1.2) close this. Guest-object locks held by an
  exiting thread are abandoned, never destroyed (D3): a bounded leak per
  reset that the soak tracks on its own.
- **Device teardown in place.** The D3D11 device lives on the ack thread,
  which must keep running; Metal has command buffers in flight. Draining
  both before band 1 is new code on both backends, and the backends must
  agree.
- **The DSP JIT and the APU.** The JIT holds code pages and the DSP cores
  hold state the guest uploaded; a stale program would play wrong audio.
  The equivalence gate's audio hash checks it.
- **Mods.** A mod that keeps a pointer into guest memory across the reset
  crashes. Mods without `on_reset` that hook guest state turn the reset
  off (D7 rule 6), so the cost is a greyed row, not a crash.
- **Burnout 3 and other games with the lock off.** The unwind works with
  the lock off (the reset check sits before `xbox_GuestCpuPreempt`'s early
  returns), but guest threads run truly in parallel there, so the stop
  takes the slowest thread's time to reach a point. Phase 0 measures it
  on Burnout 3. The deterministic mode needs the lock, so Burnout 3 gets
  no frame equivalence: its check is the goldens' tolerance after a
  reset plus the soak (task 5.6).
- **No deterministic baseline yet.** If two cold runs do not match,
  the equivalence gate cannot run as written. Phase 0 checks
  it first (task 0.9 criterion 6); if it fails, the gate falls back to a
  golden-tolerance check after the reset, which catches less.
- **Effort above the budget.** 41 to 60 days for phases 1 to 5 against
  50 (Effort).
- **The stock path.** The unwind check at each bridge entry is one load
  and a branch; the wait bridges wait on one more handle. The goldens'
  flips/s check it.
- **The 10 s saves give-up.** A title that keeps a save file open all the
  time could never be reset. None is known; overlay-saves has the same
  limit for export.
- **Dependency on parked work.** D3 is save-states phase 3's design. If
  save-states is un-parked later and its design changes, the two must be
  kept as one layer (D3, task 1.1).

## Settled (the user, 2026-11-03)

1. **The unwind is built here.** `recomp_guest_unwind` (D3) is part of
   this change, as a layer save-states reuses later. save-states stays
   parked.
2. **Phase 0 starts now**, as a milestone of its own that merges and runs
   alone (tasks 0), with its exit criteria in task 0.9. Phases 1 to 5 wait
   for the go.
3. **A restart during an FMV is allowed** and stops it. A stock movie is
   guest code and unwinds with its threads; the opt-in host FMV path
   (`RECOMP_FMV_HOST`, Windows) is stopped in D2 step 3.

## Settled (the user, 2026-11-04)

1. **Go, BLiNX 2 first** (task 0.9, criterion 7). The user accepted the
   revised 43 to 62 agent days for phases 1 to 5, scoped to BLiNX 2.
   Phases 1 to 5 build and verify the reset for BLiNX 2 only. Other games
   add their game hook (D6) and their verification later, each as its own
   follow-up.
