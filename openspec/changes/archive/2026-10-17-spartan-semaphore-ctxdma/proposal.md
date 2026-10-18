## Why

After the tracker item, Spartan: Total Warrior (XDK 5849, `spartan/tca`, toolkit ac27175) boots on the Mac and on the Deck under Proton. It gets one flip (a clear, 0 draws), then spins forever in D3D `sub_00228FA0` during device creation. The path is `sub_0019E740` → `sub_0019D730` → `sub_0022A290` → `sub_0022A250` → `sub_00229890` → `sub_002292B0` → `sub_00228FA0`.

**It is not a pushbuffer-space wait.** It is D3D's fence wait, and the fence word is never written because the executor writes the semaphore release to the wrong address.

- **Where it spins.** `sample` puts every sample at `sub_00228FA0+2428..2436`, which is the back edge of `loc_002290D7`, a loop with no calls in it (`runs/spartan/20261014-212043-extra-sections/run2-sample/sample.txt`; arm64 disassembly of the same binary). The guest loop is:

  ```
  loc_002290CD: edx = [dev+0x30]; esi = [dev+0x2C]; eax = esi - edi
  loc_002290D7: ecx = [edx]; edi' = esi - ecx; if (eax < edi') goto loc_002290D7
  ```

  `dev` is `[0x235528]` = 0x00235530 (the D3D device). `[dev+0x2C]` is the last fence D3D submitted, and `[dev+0x30]` points to the word the GPU writes as it completes work. The loop exits once `submitted - *completed <= submitted - target`, that is, once the completed word reaches `target`. This is the same function, at the same offsets, as BLiNX 2's `sub_002E8110`, the fence wait that `cat/src/main.c` describes for `xbox_Nv2aMirrorFence(0x2F1FB8, 0x2C, 0x30)`.
- **What it polls, and what it waits for.** At the hang, `[dev+0x2C]` = 0x0000000D, `[dev+0x30]` = 0x80002000, and `[0x80002000]` = 0x00000003. The word never moves (`runs/ITEM/r3-peekfields`, `runs/ITEM/r5-base-3d37629`, `RECOMP_TRACE=peek`). The wait needs it to reach a fence between 5 and 0xD.
- **Where the GPU's writes go.** The executor runs every release the title submits (`RECOMP_TRACE=sema`): 5, 7, 9 and 0xB, all with `dma 0x00000008 offset 0x00000000`, all written to **0x80000000** (`runs/ITEM/r4-lldb/stdio.log`). lldb on the hung process shows `[0x80000000]` = 0x0B and `[0x80002000]` = 0x03.
- **Why they go there.** `BACK_END_WRITE_SEMAPHORE_RELEASE` writes at `SET_SEMAPHORE_OFFSET` *inside the context DMA object* that `SET_CONTEXT_DMA_SEMAPHORE` names. `nv2a_pb_exec.c` ignores the object and treats the offset as a physical address. Its comment says so: "The DMA object's own base is not read (no RAMHT/PRAMIN walk yet); for XDK D3D it covers physical memory from 0 ... the first release is logged so a title where that is false says so." Spartan is that title. Instance memory, dumped from the hung process (`runs/ITEM/r4-lldb/pramin-0xFD700000.txt`), shows:
  - `PFIFO_RAMHT` (0xFD002210) = 0x03000000, so RAMHT is at PRAMIN 0 and is 4 KB.
  - RAMHT +0x40 holds handle 0x00000008 with context 0x8000011B: valid, instance 0x11B0. That slot is also where the hardware hash puts handle 8 on channel 0 (design, "Context").
  - PRAMIN 0x11B0 holds `0x0002B03D 0x00000020 0x00002003`: class 0x3D (DMA in memory), target PCI, limit 0x20, frame page 0x2000, adjust 0.

  So the semaphore object is a 33-byte window at physical 0x2000, and offset 0 in it is physical 0x2000, which is 0x80002000 in the contiguous window: D3D's fence word. Spartan's other objects (same dump, RAMHT handles 2..0xC): the surface, texture and vertex objects (handles 3, 4, 5, 6, 9, 0xA, 0xB) are base 0 with limit 0x07FFAFFF, handle 0xC is base 0 with limit 0x10000000, and two more small objects also sit on the fence page: handle 2 (`0x0202B003 0x1F 0x00002023`, base 0x2020, 32 bytes) and handle 7 (`0x0402B03D 0x1F 0x00002043`, base 0x2040, 32 bytes). Those two carry their low address bits in word 0's adjust field, so the adjust is not theoretical for XDK objects.
