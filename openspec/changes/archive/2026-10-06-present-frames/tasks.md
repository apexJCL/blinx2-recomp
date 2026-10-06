## 1. Survey

- [x] 1.1 Read how the toolkit reads the env vars (design.md, Context). `RECOMP_PB_SCAN` and `RECOMP_PB_EXEC` both arm the DMA_PUT poll's report. The inventory needs `RECOMP_PB_SCAN` and the unhandled ranking needs `RECOMP_PB_EXEC`.
- [x] 1.2 Boot with `RECOMP_PB_SCAN=1 RECOMP_NV2A_TRACE=1` for 150 s (`analysis/bringup/pres-1` (local analysis, not published)): 8,460 segments, 0 unrecognised words, 387 distinct pairs.
- [x] 1.3 Rank the unhandled methods with the executor on (`pres-3`, `RECOMP_PB_UNHANDLED_ALL=1`). The table is in design.md.
- [x] 1.4 Fix the survey's method-name table against `nv2a_regs.h` (toolkit).

## 2. First frames

- [x] 2.1 Boot with `RECOMP_PB_EXEC=1 RECOMP_FB_DUMP=analysis/bringup/fb2/f` (local analysis, not published) (`pres-2`). This produced 22 BMPs: 8 black, then intro movie frames, then solid white from about 90 s.
- [x] 2.2 Look at the BMPs. They show the Microsoft Game Studios logo, the Artoon logo and intro cuts, drawn correctly with letterboxing.
- [x] 2.3 Show frames live on Windows with `RECOMP_FB_WINDOW=1 RECOMP_PB_EXEC=1` (Proton bench). Proton run 3 (`bench-logs/20261001-211249`): `[FBWIN] framebuffer window open (640x480)`, movie frames drawn from the YUY2 texture.

## 3. Fence honesty

- [x] 3.1 The executor implements SET_CONTEXT_DMA_SEMAPHORE, SET_SEMAPHORE_OFFSET and BACK_END_WRITE_SEMAPHORE_RELEASE (toolkit `nv2a_pb_exec.c`).
- [x] 3.2 `fence_mirrors_tick` steps aside per word once the executor has released onto it, and stays on as the fallback otherwise (toolkit `xbox_memory_layout.c`).
- [x] 3.3 Keep `xbox_Nv2aMirrorFence` in main.c as the fallback, and update its comment.
- [x] 3.4 Verify on macOS (`pres-3`, `pres-4`). Handover logged at the first release (value 5). 6,518 releases in 150 s, all to 0x80000000. `*(device+0x30)` equals the last release. The intro plays as far as it did with the mirror.
- [x] 3.5 Verify on Proton that the intro still plays with `RECOMP_PB_EXEC=1`, and that the run is unchanged with it unset.
  - Archive note (2026-10-06): done. The executor has run in every Proton bench and golden run since; it is now the default (6.4).

## 4. Seed hygiene

- [x] 4.1 `pipeline.sh disasm` seeds `analysis/icall_seeds.json`, generated with `icall_feedback seeds --xbe`, instead of the raw `icall_targets.json`.
- [ ] 4.2 Upstream note: the `icall_feedback.py` docstring (step 3) still shows seeding the raw database.
  - Archive note: open, moved to TASKS.md as an upstream nit. The toolkit's `icall_feedback.py` docstring (step 3) still seeds the raw `icall_targets.json`.

## 5. Builds

- [x] 5.1 macOS arm64: `cmake --build build` is clean (no new warnings in the changed files).
- [x] 5.2 llvm-mingw x86_64: `build-win` cross-compiles and links.

## 6. Next (not in this change)

- [x] 6.1 The 90 s stop. After the movie's white frame, PUT stops and the main thread sits in D3DX `sub_002F4EBC` under `sub_00172030` (`pres-4` thread dump). It reproduces with the executor off (`pres-1`, `hle-14`). Root cause: offset-frame functions did not publish ebp, so the JPEG loader's setjmp saved the wrong frame (toolkit `1d171cf`, regen). Next stall, the PGRAPH 0x400B10 wait, is handled in the ack tick (`518fbee`). See design.md.
- [x] 6.2 Stack overflow in `sub_00046720` after `plcom_tex` loads. Not a cycle: a lone int3 split `sub_00044900` and its interior branch targets were unresolved stubs that pop 4 and return, so the interpreter came back with its frame on the guest stack. Toolkit `_pass_branch_alias_closure` (merged at `fd76080`, change `disasm-branch-alias-closure`) plus regen: stubs 994 to 81, none hit in 240 s (`pres-23`; the old gen hits 0x00044C80 and then dies with SIGSEGV, `pres-23old`). It now reaches `stg0101_tex_us` at about 119 s. See design.md.
- [x] 6.5 Contiguous arena exhausted while loading `stg0101_tex_us`. Fixed by `kernel-memory-and-files`: the arena is a first-fit page allocator, and MmFreeContiguousMemory frees into it. In a 240 s run there is no exhaustion, and use peaks at 24.9 MB. The title now stalls at 105.8 s, because GetExitCodeThread never sees the loader worker exit: ObReferenceObjectByHandle returns a NULL object, so the title reads STILL_ACTIVE forever. Fixed by guest thread objects (`kernel-memory-and-files` 1.7): the title now reaches the stage 1-1 attract demo, where every batch is 3D (task 6.3).
- [x] 6.3 3D: vertex programs, combiners, texture stages 1-3, depth, in the order set out in design.md. The 3D batches are still skipped. The work is tracked in `render-vertex-programs` and then `render-gpu-backend`.
  - Archive note: moved and done there. Vertex programs (`render-vertex-programs`), combiners, texture stages and depth on the D3D11 and Metal backends (`render-gpu-backend`).
- [x] 6.4 Decide whether `RECOMP_PB_EXEC` becomes the default in main.c once Proton confirms it.
  - Archive note: done. `RECOMP_PB_EXEC` defaults on; `=0` turns it off (docs/env.md).
