# Design: save states

## Context

A save state is the whole game at one moment. Loading it later, in this
process or a new one, carries on as if the game had never stopped. The
toolkit runs lifted guest code natively, so the hard part is not memory but
threads. This design rests on the spike of 2026-10-22, which drew on
three sources:

- the toolkit at `posix-host/portability` `cae8c90e`, read only;
- cat at `main` `89b45ab`;
- prior art: xemu, Dolphin, PCSX2, RPCS3, N64Recomp, and bsnes's
  cooperative-thread serialization.

It also used one throwaway measurement, described under Facts.

### Facts the design rests on

**Guest memory.** Paths are in `xboxrecomp/src/kernel/xbox_memory_layout.c`
unless named.

| Region | Size and mapping | Notes |
|---|---|---|
| RAM | 128 MB (cat sets devkit size), one file mapping, 28 mirror views | OS picks the base; `g_xbox_mem_offset` is non-zero on the Mac |
| Contiguous window, 0x80000000 | 64 MB, its own mapping (`g_contig_mapping`); the tiled aperture at 0xF0000000 is a second view of it | |
| NV2A aperture, 0xFD000000 | 16 MB plain memory | DMA PUT and GET at +0x800040 and +0x800044 |
| MCPX aperture, 0xFE800000 | first 0x30000 trapped | GP and EP DSP memories are plain pages |
| Flash, 0xFF000000 | 1 MB, zeroed | |

The allocator bookkeeping lives on the host:

- `g_heap_next` and `g_heap_blocks[65536]`;
- the contiguous-arena arrays;
- the `RECOMP_EXT_VMA` page table.

**Registers** are thread-local (`templates/runtime/recomp_types.h`):

- `g_eax` to `g_edi` and `g_esp`;
- the x87 stack and its control and condition words;
- `g_mxcsr`, XMM0-7 and MM0-7;
- `g_fs_base`, `g_seh_ebp`, `g_df` and `g_eflags`;
- `g_ebp`, which every lifted prologue reads (`ebp = g_ebp`), and
  `g_kernel_dispatch_slot`;
- the HAL's `g_current_irql`.

`ebp` and the flag temporaries are C locals in each function; `ebp` is
loaded from `g_ebp` in the prologue. A guest call is a native call, `RECOMP_ABI_CALL(va, fn)` →
`fn()`. The return VA is still pushed on the guest stack, which lives in
guest RAM. cat's generated code has 11,615 functions and about 90,000
direct and indirect call sites.

**Threads.**

- The first `PsCreateSystemThreadEx` runs the title's main routine inline
  on the boot thread, below `xbe_entry_point`. Later ones get a host thread
  each (`bridge_thread_main`).
- The guest CPU lock (`kernel_guest_cpu.c`, `RECOMP_GUEST_LOCK`) lets one
  guest thread run guest code at a time. It defaults off in the toolkit;
  cat forces it on, and Burnout 3 does not set it. ISRs and DPCs run guest
  code without it. With the lock on:
  - every kernel call releases it softly;
  - blocking calls hand it over;
  - a lowered spin wait (`RECOMP_SPIN_WAIT`) or a loop back edge with the
    preempt flag set (`RECOMP_BACK_EDGE`) yields it.
- Host threads that are not guest threads:
  - the timer thread (vblank, DPC queue, `g_timers`);
  - the vblank-ack thread;
  - `nv2a_ack_thread`, which walks the pushbuffer and writes `KeTickCount`;
  - `nv2a_kick`;
  - the OHCI 4 ms tick, which runs the title's ISR;
  - the APU frame, GP and EP threads;
  - the host audio device;
  - the watchdog.

**Kernel objects** are host objects behind tables in `kernel_bridge.c`:

- `s_handle_table[16384]` of host `HANDLE`s;
- `g_ke_shadow[4096]`, which maps guest `KEVENT`, `KTIMER` and thread
  objects to host events and keeps the guest `SignalState` in sync;
- mutants, semaphores and `s_token_thobj`;
- per-thread APC rings;
- `g_async_handles`;
- files: host fds whose position is the fd offset, with every I/O
  synchronous, plus directory contexts.

**Clocks** come from host time:

- QPC, `GetTickCount` (rewritten by `nv2a_ack_thread`) and `GetTickCount64`;
- `rdtsc`, scaled to 733 MHz;
- the 60 Hz vblank grid;
- timer due times, kept in host ms.

**GPU.** The live path is the pushbuffer walker and executor. The
xemu-derived `src/nv2a/` model is not started.

- The decoded state is plain data: `s_gpu` (about 1.3 MB with the open
  batch), `s_vsh`, the texture registers, `s_present`, `s_flip_hold`, the
  vblank and zpass counters.
- Some state needs saving or re-resolving:
  - the walker carry-over (`s_left`, `s_subch`, `s_method`, `g_scanned_put`);
  - the context-DMA binds (`s_sema_bind`, `s_report_bind`);
  - a report the backend may still owe.
- The texture, render-target, shader and PSO caches are keyed by hash and
  rebuild from guest RAM. `scale_drop()` already releases them all.
- Surfaces that exist only on the host:
  - colour targets on D3D11 (`writes_back = 0`);
  - colour targets on Metal until a lazy write-back (`metal_sync_guest`);
  - depth and stencil on every backend.

**APU.** `MCPXAPUState`:

- 512 KB of registers plus the GP and EP register files;
- 256 voice filters that hold host `SRC_STATE` and SVF pointers;
- the DSP cores: the stub `DSPState`, or the dsp56300 JIT over the guest
  MCPX pages with a `p_shadow` cache.

`dsound_device.c` mixer voices hold host PCM pointers. On POSIX, host
audio is an SDL push queue.

**Input.** The OHCI controllers (`s_hc[2]`) and the per-pad
control-transfer state are plain data. The ED and TD lists are in guest
RAM. `usb_gamepad.c` keeps the addresses and configurations. The HLE
XInput layer keeps packet numbers.

**FMV.** The Windows FMV pump is Media Foundation plus the HLE D3D8 device
on its own thread. It is host-only and cannot be saved.

**Determinism.** BLiNX 2 is not deterministic across runs
(`playthrough-replay` design: the loader bumps `0xAE7180`, which seeds
`srand`; movies run on the audio clock). The attract demo and the stage-1
walk reproduce on Metal.

**Measurement (2026-10-22, stale Oct 18 main build, Metal, stage 1 at
t=40 s, `runs/save-states/m1/`, local only):**

- Guest RAM: 12,989 of 32,768 pages non-zero (50.7 MB); `0x5000000` and up
  is empty. zlib level 1 packs the 128 MB to 24.6 MB in 0.56 s in Python.
  The contiguous window was not dumped.
