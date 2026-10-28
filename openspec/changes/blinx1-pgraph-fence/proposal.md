## Why

BLiNX 1 (XDK 5558) freezes on its loading screen: the logo and an almost empty progress bar, every frame identical (`runs/xbe-sections/diag128*`, the 128 MB diagnostic bench). The main thread spins in D3D's wait-for-idle `sub_00139120` (from `sub_00139410` <- `sub_00135F00` <- `sub_00092340` <- `sub_000AF990`):

    00139140: mov eax, [ecx+0x400B10]   ; ecx = device[0x930], the NV2A registers
              mov edx, [edi]            ; edi = device[0x30], the fence word
              xor edx, eax
              test dl, 0x1F
              jne 00139140

The toolkit writes the fence into PGRAPH `0x400B10` bits 2..6, because that is where BLiNX 2's D3D (XDK 5849) looks: `((reg ^ fence << 2) & 0x7C) == 0`. 5558 compares bits 0..4. The register only matched when the two fields happened to agree, so the wait spun for ever on the first fence that did not.

Both XDKs write the register's value themselves, in the pushbuffer. `InsertFence` emits two methods back to back:

| XDK  | function     | subchannel 5, method 0x0310               | then                                 |
|------|--------------|-------------------------------------------|--------------------------------------|
| 5558 | `0x00139360` | `(pb << 5) \| (fence & 0x1F)`               | `BACK_END_WRITE_SEMAPHORE_RELEASE fence` |
| 5849 | `0x002E8050` | `((pb << 3 \| fence & 0x1F) << 2) \| (dev[0x40] & 3)` | the same                       |

So the place of the fence's five bits is in the pushbuffer, next to every release.

## What Changes

- **Toolkit, the executor (`nv2a_pb_exec.c`):** method `0x0310` on a subchannel other than 0 (subchannel 0's `0x0310` is Kelvin's `SET_DITHER_ENABLE`) sets a "previous method was the fence word" flag, which the next method of any kind clears. When that next method is `BACK_END_WRITE_SEMAPHORE_RELEASE`, the executor finds the shift (0..7) at which the word holds the released value's low five bits. Only a shift that alone fits counts; none or several fitting is no evidence. The first such pair sets the shift; a different shift then needs three pairs in a row (design D1). Logged as `[GPU] fence field in PGRAPH 0x400B10 at bits a..b` (and `stays; a pair fits bits a..b` for an outvoted pair). `nv2a_pb_exec_fence_shift()` returns it, -1 before any pair.
- **Toolkit, the scan (`nv2a_pb_scan.c`):** a walk that stops out of step forgets the pending word (`nv2a_pb_exec_fence_ref_forget`) before its salvaged release, which is not the word's partner.
- **Toolkit, the register tick (`xbox_Nv2aPgraphFenceTick`):** writes the five-bit field at the learned shift, bits 2..6 while none has been learned, and clears the old field's bits when the shift moves. Where the completed value comes from (mirror, or the executor's releases) is unchanged.
- **Toolkit, a ctest, `tests/pgraph_fence_5558`:** the 5849 pair, the 5558 pair, the near misses (a method between the pair; Kelvin's `0x0310`; a walk stop's salvaged release; a fence whose low five bits are 0), a stray pair after the shift is set, the cleared bits after the move, an ambiguous word, and both D3D waits evaluated against the register.

## Not in this change

- **Writing the whole `0x0310` word to the register.** That would be the faithful model (BLiNX 2 also reads the register's upper bits at `0x002E7E32`, as a pushbuffer position), but it changes what BLiNX 2 and Burnout 3 read today. Recorded in design D2 as a follow-up, not done here.
- **The object class bound to subchannel 5** (handle `0x12`). Not needed: the pair is identified by its position next to the release.
- **BLiNX 1's 128 MB diagnostic switch** stays a local diagnostic in the bench tree (owns memory).

## Impact

- **BLiNX 2, Burnout 3, Spartan, KUF (XDK 5849):** every unambiguous pair fits at shift 2, which is the old behaviour; before the first pair the tick also uses 2. Goldens unchanged (tasks 2.x).
- **JSRF (older D3D):** its fence is the release alone, with no `0x0310`, and it never reads `0x400B10`. Nothing is learned; unchanged.
- **BLiNX 1 (XDK 5558):** passes the loading screen on Metal.
- **SSX 3 (XDK 5558, `0x0022F470`):** its InsertFence writes the 5558 word, so the executor learns shift 0. Its game repo overrides that wait-for-idle in `recomp/src/recomp_manual.c` with a bits-2..6 compare, written for the old toolkit. Together they spin for ever. The override must go in the same commit that moves SSX 3's toolkit pin past this change (task 4.3); until then SSX 3 pins an older toolkit and is unaffected.
- **5558 titles need `RECOMP_PB_EXEC` on** (the default): with the executor off nothing learns the shift (design D3, `docs/env.md`).
- **Hosts:** the register is written by the shared ack loop and learned in the shared executor, so D3D11, Metal and the CPU backend see the same value. No backend code changes.
