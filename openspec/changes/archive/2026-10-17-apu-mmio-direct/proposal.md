## Why

BLiNX 2 drops below 30 fps in gameplay under Proton (5-1 falls to about 20 fps when PAUSE is used, on the Steam Deck; the tracker item: Mission 1-2 slows when the enemies break the wooden barrier). On the Linux/Proton host (D3D11 under GE-Proton11-7, Ryzen 7 3700X, RTX 2060), 5-1 is already below 30 before any time power: 23-28 flips/s, p50 36-45 ms (bench-logs 20261011-215249), with the main thread at about 89% CPU and the GPU idle.

The cost is the APU register traffic, not the renderer:

- **A/B on the same exe, same script (5-1 idle play):**
  - `RECOMP_AC97_READY=0` (no emulated APU): **30.0 flips/s, p50 33.3 ms, max 33.6**, steady for the whole 70 s of play (bench-logs 20261011-221209).
  - Default (APU on): 23-28 flips/s, p50 36-45 ms (20261011-215249).
- **The rate:** `RECOMP_APU_TRACE=1` on 5-1 shows **7,500-8,000 APU register accesses per second** (about 1,450 reads and 6,000-6,500 writes per second; bench-logs 20261011-220809). The movie and title screens make about 460/s (`openspec/changes/audio/spike-results.md` 1.4), and that spike only measured the title.
  - They are almost all DirectSound per-voice updates through the front-end PIO window:
    - `PIO_FREE` reads at 0x20010: 18.5%;
    - `SET_CURRENT_VOICE` 0x202F8: 18.4%;
    - `VOICE_LOCK` 0x202FC: 24.3%;
    - `SET_VOICE_TAR_VOLA/B/C` 0x20360-0x20368: 10.5% each;
    - `SET_VOICE_TAR_PITCH` 0x2037C: 6.2%.
- **The cost per access on Proton:** every access is a trapped page fault that Wine turns into an exception and dispatches to the vectored handler. The audio spike measured the round trip at **51.4 us**, of which 0.72 us is the decoder and model (`RECOMP_APU_FAULT_BENCH`). In 5-1 the handler's own share (decoder plus model, timed inside the handler) rises to 24 us/access; the one place in the model that waits is `VOICE_LOCK`, which takes the APU frame thread's `d->lock`, so that wait is the likely cause.
  - 8,000/s x 51 us is about 410 ms of guest time every second on the dispatch alone, before the lock waits.
  - A ptrace sample of the main thread in 5-1 play (the Linux/Proton host, signals forwarded) found 58% of it in Wine's `segv_handler` and 22% in libc syscall stubs, with about 3,400 SIGSEGVs a second reaching the tracer.
- **The events add voices or retune them.** A barrier breaking starts a burst of effects. PAUSE retunes every playing voice (pitch and volume writes to 0x2037C and 0x20360-0x20368). Each extra access costs about 51 us on Proton, so these events push a near-budget 33 ms frame past a vblank, which gives 3 vblanks or 20 fps. On the Mac, arm64 handles a fault as a native SIGBUS with no Wine exception layer, and 5-1 holds 30.0 flips/s on Metal.

Every one of the hot accesses is a constant address in a plain `mov` in the generated code: DirectSound writes `MEM32(0xFE8202F8u) = eax;`, reads `eax = MEM32(0xFE820010u);`, and so on. `grep` finds 93 such operands in `src/recomp/gen/recomp_0099.c`, all of them `mov` to or from `eax`, and the same shape in Burnout 3 (105 operands). The recompiler knows the address statically, so the fault is avoidable.

## What Changes