- 15 host threads, 4 of them guest threads.
- A thread dump at t=45 s and t=48 s found these parks:
  - main: `xbox_SpinWait` under `sub_002E7F30` ← … ← `sub_0005F960` (the
    main loop) ← `sub_0029A166` ← `sub_002980E7`, 8 guest frames, at one
    sample, and inside guest code at the other;
  - two workers: `sub_002E0DB0` (cat's vblank-pacer override, a host
    sleep) ← `sub_002A1B20` or `sub_002A1BA0` ← `sub_002D702E` ←
    `sub_002980E7`, 4 frames;
  - one worker: `NtSuspendThread` on itself, 4 frames.
  The parks seen were few and shallow, but the sample was small. Lifted
  code also stops at places that are not call sites: cat has 1,430 tail
  calls, 19,970 back-edge preempt points and 28 spin waits (the
  review of 2c87ab5).

## Goals / Non-goals

**Goals**
- A state taken at a flip loads into a new process of the same build, or
  of a later build of the same XBE whose chunk versions and resume sites
  cover it. The game then continues on Metal and D3D11.
- Fixtures: a golden or a bench starts from a named state, and the state
  regenerates itself from a committed recipe when the build moves.
- A player quick save and quick load, in session, behind
  `XBOXRECOMP_ENHANCE`. The model has N slots that the player can
  rearrange, delete, and export to or import from a file (D9). Phase 4
  ships one slot with a save hotkey and a load hotkey. The slot manager
  comes later, in the mod overlay menu (phase 5).
- A slot holds the state **and the title's own save files**. A load
  restores both together, and an export or import carries both (D3
  `SAVE`). Fixtures use the same mechanism.
- All code is in the toolkit and the CLI. Per-game inputs are data only:
  `config/resume_sites.json` and the fixture recipes, in each game's repo
  (D8). The one piece of per-game code is named in D8.

**Non-goals**
- Loading a state across different XBEs, regions or mods that replace a
  parked function.
- Saving at an arbitrary instruction. The save is taken at a safe point,
  or refused and retried at the next one.
- Bit-exact continuation. The title is not deterministic.
- The equivalence gate (D7) checks what a state can promise: an exact
  round trip, and frames from the state within golden tolerance.
- Saves of other titles, the dashboard settings and the EEPROM. A slot
  carries only its own title's `UDATA` and `TDATA` directories.
- The CPU rasteriser path beyond building, and the HLE D3D8 device.

## Decisions

### D1. Guest-level re-entry, not host stacks

A thread in a state is a list of guest frames, outermost first. Each
frame is one shadow-stack entry:

- `fn`: the guest VA of the function that owns the frame;
- `site`: the guest VA it is stopped at (a return VA, a tail-jump VA or a
  loop label);
- `callee`: the resolved guest VA it called, for every call kind;
- `ebp`: the frame's `ebp` at that site;
- `esp`: the guest `esp` right after the return VA was pushed;
- `kind`: `call`, `tail`, `edge` (a `RECOMP_BACK_EDGE` preempt) or `spin`
  (a `RECOMP_SPIN_WAIT` park).

Each thread also records:

- its TLS register file, written by the thread itself (D2 step 4);
- its guest `esp` at the innermost frame;
- a **park record** for the innermost frame.

**Shadow stack.** The lifter emits, at every call site, a store of the
entry fields into a per-thread array and a depth increment, then the call,
then the decrement. The array and the depth live in one TLS struct, so a
function reaches them through a single TLS access. On macOS arm64 every
`__thread` variable costs a TLV descriptor call that the compiler shares
only per function, so phase 1 measures the layout on the Mac before it is
fixed. The saver reads the array; nothing walks host frames.

- **Indirect calls** (`RECOMP_ICALL_SAFE_AT*`, guarded arms) store the
  resolved callee. On resume the target register may already be clobbered,
  so the resume calls the stored `callee` through the dispatch, never the
  register. It is checked against frame k+1's `fn`.
- **Tail calls** (`sub_X(); return; /* tail jmp */`, `RECOMP_ITAIL`,
  `RECOMP_FALLOFF_TAIL`; 1,430 in cat) push an entry of kind `tail` at the
  tail site. Without it, a chain A → B ⇒ C would read A, C, and resuming A
  would re-enter B with no case that leads to C.
- **Back edges and spin waits** (19,970 and 28 sites in cat) are parks in
  the middle of a function, not at a call. `RECOMP_BACK_EDGE(va)` and
  `RECOMP_SPIN_WAIT` push an entry of kind `edge` or `spin` before they
  yield. The resume case is a `goto` to the loop label the macro already
  carries. The lifter proves which flag temporaries (`_cf` in adc and sbb
  loops) are live across the edge and stores them in the entry, or the
  site is refused.
- **Other live C locals.** A function that keeps any other C local live
  across a site cannot resume there. The lifter knows which ones, stores
  them, or refuses the site (`resume site with live locals: refused`).
  Flag temporaries after a call are re-derived today; phase 0 confirms it.
- **`esp`.** Intermediate frames do not re-push. Their resume sets `esp`
  from the entry and calls the next frame. Only the innermost pending
  kernel call is re-issued with a `PUSH32` of its return VA from the exact
  call-site `esp`, because the dispatch has already popped the return slot
  (`g_esp += 4`) and the bridge may have popped its arguments
  (`g_slot_arg_bytes`).
- **Depth.** Guest `setjmp`/`longjmp` (`recomp_guest_longjmp`, 2 gen files
  in cat) and any host non-local exit skip the post-call decrements.
  `setjmp` records the depth in its slot and `longjmp` restores it. The
  saver also checks the chain: `esp` strictly decreasing outward, and
  `MEM32(entry.esp) == entry.site` for `call` entries. A failed check
  refuses the save.
- **Overflow.** The array has a fixed size (256 entries, measured in
  phase 0). On overflow the depth still counts, the stores stop, and any
  save while the depth is above the size is refused. Stores are never
  skipped silently.
- **Manual overrides** are resumable only as the innermost frame. An
  override in the middle of a chain refuses the save. cat's overrides are
  leaves today; this is a rule, not an accident.

**Resume entry.** A function with listed sites gets a guarded prologue:

```c
if (RECOMP_UNLIKELY(g_state.resume_depth)) switch (recomp_resume_site()) {
case 0x00040185u: /* call */
    ebp = recomp_resume_ebp(); g_esp = recomp_resume_esp();
    recomp_resume_call(recomp_resume_callee()); goto loc_00040185;
case 0x00040210u: /* edge */
    ebp = recomp_resume_ebp(); _cf = recomp_resume_cf(); goto loc_00040210;
...
}
```

