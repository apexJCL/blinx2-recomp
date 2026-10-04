## Context

BLiNX 2 links XDK 5849: XAPILIB, D3D8, D3DX8, XGRAPHC, DSOUND and LIBCMT/LIBCPMT. Since `recomp-coverage`, the 12 library code sections are disassembled and translated: 25,258 functions in all, 4,098 of them in library sections. Translated library code runs against the toolkit kernel bridge. Only the hardware is missing: the NV2A, the APU and interrupts.

## Decisions

### Translate the XDK libraries, replace hardware-bound entry points by hand
The alternative would be a VA-keyed HLE table that maps D3D8/DSOUND entry points onto the toolkit's `src/d3d` and `src/audio` layers. The toolkit doesn't have one. It would also need every entry point identified by address, for a non-LTCG D3D8 the toolkit has never seen.

The toolkit's own instructions, and its Burnout 3 example, point the other way: translate, then override the entry points that wait on or poke the hardware. Overrides go in `src/recomp_manual.c` as `void sub_XXXXXXXX(void)` definitions. `--exclude-manual` keeps gen/ from emitting a competing body.

### BlockUntilVerticalBlank as a pacer, not synthesized interrupts
`sub_002E0DB0` does two things: it zeroes the device's vblank KEVENT SignalState (`device + 0x1DC0`), then calls `KeWaitForSingleObject(device + 0x1DBC, UserRequest, UserMode, FALSE, NULL)`. On hardware the GPU ISR at `0x002EA2E0` (vector 3, context `0x002F3BE8`) sets that event, from a DPC.

The toolkit can synthesize vblank (`RECOMP_VBLANK=1`, kernel_bridge.c), but that path doesn't work here:
- The ISR reads hardware ports (`in al, dx` at `0x002EA35C` is untranslated).
- The event was never registered with the bridge, so the DPC's KeSetEvent would hit the same lookup miss.

The override instead sleeps until the next 60 Hz boundary on a host monotonic clock (QueryPerformanceCounter on Windows, CLOCK_MONOTONIC elsewhere), leaves SignalState as the original does, and returns STATUS_SUCCESS. The two callers are the `.text` thunk `sub_002A1870` and the AvSetDisplayMode step loop in `sub_002E6660`.

### Lazy KEVENT shadowing in the bridge
This was deferred at first; it is now needed. D3D builds the vblank event its DPC signals (`0x002F3D7C`, .bss) inline, never through KeInitializeEvent. The bridge fell back to `XBOX_TO_NATIVE` and gave host `SetEvent` a guest pointer, which crashes on POSIX (hle-10).

Toolkit `0e948f5` gives KeSetEvent, KeSetEventBoostPriority, KePulseEvent, KeResetEvent and KeWaitForSingleObject a shadow on first use. The shadow's type (Type 0/1) and initial state (SignalState) come from the guest DISPATCHER_HEADER. Anything that isn't an event keeps the old fallback.

### The vblank interrupt is needed after all (RECOMP_VBLANK on by default)
The pacer is enough for the BlockUntilVerticalBlank callers, but not for the main loop. That loop (`sub_0005F960`, spinning at `0x00060475`) waits for the frame counter at `0xAE7388` to move. Only the title's vblank callback `sub_000604A0` moves it. The title registers that callback through D3DDevice_SetVerticalBlankCallback (`sub_002E0D90`, which stores it at device+0x1DB8), and D3D's vblank DPC calls it.

So `main.c` turns on the toolkit's 60 Hz vector-3 delivery: `RECOMP_VBLANK=1` unless the environment already sets it. The ISR claims the interrupt. Its `in al, dx` reads are no-ops, and the claim doesn't depend on them. With the lazy KEVENT shadow above, the DPC runs cleanly. The pacer stays: it still serves the BlockUntilVerticalBlank callers without waiting on the event.

### D3D GPU fence mirrored
`sub_002E8110` waits for the GPU-written fence word `*[device+0x30]` (contiguous memory, `0x80000000`) to reach the submitted fence at `[device+0x2C]`. Nothing executes the pushbuffer, so the word stayed `0xDEADBEEF` and the main thread hung there after the archive load (hle-8). `main.c` registers `xbox_Nv2aMirrorFence(0x2F1FB8, 0x2C, 0x30)`, the same acknowledgement the toolkit gives Wreckless.

### SuspendThread on POSIX
The shim can't suspend another thread. It now blocks a thread that suspends itself, on its CREATE_SUSPENDED gate, until ResumeThread. That covers the idle-worker pattern BLiNX 2 uses (XAPI SuspendThread at `0x00297F3D`). Without it, worker 4 spun on about 15 million NtSuspendThread calls a second.

### Devkit RAM: a deliberate deviation from retail
`main.c` calls `xbox_SetTotalRam(XBOX_DEVKIT_RAM)` (128 MB). The loader maps all 73 XBE sections at boot, including the 49 non-preload sections that XeLoadSection pages in and out on hardware. That paging isn't modeled. At 64 MB this left a ~14 MB heap and a 1 MB stack, and the game had used 13.7 MB of the heap by its first archive loads.

At 128 MB the RAM mirrors must stay below the contiguous window at `0x80000000`. The toolkit's shared mirror loop skips any mirror that overlaps it (`819c96e`, owned by proton/win-layout).

## Risks / Trade-offs

- **Memory-dependent bugs may be masked or introduced by devkit RAM.** If anything later behaves as though it depends on memory (allocation patterns, address wrap, a heap-top check), first retry at 64 MB, then consider modeling XeLoadSection.
- **Worker stacks overlap the boot stack.** `XBOX_WORKER_STACK_BASE == XBOX_STACK_BASE`, so the OHCI worker slices (`src/usb/ohci.c:735`) overlap the boot thread's stack. This is noted, not fixed. Fix it if it bites.
- **Vblank comes from a 10 ms timer tick**, at about 60 Hz with jitter, and is independent of the pacer's clock. The two aren't phase-locked.
- **Fixed 60 Hz** regardless of the display mode AvSetDisplayMode was given.
- **Disasm coverage.**
  - Of the 484 `tail_jump_alias` entries that disappeared with `recomp-coverage`, 483 are no longer referenced by any generated code. They sat inside functions whose boundaries changed, so their jumps became local. One, `0x00353334` (SRCADV), is now an unresolved stub, reached by a conditional tail jump from `recomp_0098.c`.
  - The broader risk is the 998 "not detected" stubs (`recomp_stubs_unresolved.c`): 800 are in `.text`, and 189 in library sections (D3DX 61, XGRPH 59, SRCADV 42, D3D 9, SRCED 7, DSOUND 4, PSFD_I 4, SRCAC 1). Each returns without running the code it stands for, and leaks the caller's frame on tail jumps (tools/disasm/functions.py, `_build_alias_entries`). Candidate upstream draft 08: disasm should make every jump target that lands outside a detected function an alias entry, not leave it to recomp to stub.
