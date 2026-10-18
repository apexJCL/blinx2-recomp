## Context

The NV2A runs pushbuffer methods against *context DMA objects*. A method that takes an offset, such as `SET_SURFACE_COLOR_OFFSET`, `SET_SEMAPHORE_OFFSET` or `GET_REPORT`, means "that many bytes into the object currently bound for this purpose". An object lives in PRAMIN (aperture 0x700000, 1 MB) as three words:

- word 0: class in bits 11:0 (0x002 DMA from memory, 0x003 DMA to memory, 0x03D DMA in memory), page-table and linear flags in bits 15:12, the **target** in bits 17:16 (0 VRAM, 2 PCI, 3 AGP), and the **adjust** (the low 12 bits of the base) in bits 31:20;
- word 1: the **limit**, the last valid byte offset;
- word 2: the **frame** (bits 31:12) plus present and read/write bits.

The pushbuffer names objects by *handle*. PFIFO maps a handle to an instance through RAMHT, a hash table in PRAMIN whose base and size come from `PFIFO_RAMHT` (0x002210: base in bits 8:4 in units of 4 KB, size in bits 17:16 as 4 KB << n, so 4 to 32 KB). Each RAMHT entry is `{handle, context}`. The context holds a valid bit (31), the channel (bits 28:24) and engine (17:16), and the instance in bits 15:0 in 16-byte units. The hash is xemu's `ramht_hash`: the handle folded by `log2(size) - 1` bits, XOR the channel id shifted in. On channel 0 with a 4 KB table that is the handle itself for the XDK's small handles, which is why Spartan's handle 8 sits at +0x40.

**When the hardware resolves.** PFIFO's puller translates the handle of every bind method (0x180..0x1FF) through RAMHT when it pulls the method, so PGRAPH holds the object's instance from the bind on. xemu splits it: `pfifo_run_puller` resolves the handle to the instance at pull time, but the object's three words are read when the object is used (`nv_dma_map` calls `nv_dma_load` at each semaphore release or report), so in xemu a rewrite of instance memory under a bound handle is seen by the next use. We cache base and limit at bind instead (below): it is the hardware's point of resolution for the handle, the XDK writes its DMA objects once at device creation and never rewrites a bound one, and it keeps the RAMHT scan and the log line to one per bind rather than one per release. The `cached` case of `tests/pb_semaphore` pins this choice. The Xbox is UMA, so VRAM, PCI and AGP targets all name the same physical RAM, and every object the XDK builds is linear (no page table follows the three words).

The toolkit's executor resolves every offset with `dma_resolve(offset)`, which assumes the object starts at physical 0. That holds for XDK D3D's surface, texture and vertex objects in all three titles. It does not hold for the semaphore object, which D3D aims at its fence page: physical 0x2000 in Spartan, 0x3E6000 in Burnout 3, 0 or 0x1000 in BLiNX 2 depending on the build (proposal, "Why").

## D1. Read the bound object's base from instance memory, at bind (toolkit)