- A `call` or `tail` case restores `ebp` and `esp` and calls the stored
  callee, which resumes the next frame. When the call returns, the frame
  continues at the label after it as if nothing had happened.
- An `edge` or `spin` case jumps to the loop label.
- At the innermost frame the park record decides what happens.
- The labels exist already (`loc_XXXXXXXX` follows every call and starts
  every loop). The guest stack is right because it is guest RAM and was
  restored.

**Park record.** Four kinds:

1. *Pending call.* The thread is blocked in a restartable call and is
   re-issued from its caller's site with the guest stack arguments still
   in place. This is RPCS3's syscall restart. Restartable calls:
   - kernel waits (`KeWaitForSingleObject`, `KeWaitForMultipleObjects`,
     `NtWaitFor*`, `KeDelayExecutionThread`);
   - contended `RtlEnterCriticalSection`;
   - `NtSuspendThread` on itself, only while its suspend count is
     unchanged; a resume that arrived during settling makes it *returned*;
   - `NtYieldExecution`;
   - manual overrides listed as restartable in the game's
     `config/resume_sites.json` (cat's vblank pacer `sub_002E0DB0`). The
     lifter wraps each call to a listed function in the pending phase
     word, so no override source changes.

   The record holds the wait's deadline in guest-clock time, taken when
   the wait started. A load re-arms the timeout with the remaining time.
   The guest `LARGE_INTEGER` belongs to the caller and is never
   rewritten.
2. *Returned call.* The call finished, with its side effects done (D2
   step 4), and the thread waits for the guest CPU: in the lock's queue or
   after a satisfied wait. The record holds `eax`, `edx` and the flag state
   the call returned. The resume returns at once, with no second call.
3. *Preempted.* The thread yielded at a back edge or a spin wait. The
   resume is the `edge` or `spin` case.
4. *Saver.* The saving thread itself (D2) is a pending call that has not
   been issued, at the kernel call site where the save ran. That site must
   be listed too.

**Waits abort cooperatively.** A bridge blocks in a host wait without the
guest CPU, and after the wait returns it keeps changing guest state:
`bridge_KeWaitForSingleObject` writes `SignalState = 0` for a consumed
synchronization event, `bridge_user_apc_finish` may run APCs, and the
dispatcher pops the stdcall arguments. A phase word alone races with this:
the host OS can pre-empt the thread between consuming an auto-reset event
and writing the word, and the load then loses a wake. So every bridge wait
also waits on a per-thread **save handle**. The saver signals it once the
signallers are stopped (D2 step 3). Each woken thread then decides its own
state from inside the bridge:

- the guest object was not satisfied: it records *pending* with its
  deadline;
- it was satisfied: it finishes every post-wait side effect and records
  *returned*.

Then it writes its own TLS register file and shadow chain into the state
and parks in the handshake. The classification is exact because only the
thread itself can see where it is.

**Owned objects.** Some guest objects are owned by a thread, and the
ownership lives in host objects: mutants are `CreateMutexW`, owned by a
host thread; guest critical sections are host `CRITICAL_SECTION` shadows
(`kernel_rtl.c`, `xbox_cs_shadow`) with an owner and a depth. A guest
thread that holds a CRT or title lock while it waits elsewhere is normal.
The `KOBJ` chunk therefore needs bookkeeping in every create, release and
wait bridge (D3). On load, each new host thread re-acquires the mutants
and critical sections it owned, to their recursion depth, before any
thread resumes. A barrier holds every thread until all of them have.

**The inline main thread** is saved with its frames from the thread
routine up (`sub_002980E7` for BLiNX 2). The frames below it are
`xbe_entry_point` and the inline `PsCreateSystemThreadEx` bridge, a host
frame around a guest routine. On load the routine is resumed on the boot
thread as an ordinary thread. Titles never return from it. If one did,
its thread would exit like a spawned one, where the original would have
returned to the bridge. That difference is recorded, not hidden.

**Coverage.** Resume entries are emitted only for the sites in the game's
`config/resume_sites.json`: a `sites` list of `{"fn", "site", "kind",
"observed"}` and a `restartable` list of manual-override VAs. The site list
is fed by `RECOMP_STATE_TRACE=sites`, which logs every parked chain at every
flip. A save whose chain holds an unlisted site is refused with
`[STATE] refused: thread T parked at fn+site (not in resume_sites)`, so
coverage grows in testing as `seed_functions.json` did. Phase 1 also
measures emitting entries at every site (code size, build time, frame CPU
time). If that is cheap, the list becomes an exclusion list instead.

**Build option.** All of this sits behind the CMake option
`XBOXRECOMP_STATES`. It defaults **ON**, as a recorded exception to the
CLAUDE.md rule that opt-in features default OFF. The user decided it on
2026-10-22: "Leave them on if it does not impact performance in a
significant way." It changes no behaviour, only adds the instrumentation,
and it is ON only while it passes the performance gate in D7.4; if it
fails, it ships OFF and the numbers go back to the user.

- The option changes the lifter's output, so it is part of the gen key,
  and `blinx2 analyze` and `blinx2 recomp` (through the CLI) pass it.
- The OFF build stays buildable and is built in CI.
- The player feature (hotkeys and slots) stays behind
  `XBOXRECOMP_ENHANCE` and off by default. This decision is only about
  the instrumentation being compiled in.

*Rejected:*

- **Host-stack or process snapshots** (raw stack copies, `fork`, CRIU).
  - The host stacks hold host pointers, and ASLR, a rebuild or a new GPU
    device moves them. N64Recomp dropped save states for exactly this
    (Zelda64Recomp #418).
  - CRIU exists only on Linux and has no Metal or D3D support.
  - `fork` copies one thread.
  - A raw-stack "hibernate" works only in one process. bsnes and RPCS3
    keep it for run-ahead or suspend, never for files.
- **Main-loop re-entry** (bsnes "fast sync": restart each thread at its
  loop head). This needs per-game knowledge of every thread's loop head
  and its live state, and it skips work the title was halfway through.
- **Interpreting the parked frames.** The toolkit has no x86 interpreter,
  and one per frame is a second CPU to keep correct.
- **Resume entries at every site from the start.** That adds about
  90,000 call cases plus the edge cases to cat's 138 MB of generated C,
  costing build time and I-cache, before anyone knows they are needed. It
  stays an option, measured first.
- **A phase word alone for waits.** It races with the post-wait side
  effects, as above.

### D2. The safe point is the flip, under the guest CPU lock

**The safe point holds only when `RECOMP_GUEST_LOCK` is on.** The lock is
a CONFIG key that defaults off in the toolkit (`recomp_env.h`, "upstream,
default off"). cat forces it on (`src/main.c`). Burnout 3 never sets it,
so its guest threads run guest code at the same time and "the saver keeps
the guest CPU" stops nothing. With the lock off, every `RECOMP_STATE_*`
key is refused at start with `[STATE] disabled: needs RECOMP_GUEST_LOCK=1`.

How Burnout 3 gets a safe point is decided in phase 0 (task 0.6). The two
options:

- **(a) Turn the lock on in Burnout 3**, as its own gated change: its
  goldens on Metal and D3D11, Proton and native Windows runs, and a speed
  check against the CLAUDE.md flags. The toolkit keeps one quiesce path.
- **(b) A stop-the-world path that does not need the lock.** Each guest
  thread polls a stop flag at kernel-call entry and at back edges (the
  preempt flag is polled there already) and parks itself in the
  handshake. It works for any title, but it is a second quiesce path to
  keep correct, and threads in long host calls still need the D1 abort.

**Recommendation: (a).** The lock is the toolkit's tested serialization,
cat already runs on it, and it makes the classification simple. (b) is
the fallback if phase 0 finds that Burnout 3 with the lock fails its
goldens or loses 25 % or more of its speed.

**Trigger.** A save is requested through `xbox_StateRequest(path)`, which
these call:

- a hotkey;
- `RECOMP_STATE_SAVE=<file>[@flip N]`;
- the `savestate NAME` pad-script step;
- a CLI fixture run.

The flip is `NV097_FLIP_STALL`, which `on_flip` sees on the
`nv2a_ack_thread` host thread, not a guest kernel call. `on_flip` turns a
pending request into a save flag. The next `kernel_thunk_dispatch` entry
on the guest thread that holds the CPU runs the save, after
`xbox_IrqSafePoint()`, so the thread is at `PASSIVE_LEVEL` with every
delivered interrupt finished. That thread is the saver. Its own park
record is a pending call at that kernel call site (D1, kind 4).

**Order.** Each step waits for the one before. The whole save is bounded
at two frames, then refused and retried.

1. **Freeze guest CPU hand-outs.** The saver keeps the CPU and stops
   handing it over: no 2 ms poll turns and the guest_sched 4 s valve is
   disabled, so no turn is handed out mid-save.
2. **Drain the GPU with the device threads still live.** `nv2a_ack_thread`
   walks until the flip hold is released (it needs the vblank count, which
   the timer and vblank-ack threads keep advancing) and `GET == PUT`, with
   no report still owed.
3. **Stop the device threads** at their tick edges, each by a quiesce
   flag:
   - the timer thread (no DPC mid-delivery, timers read as remaining
     time);
   - vblank-ack;
   - the OHCI tick (its ISR runs guest code without the lock);
   - the APU frame, GP and EP threads (at a frame edge, the JIT idle);
   - the watchdog, paused.
   After this step the saver is the only thread that can run guest code.
   ISRs and DPCs run guest code without the guest CPU
   (`kernel_guest_cpu.c` header, `kernel_hal.c`), so the classification
   cannot come earlier: a DPC could still wake a waiter it had classified.
4. **Classify the guest threads.** The saver signals every thread's save
   handle (D1). Each thread confirms its state from inside its bridge or
   queue slot, writes its own TLS registers (`g_eax`…`g_edi`, `g_esp`,
   `g_ebp`, x87, MXCSR, XMM, MMX, `g_fs_base`, `g_seh_ebp`, `g_df`,
   `g_eflags`, `g_kernel_dispatch_slot`, `g_current_irql`) and its shadow
   chain into the state, and parks. TLS is per thread, so no other thread
   can read it. A thread inside a non-restartable call (file I/O,
   `NtCreateFile`, a decoder) is let run to its return, which is quick
   because all I/O is synchronous. The save is refused, with the reason,
   when:
   - a guest callback runs inside a host frame (an ISR, a DPC, an APC, the
     OHCI ISR on its worker stack);
   - a thread is at raised IRQL or holds the dispatch gate;
   - a chain holds an unlisted site, a mid-chain override or fails the D1
     checks, or the shadow array overflowed;
   - a non-restartable call has not returned within the bound;
   - a thread holds a wait handle that falls back to
     `XBOX_TO_NATIVE(object)`, until phase 0 has counted those.
5. **Read back the surfaces** (D4, cross-backend loading).
6. **Copy.** Guest pages are copied into a buffer sized from the last save
   (Dolphin's 110 % rule); the host tables are serialized.
7. **Release.** Device threads, then guest CPU hand-outs, resume.
   Compression and the file write run on a host thread.

The pause target is two frames at 30 fps. About 60 MB of `memcpy` takes
roughly 10-20 ms, the readback a few ms.

A refusal never changes the game. It logs `[STATE] refused: <reason>` and
retries at the next flip, up to `RECOMP_STATE_RETRY` flips (default 30). A
player sees "can't save here" only after the retries run out.

*Rejected:*

- **Settle the threads first, then drain the GPU** (the first draft). It
  deadlocks: right after a flip a flip is usually held, and its release
  needs the vblank count that the stopped device threads no longer
  advance.
- **Saving between any two kernel calls.** It is no simpler, and the
  pushbuffer and the device threads are not at an edge there.
- **Saving at vblank from the timer thread.** That thread is not a guest
  thread and cannot hold the guest CPU without deadlocking a guest thread
  that spins on its DPC (`kernel_guest_cpu.c` header).

### D3. What is serialized and what is rebuilt

The table is a summary. Phase 0 delivers the full inventory (task 0.7):
every file-scope and TLS static in each subsystem file, classed as
serialized, rebuilt or irrelevant. The review counted about 450 in
`nv2a_pb_exec.c`, `xbox_memory_layout.c` (96), `kernel_bridge.c`,
`kernel_hal.c` and the backends. Phase 2 is gated on that inventory, not
on this table.

| Chunk | Serialized | Rebuilt on load |
|---|---|---|
| `MEM ` | RAM and contiguous window, 4 KB pages, zero pages elided, the XBE's untouched image pages elided (reloaded from the XBE) | |
| `APER` | NV2A aperture (PUT, GET, PRAMIN, RAMHT), MCPX plain pages, flash; the ack thread's mirrors in `xbox_memory_layout.c` (fence, counter, frame counter, kick state) | MMIO traps |
| `ALOC` | heap blocks, bump pointer, contiguous arena, VMA page table | |
| `THRD` | per thread: guest id, priority, affinity, TIB and stack VA, the TLS register file of D2 step 4, shadow chain, park record, suspend count, APC ring, guest-CPU queue position | host threads, TLS (each thread writes its own), CPU lock tickets |
| `KOBJ` | per guest token: type, creation parameters and flags, guest VA, signal state, count, owner guest thread, recursion; mutants, semaphores, events, timers (remaining time and period) and critical-section shadows; the DPC queue | host events, mutexes, semaphores, timers and `CRITICAL_SECTION`s, re-acquired by their owners |
| `HAL ` | IRQ posts (`g_xbox_irq_pending`), connected interrupts (`KeConnectInterrupt`), vblank callbacks, the AV display mode (`g_av_display_mode`) | the dispatch gate (no holder at a save), interrupt connections, swap chain |
| `FILE` | per handle: guest path, access, share, open flags, position, FATX pending flags, directory-enumeration cursor | host fds, reopened with `OPEN_EXISTING` |
| `CLCK` | guest tick, QPC, interrupt and system time, rdtsc, vblank and flip counts | host bases (see below) |
| `PGRA` | `s_gpu`, `s_vsh`, texture registers, `s_present`, `s_scanout`, flip hold, walker carry-over, context-DMA binds, zpass state | texture, RT, shader, PSO, combiner caches (a `scale_drop()`-style flush plus a dirty mark) |
| `SURF` | every surface whose guest pages are not current: colour targets that live only on the host, and depth and stencil, keyed by guest offset, format, size | GPU textures, uploaded from the chunk |
| `APU ` | register files, voice state minus host pointers, DSP X, Y, P, mixbuffer and peripherals, DSP core registers, the virtual clock | resamplers (re-created and primed), JIT translations, worker threads, host audio queue (refilled with silence) |
| `USB ` | OHCI registers and counters, per-pad control-transfer state, addresses and configurations, XInput packet numbers | host pads |
| `SAVE` | the title's own save files: every file under `UDATA/<title_id>/` and `TDATA/<title_id>/` with its relative path, size, attributes and times | the host directories, replaced on load |

- **`KOBJ` bookkeeping.** `s_handle_table[16384]` stores only `HANDLE`s,
  with no type or creation parameters. Host semaphores have no portable
  count query, and an auto-reset host event cannot be read without
  consuming it. So every create, release and wait bridge keeps the guest
  view itself: type, count, owner, recursion and flags. The chunk is
  written from that view, never from the host objects.
- **Files.** Reopening must not re-apply the create disposition:
  `CREATE_ALWAYS` would truncate a save file that was open for writing.
  The open flags are recorded, and the reopen uses `OPEN_EXISTING` and the
  saved position.
- **Thread IDs in guest memory.** Guest thread objects and TIBs may hold
  host-derived thread IDs or handles. Handles go through the token map;
  phase 0 checks the thread IDs.

**The title's saves (`SAVE`).** The chunk is written at the save point,
after the quiesce, so no guest write is half done. Open handles on those
files are in `FILE` with their positions and reopen after `SAVE` is
restored. On load the two directories are written to a staging directory
beside them and swapped in with renames, so a failed load leaves the old
saves in place. The undo state taken before an in-session load (D5) holds
the saves that were on disk, so undo restores both as well.

- **Size.** The measured stage-1 run had 10.3 KB (`TitleMeta.xbx` and
  `TitleImage.xbx`, no game save yet). Titles size their saves for the
  8 MB memory unit, so `UDATA` is usually under 1 MB. `TDATA` can be a
  larger cache; phase 0 measures both games. A save warns, and a player
  slot refuses, above 16 MB of `SAVE` (`RECOMP_STATE_SAVE_MAX`). It is
  compressed with the rest in player slots, so its cost is small next to
  `MEM`.
- **Privacy.** A slot, an exported slot and a fixture state hold the
  title's code and data, the user's save data and a thumbnail, and RAM
  can hold profile names. They are as private as the saves themselves:
  never committed, never published, never attached to the tracker, never
  in `bench-logs` exports, and never uploaded by any tool. An export
  writes only to a path the player picks. The public export and audit
  scripts refuse `*.xbrstate` and `*.xbrslot`.

No game-specific chunk exists. A title whose manual overrides kept host
state across a park would need one, and that would be per-game code
(D8). Phase 0's inventory covers cat's overrides.

**Clocks.** Phase 1 puts every guest-visible clock behind one base:
`guest = host − base + saved`. The readers are QPC, the tick count,
interrupt time, system time, `rdtsc`, the vblank grid and timer due times.
A load sets the base, so the guest sees its clocks continue from the
moment of the save, not jump by the wall time between save and load. The
tick write in `nv2a_ack_thread` goes through the same base. System time
(the dashboard clock) may optionally follow the host instead.

*Rejected:*

- **Saving host cache contents** (textures, shaders). They rebuild from
  guest RAM by hash. Dolphin saves them only as an option.
- **Saving the open-batch buffers.** They are empty after the drain.
- **Reading kernel-object state from the host objects.** It is not
  portable and some of it cannot be read without changing it.

### D4. Format and versioning

```
header:  "XBRSTATE" u16 major u16 minor
         title_id, xbe sha256, gen key (the generated-code key), exe build id,
         toolkit sha, game sha, backend, render scale, flip, wall time,
         thumbnail (PNG, 160x120)
chunks:  tag[4] u16 version u16 flags u32 crc32 u64 raw_size u64 stored_size data
         ... "END " sentinel
```

- **Every chunk is encoded field by field.** Each chunk has explicit
  writer and reader functions that put fixed-width little-endian fields in
  a set order; no chunk is a raw host struct. `PGRA` and `APU` included:
  the Mac build (LP64 clang) and the Windows build (LLP64 mingw) lay their
  structs out differently, and the apu-dsp work is still reshaping
  `MCPXAPUState`. A new field is a new chunk version, and the reader of
  the old version fills it with its stock value. This is what lets a
  fixture made on the Mac load on the Deck (D6).
- **Guest-level chunks do not depend on the build.** `MEM`, `APER`,
  `CLCK`, `USB`, `SAVE` and the guest parts of `THRD` and `KOBJ` use guest
  VAs and guest tokens. A rebuild of the toolkit or of the game keeps them
  valid. This is the difference from N64Recomp's dead end, where state
  named host addresses.
- **Versions.** Each chunk carries its own version (RPCS3, PCSX2). A
  reader:
  - loads a chunk version it knows;
  - migrates an older one when a migration is written;
  - refuses otherwise, naming the chunk.
  A chunk for a subsystem the title never started is not written (RPCS3),
  so changes there do not break states.
- **Load-time checks:**
  - The XBE sha must match.
  - A different gen key is allowed only when every saved frame's
    `fn`/`site`/`kind` is still a resume site in the new build, and the
    build has `XBOXRECOMP_STATES` on.
  - The `backend` field is honoured: the loader knows where the colour
    was saved (below).
  - The exe check is informational.
- **Compression.** Stored chunks are zero-page sparse. Phase 4 adds one
  vendored fast codec (LZ4, BSD-2, a single file) for player slots.
  Fixtures stay raw, so phase 2 adds no dependency. Measured on stage 1:
  50.7 MB sparse for RAM, and zlib level 1 reaches 24.6 MB, so LZ4 should
  land near 30 MB.
- **Size target:** under 100 MB raw and under 40 MB compressed:
  - RAM, about 50 MB in a stage;
  - the contiguous window, up to 64 MB, measured in phase 0;
  - surfaces, about 5-10 MB at stock resolution;
  - the APU, about 1 MB;
  - the title's saves (`SAVE`), usually under 1 MB, capped at 16 MB.
- **Speed targets:**
  - save pause under 2 frames;
  - file ready within 1 s;
  - load to the first frame within 2 s, plus cache warm-up.

**Cross-backend loading.** A state made on one backend loads on the other.
The rule is that after the readback (D2 step 5) every surface is either
current in guest memory (`MEM`) or stored in `SURF`, whatever the backend.
The loader uploads every `SURF` entry to its own backend and lets the
caches pick up the rest from guest memory by hash.

- **Metal colour.** Lazy write-back leaves the present surface's pages
  `PROT_NONE` after each flip (`nv2a_pb_metal.m`), so a plain `MEM` copy
  would fault or copy stale bytes. The save syncs every host-only render
  target (`sync_guest` is per surface, not only the present one), restores
  the page protection, and skips guarded VMA pages on purpose.
- **Metal depth.** Depth and stencil are `Depth32Float_Stencil8` in
  private storage. The save blits them to a shared buffer, with the
  depth-from-depth-stencil and stencil-from-depth-stencil options, and the
  load uploads through the mirror path.
- **D3D11 colour and depth.** Colour targets never write back
  (`writes_back = 0`), so they go to `SURF` through staging copies (the
  `dump_back_buffer` code). Depth is D32S8X24. `UpdateSubresource` cannot
  write a depth-stencil resource, so the load uploads by `CopyResource`
  from a staging or initial-data texture. This is checked on DXVK (the
  Deck, and dxvk-native for the planned Linux build).
- **Render scale.** `SURF` stores targets at guest resolution. A load at a
  scale above 1 upsamples them, which is lossy: off-screen targets are not
  re-rendered, and depth edges will not match the colour for a few
  frames. That is acceptable for players. Fixtures and goldens run at
  scale 1.
- **CPU backend.** It must keep building. `SURF` is a no-op there (its
  surfaces are guest memory already); a gap is recorded in TASKS.md, not
  closed.

### D5. Loading

- **At start** (phase 2): `RECOMP_STATE_LOAD=<file>`.
  1. Host init runs as today: memory layout, APU, kernel, paths, bridge,
     backends, window.
  2. The XBE is mapped. `xbe_entry_point` is not called.
  3. The restore runs in this order:
     1. memory and apertures;
     2. the allocator;
     3. clocks;
     4. the host init the title would have triggered lazily, replayed from
        saved facts: the AV display mode and swap chain, interrupt
        connections and vblank callbacks, the APU threads, the OHCI start;
     5. kernel objects, re-creating host objects and re-linking by token;
     6. the title's saves (`SAVE`), swapped in, then files reopened;
     7. PGRAPH, with the host caches flushed and the surfaces uploaded;
     8. APU and USB.
  4. One host thread per guest thread is created in the saved order. Each
     writes its own TLS register file from `THRD`, re-acquires the mutants
     and critical sections it owned, and waits at a barrier.
  5. When every thread is at the barrier, the guest CPU is handed out in
     the saved queue order. Each thread runs `recomp_resume(chain)`, which
     calls the outermost function in resume mode.
- **In session** (phase 3): the load is requested and quiesced as in D2.
  1. Every parked guest thread unwinds to its trampoline
     (`bridge_thread_main` or the boot-thread entry) with a `longjmp` set
     there. Lifted frames own no host resources, but the reused host
     threads still hold host mutexes and critical sections the `longjmp`
     abandons.
  2. So every host sync object, critical-section shadows included, is
     destroyed and re-created, not just "the bridge locks" checked.
  3. Threads that are not in the state exit. The rest are reused or
     created.
  4. The restore continues as at start.

  An undo state is taken first. A failed load rolls back to it (Dolphin).
- **Order.** Video comes before threads, as in Dolphin: caches are flushed
  before any thread can submit a frame.

### D6. Test fixtures, stored safely

- **Recipe.** It sits in the game's `config/states.json`: name, the
  pad-script prefix (`@stage1`, or a script in `scripts/shots/pad/`), a
  `savestate NAME` step or a flip number, and the environment. It is text
  that holds no game data, like the scripts already committed. A flip
  number becomes `RECOMP_STATE_SAVE=<file>@flip N`, which needs no game
  code; the `savestate` step needs the glue named in D8.
- **State.** States live in one shared store beside `bench-logs/` and
  `runs/`, `xbox-recomp/states/<slug>/<name>/<key>.xbrstate`, with a
  `meta.json` beside each (recipe hash, shas, flip, size). Not in a
  worktree's `analysis/`: that is per-worktree scratch, so every feature
  worktree would rebuild every state and `worktree remove` would delete
  them. The CLI resolves the store the way it resolves golden frames, and
  `notes/cleanup-derived.py` learns it. Nothing in the store is committed
  or exported.
- **Key.** The key is the XBE sha, the chunk-version vector and a hash of
  the resume sites the state's chains use, all of which the build must
  cover. It is not the build ID or the toolkit sha: with those, every
  merge would re-make every state from its recipe and the fixtures would
  save nothing. A state is stale only when its key no longer matches.
- **The title's saves** are in the state's `SAVE` chunk, the same
  mechanism as a player slot, so there is no separate `save/` copy. A
  fixture run points `RECOMP_SAVE_DIR` at an empty scratch directory under
  the run, and the load fills it from `SAVE`, so a fixture never reads or
  writes the user's real saves.
- **Commands.**
  - `blinx2 state make <name>` runs the recipe under the Mac locks and
    writes the state.
  - `state list` and `state check` (load, render N flips, compare to the
    fixture's golden frames) cover the rest.
  - `golden run --from-state <name>` and `bench run --from-state <name>`
    make a stale state again first, then start from it.
- **Goldens.** A state made before a fix carries the bug's guest-side
  results forward: a stage loaded with the tracker item's dark water, or a pool
  already corrupted. From-state goldens therefore cannot validate a change
  that acts before the save point. The full-prefix goldens stay the merge
  gate. The from-state twins are fast checks, and a change that touches
  boot or load code runs `state make` again before they count.
- **Hosts.** The encoding is portable (D4), so states made on the Mac load
  on the Deck, the Linux/Proton host and Windows; those hosts never pay the boot prefix
  to make them. States move by `rsync` to the hosts' bench scratch, as
  recordings do in `playthrough-replay`. They follow the CLAUDE.md rule
  for test frames: only the user's Mac and test hosts, never public,
  never on the tracker.
- **Generic CLI.** The CLI parts (`xbr state`) know no address. Tests use
  synthetic containers.

*Rejected:* **fixtures made per host and backend.** The Deck would run
`state make` and pay the boot prefix once per build, and Metal and D3D11
states would diverge.

### D7. Verification

1. **Round trip.** Load a state, quiesce at once, save again: every
   guest-level chunk is byte-equal. `CLCK` is equal within one tick.
2. **Continuation.**
   - On the deterministic scenes (attract on Metal, the stage-1 walk):
     state at flip N, load, compare the next frames to the uninterrupted
     run's frames with the golden tolerance. This runs on Metal, on D3D11
     under Proton, and on native Windows by phase 4 at the latest (the
     linux-native decision makes Windows a required gate; the boot switch
     needs the user's OK).
   - Cross-backend: a Metal-made state loads on D3D11 and passes the same
     check, and the reverse.
   - On the other scenes, the fixture's golden frames from the state must
     pass.
3. **Soak.** 50 quick save and load cycles in one session under a script,
   with no crash, no leak of host objects (handle and texture counts),
   and no audio starve after the refill.
4. **Stock unchanged, and the default-ON gate.** With no state key set,
   no save or load happens. Phase 1, which lands the lifter change,
   measures `XBOXRECOMP_STATES` ON against OFF on Metal (the Mac) and on
   D3D11 (the Deck under Proton), at stock settings, over the golden
   scenarios:
   - frame CPU time, median and p99, and the guest CPU's held time per
     frame (the `[PACING]` guest-cpu line), with uncapped pacing where
     possible. Flips/s is paced (the vblank pacer, the flip hold, present
     pacing), so a CPU cost does not show there until a scene is
     CPU-bound;
   - `.text` growth (for reference, the back-edge flag alone cost
     +1.6-1.9 %).

   **Threshold.** The option defaults ON only if frame CPU time rises by
   3 % or less (median and p99) on both backends and the goldens are
   frame-identical between ON and OFF. Otherwise it ships OFF and the
   numbers go back to the user. The CLAUDE.md flag (a 25 % drop in
   flips/s or a 1.5× rise in frame ms) still applies to every change as
   the hard stop; the 3 % threshold is the tighter bar for default ON, so
   the two figures do not conflict.

### D8. Generic toolkit, per-game data

All code is in the toolkit and the CLI. Per-game inputs are data only,
in each game's repo.

- **Toolkit:** the lifter's shadow stack, resume entries and restartable
  wrappers; the container and every chunk, `SAVE` included; quiesce,
  restore, the clock base and the cross-backend surface paths; the slot
  store (D9), the hotkeys and the
  `xbox_StateRequest(path)` API that every save trigger calls.
- **CLI:** `xbr state make|list|check`, `--from-state`, and in phase 5
  `xbr state slot export|import`.
- **Game data:**
  - `config/resume_sites.json`: the resume sites and the `restartable`
    list of manual overrides (cat: `0x002E0DB0`);
  - the fixture recipes (`config/states.json`).

**Per-game code, stated explicitly.** One piece exists. cat's pad-script
engine (`src/pad_input.c`) is game code, so the `savestate NAME` step is a
few lines there that call `xbox_StateRequest`. It is optional: a recipe
that names a flip instead uses `RECOMP_STATE_SAVE=<file>@flip N` and needs
no game code. It goes away if the pad-script engine moves into the
toolkit, which is a separate change. A game-specific chunk would be a
second piece. None is planned (D3), and phase 0 confirms that.

Burnout 3 is the second consumer in phase 2, before anything goes
upstream. It is the check that nothing BLiNX-specific slipped into the
toolkit.

### D9. Player slots: N in the model, one in phase 4

A slot is one self-contained file: the D4 container with the `SAVE`
chunk, the thumbnail, a label and the creation time in its header. So a
slot needs nothing beside it, and an export is a copy of that file. A
`.xbrslot` is the same container as a fixture's `.xbrstate`; the
extension only marks a player slot.

**Storage.** Under the save root, beside `UDATA` but outside it, so the
title never sees it:

```
<save root>/states/<title_id>/
  slots.json          {"version": 1, "order": ["7f3a...", "c210..."]}
  <slot id>.xbrslot   one per slot; the id is random and never reused,
                      except phase 4's one slot, `quick`
  undo.xbrslot        the state before the last load (not a slot)
```

- **Order.** `slots.json` holds only the order. Rearranging rewrites it,
  and no slot file is renamed. A missing or corrupt `slots.json` is
  rebuilt from the files, by creation time.
- **Delete** removes the file and its entry. **Move** is a reorder, or an
  export followed by a delete.
- **Export** copies one slot file to a path the player picks.
  **Import** checks the header (the XBE sha, chunk versions, resume
  sites, as for any load), gives the slot a new id and appends it. A slot
  from another XBE is refused at import, not at load.
- Every write goes to a temporary file and is renamed into place, so a
  crash never leaves a half slot.

**Phase 4** ships one slot (`quick`), a save hotkey and a load hotkey,
behind `XBOXRECOMP_ENHANCE` and off by default. The keys and the slot
settings live in the enhancements TOML, in a `[states]` table, per the
enhancements decision (keyboard F5 and F9 by default, plus an optional
pad chord). The user confirmed the keys on 2026-10-22 ("Save states keep
F5/F9"). The mouse release moves from F9 to F8, and the free-camera
reset from F5 to Home, active only in free-cam. The free-camera freeze
moves from F8 to End (orchestrator, 2026-10-22, follows from the user's
F8 choice; the user may override). Task 4.0 does the rebind. It uses the same store, with an order of length one, so phase 5
adds no migration.

**Phase 5, the slot manager,** is blocked on the mod overlay menu and
plugs into it: the list with thumbnails, rearrange, delete, export and
import. The `xbr state slot export|import` verbs come with it. They do
not need the overlay and can be pulled earlier if asked.

*Rejected:*

- **A slot directory with loose save files.** It is harder to export as
  one file and easier to half-copy. The `SAVE` chunk keeps a slot whole.
- **Numbered slot files** (`slot1`, `slot2`). Rearranging would rename
  files, and a crash mid-rename could lose one.

## Phases

| Phase | Content | Gate |
|---|---|---|
| 0. Facts | Dump the contiguous window and the APU pages in stage 1 and attract. Log parked chains for 5 minutes of `@stage1-enemies` and the story scene, in both games, and count parks by kind (call, tail, back edge, spin, host sleep) and held critical sections and mutants at the flip. Audit the C locals live across sites. The per-file static inventory. Decide the Burnout 3 safe point (D2 option a or b). | the inventory, the site list's first draft, the B3 decision, then **go/no-go** |
| 1. Lifter and clocks | Shadow stack (all four kinds, `esp`, callee, depth checks), resume entries for listed sites, restartable wrappers, the guest-clock base, `XBOXRECOMP_STATES` in the gen key | goldens unchanged; the D7.4 default-ON gate |
| 2. Fixtures | Portable container, all chunks with `SAVE`, `KOBJ` bookkeeping, cooperative wait abort, D2 quiesce, start-time load with re-acquire, `xbox_StateRequest`, the `savestate` step, the shared store, `xbr state`, `--from-state`; BLiNX 2 stage-1 and attract fixtures, then one Burnout 3 race | D7.1, D7.2 on Metal and D3D11 (Proton), cross-backend |
| 3. In-session load | `longjmp` unwind, every sync object re-created, undo state with saves, the soak | D7.3 |
| 4. Quick save | One slot in the D9 store, a save hotkey and a load hotkey behind `XBOXRECOMP_ENHANCE`, LZ4, thumbnail, the wizard notes | a manual pass on the Mac, Deck and native Windows |
| 5. Slot manager | N slots in the mod overlay menu: list, rearrange, delete, export, import; `xbr state slot export` and `import`. Blocked on the overlay | a manual pass, import refusals tested |

**Go/no-go after phase 0.** The phase 0 probe simulates a save at every
flip of the sampled scenes and counts how often it would be refused, and
why. Go when a save succeeds within `RECOMP_STATE_RETRY` flips in at least
95 % of attempts in both games. No-go, or a redesign brought to the user,
when back-edge parks without a liveness proof, or critical sections and
mutants held at the flip, are common enough that saves are mostly
refused.

## Risks

- **Burnout 3's guest CPU lock.** Option (a) of D2 is its own behaviour
  change for Burnout 3, and it may cost speed or break a golden there. If
  it does, option (b) adds a second quiesce path.
- **Hidden live C locals across sites.** If the lifter keeps a flag or a
  temporary in a C local across a call or a back edge, a resume there is
  wrong without any error. Phase 0's audit and the lifter assertion close
  this. The round trip cannot catch it, but continuation can.
- **Refusals more common than measured.** The spike saw few, shallow
  parks, but 19,970 back-edge preempt points and the 4 ms quantum mean
  many workers are queued at a back edge at the flip. The go/no-go
  measures it.
- **Restartable calls that are not.** A wait whose satisfaction had a
  side effect (an auto-reset event consumed, a semaphore decremented)
  must be recorded as returned. The cooperative abort (D1) makes the
  thread decide this itself; a bridge that skips the save handle gives a
  lost or double wake. Each wait bridge gets a ctest.
- **Ownership.** A host mutex or critical section owned by the wrong host
  thread after a load deadlocks or corrupts. The barrier and the phase 3
  re-creation of every sync object close this; the soak checks it.
- **Guest `setjmp` and SEH.** Guest `setjmp` uses a native `jmp_buf`, and
  `g_seh_ebp` is the SEH bridge. A frame whose `jmp_buf` is live across a
  park holds host stack addresses. Such a save is refused until it is
  understood (phase 0 counts them).
- **Inline main thread.** The frames below the thread routine are not
  restored, so a title that returns from its main routine behaves
  differently after a load. No known title does. It is logged.
- **Non-determinism.** Exact continuation cannot be asserted for most
  scenes. D7.2 limits it to the scenes known to repeat and uses golden
  tolerance elsewhere.
- **Stale guest-side results in fixtures.** A state made before a fix
  carries the bug forward. Full-prefix goldens stay the merge gate (D6).
- **Readback.** D3D11 readback cost at render scale 3, and MSAA if it is
  ever added; the Metal `PROT_NONE` pages and private depth; the D3D11
  depth upload on DXVK (D4).
- **Audio.** Resamplers and filter state are re-created, which can click
  at a load. The host queue starts empty, so the first frames are silent
  or a short fade. That is acceptable for players, and fixtures run with
  dummy audio.
- **Game saves versus the state.** The title caches save metadata in RAM,
  so a state and the files on disk must agree. The `SAVE` chunk keeps
  them together, which avoids xemu's trap (a state and an HDD image that
  disagree). The cost is that loading an older slot also rolls the
  title's saves back, losing progress saved after it. The load says so,
  and the undo slot holds what was on disk.
- **Default ON.** The instrumentation is compiled into every build while
  it passes the D7.4 gate. A later lifter change could push it over; the
  gate is re-run when the lifter's call or back-edge emission changes.
- **Upstream fit.** The shadow stack touches every call site in the
  lifter's output. It stays behind `XBOXRECOMP_STATES`, its cost
  published, so upstream can take it later or not.
- **Scope creep from the device models.** RPCS3 is still fixing timer and
  file serialization in 2026. Each chunk gets a round-trip ctest of its
  own in the toolkit.

## Effort

Re-estimated after the review of 2c87ab5:

| Phase | Agent days | Why |
|---|---|---|
| 0 | 2-3 | the static inventory, park counts by kind, the B3 decision |
| 1 | 6-9 | tail and back-edge resume, `esp`, setjmp resync, the TLS layout measured on the Mac, regenerating cat and B3, the default-ON gate |
| 2 | 17-25 | `KOBJ` bookkeeping in every sync bridge, re-acquire of critical sections and mutants, the cooperative wait abort, the portable encoding, the Metal and D3D11 depth paths, Proton debugging, `SAVE` (about 1 day) |
| 3 | 5-8 | host-object teardown with ownership |
| 4 | 3-5 | |
| 5 (after the overlay) | 2-3 | |
| Burnout 3 across phases 0-2 | 5-8 | option (a), turning the guest lock on, is its own change |

The total is about 40-61 agent days. Fixtures (phases 0-2 plus Burnout
3) are about 30-45, and they pay back on goldens and benches first. The
go/no-go after phase 0 bounds the loss at 2-3 days if the refusal rate is
too high.

## Open questions

- Whether a full site set (all ~90,000 calls plus the back edges) is
  cheap enough to drop the observed list. Phase 1 answers it.
- Whether Windows FMV (Media Foundation) is ever on screen at a save
  point. If it is, the save is refused there.

Settled: `XBOXRECOMP_STATES` defaults ON subject to the D7.4 gate (the
user, 2026-10-22). A slot carries the title's saves (the user,
2026-10-22).