- **BLiNX 2 and Burnout 3 have the same bug; the fence mirror hides it.** Both register `xbox_Nv2aMirrorFence`, and the mirror copies submitted to completed whenever the executor's releases do not land on the fence word. The bench logs (`bench-logs/*/game-stdio.log`, the `NV2A fence mirror: device ... fence word ...` line) say where each title's fence word is:
  - Burnout 3 (XDK 5849, the same D3D as Spartan): fence word **0x803E6000**, releases at 0x80000000, "NOT the semaphore target; mirror stays on", in all 21 runs that have the line.
  - BLiNX 2: fence word 0x80000000 and "now written by the executor; mirror off" in the 13 runs up to 2026-10-04; fence word **0x80001000**, releases at 0x80000000, "mirror stays on" in all 186 runs since 2026-10-06. D3D's fence page moved from physical 0 to physical 0x1000 (an allocation in front of it changed; which one is not established and does not matter here).

  So the bare-offset rule was right for BLiNX 2 only while its fence page happened to be physical 0, and has been wrong for both gate titles since. Two consequences follow. The executor has been writing every release into physical 0 of a title that does not own that word for its fence, and the fences of both titles have been acknowledged by the mirror at submit time, not by the executor when it consumed the release, which is exactly the race the mirror's own comment in `xbox_memory_layout.c` describes. The Deck/Proton Spartan run stops at the same place, with `NV2A USER PUT = GET = 0x3B44` (pushbuffer drained) and PFIFO all zero (`runs/spartan/20261014-223239-deck-proton/run3-d3d11-watchdog60/`). That fits: the fault is in the executor, which is common to all hosts, not in a host GPU backend.