A helper in `nv2a_pb_exec.c`, `ctxdma_lookup(handle, &base, &limit)` (the prototype's `sema_ctxdma_base`, made generic):

1. Reads `PFIFO_RAMHT` through `xbox_Nv2aAperture()` (new, in `xbox_memory_layout.c`/`.h`: the host mapping of guest 0xFD000000, or NULL). RAMHT base is bits 8:4 in 4 KB units; size is 4 KB << bits 17:16.
2. **Searches** RAMHT linearly for an entry whose handle matches and whose context has bit 31 set. The search stands in for the hash because the hash XORs in the channel id from `PFIFO_CACHE1_PUSH1`, which this runtime does not model (it is zero in the dump), and because handles are unique within a channel and XDK titles use one. On channel 0 the first hit is the hashed slot anyway. The scan reads at most 32 KB and runs once per bind.
3. Returns base `(w2 & 0xFFFFF000) | (w0 >> 20)` and limit `w1`. The target and flag bits are not checked (UMA; linear objects only) but word 0 is in the log line so a different object would show. When the aperture is not mapped or the handle is absent it reports "not found": the caller uses base 0 and no limit, today's behaviour.

**Resolve when the bind runs, not at the first use.** `NV097_SET_CONTEXT_DMA_SEMAPHORE` stores the handle (`sema_dma` in `struct nv2a_pb_gpu`, as before) and calls the helper; the result (handle, base, limit, found, and the log latches) lives in a per-purpose `struct ctxdma_bind` static in `nv2a_pb_exec.c`, `s_sema_bind`, the single source for the release. `NV097_SET_CONTEXT_DMA_REPORT` does the same into `s_report_bind` (today it returns without recording anything). That is what PFIFO does, it puts the log line at the moment the title bound the object, and a re-bind refreshes the cache the way hardware does. Nothing re-reads instance memory per release. The prototype resolves at the first release after a bind; the result is the same for every title seen, so this is a move, not a behaviour change, and it drops the `sema_base_valid` flag.

**The writes.** `BACK_END_WRITE_SEMAPHORE_RELEASE` writes at `dma_resolve(s_sema_bind.base + sema_offset)` (through `ctxdma_place`), so contiguous-window and image-overlap handling stay as they are; `get_report()` uses `dma_resolve(s_report_bind.base + (param & 0x00FFFFFF))`. Before writing, a release (4 bytes) or a report (16 bytes) whose end is past `limit + 1` of a found object is refused, logged once per purpose (the latch sits in each `ctxdma_bind`, so a refused report cannot hide a later refused release), as the hardware raises a DMA protection error and writes nothing; an object that was not found has no limit. `stop_salvage` (`nv2a_pb_scan.c`) re-runs a release through `nv2a_pb_exec_method`, so it is covered. The fence mirror's "same word" check compares against `nv2a_pb_exec_semaphore_last_va()`, which now reports the corrected address: that is why the mirror in the D2 run reports "now written by the executor; mirror off", and why it will say the same for BLiNX 2 and Burnout 3.

**Logging.** One line per bind whose result differs from the previous one for that purpose, capped at eight per purpose: `[GPU] semaphore context DMA <h>: base <b> limit <l> (RAMHT +<o>, instance <i>: w0 w1 w2)`, and the same with `report` for the report object; one line for a handle not found; one for a refused write. The first release line keeps its form. For BLiNX 2 and Burnout 3 the bind line plus the mirror's "mirror off" line are the record that the fence moved to the executor.

**Rejected: resolve every DMA object.** Surfaces, textures and vertex arrays are base 0 with a 128 MB limit in all three titles, and `dma_resolve`'s image-overlap rules assume the bare offset. Walking RAMHT for them would put a lookup on hot paths for no observed gain and would change tested renderer behaviour. The helper is generic so that change, if a title needs it, is a few lines.

**Rejected: a per-game override** (for example a `semaphore_base` key in `game.toml`). The hardware answer is in memory the title has already written, so a per-game constant would only repeat it, and it would be wrong for BLiNX 2 the next time its fence page moves.

**Rejected: register a fence mirror for Spartan and stop there.** A mirror alone *would* pass this wait, because `fence_mirrors_tick` copies submitted to completed. That is what BLiNX 2 and Burnout 3 have been running on, and it reports work as done before the executor has consumed it, which is the race the mirror's own comment describes. The executor would also keep writing physical 0, which is nobody's fence. The mirror is registered anyway (D2), but as the fallback and for the PGRAPH register, not as the fix.

## D2. Spartan's game-side defaults (`spartan/tca/src/main.c`)

Three lines, each with the comment style of `cat/src/main.c` and `b3/src/game/main.c`:

- `xbox_Nv2aMirrorFence(0x235528, 0x2C, 0x30);` right after `xbox_MemoryLayoutInit`. Device pointer 0x235528, submitted fence at +0x2C, completed-word pointer at +0x30. This is BLiNX 2's 0x2F1FB8 and Burnout 3's 0x35FB48, at the same offsets. `pgraph_fence_tick` drives PGRAPH 0x400B10, which `sub_00228CE0`'s wait-for-idle polls, from this device's fence word. With the executor writing that word, the mirror steps aside after the first release and stays as the catch-up path and the executor-off fallback.
- `RECOMP_TITLE_KEVENTS` and `RECOMP_VBLANK` default to `"1"` when unset (`recomp_env_set`, as `cat/src/main.c` does). D3D's vblank wait in `sub_00226790` needs both.

`spartan/tca` is not a repo and another agent builds in it, so the orchestrator applies these lines. They were verified in the scratch clone `wt/ITEM/tca` (`runs/ITEM/r10-proto-mirror`).

## D3. Decided: 0x400B10 keeps following the mirror; no executor fallback in this change

The question was whether `pgraph_fence_tick` should fall back to `nv2a_pb_exec_semaphore_last_value()` when `fence_completed` finds no mirror device, so that a new title passes D3D's wait-for-idle with no per-game line.

**Not in this change.** Three reasons:

1. It would not remove the per-game line. The mirror is also the catch-up path when a walk stops short of PUT and the only fence when the executor is off, so Spartan registers one regardless (D2), and the register then follows it as it does for BLiNX 2 and Burnout 3.
2. This change already moves both gate titles' fences from the mirror to the executor. The goldens and flips/s runs should measure that one change; a second source for 0x400B10 would blur any difference they show.
3. The fallback's beneficiary is a title with no mirror, and this fork tests none. It belongs with the scaffold follow-up, where a new title first runs without one.

**For the follow-up, the shape is fixed here:** the fallback applies only when `g_fence_mirror_count == 0` and the executor has released at least once; it never overrides a registered mirror; it logs once that the register follows the executor. The executor's last released value is the honest content of the register (the GPU's own copy of the last semaphore value), so the fallback is right in principle; it needs its own branch, a ctest, and runs on all three titles.

## Verification

| Run (`xbox-recomp/runs/ITEM/`) | Toolkit | Env | Result |
|---|---|---|---|
| r3-peekfields, r4-lldb | ac27175 (Spartan's build) | peek, lldb | fence word 0x80002000 = 3, releases at 0x80000000, PRAMIN dump |
| r5-base-3d37629 | posix-host/portability 3d37629 | sema, peek | the same hang: base reproduces |
| r6-proto | prototype | sema | releases at 0x80002000; fence wait passes; KEVENT SIGSEGV |
| r8-proto-kevents-only | prototype | TITLE_KEVENTS | stuck in the vblank wait `sub_00226790` |
| r9-proto-kevents-vblank-sample | prototype | + VBLANK | stuck in the wait-for-idle `sub_00228CE0` (0x400B10) |
| r10-proto-mirror | prototype + scratch `main.c` mirror | + VBLANK | past device creation, assets load, stops in a `KeDelayExecutionThread` poll |

Gate titles, from the bench logs (what the fix will change): Burnout 3 fence word 0x803E6000, BLiNX 2 fence word 0x80001000 since 2026-10-06 (0x80000000 before 2026-10-04), both with releases at 0x80000000 and the mirror on. The expected lines after the fix are in tasks 1.6 and 1.7.
