# Change: Save states (quick save and load of the full game state)

The user asked on 2026-10-22 for save
states: one quick save that restores the full game state. Players get quick
save and quick load. Tests get fixtures for well-known scenarios, so a golden
or a benchmark can start inside a scene instead of replaying the boot and the
menus to reach it.

## Why

- **Nothing can resume a running game today.** The only ways into a scene
  are:
  - the title's own save, which restores progress, not a moment;
  - a pad script that replays the boot and the menus (`@stage1` reaches the
    stage-1 walk after about 26 s and 779 flips on Metal).
  Every golden and every benchmark pays that prefix on every run and on
  every host.
- **Emulator save states do not carry over.** xemu, Dolphin, PCSX2 and
  RPCS3 save a guest CPU that stops between two instructions. Lifted code
  runs on host threads with host stacks: a guest call is a host call
  (`RECOMP_ABI_CALL`), `ebp` is a host local in each function, and a parked
  thread's continuation exists only in host frames. N64Recomp tried save
  states and dropped them for that reason (Zelda64Recomp #418: host
  addresses differ per run and per build). A host-stack or process snapshot
  (CRIU, `fork`) does not survive a restart, a rebuild or a GPU.
- **The toolkit already has most of a safe point, when the guest CPU lock
  is on.** The lock (`kernel_guest_cpu.c`, `RECOMP_GUEST_LOCK`) lets one
  guest thread run guest code at a time. cat forces it on; the toolkit
  default is off and Burnout 3 does not set it, so phase 0 decides how
  Burnout 3 gets a safe point (D2). The
  others are parked in a kernel call, at a lowered spin wait or at a loop
  back edge. A 2026-10-22 thread dump in stage 1 found every guest thread
  3 to 8 guest frames deep, parked in a vblank sleep, a spin wait or
  `NtSuspendThread`. Guest-visible state is mostly guest memory: the 128 MB
  RAM map, the 64 MB contiguous window, the NV2A aperture with PUT and GET,
  and the MCPX aperture that holds the DSP memories. The decoded PGRAPH state is two plain-data structs.
  Host caches already rebuild from guest RAM by hash (`scale_drop()`).

## What changes

- **Guest-level re-entry (D1).** The saver captures each guest thread as a
  guest call chain, never as a host stack. Each entry holds the function,
  the site (a return VA, a tail-jump VA or a loop label), the resolved
  callee, the frame's `ebp` and `esp`, and its kind (call, tail, back edge,
  spin wait), plus the thread's guest registers and its park record. Waits
  abort cooperatively through a per-thread save handle, so each thread
  decides itself whether its wait is pending or satisfied, and owned
  mutants and critical sections are re-acquired by their owners on load. The lifter records the chain in a
  small per-thread shadow stack. On load, the runtime rebuilds the host
  frames from that chain: it calls each function through a **resume entry**
  that jumps to the call site and re-issues the call. The innermost frame
  re-issues the kernel wait it was parked in, as RPCS3 does. Resume entries
  are emitted only for the call sites in `config/resume_sites.json`, an
  "observed" list like `seed_functions.json`. A save that finds a site
  missing from the list is refused with the site named, so the list grows
  in testing. The cost of emitting a resume entry at every site is measured
  in phase 1.
- **Safe point (D2).** The save is requested through
  `xbox_StateRequest` (a key, an env key or an input-script step). The ack
  thread's `on_flip` arms it, and the next kernel call on the thread that
  holds the guest CPU runs it, in this order:
  - freeze guest CPU hand-outs;
  - drain the pushbuffer with the device threads still live (GET equals
    PUT, the flip hold released, no owed report);
  - stop the timer, vblank, OHCI and APU threads at their tick edges;
  - classify the guest threads, each writing its own registers;
  - read the surfaces back on Metal and D3D11;
  - copy.
  If anything is not resumable after two frames, the save is refused with a
  reason: a guest callback nested in a host frame, an I/O call in flight,
  FMV, or a thread inside a DPC or an APC.
- **State (D3).**
  - Serialized:
    - guest RAM and the contiguous window, page-sparse;
    - the NV2A and MCPX apertures;
    - the thread table with the registers, x87, XMM and MMX of each thread,
      its shadow chain and its park record;
    - the kernel object tables (the handle table and the KE shadow, which
      today map guest objects to host events; semaphores, mutants, timers
      with their remaining time, the thread objects, the DPC queue, files
      with their guest path and position, and the heap, contiguous-arena and
      VMA bookkeeping);
    - the plain-data PGRAPH structs, the walker carry-over, the flip hold;
    - the render-target contents on D3D11, and depth and stencil on every
      backend, since those exist only on the host;
    - the APU register files, voice state and DSP cores;
    - the OHCI and pad protocol state;
    - the guest clocks: tick count, performance counter, interrupt time,
      vblank count. Today these read host time directly, so phase 1 routes
      them through one guest-clock base that a load can set.
  - Rebuilt: every host cache (textures, render targets, shaders, PSOs,
    combiner plans, DSP JIT translations, resamplers), the host audio
    queue, and the window and devices.
- **Format (D4).** One `.xbrstate` file:
  - a header: magic, format major and minor, title ID, XBE sha256, the
    exe's build ID and the generated-code key, toolkit and game shas, a
    timestamp, a thumbnail;
  - then tagged chunks, each with its own version, size, compression and
    CRC, and a sentinel between chunks. Every chunk is encoded field by
    field, never as a raw host struct, so a state made on the Mac loads on
    the Deck and Windows, and across backends.
  Guest-level chunks do not depend on the build. A chunk version or
  generated-code key that does not match is refused unless the reader has a
  migration for it.