- **The lifter emits a direct call for a `mov` whose memory operand is a constant address inside the trapped APU range (0xFE800000-0xFE82FFFF).**
  - A load becomes `eax = XBOX_MMIO_R32(0xFE8xxxxxu);` and a store `XBOX_MMIO_W32(0xFE8xxxxxu, eax);`, with the 8- and 16-bit forms likewise, instead of `MEM32(...)`.
  - Only `mov` (register or immediate source, register destination) qualifies, and only with no base, index or segment register. Every other instruction form (ALU read-modify-write, `cmp`, `test`, `inc`, `xchg`, `lock` forms, `movzx`, `push [mem]`, string ops, x87/SSE/MMX) and every access through a register is emitted as today and still traps, so it stays correct but slow. The design says why `mov` is the whole set.
  - The range is the trapped 0x30000 bytes, not the APU's 512 KB. The GP and EP DSP memories above 0xFE830000 are plain RAM by design (`xbox_memory_layout.c`, `APU_TRAP_BYTES`): the model drops writes there, and Burnout 3 bulk-copies them with `rep movsd`. A `mov` to a constant there stays a `MEM32`. In BLiNX 2 two hex operands sit there (0xFE83FF10, 0xFE85FFFC). As landed, 300 sites change (115 addresses: 47 loads, 253 stores; Burnout 3: 255). The first count of 91 came from a grep for `0xFE8` hex literals, which missed the operands the lifter prints as negative decimals (`MEM32(-25160960)` is 0xFE801300).
- **A runtime entry point: `xbox_MmioRead(va, size)` and `xbox_MmioWrite(va, value, size)`** (toolkit, next to `xbox_VehMmioFault`).
  - When the APU range is trapped and the model is up, they call the same `apu_mmio_rd`/`apu_mmio_wr` path the fault handler uses: the same model calls, size splitting and `RECOMP_APU_TRACE` tallies and timing.
  - Otherwise (`RECOMP_AC97_READY=0`, x86-64 POSIX, before the model is up) they make the plain guest-memory access the generated code makes today, at the same width, so behaviour without audio is unchanged, including the fault and crash report if the window is unmapped and the model is not up.
- **The `XBOX_MMIO_*` macros live in the runtime template `recomp_types.h`** and call those entry points.
- **The BLiNX 2 generated code is regenerated** with `blinx2 analyze` then `blinx2 recomp`, never hand-edited. The only expected diff is at those operands (300 sites as landed).
- **No new opt-in key.** This changes how a trapped access is delivered, not what the model sees: the same calls, in the same order per thread, with the same values. `RECOMP_APU_TRACE` gains a `direct=N` count beside the trapped one, so a run shows how many accesses still fault.

## Capabilities

### Modified Capabilities
- `guest-memory-layout`: constant-address `mov` accesses inside the trapped APU range reach the APU model by a direct call instead of a trapped fault. Other forms still trap.

## Impact

- **Toolkit:**
  - `tools/recomp/lifter.py`: a constant-address check in `_lift_mov`, plus a lifter unit test.
  - `templates/runtime/recomp_types.h`: the macros and the two prototypes.
  - `src/kernel/xbox_memory_layout.{c,h}`: `xbox_MmioRead`/`xbox_MmioWrite`.
  - `src/apu/apu_mmio_hook.c`: a non-fault entry that shares `apu_mmio_rd`/`apu_mmio_wr` and the tallies, on Win32 and POSIX.
  - A new ctest, `tests/mmio_direct`.
  - This changes generated code for every title, so it is upstream-relevant and gated on Burnout 3 under Proton (its DirectSound is the same XDK code: 105 constant `mov` operands, 9 of them above the trap).
- **cat:** regenerated `src/recomp/gen/` (300 sites, 115 addresses), and the `docs/env.md` `RECOMP_APU_TRACE` row (the `direct=` field).
- **Expected effect:** the dispatch cost (about 410 ms/s of main-thread time in 5-1) goes away on Proton. The `AC97_READY=0` ceiling of 30.0 flips/s also removes the `VOICE_LOCK` wait, which this change does not touch, so 30 flips/s is the target and the wait is measured after the change to see what is left. PAUSE and the 1-2 barrier no longer cost about 51 us per voice update. The Mac path skips its SIGBUS round trip too, which is a smaller gain.
- **Follow-up, not in scope:** the `VOICE_LOCK` wait on the APU frame thread's `d->lock`. At 24 us/access and about 250 accesses per frame it is already several ms per 33 ms frame, so task 4.3 records the post-change `handler=` figure and opens the follow-up change (shorten the frame thread's hold of `d->lock`) with that number, unless the figure falls under 1 ms per frame.