- **The report object has the same flaw.** `GET_REPORT` writes a 16-byte visibility report at an offset inside the object `SET_CONTEXT_DMA_REPORT` names, and `get_report()` uses the bare offset with the same "covers physical memory from 0" assumption. No title has shown a non-zero report base yet (BLiNX 2's visibility tests work), but it is the same write into guest memory through the same unverified rule, and the fix is the same helper.

**Prototype, verified.** The toolkit prototype (design D1) looks up the object's base and writes the releases to 0x80002000:

```
[GPU] semaphore context DMA 0x00000008: base 0x00002000 (RAMHT +0x40, instance 0x11B0: 0002B03D 00000020 00002003)
[GPU] semaphore release 0x00000005 -> 0x80002000 (dma 0x00000008 offset 0x00000000)
```

With it, the fence wait in `sub_00228FA0` passes (`runs/ITEM/r6-proto`). Boot then stops at three more places. The first two are game-side configuration that BLiNX 2 and Burnout 3 already carry in their `main.c` (design D2):

1. **A title-built KEVENT.** Without `RECOMP_TITLE_KEVENTS=1`, the next step is a SIGSEGV in `pthread_mutex_lock` from `KeWaitForSingleObject` on guest 0x2372EC, a KEVENT that D3D builds inline (`sub_00226790`, `runs/ITEM/r6-proto`). This is the case `xboxrecomp-cli/docs/porting.md` describes.
2. **No vblank interrupt.** With the KEVENTs on but without `RECOMP_VBLANK=1`, the same wait in `sub_00226790` never returns (`runs/ITEM/r8-proto-kevents-only/sample.txt`).
3. **No fence mirror registered.** With both on, D3D's wait-for-idle in `sub_00228CE0` (reached from `sub_00228FA0+1352`) spins on PGRAPH 0x400B10. The toolkit updates that register from the fence word of a registered fence-mirror device only (`pgraph_fence_tick` → `fence_completed`), and Spartan registers none (`runs/ITEM/r9-proto-kevents-vblank-sample/sample.txt`). With `xbox_Nv2aMirrorFence(0x235528, 0x2C, 0x30)` added to a scratch `main.c`, the mirror reports "now written by the executor; mirror off" and the wait-for-idle passes. The title then loads its sound banks and creates render targets (320x240 down to 80x60), and boot stops in a `KeDelayExecutionThread` poll under `sub_001ADCA0` ← `sub_000DC6E0` (`runs/ITEM/r10-proto-mirror`). That stop is outside this change.

## What Changes

- **Toolkit (`nv2a_pb_exec.c`), the fix (D1):** a context DMA object's base and limit are read from instance memory when the bind method runs (`SET_CONTEXT_DMA_SEMAPHORE`, `SET_CONTEXT_DMA_REPORT`), the way PFIFO resolves the handle at bind: the handle is found in RAMHT (base and size from `PFIFO_RAMHT`), the context word gives the PRAMIN instance, and the base is `(word2 & 0xFFFFF000) | (word0 >> 20)`, the limit `word1`. `BACK_END_WRITE_SEMAPHORE_RELEASE` then writes at base plus `SET_SEMAPHORE_OFFSET`, and `GET_REPORT` at base plus its offset. A handle RAMHT does not hold falls back to base 0 with no limit, today's behaviour, with one log line. A write past the object's limit is refused and logged once, as the hardware would raise a DMA protection error instead of writing. A new accessor, `xbox_Nv2aAperture()`, exposes the aperture mapping to the executor. The ctest `tests/pb_semaphore` covers base, adjust, offset, missing handle, re-bind, limit and the report object. The prototype 7e705d4 does the semaphore half of this at the first release; the design lists what moves.
- **Spartan (`spartan/tca/src/main.c`, not a git repo, hand edit; D2):** register D3D's fence with `xbox_Nv2aMirrorFence(0x235528, 0x2C, 0x30)`, and default `RECOMP_TITLE_KEVENTS` and `RECOMP_VBLANK` to on when the environment does not set them, as BLiNX 2 and Burnout 3 do.
- **Tracker:** file the next stop (`KeDelayExecutionThread` poll under `sub_001ADCA0`) as its own item, and one scaffold item for the template defaults and the 0x400B10 fallback (below).

## Not in this change

- **Driving PGRAPH 0x400B10 from the executor's last release** when no fence mirror is registered. Decided in design D3: not here. Spartan needs the mirror line anyway (it is also the catch-up path and the executor-off fallback), and this change already moves both gate titles' fences from the mirror to the executor; one behaviour change at a time. It goes in the scaffold follow-up with its own A/B.
- **A scaffold follow-up (CLI, later push round).** `templates/new-game/src/main.c` defaults `RECOMP_TITLE_KEVENTS` and `RECOMP_VBLANK` to on the way `cat/src/main.c` does (every title so far has needed both, and `porting.md` already tells the porter to do it by hand), and carries the `xbox_Nv2aMirrorFence` line as a commented example with the three device offsets. The device pointer is per game, so the mirror line itself cannot be a default.
- **The other DMA objects** (surfaces, textures, vertex arrays, NOTIFY's notifier). Base 0 in every object the three titles bind for those purposes, read on hot paths, and `dma_resolve`'s image-overlap rules are built around the bare offset. The helper generalises when a title shows otherwise; the executor does not implement NOTIFY, so the notifier object is not written at all.
- **Full NV2A object emulation** (the RAMHT hash by channel, class and access checks, page-table objects). The three titles use one channel and linear objects only.
- The `wbinvd` at 0x0022C9F4 is a harmless no-op on this path, as on BLiNX 2.

## Impact

- **Spartan:** device creation completes, and boot reaches asset loading.
- **BLiNX 2 and Burnout 3: a behaviour change, not a no-op.** Their releases move to the fence word (0x80001000 and 0x803E6000 in the current builds), the mirror reports "now written by the executor; mirror off", and from then on the title's fence waits end when the executor consumes the release rather than when the title submitted it. That is the honest order and the one BLiNX 2 ran in until 2026-10-04, but it is GPU-paced where the mirror was not: the goldens must pass on Metal and on D3D11 under Proton, and flips/s and frame ms are compared against main on both (the CLAUDE.md thresholds: 25% fewer flips/s or 1.5x frame ms is a flag). A drop is reported to the user as a finding, not absorbed: it would mean the mirror has been hiding real waits. The catch-up path (`stop_salvage`, `fence caught up`) becomes live for both titles; its log lines are part of the gate record. Possible interaction, not a claim: the tracker item's one-off freezes are on the fence path.
- **Hosts:** the change is in the shared executor, so it applies to D3D11, Metal and the CPU backend alike. No backend-specific mirror is needed. The D3D11 and Metal report paths (`on_report(va)`) receive the corrected address and need no change.
