## Decisions

1. **Bounded FIFO, not a free-never mode.** Holding every freed block would run
   the 64 MB heap out on titles that stream; JSRF frees and reloads scenes. A
   byte limit with a slot cap keeps the cost known, and oldest-first matches
   the window in which a stale pointer is likely to be read again.
2. **Drain before OOM.** A held block is never the reason a request fails: a
   request that would run out of heap empties the queue and retries once.
   Addresses still differ from a run with the switch off, so where a heap
   that is truly full fails can move.
3. **Duplicate guard.** A title that frees a block twice would otherwise put it
   in the queue twice, and the second release would free a block the heap may
   already have reused. The ctest fails without the guard.
4. **Under the heap lock.** `heap_free` takes the lock, then either pushes or
   calls `heap_free_locked`; pops call `heap_free_locked`, so the queue never
   races the allocator.
5. **Oversize blocks bypass the queue.** A block larger than the limit is
   freed at once. Held, it would evict every older block first, and a scene
   teardown frees its big buffers next to the small record the quarantine is
   there to keep (review F1). The suggested limit is 8192 KiB.
6. **A held block is still allocated to the heap.** `MmQueryAllocationSize`
   and `ExQueryPoolBlockSize` report its old size until it leaves the queue,
   and the heap's `[HEAP] free` lines fire at that release, not at the
   guest's free. `[HEAP-TRACE] free` is logged in `xbox_HeapFree`, so it
   still marks the guest's free.
7. **Opt-in, CONFIG tier.** It changes what addresses a title gets, so it never
   runs in goldens or by default (CLAUDE.md: opt-in features default OFF).

## Backends

Heap only; no renderer, audio or input change. Both GPU backends are unaffected.
