## 1. Runtime layout (toolkit, branch posix-host/portability)

- [x] 1.1 In `xbox_memory_layout.h`, make `XBOX_STACK_BASE`, `XBOX_STACK_SIZE` and `XBOX_KERNEL_DATA_BASE` expand to runtime globals (`g_xbox_stack_base`, `g_xbox_stack_size`, `g_xbox_region_base + 0x40000`) and declare them. TOP, HEAP_BASE and the worker macros keep deriving from them. Verify that the toolkit and cat build on macOS.
- [x] 1.2 In `xbox_MemoryLayoutInit`, right after the section loop, compute the region base, the stack base and size, and the heap start (design Decisions 1, 3, 4). Initialize `g_heap_next` there instead of statically. Fail with an error if the layout doesn't fit (Decision 5).
- [x] 1.3 Replace the fixed `FAKE_PRCB_VA`, `FAKE_TLS_VA`, `FAKE_RWDATA_VA`, `FAKE_TLS_BLOCK_VA` and `FAKE_TLS_THREAD_VA` addresses with `g_xbox_region_base + offset`.
- [x] 1.4 Remove the 64-section cap.
- [x] 1.5 Hand out worker stack slices only while they fit in the actual stack region (`kernel_thread.c`).

## 2. Verify

- [x] 2.1 Boot BLiNX 2 on macOS. The log shows 73 sections loaded, the region at 0x03040000, a 1 MB stack and a 14 MB heap, and none of them overlap the image.
- [x] 2.2 Show with a stub computation that the formula gives today's addresses for an image ending below 0x00700000, by reading the code or by a quick C check of the formula.
- [x] 2.3 Record how far BLiNX 2 boots now and the next blocker in design.md's Open Questions.