- **Load (D5).** Phase 2 loads a state at process start
  (`RECOMP_STATE_LOAD=<file>`): host init runs, then the restore runs in
  place of the XBE entry point. Phase 3 adds an in-session quick load: the
  parked threads unwind to their thread trampolines with `longjmp`, and the
  restore runs in the same process.
- **Test fixtures (D6).** Each fixture is a recipe plus a cached state:
  - The recipe is a pad-script prefix that ends in a `savestate NAME` step.
    It lives in `config/states.json` or `scripts/shots/pad/`; no game data
    is in it.
  - The cached state lives in a shared store beside `bench-logs/` and
    `runs/`, never in a worktree and never exported, keyed by the XBE sha,
    the chunk versions and the resume-site coverage, not the build. It carries the title's saves
    in its `SAVE` chunk, like a player slot, and a fixture run loads them
    into a scratch save directory, never the user's.
  - `blinx2 state make <name>` regenerates a stale state from its recipe.
    `golden run --from-state` and `bench run --from-state` start from the
    state.
  States move only between the user's Mac and the test hosts, as frames do.
- **Slots hold the title's saves too (D3, D9).** A slot is one file: the
  state plus the title's own `UDATA` and `TDATA` files in a `SAVE` chunk.
  Loading a slot restores both together, and an export or import carries
  both. The saves are usually under 1 MB (capped at 16 MB). Slots and
  exported slots hold user save data, so they stay private and are never
  published.
- **Player quick save (phase 4).** Behind `XBOXRECOMP_ENHANCE`, off by
  default:
  - one slot, a save hotkey and a load hotkey;
  - a store under the save root, beside `UDATA` but outside it, built for
    N slots (`slots.json` order plus one file per slot);
  - an undo slot before every load (Dolphin's `lastState`), which holds
    the saves that were on disk.
- **Slot manager (phase 5).** N slots, rearrange, delete, export and
  import of one slot to a file. It waits on the mod overlay menu and plugs
  into it.
- **Game-agnostic.** All code is in the toolkit and the CLI. Per-game
  inputs are data only: `config/resume_sites.json` and the fixture
  recipes. The one piece of per-game code is cat's optional `savestate`
  pad-script glue (D8).

## Capabilities

### New Capabilities
- `save-states`: capturing the full guest state at a safe point, the state
  file format and its versioning, loading at start and in session, and the
  test-fixture recipes.

### Modified Capabilities
- `input`: a `savestate NAME` script step (game side, a call into the
  toolkit's `xbox_StateRequest`).

## Impact

- **Toolkit** (`posix-host/portability`; upstreamable, game-agnostic):
  - `tools/recomp/lifter.py`: the shadow-stack push and pop and the resume
    entries, behind the `resume_sites` list;
  - `templates/runtime/recomp_types.h`;
  - a new `src/state/` (the container, chunks, quiesce, restore);
  - save and load hooks in:
    - `kernel_thread.c`, `kernel_sync.c`, `kernel_ob.c`, `kernel_file.c`;
    - `kernel_memory.c`, `xbox_memory_layout.c`, `kernel_guest_cpu.c`;
    - `nv2a_pb_exec.c`, `nv2a_pb_scan.c`;
    - the D3D11 and Metal backends (readback, flush, uploads);
    - `apu_*`, `ohci.c`, `usb_gamepad.c`, `input_core.c`.
  - New env rows, each with a `docs/env.md` row: `RECOMP_STATE_SAVE`,
    `RECOMP_STATE_LOAD`, `RECOMP_STATE_RETRY`, `RECOMP_STATE_SAVE_MAX`
    (CONFIG) and `RECOMP_STATE_TRACE` (TRACE). The hotkeys and slot
    settings live in the enhancements TOML.
  - The `XBOXRECOMP_STATES` CMake option, in the gen key. It defaults ON
    as a recorded exception to the opt-in-OFF rule (the user, 2026-10-22),
    only while it passes the D7.4 performance gate; the OFF build stays
    buildable.
- **Game** (`cat`): data only, `config/resume_sites.json` (sites and the
  `restartable` list) and `config/states.json`; `docs/env.md` rows;
  `.gitignore`. The one code change is
  the optional `savestate` glue in `src/pad_input.c`.
- **Public audits:** the export and audit scripts refuse `*.xbrstate` and
  `*.xbrslot`.
- **CLI** (`xboxrecomp-cli`): `xbr state make|list|check` and the
  `--from-state` flag on `golden run` and `bench run`. Tests use synthetic
  fixtures only.
- **Goldens:** stock behaviour does not change; with the keys unset the
  shadow stack is the only cost. Phase 1 measures frame CPU time (median
  and p99) and `.text` growth, ON against OFF, on Metal and D3D11; the
  option stays default ON only at 3 % or less with frame-identical
  goldens. The CLAUDE.md 25 % flag still applies as the hard stop. Each
  fixture's golden gets a from-state twin as a fast check; the
  full-prefix goldens stay the merge gate. Phase 2's gate is that a state
  saved at frame N and loaded matches the uninterrupted run's frames after
  N on Metal and D3D11, and across backends. Native Windows joins by
  phase 4.
- **Burnout 3:** the second game through phases 1 and 2, before anything
  goes upstream. Its safe point is decided in phase 0: turn its guest CPU
  lock on as its own gated change (recommended), or a lock-independent
  stop-the-world path.
- **Effort:** about 40-61 agent days, with a go/no-go after phase 0.

## Status

Spec from the spike, 2026-10-22, revised after the review of
2c87ab5 and the user's decisions of the same day. Nothing is implemented. The
follow-up items are proposed, not filed.
